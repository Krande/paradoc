import os
import pathlib
import platform
import shutil
import sys

from paradoc.config import logger


def ensure_pandoc_path():
    """
    Set the pandoc path for pypandoc

    :param pandoc_path: Path to the pandoc executable
    :return:
    """
    import pypandoc
    pandoc_path = None

    try:
        pypandoc._ensure_pandoc_path()
        return None
    except OSError:
        logger.debug("pypandoc could not find pandoc, attempting to locate it manually")

    pandoc_exe = shutil.which("pandoc")
    if pandoc_exe is not None:
        pandoc_path = pathlib.Path(pandoc_exe)
    if pandoc_path is None:
        if platform.system() == "Windows":
            pandoc_path = pathlib.Path(sys.prefix) / "Library" / "bin" / "pandoc.exe"
        else:
            pandoc_path = pathlib.Path(sys.prefix) / "bin" / "pandoc"

    if pandoc_path is None:
        raise OSError("Pandoc executable not found. Please install Pandoc.")

    os.environ["PYPANDOC_PANDOC"] = str(pandoc_path)
    pypandoc._ensure_pandoc_path()
    return None