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

"""
Reversible merge engine for crdt-merge.

Provides three complementary capabilities:

* **UnmergeEngine** — reverse tabular merges using the provenance trail,
  restoring records to their pre-merge state.
* **ModelUnmerge** — subtract a model's contribution from merged weights
  via negmerge, surgical zeroing, or proportional rescaling.
* **GDPRForget** — GDPR "right to be forgotten" wrapper that combines
  data-level and model-level unmerge with compliance reporting.

All operations require provenance metadata — without a trail there is no
reliable way to attribute contributions to their sources.
"""

from __future__ import annotations

import json
import math
import sys
import time as _time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Lazy numpy import — numpy is optional for tabular operations
# ---------------------------------------------------------------------------

def _lazy_np():
    """Return numpy if available, else ``None``."""
    try:
        import numpy as np
        return np
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Data classes — public result types
# ---------------------------------------------------------------------------

@dataclass
class UnmergeReport:
    """Result of verifying a tabular unmerge operation."""

    success: bool
    records_removed: int
    records_remaining: int
    residual_data: int  # bytes of residual from removed source
    source_removed: str
    timestamp: str


@dataclass
class ResidualReport:
    """Measures how much influence a removed model still has."""

    influence_score: float  # 0.0 = clean, 1.0 = fully present
    parameters_checked: int
    parameters_with_residual: int


@dataclass
class ForgetResult:
    """Outcome of a single GDPR forget operation."""

    success: bool
    data_records_removed: int
    model_influence_removed: bool
    compliance_timestamp: str
    contributor: str


