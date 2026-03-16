# Development Guide

## Core Principles

- **Layered architecture**: router → service → infrastructure. Each layer has one responsibility; nothing leaks across boundaries.
- **Depend on interfaces, not implementations**: services receive abstract `KeyValueStorage`, `Queue`, etc. Concrete classes are wired only in setups.
- **Domain isolation**: each domain is self-contained (`router`, `service`, `schemas`, `exceptions`). Shared infrastructure lives in top-level folders (`keyvalue/`, `queue/`).
- **Thin routers, rich services**: routers translate HTTP ↔ domain; all business logic lives in the service layer.
- **Explicit DI via setups**: the full dependency graph is assembled in one setup file. Each setup corresponds to one deployment target; swapping infrastructure means swapping the setup. No global state, no service locators.
- **Async only where necessary**: `async` is reserved for real I/O. Pure logic stays sync.
- **Infrastructure is closed**: `auth.py`, `deps.py`, `setups/base.py` are not modified — extend by adding new setups or implementations.
- **Stateless services**: services hold no mutable state between requests — all state lives in infrastructure (storage, queue). Stateless over stateful.
- **Batch over chatty**: prefer one batched call over many individual requests to external systems. Reduces latency and load.
- **Iterate, don't load**: use generators and async generators instead of loading or processing entire collections at once. Prefer `async for` over `await fetch_all()`.
- **Fail fast**: validate inputs at system boundaries (routers, external API responses). Do not propagate invalid data deep into services.
- **Idempotency**: design operations to be safe to retry. Especially important for queue consumers and external API calls.
- **Typed over untyped**: always prefer typed structures (Pydantic models, dataclasses) over plain `dict`/`list`. All public methods must be annotated.
- **Immutability**: do not mutate objects after creation. Use `model_config = ConfigDict(frozen=True)` on Pydantic models where the object must not change after construction.

---

## After Every Change

After implementing any feature or fix, always run:

```bash
uvx ruff check --fix
uvx ty check
uvx ruff format
```

Do not skip this step.

---

## Standard Libraries

Use these libraries and no others for their respective purposes.

| Purpose | Use | Never use |
|---------|-----|-----------|
| Logging | `loguru` | `print()`, `logging` |
| Data structures | `pydantic` | plain `dict`/`list`, `dataclasses` for public models |
| HTTP requests | `niquests` | `requests`, `httpx`, `aiohttp`, `urllib` |
| Testing | `pytest` + `pytest-asyncio` | `unittest` |
| Linting / formatting | `ruff` | `black`, `flake8`, `isort`, `pylint` |

### Third-party service clients

Prefer the **official SDK** of a third-party service when one exists and fits the project's requirements (async support, Python 3.13+). Fall back to `niquests` only when no official client is available.

```
# good — official SDK exists
from openai import AsyncOpenAI

# fallback — no official client
async with niquests.AsyncSession() as s:
    await s.post(...)
```

### Dependency management

Always use **`uv`** to manage dependencies — never edit `pyproject.toml` directly.

```bash
uv add <package>       # add a dependency
uv remove <package>    # remove a dependency
uv sync                # sync the environment
```

---

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
├── <infrastructure>/    # One folder per infrastructure type (e.g. queue/, keyvalue/)
│   ├── base.py          # Abstract interface
│   └── <impl>.py        # Concrete implementation
└── <domain>/            # One folder per domain
    ├── router.py        # HTTP layer
    ├── service.py       # Business logic
    ├── schemas.py       # Pydantic request/response models
    ├── exceptions.py    # Domain exceptions
    └── worker.py        # Background processing (if needed)
```

## Adding a New Domain

1. Create `app/<domain>/` with the files listed above.
2. Register the service in `setups/local.py` — add it to `INJECTABLE` and wire its dependencies in `__init__`.
3. Add `app.include_router(<domain>_router)` in `main.py`.

That's the only interaction needed with infrastructure files.

---

## Naming Conventions

| What | Style | Example |
|------|-------|---------|
| Classes | PascalCase | `TaskService`, `InMemoryQueue` |
| Functions and methods | snake_case | `create_task`, `get_task` |
| Files and modules | snake_case | `router.py`, `inmemory.py` |
| Private attributes | `_leading_underscore` | `self._storage`, `self._queue` |
| Constants | UPPER_SNAKE_CASE | `TASK_STORAGE_CAPACITY` |
| Env variables | `UPPER_SNAKE_CASE` / `NESTED__FIELD` | `APP_PORT`, `REDIS__URL` |
| Setups | Named after their infrastructure | `RedisDependencySetup`, `LocalDependencySetup` |

---

## Type Hints

Use Python 3.13+ syntax throughout.

```python
# Generics — PEP 646 syntax, no typing.Generic
class Queue[V](ABC):
    async def push(self, item: V) -> None: ...

