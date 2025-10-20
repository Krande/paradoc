import pathlib

import pytest


@pytest.fixture
def top_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().absolute().parent


@pytest.fixture
def files_dir(top_dir):
    return (top_dir / ".." / "files").resolve().absolute()
