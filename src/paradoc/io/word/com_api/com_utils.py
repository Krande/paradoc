import functools
import multiprocessing as mp
import pathlib
import platform
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterable

from paradoc.io.word.utils import logger

if TYPE_CHECKING:
    from .com_handler import WordSession, _update_docx_worker

@functools.lru_cache(maxsize=1)
def is_word_com_available() -> bool:
    """Return True if the Word COM server appears to be registered and usable.

    1) Fast path: check ProgID is registered (no process launch).
    2) Fallback: very short COM instantiation with Dispatch if registry probe fails,
       guarded to avoid noisy errors; immediately release if successful.

    Note: This function initializes COM if needed but does NOT uninitialize it.
    COM will be cleaned up automatically when the process exits. This avoids issues
    in worker processes where COM might already be initialized.
    """
    if platform.system() != "Windows":
        return False

    try:
        import pythoncom
        # Fast, non‑intrusive: consult registry
        # Note: CLSIDFromProgID might not exist in all pythoncom versions
        if hasattr(pythoncom, 'CLSIDFromProgID'):
            pythoncom.CLSIDFromProgID("Word.Application")
            return True
    except Exception:
        pass

    # Fallback: try a minimal Dispatch to confirm availability.
    # This may briefly instantiate a COM proxy, but we avoid touching the UI.
    try:
        import win32com.client
        import pythoncom

        # Initialize COM if not already initialized
        # We don't uninitialize because:
        # 1. pythoncom doesn't reliably report if COM was already initialized
        # 2. Uninitializing can break other code that expects COM to be initialized
        # 3. COM will be cleaned up automatically when the process exits
        pythoncom.CoInitialize()

        app = win32com.client.Dispatch("Word.Application")
        try:
            # If we got here, COM server is available
            return True
        finally:
            # Clean up the Word instance we created
            try:
                app.Quit()
            except Exception:
                pass
    except Exception:
        return False
    except Exception as e:
        print(f"DEBUG is_word_com_available: Exception in fallback: {e}", flush=True)
        return False


def docx_update_isolated(docx_file: pathlib.Path, timeout_s: float = 120.0) -> bool:
    """
    Run the Word COM update in an isolated process. Returns True/False for success.
    """
    from .com_handler import _update_docx_worker

    ctx = mp.get_context("spawn")  # Windows default, explicit for clarity
    with ctx.Pool(processes=1) as pool:
        async_res = pool.apply_async(_update_docx_worker, (str(docx_file),))
        try:
            ok, msg = async_res.get(timeout=timeout_s)
        except TimeoutError:
            pool.terminate()
            # Optionally: kill spawned WINWORD if it lingered; usually Word exits with the worker.
            return False
        return bool(ok)


@contextmanager
def word_session_context() -> Iterable[WordSession | None]:
    """
    Context manager for Word COM automation that properly manages WordSession lifecycle.

    Yields the Word Application COM object if available, None otherwise.
    Ensures proper cleanup of COM handles on exit.

    Usage:
        with word_session_context() as word:
            if word is not None:
                # Use word application object
                doc = word.Documents.Open(path)
                # ... work with document ...
    """
    import sys

    if sys.platform != "win32":
        yield None
        return

    session = None
    try:
        from .com_handler import WordSession

        # Use early binding to avoid some COM issues
        session = WordSession(visible=False)
        yield session
    except (ModuleNotFoundError, ImportError):
        logger.warning(
            "win32com not available - Word COM automation will be skipped. "
            'Install with "conda install -c conda-forge pywin32" if needed.'
        )
        yield None
    except Exception as e:
        logger.warning(f"Unable to start Word COM automation - will be skipped. Error: {e}")
        yield None
    finally:
        if session is not None:
            try:
                session.close_all()
                session.quit()
            except Exception as e:
                logger.warning(f"Failed to cleanup Word session: {e}")


def docx_update(docx_file):
    """
    Update fields and table of contents in a .docx file using Word COM automation.
    This is optional - if it fails, the document will still be saved correctly,
    just without automatically updated field numbers.
    """
    p = pathlib.Path(docx_file)
    success = docx_update_isolated(p)
    if not success:
        # Keep it non-fatal for your pipeline, but you can log if you want
        logger.warning("Word COM update failed (non-critical)")


def close_word_docs_by_name(names: list) -> None:
    """
    Close Word documents by name using COM automation.
    This is optional - if it fails, documents will remain open which is non-critical.
    """
    with word_session_context() as word:
        if word is None:
            logger.debug("Skipping Word document close - COM automation not available")
            return

        try:
            if len(word.Documents) > 0:
                for doc in word.Documents:
                    try:
                        doc_name = doc.Name
                        if doc_name in names:
                            logger.info(f'Closing "{doc_name}"')
                            doc.Close()
                    except Exception as e:
                        logger.warning(f"Failed to close document: {e}")
            else:
                logger.debug(f"No Word docs named {names} found to be open")
        except Exception as e:
            logger.warning(f"Failed to access Word documents: {e}")
