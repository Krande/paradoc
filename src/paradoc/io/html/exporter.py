import pypandoc

from paradoc import OneDoc


class HTMLExporter:
    def __init__(self, one_doc: OneDoc):
        self.one_doc = one_doc

    def export(self, dest_file):
        one = self.one_doc

        md_main_str = "\n".join([md.read_built_file() for md in one.md_files_main])

        app_str = """\n\n\\appendix\n\n"""

        md_app_str = "\n".join([md.read_built_file() for md in one.md_files_app])
        combined_str = md_main_str + app_str + md_app_str

        # html = markdown.markdown(combined_str)
        # with open(dest_file, 'w') as f:
        #     f.write(html)

        pypandoc.convert_text(
            combined_str,
            one.FORMATS.HTML,
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
        )
        print(f'Successfully exported HTML to "{dest_file}"')


def docx2pdf(docx_file, output_file):
    pypandoc.convert_file(
        str(docx_file),
        "pdf",
        extra_args=["--pdf-engine=pdflatex"],
        outputfile=str(output_file),
        sandbox=False,
    )
