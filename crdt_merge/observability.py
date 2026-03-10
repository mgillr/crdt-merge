# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
# Patent Pending: UK Application No. 2607132.4
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Observability primitives for crdt-merge.

Provides :class:`MetricsCollector` for recording merge timing and conflict
statistics, :class:`HealthCheck` for evaluating operational health, and
:class:`ObservedMerge` — a thin wrapper around :func:`crdt_merge.merge` that
collects metrics automatically.

Example::

    from crdt_merge.observability import ObservedMerge

    om = ObservedMerge(node_id="edge-1")
    result, metric = om.merge(left, right, key="id")
    print(metric.duration_ms)
    print(om.collector.get_summary())
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Dict, Iterator, List, Optional, Tuple

from crdt_merge import merge as _crdt_merge

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MergeMetric
# ---------------------------------------------------------------------------


@dataclass
class MergeMetric:
    """Single recorded observation of a merge (or related) operation."""

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

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Thread-safe collector for :class:`MergeMetric` instances.

    Parameters
    ----------
    node_id:
        Identifier of the node owning this collector.
    max_history:
        Maximum number of metrics to retain (FIFO eviction).
    """

    def __init__(self, node_id: str = "default", max_history: int = 10_000) -> None:
        self._node_id = node_id
        self._max_history = max_history
        self._metrics: Deque[MergeMetric] = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._error_count: int = 0
        self._total_count: int = 0

    # -- recording -----------------------------------------------------------

    def record_merge(
        self,
        left_count: int,
        right_count: int,
        result_count: int,
        duration_ms: float,
        strategy: str = "",
        conflicts: int = 0,
        **metadata: Any,
    ) -> MergeMetric:
        """Record a completed merge operation and return its metric."""
        metric = MergeMetric(
            operation="merge",
            timestamp=time.time(),
            duration_ms=duration_ms,
            input_record_count=left_count + right_count,
            output_record_count=result_count,
            conflicts_detected=conflicts,
            conflicts_resolved=conflicts,
            strategy_used=strategy,
            node_id=self._node_id,
            metadata=dict(metadata),
        )
        self._append(metric)
        return metric

    def record_operation(
        self,
        operation: str,
        duration_ms: float,
        **kwargs: Any,
    ) -> MergeMetric:
        """Record an arbitrary operation (encrypt, unmerge, audit, …)."""
        metric = MergeMetric(
            operation=operation,
            timestamp=time.time(),
            duration_ms=duration_ms,
            input_record_count=kwargs.get("input_record_count", 0),
            output_record_count=kwargs.get("output_record_count", 0),
            conflicts_detected=kwargs.get("conflicts_detected", 0),
            conflicts_resolved=kwargs.get("conflicts_resolved", 0),
            strategy_used=kwargs.get("strategy_used", ""),
            node_id=self._node_id,
            metadata={
                k: v
                for k, v in kwargs.items()
                if k
                not in {
                    "input_record_count",
                    "output_record_count",
                    "conflicts_detected",
                    "conflicts_resolved",
                    "strategy_used",
                }
            },
        )
        is_error = kwargs.get("error", False)
        self._append(metric, is_error=is_error)
        return metric

    def record_error(self, operation: str, duration_ms: float, **kwargs: Any) -> MergeMetric:
        """Convenience wrapper — records an operation flagged as an error."""
        kwargs["error"] = True
        return self.record_operation(operation, duration_ms, **kwargs)

    # -- querying ------------------------------------------------------------

    def get_metrics(
        self,
        operation: Optional[str] = None,
        since: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[MergeMetric]:
        """Return metrics matching the given filters."""
        with self._lock:
            out: List[MergeMetric] = []
            for m in self._metrics:
                if operation is not None and m.operation != operation:
                    continue
                if since is not None and m.timestamp < since:
                    continue
                out.append(m)
            if limit is not None:
                out = out[-limit:]
            return out

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregated statistics across all recorded metrics."""
        with self._lock:
            metrics = list(self._metrics)

        if not metrics:
            return {
                "total_operations": 0,
                "total_errors": self._error_count,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "total_input_records": 0,
                "total_output_records": 0,
                "total_conflicts": 0,
                "conflict_rate": 0.0,
                "error_rate": 0.0,
                "operations_by_type": {},
            }

        durations = [m.duration_ms for m in metrics]
        total_conflicts = sum(m.conflicts_detected for m in metrics)
        total_ops = len(metrics)
        ops_by_type: Dict[str, int] = {}
        for m in metrics:
            ops_by_type[m.operation] = ops_by_type.get(m.operation, 0) + 1

        return {
            "total_operations": total_ops,
            "total_errors": self._error_count,
            "avg_duration_ms": sum(durations) / total_ops,
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "total_input_records": sum(m.input_record_count for m in metrics),
            "total_output_records": sum(m.output_record_count for m in metrics),
            "total_conflicts": total_conflicts,
            "conflict_rate": total_conflicts / total_ops if total_ops else 0.0,
            "error_rate": self._error_count / self._total_count if self._total_count else 0.0,
            "operations_by_type": ops_by_type,
        }

    # -- lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        """Drop all recorded metrics."""
        with self._lock:
            self._metrics.clear()
            self._error_count = 0
            self._total_count = 0

    def export_metrics(self, filepath: Optional[str] = None) -> str:
        """Serialise all metrics to JSON.  Optionally write to *filepath*."""
        with self._lock:
            data = [m.to_dict() for m in self._metrics]
        payload = json.dumps(data, default=str, indent=2)
        if filepath:
            with open(filepath, "w") as fh:
                fh.write(payload)
            logger.debug("exported %d metrics to %s", len(data), filepath)
        return payload

    # -- dunder protocols ----------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._metrics)

    def __iter__(self) -> Iterator[MergeMetric]:
        with self._lock:
            return iter(list(self._metrics))

    # -- internals -----------------------------------------------------------

    def _append(self, metric: MergeMetric, *, is_error: bool = False) -> None:
        with self._lock:
            self._metrics.append(metric)
            self._total_count += 1
            if is_error:
                self._error_count += 1


