## Project Tooling

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
