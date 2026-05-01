import typer

app = typer.Typer()


@app.command()
def status() -> None:
    """Show application status."""
    typer.echo("Service is running.")
