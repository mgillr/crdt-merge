# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Patent: UK Application No. 2607132.4, GB2608127.3
#
# Change Date: 2028-04-08
# Change License: Apache License, Version 2.0

"""Schema heterogeneity adapter for cross-domain delta merging.

Addresses Brennan §C19 and Tanaka §C21: E4 assumes peers share a common
data schema (parameter positions in the Merkle tree are meaningful).
Knowledge graphs have heterogeneous schemas, and NAS workers evaluate
on different hardware/datasets producing incomparable results.

Solution — schema-neutral delta encoding:

  Layer 1: Schema descriptor.
    Each delta carries a compact schema descriptor that maps logical
    field names to Merkle tree positions.  Descriptors are versioned
    and registered in a schema registry (itself a CRDT — OR-Set of
    schema versions).

  Layer 2: Schema alignment.
    When merging deltas from different schemas, the adapter computes
    a field-level alignment (matching logical names, resolving type
    coercions) and produces a unified merge schema.  Unaligned fields
    are carried as opaque extensions.

  Layer 3: Result normalisation.
    For NAS/AutoML, results from different hardware/datasets are
    normalised to a reference configuration before merging.  The
    normalisation factors are stored as CRDT state so all peers
    converge on the same normalisation.

Technical effect (UK patent): enables CRDT-based merging across
heterogeneous data schemas through a schema-neutral delta encoding
with convergent schema alignment.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# -- Schema descriptor -----------------------------------------------------

@dataclass
class FieldDescriptor:
    """Description of a single field in a schema."""
    name: str
    dtype: str         # "float64", "int32", "string", "bytes", etc.
    position: int      # Merkle tree position
    nullable: bool = False
    default: Any = None

    def compatible_with(self, other: FieldDescriptor) -> bool:
        """Check type compatibility for merge."""
        if self.dtype == other.dtype:
            return True
        compatible_pairs = {
            ("float32", "float64"), ("float64", "float32"),
            ("int32", "int64"), ("int64", "int32"),
            ("float32", "int32"), ("int32", "float32"),
            ("float64", "int64"), ("int64", "float64"),
        }
        return (self.dtype, other.dtype) in compatible_pairs

    def wider_type(self, other: FieldDescriptor) -> str:
        """Return the wider type for merge."""
        width = {"int32": 1, "float32": 2, "int64": 3, "float64": 4}
        return self.dtype if width.get(self.dtype, 0) >= width.get(other.dtype, 0) else other.dtype


@dataclass
class SchemaDescriptor:
    """Versioned schema for delta encoding."""
    schema_id: str
    version: int
    fields: List[FieldDescriptor] = field(default_factory=list)

    def field_names(self) -> Set[str]:
        return {f.name for f in self.fields}

    def get_field(self, name: str) -> Optional[FieldDescriptor]:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def content_hash(self) -> str:
        h = hashlib.sha256()
        h.update(f"{self.schema_id}:{self.version}".encode())
        for f in self.fields:
            h.update(f"{f.name}:{f.dtype}:{f.position}".encode())
        return h.hexdigest()[:16]


# -- Schema alignment ------------------------------------------------------

@dataclass(frozen=True)
class FieldAlignment:
    """Alignment between two fields from different schemas."""
    local_field: str
    remote_field: str
    merge_type: str
    position: int


@dataclass
class SchemaAlignment:
    """Computed alignment between two schemas."""
    local_schema: str
    remote_schema: str
    aligned_fields: List[FieldAlignment] = field(default_factory=list)
    local_only: List[str] = field(default_factory=list)
    remote_only: List[str] = field(default_factory=list)

    @property
    def alignment_ratio(self) -> float:
        total = len(self.aligned_fields) + len(self.local_only) + len(self.remote_only)
        if total == 0:
            return 1.0
        return len(self.aligned_fields) / total


class SchemaAligner:
    """Compute field-level alignment between heterogeneous schemas.

    Parameters
    ----------
    strict :
        If True, only align fields with identical names and compatible
        types.  If False, attempt fuzzy name matching.
    """

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict

    def align(
        self,
        local: SchemaDescriptor,
        remote: SchemaDescriptor,
    ) -> SchemaAlignment:
        """Compute alignment between two schemas."""
        aligned = []
        local_matched = set()
        remote_matched = set()

        for lf in local.fields:
            rf = remote.get_field(lf.name)
            if rf and lf.compatible_with(rf):
                aligned.append(FieldAlignment(
                    lf.name, rf.name,
                    lf.wider_type(rf),
                    lf.position,
                ))
                local_matched.add(lf.name)
                remote_matched.add(rf.name)

        if not self._strict:
            for lf in local.fields:
                if lf.name in local_matched:
                    continue
                for rf in remote.fields:
                    if rf.name in remote_matched:
                        continue
                    if self._fuzzy_match(lf.name, rf.name) and lf.compatible_with(rf):
                        aligned.append(FieldAlignment(
                            lf.name, rf.name,
                            lf.wider_type(rf),
                            lf.position,
                        ))
                        local_matched.add(lf.name)
                        remote_matched.add(rf.name)
                        break

        local_only = [f.name for f in local.fields if f.name not in local_matched]
        remote_only = [f.name for f in remote.fields if f.name not in remote_matched]

        return SchemaAlignment(
            local.schema_id, remote.schema_id,
            aligned, local_only, remote_only,
        )

    def _fuzzy_match(self, a: str, b: str) -> bool:
        """Simple fuzzy name matching (normalise underscores and case)."""
        na = a.lower().replace("_", "").replace("-", "")
        nb = b.lower().replace("_", "").replace("-", "")
        return na == nb


# -- Result normalisation (NAS/AutoML) ------------------------------------

@dataclass(frozen=True)
class NormalisationFactor:
    """Hardware/dataset normalisation factor for comparable results."""
    factor_id: str
    hardware_ref: str
    dataset_ref: str
    compute_multiplier: float
    accuracy_offset: float


class ResultNormaliser:
    """Normalise results from heterogeneous evaluation environments.

    Parameters
    ----------
    reference_hardware :
        Identifier for the reference hardware configuration.
    reference_dataset :
        Identifier for the reference evaluation dataset.
    """

    def __init__(
        self,
        reference_hardware: str = "a100",
        reference_dataset: str = "imagenet-val",
    ) -> None:
        self._ref_hw = reference_hardware
        self._ref_ds = reference_dataset
        self._factors: Dict[str, NormalisationFactor] = {}

    def register_factor(self, factor: NormalisationFactor) -> None:
        self._factors[factor.factor_id] = factor

    def normalise(
        self,
        metric: float,
        hardware: str,
        dataset: str,
    ) -> float:
        """Normalise a metric to the reference configuration."""
        key = f"{hardware}:{dataset}"
        factor = self._factors.get(key)
        if factor is None:
            return metric
        return (metric + factor.accuracy_offset) * factor.compute_multiplier

    def register_from_calibration(
        self,
        hardware: str,
        dataset: str,
        reference_score: float,
        observed_score: float,
    ) -> NormalisationFactor:
        """Compute normalisation factor from calibration run."""
        if observed_score == 0:
            multiplier = 1.0
        else:
            multiplier = reference_score / observed_score
        offset = reference_score - observed_score * multiplier
        factor = NormalisationFactor(
            factor_id=f"{hardware}:{dataset}",
            hardware_ref=hardware,
            dataset_ref=dataset,
            compute_multiplier=multiplier,
            accuracy_offset=offset,
        )
        self._factors[factor.factor_id] = factor
        return factor

    @property
    def factor_count(self) -> int:
        return len(self._factors)


# -- Schema registry (CRDT-compatible) ------------------------------------

class SchemaRegistry:
    """Registry of known schemas, maintained as an OR-Set.

    Schemas are identified by (schema_id, version) pairs.  The registry
    converges via union (add-wins) semantics — once a schema version is
    registered, it is never removed.
    """

    def __init__(self) -> None:
        self._schemas: Dict[str, SchemaDescriptor] = {}

    def register(self, schema: SchemaDescriptor) -> None:
        key = f"{schema.schema_id}:v{schema.version}"
        self._schemas[key] = schema

    def get(self, schema_id: str, version: int) -> Optional[SchemaDescriptor]:
        return self._schemas.get(f"{schema_id}:v{version}")

    def latest(self, schema_id: str) -> Optional[SchemaDescriptor]:
        candidates = [
            (v, s) for k, s in self._schemas.items()
            if (v := k.split(":v")) and v[0] == schema_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1].version)[1]

    def merge(self, remote: SchemaRegistry) -> None:
        """OR-Set merge: union of all schema versions."""
        for key, schema in remote._schemas.items():
            if key not in self._schemas:
                self._schemas[key] = schema

    @property
    def schema_count(self) -> int:
        return len(self._schemas)

    def all_schemas(self) -> List[SchemaDescriptor]:
        return list(self._schemas.values())
