# crdt_merge.observability — Metrics, Tracing & Monitoring

> **Module**: `crdt_merge/observability.py` | **Layer**: 5 — Enterprise | **Version**: 0.9.3

---

## Overview

Provides observability primitives for crdt-merge: `MetricsCollector` for recording merge timing and conflict statistics, `HealthCheck` for evaluating operational health, `ObservedMerge` for auto-instrumented merges, `MergeTracer` for OpenTelemetry-compatible tracing, `DriftDetector` for schema and statistical drift detection, and `PrometheusExporter` / `GrafanaDashboard` for monitoring integration.

---

## Quick Start

```python
from crdt_merge.observability import ObservedMerge

om = ObservedMerge(node_id="edge-1")

left = [{"id": 1, "score": 10}, {"id": 2, "score": 20}]
right = [{"id": 1, "score": 15}, {"id": 3, "score": 30}]

result, metric = om.merge(left, right, key="id")
print(f"Duration: {metric.duration_ms:.2f}ms")
print(f"Conflicts: {metric.conflicts_detected}")
print(om.collector.get_summary())
```

---

## Classes

### `MergeMetric`

Single recorded observation of a merge (or related) operation. This is a **dataclass**.

```python
@dataclass
class MergeMetric:
    operation: str
    timestamp: float
    duration_ms: float
    input_record_count: int = 0
    output_record_count: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    strategy_used: str = ""
    node_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Fields:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `operation` | `str` | *(required)* | Operation type (e.g. `"merge"`, `"encrypt"`). |
| `timestamp` | `float` | *(required)* | Wall-clock time when recorded. |
| `duration_ms` | `float` | *(required)* | Duration of the operation in milliseconds. |
| `input_record_count` | `int` | `0` | Number of input records. |
| `output_record_count` | `int` | `0` | Number of output records. |
| `conflicts_detected` | `int` | `0` | Number of conflicts detected. |
| `conflicts_resolved` | `int` | `0` | Number of conflicts resolved. |
| `strategy_used` | `str` | `""` | Name of the strategy used. |
| `node_id` | `str` | `"default"` | Node identifier. |
| `metadata` | `Dict[str, Any]` | `{}` | Arbitrary metadata. |

**Methods:**

#### `to_dict() → Dict[str, Any]`

Serialise to a plain dictionary (via `dataclasses.asdict`).

---

### `MetricsCollector`

Thread-safe collector for `MergeMetric` instances with FIFO eviction.

```python
class MetricsCollector:
    def __init__(self, node_id: str = "default", max_history: int = 10_000) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `node_id` | `str` | `"default"` | Identifier of the node owning this collector. |
| `max_history` | `int` | `10_000` | Maximum number of metrics to retain (FIFO eviction). |

**Supports:** `len()`, `iter()`.

**Methods:**

#### `record_merge(left_count, right_count, result_count, duration_ms, strategy="", conflicts=0, **metadata) → MergeMetric`

Record a completed merge operation and return its metric.

**Parameters:**
- `left_count` (`int`): Number of left-side records.
- `right_count` (`int`): Number of right-side records.
- `result_count` (`int`): Number of result records.
- `duration_ms` (`float`): Duration in milliseconds.
- `strategy` (`str`): Strategy name.
- `conflicts` (`int`): Number of conflicts detected.
- `**metadata` (`Any`): Additional metadata.

**Returns:** `MergeMetric`

---

#### `record_operation(operation, duration_ms, **kwargs) → MergeMetric`

Record an arbitrary operation (encrypt, unmerge, audit, etc.).

**Parameters:**
- `operation` (`str`): Operation label.
- `duration_ms` (`float`): Duration in milliseconds.
- `**kwargs` (`Any`): Optional fields: `input_record_count`, `output_record_count`, `conflicts_detected`, `conflicts_resolved`, `strategy_used`, `error` (bool), plus arbitrary metadata.

**Returns:** `MergeMetric`

---

#### `record_error(operation, duration_ms, **kwargs) → MergeMetric`

Convenience wrapper — records an operation flagged as an error.

