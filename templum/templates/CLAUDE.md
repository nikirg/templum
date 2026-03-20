# Development Guide

## Rule Levels

This guide distinguishes between three kinds of rules:

- **Required** — architectural or process rules that must be followed.
- **Default** — the preferred project convention unless there is a justified reason to do otherwise.
- **Local choice** — project-specific tooling or implementation decisions.

When in doubt, preserve architectural boundaries first, then typing, then style consistency.

---

## Core Principles

### Required

- **Layered architecture**: `router → service → infrastructure`. Each layer has one responsibility; behavior and abstractions do not leak across boundaries.
- **Depend on interfaces, not implementations**: services receive abstract dependencies such as `Repository`, `MessageQueue`, `Notifier`, `ExternalClient`. Concrete classes are wired only in setups.
- **Domain isolation**: each domain is self-contained (`router`, `service`, `schemas`, `exceptions`, optional domain-local adapters). Shared infrastructure lives in top-level folders.
- **Thin routers, rich services**: routers translate transport concerns into domain calls; business logic lives in services.
- **Explicit DI via setups**: the full dependency graph is assembled in one setup file. No global state, registries, or service locators.
- **Fail fast at boundaries**: validate incoming requests, configuration, and external responses before they enter the domain layer.
- **Idempotency by default**: operations that may be retried must be safe to retry, especially queue consumers and external integrations.
- **Public APIs are typed**: all public functions and methods must have explicit argument and return type annotations.
- **No transport concerns in services**: services do not raise `HTTPException`, access request objects, or encode HTTP status codes.
- **No mutable cross-request service state**: services must not store request-specific or evolving state between calls.

### Default

- **Async only for I/O or async orchestration**: use `async` when a function performs I/O directly or coordinates async dependencies. Pure helpers remain sync.
- **Batch over chatty**: prefer batched calls to external systems when it improves latency and load without harming memory usage or fairness.
- **Iterate, do not preload**: prefer iterators, generators, and async generators over loading entire collections into memory.
- **Prefer immutable DTOs**: request models, response models, config models, events, and other boundary objects should be immutable unless mutation is justified.
- **Normalize external data early**: raw `dict[str, Any]` and untyped payloads are acceptable only at adapter boundaries and should be converted to typed models quickly.

### Local choice

- `auth.py`, `deps.py`, and `setups/base.py` are framework-owned extension points and must not be modified directly.
- Infrastructure is extended by adding new setups or new implementations, not by patching framework internals.

---

## After Every Change

After implementing any feature or fix, run:

```bash
uvx ruff check --fix
uvx ty check
uvx ruff format
uv run pytest
```

Do not skip this step. Linting, type checking, formatting, and tests are part of the definition of done.

---

## Standard Libraries

Use these libraries and no others for their respective purposes unless there is an explicit project exception.

| Purpose | Use | Never use |
|---------|-----|-----------|
| Logging | `loguru` | `print()`, `logging` |
| Public data models | `pydantic` | plain `dict`/`list` |
| HTTP requests | `niquests` | `requests`, `httpx`, `aiohttp`, `urllib` |
| Testing | `pytest` + `pytest-asyncio` | `unittest` |
| Linting / formatting | `ruff` | `black`, `flake8`, `isort`, `pylint` |

### Data model guidance

- Use **Pydantic models** for request/response schemas, config, external payloads, and other boundary-facing models.
- Internal immutable value objects may use `dataclass(frozen=True, slots=True)` when Pydantic adds no value.
- Do not pass raw `dict` or `list` through service boundaries when a typed model is practical.

### Third-party service clients

Prefer the **official SDK** of a third-party service when one exists and fits the project requirements such as async support and Python 3.13+ compatibility. Fall back to `niquests` only when no suitable official client exists.

```python
# good — official SDK exists
from openai import AsyncOpenAI

# fallback — no official client
async with niquests.AsyncSession() as session:
    await session.post(...)
```

### Dependency management

Always use **`uv`** to manage dependencies.

```bash
uv add <package>       # add a dependency
uv remove <package>    # remove a dependency
uv sync                # sync the environment
```

Do not edit dependency sections in `pyproject.toml` manually.

---

## Project Structure

```text
app/
├── main.py              # FastAPI app, lifespan, router registration
├── config.py            # Configuration via pydantic-settings
├── auth.py              # Auth dependency factory (do not modify)
├── deps.py              # DI engine (do not modify)
├── setups/
│   ├── base.py          # Abstract setup (do not modify)
│   └── local.py         # Default setup
├── <infrastructure>/    # One folder per infrastructure type
│   ├── base.py          # Abstract interface
│   └── <impl>.py        # Concrete implementation
└── <domain>/            # One folder per domain module
    ├── router.py        # Transport layer
    ├── service.py       # Business logic
    ├── schemas.py       # Request/response schemas
    ├── exceptions.py    # Domain exceptions
    └── worker.py        # Background processing (if needed)
```

