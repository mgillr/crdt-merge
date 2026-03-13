# crdt_merge.parquet — Parquet Engine

**Module**: `crdt_merge/parquet.py`
**Layer**: 2 — Merge Engines
**LOC**: 476 *(corrected 2026-03-31 — was 625 from inventory; AST-verified actual: 476)*
**Dependencies**: `crdt_merge.arrow`, `pyarrow`, `pyarrow.parquet`

---

## Classes

### SelfMergingParquet
Parquet files that automatically merge on read.

```python
class SelfMergingParquet:
    def __init__(self, path: str, key: str, schema: Optional[MergeSchema] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `write()` | `write(data: DataFrame) -> None` | Append data to Parquet store |
| `read()` | `read() -> DataFrame` | Read and auto-merge all partitions |
| `compact()` | `compact() -> None` | Compact all partitions into one merged file |
| `partitions()` | `partitions() -> List[str]` | List partition file paths |

### ParquetMerge
Direct Parquet file merging.

```python
class ParquetMerge:
    def __init__(self, schema: Optional[MergeSchema] = None) -> None
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge_files()` | `merge_files(paths: List[str], key: str, output: str) -> None` | Merge multiple Parquet files |


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class ParquetMergeMetadata`

Merge schema stored in Parquet key-value metadata.

    Embeds merge semantics (key, strategies, provenance config) in the
    Parquet file's metadata section so files are self-describing.
    

**Attributes:**
- `key_column`: `str`
- `strategies`: `Dict[str, str]`
- `provenance_enabled`: `bool`
- `schema_version`: `str`
- `created_at`: `Optional[str]`
- `source_count`: `int`
- `merge_count`: `int`



### `ParquetMergeMetadata.to_parquet_metadata(self) → Dict[str, str]`

Serialize to Parquet key-value metadata format.

        Returns:
            Dict suitable for embedding in Parquet file metadata.
        

**Returns:** `Dict[str, str]`



### `ParquetMergeMetadata.from_parquet_metadata(cls, meta: Dict[str, str]) → 'ParquetMergeMetadata'`

Deserialize from Parquet key-value metadata.

        Args:
            meta: Dict from Parquet file metadata.

        Returns:
            ParquetMergeMetadata instance.

        Raises:
            ValueError: If metadata is missing required fields.
        

**Parameters:**
- `meta` (`Dict[str, str]`)

**Returns:** `'ParquetMergeMetadata'`

**Raises:** `ValueError(f"Missing required metadata key '{_KEY_COLUMN_KEY}'. This file does not appear to be a self-merging Parquet file.")`



### `ParquetMergeMetadata.to_dict(self) → Dict[str, Any]`

Serialize to plain dict.

**Returns:** `Dict[str, Any]`



### `ParquetMergeMetadata.from_dict(cls, d: Dict[str, Any]) → 'ParquetMergeMetadata'`

Deserialize from plain dict.

**Parameters:**
- `d` (`Dict[str, Any]`)

**Returns:** `'ParquetMergeMetadata'`



### `class IngestResult`

Result of ingesting data into a self-merging Parquet file.

**Attributes:**
- `records_ingested`: `int`
- `conflicts_resolved`: `int`
- `new_records`: `int`
- `updated_records`: `int`
- `merge_time_ms`: `float`
- `provenance_entries`: `int`



### `class CompactResult`

Result of compacting a self-merging Parquet file.

**Attributes:**
- `records_before`: `int`
- `records_after`: `int`
- `duplicates_removed`: `int`
- `compact_time_ms`: `float`



### `class ProvenanceEntry`

A single provenance log entry for an ingest operation.

**Attributes:**
- `source`: `str`
- `timestamp`: `float`
- `records_ingested`: `int`
- `conflicts_resolved`: `int`
- `new_records`: `int`
- `updated_records`: `int`



### `ProvenanceEntry.to_dict(self) → Dict[str, Any]`

Serializes this provenance entry to a plain dictionary with keys: `source`, `timestamp`, `records_ingested`, `conflicts_resolved`, `new_records`, and `updated_records`.

**Returns:** `Dict[str, Any]`



### `SelfMergingParquet.metadata(self) → ParquetMergeMetadata`

Get the embedded merge metadata.

        Returns:
            ParquetMergeMetadata reflecting current container state.
        

**Returns:** `ParquetMergeMetadata`



### `SelfMergingParquet.merge_with(self, other: 'SelfMergingParquet') → IngestResult`

Merge another SelfMergingParquet into this one.

        Args:
            other: Another SelfMergingParquet container.

        Returns:
            IngestResult with merge statistics.
        

**Parameters:**
- `other` (`'SelfMergingParquet'`)

**Returns:** `IngestResult`

**Raises:** `ValueError(f"Key column mismatch: self uses '{self._key}', other uses '{other._key}'")`



### `SelfMergingParquet.get_provenance_log(self) → List[Dict[str, Any]]`

Return the provenance log as a list of dicts.

**Returns:** `List[Dict[str, Any]]`



### `SelfMergingParquet.to_parquet(self, path: str) → None`

Export to actual Parquet file with embedded metadata.

        Requires PyArrow.  Raises ImportError if not available.

        Args:
            path: Output file path.
        

**Parameters:**
- `path` (`str`)

**Returns:** `None`

**Raises:** `ImportError('PyArrow is required for Parquet I/O. Install it with: pip install pyarrow')`



### `SelfMergingParquet.from_parquet(cls, path: str) → 'SelfMergingParquet'`

Load from a Parquet file with embedded merge metadata.

        Requires PyArrow.  Raises ImportError if not available.

        Args:
            path: Input file path.

        Returns:
            SelfMergingParquet instance with data and metadata loaded.
        

**Parameters:**
- `path` (`str`)

**Returns:** `'SelfMergingParquet'`

**Raises:** `ImportError('PyArrow is required for Parquet I/O. Install it with: pip install pyarrow')`

