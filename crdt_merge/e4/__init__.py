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

"""E4 Recursive Trust-Delta Architecture.

Core modules for the E4 extension to the crdt-merge CRDT framework.
Provides projection delta encoding, typed trust scores, proof-carrying
evidence, and aggregate proof-carrying operations.

Public API
----------
TypedTrustScore        -- multi-dimensional trust with GCounter evidence
TrustHomeostasis       -- conserved-budget normalization
TrustEvidence          -- proof-carrying trust evidence
SubtreeRef             -- Merkle subtree reference
AggregateProofCarryingOperation -- 128-byte aggregate PCO
ProjectionDelta        -- sparse delta encoding
ProjectionDeltaManager -- delta lifecycle management
FrozenDict             -- immutable dict for frozen dataclasses
"""

from crdt_merge.e4.typed_trust import (
    PROBATION_TRUST,
    QUARANTINE_THRESHOLD,
    LOW_TRUST_THRESHOLD,
    PARTIAL_THRESHOLD,
    TRUST_DIMENSIONS,
    TrustHomeostasis,
    TypedTrustScore,
)
from crdt_merge.e4.proof_evidence import (
    EVIDENCE_TYPES,
    TrustEvidence,
    pack_attestation_pair,
    pack_clock_pair,
    pack_delta_proof,
    pack_merkle_path,
    pack_state_pair,
)
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    SubtreeRef,
)
from crdt_merge.e4.projection_delta import (
    FrozenDict,
    ProjectionDelta,
    ProjectionDeltaManager,
)
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry,
    ConflictType,
    ResolutionResult,
    TrustGatedAcceptanceFilter,
    TrustWeightedAveragingResolver,
    TrustWeightedLWWResolver,
    TrustWeightedStrategy,
    TrustWeightedStrategySelector,
)

__all__ = [
    "TypedTrustScore",
    "TrustHomeostasis",
    "TRUST_DIMENSIONS",
    "PROBATION_TRUST",
    "QUARANTINE_THRESHOLD",
    "LOW_TRUST_THRESHOLD",
    "PARTIAL_THRESHOLD",
    "TrustEvidence",
    "EVIDENCE_TYPES",
    "pack_attestation_pair",
    "pack_clock_pair",
    "pack_delta_proof",
    "pack_merkle_path",
    "pack_state_pair",
    "AggregateProofCarryingOperation",
    "SubtreeRef",
    "ProjectionDelta",
    "ProjectionDeltaManager",
    "FrozenDict",
    "ConflictEntry",
    "ConflictType",
    "ResolutionResult",
    "TrustGatedAcceptanceFilter",
    "TrustWeightedAveragingResolver",
    "TrustWeightedLWWResolver",
    "TrustWeightedStrategy",
    "TrustWeightedStrategySelector",
]


# Hardening subsystem (v0.9.5.1) — addresses all peer review concerns
# Import makes resilience available as crdt_merge.e4.resilience.*
from crdt_merge.e4 import resilience as resilience  # noqa: F401
