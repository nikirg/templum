# Development Guide

## Core Contract

This document defines the default architecture and development conventions for projects generated from this template.

### Rule levels

* **Required** — architectural and process rules that must be followed.
* **Default** — the preferred convention unless there is a clear project-specific reason to do otherwise.
* **Local choice** — implementation details that may vary between projects.

When rules conflict, preserve architectural boundaries first, then type safety, then style consistency.

## Core Principles

### Required

* Use layered architecture: `router -> service -> infrastructure`.
* Keep each domain self-contained: `router.py`, `service.py`, `schemas.py`, `exceptions.py`, optional `worker.py` or local adapters.
* Keep routers thin. Routers handle transport concerns; services own business logic.
* Services depend on interfaces, not concrete adapters.
* Build the dependency graph explicitly in setups. Do not use service locators, implicit globals, or hidden wiring.
* Validate requests, config, queue payloads, and third-party responses at the boundary before they enter the domain.
* Public APIs must be typed: explicit argument and return annotations are required.
* Services must not know about HTTP. They do not raise `HTTPException`, inspect request objects, or encode HTTP status codes.
* Services must not keep mutable cross-request state.
* Operations that may be retried should be safe to retry where practical, especially workers and external integrations.

### Default

* Use `async` only for I/O or async orchestration. Keep pure logic synchronous.
* Prefer typed DTOs over raw `dict[str, Any]` across module boundaries.
* Prefer immutable DTOs, config models, and events unless mutation is justified.
* Normalize untyped external payloads early.
* Prefer batched external calls when this improves latency or load without harming fairness or memory usage.
* Prefer iteration/streaming over preloading full collections into memory.

### Local choice

* `auth.py`, `deps.py`, and `setups/base.py` are framework-owned extension points and should not be modified directly.
* Extend infrastructure by adding new setups or adapter implementations rather than patching framework internals.

---

## Definition of Done

Before considering a change complete, run the standard quality gates:

```bash
uvx ruff check --fix
uvx ty check
uvx ruff format
uv run pytest
```

These checks are part of the default delivery workflow. Temporary local exceptions are acceptable while iterating, but final changes should pass all of them.

---

## Default Tooling

These are project defaults, not universal laws. Deviate only when there is a concrete reason and the choice is documented in the project.

| Purpose               | Default                                        |
| --------------------- | ---------------------------------------------- |
| Logging               | `loguru`                                       |
| Public data models    | `pydantic`                                     |
| HTTP requests         | official SDK if suitable, otherwise `niquests` |
| Testing               | `pytest` + `pytest-asyncio`                    |
| Linting / formatting  | `ruff`                                         |
| Dependency management | `uv`                                           |

### Data model guidance

* Use Pydantic models for request/response DTOs, config, external payloads, and other boundary-facing models.
* Internal immutable value objects may use `dataclass(frozen=True, slots=True)` when Pydantic adds no value.
* Avoid passing raw `dict` or `list` through service boundaries when a typed model is practical.

### Third-party clients

* Prefer an official SDK when it fits the project requirements.
* Use `niquests` when there is no suitable official client or when a direct HTTP client is simpler and more maintainable.

### Dependency management

Use `uv` by default:

```bash
uv add <package>
uv remove <package>
uv sync
```

Prefer managing dependencies through `uv` commands instead of editing dependency sections manually.

---

## Project Structure

```text
app/
├── main.py
├── config.py
├── auth.py
├── deps.py
├── setups/
│   ├── base.py
│   └── local.py
├── <infrastructure>/
│   ├── base.py
│   └── <impl>.py
└── <domain>/
    ├── router.py
    ├── service.py
    ├── schemas.py
    ├── exceptions.py
    └── worker.py
```

### Structure rules

* Shared adapters and interfaces live in top-level infrastructure folders.
* Domain modules contain business-facing code for one domain.
* `worker.py` is optional and used only when the domain owns background processing.

---

## Naming Conventions

| Item                | Convention                           | Example                           |
| ------------------- | ------------------------------------ | --------------------------------- |
| Classes             | `PascalCase`                         | `OrderService`, `RedisRepository` |
| Functions / methods | `snake_case`                         | `create_order`, `get_order`       |
| Files / modules     | `snake_case`                         | `router.py`, `redis_repo.py`      |
| Private attrs       | `_leading_underscore`                | `self._repository`                |
| Constants           | `UPPER_SNAKE_CASE`                   | `MAX_BATCH_SIZE`                  |
| Env vars            | `UPPER_SNAKE_CASE` / `NESTED__FIELD` | `APP_PORT`, `REDIS__URL`          |
| Setups              | name by infrastructure choice        | `LocalSetup`, `RedisSetup`        |

Additional defaults:

* Name interfaces by role, not by `Base`: `Repository`, `Publisher`, `Notifier`.
* Name implementations by backend or strategy: `RedisRepository`, `S3BlobStore`, `WebhookNotifier`.
* Avoid vague names such as `Manager`, `Helper`, `Utils`, `Common`.
* Prefer domain language over generic technical placeholders.

---

## Type Hints

Use modern Python typing consistently.

```python
class Repository[K, V](ABC):
    async def get(self, key: K) -> V | None: ...

async def get_entity(entity_id: UUID) -> Entity | None: ...
```

Rules:

* All public functions and methods must have argument and return type annotations.
* Avoid `Any` unless it is unavoidable at a boundary.
* Prefer concrete models, protocols, or interfaces over loosely shaped mappings.

---

## Async vs Sync

