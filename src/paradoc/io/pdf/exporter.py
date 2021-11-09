import pypandoc

from paradoc import OneDoc


class PdfExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file):
        one = self.one_doc

        md_main_str = "\n".join([md.read_built_file() for md in one.md_files_main])

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str
        pypandoc.convert_text(
            combined_str,
            one.FORMATS.PDF,
            outputfile=str(dest_file),
            format="markdown",
            extra_args=[
                "-M2GB",
                "+RTS",
                "-K64m",
                "-RTS",
                f"--metadata-file={one.metadata_file}"
                # f"--reference-doc={MY_DOCX_TMPL}",
            ],
            filters=["pandoc-crossref"],
            encoding="utf8",
        )
        print(f'Successfully exported PDF to "{dest_file}"')
