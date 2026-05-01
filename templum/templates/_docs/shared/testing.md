## Testing Principles

### Service tests

* Test business behavior through service interfaces.
* Fake or mock infrastructure interfaces, not concrete adapters.
* Cover invariants, branching logic, retries, and idempotency where relevant.

### Infrastructure tests

* Verify adapters against the interface contract when one exists; otherwise test the concrete implementation directly.
* Cover serialization, error handling, cleanup, and integration edge cases.
