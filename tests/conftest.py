import pathlib

import pytest


def pytest_addoption(parser):
    """Register custom command line options used by frontend tests.

    Declaring them here (root tests conftest) ensures pytest recognizes the
    options before parsing, even if frontend tests are not collected.
    """
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


@pytest.fixture
def top_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().absolute().parent


@pytest.fixture
def files_dir(top_dir):
    return (top_dir / ".." / "files").resolve().absolute()