---

## Adding a New Domain Module

1. Create `app/<domain>/` with the files listed above.
2. Register the service in `setups/local.py`: add it to `INJECTABLE` and wire its dependencies in `__init__`.
3. Add `app.include_router(<domain>_router)` in `main.py`.

That is the only required interaction with framework-owned infrastructure files.

---

## Naming Conventions

| What | Style | Example |
|------|-------|---------|
| Classes | PascalCase | `OrderService`, `RedisRepository` |
| Functions and methods | snake_case | `create_order`, `get_order` |
| Files and modules | snake_case | `router.py`, `redis_repo.py` |
| Private attributes | `_leading_underscore` | `self._repository`, `self._queue` |
| Constants | UPPER_SNAKE_CASE | `MAX_BATCH_SIZE` |
| Env variables | `UPPER_SNAKE_CASE` / `NESTED__FIELD` | `APP_PORT`, `REDIS__URL` |
| Setups | Named after infrastructure choice | `RedisSetup`, `LocalSetup` |

Additional rules:

- Name interfaces by **role**, not by `Base`: `Repository`, `Publisher`, `Notifier`.
- Name implementations by **backend or strategy**: `RedisRepository`, `S3BlobStore`, `WebhookNotifier`.
- Avoid vague names such as `Manager`, `Helper`, `Utils`, `Common`.
- Prefer domain language over technical placeholders.

---

## Type Hints

Use Python 3.13+ syntax throughout.

```python
# generic class syntax
class Repository[K, V](ABC):
    async def get(self, key: K) -> V | None: ...

# union syntax
async def get_entity(self, entity_id: UUID) -> Entity | None: ...

# Annotated for FastAPI dependency parameters
credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_auth_scheme)]
```

Rules:

- All public methods must have argument and return type annotations.
- Avoid `Any` unless it is unavoidable at a boundary.
- Prefer concrete protocols or models over loosely shaped mappings.

---

## async vs sync

Use `async` when a function:

- directly performs I/O, such as database access, queue operations, HTTP calls, file I/O;
- or orchestrates async dependencies and must `await` them.

Keep pure logic sync.

```python
# async — calls storage
async def get_entity(self, entity_id: UUID) -> Entity | None:
    return await self._repository.get(entity_id)

# sync — pure logic
def _build_not_found_message(self, entity_id: UUID) -> str:
    return f"Entity {entity_id} not found"
```

Do not mark a function `async` merely because it is called from an async context.

---

## Dependency Injection

The DI engine (`deps.py`) and setup base (`setups/base.py`) are framework-owned and must not be modified.

### Wiring dependencies — `setups/local.py`

Declare which services are injectable via `INJECTABLE`, and construct them in `__init__`.

```python
class LocalSetup(DependencySetup):
    INJECTABLE = (EntityService,)

    def __init__(self, config: Config) -> None:
        queue = InMemoryMessageQueue[EntityCreatedEvent]()
        repository = InMemoryRepository[UUID, Entity]()

        self.entity_service = EntityService(repository, queue)
        self._worker = EntityEventWorker(queue)
        self._worker_task: asyncio.Task[None] | None = None

    async def init(self) -> None:
        self._worker_task = asyncio.create_task(self._worker.run())

    async def dispose(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
```

Only services consumed by routers go into `INJECTABLE`. Infrastructure objects are setup internals.

### Requesting a service in a router

```python
@router.post("/")
async def create_entity(
    payload: EntityCreate,
    service: EntityService = Depends(DependencyInjector.provide(EntityService)),
) -> EntityResponse:
    entity = await service.create_entity(payload)
    return EntityResponse.model_validate(entity)
```

### Lifecycle rules

- Objects created in a setup are **setup-scoped singletons** unless explicitly documented otherwise.
- Request-specific state must live in function scope, not in setup-owned services.
- Long-lived resources must be closed in `dispose()`.
- Async connections and background tasks must be started in `init()`, not in `__init__`.

---

## Setups

A setup wires the full dependency graph for one infrastructure combination. Each setup corresponds to one deployment target.

### `__init__` vs `init()`

| | `__init__` | `init()` |
|---|---|---|
| When | sync initialization | async initialization |
| Use for | lightweight objects, sync clients | opening connections, starting tasks |
| Example | `Redis.from_url(...)`, client construction | `connect(...)`, background worker startup |

Always close resources in `dispose()`.

