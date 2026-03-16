# temple

A FastAPI scaffold for building microservices with clean layered architecture and explicit dependency injection. Designed for development with or without AI assistance — ships with a `CLAUDE.md` that encodes all architectural rules so Claude Code can work within the project's patterns from the first message.

## What's included

- **FastAPI app** with lifespan management and optional Bearer token auth
- **DI engine** (`deps.py`) — request-scoped service injection via `DependencyInjector.provide()`
- **Setup system** (`setups/`) — one file per deployment target; swap infrastructure by swapping the setup
- **Config** via `pydantic-settings` with `.env` support and `__`-delimited nesting
- **Dockerfile** — multi-stage build with uv, Python 3.13
- **`CLAUDE.md`** — architectural rules, patterns, and conventions for AI-assisted development

No domains or infrastructure implementations are included — the scaffold defines the shape; you fill it in.

## Quick Start

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`. Docs at `/docs`.

### Docker

```bash
docker build -t temple .
docker run -p 8000:8000 temple uv run uvicorn app.main:app --host 0.0.0.0
```

## Architecture

```
router → service → infrastructure
```

Each layer has one job and depends only on the layer below it via abstract interfaces. The full dependency graph is assembled in a single setup file — swapping Redis for RabbitMQ means creating a new setup, not touching any service.

See `CLAUDE.md` for the full spec: layer rules, DI patterns, naming conventions, async guidelines, and more.

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, router registration
├── config.py            # Configuration via pydantic-settings
├── auth.py              # Auth dependency factory (do not modify)
├── deps.py              # DI engine (do not modify)
├── setups/
│   ├── base.py          # Abstract setup (do not modify)
│   └── local.py         # Default setup — wire new services here
├── <infrastructure>/    # One folder per infrastructure type (keyvalue/, queue/, …)
│   ├── base.py          # Abstract interface
│   └── <impl>.py        # Concrete implementation
└── <domain>/            # One folder per domain
    ├── router.py
    ├── service.py
    ├── schemas.py
    ├── exceptions.py
    └── worker.py        # optional
```

## Adding a New Domain

1. Create `app/<domain>/` — `schemas.py`, `exceptions.py`, `service.py`, `router.py`
2. Register the service in `setups/local.py` — add to `INJECTABLE`, wire in `__init__`
3. `app.include_router(...)` in `main.py`

## Configuration

Settings are read from environment variables and `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | `8000` | Server port |
| `APP_NAME` | `temple` | App name (shown in docs) |
| `APP_AUTH_TOKEN` | unset | Bearer token; if unset, auth is disabled |
| `APP_SETUP` | `local` | Which setup to use |

Nested configs use `__` as delimiter: `SOMESERVICE__URL=http://...`

## Authentication

Set `APP_AUTH_TOKEN` to enable Bearer token auth on all routes:

```env
APP_AUTH_TOKEN=your-secret-token
```

If unset, the app starts without auth and logs a warning.

## Development

After every change:

```bash
uvx ruff check --fix
uvx ty check
uvx ruff format
```

Dependencies:

```bash
uv add <package>
uv remove <package>
uv sync
```

## Using with Claude Code

Open the project and start a conversation — `CLAUDE.md` is loaded automatically. Claude will follow the layer boundaries, DI conventions, naming rules, and library choices defined there without any additional prompting.

## License

MIT
