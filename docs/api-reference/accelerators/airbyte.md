# Accelerator: airbyte

**Module**: `crdt_merge/accelerators/airbyte.py`
**Category**: Accelerator Integration

---

Airbyte connector for CRDT merge as an ETL destination.

Configurable via Airbyte connection settings with CRDT merge strategies per stream.


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class AirbyteMessage`

Simplified Airbyte protocol message.

**Attributes:**
- `type`: `str`
- `record`: `Optional[Dict[str, Any]]`
- `state`: `Optional[Dict[str, Any]]`
- `log`: `Optional[Dict[str, Any]]`
- `spec`: `Optional[Dict[str, Any]]`
- `connection_status`: `Optional[Dict[str, Any]]`



### `class AirbyteRecordMessage`

An individual Airbyte record.

**Attributes:**
- `stream`: `str`
- `data`: `Dict[str, Any]`
- `emitted_at`: `float`
- `namespace`: `Optional[str]`



### `class StreamConfig`

Per-stream CRDT merge configuration.

**Attributes:**
- `key_column`: `str`
- `strategies`: `Dict[str, str]`
- `default_strategy`: `str`
- `timestamp_column`: `str`
- `provenance_enabled`: `bool`



### `StreamConfig.resolve_strategy_name(self, column: str) → str`

Return the strategy name for a given column.

**Parameters:**
- `column` (`str`)

**Returns:** `str`



### `class WriteResult`

Result of a write operation.

**Attributes:**
- `stream_name`: `str`
- `records_written`: `int`
- `records_merged`: `int`
- `conflicts_resolved`: `int`
- `merge_time_ms`: `float`



### `WriteResult.to_dict(self) → Dict[str, Any]`

Serialise to plain dict.

**Returns:** `Dict[str, Any]`



### `class _StreamStore`

In-memory record store for a single Airbyte stream.



### `_StreamStore.records(self) → List[Dict[str, Any]]`

*No docstring — needs documentation.*

**Returns:** `List[Dict[str, Any]]`



### `_StreamStore.count(self) → int`

*No docstring — needs documentation.*

**Returns:** `int`



### `_StreamStore.put(self, record: Dict[str, Any], timestamp: float) → None`

Store a (merged) record.

**Parameters:**
- `record` (`Dict[str, Any]`)
- `timestamp` (`float`)

**Returns:** `None`



### `_StreamStore.get_timestamp(self, key: Any) → float`

*No docstring — needs documentation.*

**Parameters:**
- `key` (`Any`)

**Returns:** `float`



### `_StreamStore.clear(self) → None`

*No docstring — needs documentation.*

**Returns:** `None`



### `class AirbyteMergeDestination`

Airbyte custom destination connector with CRDT merge semantics.

    Attributes:
        name: Accelerator name for the registry.
        version: Connector version string.
    

**Attributes:**
- `name`: `str`
- `version`: `str`



### `AirbyteMergeDestination.health_check(self) → Dict[str, Any]`

Return health / readiness status.

**Returns:** `Dict[str, Any]`



### `AirbyteMergeDestination.is_available(self) → bool`

Always available — no hard external deps.

**Returns:** `bool`



### `AirbyteMergeDestination.get_spec(self) → Dict[str, Any]`

Return the Airbyte connector specification.

        Returns:
            Dict matching the Airbyte connector spec schema.
        

**Returns:** `Dict[str, Any]`



### `AirbyteMergeDestination.check_connection(self, config: Dict[str, Any]) → Tuple[bool, Optional[str]]`

Validate the connection configuration.

        Args:
            config: Connector config dict from Airbyte.

        Returns:
            (success, error_message_or_None)
        

**Parameters:**
- `config` (`Dict[str, Any]`)

**Returns:** `Tuple[bool, Optional[str]]`



### `AirbyteMergeDestination.read_stream(self, stream_name: str) → List[Dict[str, Any]]`

Read all merged records from a stream.

        Args:
            stream_name: Name of the stream.

        Returns:
            List of merged record dicts.
        

**Parameters:**
- `stream_name` (`str`)

**Returns:** `List[Dict[str, Any]]`



### `AirbyteMergeDestination.get_state(self) → Dict[str, Any]`

Return current connector state.

**Returns:** `Dict[str, Any]`



### `AirbyteMergeDestination.get_write_results(self) → List[WriteResult]`

Return all write results since initialisation.

**Returns:** `List[WriteResult]`



### `AirbyteMergeDestination.clear_stream(self, stream_name: str) → None`

Clear all records in a stream.

**Parameters:**
- `stream_name` (`str`)

**Returns:** `None`



### `AirbyteMergeDestination.list_streams(self) → List[str]`

Return names of all active streams.

**Returns:** `List[str]`

