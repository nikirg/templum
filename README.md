# temple

A production-ready FastAPI scaffold for building microservices with clean layered architecture, explicit dependency injection, and swappable infrastructure — designed for both manual development and AI-assisted coding with Claude Code.

## Features

- **Layered architecture** — router → service → infrastructure with strict boundaries
- **Explicit dependency injection** — full dependency graph assembled in one setup file per deployment target
- **Swappable infrastructure** — swap Redis for RabbitMQ for SQS by swapping the setup, zero service changes
- **Interface-driven** — services depend on abstract `KeyValueStorage`, `Queue`, etc., never on concrete classes
- **Optional Bearer auth** — pre-built, enabled by setting one env var
- **Typed throughout** — Python 3.13+, Pydantic v2, full annotations on all public methods
- **Async only where needed** — pure logic stays sync; `async` reserved for real I/O
- **Structured logging** — loguru, no `print()`
- **Docker-ready** — multi-stage Dockerfile with uv

## Tech Stack

| Purpose | Library |
|---------|---------|
| Web framework | FastAPI |
| Server | Uvicorn |
| Configuration | pydantic-settings |
| Logging | loguru |
| HTTP client | niquests |
| Linting / formatting | ruff |
| Type checking | ty |
| Package manager | uv |
| Python | 3.13+ |

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/temple.git
cd temple

# Install dependencies
uv sync

# Run
uv run uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. Docs are at `/docs`.

### With Docker

```bash
docker build -t temple .
docker run -p 8000:8000 temple uv run uvicorn app.main:app --host 0.0.0.0
```

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, router registration
├── config.py            # Configuration via pydantic-settings
├── auth.py              # Auth dependency factory (do not modify)
├── deps.py              # DI engine (do not modify)
├── setups/
│   ├── base.py          # Abstract setup (do not modify)
│   └── local.py         # Default setup — edit this to add new services
├── <infrastructure>/    # One folder per infrastructure type
│   ├── base.py          # Abstract interface
│   └── <impl>.py        # Concrete implementation
└── <domain>/            # One folder per domain
    ├── router.py        # HTTP layer
    ├── service.py       # Business logic
    ├── schemas.py       # Pydantic request/response models
    ├── exceptions.py    # Domain exceptions
    └── worker.py        # Background processing (if needed)
```

## Architecture

### Layers

```
HTTP Request
    │
    ▼
┌─────────┐
│ Router  │  Translates HTTP ↔ domain. Raises HTTPException. No business logic.
└────┬────┘
     │
     ▼
┌─────────┐
│ Service │  Business logic only. Raises domain exceptions. No HTTP concepts.
└────┬────┘
     │
     ▼
┌──────────────┐
│Infrastructure│  Storage, queues, external APIs. Accessed via abstract interfaces.
└──────────────┘
```

### Dependency Injection

The DI system is assembled in a **setup file** — one per deployment target. The setup constructs all objects and wires them together. Routers request services via `DependencyInjector.provide(ServiceClass)`.

```python
# setups/local.py
class LocalDependencySetup(DependencySetup):
    INJECTABLE = (TaskService,)

    def __init__(self, config: Config):
        queue = InMemoryQueue()
        self.task_service = TaskService(InMemoryKeyValueStorage(), queue)
        self._worker = TaskWorker(queue)

    async def init(self) -> None:
        self._worker_task = asyncio.create_task(self._worker.run())

    async def dispose(self) -> None:
        self._worker_task.cancel()
```

Swapping to Redis means creating `setups/redis.py` with `RedisKeyValueStorage` — services are untouched.

## Adding a New Domain

1. Create `app/<domain>/` with these files:

```
schemas.py     # Pydantic input/output models
exceptions.py  # Domain-specific exceptions
service.py     # Business logic, depends on abstract interfaces
router.py      # HTTP layer, converts exceptions to HTTPException
```

2. Register the service in `setups/local.py`:

```python
class LocalDependencySetup(DependencySetup):
    INJECTABLE = (TaskService, YourNewService)  # add here

    def __init__(self, config: Config):
        self.your_new_service = YourNewService(InMemoryKeyValueStorage())