# ---------------------------------------------------------------------------
# HealthCheck
# ---------------------------------------------------------------------------


_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "merge_time_ms": 5000.0,
    "error_rate": 0.05,
    "conflict_rate": 0.5,
}


class HealthCheck:
    """Evaluate operational health of a :class:`MetricsCollector`.

    Parameters
    ----------
    collector:
        The metrics source.
    thresholds:
        Override default thresholds (merge_time_ms, error_rate, conflict_rate).
    """

    def __init__(
        self,
        collector: MetricsCollector,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._collector = collector
        self._thresholds: Dict[str, float] = {**_DEFAULT_THRESHOLDS}
        if thresholds:
            self._thresholds.update(thresholds)

    def check_health(self) -> Dict[str, Any]:
        """Return a health report dict.

        ``status`` is one of ``"healthy"``, ``"degraded"``, ``"unhealthy"``.
        """
        summary = self._collector.get_summary()
        checks: Dict[str, Dict[str, Any]] = {}
        status = "healthy"

        # -- avg merge time --------------------------------------------------
        avg_ms = summary["avg_duration_ms"]
        threshold_ms = self._thresholds["merge_time_ms"]
        if avg_ms > threshold_ms:
            checks["avg_merge_time"] = {
                "status": "unhealthy",
                "value": avg_ms,
                "threshold": threshold_ms,
            }
            status = "unhealthy"
        elif avg_ms > threshold_ms * 0.8:
            checks["avg_merge_time"] = {
                "status": "degraded",
                "value": avg_ms,
                "threshold": threshold_ms,
            }
            if status != "unhealthy":
                status = "degraded"
        else:
            checks["avg_merge_time"] = {
                "status": "healthy",
                "value": avg_ms,
                "threshold": threshold_ms,
            }

        # -- error rate ------------------------------------------------------
        err_rate = summary["error_rate"]
        err_thresh = self._thresholds["error_rate"]
        if err_rate > err_thresh:
            checks["error_rate"] = {
                "status": "unhealthy",
                "value": err_rate,
                "threshold": err_thresh,
            }
            status = "unhealthy"
        elif err_rate > err_thresh * 0.8:
            checks["error_rate"] = {
                "status": "degraded",
                "value": err_rate,
                "threshold": err_thresh,
            }
            if status != "unhealthy":
                status = "degraded"
        else:
            checks["error_rate"] = {
                "status": "healthy",
                "value": err_rate,
                "threshold": err_thresh,
            }

        # -- conflict rate ---------------------------------------------------
        cfl_rate = summary["conflict_rate"]
        cfl_thresh = self._thresholds["conflict_rate"]
        if cfl_rate > cfl_thresh:
            checks["conflict_rate"] = {
                "status": "unhealthy",
                "value": cfl_rate,
                "threshold": cfl_thresh,
            }
            status = "unhealthy"
        elif cfl_rate > cfl_thresh * 0.8:
            checks["conflict_rate"] = {
                "status": "degraded",
                "value": cfl_rate,
                "threshold": cfl_thresh,
            }
            if status != "unhealthy":
                status = "degraded"
        else:
            checks["conflict_rate"] = {
                "status": "healthy",
                "value": cfl_rate,
                "threshold": cfl_thresh,
            }

        return {"status": status, "checks": checks, "summary": summary}


# ---------------------------------------------------------------------------
# ObservedMerge — auto-instrumented merge wrapper
# ---------------------------------------------------------------------------


class ObservedMerge:
    """Wraps :func:`crdt_merge.merge` with automatic metrics collection.

    Parameters
    ----------
    collector:
        An existing :class:`MetricsCollector` instance.  One is created
        automatically when omitted.
    node_id:
        Node identifier passed to the auto-created collector.
    """

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        node_id: str = "default",
    ) -> None:
        if collector is not None:
            self._collector = collector
        else:
            self._collector = MetricsCollector(node_id=node_id)

    @property
    def collector(self) -> MetricsCollector:
        """The underlying :class:`MetricsCollector`."""
        return self._collector

    def merge(
        self,
        left: Any,
        right: Any,
        key: Any,
        schema: Any = None,
        **kwargs: Any,
    ) -> Tuple[Any, MergeMetric]:
        """Perform a merge and return ``(result, metric)``.

        Timing uses :func:`time.perf_counter` for sub-millisecond precision.
        """
        left_count = len(left) if isinstance(left, list) else 0
        right_count = len(right) if isinstance(right, list) else 0

        strategy_name = ""
        if schema is not None:
            if hasattr(schema, "default") and schema.default is not None:
                strategy_name = type(schema.default).__name__

        t0 = time.perf_counter()
        try:
            result = _crdt_merge(left, right, key=key, schema=schema, **kwargs)
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._collector.record_error("merge", elapsed_ms)
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        result_count = len(result) if isinstance(result, list) else 0

        # Heuristic: conflicts ≈ keys present on both sides
        conflicts = 0
        if isinstance(left, list) and isinstance(right, list) and key:
            left_keys = {r.get(key) for r in left if isinstance(r, dict)}
            right_keys = {r.get(key) for r in right if isinstance(r, dict)}
            conflicts = len(left_keys & right_keys)

        metric = self._collector.record_merge(
            left_count=left_count,
            right_count=right_count,
            result_count=result_count,
            duration_ms=elapsed_ms,
            strategy=strategy_name,
            conflicts=conflicts,
        )
        return result, metric


