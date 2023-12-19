import typer

from paradoc import OneDoc

app = typer.Typer()


@app.command("paradoc")
def main(source_dir: str, report_name: str, auto_open: bool = False, work_dir: str = None):
    one = OneDoc(source_dir, work_dir=work_dir)
    one.compile(report_name, auto_open=auto_open)


if __name__ == "__main__":
    app()
