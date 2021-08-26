import os
import pathlib

this_dir = pathlib.Path(__file__).resolve().absolute().parent
test_dir = pathlib.Path(os.getenv("PARADOC_temp_dir", "temp"))
files_dir = (this_dir / ".." / "files").resolve().absolute()
