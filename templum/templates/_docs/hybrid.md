# Development Guide

## Core Contract

This document defines the default architecture and development conventions for this project, which combines a FastAPI HTTP server with a Typer management CLI.

### Rule levels

* **Required** — architectural and process rules that must be followed.
* **Default** — the preferred convention unless there is a clear project-specific reason to do otherwise.
* **Local choice** — implementation details that may vary between projects.

When rules conflict, preserve architectural boundaries first, then type safety, then style consistency.

## Core Principles

### Required

* Use layered architecture: `router -> service -> infrastructure`.
* Keep each domain self-contained: `service.py`, `schemas.py`, `exceptions.py`, optional `router.py`, optional `worker.py` or local adapters.
* CLI commands (`cli/`) and HTTP routers (`app/`) are both transport layers — neither owns business logic.
* Services must not know about HTTP or CLI. They do not raise `HTTPException`, call `typer.echo`, or inspect request/command objects.
* Both entry points share the same domain services and config. Wire them through the same setup in `app/setups/`.
* Build the dependency graph explicitly in setups. Do not use service locators, implicit globals, or hidden wiring.
* Validate all inputs at the boundary — HTTP request bodies, CLI arguments, env vars, and third-party responses.
* Public APIs must be typed: explicit argument and return annotations are required.
* Services must not keep mutable cross-request state.

### Default

* Use `async` only for I/O or async orchestration. Keep pure logic synchronous.
* Prefer typed DTOs over raw `dict[str, Any]` across module boundaries.
* Prefer immutable DTOs, config models, and events unless mutation is justified.
* Normalize untyped external payloads early.

### Required (framework boundaries)

* `app/auth.py`, `app/deps.py`, and `app/setups/base.py` are framework-owned extension points and must not be modified directly.
* Extend infrastructure by adding new setups or adapter implementations rather than patching framework internals.

---

## Default Tooling

These are project defaults, not universal laws. Deviate only when there is a concrete reason and the choice is documented in the project.

| Purpose               | Default                                        |
| --------------------- | ---------------------------------------------- |
| HTTP server           | `fastapi` + `uvicorn`                          |
| CLI framework         | `typer`                                        |
| Logging               | `loguru`                                       |
| Public data models    | `pydantic`                                     |
| HTTP requests         | official SDK if suitable, otherwise `niquests` |
| Testing               | `pytest` + `pytest-asyncio`                    |
| Linting / formatting  | `ruff`                                         |
| Dependency management | `uv`                                           |

---

## Project Structure

```text
app/
├── main.py          # FastAPI app, lifespan, router registration
├── config.py        # Configuration via pydantic-settings (shared with CLI)
├── auth.py          # Bearer token auth factory (do not modify)
├── deps.py          # DI engine (do not modify)
└── setups/
    ├── base.py      # Abstract setup (do not modify)
    └── local.py     # Default setup — wire new services here
cli/
├── main.py          # Typer app entry point, imports from app.config
└── commands/
    └── root.py      # Default management command group
```

### Structure rules

* `app/` is the HTTP layer. `cli/` is the management layer. Domain logic lives in neither — it lives in service modules under `app/<domain>/`.
* `cli/main.py` imports `Config` from `app.config` — config is not duplicated.
* CLI commands interact with services through the same interfaces used by HTTP routers.
* `cli/` has no setups of its own; it instantiates the appropriate setup from `app/setups/` directly.

### Adding a new CLI command group

1. Create `cli/commands/<group>.py` with `app = typer.Typer()` and command functions.
2. Register it in `cli/main.py` via `app.add_typer(group_app, name="<group>")`.

---

## Dependency Injection and Setups

The setup in `app/setups/` is the single source of wired dependencies for both the HTTP server and the CLI.

### Required

* Services used by HTTP routers are declared injectable in the setup's `INJECTABLE` tuple.
* CLI commands instantiate the setup directly — they do not use FastAPI's `Depends()`.
* Concrete adapters are created in setups, not in routers, commands, or services.
* Long-lived resources are cleaned up in `dispose()`.
* Async connections and background tasks start in `init()`, not in `__init__()`.

### Example — CLI command using a service

```python
@app.command()
def backfill() -> None:
    """Run a data backfill."""
    config = Config()
    setup = config.build_setup()
    asyncio.run(_run(setup))

async def _run(setup: LocalSetup) -> None:
    await setup.init()
    try:
        await setup.entity_service.backfill()
    finally:
        await setup.dispose()
```

---

## Configuration

`app/config.py` is the single config source for both server and CLI.

* Use nested `BaseModel` classes for grouped infrastructure config.
* Use `SecretStr` for sensitive values.
* The HTTP server instantiates `Config` in `app/main.py` and passes it to the selected setup.
* CLI commands import `Config` from `app.config` and instantiate it directly.

Example:

```python
class ServiceConfig(BaseModel):
    URL: str = "http://localhost:1234"

class Config(BaseSettings):
    APP_PORT: int = 8000
    APP_AUTH_TOKEN: SecretStr | None = None
    SERVICE: ServiceConfig = ServiceConfig()
```

---

## Testing Strategy

### Router tests

* Verify request parsing, auth, response codes, and exception translation.
* Do not re-test service internals here.

### Command tests

* Verify argument parsing, option defaults, error output, and exit codes.
* Use `typer.testing.CliRunner` to invoke commands without spawning subprocesses.
* Do not re-test service internals here.

### End-to-end tests

* Keep them limited but include critical flows.
* Use them to validate wiring, not every business branch.

---

## Checklists

### New domain

* Create `app/<domain>/service.py` — the domain entrypoint class
* Create `app/<domain>/schemas.py`
* Create `app/<domain>/exceptions.py`
* Create `app/<domain>/router.py` if the domain exposes an HTTP API
* Register the service in the selected setup
* Add the router in `app/main.py` (if created)
* Add router and service tests

### New CLI command group

* Create `cli/commands/<group>.py` with `app = typer.Typer()`
* Add command functions that instantiate the setup and call services
* Register in `cli/main.py` via `app.add_typer(...)`
* Add command tests using `CliRunner`

### New setup

* Create `app/setups/<name>.py`
* Subclass `DependencySetup`
* Declare `INJECTABLE`
* Wire concrete dependencies in `__init__()`
* Register setup selection in `app/config.py`
* Add `init()` and `dispose()` hooks
* Add tests for new adapters or infrastructure behavior

---

## Running

### HTTP server

```bash
uv run fastapi dev app/main.py
```

Server at `http://localhost:8000`, docs at `/docs`.

### Management CLI

```bash
uv run {{ project_name }} --help
uv run {{ project_name }} status
```

### Docker

```bash
docker build -t {{ project_name }} .
docker run -p 8000:8000 {{ project_name }}
```
