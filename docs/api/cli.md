# CLI Tools 🆕

Command-line tools for crdt-merge — MergeKit migration and more. **New in v0.8.2.**

## Quick Example

```bash
# Convert MergeKit YAML to crdt-merge Python
crdt-merge migrate mergekit-config.yaml --output merge_pipeline.py
```

---

## API Reference

## `crdt_merge.cli`

> crdt-merge CLI tools.

**Module:** `crdt_merge.cli`

### Functions

#### `main()`

Entry point for crdt-merge CLI.


## `crdt_merge.cli.migrate`

> MergeKit YAML → crdt-merge Python migration tool.

**Module:** `crdt_merge.cli.migrate`

### Classes

#### `Any(*args, **kwargs)`

Special type indicating an unconstrained type.

### Functions

#### `cli_migrate(args: 'list') -> 'None'`

CLI entry point for the ``migrate`` command.

#### `load_yaml_config(path: 'str') -> 'dict'`

Load a YAML config file.

#### `load_yaml_string(text: 'str') -> 'dict'`

Parse a YAML string into a dict.

#### `migrate_config(config_path: 'str') -> 'str'`

Convert a MergeKit YAML config to crdt-merge Python code.

#### `migrate_config_string(yaml_text: 'str') -> 'str'`

Convert a MergeKit YAML string to crdt-merge Python code.

#### `migrate_config_to_schema(config_path: 'str') -> 'tuple'`

Convert a MergeKit config file to a ``ModelMergeSchema`` object.

#### `migrate_string_to_schema(yaml_text: 'str') -> 'tuple'`

Convert a MergeKit YAML string to a ``ModelMergeSchema`` object.

#### `parse_basic_yaml_string(text: 'str') -> 'Any'`

Parse a YAML string into nested Python objects (dict/list/scalar).



---

**License:** BSL-1.1 · Copyright 2026 Ryan Gillespie / Optitransfer  
Change Date: 2028-03-29 → Apache License 2.0
