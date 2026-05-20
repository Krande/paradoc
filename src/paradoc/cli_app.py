import typer

from paradoc import OneDoc
from paradoc.cli.publish import app as publish_app
from paradoc.common import ExportFormats

app = typer.Typer()
# `paradoc publish <doc_dir>` — compile and upload a bundle to a
# running paradoc-serve. Lives in its own module so the heavy
# paradoc.OneDoc compile path stays out of `paradoc --help`.
app.add_typer(publish_app, name="publish")


@app.command("paradoc")
def main(
    source_dir: str,
    report_name: str,
    auto_open: bool = False,
    work_dir: str = "temp",
    export_format: ExportFormats = ExportFormats.DOCX,
):
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile(report_name, auto_open=auto_open, export_format=export_format)


if __name__ == "__main__":
    app()
