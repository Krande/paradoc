import pypandoc

from paradoc import OneDoc
from paradoc.utils import copy_figures_to_dist


class HTMLExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file):
        one = self.one_doc

        md_main_str = "\n\n".join([md.read_built_file() for md in one.md_files_main])

        copy_figures_to_dist(one, dest_file.parent)

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n".join([md.read_built_file() for md in one.md_files_app])
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
        styled_html = f"""<html>
        <head>
        <link rel="stylesheet" type="text/css" href="style.css">
        </head>
        <body>
        {html_str}
        </body>
        </html>"""

        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(styled_html)
        print(f'Successfully exported HTML to "{dest_file}"')
