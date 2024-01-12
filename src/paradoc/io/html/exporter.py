import pathlib
import shutil

import pypandoc

from paradoc import OneDoc
from paradoc.utils import copy_figures_to_dist

THIS_DIR = pathlib.Path(__file__).parent


class HTMLExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file, include_navbar=True):
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])

        copy_figures_to_dist(one, dest_file.parent)

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

        html_str = pypandoc.convert_text(
            combined_str,
            one.FORMATS.HTML,
            format="markdown",
            extra_args=[
                "-M2GB",
                "+RTS",
                "-K64m",
                "-RTS",
                f"--metadata-file={one.metadata_file}",
            ],
            filters=["pandoc-crossref"],
        )

        js_script = ""
        if include_navbar:
            js_script = "<script>\n" + open(THIS_DIR / "js/navbar.js", "r").read() + "\n</script>"

        app_file1 = open(one.md_files_app[0].path, "r").read()
        app_head_text = ""
        for line in app_file1.splitlines():
            if line.startswith("# "):
                app_head_text = line[2:]
                break

        styled_html = f"""<html>
        <head>
        <meta name="data-appendix-start" content="{app_head_text}">
        <link rel="stylesheet" type="text/css" href="style.css">
        <script type="text/javascript" async
            src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js">
        </script>
        {js_script}
        </head>
        <body>
        <div class="content">
        {html_str}
        </div>
        </body>
        </html>"""

        # styled_html.format(__custom_js_navbar__=js_script)

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
