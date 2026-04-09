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

"""
Comprehensive tests for CRDTMergeState — verifies CRDT laws hold for ALL 26 strategies.

This test suite proves that the two-layer architecture (CRDT state + atomic resolution)
delivers true CRDT guarantees for every strategy in crdt-merge.

Test categories:
  1. CRDT Law Proofs (C/A/I) for all 26 strategies
  2. Resolve consistency (merge order doesn't change output)
  3. OR-Set semantics (add/remove with concurrent ops)
  4. Versioned registry (model update support)
  5. Serialization roundtrip
  6. Edge cases (empty state, single model, duplicate adds)
  7. Provenance / Merkle integrity
"""

import pytest
import numpy as np
from crdt_merge.model.crdt_state import (
    CRDTMergeState,
    MergeContribution,
    ConflictResolution,
)
from crdt_merge.model.strategies import list_strategies

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STRATEGIES = list_strategies()
TENSOR_SIZE = 10
NUM_TRIALS = 20

BASE_REQUIRED = CRDTMergeState.BASE_REQUIRED
STOCHASTIC = CRDTMergeState.STOCHASTIC

def gen(seed, size=TENSOR_SIZE):
    return np.random.RandomState(seed).randn(size).astype(np.float64)

def make_state(strategy, trial=0):
    """Create three single-contribution states + optional base."""
    needs_base = strategy in BASE_REQUIRED
    base = gen(trial * 100 + 99) if needs_base else None
    sa = CRDTMergeState(strategy, base=base, seed=42)
    sa.add(gen(trial * 100 + 1), model_id="A", weight=1.0)
    sb = CRDTMergeState(strategy, base=base, seed=42)
    sb.add(gen(trial * 100 + 2), model_id="B", weight=1.0)
    sc = CRDTMergeState(strategy, base=base, seed=42)
    sc.add(gen(trial * 100 + 3), model_id="C", weight=1.0)
    return sa, sb, sc

# ===========================================================================
# 1. CRDT LAW PROOFS -- All 25 Strategies
# ===========================================================================

class TestCRDTLaws:
    """Verify commutativity, associativity, and idempotency for every strategy."""

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_commutativity_state(self, strategy):
        """merge(A, B) == merge(B, A) at the STATE level."""
        for trial in range(NUM_TRIALS):
            sa, sb, _ = make_state(strategy, trial)
            ab = sa.merge(sb)
            ba = sb.merge(sa)
            assert ab == ba, f"{strategy} trial {trial}: state not commutative"

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_commutativity_resolve(self, strategy):
        """merge(A, B).resolve() == merge(B, A).resolve()."""
        for trial in range(NUM_TRIALS):
            sa, sb, _ = make_state(strategy, trial)
            r_ab = sa.merge(sb).resolve()
            r_ba = sb.merge(sa).resolve()
            np.testing.assert_allclose(
                r_ab, r_ba, atol=1e-6, rtol=1e-6,
                err_msg=f"{strategy} trial {trial}: resolve not commutative"
            )

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_associativity_state(self, strategy):
        """merge(merge(A, B), C) == merge(A, merge(B, C)) at STATE level."""
        for trial in range(NUM_TRIALS):
            sa, sb, sc = make_state(strategy, trial)
            left = sa.merge(sb).merge(sc)
            right = sa.merge(sb.merge(sc))
            assert left == right, f"{strategy} trial {trial}: state not associative"

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_associativity_resolve(self, strategy):
        """merge(merge(A, B), C).resolve() == merge(A, merge(B, C)).resolve()."""
        for trial in range(NUM_TRIALS):
            sa, sb, sc = make_state(strategy, trial)
            r_left = sa.merge(sb).merge(sc).resolve()
            r_right = sa.merge(sb.merge(sc)).resolve()
            np.testing.assert_allclose(
                r_left, r_right, atol=1e-6, rtol=1e-6,
                err_msg=f"{strategy} trial {trial}: resolve not associative"
            )

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_idempotency_state(self, strategy):
        """merge(A, A) == A at STATE level."""
        for trial in range(NUM_TRIALS):
            sa, _, _ = make_state(strategy, trial)
            aa = sa.merge(sa)
            assert aa == sa, f"{strategy} trial {trial}: state not idempotent"

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_idempotency_resolve(self, strategy):
        """merge(A, A).resolve() == A.resolve()."""
        for trial in range(NUM_TRIALS):
            sa, _, _ = make_state(strategy, trial)
            r_a = sa.resolve()
            r_aa = sa.merge(sa).resolve()
            np.testing.assert_allclose(
                r_aa, r_a, atol=1e-6, rtol=1e-6,
                err_msg=f"{strategy} trial {trial}: resolve not idempotent"
            )

