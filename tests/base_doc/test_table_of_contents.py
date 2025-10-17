from paradoc import MY_DOCX_TMPL_BLANK, OneDoc


def test_no_toc(tmp_path):
    o = OneDoc("temp/no_toc", work_dir=tmp_path / "no_toc", create_dirs=True)
    o.compile("no_toc", main_tmpl=MY_DOCX_TMPL_BLANK)


def test_just_toc_has_toc(tmp_path):
    o = OneDoc("temp/just_toc", work_dir=tmp_path / "just_toc", create_dirs=True)
    o.compile("just_toc")


def test_has_toc(tmp_path, files_dir):
    o = OneDoc(files_dir / "toc", work_dir=tmp_path / "has_toc", create_dirs=True)
    o.compile("heading_toc_just_toc")
