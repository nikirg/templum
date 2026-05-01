import typer

app = typer.Typer()


@app.command()
def hello(name: str = typer.Option("World", "--name", "-n")) -> None:
    """Say hello."""
    typer.echo(f"Hello, {name}!")
