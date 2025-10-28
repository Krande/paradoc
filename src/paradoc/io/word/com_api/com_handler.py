
import gc
import time

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
                if (getattr(self._app, "BackgroundSavingStatus", 0) == 0 and
                    getattr(self._app, "BackgroundPrintingStatus", 0) == 0):
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