## Naming Conventions

| Item                | Convention                           | Example                           |
| ------------------- | ------------------------------------ | --------------------------------- |
| Classes             | `PascalCase`                         | `OrderService`, `RedisRepository` |
| Functions / methods | `snake_case`                         | `create_order`, `get_order`       |
| Files / modules     | `snake_case`                         | `router.py`, `repository.py`      |
| Private attrs       | `_leading_underscore`                | `self._repository`                |
| Constants           | `UPPER_SNAKE_CASE`                   | `MAX_BATCH_SIZE`                  |
| Env vars            | `UPPER_SNAKE_CASE` / `NESTED__FIELD` | `APP_PORT`, `REDIS__URL`          |

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
