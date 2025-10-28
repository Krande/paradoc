import pathlib
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterable

from paradoc.io.word.utils import logger

if TYPE_CHECKING:
    from .com_handler import WordSession


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
    with word_session_context() as session:
        if session is None:
            logger.debug("Skipping Word COM update - automation not available")
            return

        try:

            word = session.app
            # Convert to absolute path for COM
            abs_path = str(pathlib.Path(docx_file).absolute())
            word.Documents.Open(abs_path, ReadOnly=False)

            # update all figure / table numbers
            word.ActiveDocument.Fields.Update()

            # update Table of content / figure / table
            if len(word.ActiveDocument.TablesOfContents) > 0:
                word.ActiveDocument.TablesOfContents(1).Update()
            else:
                logger.debug("No table of contents found in document")

        except BaseException as e:
            logger.warning(f"Failed to update document via Word COM (non-critical): {e}")
        finally:
            session.close_all()
            session.quit()
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