```python
# sync client — create in __init__
class ExternalSetup(DependencySetup):
    def __init__(self, config: Config) -> None:
        self._client = SomeClient(config.SERVICE.URL)

    async def dispose(self) -> None:
        await self._client.aclose()

# async connection — create in init()
class AsyncSetup(DependencySetup):
    def __init__(self, config: Config) -> None:
        self._config = config
        self._connection: SomeConnection | None = None

    async def init(self) -> None:
        self._connection = await some_lib.connect(self._config.SERVICE.URL)

    async def dispose(self) -> None:
        if self._connection is not None:
            await self._connection.close()
```

### Shared dependencies between services

If multiple services depend on the same object, create it once in the setup and pass it to each consumer.

```python
def __init__(self, config: Config) -> None:
    client = ExternalClient(config.EXTERNAL.URL)

    primary_repository = SqlRepository(client)
    audit_repository = AuditRepository(client)
    publisher = EventPublisher(client)

    self.primary_service = PrimaryService(primary_repository, publisher)
    self.audit_service = AuditService(audit_repository)
```

Services receive shared dependencies through `__init__` and remain unaware that sharing exists.

### Adding a new setup

1. Create `app/setups/<name>.py`, subclass `DependencySetup`, declare `INJECTABLE`.
2. Add the new name to the `Setup` enum in `config.py`.
3. Add a `case` for it in `Config.build_setup()` with a lazy import.

```python
class Setup(StrEnum):
    LOCAL = "local"
    MYNEW = "mynew"

def build_setup(self) -> "DependencySetup":
    match self.APP_SETUP:
        case Setup.LOCAL:
            from app.setups.local import LocalSetup
            return LocalSetup(self)
        case Setup.MYNEW:
            from app.setups.mynew import MyNewSetup
            return MyNewSetup(self)
```

`main.py` is never touched for setup selection; it always calls `config.build_setup()`.

---

## Infrastructure Interfaces

Shared infrastructure folders contain interfaces and implementations. Services depend on interfaces, never on concrete classes.

```python
class Repository[K, V](ABC):
    async def get(self, key: K) -> V | None: ...
    async def save(self, key: K, value: V) -> None: ...
    async def delete(self, key: K) -> None: ...


class MessageQueue[T](ABC):
    async def publish(self, message: T) -> None: ...
```

```python
class EntityService:
    def __init__(
        self,
        repository: Repository[UUID, Entity],
        queue: MessageQueue[EntityCreatedEvent],
    ) -> None:
        self._repository = repository
        self._queue = queue
```

Implementations should stay generic where practical. Serialization belongs in the adapter, not in the service.

```python
JsonRepository(
    client=client,
    serialize=lambda value: value.model_dump_json(),
    deserialize=Entity.model_validate_json,
)
```

### Where to put a new shared dependency

- Used by **multiple domains** → `app/<name>/`
- Used by **one domain only** → keep it in `app/<domain>/` until reuse appears
- Promote to a shared folder only when a second consumer exists or a stable abstraction emerges

---

## Router Layer

The router is a transport wrapper only: receive request → call service → return response or transport error.

```python
router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("/{entity_id}")
async def get_entity(
    entity_id: UUID,
    service: EntityService = Depends(DependencyInjector.provide(EntityService)),
) -> EntityResponse:
    if entity := await service.get_entity(entity_id):
        return EntityResponse.model_validate(entity)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Entity not found",
    )

@router.post("/")
async def create_entity(
    payload: EntityCreate,
    service: EntityService = Depends(DependencyInjector.provide(EntityService)),
) -> EntityResponse:
    try:
        entity = await service.create_entity(payload)
    except CapacityExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Capacity exceeded",
        )

    return EntityResponse.model_validate(entity)
```

Rules:

- Convert domain exceptions to transport-specific errors in the router, not in the service.
- Use `status.HTTP_*` constants, not magic numbers.
- Keep request parsing, auth dependencies, and HTTP mapping in the router.
- Do not embed business rules in route handlers.

---

## Service Layer

Services contain business logic only.

```python
class EntityService:
    def __init__(
        self,
        repository: Repository[UUID, Entity],
        queue: MessageQueue[EntityCreatedEvent],
    ) -> None:
        self._repository = repository
        self._queue = queue

    async def create_entity(self, data: EntityCreate) -> Entity:
        entity = Entity(id=uuid4(), name=data.name)
        await self._repository.save(entity.id, entity)
        await self._queue.publish(EntityCreatedEvent(entity_id=entity.id))
        return entity

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        return await self._repository.get(entity_id)
```

Rules:

