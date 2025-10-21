"""WebSocket client wrapper for communicating with the Paradoc WS server."""
import json
from typing import Any, Dict, List

from paradoc.config import logger


class WSClient:
    """
    WebSocket client wrapper for sending document data to the Paradoc WS server.
    Handles connection management and message sending.
    """

    def __init__(self, host: str = "localhost", port: int = 13579):
        """
        Initialize WebSocket client.

        Args:
            host: WebSocket server host
            port: WebSocket server port
        """
        self.host = host
        self.port = port
        self.ws_url = f"ws://{host}:{port}"
        self._ws = None

    def connect(self, timeout: int = 3) -> bool:
        """
        Connect to the WebSocket server.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful, False otherwise
        """
        try:
            import websocket

            self._ws = websocket.create_connection(self.ws_url, timeout=timeout)
            logger.debug(f"Connected to WebSocket server at {self.ws_url}")
            return True
        except Exception as e:
            logger.error(f"Could not connect to frontend WebSocket at {self.ws_url}: {e}")
            return False

    def disconnect(self):
        """Close the WebSocket connection."""
        if self._ws:
            try:
                self._ws.close()
                logger.debug("Disconnected from WebSocket server")
            except Exception as e:
                logger.warning(f"Error closing WebSocket connection: {e}")
            finally:
                self._ws = None

    def send_manifest(self, manifest: Dict[str, Any]) -> bool:
        """
        Send manifest message to the WebSocket server.

        Args:
            manifest: Manifest data containing docId and sections

        Returns:
            True if successful, False otherwise
        """
        if not self._ws:
            logger.error("WebSocket not connected")
            return False

        try:
            msg = {"kind": "manifest", "manifest": manifest}
            self._ws.send(json.dumps(msg))
            logger.debug("Sent manifest to WebSocket server")
            return True
        except Exception as e:
            logger.error(f"Failed to send manifest: {e}")
            return False

    def send_section(self, section: Dict[str, Any], doc: Dict[str, Any]) -> bool:
        """
        Send a section bundle to the WebSocket server.

        Args:
            section: Section metadata (id, title, level, index)
            doc: Document data containing blocks

        Returns:
            True if successful, False otherwise
        """
        if not self._ws:
            logger.error("WebSocket not connected")
            return False

        try:
            msg = {"kind": "ast_section", "section": section, "doc": doc}
            self._ws.send(json.dumps(msg))
            logger.debug(f"Sent section {section.get('id')} to WebSocket server")
            return True
        except Exception as e:
            logger.error(f"Failed to send section: {e}")
            return False

    def send_embedded_images(self, images: Dict[str, Dict[str, str]]) -> bool:
        """
        Send embedded images to the WebSocket server.

        Args:
            images: Dictionary mapping image paths to {data: base64, mimeType: str}

        Returns:
            True if successful, False otherwise
        """
        if not self._ws:
            logger.error("WebSocket not connected")
            return False

        if not images:
            return True

        try:
            msg = {"kind": "embedded_images", "images": images}
            self._ws.send(json.dumps(msg))
            logger.debug(f"Sent {len(images)} embedded images to WebSocket server")
            return True
        except Exception as e:
            logger.error(f"Failed to send embedded images: {e}")
            return False

    def send_plot_data(self, plot_data: Dict[str, Any]) -> bool:
        """
        Send plot data to the WebSocket server.

        Args:
            plot_data: Dictionary mapping plot keys to plot data

        Returns:
            True if successful, False otherwise
        """
        if not self._ws:
            logger.error("WebSocket not connected")
            return False

        if not plot_data:
            return True

        try:
            msg = {"kind": "plot_data", "data": plot_data}
            self._ws.send(json.dumps(msg))
            logger.info(f"Sent {len(plot_data)} plots to WebSocket server")
            return True
        except Exception as e:
            logger.error(f"Failed to send plot data: {e}")
            return False

    def send_table_data(self, table_data: Dict[str, Any]) -> bool:
        """
        Send table data to the WebSocket server.

        Args:
            table_data: Dictionary mapping table keys to table data

        Returns:
            True if successful, False otherwise
        """
        if not self._ws:
            logger.error("WebSocket not connected")
            return False

        if not table_data:
            return True

        try:
            msg = {"kind": "table_data", "data": table_data}
            self._ws.send(json.dumps(msg))
            logger.info(f"Sent {len(table_data)} tables to WebSocket server")
            return True
        except Exception as e:
            logger.error(f"Failed to send table data: {e}")
            return False

    def send_complete_document(
        self,
        manifest: Dict[str, Any],
        sections: List[Dict[str, Any]],
        embedded_images: List[Dict[str, Dict[str, str]]] = None,
        plot_data: Dict[str, Any] = None,
        table_data: Dict[str, Any] = None,
    ) -> bool:
        """
        Send a complete document (manifest, sections, and optional data) to the WebSocket server.

        Args:
            manifest: Document manifest
            sections: List of section bundles
            embedded_images: Optional list of embedded image dicts (one per section)
            plot_data: Optional plot data dictionary
            table_data: Optional table data dictionary

        Returns:
            True if successful, False otherwise
        """
        # Send manifest
        if not self.send_manifest(manifest):
            return False

        # Send sections
        for bundle in sections:
            section = bundle.get("section", {})
            doc = bundle.get("doc", {})
            if not self.send_section(section, doc):
                return False

        # Send embedded images if provided
        if embedded_images:
            for images in embedded_images:
                if images and not self.send_embedded_images(images):
                    return False

        # Send plot data if provided
        if plot_data:
            if not self.send_plot_data(plot_data):
                return False

        # Send table data if provided
        if table_data:
            if not self.send_table_data(table_data):
                return False

        logger.info("Successfully sent complete document to WebSocket server")
        return True

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