# ---------------------------------------------------------------------------
# OpenTelemetry-compatible merge tracing
# ---------------------------------------------------------------------------

# Try importing OpenTelemetry; fall back to no-ops when unavailable.
try:
    from opentelemetry import trace as _otel_trace  # type: ignore[import-untyped]

    _HAS_OTEL = True
except ImportError:  # pragma: no cover – optional dependency
    _otel_trace = None  # type: ignore[assignment]
    _HAS_OTEL = False

# Try importing prometheus_client; fall back to None when unavailable.
try:
    import prometheus_client as _prom  # type: ignore[import-untyped]

    _HAS_PROM = True
except ImportError:  # pragma: no cover – optional dependency
    _prom = None  # type: ignore[assignment]
    _HAS_PROM = False

import math
from contextlib import contextmanager

__all__ = [
    "logger",
    "MergeMetric",
    "MetricsCollector",
    "HealthCheck",
    "ObservedMerge",
    "MergeTracer",
    "DriftReport",
    "DriftDetector",
    "PrometheusExporter",
    "GrafanaDashboard",
]


class _NoOpSpan:
    """Minimal stand-in for an OTel span when the SDK is absent."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D401
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        pass


class MergeTracer:
    """OpenTelemetry-compatible merge tracing.

    Falls back to no-op when ``opentelemetry-api`` is not installed.

    Example::

        tracer = MergeTracer(service_name="my-merge-service")
        with tracer.trace_merge("merge_users", {"key": "user_id"}) as span:
            result = merge(a, b, key="user_id")
        # span automatically records duration and status
    """

    def __init__(
        self,
        service_name: str = "crdt-merge",
        collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._service_name = service_name
        self._collector = collector
        self._tracer: Any = None
        if _HAS_OTEL:
            self._tracer = _otel_trace.get_tracer(service_name)  # type: ignore[union-attr]

    # -- public properties ---------------------------------------------------

    @property
    def is_enabled(self) -> bool:
        """Return ``True`` when OpenTelemetry is available."""
        return _HAS_OTEL

    def get_tracer(self) -> Any:
        """Return the underlying OTel tracer, or ``None``."""
        return self._tracer

    # -- context managers ----------------------------------------------------

    @contextmanager
    def trace_merge(
        self,
        operation_name: str = "merge",
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """Context manager that creates an OTel span (or no-op) for a merge.

        Records ``duration_ms``, ``status``, and exceptions.  When a
        :class:`MetricsCollector` was provided at init time the metric is also
        recorded there.
        """
        attrs = attributes or {}
        span: Any
        if self._tracer is not None:
            span = self._tracer.start_span(operation_name, attributes=attrs)
        else:
            span = _NoOpSpan()

        t0 = time.perf_counter()
        try:
            yield span
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.set_attribute("merge.duration_ms", elapsed_ms)
            span.set_attribute("merge.status", "ok")
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.set_attribute("merge.duration_ms", elapsed_ms)
            span.set_attribute("merge.status", "error")
            span.record_exception(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.end()
            if self._collector is not None:
                self._collector.record_operation(
                    operation_name,
                    elapsed_ms,
                    metadata=attrs,
                )

    @contextmanager
    def trace_batch(
        self,
        operation_name: str = "batch_merge",
        batch_size: int = 0,
    ) -> Iterator[Any]:
        """Context manager for tracing a batch of merges."""
        attrs = {"batch.size": batch_size}
        span: Any
        if self._tracer is not None:
            span = self._tracer.start_span(operation_name, attributes=attrs)
        else:
            span = _NoOpSpan()

        t0 = time.perf_counter()
        try:
            yield span
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.set_attribute("batch.duration_ms", elapsed_ms)
            span.set_attribute("batch.status", "ok")
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.set_attribute("batch.duration_ms", elapsed_ms)
            span.set_attribute("batch.status", "error")
            span.record_exception(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            span.end()
            if self._collector is not None:
                self._collector.record_operation(
                    operation_name,
                    elapsed_ms,
                    input_record_count=batch_size,
                )


# ---------------------------------------------------------------------------
# DriftReport dataclass
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Result of a :meth:`DriftDetector.check` call."""

    has_drift: bool
    schema_changes: Dict[str, Any] = field(default_factory=dict)
    statistical_drift: Dict[str, Any] = field(default_factory=dict)
    checked_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# DriftDetector