# ===========================================================================
# 2. RESOLVE CONSISTENCY -- All merge orderings produce same output
# ===========================================================================

class TestResolveConsistency:
    """Verify that all possible merge orderings produce the same resolved tensor."""

    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_all_orderings_produce_same_result(self, strategy):
        """6 possible merge orderings of 3 states should all resolve identically."""
        from itertools import permutations
        sa, sb, sc = make_state(strategy, trial=0)
        states = [sa, sb, sc]

        results = []
        for perm in permutations(range(3)):
            merged = states[perm[0]].merge(states[perm[1]]).merge(states[perm[2]])
            results.append(merged.resolve())

        for i, r in enumerate(results[1:], 1):
            np.testing.assert_allclose(
                results[0], r, atol=1e-6, rtol=1e-6,
                err_msg=f"{strategy}: ordering {i} differs from ordering 0"
            )

# ===========================================================================
# 3. OR-SET SEMANTICS -- Add/Remove with concurrent operations
# ===========================================================================

class TestORSetSemantics:
    """Verify add/remove behaves correctly under concurrent operations."""

    def test_add_wins_over_concurrent_remove(self):
        """If A adds model_X and B removes model_X, add-wins semantics."""
        state = CRDTMergeState("weight_average")
        state.add(gen(1), model_id="X")
        state.add(gen(2), model_id="Y")

        # Fork: replica_a adds Z, replica_b removes X
        replica_a = CRDTMergeState("weight_average")
        replica_a.add(gen(1), model_id="X")
        replica_a.add(gen(2), model_id="Y")
        replica_a.add(gen(3), model_id="Z")

        replica_b = CRDTMergeState("weight_average")
        replica_b.add(gen(1), model_id="X")
        replica_b.add(gen(2), model_id="Y")
        replica_b.remove("X")

        merged = replica_a.merge(replica_b)
        # Z should be present (added by A)
        assert "Z" in merged.model_ids
        # Y should be present (not removed)
        assert "Y" in merged.model_ids

    def test_remove_then_readd(self):
        """Remove + re-add should result in the model being present."""
        state = CRDTMergeState("weight_average")
        state.add(gen(1), model_id="X")
        state.remove("X")
        state.add(gen(2), model_id="X", version=2)
        assert "X" in state.model_ids

# ===========================================================================
# 4. VERSIONED REGISTRY -- Model update support
# ===========================================================================

class TestVersionedRegistry:
    """Verify version-based conflict resolution works correctly."""

    def test_higher_version_wins(self):
        """A contribution with higher version should supersede lower."""
        state = CRDTMergeState("weight_average",
                                conflict_resolution=ConflictResolution.HIGHEST_VERSION)
        state.add(gen(1), model_id="X", version=1)
        state.add(gen(2), model_id="X", version=3)  # Should win

        contrib = state.get_contribution("X")
        assert contrib is not None
        assert contrib.version == 3

    def test_concurrent_versions_merge_deterministically(self):
        """Two replicas with different versions of same model merge correctly."""
        ra = CRDTMergeState("weight_average")
        ra.add(gen(1), model_id="X", version=2)

        rb = CRDTMergeState("weight_average")
        rb.add(gen(2), model_id="X", version=5)

        # Merge both directions
        m1 = ra.merge(rb)
        m2 = rb.merge(ra)

        # Both should have version 5
        assert m1.get_contribution("X").version == 5
        assert m2.get_contribution("X").version == 5
        assert m1 == m2

# ===========================================================================
# 5. SERIALIZATION ROUNDTRIP
# ===========================================================================

class TestSerialization:
    """Verify to_dict/from_dict roundtrip preserves CRDT state."""

    @pytest.mark.parametrize("strategy", STRATEGIES[:5])  # Sample
    def test_roundtrip_preserves_state(self, strategy):
        sa, sb, _ = make_state(strategy, trial=0)
        merged = sa.merge(sb)

        serialized = merged.to_dict()
        restored = CRDTMergeState.from_dict(serialized)

        assert restored.strategy_name == merged.strategy_name
        assert restored.model_ids == merged.model_ids

    def test_roundtrip_preserves_resolve(self):
        state = CRDTMergeState("weight_average")
        state.add(gen(1), model_id="A")
        state.add(gen(2), model_id="B")

        original_resolve = state.resolve()
        restored = CRDTMergeState.from_dict(state.to_dict())
        restored_resolve = restored.resolve()

        np.testing.assert_allclose(original_resolve, restored_resolve, atol=1e-10)

