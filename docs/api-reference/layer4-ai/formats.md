# Formats

> MergeKit / FusionBench compatibility layer.

**Source:** `crdt_merge/model/formats.py`  
**Lines of Code:** 232

## Overview

Provides import/export of MergeKit-style YAML configurations and
bidirectional strategy name mapping.

Example::

    from crdt_merge.model.formats import import_mergekit_config, export_mergekit_config

    schema, extra = import_mergekit_config({
        "merge_method": "ties",
        "models": [{"model": "path/a"}, {"model": "path/b"}],
        "parameters": {"density": 0.5},
    })

## Functions

### `_map_to_crdt()`

```python
_map_to_crdt(mergekit_name: str) -> str
```

Map a MergeKit strategy name to crdt-merge equivalent.

### `_map_to_mergekit()`

```python
_map_to_mergekit(crdt_name: str) -> str
```

Map a crdt-merge strategy name to MergeKit equivalent.

### `_parse_yaml_string()`

```python
_parse_yaml_string(yaml_str: str) -> dict
```

Parse a YAML string into a dict. Uses yaml if available, else basic parsing.

### `import_mergekit_config()`

```python
import_mergekit_config(config: Union[dict, str]) -> Tuple[ModelMergeSchema, dict]
```

Parse a MergeKit-style config into a ModelMergeSchema.

### `export_mergekit_config()`

```python
export_mergekit_config(schema: ModelMergeSchema, models: Optional[List[str]] = None) -> dict
```

Convert a ModelMergeSchema back to MergeKit format.

## Constants / Module Variables

- `STRATEGY_MAP` — `Dict[str, str] = {'linear': 'linear', 'slerp': 'slerp', 'ties': 'ties', 'dare_ties': 'dare_ties', 'task_arithmetic...`
- `REVERSE_STRATEGY_MAP` — `Dict[str, str] = {v: k for k, v in STRATEGY_MAP.items()}`


## Shadow Dependencies

### Dynamic Dispatch via `STRATEGY_MAP` and `REVERSE_STRATEGY_MAP`

The `formats.py` module implements bidirectional strategy name translation between MergeKit conventions and crdt-merge internal names. The dispatch mechanism operates through two module-level dictionaries:

| Constant | Type | Purpose |
|----------|------|---------|
| `STRATEGY_MAP` | `Dict[str, str]` | MergeKit name → crdt-merge name (e.g., `"dare_linear"` → `"dare"`) |
| `REVERSE_STRATEGY_MAP` | `Dict[str, str]` | crdt-merge name → MergeKit name (e.g., `"dare"` → `"dare_linear"`) |

#### Dispatch Flow

- `import_mergekit_config()` calls `_map_to_crdt()` which does a `STRATEGY_MAP.get(name, name)` lookup — unmapped names pass through unchanged, acting as an implicit fallback.
- `export_mergekit_config()` calls `_map_to_mergekit()` which does a `REVERSE_STRATEGY_MAP.get(name, name)` lookup with the same pass-through fallback.

#### Strategy Registry Interaction (`__init__.py`)

The `strategies/__init__.py` module uses a separate `_REGISTRY: Dict[str, Type[ModelMergeStrategy]]` for dynamic dispatch of strategy instantiation. The `@register_strategy(name)` decorator populates this registry at import time. `get_strategy(name)` performs a lookup against `_REGISTRY` after calling `_discover_plugins()` to ensure community strategies are loaded.

These two dispatch mechanisms (`STRATEGY_MAP` for name translation, `_REGISTRY` for class instantiation) are independent — `formats.py` translates names but does not instantiate strategies, while `strategies/__init__.py` instantiates strategies but does not handle MergeKit name translation.

---

## Analysis Notes

### GDEPA Findings
- Runtime-only symbols: 2
- Inherited methods: 0
- Circular dependencies: None

### RREA Findings
- Entropy profile: Low (shadow deps present)
- Dead code: None
- Shadow dependencies: `REVERSE_STRATEGY_MAP.get` → `export_mergekit_config`, `STRATEGY_MAP.get` → `import_mergekit_config`, `config.get` → `import_mergekit_config`
- Chokepoint status: None

### Code Quality (Team 2)
- Docstring coverage: 100.0%
- `__all__` defined: Yes
- Code smells: None

### Second Pass
- Heightened findings: None (all 1,063 new inherited methods classified as false positive dunders)