# Union — | syntax, not Optional/Union
async def get_task(self, task_id: UUID) -> Task | None: ...

# Annotated for FastAPI dependency parameters
credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_auth_scheme)]
```

All public methods must have argument and return type annotations.

---

## async vs sync

Use `async` only when a function actually performs I/O: database calls, Redis, queue operations, HTTP requests, file I/O.

```python
# async — reads from storage (I/O)
async def get_task(self, task_id: UUID) -> Task | None:
    return await self._storage.get(task_id)

# sync — pure logic, no I/O
def _build_error_detail(self, task_id: UUID) -> str:
    return f"Task {task_id} not found"
```

Do not add `async` to methods just because they are in an async context.

---

## Dependency Injection

The DI engine (`deps.py`) and setup base (`setups/base.py`) are infrastructure — do not modify them.

### Wiring dependencies — `setups/local.py`

Declare what services are injectable via `INJECTABLE`, and construct them in `__init__`:

```python
class LocalDependencySetup(DependencySetup):
    INJECTABLE = (TaskService,)  # only services consumed by routers

    def __init__(self, config: Config):
        queue = InMemoryQueue()
        self.task_service = TaskService(InMemoryKeyValueStorage(), queue)
        self._worker = TaskWorker(queue)
        self._worker_task: asyncio.Task | None = None

    async def init(self) -> None:
        self._worker_task = asyncio.create_task(self._worker.run())

    async def dispose(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
```

Only services needed by routers go into `INJECTABLE`. Infrastructure objects (`Queue`, `Storage`, `Worker`) are implementation details of the setup.

### Requesting a service in a router

```python
@router.post("/")
async def create_task(
    task: TaskCreate,
    task_service: TaskService = Depends(DependencyInjector.provide(TaskService)),
) -> Task:
    return await task_service.create_task(task)
```

---

## Setups

A setup wires the full dependency graph for a particular infrastructure combination. Each setup corresponds to one deployment target.

### `__init__` vs `init()`

| | `__init__` | `init()` |
|---|---|---|
| When | sync initialization | async initialization |
| Use for | lightweight objects, sync clients | opening connections, starting tasks |
| Example | `Redis.from_url(...)`, `get_session()` | `aio_pika.connect_robust(...)` |

Always close resources in `dispose()`.

```python
# sync client — create in __init__
class ExternalDependencySetup(DependencySetup):
    def __init__(self, config: Config):
        self._client = SomeClient(config.SOME.URL)
        ...

    async def dispose(self) -> None:
        await self._client.aclose()

# async connection — create in init()
class AsyncDependencySetup(DependencySetup):
    def __init__(self, config: Config):
        self._config = config
        self._connection: SomeConnection | None = None

    async def init(self) -> None:
        self._connection = await some_lib.connect(self._config.SOME.URL)
        ...

    async def dispose(self) -> None:
        if self._connection is not None:
            await self._connection.close()
```

### Shared dependencies between services

If multiple services depend on the same object, create it once in the setup and pass it to each:

```python
def __init__(self, config: Config):
    client = SomeClient(config.SOME.URL)  # shared between both services

    # Give each dependency its own local variable — don't construct inline
    foo_storage = SomeStorage(client, ...)
    foo_queue = SomeQueue(client, ...)
    self.foo_service = FooService(foo_storage, foo_queue)

    bar_storage = SomeStorage(client, ...)
    self.bar_service = BarService(bar_storage)
```

Services receive the shared object via `__init__` and are unaware it's shared — that's a setup detail.

### Adding a new setup

1. Create `app/setups/<name>.py`, subclass `DependencySetup`, declare `INJECTABLE`.
2. Add the new name to the `Setup` enum in `config.py`.
3. Add a `case` for it in `Config.build_setup()` with a lazy import:

```python
class Setup(StrEnum):
    LOCAL = "local"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    SQS = "sqs"
    MYNEW = "mynew"

def build_setup(self) -> "DependencySetup":
    match self.APP_SETUP:
        ...
        case Setup.MYNEW:
            from app.setups.mynew import MyNewDependencySetup
            return MyNewDependencySetup(self)
```

`main.py` is never touched — it always calls `config.build_setup()`.

The lazy import inside the `case` block avoids circular imports: `config.py` is fully loaded before any setup module is imported.

---

## Infrastructure Interfaces

`keyvalue/` and `queue/` contain abstract interfaces and their implementations. Services depend on the interfaces, never on concrete classes.

```python
# interface
class KeyValueStorage[K, V](ABC):
    async def get(self, key: K) -> V | None: ...
    async def set(self, key: K, value: V) -> None: ...
    async def delete(self, key: K) -> None: ...

# service depends on interface, not implementation
class TaskService:
    def __init__(self, storage: KeyValueStorage[UUID, Task], queue: Queue[Task]):
        ...
```

Implementations receive `serialize`/`deserialize` callbacks so they stay generic:

```python
SomeKeyValueStorage(
    client,
    serialize=lambda v: v.model_dump_json(),
    deserialize=MyModel.model_validate_json,
)
```

### Where to put a new shared dependency

- Used by **multiple domains** → `app/<name>/` (e.g. `app/keyvalue/`, `app/queue/`)
- Used by **one domain only** → `app/<domain>/` next to the service that uses it; move to a shared folder when a second consumer appears

---

## Router Layer

The router is an HTTP wrapper only: receive request → call service → return response or HTTP error.

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

@router.post("/")
async def create_task(
    task: TaskCreate,
    task_service: TaskService = Depends(DependencyInjector.provide(TaskService)),
) -> Task:
    try:
        return await task_service.create_task(task)
    except FullStorageException:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Storage is full")
```

Rules:
- Convert domain exceptions (`FullStorageException`) to `HTTPException` in the router, not in the service.
- Use `status.HTTP_*` constants, not magic numbers.
- Use the walrus operator `:=` for concise `None` checks.

---

## Service Layer

Services contain business logic only — nothing HTTP-related.

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

Rules:
- Receive dependencies via `__init__`, typed as interfaces (`KeyValueStorage`, `Queue`) — not concrete implementations.
- Generate IDs (`uuid4()`) in the service, not in schemas.
- Raise domain exceptions, never `HTTPException`.

---

## Schemas

Separate input and output models:

```python
class TaskCreate(BaseModel):  # request body
    name: str

class Task(BaseModel):        # response and internal representation
    id: UUID
    name: str
```

Do not reuse the same model for both input and output when the field sets differ.

---

## Configuration

`config.py` is managed infrastructure — add new settings there, do not move config logic elsewhere.

Infrastructure-specific settings are grouped into nested `BaseModel` classes. The parent `Config` uses `env_nested_delimiter="__"` to map env vars to nested fields:

```python
class SomeServiceConfig(BaseModel):
    URL: str = "http://localhost:1234"


class Config(BaseSettings):
    APP_PORT: int = 8000
    APP_AUTH_TOKEN: SecretStr | None = None

    SOMESERVICE: SomeServiceConfig = SomeServiceConfig()

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__")
```

Access in a setup:

```python
SomeClient(config.SOMESERVICE.URL)  # env: SOMESERVICE__URL
```

Optional infrastructure (has required fields with no defaults) uses `| None = None`. pydantic-settings auto-constructs it when the env vars are present:

```python
class SomeOptionalConfig(BaseModel):
    REQUIRED_FIELD: str  # no default — makes the whole config optional


class Config(BaseSettings):
    SOMEOPTIONAL: SomeOptionalConfig | None = None  # None if env vars not set
```

Rules:
- Sensitive values use `SecretStr`; access with `.get_secret_value()` only where needed.
- Env variables use `__` for nesting: `APP_PORT`, `SOMESERVICE__URL`.
- Nested configs are `BaseModel`, never `BaseSettings` — only `Config` is a `BaseSettings`.
- `Config` is instantiated once in `main.py` and passed to the setup.
- Optional infrastructure is typed as `SomeConfig | None = None`; the corresponding setup asserts it is set.

---

## Authentication

Auth is pre-built in `auth.py` — do not modify it. To enable auth, set `APP_AUTH_TOKEN` in the environment or `.env` file. If unset, the app starts without auth and logs a warning.

---

## Logging

Use `loguru`. No `print()`.

```python
from loguru import logger

logger.info("TaskWorker started")
logger.info("Processing task {}: {}", task.id, task.name)
logger.warning("APP_AUTH_TOKEN is not set...")
```

---

## New Domain Checklist

- [ ] `app/<domain>/schemas.py` — input/output Pydantic models
- [ ] `app/<domain>/exceptions.py` — domain exceptions
- [ ] `app/<domain>/service.py` — business logic, depends on interfaces
- [ ] `app/<domain>/router.py` — HTTP layer, converts exceptions to HTTP responses
- [ ] Add service to `INJECTABLE` and wire it in `setups/local.py`
- [ ] `app.include_router(...)` in `main.py`
