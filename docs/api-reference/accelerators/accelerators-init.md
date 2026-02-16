# `crdt_merge/accelerators/__init__.py`

> crdt-merge Accelerators — ecosystem integrations for the modern data stack.

Each accelerator uses lazy imports to avoid mandatory dependencies.
Accelerators implement the AcceleratorProtocol for uniform discovery.

Available accelerators:
    - duckdb_udf: DuckDB UDF / MergeQL extension
    - fligh

**Source:** `crdt_merge/accelerators/__init__.py` | **Lines:** 94

---

**Exports (`__all__`):** `['AcceleratorProtocol', 'ACCELERATOR_REGISTRY', 'register_accelerator', 'get_accelerator', 'list_accelerators']`

## Classes

### `class AcceleratorProtocol(Protocol)`

Base protocol for all crdt-merge accelerators.

- `name`: `str`
- `version`: `str`

**Methods:**

#### `AcceleratorProtocol.health_check(self) → Dict[str, Any]`

Return health / readiness status.

#### `AcceleratorProtocol.is_available(self) → bool`

Check whether external dependencies are available.


## Functions

### `register_accelerator(cls: type) → type`

Decorator to register an accelerator.

    Usage::

        @register_accelerator
        class MyAccelerator:
            name = "my_accel"
            version = "0.7.0"
            ...

### `get_accelerator(name: str) → type`

Get a registered accelerator class by name.

    Raises:
        KeyError: if the accelerator is not registered.

### `list_accelerators() → List[str]`

List all registered accelerator names.

