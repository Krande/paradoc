"""Worker entrypoint for PixiSubprocessExecutor.

Invoked by the controlling Runner as:

    pixi run --manifest-path <pixi.toml> -e <env> python -m paradoc.tasks.run_cell <tmpdir>

Reads `(cell, parent_result)` from `<tmpdir>/input.pkl`, executes the
cell, writes either `<tmpdir>/output.pkl` (success) or
`<tmpdir>/error.pkl` (exception). Exit code mirrors success/failure so
the controlling side can fall back gracefully if pickling the result
itself fails.

Why temp files rather than stdin/stdout: a task body that calls
`print(...)` or shells out to a solver writes to stdout. Mixing that
with the binary pickle channel breaks the protocol. Temp files keep
the streams orthogonal.
"""

from __future__ import annotations

import pickle
import sys
import traceback
from pathlib import Path


def main(tmpdir: Path) -> int:
    input_path = tmpdir / "input.pkl"
    output_path = tmpdir / "output.pkl"
    error_path = tmpdir / "error.pkl"

    with input_path.open("rb") as fh:
        payload = pickle.load(fh)
    cell = payload["cell"]
    parent_result = payload["parent_result"]
    extra_kwargs = payload.get("extra_kwargs") or {}

    try:
        merged_kwargs = {**cell.kwargs, **extra_kwargs}
        if parent_result is None:
            result = cell.task(**merged_kwargs)
        else:
            result = cell.task(parent_result, **merged_kwargs)
    except BaseException as exc:
        # Pickle the exception so the controlling side can re-raise.
        # If the exception itself isn't picklable (rare — most are), fall
        # back to a RuntimeError carrying the formatted traceback string,
        # so the build doesn't deadlock on a "no output.pkl, no error.pkl"
        # ambiguous state.
        try:
            with error_path.open("wb") as fh:
                pickle.dump(exc, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError):
            tb = traceback.format_exc()
            with error_path.open("wb") as fh:
                pickle.dump(RuntimeError(f"unpicklable exception: {tb}"), fh,
                            protocol=pickle.HIGHEST_PROTOCOL)
        return 1

    try:
        with output_path.open("wb") as fh:
            pickle.dump(result, fh, protocol=pickle.HIGHEST_PROTOCOL)
    except (pickle.PicklingError, TypeError) as exc:
        # The task returned something that doesn't pickle. Surface that
        # as an error so the user knows to fix the result type.
        with error_path.open("wb") as fh:
            pickle.dump(
                TypeError(f"task result is not picklable: {type(result).__name__}: {exc}"),
                fh,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        return 1

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m paradoc.tasks.run_cell <tmpdir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
