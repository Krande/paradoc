import contextlib
import os
import pathlib
import shutil

import pypandoc

from paradoc import OneDoc
from paradoc.citation import FILTER_PATH as SHELF_CITATION_FILTER
from paradoc.utils import copy_figures_to_dist


@contextlib.contextmanager
def _shelf_citation_env(one: OneDoc):
    """Set the env vars the shelf-citation pandoc filter consumes.

    pypandoc inherits the parent env when it spawns pandoc, which in
    turn inherits when it spawns the `--filter` subprocess. We restore
    the original env on exit so a long-running process (test runner,
    notebook) doesn't accumulate stale state.
    """
    keys = ("PARADOC_BIBLIOGRAPHY", "PARADOC_SHELF_BASE_URL")
    prior = {k: os.environ.get(k) for k in keys}
    if one.bibliography_file is not None:
        os.environ["PARADOC_BIBLIOGRAPHY"] = str(one.bibliography_file)
    else:
        os.environ.pop("PARADOC_BIBLIOGRAPHY", None)
    if one.shelf_base_url:
        os.environ["PARADOC_SHELF_BASE_URL"] = one.shelf_base_url
    else:
        os.environ.pop("PARADOC_SHELF_BASE_URL", None)
    try:
        yield
    finally:
        for k, v in prior.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


THIS_DIR = pathlib.Path(__file__).parent


class HTMLExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def _build_styled_html(self, include_navbar: bool = True) -> str:
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])
        app_str = """\n\n\\appendix\n\n"""
        md_app_str = "\n\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

        extra_args = [
            "-M2GB",
            "+RTS",
            "-K64m",
            "-RTS",
            f"--metadata-file={one.metadata_file}",
        ]
        # Shelf citation filter is appended after pandoc-crossref so
        # cross-references are already resolved by the time we walk
        # Cite nodes. The filter no-ops when its env vars are unset.
        filters = ["pandoc-crossref", str(SHELF_CITATION_FILTER)]
        with _shelf_citation_env(one):
            html_str = pypandoc.convert_text(
                combined_str,
                one.FORMATS.HTML,
                format="markdown",
                extra_args=extra_args,
                filters=filters,
            )

        js_script = ""
        if include_navbar:
            js_script = "<script>\n" + open(THIS_DIR / "js/navbar.js", "r").read() + "\n</script>"

        app_head_text = ""
        if len(one.md_files_app) > 0:
            app_file1 = open(one.md_files_app[0].path, "r").read()
            for line in app_file1.splitlines():
                if line.startswith("# "):
                    app_head_text = line[2:]
                    break

        styled_html = f"""<html>
        <head>
        <meta name=\"data-appendix-start\" content=\"{app_head_text}\">
        <link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\">
        <script type=\"text/javascript\" async
            src=\"https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js\">
        </script>
        {js_script}
        </head>
        <body>
        <div class=\"content\">
        {html_str}
        </div>
        </body>
        </html>"""
        return styled_html

    def export(self, dest_file, include_navbar=True):
        one = self.one_doc

        # Ensure figures are copied
        copy_figures_to_dist(one, dest_file.parent)

        styled_html = self._build_styled_html(include_navbar=include_navbar)

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(styled_html)

        style_css_file = one.source_dir / "style.css"
        if style_css_file.exists():
            shutil.copy(style_css_file, dest_file.parent / "style.css")
        else:
            if self.one_doc.use_default_html_style:
                from paradoc.common import MY_DEFAULT_HTML_CSS

                shutil.copy(MY_DEFAULT_HTML_CSS, dest_file.parent / "style.css")

        print(f'Successfully exported HTML to "{dest_file}"')
