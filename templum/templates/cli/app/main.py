import typer

from app.config import Config
from app.commands.root import app as root_app

config = Config()

app = typer.Typer(name=config.APP_NAME, help=f"{config.APP_NAME} CLI.")
app.add_typer(root_app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
