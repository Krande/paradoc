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
        help="Run Playwright tests with visual feedback (non-headless mode)"
    )
    parser.addoption(
        "--pw-duration",
        action="store",
        default="2",
        help="Duration in seconds to keep browser visible after each test (default: 2)"
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
            except Exception as e:
                # Chromium not installed, install it now
                print("\nChromium not found. Installing Playwright browsers...")
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                    capture_output=False
                )
                print("Playwright Chromium installed successfully.")
    except Exception as e:
        print(f"Warning: Could not verify Playwright installation: {e}")
        # Try to install anyway
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                capture_output=False
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
            headless=not pw_watch,
            slow_mo=500 if pw_watch else 0  # Slow down actions by 500ms when watching
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
    Ensure WebSocket server is running for the test session.
    Uses session scope to start the server once and reuse it across all tests.
    """
    from paradoc.frontend.ws_server import ensure_ws_server, ping_ws_server
    import logging

    logger = logging.getLogger("paradoc.ws_server")
    host = "localhost"
    port = 13579

    # Try to ensure server is running
    logger.info(f"Test fixture: Ensuring WebSocket server is running on {host}:{port}")

    # Give it more time in CI environments
    wait_time = 10.0  # Increased from default 3.0 seconds

    if not ensure_ws_server(host=host, port=port, wait_seconds=wait_time):
        # If it still failed, try one more time with even more patience
        logger.warning("First attempt failed, retrying WebSocket server startup...")
        time.sleep(2)
        if not ensure_ws_server(host=host, port=port, wait_seconds=wait_time):
            pytest.fail(f"Failed to start WebSocket server on {host}:{port} after multiple attempts")

    logger.info(f"Test fixture: WebSocket server is running on {host}:{port}")

    # Verify it's actually responding
    if not ping_ws_server(host=host, port=port, timeout=5.0):
        pytest.fail(f"WebSocket server started but not responding on {host}:{port}")

    yield {"host": host, "port": port}

    # Note: We don't shut down the server here as it may be shared across tests
    # and we want it to persist for the entire test session
    logger.info("Test fixture: WebSocket server session completed")

