from __future__ import annotations

import ctypes
import gc
import pathlib
import time
from typing import Final

import pythoncom
import pywintypes
import win32com.client as win32


class WordSession:
    def __init__(self, visible: bool = False):
        # STA init for this thread
        pythoncom.CoInitialize()
        self._app = win32.gencache.EnsureDispatch("Word.Application")
        self._app.Visible = visible

        # Reduce async/background/race hazards
        self._app.DisplayAlerts = 0  # wdAlertsNone
        self._app.Options.BackgroundSave = False
        # Background printing can still be triggered by some addins/templates
        # We’ll actively wait on both flags before quitting.

    @property
    def app(self):
        return self._app

    def wait_for_background(self, timeout_s: float = 15.0) -> None:
        start = time.perf_counter()
        while True:
            try:
                if (
                    getattr(self._app, "BackgroundSavingStatus", 0) == 0
                    and getattr(self._app, "BackgroundPrintingStatus", 0) == 0
                ):
                    return
            except pywintypes.com_error:
                # If Word is already gone, nothing to wait for.
                return
            if time.perf_counter() - start > timeout_s:
                return
            time.sleep(0.05)

    def close_all(self) -> None:
        try:
            # Close any open docs without prompting
            docs = list(self._app.Documents)  # materialize to detach enumeration
            for d in docs:
                try:
                    d.Close(SaveChanges=0)  # wdDoNotSaveChanges
                except pywintypes.com_error:
                    pass
        except pywintypes.com_error:
            pass

    def quit(self) -> None:
        # Ensure we do not quit while background tasks are active
        self.wait_for_background()
        try:
            self._app.Quit()
        except pywintypes.com_error:
            pass
        # Drop proxies and collect before CoUninitialize
        self._app = None
        gc.collect()
        pythoncom.CoUninitialize()

    # Optional context manager
    def __enter__(self) -> "WordSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close_all()
        self.quit()


# Windows error-mode flags
SEM_FAILCRITICALERRORS: Final[int] = 0x0001
SEM_NOGPFAULTERRORBOX: Final[int] = 0x0002
SEM_NOOPENFILEERRORBOX: Final[int] = 0x8000


def _suppress_windows_error_ui() -> None:
    # Prevents Windows “application error” dialog boxes in the worker
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX)
    except Exception:
        pass


def _wait_background(app, timeout_s: float = 15.0) -> None:
    start = time.perf_counter()
    while True:
        try:
            if getattr(app, "BackgroundSavingStatus", 0) == 0 and getattr(app, "BackgroundPrintingStatus", 0) == 0:
                return
        except pywintypes.com_error:
            return
        if time.perf_counter() - start > timeout_s:
            return
        time.sleep(0.05)


def _update_docx_worker(docx_path_str: str) -> tuple[bool, str]:
    """
    This runs in a child process. Returns (ok, message).
    """
    _suppress_windows_error_ui()
    pythoncom.CoInitialize()  # STA for this process
    app = None
    doc = None
    try:
        # Early binding helps reduce late-call surprises
        app = win32.gencache.EnsureDispatch("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        app.Options.BackgroundSave = False

        docx_path = pathlib.Path(docx_path_str)
        abs_path = str(docx_path.absolute())
        doc = app.Documents.Open(abs_path, ReadOnly=False)

        # Update fields
        app.ActiveDocument.Fields.Update()

        # Update ToC if present
        if len(app.ActiveDocument.TablesOfContents) > 0:
            app.ActiveDocument.TablesOfContents(1).Update()

        doc.Save()
        ok = True
        msg = "Updated fields/ToC."
    except BaseException as e:
        ok = False
        msg = f"COM worker failed: {e!r}"
    finally:
        # Try hard to close/quit cleanly; swallow COM errors
        try:
            if doc is not None:
                try:
                    doc.Close(SaveChanges=0)
                except pywintypes.com_error:
                    pass
        finally:
            try:
                if app is not None:
                    _wait_background(app)
                    try:
                        app.Quit()
                    except pywintypes.com_error:
                        pass
            finally:
                # Ensure all proxies are gone before CoUninitialize
                doc = None
                app = None
                import gc

                gc.collect()
                pythoncom.CoUninitialize()
    return (ok, msg)
