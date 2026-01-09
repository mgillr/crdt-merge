# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
Conflict Topology Visualization — interactive conflict analysis with D3-compatible export.

Provides multi-dimensional analysis of merge conflict patterns:
  - Heatmaps: Which fields conflict most between which sources
  - Temporal: How conflicts evolve over time
  - Clusters: Related conflict groups
  - Summary: Human-readable overview

All outputs are D3-compatible JSON or CSV for visualization.

Usage::

    from crdt_merge.viz import ConflictTopology

    topo = ConflictTopology.from_merge(merge_result, provenance_log)
    print(topo.summary())           # Human-readable summary
    heatmap = topo.heatmap()        # Field × source conflict matrix
    json_data = topo.to_json()      # D3-compatible visualization data
    topo.to_csv("conflicts.csv")    # CSV export
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConflictRecord:
    """A single conflict event.

    Attributes:
        key: Record key where conflict occurred.
        field: Field name.
        sources: Contributing sources.
        values: Conflicting values.
        resolved_value: Value after resolution.
        strategy: Strategy used (default ``"lww"``).
        timestamp: When conflict occurred (ISO-8601 string, optional).
    """

    key: Any
    field: str
    sources: List[str]
    values: List[Any]
    resolved_value: Any
    strategy: str = "lww"
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "key": _safe(self.key),
            "field": self.field,
            "sources": list(self.sources),
            "values": [_safe(v) for v in self.values],
            "resolved_value": _safe(self.resolved_value),
            "strategy": self.strategy,
            "timestamp": self.timestamp,
        }

@dataclass
class ConflictCluster:
    """Group of related conflicts sharing a pattern.

    Attributes:
        fields: Fields involved.
        source_pairs: Source pairs in conflict.
        count: Number of conflicts.
        pattern: Description of pattern.
    """

    fields: List[str]
    source_pairs: List[Tuple[str, str]]
    count: int
    pattern: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val: Any) -> Any:
    """Convert value to a JSON-safe representation."""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    return repr(val)

def _source_pair_key(sources: List[str]) -> str:
    """Deterministic pair key from a source list."""
    s = sorted(set(sources))
    if len(s) >= 2:
        return f"{s[0]}↔{s[1]}"
    if len(s) == 1:
        return s[0]
    return "unknown"

# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class ConflictTopology:
    """Analyze and visualize merge conflict patterns.

    Provides multi-dimensional conflict analysis:
    - Heatmaps: Which fields conflict most between which sources
    - Temporal: How conflicts evolve over time
    - Clusters: Related conflict groups
    - Summary: Human-readable overview

    All outputs are D3-compatible JSON or CSV for visualization.
    """

    def __init__(self, conflicts: Optional[List[ConflictRecord]] = None) -> None:
        """Initialize with a list of conflict records.

        Args:
            conflicts: List of :class:`ConflictRecord` objects.
        """
        self._conflicts: List[ConflictRecord] = list(conflicts) if conflicts else []

    # -- Factory constructors -----------------------------------------------

    @classmethod
    def from_merge(cls, result: Any, provenance: Optional[Any] = None) -> ConflictTopology:
        """Create from a merge result and optional provenance log.

        Extracts conflict information from merge output and provenance data.

        Supports:
        - ``MergeQLResult`` objects (with ``.data`` and ``.conflicts`` attrs)
        - ``ProvenanceLog`` objects passed as *provenance*
        - Plain list-of-dicts *result* (scanned for ``_provenance`` keys)

        Args:
            result: Merge result (list of dicts with ``_provenance``, or ``MergeQLResult``).
            provenance: Optional ``ProvenanceLog`` for detailed analysis.

        Returns:
            :class:`ConflictTopology` instance.
        """
        conflicts: List[ConflictRecord] = []

        # --- Try MergeQLResult -------------------------------------------------
        if hasattr(result, "data") and hasattr(result, "plan"):
            # MergeQLResult — walk provenance entries if present
            prov = getattr(result, "provenance", None) or []
            for entry in prov:
                if isinstance(entry, dict):
                    for dec in entry.get("decisions", []):
                        if dec.get("source") == "conflict_resolved":
                            conflicts.append(ConflictRecord(
                                key=entry.get("key"),
                                field=dec.get("field", ""),
                                sources=["a", "b"],
                                values=[dec.get("value"), dec.get("alternative")],
                                resolved_value=dec.get("value"),
                                strategy=dec.get("strategy", "lww"),
                            ))

        # --- ProvenanceLog object ----------------------------------------------
        if provenance is not None:
            records = getattr(provenance, "records", [])
            for rec in records:
                key = getattr(rec, "key", None)
                for dec in getattr(rec, "conflicts", []):
                    conflicts.append(ConflictRecord(
                        key=key,
                        field=getattr(dec, "field", ""),
                        sources=["a", "b"],
                        values=[getattr(dec, "value", None),
                                getattr(dec, "alternative", None)],
                        resolved_value=getattr(dec, "value", None),
                        strategy=getattr(dec, "strategy", "lww"),
                    ))

        # --- Plain list of dicts with embedded _provenance ---------------------
        if isinstance(result, list):
            for row in result:
                if isinstance(row, dict) and "_provenance" in row:
                    prov_entry = row["_provenance"]
                    for dec in prov_entry.get("conflicts", []):
                        conflicts.append(ConflictRecord(
                            key=prov_entry.get("key"),
                            field=dec.get("field", ""),
                            sources=dec.get("sources", ["a", "b"]),
                            values=dec.get("values", []),
                            resolved_value=dec.get("resolved_value"),
                            strategy=dec.get("strategy", "lww"),
                        ))

        return cls(conflicts)

    @classmethod
    def from_records(cls, conflicts: List[Dict[str, Any]]) -> ConflictTopology:
        """Create from raw conflict dicts.

        Args:
            conflicts: List of dicts with keys:
                ``key``, ``field``, ``sources``, ``values``, ``resolved_value``.

        Returns:
            :class:`ConflictTopology` instance.
        """
        records = []
        for c in conflicts:
            records.append(ConflictRecord(
                key=c.get("key"),
                field=c.get("field", ""),
                sources=c.get("sources", []),
                values=c.get("values", []),
                resolved_value=c.get("resolved_value"),
                strategy=c.get("strategy", "lww"),
                timestamp=c.get("timestamp"),
            ))
        return cls(records)

    # -- Mutators -----------------------------------------------------------

    def add_conflict(self, conflict: ConflictRecord) -> None:
        """Add a conflict record."""
        self._conflicts.append(conflict)

    # -- Analysis -----------------------------------------------------------

    def heatmap(self) -> Dict[str, Dict[str, int]]:
        """Generate field × source conflict frequency matrix.

        Returns:
            Nested dict: ``{field: {source_pair: count}}``.
        """
        matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for c in self._conflicts:
            pair = _source_pair_key(c.sources)
            matrix[c.field][pair] += 1
        # Convert from defaultdict for clean output
        return {f: dict(pairs) for f, pairs in matrix.items()}

    def temporal_pattern(self) -> List[Dict[str, Any]]:
        """Analyze conflict patterns over time.

        Returns:
            List of time-bucketed conflict counts, sorted by timestamp.
        """
        by_ts: Dict[Optional[str], int] = Counter()
        for c in self._conflicts:
            by_ts[c.timestamp] += 1

        result: List[Dict[str, Any]] = []
        for ts, count in sorted(by_ts.items(), key=lambda x: (x[0] is None, x[0])):
            result.append({"timestamp": ts, "count": count})
        return result

    def clusters(self) -> List[ConflictCluster]:
        """Identify clusters of related conflicts.

        Clusters are grouped by (field, source_pair) combinations.

        Returns:
            List of :class:`ConflictCluster` groups.
        """
        # Group conflicts by the set of fields that share source pairs
        pair_fields: Dict[str, List[str]] = defaultdict(list)
        pair_counts: Counter = Counter()

        for c in self._conflicts:
            pair = _source_pair_key(c.sources)
            pair_fields[pair].append(c.field)
            pair_counts[pair] += 1

        clusters: List[ConflictCluster] = []
        for pair, fields in pair_fields.items():
            unique_fields = sorted(set(fields))
            parts = pair.split("↔")
            source_pairs = [(parts[0], parts[1])] if len(parts) == 2 else [(pair, pair)]
            count = pair_counts[pair]
            pattern = (
                f"{count} conflict(s) across {len(unique_fields)} field(s) "
                f"between {pair}"
            )
            clusters.append(ConflictCluster(
                fields=unique_fields,
                source_pairs=source_pairs,
                count=count,
                pattern=pattern,
            ))
        return clusters

    def field_frequency(self) -> Dict[str, int]:
        """Count conflicts per field.

        Returns:
            Dict mapping field names to conflict counts.
        """
        return dict(Counter(c.field for c in self._conflicts))

    def source_frequency(self) -> Dict[str, int]:
        """Count conflicts per source.

        Returns:
            Dict mapping source names to conflict counts.
        """
        freq: Counter = Counter()
        for c in self._conflicts:
            for s in c.sources:
                freq[s] += 1
        return dict(freq)

    def strategy_stats(self) -> Dict[str, int]:
        """Count which strategies resolved conflicts.

        Returns:
            Dict mapping strategy names to usage counts.
        """
        return dict(Counter(c.strategy for c in self._conflicts))

    def summary(self) -> str:
        """Generate human-readable conflict summary.

        Returns:
            Multi-line string with conflict statistics.
        """
        total = len(self._conflicts)
        if total == 0:
            return "No conflicts detected."

        fields = self.field_frequency()
        num_fields = len(fields)
        num_clusters = len(self.clusters())

        lines = [
            f"{total} conflicts across {num_fields} fields, {num_clusters} clusters",
        ]

        # Top conflicting fields
        top_fields = sorted(fields.items(), key=lambda x: -x[1])[:5]
        if top_fields:
            lines.append("Top fields:")
            for f, cnt in top_fields:
                lines.append(f"  {f}: {cnt}")

        # Strategy breakdown
        strats = self.strategy_stats()
        if strats:
            lines.append("Strategies:")
            for s, cnt in sorted(strats.items(), key=lambda x: -x[1]):
                lines.append(f"  {s}: {cnt}")

        return "\n".join(lines)

    # -- Export -------------------------------------------------------------

    def to_json(self) -> str:
        """Export as D3-compatible JSON.

        The JSON structure contains:
        - ``nodes``: list of field and source nodes
        - ``links``: list of conflict links between nodes
        - ``heatmap``: field × source frequency matrix
        - ``stats``: summary statistics

        Returns:
            JSON string with nodes and links.
        """
        # Collect all unique nodes
        field_nodes: set = set()
        source_nodes: set = set()
        for c in self._conflicts:
            field_nodes.add(c.field)
            for s in c.sources:
                source_nodes.add(s)

        nodes = []
        for f in sorted(field_nodes):
            nodes.append({"id": f"field:{f}", "label": f, "type": "field"})
        for s in sorted(source_nodes):
            nodes.append({"id": f"source:{s}", "label": s, "type": "source"})

        # Build links
        link_counts: Counter = Counter()
        for c in self._conflicts:
            for s in c.sources:
                link_counts[(f"field:{c.field}", f"source:{s}")] += 1

        links = []
        for (src, tgt), weight in link_counts.items():
            links.append({"source": src, "target": tgt, "weight": weight})

        data = {
            "nodes": nodes,
            "links": links,
            "heatmap": self.heatmap(),
            "stats": {
                "total_conflicts": len(self._conflicts),
                "field_frequency": self.field_frequency(),
                "source_frequency": self.source_frequency(),
                "strategy_stats": self.strategy_stats(),
            },
        }
        return json.dumps(data, indent=2, default=str)

    def to_csv(self, path: str) -> None:
        """Export conflict records to CSV.

        Args:
            path: Output CSV file path.
        """
        fieldnames = ["key", "field", "sources", "values", "resolved_value",
                       "strategy", "timestamp"]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for c in self._conflicts:
                writer.writerow({
                    "key": _safe(c.key),
                    "field": c.field,
                    "sources": ";".join(str(s) for s in c.sources),
                    "values": ";".join(str(_safe(v)) for v in c.values),
                    "resolved_value": _safe(c.resolved_value),
                    "strategy": c.strategy,
                    "timestamp": c.timestamp or "",
                })

    def to_csv_string(self) -> str:
        """Export conflict records to a CSV string.

        Returns:
            CSV-formatted string.
        """
        buf = io.StringIO()
        fieldnames = ["key", "field", "sources", "values", "resolved_value",
                       "strategy", "timestamp"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for c in self._conflicts:
            writer.writerow({
                "key": _safe(c.key),
                "field": c.field,
                "sources": ";".join(str(s) for s in c.sources),
                "values": ";".join(str(_safe(v)) for v in c.values),
                "resolved_value": _safe(c.resolved_value),
                "strategy": c.strategy,
                "timestamp": c.timestamp or "",
            })
        return buf.getvalue()

    def to_dict(self) -> Dict[str, Any]:
        """Export complete topology as dict.

        Returns:
            Dict with heatmap, clusters, summary, stats.
        """
        return {
            "heatmap": self.heatmap(),
            "clusters": [
                {
                    "fields": cl.fields,
                    "source_pairs": cl.source_pairs,
                    "count": cl.count,
                    "pattern": cl.pattern,
                }
                for cl in self.clusters()
            ],
            "summary": self.summary(),
            "field_frequency": self.field_frequency(),
            "source_frequency": self.source_frequency(),
            "strategy_stats": self.strategy_stats(),
            "total_conflicts": len(self._conflicts),
            "records": [c.to_dict() for c in self._conflicts],
        }

    # -- Dunder -------------------------------------------------------------

    def __len__(self) -> int:
        """Number of conflict records."""
        return len(self._conflicts)

    def __repr__(self) -> str:
        n = len(self._conflicts)
        fields = len(self.field_frequency())
        return f"ConflictTopology(conflicts={n}, fields={fields})"
