# crdt_merge.cli.migrate — MergeKit Migration

**Module**: `crdt_merge/cli/migrate.py`
**LOC**: 548

---

## Overview

CLI tool for migrating MergeKit YAML configurations to crdt-merge Python code.

## Usage

```bash
python -m crdt_merge.cli.migrate --input mergekit_config.yaml --output merge_script.py
```

## Supported MergeKit Features

- Linear interpolation → `WeightedAverage`
- SLERP → `SLERPMerge`
- Task arithmetic → `TaskArithmetic`
- TIES → `TiesMerge`
- DARE → `DareMerge`
- LoRA adapters → `LoRAMerge`


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `parse_basic_yaml_string(text: str) → Any`

Parse a YAML string into nested Python objects (dict/list/scalar).

    This handles the *subset* of YAML commonly found in MergeKit configs.
    

**Parameters:**
- `text` (`str`)

**Returns:** `Any`



### `load_yaml_config(path: str) → dict`

Load a YAML config file.

    Uses PyYAML when available; falls back to a zero-dependency basic parser
    that handles the subset of YAML found in MergeKit configs.
    

**Parameters:**
- `path` (`str`)

**Returns:** `dict`



### `load_yaml_string(text: str) → dict`

Parse a YAML string into a dict.

    Uses PyYAML when available; falls back to basic parser.
    

**Parameters:**
- `text` (`str`)

**Returns:** `dict`



### `migrate_config(config_path: str) → str`

Convert a MergeKit YAML config to crdt-merge Python code.

    Args:
        config_path: Path to MergeKit YAML config file.

    Returns:
        Python source code string using crdt-merge APIs.
    

**Parameters:**
- `config_path` (`str`)

**Returns:** `str`



### `migrate_config_string(yaml_text: str) → str`

Convert a MergeKit YAML string to crdt-merge Python code.

    Args:
        yaml_text: MergeKit YAML configuration as a string.

    Returns:
        Python source code string using crdt-merge APIs.
    

**Parameters:**
- `yaml_text` (`str`)

**Returns:** `str`



### `cli_migrate(args: list) → None`

CLI entry point for the ``migrate`` command.

**Parameters:**
- `args` (`list`)

**Returns:** `None`

