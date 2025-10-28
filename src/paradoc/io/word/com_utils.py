import pathlib

from paradoc.io.word.utils import logger


def open_word_win32():
    import sys

    if sys.platform != "win32":
        return None

    try:
        import win32com.client

        # Use early binding to avoid some COM issues
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False

        return word
    except (ModuleNotFoundError, ImportError):
        logger.warning(
            "win32com not available - Word COM automation will be skipped. "
            'Install with "conda install -c conda-forge pywin32" if needed.'
        )
        return None
    except Exception as e:
        logger.warning(f"Unable to start Word COM automation - will be skipped. Error: {e}")
        return None


def docx_update(docx_file):
    """
    Update fields and table of contents in a .docx file using Word COM automation.
    This is optional - if it fails, the document will still be saved correctly,
    just without automatically updated field numbers.
    """
    word = open_word_win32()
    if word is None:
        logger.debug("Skipping Word COM update - automation not available")
        return

    doc = None
    try:
        # Convert to absolute path for COM
        abs_path = str(pathlib.Path(docx_file).absolute())
        doc = word.Documents.Open(abs_path, ReadOnly=False)

        # update all figure / table numbers
        word.ActiveDocument.Fields.Update()

        # update Table of content / figure / table
        if len(word.ActiveDocument.TablesOfContents) > 0:
            word.ActiveDocument.TablesOfContents(1).Update()
        else:
            logger.debug("No table of contents found in document")

    except Exception as e:
        logger.warning(f"Failed to update document via Word COM (non-critical): {e}")
    finally:
        # Clean up in reverse order
        if doc is not None:
            try:
                doc.Close(SaveChanges=True)
            except Exception as e:
                logger.warning(f"Failed to close document: {e}")

        if word is not None:
            try:
                word.Quit()
            except Exception as e:
                logger.warning(f"Failed to quit Word application: {e}")


def close_word_docs_by_name(names: list) -> None:
    """
    Close Word documents by name using COM automation.
    This is optional - if it fails, documents will remain open which is non-critical.
    """
    word = open_word_win32()
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
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception as e:
                logger.warning(f"Failed to quit Word application: {e}")
