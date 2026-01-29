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
