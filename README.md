# Templum

[![PyPI version](https://img.shields.io/pypi/v/templum)](https://pypi.org/project/templum/)
[![PyPI downloads](https://img.shields.io/pypi/dm/templum)](https://pypi.org/project/templum/)

CLI scaffold generator for FastAPI microservices with clean layered architecture and explicit dependency injection. Install the package — one command creates a ready project with dependencies.

Every generated project ships with a `CLAUDE.md` that encodes all architectural rules so Claude Code works within the project's patterns from the first message.

## Usage

```bash
uvx templum my-service
```

Or install globally and use as a persistent command:

```bash
uv tool install templum
templum my-service
```

With options:

```bash
templum my-service --output-dir ~/projects --python 3.12
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir`, `-o` | `.` | Parent directory for the new project |
| `--python`, `-p` | `3.13` | Minimum Python version |

The command runs:
1. `uv init --bare` — initializes the project
2. Copies the scaffold (`app/`, `Dockerfile`, `CLAUDE.md`, `.gitignore`)
3. `uv add` — installs base dependencies

## What you get

```
my-service/
├── app/
│   ├── main.py          # FastAPI app, lifespan, router registration
│   ├── config.py        # Configuration via pydantic-settings
│   ├── auth.py          # Bearer token auth factory (do not modify)
│   ├── deps.py          # DI engine (do not modify)
│   └── setups/
│       ├── base.py      # Abstract setup (do not modify)
│       └── local.py     # Default setup — wire new services here
├── Dockerfile            # Multi-stage build with uv
├── CLAUDE.md             # Architectural rules for Claude Code
└── pyproject.toml        # Created by uv init
```

No domains or infrastructure implementations are included — the scaffold defines the shape; you fill it in.

## Running the generated project

```bash
cd my-service
uv run fastapi dev app/main.py
```

Server at `http://localhost:8000`, docs at `/docs`.

### Docker

```bash
docker build -t my-service .
docker run -p 8000:8000 my-service
```

## Architecture

```
router → service → infrastructure
```

Each layer has one job and depends only on the layer below it via abstract interfaces. The full dependency graph is assembled in a single setup file — swapping infrastructure means creating a new setup, not touching any service.

The full spec lives in the generated project's `CLAUDE.md`: layer rules, DI patterns, naming conventions, and async guidelines.

## License

MIT — see [LICENSE](LICENSE).
