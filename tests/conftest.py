import os
import pathlib

import pytest


@pytest.fixture
def top_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().absolute().parent


@pytest.fixture
def test_dir():
    return pathlib.Path(os.getenv("PARADOC_temp_dir", "temp"))


@pytest.fixture
def files_dir(top_dir):
    return (top_dir / ".." / "files").resolve().absolute()
