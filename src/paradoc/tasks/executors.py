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

from concurrent.futures import Future
from typing import Any, Protocol, runtime_checkable

from .cells import Cell


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