Use `async` when a function:

* directly performs I/O;
* or orchestrates async dependencies and must `await` them.

Keep pure logic synchronous.

```python
async def get_entity(self, entity_id: UUID) -> Entity | None:
    return await self._repository.get(entity_id)

def _build_not_found_message(self, entity_id: UUID) -> str:
    return f"Entity {entity_id} not found"
```

Do not mark a function `async` only because it is called from async code.

---

## Dependency Injection and Setups

A setup assembles one full dependency graph for one infrastructure combination.

### Required

* Services used by routers are declared injectable.
* Concrete adapters are created in setups, not in routers or services.
* Long-lived resources are cleaned up in `dispose()`.
* Async connections and background tasks start in `init()`, not in `__init__()`.

### Default

* Treat setup-created objects as setup-scoped singletons unless documented otherwise.
* Keep request-specific state inside function scope.
* Keep infrastructure objects internal to the setup unless a router needs the corresponding service.

### Example

```python
class LocalSetup(DependencySetup):
    INJECTABLE = (EntityService,)

    def __init__(self, config: Config) -> None:
        queue = InMemoryMessageQueue[EntityCreatedEvent]()
        repository = InMemoryRepository[UUID, Entity]()
        self.entity_service = EntityService(repository, queue)
```

---

## Router Layer

The router is a transport wrapper: parse request, call service, map result to response, translate transport-specific errors.

```python
@router.post("/")
async def create_entity(
    payload: EntityCreate,
    service: EntityService = Depends(DependencyInjector.provide(EntityService)),
) -> EntityResponse:
    entity = await service.create_entity(payload)
    return EntityResponse.model_validate(entity)
```

Rules:

* Convert domain exceptions to transport errors in the router.
* Keep auth dependencies, request parsing, and HTTP mapping in the router.
* Use `status.HTTP_*` constants instead of magic numbers.
* Do not place business rules in route handlers.

---

## Service Layer

Services contain business behavior and orchestrate domain operations through interfaces.

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
```

Rules:

* Receive dependencies via `__init__`, typed as interfaces.
* Enforce invariants and create domain objects in the service or deeper domain layer, not in transport schemas.
* Raise domain exceptions, not transport exceptions.
* Keep serialization, HTTP concerns, and adapter-specific details out of the service.

---

## Schemas and Models

Do not collapse all model roles into one class unless the shapes are genuinely identical.

Recommended separation:

* Request DTO — incoming transport payload
* Response DTO — outgoing transport payload
* Domain model — internal business representation
* Persistence model — storage representation when it differs from the domain model

Rules:

* Use separate input and output models when field sets differ.
* Do not expose persistence-only fields in public responses.
* Prefer immutable DTOs and events.

---

## Validation

Validation happens at different layers for different reasons.

### Boundary validation

Use schemas and typed adapters to validate:

* HTTP request bodies and parameters
* environment/config
* third-party API responses
* queue messages entering the system

### Domain validation

Use services or domain models to enforce:

* invariants
* state transition rules
* uniqueness or consistency rules not expressible as simple schema validation

Do not rely on transport schemas alone to protect domain correctness.

---

## Configuration

`config.py` is managed infrastructure. Add settings there instead of scattering config loading across the codebase.

Defaults:

* Use nested `BaseModel` classes for grouped infrastructure config.
* Use `SecretStr` for sensitive values.
* Instantiate `Config` once in `main.py` and pass it into the selected setup.
* Optional infrastructure may be absent from config, but the setup that uses it must validate required fields before use.

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

## Authentication

Authentication is framework-managed in `auth.py`.

* Enable it by setting `APP_AUTH_TOKEN`.
* If auth is optional for a project, unauthenticated startup behavior should be explicit and visible in logs.

---

## Logging

Use `loguru` by default.

```python
from loguru import logger

logger.info("Background worker started")
logger.info("Processing entity {}", entity_id)
```

Rules:

* Log facts, not commentary.
* Never log secrets or raw credentials.
* Prefer structured, parameterized logs over string concatenation.
* Use `print()` only for short-lived local debugging, not committed application behavior.

---

## Testing Strategy

### Service tests

* Test business behavior through service interfaces.
* Fake or mock infrastructure interfaces, not concrete adapters.
* Cover invariants, branching logic, retries, and idempotency where relevant.

### Router tests

* Verify request parsing, auth, response codes, and exception translation.
* Do not re-test service internals here.

### Infrastructure tests

* Verify adapters against the interface contract.
* Cover serialization, error handling, cleanup, and integration edge cases.

### End-to-end tests

* Keep them limited but include critical flows.
* Use them to validate wiring, not every business branch.

---

## Checklists

### New domain

* Create `app/<domain>/router.py`
* Create `app/<domain>/service.py`
* Create `app/<domain>/schemas.py`
* Create `app/<domain>/exceptions.py`
* Add `worker.py` or domain-local adapters only if needed
* Register the service in the selected setup
* Add the router in `main.py`
* Add router and service tests

### New setup

* Create `app/setups/<name>.py`
* Subclass `DependencySetup`
* Declare `INJECTABLE`
* Wire concrete dependencies in `__init__()`
* Add config models if needed
* Register setup selection in `config.py`
* Add `init()` for async startup and `dispose()` for cleanup
* Add tests for new adapters or infrastructure behavior

---

## Summary

This template optimizes for explicit boundaries, typed interfaces, predictable wiring, and maintainable services. When deviating from a default, prefer a documented exception over an implicit convention drift.
