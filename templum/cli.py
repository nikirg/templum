import shutil
import subprocess
from pathlib import Path

import typer

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_BASE_DEPS = [
    "fastapi>=0.135.1",
    "loguru>=0.7.3",
    "pydantic-settings>=2.13.1",
    "uvicorn>=0.41.0",
]

app = typer.Typer(help="Templum — FastAPI project scaffold generator.")


@app.command()
def new(
    name: str = typer.Argument(help="Project name."),
    output_dir: Path = typer.Option(
        Path("."), "--output-dir", "-o", help="Parent directory for the new project."
    ),
    python: str = typer.Option("3.13", "--python", "-p", help="Python version."),
) -> None:
    """Generate a new project scaffold named NAME."""
    target = output_dir.resolve() / name

    if target.exists():
        typer.echo(f"Error: '{target}' already exists.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Initializing '{name}'...")
    subprocess.run(
        ["uv", "init", "--bare", "--python", f">={python}", str(target)],
        check=True,
    )

    typer.echo("Copying scaffold...")
    for src in _TEMPLATES_DIR.iterdir():
        dst = target / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    _render(target / "app" / "config.py", project_name=name)

    typer.echo("Adding dependencies...")
    subprocess.run(["uv", "add", *_BASE_DEPS], check=True, cwd=target)

    typer.echo(f"\nDone! Project '{name}' created at {target}")
    typer.echo(f"\n  cd {name}")
    typer.echo("  uv run fastapi dev app/main.py")


def main() -> None:
    app()


def _render(path: Path, **variables: str) -> None:
    text = path.read_text(encoding="utf-8")
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    path.write_text(text, encoding="utf-8")
