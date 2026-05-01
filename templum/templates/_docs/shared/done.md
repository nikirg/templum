## Definition of Done

Before considering a change complete, run the standard quality gates:

```bash
uvx ruff check --fix
uvx ty check
uvx ruff format
uv run pytest
```

These checks are part of the default delivery workflow. Temporary local exceptions are acceptable while iterating, but final changes should pass all of them.
