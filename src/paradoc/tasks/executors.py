"""Executor — the dispatch boundary for cell evaluation.

This is the seam that lets paradoc.tasks scale from single-process today
to a NATS-backed worker pool tomorrow without rewriting the Runner. The
contract is intentionally narrow: take a Cell + its parent's result,
return a Future. Concurrency, isolation, and remote dispatch are all
hidden behind it.

Implementations on the roadmap:

- `InProcessExecutor` (here) — direct call in the runner's process.
  No isolation, no parallelism. The v0 default; useful for tests and
  for tasks declaring `env="default"`.
- `PixiSubprocessExecutor` (future) — `pixi run -e <task.env> python -m
  paradoc.run_cell <pickled>`. Single-machine multi-env isolation.
- `NatsExecutor` (future) — publish to a NATS subject, await reply.
  Workers in a pool subscribe; each worker has pixi available locally
  for env selection. Same NATS server as adapy, separate subject space.

The Runner stays oblivious to which executor it holds. Switching is a
constructor argument, nothing else.

What this design relies on:

- `Cell` is picklable. Confirmed by `tasks/cells.py` design — TaskFn
  has stable `__module__`/`__qualname__`; kwargs are typically
  primitives.
- `parent_result` is picklable. For the adapy verification pipeline,
  that means `ada.Assembly` must round-trip; we did that work in
  Q8 (commits 2eaee4df / 6c1dd79d in adapy).

Failure semantics: any exception raised inside `submit()` (or the
underlying call) is set on the returned Future. The runner reads
`future.result()` and re-raises, so the call site sees the original
exception with traceback intact (modulo the wire format for the
remote-dispatch cases, where the worker pickles the exception back).
"""

from __future__ import annotations

import logging
import os
import pickle
import shutil
import subprocess
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from .cells import Cell

logger = logging.getLogger(__name__)


@runtime_checkable
class Executor(Protocol):
    """Submit-and-await interface for cell evaluation."""

    def submit(self, cell: Cell, parent_result: Any) -> Future:
        """Schedule the cell for execution and return a Future of its result."""

    def shutdown(self) -> None:
        """Release any executor-held resources (workers, sockets, ...)."""


class InProcessExecutor:
    """Direct in-process call. No isolation, no parallelism.

    Default executor for the v0 runner. Use cases:
    - Pytest / unit-test pipelines where subprocess overhead bites.
    - Tasks declaring `env="default"` (no env switch needed).
    - Debug runs where stack traces should land in the runner's process.
    """

    def submit(self, cell: Cell, parent_result: Any) -> Future:
        future: Future = Future()
        try:
            if parent_result is None:
                result = cell.task(**cell.kwargs)
            else:
                result = cell.task(parent_result, **cell.kwargs)
            future.set_result(result)
        except BaseException as exc:  # noqa: BLE001 — explicit propagation through Future
            future.set_exception(exc)
        return future

    def shutdown(self) -> None:
        return None


class PixiSubprocessError(RuntimeError):
    """Raised when the worker subprocess exits non-zero with no error.pkl."""

    def __init__(self, returncode: int, stderr: str, cmd: list[str]) -> None:
        super().__init__(
            f"pixi worker exited {returncode} with no error.pkl\n"
            f"cmd: {' '.join(cmd)}\n"
            f"stderr:\n{stderr}"
        )
        self.returncode = returncode
        self.stderr = stderr
        self.cmd = cmd


class PixiSubprocessExecutor:
    """Per-cell `pixi run -e <env> python -m paradoc.tasks.run_cell <tmpdir>`.

    Each cell runs in its own subprocess, inside a pixi env selected
    from `task.env` via `env_map`. Marshaling uses temp files
    (input.pkl / output.pkl / error.pkl) so the cell's stdout/stderr
    stay free for solver / print output.

    The Future-returning interface is backed by a ThreadPoolExecutor so
    the Runner can fan out concurrent subprocesses once it learns to
    submit-all-then-await. The v0 Runner still iterates serially; this
    executor doesn't yet pay off in wall-clock, but the seam is in
    place.

    Constructor args
    ----------------
    pixi_toml : Path
        Manifest passed to `pixi run --manifest-path`. Usually the
        consumer repo's pixi.toml.
    env_map : Mapping[str, str]
        Alias -> pixi env name. The future paradoc.toml `[paradoc.envs]`
        section populates this. `"default"` is the fallback when
        `task.env is None`.
    max_workers : int | None
        Forwarded to the underlying ThreadPoolExecutor.
    pixi_executable : str
        For testability; defaults to "pixi" on PATH.
    extra_pixi_args : list[str] | None
        Additional args inserted before `python -m paradoc.tasks.run_cell`
        (eg `--frozen` for reproducible CI builds).
    extra_env : Mapping[str, str] | None
        Environment variables forwarded into the subprocess on top of
        the controlling process's env. Use this for things pixi can't
        inject — solver license paths, scratch directories, license
        server tokens, PYTHONPATH overrides for dev installs.
    """

    def __init__(
        self,
        pixi_toml: Path,
        env_map: Mapping[str, str],
        *,
        max_workers: Optional[int] = None,
        pixi_executable: str = "pixi",
        extra_pixi_args: Optional[list[str]] = None,
        extra_env: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.pixi_toml = Path(pixi_toml)
        self.env_map = dict(env_map)
        self.pixi_executable = pixi_executable
        self.extra_pixi_args = list(extra_pixi_args or [])
        self.extra_env = dict(extra_env or {})
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="paradoc-pixi")

    def submit(self, cell: Cell, parent_result: Any) -> Future:
        return self._pool.submit(self._run_one, cell, parent_result)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=True)

    # ---------------- internals ----------------

    def _resolve_env(self, cell: Cell) -> str:
        """Map `task.env` (string or callable) to a concrete pixi env name."""
        raw = cell.task.env
        if callable(raw):
            raw = raw(cell.kwargs)
        if raw is None:
            raw = "default"
        if raw not in self.env_map:
            raise KeyError(
                f"task {cell.task.qualname!r} declared env={raw!r}, "
                f"but no such alias is in env_map (known: {sorted(self.env_map)!r})"
            )
        return self.env_map[raw]

    def _run_one(self, cell: Cell, parent_result: Any) -> Any:
        env = self._resolve_env(cell)
        tmpdir = Path(tempfile.mkdtemp(prefix="paradoc-cell-"))
        try:
            input_path = tmpdir / "input.pkl"
            output_path = tmpdir / "output.pkl"
            error_path = tmpdir / "error.pkl"

            with input_path.open("wb") as fh:
                pickle.dump(
                    {"cell": cell, "parent_result": parent_result},
                    fh,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )

            cmd = [
                self.pixi_executable,
                "run",
                "--manifest-path",
                str(self.pixi_toml),
                "-e",
                env,
                *self.extra_pixi_args,
                "python",
                "-m",
                "paradoc.tasks.run_cell",
                str(tmpdir),
            ]
            logger.debug(f"submit {cell!r} env={env!r}")
            sub_env = {**os.environ, **self.extra_env} if self.extra_env else None
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=sub_env)

            if error_path.exists():
                with error_path.open("rb") as fh:
                    exc = pickle.load(fh)
                # Re-raise the worker's exception in the controlling thread.
                raise exc

            if proc.returncode != 0:
                # No error.pkl + non-zero exit = pixi itself failed (env
                # not found, manifest invalid, etc).
                raise PixiSubprocessError(proc.returncode, proc.stderr, cmd)

            with output_path.open("rb") as fh:
                return pickle.load(fh)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