# ---------------------------------------------------------------------------


class DriftDetector:
    """Detects schema and statistical drift between merge operations.

    Example::

        detector = DriftDetector()
        detector.record_baseline([{"id": 1, "score": 0.8}, ...])
        report = detector.check([{"id": 1, "score": 0.2, "new_col": "x"}, ...])
        print(report.has_drift)  # True
    """

    def __init__(self, sensitivity: float = 2.0) -> None:
        self._sensitivity = sensitivity
        self._baseline_columns: Optional[List[str]] = None
        self._baseline_types: Optional[Dict[str, str]] = None
        self._baseline_stats: Optional[Dict[str, Dict[str, float]]] = None
        self._baseline_count: int = 0

    # -- public API ----------------------------------------------------------

    def record_baseline(self, records: List[Dict[str, Any]]) -> None:
        """Compute and store baseline schema and statistics."""
        if not records:
            self._baseline_columns = []
            self._baseline_types = {}
            self._baseline_stats = {}
            self._baseline_count = 0
            return

        columns: Dict[str, str] = {}
        for rec in records:
            for k, v in rec.items():
                if k not in columns:
                    columns[k] = type(v).__name__ if v is not None else "NoneType"

        self._baseline_columns = sorted(columns.keys())
        self._baseline_types = {k: columns[k] for k in self._baseline_columns}
        self._baseline_count = len(records)

        # Compute numeric stats
        self._baseline_stats = {}
        for col in self._baseline_columns:
            values = [
                rec[col]
                for rec in records
                if col in rec and isinstance(rec[col], (int, float))
            ]
            if values:
                mean = sum(values) / len(values)
                variance = sum((v - mean) ** 2 for v in values) / len(values)
                stddev = math.sqrt(variance)
                self._baseline_stats[col] = {"mean": mean, "stddev": stddev}

    def check(self, records: List[Dict[str, Any]]) -> DriftReport:
        """Compare *records* against the stored baseline."""
        if self._baseline_columns is None:
            raise RuntimeError("No baseline recorded — call record_baseline first.")

        # Current schema
        current_columns: Dict[str, str] = {}
        for rec in records:
            for k, v in rec.items():
                if k not in current_columns:
                    current_columns[k] = type(v).__name__ if v is not None else "NoneType"

        current_col_set = set(current_columns.keys())
        baseline_col_set = set(self._baseline_columns)

        added = sorted(current_col_set - baseline_col_set)
        removed = sorted(baseline_col_set - current_col_set)
        type_changed: Dict[str, Dict[str, str]] = {}
        for col in current_col_set & baseline_col_set:
            if current_columns[col] != self._baseline_types.get(col, ""):
                type_changed[col] = {
                    "baseline": self._baseline_types.get(col, ""),
                    "current": current_columns[col],
                }

        schema_changes: Dict[str, Any] = {
            "added": added,
            "removed": removed,
            "type_changed": type_changed,
        }

        # Statistical drift
        statistical_drift: Dict[str, Any] = {}
        if self._baseline_stats:
            for col, baseline in self._baseline_stats.items():
                values = [
                    rec[col]
                    for rec in records
                    if col in rec and isinstance(rec[col], (int, float))
                ]
                if not values:
                    continue
                current_mean = sum(values) / len(values)
                bm = baseline["mean"]
                bs = baseline["stddev"]
                if bs > 0:
                    drift_score = abs(current_mean - bm) / bs
                else:
                    drift_score = 0.0 if current_mean == bm else float("inf")
                if drift_score > self._sensitivity:
                    statistical_drift[col] = {
                        "baseline_mean": bm,
                        "current_mean": current_mean,
                        "drift_score": drift_score,
                    }

        has_drift = bool(added or removed or type_changed or statistical_drift)
        return DriftReport(
            has_drift=has_drift,
            schema_changes=schema_changes,
            statistical_drift=statistical_drift,
            checked_at=time.time(),
        )

    def reset(self) -> None:
        """Clear baseline data."""
        self._baseline_columns = None
        self._baseline_types = None
        self._baseline_stats = None
        self._baseline_count = 0


