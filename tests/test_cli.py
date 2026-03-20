from pathlib import Path
from unittest.mock import MagicMock, call, patch

from typer.testing import CliRunner

from temple.cli import _BASE_DEPS, app

runner = CliRunner()

_BARE_PYPROJECT = """\
[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []
"""


def _fake_uv_init(cmd: list[str], **_: object) -> MagicMock:
    """Simulate `uv init --bare` by creating a minimal pyproject.toml."""
    target = Path(cmd[-1])
    target.mkdir(parents=True, exist_ok=True)
    name = target.name
    (target / "pyproject.toml").write_text(_BARE_PYPROJECT.format(name=name))
    return MagicMock(returncode=0)


def _fake_uv_add(cmd: list[str], **_: object) -> MagicMock:
    return MagicMock(returncode=0)


def _make_side_effect(tmp_path: Path):
    def side_effect(cmd: list[str], **kwargs: object) -> MagicMock:
        if "init" in cmd:
            return _fake_uv_init(cmd, **kwargs)
        return _fake_uv_add(cmd, **kwargs)

    return side_effect


def test_new_creates_scaffold(tmp_path: Path) -> None:
    with patch("temple.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
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


def test_new_renders_project_name(tmp_path: Path) -> None:
    with patch("temple.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["my-api", "--output-dir", str(tmp_path)])

    config = (tmp_path / "my-api" / "app" / "config.py").read_text()
    assert '"my-api"' in config


def test_new_calls_uv_add_with_base_deps(tmp_path: Path) -> None:
    with patch(
        "temple.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)
    ) as mock_run:
        runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])

    add_call = next(c for c in mock_run.call_args_list if "add" in c.args[0])
    assert add_call == call(
        ["uv", "add", *_BASE_DEPS], check=True, cwd=tmp_path / "proj"
    )


def test_new_fails_if_exists(tmp_path: Path) -> None:
    with patch("temple.cli.subprocess.run", side_effect=_make_side_effect(tmp_path)):
        runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])
        result = runner.invoke(app, ["proj", "--output-dir", str(tmp_path)])

    assert result.exit_code != 0