```

3. Register the router in `main.py`:

```python
from app.your_domain.router import router as your_domain_router
app.include_router(your_domain_router)
```

That's it. No other infrastructure files need to change.

### Example: Tasks Domain

**schemas.py**
```python
class TaskCreate(BaseModel):
    name: str

class Task(BaseModel):
    id: UUID
    name: str
```

**service.py**
```python
class TaskService:
    def __init__(self, storage: KeyValueStorage[UUID, Task], queue: Queue[Task]):
        self._storage = storage
        self._queue = queue

    async def create_task(self, task: TaskCreate) -> Task:
        new_task = Task(id=uuid4(), name=task.name)
        await self._storage.set(new_task.id, new_task)
        await self._queue.push(new_task)
        return new_task

    async def get_task(self, task_id: UUID) -> Task | None:
        return await self._storage.get(task_id)
```

**router.py**
```python
router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/{task_id}")
async def get_task(
    task_id: UUID,
    task_service: TaskService = Depends(DependencyInjector.provide(TaskService)),
) -> Task:
    if task := (await task_service.get_task(task_id)):
        return task
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
```

## Configuration

All configuration is driven by environment variables with the `TEMPLE_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPLE_APP_PORT` | `8000` | Server port |
| `TEMPLE_APP_NAME` | `temple` | App name (shown in docs) |
| `TEMPLE_APP_AUTH_TOKEN` | unset | Bearer token; if unset, auth is disabled |
| `TEMPLE_APP_SETUP` | `local` | Which setup to use |

Nested configs use `__` as a delimiter:

```env
TEMPLE_REDIS__URL=redis://localhost:6379
TEMPLE_SOMESERVICE__API_KEY=secret
```

## Authentication

Set `TEMPLE_APP_AUTH_TOKEN` to enable Bearer token auth across all routes:

```env
TEMPLE_APP_AUTH_TOKEN=your-secret-token
```

```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:8000/tasks
```

If unset, the app starts without auth and logs a warning. The auth implementation in `auth.py` is pre-built and should not be modified.

## Infrastructure Interfaces

Services depend on abstract interfaces, not concrete classes. Implement these to add new backends:

**KeyValueStorage**
```python
class KeyValueStorage[K, V](ABC):
    async def get(self, key: K) -> V | None: ...
    async def set(self, key: K, value: V) -> None: ...
    async def delete(self, key: K) -> None: ...
```

**Queue**
```python
class Queue[V](ABC):
    async def push(self, item: V) -> None: ...
    async def pop(self) -> V: ...
```

Implementations accept `serialize`/`deserialize` callbacks to stay generic:

```python
RedisKeyValueStorage(
    client,
    serialize=lambda v: v.model_dump_json(),
    deserialize=Task.model_validate_json,
)
```

## Adding a New Setup

1. Create `app/setups/<name>.py`, subclass `DependencySetup`
2. Add the name to the `Setup` enum in `config.py`
3. Add a `case` in `Config.build_setup()` with a lazy import

```python
case Setup.REDIS:
    from app.setups.redis import RedisDependencySetup
    return RedisDependencySetup(self)
```

## Development

After every change:

```bash
uvx ruff check --fix   # lint
uvx ty check           # type check
uvx ruff format        # format
```

Manage dependencies with `uv`:

```bash
uv add <package>       # add dependency
uv remove <package>    # remove dependency
uv sync                # sync environment
```

### Running Tests

```bash
uv run pytest
```

## Using with Claude Code

This repository ships with a `CLAUDE.md` that encodes all architectural rules, naming conventions, and patterns. When working with Claude Code, the AI assistant will follow these rules automatically — proposing domain files in the right structure, using the correct libraries, wiring DI correctly, and running the required checks after every change.

## License

MIT