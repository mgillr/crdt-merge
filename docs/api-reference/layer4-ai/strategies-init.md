# `crdt_merge/model/strategies/__init__.py`

> Strategy registry with ``@register_strategy`` decorator and plugin discovery.

Usage::

    from crdt_merge.model.strategies import register_strategy, get_strategy

    @register_strategy("my_strategy")
    class MyStrategy(ModelMergeStrategy):
        ...

    strategy = get_strategy("my_strategy")

**Source:** `crdt_merge/model/strategies/__init__.py` | **Lines:** 205

---

**Exports (`__all__`):** `['register_strategy', 'get_strategy', 'list_strategies', 'list_strategies_by_category']`

## Constants

- `_PLUGINS_LOADED` = `False`

## Functions

### `register_strategy(name: str)`

Class decorator that registers a ``ModelMergeStrategy`` subclass.

    Parameters
    ----------
    name : str
        Unique name used to look up the strategy.

    Raises
    ------
    ValueError
        If *name* is already registered.
    TypeError
        If the decorated class is not a subclass of ``ModelMergeStrategy``.

### `get_strategy(name: str, **kwargs: Any) → ModelMergeStrategy`

Instantiate a registered strategy by *name*.

    Parameters
    ----------
    name : str
        Registered strategy name.
    **kwargs
        Forwarded to the strategy constructor.

    Raises
    ------
    KeyError
        If the strategy name is not registered.

### `list_strategies() → List[str]`

Return sorted list of all registered strategy names.

### `list_strategies_by_category() → Dict[str, List[str]]`

Return strategies grouped by their ``category`` property.

### `_discover_plugins() → None`

Load community strategies from the ``crdt_merge.model_strategies`` entry-point group.

### `_reset_registry() → None`

Reset registry — for testing only.

### `_auto_register()`

Import all strategy modules to trigger registration.


## Critical Chokepoints

### `_discover_plugins` — Ping H = 0.944

`_discover_plugins()` is the **dynamic strategy discovery gate** — it is called by `get_strategy()`, `list_strategies()`, and `list_strategies_by_category()` before any registry lookup. Every external access to the strategy registry passes through this function.

#### Plugin Discovery Pipeline

1. **Guard check**: A module-level `_PLUGINS_LOADED` boolean prevents re-execution. Once discovery has run once, subsequent calls return immediately (O(1) no-op).

2. **Entry-point scanning**: Uses `importlib.metadata.entry_points()` to find all packages registered under the `crdt_merge.model_strategies` entry-point group. Handles API differences across Python versions:
   - Python ≥ 3.12: Direct `entry_points(group=...)` call
   - Python < 3.12: Falls back to `_ep().select(group=...)` or dict-based access

3. **Plugin loading**: Iterates over discovered entry points and calls `ep.load()` for each. Loading a plugin module triggers its `@register_strategy` decorators, which add strategy classes to `_REGISTRY`.

#### Registration Mechanism

The `@register_strategy(name)` decorator registers a `ModelMergeStrategy` subclass into the internal `_REGISTRY` dict. It enforces:
- The decorated class **must** be a subclass of `ModelMergeStrategy` (raises `TypeError` otherwise)
- The strategy name **must** be unique (raises `ValueError` on duplicate registration)

Built-in strategies are registered at module import time via `_auto_register()`, which imports all built-in strategy modules (`basic`, `subspace`, `linear`, `evolutionary_merge`, `unlearning`, `calibration`, `safety`, `continual`) inside `try/except ImportError` blocks.

#### Fallback Behavior

`_discover_plugins` is designed to be fault-tolerant:
- If `importlib.metadata` is unavailable or raises any exception during entry-point enumeration, discovery silently returns with no plugins loaded. Built-in strategies (registered via `_auto_register()`) remain available.
- If an individual plugin's `ep.load()` fails (e.g., missing dependency, import error), that plugin is silently skipped and other plugins continue loading.
- The `_PLUGINS_LOADED` flag is set to `True` **before** iterating plugins, so a failure during loading does not cause repeated discovery attempts on subsequent calls.

#### Implications

Since `_discover_plugins` gates all registry lookups, any failure in the plugin discovery path affects `get_strategy()`, `list_strategies()`, and `list_strategies_by_category()`. However, the fault-tolerant design ensures that built-in strategies are always accessible even if community plugin discovery fails entirely.

---

## Analysis Notes
