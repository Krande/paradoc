"""Pytest configuration for frontend tests."""
import pytest
import time
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


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
def browser():
    """Launch browser for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser: Browser):
    """Create a new browser context for each test."""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext):
    """Create a new page for each test."""
    page = context.new_page()
    yield page
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
"""Frontend tests using Playwright."""