# ---------------------------------------------------------------------------
# PrometheusExporter
# ---------------------------------------------------------------------------

_HISTOGRAM_BUCKETS = (1, 5, 10, 50, 100, 500, 1000)


class PrometheusExporter:
    """Export :class:`MetricsCollector` data in Prometheus exposition format.

    Works standalone (generates text format) or with ``prometheus_client``
    if available.

    Example::

        exporter = PrometheusExporter.from_collector(collector)
        print(exporter.expose())  # Prometheus text format
    """

    def __init__(
        self,
        metrics: List[MergeMetric],
        namespace: str = "crdt_merge",
    ) -> None:
        self._metrics = metrics
        self._namespace = namespace

    @classmethod
    def from_collector(
        cls,
        collector: MetricsCollector,
        namespace: str = "crdt_merge",
    ) -> "PrometheusExporter":
        """Build an exporter from a :class:`MetricsCollector`."""
        return cls(metrics=list(collector), namespace=namespace)

    # -- exposition ----------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return raw aggregated metrics as a dict."""
        total = len(self._metrics)
        durations = [m.duration_ms for m in self._metrics]
        conflicts = sum(m.conflicts_detected for m in self._metrics)
        errors = sum(1 for m in self._metrics if m.metadata.get("error"))
        records = sum(m.input_record_count for m in self._metrics)

        buckets: Dict[str, int] = {}
        for b in _HISTOGRAM_BUCKETS:
            buckets[str(b)] = sum(1 for d in durations if d <= b)
        buckets["+Inf"] = total

        return {
            f"{self._namespace}_merges_total": total,
            f"{self._namespace}_merge_duration_ms": {
                "buckets": buckets,
                "sum": sum(durations) if durations else 0.0,
                "count": total,
            },
            f"{self._namespace}_conflicts_total": conflicts,
            f"{self._namespace}_errors_total": errors,
            f"{self._namespace}_records_processed_total": records,
        }

    def expose(self) -> str:
        """Generate Prometheus exposition text format."""
        ns = self._namespace
        data = self.to_dict()
        lines: List[str] = []

        # merges_total
        lines.append(f"# HELP {ns}_merges_total Total number of merge operations.")
        lines.append(f"# TYPE {ns}_merges_total counter")
        lines.append(f"{ns}_merges_total {data[f'{ns}_merges_total']}")
        lines.append("")

        # merge_duration_ms histogram
        dur = data[f"{ns}_merge_duration_ms"]
        lines.append(f"# HELP {ns}_merge_duration_ms Merge duration in milliseconds.")
        lines.append(f"# TYPE {ns}_merge_duration_ms histogram")
        for b in _HISTOGRAM_BUCKETS:
            lines.append(
                f'{ns}_merge_duration_ms_bucket{{le="{b}"}} {dur["buckets"][str(b)]}'
            )
        lines.append(
            f'{ns}_merge_duration_ms_bucket{{le="+Inf"}} {dur["buckets"]["+Inf"]}'
        )
        lines.append(f"{ns}_merge_duration_ms_sum {dur['sum']}")
        lines.append(f"{ns}_merge_duration_ms_count {dur['count']}")
        lines.append("")

        # conflicts_total
        lines.append(f"# HELP {ns}_conflicts_total Total conflicts detected.")
        lines.append(f"# TYPE {ns}_conflicts_total counter")
        lines.append(f"{ns}_conflicts_total {data[f'{ns}_conflicts_total']}")
        lines.append("")

        # errors_total
        lines.append(f"# HELP {ns}_errors_total Total merge errors.")
        lines.append(f"# TYPE {ns}_errors_total counter")
        lines.append(f"{ns}_errors_total {data[f'{ns}_errors_total']}")
        lines.append("")

        # records_processed_total
        lines.append(f"# HELP {ns}_records_processed_total Total records processed.")
        lines.append(f"# TYPE {ns}_records_processed_total counter")
        lines.append(
            f"{ns}_records_processed_total {data[f'{ns}_records_processed_total']}"
        )
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# GrafanaDashboard
# ---------------------------------------------------------------------------


