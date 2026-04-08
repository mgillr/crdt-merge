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

"""Shared pytest fixtures for the E4 test suite.

Provides sample peers, trust vectors, delta payloads, mock Merkle trees,
and helper factories used across all test modules.
"""

import hashlib
import struct

import pytest


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
from crdt_merge.e4.delta_trust_lattice import (
    DeltaTrustLattice,
    TrustCircuitBreaker,
    CircuitBreakerTripped,
)
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle, MerkleNode
from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.adaptive_verification import (
    AdaptiveVerificationController,
    VerificationOutcome,
    VerificationResult,
)
from crdt_merge.e4.compatibility import (
    CompatibilityController,
    CompatibilityMode,
    PeerCapability,
    CompatHandshake,
)
from crdt_merge.e4.trust_weighted_strategy import (
    ConflictEntry,
    ConflictType,
    ResolutionResult,
    TrustGatedAcceptanceFilter,
    TrustWeightedAveragingResolver,
    TrustWeightedLWWResolver,
    TrustWeightedStrategySelector,
)
from crdt_merge.e4.integration.config import E4Config, get_config, set_config, reset_config
from crdt_merge.e4.integration.gossip_bridge import TrustGossipEngine, TrustGossipPayload
from crdt_merge.e4.integration.stream_bridge import TrustStreamMerge, StreamChunk, ChunkResult
from crdt_merge.e4.integration.agent_bridge import TrustAgentState, TrustAnnotatedEntry

from e4_factories import (
    make_pco, make_delta, make_attestation_blob,
    make_equivocation_proof, make_clock_regression_proof,
    make_invalid_delta_proof, make_state_pair_proof, make_merkle_node,
)



# ---------------------------------------------------------------------------
# Sample peer IDs
# ---------------------------------------------------------------------------

PEER_IDS = ["peer-alice", "peer-bob", "peer-carol", "peer-dave", "peer-eve"]


@pytest.fixture
def peer_ids():
    """Five sample peer identifiers."""
    return list(PEER_IDS)


@pytest.fixture
def peer_alice():
    return "peer-alice"


@pytest.fixture
def peer_bob():
    return "peer-bob"


# ---------------------------------------------------------------------------
# Trust vectors
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_trust():
    """A brand-new probationary trust score (no evidence)."""
    return TypedTrustScore.probationary()


@pytest.fixture
def full_trust_score():
    """A trust score with zero evidence (full trust)."""
    return TypedTrustScore.full_trust()


@pytest.fixture
def low_trust_score():
    """A trust score driven below LOW_TRUST_THRESHOLD."""
    ts = TypedTrustScore()
    evidence = {}
    for dim in TRUST_DIMENSIONS:
        evidence[dim] = {"observer-1": 0.7}
    return TypedTrustScore(_evidence=evidence)


@pytest.fixture
def quarantined_trust_score():
    """A trust score below QUARANTINE_THRESHOLD."""
    evidence = {}
    for dim in TRUST_DIMENSIONS:
        evidence[dim] = {"observer-1": 0.95}
    return TypedTrustScore(_evidence=evidence)


# ---------------------------------------------------------------------------
# SubtreeRef helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_subtree_ref():
    """A single sample SubtreeRef."""
    return SubtreeRef(path=(0,), depth=1, old_hash="aaa", new_hash="bbb")


@pytest.fixture
def sample_subtree_refs():
    """A list of two SubtreeRefs."""
    return [
        SubtreeRef(path=(0,), depth=1, old_hash="aaa", new_hash="bbb"),
        SubtreeRef(path=(1,), depth=1, old_hash="ccc", new_hash="ddd"),
    ]


# ---------------------------------------------------------------------------
# Dummy signing function
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_signing_fn():
    """Signing function that returns 64 zero bytes (passes stub verifier)."""
    return lambda h: b"\x00" * 64


# ---------------------------------------------------------------------------
# PCO factory
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_pco():
    return make_pco()


# ---------------------------------------------------------------------------
# ProjectionDelta factory
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_delta():
    """A ProjectionDelta with zero changes."""
    return make_delta()


@pytest.fixture
def sample_delta():
    """A ProjectionDelta with one insertion and one update."""
    return make_delta(
        insertions={"key1": b"value1"},
        updates={"key2": (hashlib.sha256(b"old").hexdigest(), b"new_value")},
        deletions=["key3"],
        subtrees=[SubtreeRef(path=(0,), depth=1, old_hash="aaa", new_hash="bbb")],
    )


# ---------------------------------------------------------------------------
# TrustEvidence helpers
# ---------------------------------------------------------------------------






@pytest.fixture
def equivocation_evidence():
    """A valid equivocation TrustEvidence."""
    return TrustEvidence.create(
        observer="peer-alice",
        target="peer-eve",
        evidence_type="equivocation",
        dimension="integrity",
        amount=0.1,
        proof=make_equivocation_proof(),
    )


# ---------------------------------------------------------------------------
# DeltaTrustLattice factory
# ---------------------------------------------------------------------------

@pytest.fixture
def trust_lattice():
    """A DeltaTrustLattice with two initial peers."""
    return DeltaTrustLattice(
        "peer-alice",
        initial_peers={"peer-bob", "peer-carol"},
    )


# ---------------------------------------------------------------------------
# TrustBoundMerkle factory
# ---------------------------------------------------------------------------

@pytest.fixture
def merkle_tree():
    """A TrustBoundMerkle with default branching factor."""
    return TrustBoundMerkle(branching_factor=256)


# ---------------------------------------------------------------------------
# CausalTrustClock factory
# ---------------------------------------------------------------------------

@pytest.fixture
def trust_clock():
    """A CausalTrustClock for peer-alice."""
    return CausalTrustClock("peer-alice")


# ---------------------------------------------------------------------------
# CircuitBreaker factory
# ---------------------------------------------------------------------------

@pytest.fixture
def circuit_breaker():
    return TrustCircuitBreaker(
        window_size=20,
        sigma_threshold=2.0,
        cooldown_seconds=0.1,
        min_samples=5,
    )


# ---------------------------------------------------------------------------
# MerkleNode factory
# ---------------------------------------------------------------------------

def make_merkle_node(path=(0,), hash_val="abc", is_leaf=True, children=None, data=None, originator=None):
    return MerkleNode(
        path=path,
        hash=hash_val,
        is_leaf=is_leaf,
        children=children or [],
        data=data,
        originator=originator,
    )
