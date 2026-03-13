# Flight Server

> Arrow Flight Merge-as-a-Service — gRPC-based merge server.

**Source:** `crdt_merge/accelerators/flight_server.py`  
**Lines of Code:** 488

## Overview

Implements ``DoExchange`` for streaming CRDT merge via gRPC.
Clients send two Arrow streams, receive one merged stream.
Strategy configuration via Flight metadata headers.

All Arrow / Flight dependencies are lazily imported.

Example::

    from crdt_merge.accelerators.flight_server import FlightMergeServer

    server = FlightMergeServer(host="0.0.0.0", port=8815)
    server.serve()  # blocking

## Classes

### `FlightMergeServer`

Arrow Flight server for merge-as-a-service.

**Class Attributes:**

- `name` — `str = 'flight_server'`
- `version` — `str = '0.7.0'`

**Constructor:**

```python
FlightMergeServer(host: str = '0.0.0.0', port: int = 8815, default_schema: Optional[MergeSchema] = None) -> None
```

Initialise the Flight merge server.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_available` | `is_available() -> bool` | Return True if pyarrow.flight is importable. |
| `serve` | `serve() -> None` | Start the Flight server (blocking). |
| `start` | `start() -> None` | Start the Flight server in a background thread. |
| `stop` | `stop() -> None` | Stop the Flight server. |
| `do_merge` | `do_merge(left: Any, right: Any, key: str, strategies: Optional[Dict[str, str]] = None) -> Tuple[Any, int]` | Merge two Arrow tables (or list-of-dicts) directly. |
| `do_exchange` | `do_exchange(context: Any, descriptor: Any, reader: Any, writer: Any) -> None` | Handle DoExchange RPC — receive two streams, return merged stream. |
| `do_get` | `do_get(context: Any, ticket: Any) -> Any` | Handle DoGet — retrieve previously merged results. |
| `list_flights` | `list_flights(context: Any = None, criteria: Any = None) -> List[Dict[str, Any]]` | List available merge endpoints. |
| `health_check` | `health_check() -> Dict[str, Any]` | — |

### `_FlightServerImpl`

Thin wrapper used only when pyarrow.flight is available.

**Constructor:**

```python
_FlightServerImpl(location: Any, merge_schema: MergeSchema, cache: Dict[str, List[dict]]) -> None
```

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `serve` | `serve() -> None` | — |
| `shutdown` | `shutdown() -> None` | — |

### `FlightMergeClient`

Client for the Arrow Flight merge service.

**Constructor:**

```python
FlightMergeClient(location: str) -> None
```

Connect to a Flight merge server.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `merge` | `merge(left: Any, right: Any, key: str = 'id', strategies: Optional[Dict[str, str]] = None) -> Any` | Send two tables to the merge server and receive merged result. |
| `close` | `close() -> None` | Close the client connection. |

**Special Methods:**

- `__enter__() -> FlightMergeClient` — —
- `__exit__(*exc: Any) -> None` — —

## Functions

### `_resolve_strategy_name()`

```python
_resolve_strategy_name(name: str) -> MergeStrategy
```

Defined in `crdt_merge/accelerators/flight_server.py`.

### `_table_to_records()`

```python
_table_to_records(table: Any) -> List[dict]
```

Convert a ``pyarrow.Table`` to list-of-dicts.

### `_records_to_table()`

```python
_records_to_table(records: List[dict]) -> Any
```

Convert list-of-dicts to a ``pyarrow.Table``.

### `_merge_records()`

```python
_merge_records(left: List[dict], right: List[dict], key: str, schema: MergeSchema) -> Tuple[List[dict], int]
```

Defined in `crdt_merge/accelerators/flight_server.py`.

### `_build_schema()`

```python
_build_schema(strategies: Optional[Dict[str, str]] = None) -> MergeSchema
```

Build a ``MergeSchema`` from a strategy name map.

### `_parse_metadata()`

```python
_parse_metadata(raw_metadata: Any) -> Dict[str, str]
```

Extract a dict from Arrow Flight metadata bytes/headers.

## Constants / Module Variables

- `_STRATEGY_MAP` — `Dict[str, type] = {'lww': LWW, 'max': MaxWins, 'maxwins': MaxWins, 'min': MinWins, 'minwins': MinWins, 'union': Uni...`
