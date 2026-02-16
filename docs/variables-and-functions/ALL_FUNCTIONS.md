# All Functions — Complete Listing

## Layer 1: Core Functions

| Function | Module | Signature |
|----------|--------|-----------|
| `dedup` | `dedup.py` | `dedup(records, key, strategy=None) -> List[dict]` |
| `dedup_records` | `dedup.py` | `dedup_records(records, keys, schema=None) -> List[dict]` |
| `merge_with_provenance` | `provenance.py` | `merge_with_provenance(df_a, df_b, key, schema, source_a, source_b) -> Tuple` |
| `export_provenance` | `provenance.py` | `export_provenance(log, format="json") -> str` |
| `verify_crdt` | `verify.py` | `verify_crdt(crdt_class, num_tests=100) -> VerificationResult` |
| `verified_merge` | `verify.py` | `@verified_merge` *(decorator)* |
| `_safe_parse_ts` | `strategies.py` | `_safe_parse_ts(value) -> float` *(internal)* |

## Layer 2: Engine Functions

| Function | Module | Signature |
|----------|--------|-----------|
| `merge` | `dataframe.py` | `merge(df_a, df_b, key, schema=None, timestamp_col=None, node_a="a", node_b="b") -> DataFrame` |
| `diff` | `dataframe.py` | `diff(df_a, df_b, key) -> DiffResult` |
| `merge_stream` | `streaming.py` | `merge_stream(stream_a, stream_b, key, schema=None, timestamp_col=None) -> Iterator[dict]` |
| `merge_sorted_stream` | `streaming.py` | `merge_sorted_stream(stream_a, stream_b, key, schema=None) -> Iterator[dict]` |
| `arrow_merge` | `arrow.py` | `arrow_merge(table_a, table_b, key, schema=None) -> pa.Table` |
| `parallel_merge` | `parallel.py` | `parallel_merge(df_a, df_b, key, schema=None, num_workers=4) -> DataFrame` |
| `amerge` | `async_merge.py` | `async amerge(df_a, df_b, key, schema=None) -> DataFrame` |
| `amerge_stream` | `async_merge.py` | `async amerge_stream(stream_a, stream_b, key, schema=None) -> AsyncIterator` |
| `merge_dicts` | `json_merge.py` | `merge_dicts(dict_a, dict_b, schema=None) -> dict` |
| `merge_json_lines` | `json_merge.py` | `merge_json_lines(file_a, file_b, key, schema=None, output=None) -> List[dict]` |

## Layer 3: Transport Functions

| Function | Module | Signature |
|----------|--------|-----------|
| `serialize` | `wire.py` | `serialize(obj, format="msgpack") -> bytes` |
| `deserialize` | `wire.py` | `deserialize(data, format="msgpack") -> Any` |
| `peek` | `wire.py` | `peek(data) -> dict` |
| `merkle_diff` | `merkle.py` | `merkle_diff(tree_a, tree_b) -> DiffResult` |
| `anti_entropy` | `gossip.py` | `anti_entropy(local, remote) -> Tuple[bytes, bytes]` |
| `compute_delta` | `delta.py` | `compute_delta(state_a, state_b) -> dict` |
| `apply_delta` | `delta.py` | `apply_delta(state, delta) -> dict` |
| `evolve_schema` | `schema_evolution.py` | `evolve_schema(old_schema, new_fields, removed_fields=None, version=None) -> MergeSchema` |
| `check_compatibility` | `schema_evolution.py` | `check_compatibility(schema_v1, schema_v2) -> CompatibilityResult` |

## Layer 4: AI Functions

| Function | Module | Signature |
|----------|--------|-----------|
| `merge_datasets` | `datasets_ext.py` | `merge_datasets(dataset_a, dataset_b, key, schema=None) -> Dataset` |
