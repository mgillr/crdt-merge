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

"""Factory functions for E4 tests.

Extracted from conftest to avoid import shadowing when tests run from
the crdt-merge root (where the root conftest is found first).
"""

import hashlib

from crdt_merge.e4.typed_trust import (
    TRUST_DIMENSIONS,
    TypedTrustScore,
)
from crdt_merge.e4.proof_evidence import (
    pack_attestation_pair,
    pack_clock_pair,
    pack_delta_proof,
    pack_state_pair,
)
from crdt_merge.e4.pco import (
    AggregateProofCarryingOperation,
    SubtreeRef,
)
from crdt_merge.e4.projection_delta import (
    FrozenDict,
    ProjectionDelta,
)
from crdt_merge.e4.trust_bound_merkle import MerkleNode


def make_pco(
    originator_id="peer-alice",
    signing_fn=None,
    merkle_root="",
    clock_snapshot=b"",
    trust_vector_hash="",
    delta_bounds=(),
):
    """Build a minimal valid AggregateProofCarryingOperation."""
    if signing_fn is None:
        signing_fn = lambda h: b"\x00" * 64
    return AggregateProofCarryingOperation.build(
        originator_id=originator_id,
        signing_fn=signing_fn,
        merkle_root=merkle_root,
        clock_snapshot=clock_snapshot,
        trust_vector_hash=trust_vector_hash,
        delta_bounds=delta_bounds,
    )


def make_delta(
    source_id="peer-alice",
    insertions=None,
    updates=None,
    deletions=None,
    subtrees=None,
    pco=None,
    encoding="raw",
):
    """Build a minimal valid ProjectionDelta."""
    if pco is None:
        pco = make_pco(originator_id=source_id)
    return ProjectionDelta(
        source_id=source_id,
        source_version=None,
        target_version=None,
        changed_subtrees=tuple(subtrees or []),
        insertions=FrozenDict(insertions or {}),
        updates=FrozenDict(updates or {}),
        deletions=frozenset(deletions or []),
        pco=pco,
        encoding=encoding,
        compression_ratio=1.0,
    )


def make_attestation_blob(signer, sequence, content, signature=None):
    """Build a minimal attestation blob for equivocation proofs."""
    if signature is None:
        signature = b"\x00" * 64
    text = f"{signer}\x00{sequence}\x00{content}\x00".encode("utf-8")
    return text + signature


def make_equivocation_proof(signer="peer-eve", sequence=1):
    """Create a valid equivocation proof (two conflicting ops)."""
    op_a = make_attestation_blob(signer, sequence, "content_A")
    op_b = make_attestation_blob(signer, sequence, "content_B")
    return pack_attestation_pair(op_a, op_b)


def make_clock_regression_proof(peer="peer-eve"):
    """Create a valid clock regression proof (after < before)."""
    before = f"{peer}=5".encode("utf-8")
    after = f"{peer}=3".encode("utf-8")
    return pack_clock_pair(before, after)


def make_invalid_delta_proof(target="eve"):
    """Create a valid invalid-delta proof (hash mismatch)."""
    delta_bytes = f"some bogus delta content from {target} node".encode("utf-8")
    wrong_hash = b"\x00" * 32
    return pack_delta_proof(wrong_hash, delta_bytes)


def make_state_pair_proof(target="eve"):
    """Create a valid trust-manipulation proof (two different states)."""
    state_a = f"state_version_1_of_{target}_trust_vector_alpha".encode("utf-8")
    state_b = f"state_version_2_of_{target}_trust_vector_beta".encode("utf-8")
    return pack_state_pair(state_a, state_b)


def make_merkle_node(path=(0,), hash_val="abc", is_leaf=True, children=None, data=None, originator=None):
    return MerkleNode(
        path=path,
        hash=hash_val,
        is_leaf=is_leaf,
        children=children or [],
        data=data,
        originator=originator,
    )
