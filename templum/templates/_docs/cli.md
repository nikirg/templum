# Development Guide

## Core Contract

This document defines the architecture and development conventions for this Typer CLI project.

### Rule levels

* **Required** — architectural and process rules that must be followed.
* **Default** — the preferred convention unless there is a clear project-specific reason to do otherwise.
* **Local choice** — implementation details that may vary between projects.

When rules conflict, preserve architectural boundaries first, then type safety, then style consistency.

## Core Principles

### Required

* Keep commands thin. Commands handle argument parsing and output; services own business logic.
* Services must not know about the CLI layer. They do not call `typer.echo`, `typer.Exit`, or inspect Typer objects.
* Services must not keep mutable cross-request state.
* Public APIs must be typed: explicit argument and return annotations are required.
* Validate external input (files, env vars, third-party responses) at the boundary before it enters the domain.
* Build the dependency graph explicitly in `main.py` or a dedicated setup. Do not use service locators or hidden wiring.

### Default

* Use `async` only for I/O or async orchestration. Keep pure logic synchronous.
* Prefer typed DTOs over raw `dict[str, Any]` across module boundaries.
* Prefer immutable DTOs and events unless mutation is justified.
* Normalize untyped external payloads early.

---

## Default Tooling

These are project defaults, not universal laws. Deviate only when there is a concrete reason and the choice is documented in the project.

| Purpose               | Default                                        |
| --------------------- | ---------------------------------------------- |
| CLI framework         | `typer`                                        |
| Logging               | `loguru`                                       |
| Public data models    | `pydantic`                                     |
| HTTP requests         | official SDK if suitable, otherwise `niquests` |
| Testing               | `pytest`                                       |
| Linting / formatting  | `ruff`                                         |
| Dependency management | `uv`                                           |

---

## Project Structure

```
app/
├── main.py          # Entry point — root Typer app, registers command groups
├── config.py        # Configuration via pydantic-settings
└── commands/
    ├── __init__.py
    └── root.py      # Default command group — add more modules here
```

### Structure rules

* `main.py` owns the root `typer.Typer()` instance and registers sub-apps via `app.add_typer(...)`.
* Each command group lives in its own module under `commands/`.
* `config.py` is the only place settings are loaded.
* Business logic lives in separate service modules, not in command handlers.

### Adding a new command group

1. Create `app/commands/<group>.py` with `app = typer.Typer()` and command functions.
2. Register it in `main.py`: `app.add_typer(group_app, name="<group>")`.

---

## Configuration

`config.py` is managed infrastructure. Add settings there instead of scattering config loading across the codebase.

* Use nested `BaseModel` classes for grouped infrastructure config.
* Use `SecretStr` for sensitive values.
* Instantiate `Config` once at startup and pass it into services.

Example:

```python
class ApiConfig(BaseModel):
    BASE_URL: str = "https://api.example.com"
    TIMEOUT: int = 30

class Config(BaseSettings):
    APP_NAME: str = "{{ project_name }}"
    API: ApiConfig = ApiConfig()
```

---

## Testing Strategy

### Command tests

* Verify argument parsing, option defaults, error output, and exit codes.
* Use `typer.testing.CliRunner` to invoke commands without spawning subprocesses.
* Do not re-test service internals here.

---

## Checklists

### New command group

* Create `app/commands/<group>.py` with `app = typer.Typer()`
* Add command functions with typed arguments and options
* Register in `main.py` via `app.add_typer(...)`
* Add command tests using `CliRunner`

### New service

* Create `app/<name>/service.py`
* Receive dependencies via `__init__`, typed as interfaces
* Raise domain exceptions, not CLI exceptions
* Add service tests

---

## Running

```bash
uv run {{ project_name }} --help
uv run {{ project_name }} hello --name Claude
```

During development:

```bash
uv run python -m app.main --help
```