**Parameters:**
- `operation` (`str`): Operation label.
- `duration_ms` (`float`): Duration in milliseconds.
- `**kwargs` (`Any`): Additional keyword arguments.

**Returns:** `MergeMetric`

---

#### `get_metrics(operation=None, since=None, limit=None) → List[MergeMetric]`

Return metrics matching the given filters.

**Parameters:**
- `operation` (`Optional[str]`): Filter by operation type.
- `since` (`Optional[float]`): Minimum timestamp (inclusive).
- `limit` (`Optional[int]`): Return only the last N matching metrics.

**Returns:** `List[MergeMetric]`

---

#### `get_summary() → Dict[str, Any]`

Return aggregated statistics across all recorded metrics.

**Returns:** `Dict[str, Any]` — Contains keys: `total_operations`, `total_errors`, `avg_duration_ms`, `max_duration_ms`, `min_duration_ms`, `total_input_records`, `total_output_records`, `total_conflicts`, `conflict_rate`, `error_rate`, `operations_by_type`.

**Example:**
```python
collector = MetricsCollector(node_id="edge-1")
collector.record_merge(10, 10, 15, duration_ms=42.5, conflicts=3)
collector.record_merge(5, 5, 8, duration_ms=12.1, conflicts=1)

summary = collector.get_summary()
print(f"Total ops: {summary['total_operations']}")  # 2
print(f"Avg duration: {summary['avg_duration_ms']:.1f}ms")  # 27.3
print(f"Total conflicts: {summary['total_conflicts']}")  # 4
```

---

#### `reset() → None`

Drop all recorded metrics and reset counters.

---

#### `export_metrics(filepath=None) → str`

Serialise all metrics to JSON. Optionally write to a file.

**Parameters:**
- `filepath` (`Optional[str]`): Path to write the JSON output.

**Returns:** `str` — JSON string.

---

### `HealthCheck`

Evaluate operational health of a `MetricsCollector`.

```python
class HealthCheck:
    def __init__(
        self,
        collector: MetricsCollector,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `collector` | `MetricsCollector` | *(required)* | The metrics source. |
| `thresholds` | `Optional[Dict[str, float]]` | `None` | Override default thresholds. |

**Default Thresholds:**

| Key | Default | Description |
|-----|---------|-------------|
| `merge_time_ms` | `5000.0` | Avg merge duration threshold (ms). |
| `error_rate` | `0.05` | Error rate threshold (0.0–1.0). |
| `conflict_rate` | `0.5` | Conflict rate threshold. |

**Methods:**

#### `check_health() → Dict[str, Any]`

Return a health report dict. `status` is one of `"healthy"`, `"degraded"`, or `"unhealthy"`.

**Returns:** `Dict[str, Any]` — Keys: `status`, `checks` (per-check details), `summary` (from `get_summary()`).

- Values above 80% of the threshold are `"degraded"`.
- Values exceeding the threshold are `"unhealthy"`.

**Example:**
```python
from crdt_merge.observability import MetricsCollector, HealthCheck

collector = MetricsCollector()
collector.record_merge(10, 10, 15, duration_ms=100.0)

hc = HealthCheck(collector)
report = hc.check_health()
print(report["status"])  # "healthy"
print(report["checks"]["avg_merge_time"]["status"])  # "healthy"
```

---

### `ObservedMerge`

Wraps `crdt_merge.merge()` with automatic metrics collection.

```python
class ObservedMerge:
    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        node_id: str = "default",
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `collector` | `Optional[MetricsCollector]` | `None` | An existing collector. When `None`, a new one is created automatically. |
| `node_id` | `str` | `"default"` | Node identifier passed to the auto-created collector (ignored when `collector` is supplied). |

**Properties:**

| Name | Type | Description |
|------|------|-------------|
| `collector` | `MetricsCollector` | The underlying metrics collector. |

**Methods:**

#### `merge(left, right, key, schema=None, **kwargs) → Tuple[Any, MergeMetric]`

Perform a merge and return `(result, metric)`. Timing uses `time.perf_counter` for sub-millisecond precision. Errors are recorded via `record_error()` and re-raised.

