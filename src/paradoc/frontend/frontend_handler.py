"""Frontend handler for managing local static HTML frontends."""

import pathlib
import time
import webbrowser
from typing import TYPE_CHECKING

from paradoc.config import logger
from paradoc.utils import get_md5_hash_for_file

if TYPE_CHECKING:
    from paradoc import OneDoc


class FrontendHandler:
    """
    Handler for managing local static HTML frontends.
    Handles extraction, launching, and waiting for frontend connection.
    """

    def __init__(self, one_doc: "OneDoc", host: str = "localhost", port: int = 13579):
        """
        Initialize frontend handler.

        Args:
            one_doc: OneDoc instance
            host: WebSocket server host
            port: WebSocket server port
        """
        self.one_doc = one_doc
        self.host = host
        self.port = port
        self.resources_dir = self.get_resources_dir()
        self.zip_path = self.get_frontend_zip_path()
        self.hash_file = self.zip_path.with_suffix(".hash")
        self.index_html = self.resources_dir / "index.html"

    @staticmethod
    def get_resources_dir() -> pathlib.Path:
        """Get the resources directory path."""
        return pathlib.Path(__file__).parent / "resources"

    @staticmethod
    def get_frontend_zip_path() -> pathlib.Path:
        """Get the frontend.zip path."""
        return FrontendHandler.get_resources_dir() / "frontend.zip"

    def has_active_frontends(self) -> bool:
        """
        Check if there are any active frontends connected to the WebSocket server.

        Returns:
            True if at least one frontend is connected, False otherwise
        """
        try:
            from paradoc.frontend.ws_server import has_active_frontends

            return has_active_frontends(host=self.host, port=self.port)
        except Exception as e:
            logger.warning(f"Could not check for active frontends: {e}")
            return False

    def get_connected_frontends(self) -> list:
        """
        Get list of connected frontend IDs.

        Returns:
            List of frontend IDs
        """
        try:
            from paradoc.frontend.ws_server import get_connected_frontends

            return get_connected_frontends(host=self.host, port=self.port)
        except Exception as e:
            logger.warning(f"Could not get connected frontends: {e}")
            return []

    def ensure_frontend_extracted(self) -> bool:
        """
        Ensure frontend.zip is extracted to resources directory.
        Uses hash-based caching to avoid unnecessary extraction.

        Returns:
            True if frontend is ready, False otherwise
        """
        if not self.zip_path.exists():
            logger.error(f"frontend.zip not found at {self.zip_path}")
            return False

        # Check if we need to extract
        hash_content = get_md5_hash_for_file(self.zip_path).hexdigest()

        if self.index_html.exists() and self.hash_file.exists():
            with open(self.hash_file, "r") as f:
                hash_stored = f.read()
            if hash_content == hash_stored:
                logger.debug("Frontend already extracted and up to date")
                return True

        # Extract frontend
        logger.info("Extracting frontend...")
        return self._extract_frontend(hash_content)

    def _extract_frontend(self, hash_content: str) -> bool:
        """
        Extract frontend.zip to resources directory.

        Args:
            hash_content: MD5 hash of the zip file

        Returns:
            True if extraction successful, False otherwise
        """
        import zipfile

        try:
            logger.info(f"Extracting frontend from {self.zip_path} to {self.resources_dir}")
            with zipfile.ZipFile(self.zip_path) as archive:
                archive.extractall(self.resources_dir)

            # Update hash file
            with open(self.hash_file, "w") as f:
                f.write(hash_content)

            logger.info("Frontend extraction complete")
            return True
        except Exception as e:
            logger.error(f"Failed to extract frontend: {e}")
            return False

    def open_frontend(self) -> bool:
        """
        Open the frontend HTML file in the default browser.

        Returns:
            True if successful, False otherwise
        """
        if not self.index_html.exists():
            logger.error(f"Frontend HTML not found at {self.index_html}")
            return False

        try:
            url = self.index_html.resolve().as_uri()
            webbrowser.open(url)
            logger.info(f"OK Opened frontend in browser: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to open frontend in browser: {e}")
            return False

    def wait_for_frontend_connection(self, timeout: int = 10, check_interval: float = 0.5) -> bool:
        """
        Wait for a frontend to connect to the WebSocket server.

        Args:
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds

        Returns:
            True if a frontend connected, False if timeout
        """
        logger.info("Waiting for frontend to connect...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.has_active_frontends():
                connected = self.get_connected_frontends()
                logger.info(f"Frontend connected: {connected}")
                return True
            time.sleep(check_interval)

        logger.warning(f"Timeout waiting for frontend connection ({timeout}s)")
        return False

    def ensure_frontend_ready(self, auto_open: bool = True, wait_for_connection: bool = True) -> bool:
        """
        Ensure a frontend is ready to receive documents.
        If no frontends are connected, opens a new one and waits for connection.

        Args:
            auto_open: If True, automatically open a new frontend if none connected
            wait_for_connection: If True, wait for the frontend to connect before returning

        Returns:
            True if a frontend is ready, False otherwise
        """
        # Check if any frontends are already connected
        if self.has_active_frontends():
            connected = self.get_connected_frontends()
            logger.info(f"Frontend already connected: {connected}")
            return True

        if not auto_open:
            logger.warning("No frontends connected and auto_open=False")
            return False

        # Ensure WebSocket server is running
        try:
            from paradoc.frontend.ws_server import ensure_ws_server

            if not ensure_ws_server(host=self.host, port=self.port):
                logger.error("WebSocket server could not be started")
                return False
        except Exception as e:
            logger.error(f"Could not ensure WebSocket server is running: {e}")
            return False

        # Extract and open frontend
        if not self.ensure_frontend_extracted():
            return False

        if not self.open_frontend():
            return False

        # Wait for frontend to connect if requested
        if wait_for_connection:
            if not self.wait_for_frontend_connection():
                logger.warning("Frontend opened but did not connect in time")
                return False

        return True

    def print_frontend_status(self, embed_images: bool = False):
        """
        Print user-friendly status message about the frontend.

        Args:
            embed_images: Whether images are embedded or served via HTTP
        """
        if embed_images:
            print("OK Sent document to Reader with embedded images.")
            print("OK Images stored in browser IndexedDB - no HTTP server needed!")
            print("OK You can close this script now - the document is fully cached in the browser.")
        else:
            http_port = self.port + 1
            print("OK Sent document to Reader.")
            print(f"Serving JSON and assets via HTTP server at http://{self.host}:{http_port}/")
            print("The browser is open. Press Ctrl+C here to stop the servers.")