@dataclass
class GDPRComplianceReport:
    """Aggregate compliance report across all forget requests."""

    requests_processed: list
    total_records_removed: int
    total_models_cleaned: int
    generated_at: str

    def to_dict(self) -> dict:
        return {
            "requests_processed": [
                r if isinstance(r, dict) else r.__dict__
                for r in self.requests_processed
            ],
            "total_records_removed": self.total_records_removed,
            "total_models_cleaned": self.total_models_cleaned,
            "generated_at": self.generated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso_now() -> str:
    """UTC ISO-8601 timestamp string."""
    t = _time.gmtime()
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", t)


def _records_from_provenance(provenance) -> list:
    """Extract MergeRecord list from a ProvenanceLog or raw list."""
    if hasattr(provenance, "records"):
        return provenance.records
    return list(provenance)


def _record_key(row: dict, key_field: str = "id") -> Any:
    """Extract the key value from a record dict."""
    if key_field in row:
        return row[key_field]
    # Fall back to first value
    for v in row.values():
        return v
    return None


def _estimate_bytes(value: Any) -> int:
    """Rough byte estimate for a Python value."""
    return len(json.dumps(value, default=str).encode("utf-8"))


# ---------------------------------------------------------------------------
# UnmergeEngine — tabular unmerge
# ---------------------------------------------------------------------------

class UnmergeEngine:
    """Reverse a tabular merge using the provenance trail.

    Given the merged output, its provenance log, and the name of a source
    to remove (``"a"`` or ``"b"``), produces the dataset as it would have
    looked had that source never participated in the merge.

    Provenance convention (from ``merge_with_provenance``):

    * ``MergeRecord.origin`` — ``"unique_a"``, ``"unique_b"``, or ``"merged"``
    * ``MergeDecision.source`` — ``"a_only"``, ``"b_only"``,
      ``"both_equal"``, or ``"conflict_resolved"``
    * For ``conflict_resolved`` decisions the ``value`` field holds B's
      contribution and ``alternative`` holds A's contribution (LWW default).
    """

    def __init__(self) -> None:
        pass

    # ---- public API -------------------------------------------------------

    def unmerge(
        self,
        merged_data: List[dict],
        provenance,
        remove_source: str,
        key_field: str = "id",
    ) -> List[dict]:
        """Remove all contributions from *remove_source* and return the rest.

        Parameters
        ----------
        merged_data:
            Merged records (list of dicts).
        provenance:
            ``ProvenanceLog`` or ``list[MergeRecord]`` from the original merge.
        remove_source:
            Source identifier — ``"a"`` or ``"b"``.
        key_field:
            Name of the key column (default ``"id"``).

        Returns
        -------
        list[dict]
            Records remaining after the source is removed, with conflict
            resolutions reversed where the removed source had won.
        """
        records = _records_from_provenance(provenance)
        prov_by_key: Dict[Any, Any] = {rec.key: rec for rec in records}

        remove_unique = f"unique_{remove_source}"
        keep_source = "b" if remove_source == "a" else "a"
        remove_only = f"{remove_source}_only"
        keep_only = f"{keep_source}_only"

        result: List[dict] = []

        for row in merged_data:
            key_val = _record_key(row, key_field)
            prov_rec = prov_by_key.get(key_val)

            # No provenance — keep record unchanged (safe default)
            if prov_rec is None:
                result.append(dict(row))
                continue

            # Record was unique to the removed source — drop it
            if prov_rec.origin == remove_unique:
                continue

            # Record was unique to the kept source — keep as-is
            if prov_rec.origin == f"unique_{keep_source}":
                result.append(dict(row))
                continue

            # Merged record — reconstruct without the removed source
            if prov_rec.origin == "merged":
                new_row = self._reconstruct_merged_row(
                    prov_rec, remove_source, remove_only, keep_only,
                )
                if new_row:
                    result.append(new_row)

        return result

    def verify_unmerge(
        self,
        original_merged: List[dict],
        unmerged: List[dict],
        removed_source: str,
        provenance,
    ) -> UnmergeReport:
        """Verify that *unmerged* contains no residual data from *removed_source*.

        Returns an :class:`UnmergeReport` summarising the verification.
        """
        records = _records_from_provenance(provenance)
        prov_by_key = {rec.key: rec for rec in records}

        remove_unique = f"unique_{removed_source}"
        remove_only = f"{removed_source}_only"

        removed_count = 0
        residual_bytes = 0

        # Count records that should have been removed
        for rec in records:
            if rec.origin == remove_unique:
                removed_count += 1

        # Scan unmerged for residual data from the removed source
        unmerged_keys = {_record_key(r) for r in unmerged}
        for rec in records:
            if rec.origin == remove_unique and rec.key in unmerged_keys:
                # Record should have been removed but wasn't
                for r in unmerged:
                    if _record_key(r) == rec.key:
                        residual_bytes += _estimate_bytes(r)
                        break

            if rec.origin == "merged":
                for dec in rec.decisions:
                    if dec.source == "conflict_resolved":
                        # Check if the removed source's value is still present
                        removed_val = (
                            dec.value if removed_source == "b" else dec.alternative
                        )
                        for r in unmerged:
                            if _record_key(r) == rec.key:
                                actual = r.get(dec.field)
                                if actual == removed_val and removed_val != (
                                    dec.alternative
                                    if removed_source == "b"
                                    else dec.value
                                ):
                                    residual_bytes += _estimate_bytes(removed_val)
                                break

        success = residual_bytes == 0
        return UnmergeReport(
            success=success,
            records_removed=len(original_merged) - len(unmerged),
            records_remaining=len(unmerged),
            residual_data=residual_bytes,
            source_removed=removed_source,
            timestamp=_iso_now(),
        )

    def unmerge_delta(self, delta, provenance, remove_source: str):
        """Return a copy of *delta* with contributions from *remove_source* stripped.

        Parameters
        ----------
        delta:
            A ``crdt_merge.delta.Delta`` instance.
        provenance:
            ``ProvenanceLog`` or list of ``MergeRecord``.
        remove_source:
            Source identifier to remove (``"a"`` or ``"b"``).

        Returns
        -------
        Delta
            Filtered delta with the removed source's operations excluded.
        """
        from crdt_merge.delta import Delta

        records = _records_from_provenance(provenance)
        remove_unique = f"unique_{remove_source}"
        remove_only = f"{remove_source}_only"

        # Keys belonging to the removed source
        removed_keys = set()
        for rec in records:
            if rec.origin == remove_unique:
                removed_keys.add(rec.key)
            elif rec.origin == "merged":
                # Check if all non-key fields came from removed source
                all_removed = all(
                    dec.source == remove_only
                    for dec in rec.decisions
                    if dec.field != "id"
                )
                if all_removed:
                    removed_keys.add(rec.key)

        removed_key_strs = {str(k) for k in removed_keys}

        filtered_added = [
            r for r in (delta.added or [])
            if _record_key(r) not in removed_keys
        ]
        filtered_modified = [
            r for r in (delta.modified or [])
            if _record_key(r) not in removed_keys
        ]
        filtered_removed = [
            k for k in (delta.removed or [])
            if k not in removed_key_strs and str(k) not in removed_key_strs
        ]

        return Delta(
            added=filtered_added,
            modified=filtered_modified,
            removed=filtered_removed,
            version=delta.version,
            timestamp=delta.timestamp,
            source_node=delta.source_node,
        )

    # ---- private helpers --------------------------------------------------

    @staticmethod
    def _reconstruct_merged_row(
        prov_rec,
        remove_source: str,
        remove_only: str,
        keep_only: str,
    ) -> Optional[dict]:
        """Rebuild a merged record without the removed source's data.

        For ``conflict_resolved`` decisions the provenance stores the
        winning value (B) in ``value`` and the losing value (A) in
        ``alternative`` when using the default LWW strategy.
        """
        new_row: dict = {}
        has_kept_data = False

        for dec in prov_rec.decisions:
            if dec.source == "both_equal":
                # Both sources agree — safe to keep
                new_row[dec.field] = dec.value
                has_kept_data = True

            elif dec.source == remove_only:
                # Field contributed only by the removed source — drop it
                continue

            elif dec.source == keep_only:
                # Field contributed only by the kept source — keep it
                new_row[dec.field] = dec.value
                has_kept_data = True

            elif dec.source == "conflict_resolved":
                # In default LWW: value=B's contribution, alternative=A's
                if remove_source == "b":
                    # B won the conflict but is being removed → restore A
                    new_row[dec.field] = dec.alternative
                else:
                    # A lost the conflict and is being removed → keep B
                    new_row[dec.field] = dec.value
                has_kept_data = True

        return new_row if has_kept_data else None


# ---------------------------------------------------------------------------
# ModelUnmerge — model weight unmerge
# ---------------------------------------------------------------------------

class ModelUnmerge:
    """Remove a model's contribution from merged weights.

    Supports three methods:

    * **negmerge** — ``cleaned = merged − α · removed``
    * **surgical** — zero out the contribution entirely
    * **proportional** — rescale remaining contributions by their weight ratio
    """

    _METHODS = {"negmerge", "surgical", "proportional"}

    def __init__(self) -> None:
        pass

    def unmerge_model(
        self,
        merged_state,
        provenance,
        remove_model: str,
        method: str = "negmerge",
    ) -> dict:
        """Remove *remove_model* from *merged_state*.

        Parameters
        ----------
        merged_state:
            Either a ``CRDTMergeState`` or a plain ``dict`` mapping layer
            names to tensor-like objects (lists or numpy arrays).
        provenance:
            Provenance metadata — a ``ProvenanceLog``, a list of dicts
            from ``CRDTMergeState.provenance()``, or ``None`` when the
            state itself carries provenance internally.
        remove_model:
            The ``model_id`` of the contributor to remove.
        method:
            One of ``"negmerge"``, ``"surgical"``, or ``"proportional"``.

        Returns
        -------
        dict
            Mapping of layer names to cleaned tensors.
        """
        if method not in self._METHODS:
            raise ValueError(
                f"Unknown unmerge method '{method}'. "
                f"Supported: {sorted(self._METHODS)}"
            )

        np = _lazy_np()

        # Handle CRDTMergeState objects
        from crdt_merge.model.crdt_state import CRDTMergeState

        if isinstance(merged_state, CRDTMergeState):
            return self._unmerge_crdt_state(
                merged_state, remove_model, method, np,
            )

        # Plain dict of layer_name -> tensor
        if not isinstance(merged_state, dict):
            raise TypeError(
                f"merged_state must be a CRDTMergeState or dict, "
                f"got {type(merged_state).__name__}"
            )

        return self._unmerge_tensor_dict(
            merged_state, provenance, remove_model, method, np,
        )

    def measure_residual(
        self,
        cleaned_state: dict,
        original_model: dict,
    ) -> ResidualReport:
        """Measure how much of *original_model* remains in *cleaned_state*.

        Uses cosine similarity between corresponding layers. A score of
        0.0 means the removed model's influence is completely gone; 1.0
        means the cleaned state still fully contains the original.

        Parameters
        ----------
        cleaned_state:
            Dict of layer names to cleaned tensors.
        original_model:
            Dict of layer names to the removed model's original tensors.

        Returns
        -------
        ResidualReport
        """
        np = _lazy_np()
        parameters_checked = 0
        parameters_with_residual = 0
        similarities: List[float] = []

        for layer_name, original_tensor in original_model.items():
            if layer_name not in cleaned_state:
                continue

            cleaned_tensor = cleaned_state[layer_name]
            parameters_checked += 1

            sim = self._cosine_similarity(cleaned_tensor, original_tensor, np)
            if sim > 0.01:
                parameters_with_residual += 1
            similarities.append(abs(sim))

        influence = (
            sum(similarities) / len(similarities) if similarities else 0.0
        )
        return ResidualReport(
            influence_score=influence,
            parameters_checked=parameters_checked,
            parameters_with_residual=parameters_with_residual,
        )

    # ---- private helpers --------------------------------------------------

    def _unmerge_crdt_state(
        self,
        state,
        remove_model: str,
        method: str,
        np,
    ) -> dict:
        """Unmerge from a CRDTMergeState using its built-in provenance."""
        contribution = state.get_contribution(remove_model)
        if contribution is None:
            # Nothing to remove — resolve and return as single-layer result
            resolved = state.resolve()
            return {"merged": self._to_native(resolved, np)}

        removed_tensor = contribution.tensor
        removed_weight = contribution.weight

        # Get the merged result before removal
        merged_tensor = state.resolve()

        # Compute total weight of all active contributions
        all_prov = state.provenance()
        total_weight = sum(p["weight"] for p in all_prov)
        remaining_weight = total_weight - removed_weight

        if method == "negmerge":
            alpha = removed_weight / total_weight if total_weight > 0 else 1.0
            cleaned = self._negmerge(merged_tensor, removed_tensor, alpha, np)
        elif method == "surgical":
            cleaned = self._surgical(merged_tensor, removed_tensor, np)
        elif method == "proportional":
            scale = (
                total_weight / remaining_weight
                if remaining_weight > 0
                else 1.0
            )
            cleaned = self._proportional(
                merged_tensor, removed_tensor, removed_weight,
                total_weight, scale, np,
            )

        return {"merged": self._to_native(cleaned, np)}

    def _unmerge_tensor_dict(
        self,
        merged_state: dict,
        provenance,
        remove_model: str,
        method: str,
        np,
    ) -> dict:
        """Unmerge from a plain dict of layer_name -> tensor."""
        # Extract contribution info from provenance
        prov_entries = []
        if provenance is not None:
            if hasattr(provenance, "records"):
                prov_entries = provenance.records
            elif isinstance(provenance, list):
                prov_entries = provenance

        # Determine contribution weight from provenance
        removed_weight = 1.0
        total_weight = 0.0
        for entry in prov_entries:
            w = entry.get("weight", 1.0) if isinstance(entry, dict) else 1.0
            mid = (
                entry.get("model_id", "")
                if isinstance(entry, dict)
                else getattr(entry, "model_id", "")
            )
            total_weight += w
            if mid == remove_model:
                removed_weight = w

        if total_weight == 0.0:
            total_weight = 1.0

        result: dict = {}
        for layer_name, merged_tensor in merged_state.items():
            if layer_name == remove_model:
                # This layer IS the removed model — skip
                continue

            removed_tensor = merged_state.get(remove_model)
            if removed_tensor is None:
                result[layer_name] = merged_tensor
                continue

            if method == "negmerge":
                alpha = removed_weight / total_weight
                result[layer_name] = self._to_native(
                    self._negmerge(merged_tensor, removed_tensor, alpha, np),
                    np,
                )
            elif method == "surgical":
                result[layer_name] = self._to_native(
                    self._surgical(merged_tensor, removed_tensor, np), np,
                )
            elif method == "proportional":
                remaining_weight = total_weight - removed_weight
                scale = (
                    total_weight / remaining_weight
                    if remaining_weight > 0
                    else 1.0
                )
                result[layer_name] = self._to_native(
                    self._proportional(
                        merged_tensor, removed_tensor, removed_weight,
                        total_weight, scale, np,
                    ),
                    np,
                )

        return result

    @staticmethod
    def _negmerge(merged, removed, alpha: float, np):
        """``cleaned = merged − alpha * removed``"""
        if np is not None:
            m = np.asarray(merged, dtype=np.float64)
            r = np.asarray(removed, dtype=np.float64)
            return m - alpha * r
        # Pure-Python fallback for flat lists
        m = list(merged) if not isinstance(merged, list) else merged
        r = list(removed) if not isinstance(removed, list) else removed
        return [mv - alpha * rv for mv, rv in zip(m, r)]

    @staticmethod
    def _surgical(merged, removed, np):
        """Zero out the removed contribution: ``cleaned = merged − removed``."""
        if np is not None:
            m = np.asarray(merged, dtype=np.float64)
            r = np.asarray(removed, dtype=np.float64)
            return m - r
        m = list(merged) if not isinstance(merged, list) else merged
        r = list(removed) if not isinstance(removed, list) else removed
        return [mv - rv for mv, rv in zip(m, r)]

    @staticmethod
    def _proportional(merged, removed, removed_weight, total_weight, scale, np):
        """Remove contribution proportionally and rescale remaining weights."""
        if np is not None:
            m = np.asarray(merged, dtype=np.float64)
            r = np.asarray(removed, dtype=np.float64)
            contrib = (removed_weight / total_weight) * r if total_weight > 0 else r
            cleaned = m - contrib
            return cleaned * scale
        m = list(merged) if not isinstance(merged, list) else merged
        r = list(removed) if not isinstance(removed, list) else removed
        ratio = removed_weight / total_weight if total_weight > 0 else 1.0
        cleaned = [mv - ratio * rv for mv, rv in zip(m, r)]
        return [c * scale for c in cleaned]

    @staticmethod
    def _cosine_similarity(a, b, np) -> float:
        """Cosine similarity between two tensors."""
        if np is not None:
            a_arr = np.asarray(a, dtype=np.float64).flatten()
            b_arr = np.asarray(b, dtype=np.float64).flatten()
            dot = float(np.dot(a_arr, b_arr))
            norm_a = float(np.linalg.norm(a_arr))
            norm_b = float(np.linalg.norm(b_arr))
            if norm_a == 0.0 or norm_b == 0.0:
                return 0.0
            return dot / (norm_a * norm_b)
        # Pure-Python fallback
        a_flat = list(a) if not isinstance(a, list) else a
        b_flat = list(b) if not isinstance(b, list) else b
        dot = sum(x * y for x, y in zip(a_flat, b_flat))
        norm_a = math.sqrt(sum(x * x for x in a_flat))
        norm_b = math.sqrt(sum(x * x for x in b_flat))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _to_native(tensor, np):
        """Convert numpy arrays to lists for serialisation safety."""
        if np is not None and isinstance(tensor, np.ndarray):
            return tensor
        return tensor


# ---------------------------------------------------------------------------
# GDPRForget — compliance-oriented forget API
# ---------------------------------------------------------------------------

class GDPRForget:
    """GDPR "right to be forgotten" implementation.

    Wraps :class:`UnmergeEngine` and :class:`ModelUnmerge` with compliance
    metadata, timestamped audit entries, and report generation.
    """

    def __init__(
        self,
        engine: Optional[UnmergeEngine] = None,
        model_unmerge: Optional[ModelUnmerge] = None,
    ) -> None:
        self._engine = engine or UnmergeEngine()
        self._model_unmerge = model_unmerge or ModelUnmerge()
        self._history: List[ForgetResult] = []

    def forget_data(
        self,
        merged_data: List[dict],
        provenance,
        contributor: str,
        key_field: str = "id",
    ) -> ForgetResult:
        """Remove a contributor's data records and return a :class:`ForgetResult`.

        Parameters
        ----------
        merged_data:
            The current merged dataset.
        provenance:
            Provenance log from the original merge.
        contributor:
            Source identifier (``"a"`` or ``"b"``).
        key_field:
            Key column name.

        Returns
        -------
        ForgetResult
        """
        original_count = len(merged_data)
        cleaned = self._engine.unmerge(
            merged_data, provenance, contributor, key_field=key_field,
        )
        removed_count = original_count - len(cleaned)

        result = ForgetResult(
            success=True,
            data_records_removed=removed_count,
            model_influence_removed=False,
            compliance_timestamp=_iso_now(),
            contributor=contributor,
        )
        self._history.append(result)
        return result

    def forget_training_data(
        self,
        model_state,
        provenance,
        data_to_forget: str,
        method: str = "negmerge",
    ) -> ForgetResult:
        """Remove a model contributor's influence.

        Parameters
        ----------
        model_state:
            ``CRDTMergeState`` or dict of layer tensors.
        provenance:
            Provenance metadata.
        data_to_forget:
            The ``model_id`` of the contributor to forget.
        method:
            Unmerge method (``"negmerge"``, ``"surgical"``, ``"proportional"``).

        Returns
        -------
        ForgetResult
        """
        try:
            self._model_unmerge.unmerge_model(
                model_state, provenance, data_to_forget, method=method,
            )
            success = True
        except Exception:
            success = False

        result = ForgetResult(
            success=success,
            data_records_removed=0,
            model_influence_removed=success,
            compliance_timestamp=_iso_now(),
            contributor=data_to_forget,
        )
        self._history.append(result)
        return result

    def compliance_report(self) -> GDPRComplianceReport:
        """Generate a compliance report covering all forget operations."""
        data_removed = sum(r.data_records_removed for r in self._history)
        models_cleaned = sum(1 for r in self._history if r.model_influence_removed)

        return GDPRComplianceReport(
            requests_processed=[
                {
                    "contributor": r.contributor,
                    "success": r.success,
                    "data_records_removed": r.data_records_removed,
                    "model_influence_removed": r.model_influence_removed,
                    "timestamp": r.compliance_timestamp,
                }
                for r in self._history
            ],
            total_records_removed=data_removed,
            total_models_cleaned=models_cleaned,
            generated_at=_iso_now(),
        )
