# Templum

[![PyPI version](https://img.shields.io/pypi/v/templum)](https://pypi.org/project/templum/)
[![PyPI downloads](https://img.shields.io/pypi/dm/templum)](https://pypi.org/project/templum/)

CLI scaffold generator for FastAPI services and Typer CLI tools with clean layered architecture. Install the package — one command creates a ready project with dependencies.

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
templum my-tool --type cli
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir`, `-o` | `.` | Parent directory for the new project |
| `--python`, `-p` | `3.13` | Minimum Python version |
| `--type`, `-t` | `api` | Project type: `api`, `cli`, or `hybrid` |

The command runs:
1. `uv init --bare` — initializes the project
2. Copies the scaffold (`app/`, `Dockerfile` for API, `.gitignore`)
3. Assembles `CLAUDE.md` from Jinja2 templates — type-specific architecture + shared conventions
4. `uv add` — installs base dependencies

## What you get

### API project

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

### CLI project

```
my-tool/
├── app/
│   ├── main.py          # Entry point — root Typer app, main() entry point
│   ├── config.py        # Configuration via pydantic-settings
│   └── commands/
│       └── root.py      # Default command group — add more modules here
├── CLAUDE.md             # Architectural rules for Claude Code
└── pyproject.toml        # Created by uv init, includes [project.scripts]
```

### Hybrid project

FastAPI server + Typer management CLI sharing the same config and domain services.

```
my-project/
├── app/
│   ├── main.py          # FastAPI app, lifespan, router registration
│   ├── config.py        # Configuration shared with the CLI
│   ├── auth.py          # Bearer token auth factory (do not modify)
│   ├── deps.py          # DI engine (do not modify)
│   └── setups/
│       └── local.py     # Default setup — wire new services here
├── cli/
│   ├── main.py          # Typer app, imports Config from app.config
│   └── commands/
│       └── root.py      # Management command group
├── Dockerfile            # Multi-stage build with uv
├── CLAUDE.md             # Architectural rules for Claude Code
└── pyproject.toml        # Includes [project.scripts] for CLI entry point
```

## Running the generated project

### API

```bash
cd my-service
uv run fastapi dev app/main.py
```

Server at `http://localhost:8000`, docs at `/docs`.

#### Docker

```bash
docker build -t my-service .
docker run -p 8000:8000 my-service
```

### CLI

```bash
cd my-tool
uv run my-tool --help
uv run my-tool hello --name Claude
```

### Hybrid

```bash
cd my-project
uv run fastapi dev app/main.py   # HTTP server
uv run my-project --help         # management CLI
uv run my-project status
```

## Architecture

### API

```
router → service → infrastructure
```

Each layer has one job and depends only on the layer below it via abstract interfaces. The full dependency graph is assembled in a single setup file — swapping infrastructure means creating a new setup, not touching any service.

### CLI

```
commands/ → app/main.py → config.py
```

Each command group lives in its own module under `commands/`. Add new groups by creating `commands/<group>.py` and registering them in `main.py`.

The full spec lives in the generated project's `CLAUDE.md`.

## CLAUDE.md structure

The generated `CLAUDE.md` is assembled at scaffold time from composable Markdown fragments:

```
_docs/
├── api.md / cli.md      # Type-specific: architecture, principles, structure, checklists
└── shared/
    ├── code_style.md    # Naming conventions, type hints, async/sync rules, logging
    ├── done.md          # Definition of Done
    ├── tooling.md       # Data model guidance, third-party clients, dependency management
    └── testing.md       # Service tests, infrastructure tests
```

Jinja2 templates (`claude_api.md.j2`, `claude_cli.md.j2`) stitch the fragments together in the right order. No content is duplicated — each rule lives in exactly one file.

## License

MIT — see [LICENSE](LICENSE).