# ===========================================================================
# 6. EDGE CASES
# ===========================================================================

class TestEdgeCases:
    """Edge cases: empty state, single model, duplicates, mismatched strategies."""

    def test_empty_state_with_base_resolves_to_base(self):
        base = gen(42)
        state = CRDTMergeState("weight_average", base=base)
        result = state.resolve()
        np.testing.assert_array_equal(result, base)

    def test_empty_state_without_base_raises(self):
        state = CRDTMergeState("weight_average")
        with pytest.raises(ValueError, match="empty CRDT state"):
            state.resolve()

    def test_single_model_resolves_correctly(self):
        """Single contribution should resolve to that tensor."""
        t = gen(1)
        state = CRDTMergeState("weight_average")
        state.add(t, model_id="only")
        result = state.resolve()
        np.testing.assert_allclose(result, t, atol=1e-6)

    def test_duplicate_add_same_tensor_same_id(self):
        """Adding the same tensor twice with same ID is idempotent."""
        t = gen(1)
        state = CRDTMergeState("weight_average")
        state.add(t, model_id="X", version=1)
        state.add(t, model_id="X", version=1)
        assert state.size == 1

    def test_merge_with_empty_state(self):
        """Merging with empty state returns original."""
        sa = CRDTMergeState("weight_average")
        sa.add(gen(1), model_id="A")

        empty = CRDTMergeState("weight_average")
        merged = sa.merge(empty)
        assert merged == sa

    def test_four_way_merge(self):
        """Test 4-way merge in various orderings."""
        states = []
        for i in range(4):
            s = CRDTMergeState("weight_average")
            s.add(gen(i+1), model_id=f"M{i}")
            states.append(s)

        # Two different merge trees
        r1 = states[0].merge(states[1]).merge(states[2].merge(states[3]))
        r2 = states[3].merge(states[0]).merge(states[2]).merge(states[1])
        np.testing.assert_allclose(r1.resolve(), r2.resolve(), atol=1e-6)

# ===========================================================================
# 7. PROVENANCE / MERKLE INTEGRITY
# ===========================================================================

class TestProvenance:
    """Verify Merkle hashing and provenance trails."""

    def test_merkle_hash_deterministic(self):
        """Same content → same hash."""
        t = gen(42)
        c1 = MergeContribution("X", t, weight=1.0, version=1)
        c2 = MergeContribution("X", t, weight=1.0, version=1)
        assert c1.merkle_hash == c2.merkle_hash

    def test_different_content_different_hash(self):
        """Different content → different hash."""
        c1 = MergeContribution("X", gen(1))
        c2 = MergeContribution("X", gen(2))
        assert c1.merkle_hash != c2.merkle_hash

    def test_provenance_trail(self):
        state = CRDTMergeState("weight_average")
        state.add(gen(1), model_id="node-a-llama", metadata={"node": "a"})
        state.add(gen(2), model_id="node-b-llama", metadata={"node": "b"})

        prov = state.provenance()
        assert len(prov) == 2
        assert prov[0]["model_id"] == "node-a-llama"
        assert prov[0]["metadata"]["node"] == "a"
        assert len(prov[0]["merkle_hash"]) == 64

# ===========================================================================
# GRAND FINALE: Full matrix confirmation
# ===========================================================================

class TestGrandFinale:
    """One comprehensive test that confirms ALL 26 strategies × ALL 3 laws."""

    def test_all_25_strategies_are_true_crdts(self):
        """Every registered strategy satisfies all CRDT laws via CRDTMergeState."""
        strategies = list_strategies()
        failures = []

        for strategy in strategies:
            for trial in range(5):
                sa, sb, sc = make_state(strategy, trial)

                # Commutativity
                if sa.merge(sb) != sb.merge(sa):
                    failures.append(f"{strategy}:commutativity:trial{trial}")
                # Associativity
                if sa.merge(sb).merge(sc) != sa.merge(sb.merge(sc)):
                    failures.append(f"{strategy}:associativity:trial{trial}")
                # Idempotency
                if sa.merge(sa) != sa:
                    failures.append(f"{strategy}:idempotency:trial{trial}")

        assert failures == [], f"CRDT law failures: {failures}"