- Receive dependencies via `__init__`, typed as interfaces.
- Generate IDs and enforce domain invariants in the service or deeper domain layer, not in schemas.
- Raise domain exceptions, never transport exceptions.
- Keep serialization, HTTP mapping, and persistence-specific details out of the service.

---

## Schemas and Models

Do not collapse all model roles into one class unless the shapes are truly identical.

Recommended separation:

- **Request DTO** — incoming transport payload
- **Response DTO** — outgoing transport payload
- **Domain model** — internal business representation
- **Persistence model** — storage representation, if it differs from the domain model

```python
class EntityCreate(BaseModel):
    name: str


class EntityResponse(BaseModel):
    id: UUID
    name: str


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
```

Rules:

- Use separate input and output models when field sets differ.
- Do not expose persistence-only fields in public responses.
- Prefer immutable models for DTOs and events.

---

## Validation

Validation happens at different layers for different reasons.

### Boundary validation

Use schemas and typed adapters to validate:

- HTTP request bodies
- query/path parameters
- environment/config
- third-party API responses
- queue messages entering the system

### Domain validation

Use services or domain models to enforce:

- invariants
- state transition rules
- uniqueness or consistency rules not expressible as simple schema validation

Do not rely on transport schemas alone to protect domain correctness.

---

## Configuration

`config.py` is managed infrastructure: add new settings there, do not move config logic elsewhere.

Infrastructure-specific settings are grouped into nested `BaseModel` classes. The parent `Config` uses `env_nested_delimiter="__"`.

```python
class ServiceConfig(BaseModel):
    URL: str = "http://localhost:1234"


class Config(BaseSettings):
    APP_PORT: int = 8000
    APP_AUTH_TOKEN: SecretStr | None = None

    SERVICE: ServiceConfig = ServiceConfig()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )
```

Access in a setup:

```python
SomeClient(config.SERVICE.URL)  # env: SERVICE__URL
```

Optional infrastructure uses `| None = None`.

```python
class OptionalServiceConfig(BaseModel):
    REQUIRED_FIELD: str


class Config(BaseSettings):
    OPTIONAL_SERVICE: OptionalServiceConfig | None = None
```

Rules:

- Sensitive values use `SecretStr`.
- Nested configs are `BaseModel`, never `BaseSettings`.
- `Config` is instantiated once in `main.py` and passed to the setup.
- Optional infrastructure may be absent from config; the corresponding setup must validate that required config is present before use.

---

## Authentication

Auth is pre-built in `auth.py` and must not be modified. To enable auth, set `APP_AUTH_TOKEN` in the environment or `.env` file.

If unset, the app starts without auth and logs a warning.

---

## Logging

Use `loguru`. Do not use `print()`.

```python
from loguru import logger

logger.info("Background worker started")
logger.info("Processing entity {}", entity_id)
logger.warning("APP_AUTH_TOKEN is not set")
```

Rules:

- Log facts, not commentary.
- Never log secrets or raw credentials.
- Prefer structured, parameterized logs over string concatenation.

---

## Testing Strategy

### Service tests

- Test business behavior through service interfaces.
- Mock or fake infrastructure interfaces, not concrete adapters.
- Cover invariants, retries, idempotency, and branching logic.

### Router tests

- Verify HTTP mapping only: request parsing, response codes, auth, exception translation.
- Do not re-test service internals in router tests.

### Infrastructure tests

- Verify each adapter against the interface contract.
- Cover serialization, deserialization, retries, error handling, and cleanup.

### End-to-end tests

- Keep them minimal but include critical flows.
- Use them to validate wiring, not every business branch.

---

## New Domain Checklist

- [ ] `app/<domain>/schemas.py` — request/response models
- [ ] `app/<domain>/exceptions.py` — domain exceptions
- [ ] `app/<domain>/service.py` — business logic, depends on interfaces
- [ ] `app/<domain>/router.py` — transport layer, converts domain exceptions to HTTP responses
- [ ] Optional domain-local adapters or worker if needed
- [ ] Add service to `INJECTABLE` and wire it in `setups/local.py`
- [ ] Add `app.include_router(...)` in `main.py`
- [ ] Add tests for router and service behavior

## New Setup Checklist

- [ ] `app/setups/<name>.py` — subclass `DependencySetup`, declare `INJECTABLE`, wire dependencies in `__init__`
- [ ] Add config classes to `config.py` if needed
- [ ] Add the new name to the `Setup` enum in `config.py`
- [ ] Add a `case` for it in `Config.build_setup()` with a lazy import
- [ ] Add required infrastructure packages via `uv add`
- [ ] Implement `init()` for async connections and `dispose()` for cleanup
- [ ] Add infrastructure tests for new adapters