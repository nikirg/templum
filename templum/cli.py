import shutil
import subprocess
from enum import StrEnum
from pathlib import Path

import jinja2
import typer

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class ProjectType(StrEnum):
    API = "api"
    CLI = "cli"
    HYBRID = "hybrid"


_DEPS: dict[ProjectType, list[str]] = {
    ProjectType.API: [
        "fastapi>=0.135.1",
        "loguru>=0.7.3",
        "pydantic-settings>=2.13.1",
        "uvicorn>=0.41.0",
    ],
    ProjectType.CLI: [
        "typer>=0.15.0",
        "loguru>=0.7.3",
        "pydantic-settings>=2.13.1",
    ],
    ProjectType.HYBRID: [
        "fastapi>=0.135.1",
        "loguru>=0.7.3",
        "pydantic-settings>=2.13.1",
        "uvicorn>=0.41.0",
        "typer>=0.15.0",
    ],
}

# Script entry point for types that register a CLI command; None means no entry.
_SCRIPTS: dict[ProjectType, str | None] = {
    ProjectType.API: None,
    ProjectType.CLI: "app.main:main",
    ProjectType.HYBRID: "cli.main:main",
}

app = typer.Typer(help="Templum — project scaffold generator.")


@app.command()
def new(
    name: str = typer.Argument(help="Project name."),
    output_dir: Path = typer.Option(
        Path("."), "--output-dir", "-o", help="Parent directory for the new project."
    ),
    python: str = typer.Option("3.13", "--python", "-p", help="Python version."),
    project_type: ProjectType = typer.Option(
        ProjectType.API, "--type", "-t", help="Project type."
    ),
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
    if project_type == ProjectType.HYBRID:
        # Hybrid = API scaffold + CLI layer on top
        _copy_scaffold(_TEMPLATES_DIR / ProjectType.API, target)
        _copy_scaffold(_TEMPLATES_DIR / ProjectType.HYBRID, target)
    else:
        _copy_scaffold(_TEMPLATES_DIR / project_type, target)

    _render(target / "app" / "config.py", project_name=name)
    _build_claude_md(target, project_type, project_name=name)

    if entry := _SCRIPTS[project_type]:
        _add_scripts_entry(target / "pyproject.toml", name, entry)

    typer.echo("Adding dependencies...")
    subprocess.run(["uv", "add", *_DEPS[project_type]], check=True, cwd=target)

    typer.echo(f"\nDone! Project '{name}' created at {target}")
    typer.echo(f"\n  cd {name}")
    if project_type == ProjectType.API:
        typer.echo("  uv run fastapi dev app/main.py")
    elif project_type == ProjectType.CLI:
        typer.echo(f"  uv run {name} --help")
    else:
        typer.echo("  uv run fastapi dev app/main.py")
        typer.echo(f"  uv run {name} --help")


def main() -> None:
    app()


def _copy_scaffold(template_dir: Path, target: Path) -> None:
    for src in template_dir.iterdir():
        dst = target / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def _build_claude_md(target: Path, project_type: ProjectType, **variables: str) -> None:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )
    template = env.get_template(f"claude_{project_type}.md.j2")
    content = template.render(**variables)
    (target / "CLAUDE.md").write_text(content, encoding="utf-8")


def _render(path: Path, **variables: str) -> None:
    text = path.read_text(encoding="utf-8")
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    path.write_text(text, encoding="utf-8")


def _add_scripts_entry(pyproject_path: Path, project_name: str, entry: str) -> None:
    text = pyproject_path.read_text(encoding="utf-8")
    text += f'\n[project.scripts]\n{project_name} = "{entry}"\n'
    pyproject_path.write_text(text, encoding="utf-8")