class GrafanaDashboard:
    """Generate Grafana dashboard JSON model for crdt-merge monitoring.

    Example::

        dashboard = GrafanaDashboard(title="CRDT Merge Monitoring")
        json_model = dashboard.generate()
        # Import into Grafana via API or dashboard JSON import
    """

    def __init__(
        self,
        title: str = "CRDT Merge Monitoring",
        datasource: str = "Prometheus",
        refresh: str = "30s",
    ) -> None:
        self._title = title
        self._datasource = datasource
        self._refresh = refresh

    # -- panel builders ------------------------------------------------------

    def _ds(self) -> Dict[str, str]:
        return {"type": "prometheus", "uid": self._datasource}

    def _panel_throughput(self) -> Dict[str, Any]:
        return {
            "title": "Merge Throughput",
            "type": "timeseries",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "rate(crdt_merge_merges_total[5m])",
                    "legendFormat": "merges/s",
                }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        }

    def _panel_latency(self) -> Dict[str, Any]:
        return {
            "title": "Merge Latency",
            "type": "histogram",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "histogram_quantile(0.95, rate(crdt_merge_merge_duration_ms_bucket[5m]))",
                    "legendFormat": "p95",
                },
                {
                    "expr": "histogram_quantile(0.50, rate(crdt_merge_merge_duration_ms_bucket[5m]))",
                    "legendFormat": "p50",
                },
            ],
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        }

    def _panel_conflict_rate(self) -> Dict[str, Any]:
        return {
            "title": "Conflict Rate",
            "type": "gauge",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "rate(crdt_merge_conflicts_total[5m]) / rate(crdt_merge_merges_total[5m])",
                    "legendFormat": "conflict ratio",
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8},
        }

    def _panel_error_rate(self) -> Dict[str, Any]:
        return {
            "title": "Error Rate",
            "type": "stat",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "rate(crdt_merge_errors_total[5m])",
                    "legendFormat": "errors/s",
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 6, "y": 8},
        }

    def _panel_health_status(self) -> Dict[str, Any]:
        return {
            "title": "Health Status",
            "type": "stat",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "crdt_merge_health_status",
                    "legendFormat": "health",
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
        }

    def _panel_drift_alerts(self) -> Dict[str, Any]:
        return {
            "title": "Drift Alerts",
            "type": "table",
            "datasource": self._ds(),
            "targets": [
                {
                    "expr": "crdt_merge_drift_detected",
                    "legendFormat": "{{column}}",
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
        }

    # -- public API ----------------------------------------------------------

    def generate(self) -> Dict[str, Any]:
        """Return a full Grafana dashboard JSON model."""
        return {
            "dashboard": {
                "title": self._title,
                "uid": "crdt-merge-dashboard",
                "refresh": self._refresh,
                "schemaVersion": 39,
                "panels": [
                    self._panel_throughput(),
                    self._panel_latency(),
                    self._panel_conflict_rate(),
                    self._panel_error_rate(),
                    self._panel_health_status(),
                    self._panel_drift_alerts(),
                ],
                "templating": {"list": []},
                "time": {"from": "now-1h", "to": "now"},
            },
            "overwrite": True,
        }

    def to_json(self) -> str:
        """Return the dashboard as a JSON string."""
        return json.dumps(self.generate(), indent=2)
