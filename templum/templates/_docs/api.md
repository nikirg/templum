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
* Keep each domain self-contained: `service.py`, `schemas.py`, `exceptions.py`, optional `router.py`, optional `worker.py` or local adapters.
* Keep routers thin. Routers handle transport concerns; services own business logic.
* Services depend on interfaces when multiple implementations exist or a swap is anticipated; depend on a concrete adapter directly when there is a single implementation with no planned replacement.
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

### Required (framework boundaries)

* `auth.py`, `deps.py`, and `setups/base.py` are framework-owned extension points and must not be modified directly.
* Extend infrastructure by adding new setups or adapter implementations rather than patching framework internals.

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
├── <infrastructures>/     # plural: multiple implementations
│   ├── base.py            # optional: only when interface is needed
│   └── <backend>/
│       └── <infrastructure>.py
├── <infrastructure>/      # singular: single implementation
│   └── <infrastructure>.py
└── <domain>/
    ├── service.py
    ├── schemas.py
    ├── exceptions.py
    ├── router.py          # optional
    └── worker.py          # optional
```

### Structure rules

* Shared adapters and interfaces live in top-level infrastructure folders.
* Domain modules contain business-facing code for one domain.
* `router.py` is optional — a service used only as a dependency of another service does not need to expose an HTTP API.
* `worker.py` is optional and used only when the domain owns background processing.

### Infrastructure layout

An infrastructure folder may contain a flat list of files or nested subfolders for complex implementations. Naming follows these rules:

* Use plural when there are multiple implementations (`repositories/`, `notifiers/`), singular when there is only one (`billing_client/`).
* The entrypoint file inside a subfolder matches the singular form of the folder name (`repository.py`, `billing_client.py`).
* Add `base.py` with an abstract interface when multiple implementations exist or a swap is anticipated. Omit it when there is a single implementation with no planned replacement.
* Each infrastructure unit may have its own `schemas.py` and `exceptions.py` when the implementation warrants it.

```text
app/
├── repositories/          # interface + multiple implementations (subfolders)
│   ├── base.py            # Repository (ABC)
│   ├── postgres/
│   │   ├── repository.py  # entrypoint
│   │   ├── queries.py
│   │   └── models.py
│   └── redis/
│       └── repository.py
├── notifiers/             # interface + multiple implementations (flat files)
│   ├── base.py            # Notifier (ABC)
│   ├── email.py
│   ├── sms.py
│   ├── telegram.py
│   └── whatsapp.py
└── billing_client/        # no interface, single complex implementation
    ├── billing_client.py  # entrypoint
    ├── schemas.py
    └── exceptions.py
```

### Clients for external and internal APIs

HTTP clients for other services are infrastructure, not services. They live in a dedicated folder following the infrastructure naming rules above and may own their own `schemas.py` and `exceptions.py`. Wrap a client in a service only when business logic (aggregation, enrichment, domain rules) sits on top of it.

---

## Dependency Injection and Setups

A setup assembles one full dependency graph for one infrastructure combination. Create a new setup when the dependency graph changes significantly — for example, an on-premise deployment uses a local message queue and file storage, while a cloud deployment wires SQS and S3 in their place. If only one or two concrete adapters need to vary, inject the variant directly rather than creating a separate setup.

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

Services contain business behavior and orchestrate domain operations through interfaces. `service.py` holds the domain's entrypoint class — the primary object other layers interact with. Complex domains may spread logic across additional modules inside the domain folder; `service.py` is the entry point, not the container for all logic.

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
* Let infrastructure exceptions propagate unless the service has a meaningful recovery or retry strategy. Do not swallow or re-wrap them without purpose.

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

## Testing Strategy

### Router tests

* Verify request parsing, auth, response codes, and exception translation.
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
* Create `app/<domain>/router.py` only if the domain exposes an HTTP API; omit if the service is consumed solely by other services
* Add `worker.py` or domain-local adapters only if needed
* Register the service in the selected setup
* Add the router in `main.py` (if a router was created)
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
