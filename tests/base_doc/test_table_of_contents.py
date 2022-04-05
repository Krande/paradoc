from paradoc import MY_DOCX_TMPL_BLANK, OneDoc


def test_no_toc(test_dir):
    o = OneDoc("temp/no_toc", work_dir=test_dir, create_dirs=True)
    o.compile("no_toc", main_tmpl=MY_DOCX_TMPL_BLANK)


def test_just_toc_has_toc(test_dir):
    o = OneDoc("temp/just_toc", work_dir=test_dir, create_dirs=True)
    o.compile("just_toc")


def test_has_toc(test_dir, files_dir):
    o = OneDoc(files_dir / "toc", work_dir=test_dir, create_dirs=True)
    o.compile("heading_toc_just_toc")
