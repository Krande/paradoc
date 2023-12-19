import typer
from paradoc import OneDoc

app = typer.Typer()


@app.command("paradoc")
def main(source_dir: str, report_name: str, auto_open: bool = False):
    one = OneDoc(source_dir)
    one.compile(report_name, auto_open=True)


if __name__ == "__main__":
    app()
