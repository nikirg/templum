from pathlib import Path
from unittest.mock import MagicMock, call, patch

from typer.testing import CliRunner

from templum.cli import _DEPS, ProjectType, app

runner = CliRunner()

_BARE_PYPROJECT = """\
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []
"""


def _fake_uv_init(cmd: list[str], **_: object) -> MagicMock:
    target = Path(cmd[-1])
    target.mkdir(parents=True, exist_ok=True)
    (target / "pyproject.toml").write_text(_BARE_PYPROJECT.format(name=target.name))
    return MagicMock(returncode=0)


def _make_side_effect(tmp_path: Path):
    def side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        if "init" in cmd:
            return _fake_uv_init(cmd, **kwargs)
        return MagicMock(returncode=0)

    return side_effect


# --- api type (default) ---


def test_api_creates_scaffold(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        result = runner.invoke(app, ["my-project", "--output-dir", str(tmp_path)])

    assert result.exit_code == 0, result.output

    project = tmp_path / "my-project"
    expected = [
        "pyproject.toml",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/auth.py",
        "app/deps.py",
        "app/setups/__init__.py",
        "app/setups/base.py",
        "app/setups/local.py",
        "Dockerfile",
        "CLAUDE.md",
    ]
    for rel in expected:
        assert (project / rel).exists(), f"Missing: {rel}"


def test_api_renders_project_name(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["my-api", "--output-dir", str(tmp_path)])

    config = (tmp_path / "my-api" / "app" / "config.py").read_text()
    assert '"my-api"' in config


def test_api_calls_uv_add_with_correct_deps(tmp_path: Path) -> None:
    with patch(
        "templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)
    ) as mock_run:
        runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])

    add_call = next(c for c in mock_run.call_args_list if "add" in c.args[0])
    assert add_call == call(
        ["uv", "add", *_DEPS[ProjectType.API]], check=True, cwd=tmp_path / "proj"
    )


def test_api_does_not_add_scripts_entry(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])

    pyproject = (tmp_path / "proj" / "pyproject.toml").read_text()
    assert "[project.scripts]" not in pyproject


# --- cli type ---


def test_cli_creates_scaffold(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        result = runner.invoke(
            app, ["my-tool", "--output-dir", str(tmp_path), "--type", "cli"]
        )

    assert result.exit_code == 0, result.output

    project = tmp_path / "my-tool"
    expected = [
        "pyproject.toml",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/commands/__init__.py",
        "app/commands/root.py",
        "CLAUDE.md",
    ]
    for rel in expected:
        assert (project / rel).exists(), f"Missing: {rel}"

    assert not (project / "Dockerfile").exists()


def test_cli_renders_project_name(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["my-tool", "--output-dir", str(tmp_path), "--type", "cli"])

    config = (tmp_path / "my-tool" / "app" / "config.py").read_text()
    assert '"my-tool"' in config


def test_cli_renders_project_name_in_claude_md(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["my-tool", "--output-dir", str(tmp_path), "--type", "cli"])

    claude_md = (tmp_path / "my-tool" / "CLAUDE.md").read_text()
    assert "my-tool" in claude_md
    assert "{{project_name}}" not in claude_md


def test_cli_calls_uv_add_with_correct_deps(tmp_path: Path) -> None:
    with patch(
        "templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)
    ) as mock_run:
        runner.invoke(app, ["my-tool", "--output-dir", str(tmp_path), "--type", "cli"])

    add_call = next(c for c in mock_run.call_args_list if "add" in c.args[0])
    assert add_call == call(
        ["uv", "add", *_DEPS[ProjectType.CLI]], check=True, cwd=tmp_path / "my-tool"
    )


def test_cli_adds_scripts_entry(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["my-tool", "--output-dir", str(tmp_path), "--type", "cli"])

    pyproject = (tmp_path / "my-tool" / "pyproject.toml").read_text()
    assert "[project.scripts]" in pyproject
    assert 'my-tool = "app.main:main"' in pyproject


# --- hybrid type ---


def test_hybrid_creates_scaffold(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        result = runner.invoke(
            app, ["my-svc", "--output-dir", str(tmp_path), "--type", "hybrid"]
        )

    assert result.exit_code == 0, result.output

    project = tmp_path / "my-svc"
    expected = [
        "pyproject.toml",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/auth.py",
        "app/deps.py",
        "app/setups/__init__.py",
        "app/setups/base.py",
        "app/setups/local.py",
        "Dockerfile",
        "cli/__init__.py",
        "cli/main.py",
        "cli/commands/__init__.py",
        "cli/commands/root.py",
        "CLAUDE.md",
    ]
    for rel in expected:
        assert (project / rel).exists(), f"Missing: {rel}"


def test_hybrid_renders_project_name(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(
            app, ["my-svc", "--output-dir", str(tmp_path), "--type", "hybrid"]
        )

    config = (tmp_path / "my-svc" / "app" / "config.py").read_text()
    assert '"my-svc"' in config


def test_hybrid_adds_scripts_entry(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(
            app, ["my-svc", "--output-dir", str(tmp_path), "--type", "hybrid"]
        )

    pyproject = (tmp_path / "my-svc" / "pyproject.toml").read_text()
    assert "[project.scripts]" in pyproject
    assert 'my-svc = "cli.main:main"' in pyproject


def test_hybrid_calls_uv_add_with_correct_deps(tmp_path: Path) -> None:
    with patch(
        "templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)
    ) as mock_run:
        runner.invoke(
            app, ["my-svc", "--output-dir", str(tmp_path), "--type", "hybrid"]
        )

    add_call = next(c for c in mock_run.call_args_list if "add" in c.args[0])
    assert add_call == call(
        ["uv", "add", *_DEPS[ProjectType.HYBRID]], check=True, cwd=tmp_path / "my-svc"
    )


def test_hybrid_renders_project_name_in_claude_md(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(
            app, ["my-svc", "--output-dir", str(tmp_path), "--type", "hybrid"]
        )

    claude_md = (tmp_path / "my-svc" / "CLAUDE.md").read_text()
    assert "my-svc" in claude_md
    assert "{{ project_name }}" not in claude_md


# --- shared ---


def test_new_fails_if_exists(tmp_path: Path) -> None:
    with patch("templum.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])
        result = runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])

    assert result.exit_code != 0