**Parameters:**
- `left` (`Any`): Left dataset.
- `right` (`Any`): Right dataset.
- `key` (`Any`): Key column(s).
- `schema` (`Any`, optional): Merge schema.
- `**kwargs` (`Any`): Forwarded to `crdt_merge.merge()`.

**Returns:** `Tuple[Any, MergeMetric]` — Merged result and the recorded metric.

**Example:**
```python
from crdt_merge.observability import ObservedMerge

om = ObservedMerge(node_id="edge-1")

left = [{"id": 1, "val": "a"}, {"id": 2, "val": "b"}]
right = [{"id": 1, "val": "A"}, {"id": 3, "val": "c"}]

result, metric = om.merge(left, right, key="id")
print(f"Duration: {metric.duration_ms:.2f}ms")
print(f"Conflicts: {metric.conflicts_detected}")
print(f"Input records: {metric.input_record_count}")
print(f"Output records: {metric.output_record_count}")

# Check cumulative stats
summary = om.collector.get_summary()
print(f"Total operations: {summary['total_operations']}")
```

---

### `MergeTracer`

OpenTelemetry-compatible merge tracing. Falls back to no-op spans when `opentelemetry-api` is not installed.

```python
class MergeTracer:
    def __init__(
        self,
        service_name: str = "crdt-merge",
        collector: Optional[MetricsCollector] = None,
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `service_name` | `str` | `"crdt-merge"` | OpenTelemetry service name for the tracer. |
| `collector` | `Optional[MetricsCollector]` | `None` | Optional collector to record metrics alongside traces. |

**Properties:**

| Name | Type | Description |
|------|------|-------------|
| `is_enabled` | `bool` | `True` when OpenTelemetry is available. |

**Methods:**

#### `get_tracer() → Any`

Return the underlying OTel tracer, or `None` if OpenTelemetry is not installed.

---

#### `trace_merge(operation_name="merge", attributes=None)` *(context manager)*

Context manager that creates an OTel span (or no-op) for a merge. Records `duration_ms`, `status`, and exceptions.

**Parameters:**
- `operation_name` (`str`): Span operation name. Default: `"merge"`.
- `attributes` (`Optional[Dict[str, Any]]`): Span attributes.

**Yields:** An OpenTelemetry span (or `_NoOpSpan`).

**Example:**
```python
from crdt_merge.observability import MergeTracer
from crdt_merge import merge

tracer = MergeTracer(service_name="my-service")
with tracer.trace_merge("merge_users", {"key": "user_id"}) as span:
    result = merge(left, right, key="user_id")
# Span automatically records duration and status
```

---

#### `trace_batch(operation_name="batch_merge", batch_size=0)` *(context manager)*

Context manager for tracing a batch of merges.

**Parameters:**
- `operation_name` (`str`): Span name. Default: `"batch_merge"`.
- `batch_size` (`int`): Number of items in the batch.

**Yields:** An OpenTelemetry span (or `_NoOpSpan`).

---

### `DriftReport`

Result of a `DriftDetector.check()` call. This is a **dataclass**.

```python
@dataclass
class DriftReport:
    has_drift: bool
    schema_changes: Dict[str, Any] = field(default_factory=dict)
    statistical_drift: Dict[str, Any] = field(default_factory=dict)
    checked_at: float = 0.0
```

**Fields:**

| Name | Type | Description |
|------|------|-------------|
| `has_drift` | `bool` | `True` if any drift was detected. |
| `schema_changes` | `Dict[str, Any]` | Contains `added`, `removed`, and `type_changed` keys. |
| `statistical_drift` | `Dict[str, Any]` | Per-column drift info (baseline_mean, current_mean, drift_score). |
| `checked_at` | `float` | Timestamp of the check. |

**Methods:**

#### `to_dict() → Dict[str, Any]`

Serialise to a plain dictionary.

---

### `DriftDetector`

Detects schema and statistical drift between merge operations by comparing current data against a stored baseline.

```python
class DriftDetector:
    def __init__(self, sensitivity: float = 2.0) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `sensitivity` | `float` | `2.0` | Number of standard deviations a column mean must shift to be flagged as statistical drift. |

**Methods:**

