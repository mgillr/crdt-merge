# SPDX-License-Identifier: BUSL-1.1

# CLI Command Reference

`crdt-merge` is the command-line interface for all merge, diff, query, model,
transport, and infrastructure operations provided by the crdt-merge library.

---

## Global Options

These options are accepted by every command and sub-command.

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--format FORMAT` | | `table` | Output format. Choices: `table`, `json`, `csv`, `jsonl`, `parquet`. |
| `--output PATH` | `-o` | stdout | Write output to a file instead of stdout. |
| `--no-color` | | off | Disable ANSI color codes in terminal output. |
| `--verbose` | `-v` | off | Enable verbose/debug output. |
| `--quiet` | `-q` | off | Suppress all informational messages; print only data. |
| `--config PATH` | | auto | Path to a `.crdt-merge.toml` config file. Defaults to the nearest `.crdt-merge.toml` found by walking up from the working directory, then `~/.crdt-merge.toml`. |
| `--version` | | | Print version and exit. |
| `--help` | `-h` | | Print help and exit. |

---

## merge

CRDT-aware merge of two data files. Rows are matched by `--key`; conflicts are
resolved per-column using `--strategy` flags or a `--schema` file.

**Synopsis**

```
crdt-merge merge FILE_A FILE_B --key COLUMN [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `FILE_A` | Path to the first input file (CSV, JSON, or Parquet). |
| `FILE_B` | Path to the second input file. |

**Options**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--key COLUMN` | `-k` | required | Column name (or comma-separated names) used as the merge key. |
| `--prefer {a,b,latest}` | | CRDT semantics | Global conflict-resolution preference. `a` always prefers FILE_A; `b` prefers FILE_B; `latest` uses timestamp. |
| `--strategy COL=STRATEGY` | | | Per-column strategy override. Repeatable. Example: `--strategy score=MAX --strategy name=LWW`. |
| `--dedup` | | off | De-duplicate the merged result before writing output. |
| `--schema PATH` | | | Path to a YAML/JSON merge-schema file. |
| `--timestamp-col COL` | | | Column containing timestamps (used by LWW / `--prefer latest`). |
| `--provenance` | | off | Attach provenance metadata to every output row. |
| `--audit` | | off | Write an audit log alongside the merged output. |
| `--encrypt KEY` | | | Encrypt the output file with the given key. |
| `--encrypt-backend {fernet,age,gpg}` | | `fernet` | Encryption backend. |

**Examples**

```bash
# Basic merge on column "id"
crdt-merge merge a.csv b.csv --key id

# Prefer latest timestamp globally
crdt-merge merge a.csv b.csv -k id --prefer latest

# Per-column strategies
crdt-merge merge a.csv b.csv -k id --strategy name=LWW --strategy score=MAX

# With provenance and audit log
crdt-merge merge a.json b.json -k id --provenance --audit -o merged.json

# Encrypt output
crdt-merge merge a.csv b.csv -k id --encrypt mysecretkey -o encrypted.csv
```

---

## diff

Compute a structured diff between two data files. Reports added, removed, and
changed records.

**Synopsis**

```
crdt-merge diff FILE_A FILE_B --key COLUMN [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `FILE_A` | Path to the base file. |
| `FILE_B` | Path to the comparison file. |

**Options**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--key COLUMN` | `-k` | required | Column name used as the diff key. |
| `--only {added,removed,changed}` | | all | Limit output to a single change type. |
| `--stats` | | off | Print summary statistics (counts per category) instead of the full diff. |

**Examples**

```bash
crdt-merge diff v1.csv v2.csv --key id
crdt-merge diff v1.json v2.json -k id --only changed
crdt-merge diff v1.parquet v2.parquet -k id --stats
```

---

## dedup

Remove duplicate records from a single file using exact matching, fuzzy
similarity, or MinHash locality-sensitive hashing.

**Synopsis**

```
crdt-merge dedup FILE [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `FILE` | Path to the input file. |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--method {exact,fuzzy,minhash}` | `exact` | Deduplication method. |
| `--key COLUMNS` | all columns | Column(s) to consider for dedup. |
| `--threshold FLOAT` | `0.8` | Similarity threshold for fuzzy/minhash (0.0–1.0). |
| `--num-perm INT` | `128` | Number of permutations for MinHash. |

**Examples**

```bash
crdt-merge dedup records.csv -o deduped.csv
crdt-merge dedup records.json --method fuzzy --threshold 0.85
crdt-merge dedup large.parquet --method minhash --num-perm 256 -o deduped.parquet
```

---

## stream

Streaming merge of two potentially large data sources using batched processing.
Suitable for files that do not fit entirely in memory.

**Synopsis**

```
crdt-merge stream SOURCE_A SOURCE_B --key COLUMN [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `SOURCE_A` | Path or URI of the first source. |
| `SOURCE_B` | Path or URI of the second source. |

**Options**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--key COLUMN` | `-k` | required | Column name used as the merge key. |
| `--batch-size INT` | | `5000` | Number of rows per batch. |
| `--stats` | | off | Print throughput and merge statistics on completion. |

**Examples**

```bash
crdt-merge stream huge_a.parquet huge_b.parquet -k id --batch-size 10000
crdt-merge stream a.csv b.csv -k id --stats -o merged_stream.csv
```

---

## json

JSON-specific merge operations for JSON documents and JSON-Lines files.

### json merge

Deep-merge two JSON documents. Objects are merged key-by-key; scalars use
last-writer-wins by default.

**Synopsis**

```
crdt-merge json merge FILE_A FILE_B [options]
```

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--prefer {a,b}` | deep merge | Which file wins on scalar conflicts. |
| `--array-strategy {concat,union,replace}` | `union` | Strategy for merging arrays. |

**Examples**

```bash
crdt-merge json merge config_a.json config_b.json -o merged_config.json
crdt-merge json merge doc_a.json doc_b.json --prefer b --array-strategy concat
```

### json merge-lines

Merge two JSON-Lines (`.jsonl`) files by a shared key field.

**Synopsis**

```
crdt-merge json merge-lines FILE_A FILE_B --key FIELD [options]
```

**Options**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--key FIELD` | `-k` | required | JSON field name used to match records. |
| `--prefer {a,b}` | | deep merge | Which file wins on scalar conflicts. |

**Examples**

```bash
crdt-merge json merge-lines events_a.jsonl events_b.jsonl -k event_id -o merged.jsonl
```

---

## query

Parse and execute MergeQL queries against registered data sources.

**Synopsis**

```
crdt-merge query [QUERY_STRING] [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `QUERY_STRING` | MergeQL query string (optional if `--file` is provided). |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--file PATH` | | Read the MergeQL query from a file instead of a positional argument. |
| `--register NAME=PATH` | | Register a data source by name. Repeatable. Example: `--register a=data_a.json`. |
| `--explain` | off | Show the query plan without executing the merge. |

**Examples**

```bash
crdt-merge query "MERGE a, b ON id" \
  --register a=east.json --register b=west.json

crdt-merge query "MERGE a, b ON id STRATEGY name='lww', score='max'" \
  --register a=left.csv --register b=right.csv

crdt-merge query --file query.mql \
  --register a=data_a.json --register b=data_b.json

crdt-merge query "MERGE a, b ON id" --explain

crdt-merge query "MERGE a, b ON id WHERE score > 80 LIMIT 100" \
  --register a=data_a.json --register b=data_b.json
```

---

## verify

Verify CRDT mathematical properties (commutativity, associativity, idempotency,
convergence) for built-in CRDT types or user-supplied merge functions.

### verify crdt

Verify all properties for a named built-in CRDT type.

**Synopsis**

```
crdt-merge verify crdt TYPE
```

Supported types: `gcounter`, `pncounter`, `lww`, `orset`, `lwwmap`

### verify commutative / associative / idempotent / convergence

Check a single property for a custom merge function referenced by dotted
Python path.

**Synopsis**

```
crdt-merge verify commutative DOTTED_PATH [--trials N]
crdt-merge verify associative DOTTED_PATH [--trials N]
crdt-merge verify idempotent  DOTTED_PATH [--trials N]
crdt-merge verify convergence DOTTED_PATH [--trials N]
```

### verify all

Run all four property checks for a custom merge function.

**Synopsis**

```
crdt-merge verify all DOTTED_PATH [--trials N]
```

**Examples**

```bash
crdt-merge verify crdt lww
crdt-merge verify crdt orset
crdt-merge verify commutative mypackage.mymodule.my_merge_fn
crdt-merge verify all mypackage.merges.custom_fn --trials 500
```

---

## merkle

Build and compare Merkle trees for dataset integrity verification.

### merkle build

Build a Merkle tree from a data file.

**Synopsis**

```
crdt-merge merkle build FILE [--key COLUMN] [-o PATH]
```

### merkle diff

Diff two serialized Merkle tree JSON files.

**Synopsis**

```
crdt-merge merkle diff TREE_A TREE_B
```

### merkle compare

Compare two datasets directly by building and diffing their Merkle trees.

**Synopsis**

```
crdt-merge merkle compare FILE_A FILE_B [--key COLUMN]
```

**Examples**

```bash
crdt-merge merkle build dataset.csv --key id -o tree.json
crdt-merge merkle diff tree_v1.json tree_v2.json
crdt-merge merkle compare snapshot_a.parquet snapshot_b.parquet --key record_id
```

---

## wire

Serialize and inspect data using the crdt-merge binary wire format.

### wire serialize

Serialize a data file to binary wire format.

**Synopsis**

```
crdt-merge wire serialize FILE --type TYPE [--compress] [-o PATH]
```

CRDT types: `gcounter`, `pncounter`, `lww`, `orset`, `lwwmap`, `generic`

### wire deserialize

Deserialize a binary wire file to JSON.

**Synopsis**

```
crdt-merge wire deserialize FILE [-o PATH]
```

### wire inspect

Show the type header of a binary wire file.

**Synopsis**

```
crdt-merge wire inspect FILE
```

### wire size

Show size statistics for a binary wire file.

**Synopsis**

```
crdt-merge wire size FILE
```

**Examples**

```bash
crdt-merge wire serialize state.json --type lww -o state.bin
crdt-merge wire serialize counter.json --type gcounter --compress -o counter.bin.gz
crdt-merge wire deserialize state.bin
crdt-merge wire inspect state.bin
crdt-merge wire size state.bin
```

---

## delta

Compute, apply, and compose deltas between dataset versions for
bandwidth-efficient synchronization.

### delta compute

Compute a delta between an old and new version of a dataset.

**Synopsis**

```
crdt-merge delta compute OLD_FILE NEW_FILE [--key COLUMN] [-o PATH]
```

### delta apply

Apply a delta to a base dataset to produce an updated version.

**Synopsis**

```
crdt-merge delta apply BASE_FILE DELTA_FILE [-o PATH]
```

### delta compose

Compose multiple delta files into a single delta.

**Synopsis**

```
crdt-merge delta compose DELTA_FILE... [-o PATH]
```

**Examples**

```bash
crdt-merge delta compute v1.csv v2.csv --key id -o delta_v1_v2.json
crdt-merge delta apply v1.csv delta_v1_v2.json -o v2_restored.csv
crdt-merge delta compose delta_1.json delta_2.json delta_3.json -o combined.json
```

---

## clock

Create, merge, and compare distributed clocks (Vector Clocks and Dotted
Version Vectors).

### clock create

Create a new clock and write it to a file.

**Synopsis**

```
crdt-merge clock create {vectorclock,dvv} --node NODE_ID [-o PATH]
```

### clock merge

Merge two serialized clock files.

**Synopsis**

```
crdt-merge clock merge CLOCK_A CLOCK_B [-o PATH]
```

### clock compare

Compare two clocks and report their causal ordering.

**Synopsis**

```
crdt-merge clock compare CLOCK_A CLOCK_B
```

**Examples**

```bash
crdt-merge clock create vectorclock --node node-1 -o clock_a.json
crdt-merge clock create dvv --node node-2 -o clock_b.json
crdt-merge clock merge clock_a.json clock_b.json -o merged_clock.json
crdt-merge clock compare clock_a.json clock_b.json
```

---

## gossip

Manage gossip protocol state for anti-entropy synchronization between nodes.

### gossip init

Initialize an empty gossip state file.

**Synopsis**

```
crdt-merge gossip init --node NODE_ID --state-file PATH
```

### gossip update

Update a key in a gossip state file.

**Synopsis**

```
crdt-merge gossip update STATE_FILE KEY JSON_VALUE
```

### gossip digest

Output a digest summary of a gossip state.

**Synopsis**

```
crdt-merge gossip digest STATE_FILE
```

### gossip sync

Synchronize two gossip states via anti-entropy and write the reconciled result.

**Synopsis**

```
crdt-merge gossip sync STATE_A STATE_B [-o PATH]
```

**Examples**

```bash
crdt-merge gossip init --node node-1 --state-file state_a.json
crdt-merge gossip update state_a.json username '"alice"'
crdt-merge gossip update state_a.json config '{"timeout": 30}'
crdt-merge gossip digest state_a.json
crdt-merge gossip sync state_a.json state_b.json -o reconciled.json
```

---

## model

Merge model checkpoints, manage LoRA adapters, run safety analysis, and
execute multi-step merge pipelines. Requires `pip install crdt-merge[model]`.

### model merge

Merge two or more model checkpoints using a named strategy.

**Synopsis**

```
crdt-merge model merge MODEL... --output PATH [options]
```

**Arguments**

| Argument | Description |
|----------|-------------|
| `MODEL...` | Paths to model checkpoint directories (minimum 2). |

**Options**

| Option | Default | Description |
|--------|---------|-------------|
| `--output PATH` | required | Output path for the merged model. |
| `--strategy NAME` | `linear` | Global merge strategy (e.g. `linear`, `slerp`, `ties`, `dare_ties`). |
| `--layer-strategy PAT=STRAT` | | Per-layer strategy override using glob patterns. Repeatable. |
| `--weights FLOAT,...` | uniform | Comma-separated merge weights, one per model. |
| `--base MODEL` | | Path to a base model (required by TIES, DARE, task_arithmetic). |
| `--dtype {float16,float32,bfloat16}` | | Data type for merged tensors. |
| `--config PATH` | | YAML/JSON config file with additional merge parameters. |
| `--provenance` | off | Save provenance metadata alongside the merged model. |
| `--safety` | off | Run safety analysis on the merged model after merging. |

**Examples**

```bash
crdt-merge model merge model_a/ model_b/ --strategy slerp --output merged/

crdt-merge model merge model_a/ model_b/ model_c/ \
  --strategy ties --weights 0.5,0.3,0.2 --base base/ --output merged/

crdt-merge model merge model_a/ model_b/ \
  --strategy dare_ties \
  --layer-strategy "layers.0.*=slerp" \
  --output merged/

crdt-merge model merge a/ b/ --strategy linear --provenance --output merged/
```

### model strategies

List all registered merge strategies.

**Synopsis**

```
crdt-merge model strategies [--category NAME] [--verbose]
```

**Options**

| Option | Description |
|--------|-------------|
| `--category NAME` | Filter by category (e.g. `averaging`, `interpolation`, `task_vector`). |
| `--verbose` | Show full descriptions. |

### model safety

Run safety analysis on model checkpoints to detect alignment regressions.

**Synopsis**

```
crdt-merge model safety MODEL... [--threshold FLOAT]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--threshold FLOAT` | `0.9` | Safety threshold (0.0–1.0). Lower values are stricter. |

### model lora merge

Merge two or more LoRA adapters.

**Synopsis**

```
crdt-merge model lora merge ADAPTER... --output PATH [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--strategy NAME` | `linear` | Merge strategy (`linear`, `cat`, `svd`). |
| `--weights FLOAT,...` | uniform | Weights per adapter. |
| `--rank-method {max,min,mean,adaptive}` | | Method for determining merged rank. |

### model pipeline run

Execute a multi-step merge pipeline from a YAML/JSON config file.

**Synopsis**

```
crdt-merge model pipeline run CONFIG_FILE [--dry-run] [--output PATH]
```

### model pipeline validate

Validate a pipeline configuration file without executing it.

**Synopsis**

```
crdt-merge model pipeline validate CONFIG_FILE
```

**Examples**

```bash
crdt-merge model strategies --verbose
crdt-merge model strategies --category interpolation
crdt-merge model safety model_a/ model_b/ --threshold 0.8
crdt-merge model lora merge adapter_a/ adapter_b/ --strategy cat --output merged_adapter/
crdt-merge model pipeline run pipeline.yaml --output merged/
crdt-merge model pipeline validate pipeline.yaml
```

---

## hub

Push, pull, and merge models via the HuggingFace Hub. Requires
`pip install crdt-merge[hub]`.

Token resolution order: `--token` flag → `config hub.token` → `HF_TOKEN`
environment variable → `HUGGINGFACE_TOKEN` environment variable.

### hub push

**Synopsis**

```
crdt-merge hub push LOCAL_PATH REPO_ID [--private] [--token TOKEN] [--commit-message MSG]
```

### hub pull

**Synopsis**

```
crdt-merge hub pull REPO_ID [--output PATH] [--revision REF] [--token TOKEN]
```

### hub merge

Merge two Hub repositories and optionally push the result.

**Synopsis**

```
crdt-merge hub merge REPO_A REPO_B [--strategy NAME] [--push-to REPO_ID] [--token TOKEN]
```

**Examples**

```bash
crdt-merge hub push ./merged-model my-org/my-model --private --commit-message "v2 merge"
crdt-merge hub pull my-org/my-model --output ./local-model --revision main
crdt-merge hub merge my-org/model-a my-org/model-b --strategy slerp --push-to my-org/merged
```

---

## accel

Manage accelerators and ecosystem integrations (DuckDB, SQLite, Polars, Arrow
Flight, Airbyte, dbt).

### accel list

List all registered accelerators and their availability status.

```bash
crdt-merge accel list
```

### accel duckdb

DuckDB UDF integration.

```bash
crdt-merge accel duckdb install          # Register CRDT merge UDFs in DuckDB
crdt-merge accel duckdb query "SELECT crdt_merge_lww(a, b) FROM ..."
```

### accel sqlite

SQLite extension.

```bash
crdt-merge accel sqlite install /path/to/db.sqlite  # Register extension functions
```

### accel polars

Polars plugin.

```bash
crdt-merge accel polars register  # Register plugin expressions
```

### accel flight

Arrow Flight merge server.

```bash
crdt-merge accel flight serve --host 0.0.0.0 --port 8815
```

### accel airbyte

Airbyte connector operations.

```bash
crdt-merge accel airbyte spec            # Print connector spec
crdt-merge accel airbyte check config.json
```

### accel dbt

dbt package integration.

```bash
crdt-merge accel dbt run     # Run dbt merge models
crdt-merge accel dbt compile # Compile dbt merge models
```

---

## config

Manage crdt-merge configuration files.

### config show

Display the effective configuration (merged global + local).

```bash
crdt-merge config show
```

### config path

Print the paths of all config files that are loaded.

```bash
crdt-merge config path
```

### config init

Create a default config file.

```bash
crdt-merge config init --global  # Write to ~/.crdt-merge.toml
crdt-merge config init --local   # Write to ./.crdt-merge.toml
```

---

## observe

Observability commands: system health, metrics export, and drift detection.

### doctor / health

Check environment, dependencies, and accelerator availability.

```bash
crdt-merge doctor            # Check all components
crdt-merge doctor --fix      # Print pip install commands for missing extras
crdt-merge health            # Alias for doctor
```

### observe metrics

Collect and display merge operation metrics.

```bash
crdt-merge observe metrics
crdt-merge observe metrics --format json
```

### observe export

Export metrics to an external monitoring system.

```bash
crdt-merge observe export --format prometheus
crdt-merge observe export --format json -o metrics.json
```

### observe drift

Detect statistical drift between a reference dataset and a current dataset.

```bash
crdt-merge observe drift reference.parquet current.parquet --key id
```

---

## completion

Generate shell completion scripts for bash, zsh, or fish.

**Synopsis**

```
crdt-merge completion {bash,zsh,fish}
```

**Installation**

```bash
# bash — add to ~/.bashrc
eval "$(crdt-merge completion bash)"

# zsh — add to ~/.zshrc
eval "$(crdt-merge completion zsh)"

# fish — save to completions directory
crdt-merge completion fish > ~/.config/fish/completions/crdt-merge.fish
```

---

## Additional Commands

The following commands are available for enterprise and compliance use cases.
Run `crdt-merge COMMAND --help` for full documentation.

| Command | Description |
|---------|-------------|
| `audit log` | View the audit log for a node or time range. |
| `audit export` | Export the audit log to JSON or CSV. |
| `provenance show` | Show merge provenance for a dataset. |
| `provenance export` | Export provenance metadata. |
| `compliance check` | Run compliance checks (GDPR, HIPAA, SOX). |
| `compliance report` | Generate a compliance report. |
| `encrypt` | Encrypt a data file using field-level encryption. |
| `decrypt` | Decrypt an encrypted data file. |
| `unmerge rollback` | Roll back a merge operation. |
| `unmerge forget` | Remove records from the CRDT state (GDPR right-to-erasure). |
| `rbac init` | Initialize RBAC policies for a deployment. |
| `rbac check` | Check whether a node has a given permission. |
| `migrate` | Migrate data files between schema versions. |
| `repl` | Start an interactive MergeQL REPL. |
| `wizard merge` | Interactive guided merge setup. |
| `wizard schema` | Interactive schema design wizard. |
| `wizard model` | Interactive model merge wizard. |
| `wizard pipeline` | Interactive pipeline builder. |
