"""Pytest configuration for frontend tests."""

import pytest
import time
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


def pytest_addoption(parser):
    """Add custom command line options for Playwright tests."""
    parser.addoption(
        "--pw-watch",
        action="store_true",
        default=False,
        help="Run Playwright tests with visual feedback (non-headless mode)",
    )
    parser.addoption(
        "--pw-duration",
        action="store",
        default="2",
        help="Duration in seconds to keep browser visible after each test (default: 2)",
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_playwright_installed():
    """Ensure Playwright browsers are installed before running tests."""
    try:
        # Try to launch Chromium to check if it's installed
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
            except Exception:
                # Chromium not installed, install it now
                print("\nChromium not found. Installing Playwright browsers...")
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"], check=True, capture_output=False
                )
                print("Playwright Chromium installed successfully.")
    except Exception as e:
        print(f"Warning: Could not verify Playwright installation: {e}")
        # Try to install anyway
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"], check=True, capture_output=False
            )
        except Exception as install_error:
            print(f"Failed to install Playwright: {install_error}")
            raise


@pytest.fixture(scope="session")
def browser(request):
    """Launch browser for the test session."""
    pw_watch = request.config.getoption("--pw-watch")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not pw_watch, slow_mo=500 if pw_watch else 0  # Slow down actions by 500ms when watching
        )
        yield browser
        browser.close()


@pytest.fixture
def context(browser: Browser):
    """Create a new browser context for each test."""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext, request):
    """Create a new page for each test."""
    page = context.new_page()
    yield page

    # If in watch mode, pause before closing the page so user can see results
    pw_watch = request.config.getoption("--pw-watch")
    if pw_watch:
        duration = float(request.config.getoption("--pw-duration"))
        print(f"\n[Playwright Watch Mode] Keeping browser open for {duration} seconds...")
        time.sleep(duration)

    page.close()


@pytest.fixture
def frontend_url(tmp_path):
    """
    Returns a function that can generate a frontend URL for a given document.
    The actual URL is determined after send_to_frontend() extracts the HTML.
    """

    def _get_url(one_doc):
        """Get the URL for the frontend HTML."""
        from paradoc.io.ast.exporter import ASTExporter

        # Find the extracted index.html
        exporter = ASTExporter(one_doc)
        resources_dir = Path(exporter.__class__.__module__.replace(".", "/")).parent / "io" / "ast" / "resources"
        resources_dir = Path(__file__).parent.parent.parent / "src" / "paradoc" / "io" / "ast" / "resources"
        index_html = resources_dir / "index.html"

        if index_html.exists():
            return f"file:///{index_html.as_posix()}"
        else:
            raise FileNotFoundError(f"Frontend HTML not found at {index_html}")

    return _get_url


@pytest.fixture
def wait_for_frontend():
    """Wait for frontend to load and initialize."""

    def _wait(page: Page, timeout: int = 10000):
        """
        Wait for the frontend to be ready.

        Args:
            page: Playwright page object
            timeout: Maximum time to wait in milliseconds
        """
        # Wait for the main app container to be visible
        page.wait_for_selector('[data-testid="app"], .app, #root', timeout=timeout)

        # Give React time to hydrate and render
        page.wait_for_timeout(1000)

    return _wait


@pytest.fixture(scope="session")
def ws_server():
    """
    Start WebSocket server in a background thread for the test session.
    This approach is more reliable in CI environments than subprocess spawning.
    """
    import threading
    import logging
    from paradoc.frontend.ws_server import run_server, ping_ws_server

    logger = logging.getLogger("paradoc.ws_server")
    host = "localhost"
    port = 13579

    # First check if a server is already running
    if ping_ws_server(host=host, port=port, timeout=1.0):
        logger.info(f"Test fixture: WebSocket server already running on {host}:{port}")
        yield {"host": host, "port": port}
        return

    # Start the server in a background daemon thread
    logger.info(f"Test fixture: Starting WebSocket server in background thread on {host}:{port}")

    server_thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True,  # Daemon thread will be killed when main thread exits
        name="WebSocketServerThread",
    )
    server_thread.start()

    # Wait for the server to become responsive
    max_wait = 10.0  # seconds
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < max_wait:
        if ping_ws_server(host=host, port=port, timeout=1.0):
            server_ready = True
            logger.info(f"Test fixture: WebSocket server is ready on {host}:{port}")
            break
        time.sleep(0.2)

    if not server_ready:
        pytest.fail(f"Failed to start WebSocket server on {host}:{port} after {max_wait}s")

    yield {"host": host, "port": port}

    # Note: We don't explicitly shut down the server as it's a daemon thread
    # and will be cleaned up when the test process exits
    logger.info("Test fixture: WebSocket server session completed")