#### `record_baseline(records: List[Dict[str, Any]]) → None`

Compute and store baseline schema and statistics from the given records.

**Parameters:**
- `records` (`List[Dict[str, Any]]`): Baseline dataset.

---

#### `check(records: List[Dict[str, Any]]) → DriftReport`

Compare records against the stored baseline. Detects:
- **Schema drift**: Added columns, removed columns, changed column types.
- **Statistical drift**: Column means shifted by more than `sensitivity` standard deviations.

**Parameters:**
- `records` (`List[Dict[str, Any]]`): Current dataset to check.

**Returns:** `DriftReport`

**Raises:** `RuntimeError` if no baseline has been recorded.

**Example:**
```python
from crdt_merge.observability import DriftDetector

detector = DriftDetector(sensitivity=2.0)

baseline = [{"id": 1, "score": 0.8}, {"id": 2, "score": 0.9}]
detector.record_baseline(baseline)

current = [{"id": 1, "score": 0.2, "new_col": "x"}, {"id": 2, "score": 0.1}]
report = detector.check(current)
print(report.has_drift)  # True
print(report.schema_changes["added"])  # ["new_col"]
print(report.statistical_drift)  # {"score": {"baseline_mean": 0.85, ...}}
```

---

#### `reset() → None`

Clear baseline data.

---

### `PrometheusExporter`

Export `MetricsCollector` data in Prometheus exposition text format. Works standalone or with the `prometheus_client` library.

```python
class PrometheusExporter:
    def __init__(
        self,
        metrics: List[MergeMetric],
        namespace: str = "crdt_merge",
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `metrics` | `List[MergeMetric]` | *(required)* | Snapshot of metrics to expose. |
| `namespace` | `str` | `"crdt_merge"` | Prometheus metric name prefix. |

**Class Methods:**

#### `from_collector(collector: MetricsCollector, namespace="crdt_merge") → PrometheusExporter`

Build an exporter from a `MetricsCollector`.

**Methods:**

#### `to_dict() → Dict[str, Any]`

Return raw aggregated metrics as a dict (totals, histogram buckets, etc.).

---

#### `expose() → str`

Generate Prometheus exposition text format with histogram buckets: `1, 5, 10, 50, 100, 500, 1000` ms.

Exposed metrics:
- `{namespace}_merges_total` (counter)
- `{namespace}_merge_duration_ms` (histogram)
- `{namespace}_conflicts_total` (counter)
- `{namespace}_errors_total` (counter)
- `{namespace}_records_processed_total` (counter)

**Example:**
```python
from crdt_merge.observability import MetricsCollector, PrometheusExporter

collector = MetricsCollector()
collector.record_merge(10, 10, 15, duration_ms=42.5)

exporter = PrometheusExporter.from_collector(collector)
print(exporter.expose())
# Outputs Prometheus text format
```

---

### `GrafanaDashboard`

Generate a Grafana dashboard JSON model for crdt-merge monitoring.

```python
class GrafanaDashboard:
    def __init__(
        self,
        title: str = "CRDT Merge Monitoring",
        datasource: str = "Prometheus",
        refresh: str = "30s",
    ) -> None
```

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `title` | `str` | `"CRDT Merge Monitoring"` | Dashboard title shown in the Grafana UI. |
| `datasource` | `str` | `"Prometheus"` | UID (or name) of the Prometheus data source. |
| `refresh` | `str` | `"30s"` | Auto-refresh interval. |

**Methods:**

#### `generate() → Dict[str, Any]`

Return a full Grafana dashboard JSON model. Includes panels for:
- Merge Throughput (timeseries)
- Merge Latency (histogram, p50/p95)
- Conflict Rate (gauge)
- Error Rate (stat)
- Health Status (stat)
- Drift Alerts (table)

**Returns:** `Dict[str, Any]` — Grafana dashboard JSON structure.

---

#### `to_json() → str`

Return the dashboard as a JSON string.

**Example:**
```python
from crdt_merge.observability import GrafanaDashboard

dashboard = GrafanaDashboard(title="My CRDT Monitoring")
json_model = dashboard.to_json()
# Import into Grafana via API or JSON import
```
