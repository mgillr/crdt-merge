# Accelerator: flight-server

**Module**: `crdt_merge/accelerators/flight_server.py`
**Category**: Accelerator Integration

---

Apache Arrow Flight server for distributed CRDT merge queries.

```python
from crdt_merge.accelerators.flight_server import MergeFlightServer
server = MergeFlightServer(port=8815)
server.serve()
```


---

## Additional API (Pass 2 — Auditor Review)

*The following symbols were identified as missing during the second-pass review.*

### `class FlightMergeServer`

Arrow Flight server for merge-as-a-service.

    Implements DoExchange for streaming CRDT merge via gRPC.
    Clients send two Arrow record-batch streams (delimited by a sentinel),
    and receive one merged stream back.

    Attributes:
        name: Accelerator name.
        version: Accelerator version.
    

**Attributes:**
- `name`: `str`
- `version`: `str`



### `FlightMergeServer.is_available(self) → bool`

Return True if pyarrow.flight is importable.

**Returns:** `bool`



### `FlightMergeServer.start(self) → None`

Start the Flight server in a background thread.

**Returns:** `None`



### `FlightMergeServer.stop(self) → None`

Stop the Flight server.

**Returns:** `None`



### `FlightMergeServer.do_get(self, context: Any, ticket: Any) → Any`

Handle DoGet — retrieve previously merged results.

        The ticket should contain the cache key (string).
        

**Parameters:**
- `context` (`Any`)
- `ticket` (`Any`)

**Returns:** `Any`



### `FlightMergeServer.list_flights(self, context: Any = None, criteria: Any = None) → List[Dict[str, Any]]`

List available merge endpoints.

        Returns:
            List of endpoint descriptors.
        

**Parameters:**
- `context` (`Any`)
- `criteria` (`Any`)

**Returns:** `List[Dict[str, Any]]`



### `FlightMergeServer.health_check(self) → Dict[str, Any]`

*No docstring — needs documentation.*

**Returns:** `Dict[str, Any]`



### `class _FlightServerImpl`

Thin wrapper used only when pyarrow.flight is available.



### `_FlightServerImpl.shutdown(self) → None`

*No docstring — needs documentation.*

**Returns:** `None`



### `class FlightMergeClient`

Client for the Arrow Flight merge service.

    Example::

        client = FlightMergeClient("localhost:8815")
        result = client.merge(left_table, right_table, key="id", strategy="lww")
    



### `FlightMergeClient.close(self) → None`

Close the client connection.

**Returns:** `None`

