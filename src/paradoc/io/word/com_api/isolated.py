"""Isolated process execution for Word COM operations.

This module provides utilities to run Word COM operations in a separate process,
which helps suppress C stack error logs and improves stability.
"""

import ctypes
import gc
import multiprocessing as mp
import sys
from typing import Any, Callable

from paradoc.config import logger

# Windows error-mode flags for suppressing error dialogs
SEM_FAILCRITICALERRORS = 0x0001
SEM_NOGPFAULTERRORBOX = 0x0002
SEM_NOOPENFILEERRORBOX = 0x8000


def _suppress_windows_error_ui() -> None:
    """Suppress Windows error dialog boxes in worker processes."""
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX)  # type: ignore[attr-defined]
    except Exception:
        pass


def _init_pool_worker() -> None:
    """Initialize each pool worker process with COM support.

    This is called once per worker process when the pool is created.
    It ensures COM is properly initialized before any tasks run.
    """
    _suppress_windows_error_ui()

    try:
        import pythoncom
        # COINIT_APARTMENTTHREADED = 2 (STA mode, required for Word COM)
        pythoncom.CoInitializeEx(2)
    except Exception:
        # If initialization fails here, tasks will fail with proper error messages
        pass



def _isolated_worker(func: Callable, args: tuple, kwargs: dict, redirect_stdout: bool) -> tuple[bool, Any, str, str]:
    """
    Worker function that runs in an isolated process.

    Args:
        func: Function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        redirect_stdout: Whether to capture stdout/stderr

    Returns:
        Tuple of (success: bool, result: Any, message: str, output: str)

    Note:
        We also initialize COM in this worker thread to be absolutely sure the
        thread that invokes Word COM is COM-initialized (STA). The pool
        initializer sets process-level state, but COM is a per-thread init.
    """
    # Capture stdout/stderr if requested
    output = ""
    old_stdout = None
    old_stderr = None

    if redirect_stdout:
        from io import StringIO
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

    result = None
    success = False
    message = ""

    try:
        try:
            import pythoncom  # type: ignore
            # Explicitly initialize COM in STA mode on this thread
            # COINIT_APARTMENTTHREADED = 2
            # We call this even if pool initializer already did, to ensure COM is initialized
            # on this thread. Multiple calls are safe (reference counted).
            pythoncom.CoInitializeEx(2)
        except Exception:
            # If initialization fails, continue anyway - will fail later with clear error
            pass

        result = func(*args, **kwargs)
        success = True
        message = "Success"
    except Exception as e:
        success = False
        message = f"Worker failed: {e!r}"
        import traceback
        message += f"\n{traceback.format_exc()}"
    finally:
        try:
            if redirect_stdout and old_stdout is not None and old_stderr is not None:
                output = sys.stdout.getvalue() + "\n" + sys.stderr.getvalue()
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            gc.collect()
        except:
            pass
        # Note: We don't call CoUninitialize here because:
        # 1. pythoncom doesn't reliably report if we initialized COM or it was already initialized
        # 2. COM will be cleaned up automatically when the worker process exits
        # 3. Uninitializing prematurely can break subsequent operations in the same worker

    return (success, result, message, output)


def run_word_operation_isolated(
    func: Callable,
    *args,
    timeout_s: float = 120.0,
    redirect_stdout: bool = True,
    **kwargs
) -> tuple[bool, Any, str]:
    """
    Run a Word COM operation in an isolated process.

    This helps suppress C stack error logs and improves stability by isolating
    COM operations from the main process.

    Args:
        func: Function to execute (must be picklable)
        *args: Positional arguments for the function
        timeout_s: Timeout in seconds
        redirect_stdout: Whether to redirect and suppress stdout/stderr from worker
        **kwargs: Keyword arguments for the function

    Returns:
        Tuple of (success: bool, result: Any, message: str)

    Example:
        def create_doc(output_path):
            from paradoc.io.word.com_api import WordApplication
            with WordApplication(visible=False) as word_app:
                doc = word_app.create_document()
                doc.add_heading("Test", level=1)
                doc.save(output_path)
            return str(output_path)

        success, result, msg = run_word_operation_isolated(
            create_doc,
            "output.docx"
        )
    """
    ctx = mp.get_context("spawn")  # Windows default, explicit for clarity
    success: bool = False
    result: Any = None
    message: str = ""
    output: str = ""

    # Use a single-process pool with an initializer that sets up COM in the worker
    with ctx.Pool(processes=1, initializer=_init_pool_worker) as pool:
        async_res = pool.apply_async(
            _isolated_worker,
            (func, args, kwargs, redirect_stdout)
        )
        try:
            success, result, message, output = async_res.get(timeout=timeout_s)
        except mp.TimeoutError:
            pool.terminate()
            pool.join()
            return (False, None, f"Operation timed out after {timeout_s}s")
        except Exception as e:
            pool.terminate()
            pool.join()
            return (False, None, f"Pool error: {e!r}")

    # Log captured output if any
    if redirect_stdout and output:
        logger.info(output.rstrip())

    return (success, result, message)

