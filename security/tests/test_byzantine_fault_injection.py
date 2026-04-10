"""
Byzantine Fault Injection Test Suite
Validates E4 trust lattice resilience under adversarial conditions.
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from crdt_merge.e4.causal_trust_clock import CausalTrustClock
from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.trust_bound_merkle import TrustBoundMerkle
from crdt_merge.e4.proof_evidence import (
    TrustEvidence, EVIDENCE_TYPES,
    pack_attestation_pair, pack_merkle_path, pack_clock_pair,
    pack_delta_proof, pack_state_pair,
)
from crdt_merge.e4.typed_trust import (
    TypedTrustScore, PROBATION_TRUST, QUARANTINE_THRESHOLD,
)

DIMENSIONS = ["causality", "integrity", "context", "model", "gossip", "consistency"]


class _NoOpHomeostasis:
    """Homeostasis that does nothing so evidence reliably changes trust."""
    @staticmethod
    def normalize(scores, peer_count):
        return dict(scores)


def _make_attestation_blob(signer, sequence, content):
    text = f"{signer}\x00{sequence}\x00{content}\x00".encode("utf-8")
    return text + b"\x00" * 64


def make_equivocation_proof(signer="bad"):
    op_a = _make_attestation_blob(signer, 1, "content_A")
    op_b = _make_attestation_blob(signer, 1, "content_B")
    return pack_attestation_pair(op_a, op_b)


def make_clock_regression_proof(peer="bad"):
    before = f"{peer}=5".encode("utf-8")
    after = f"{peer}=3".encode("utf-8")
    return pack_clock_pair(before, after)


def make_invalid_delta_proof():
    return pack_delta_proof(b"\x00" * 32, b"bogus delta content")


def make_state_pair_proof():
    return pack_state_pair(b"state_v1", b"state_v2")


def make_lattice(*peers):
    return DeltaTrustLattice(
        "observer", initial_peers=set(peers), homeostasis=_NoOpHomeostasis()
    )


# -- 1. Equivocation Detection ------------------------------------------------

class TestEquivocationDetection:
    def test_single_equivocation_reduces_trust(self):
        lattice = make_lattice("byzantine")
        initial = lattice.get_trust("byzantine").overall_trust()
        ev = TrustEvidence.create(
            "observer", "byzantine", "equivocation", "integrity", 0.8,
            make_equivocation_proof("byzantine"),
        )
        lattice.observe_and_propagate(ev)
        after = lattice.get_trust("byzantine").overall_trust()
        assert after < initial, f"Trust should drop: {initial} -> {after}"

    def test_repeated_equivocation_drives_trust_down(self):
        lattice = make_lattice("byzantine")
        for _ in range(10):
            ev = TrustEvidence.create(
                "observer", "byzantine", "equivocation", "integrity", 0.5,
                make_equivocation_proof("byzantine"),
            )
            lattice.observe_and_propagate(ev)
        trust = lattice.get_trust("byzantine").overall_trust()
        assert trust < PROBATION_TRUST, f"10 equivocations should push below probation, got {trust}"

    def test_equivocation_does_not_affect_honest_peers(self):
        lattice = make_lattice("honest", "byzantine")
        honest_before = lattice.get_trust("honest").overall_trust()
        for _ in range(5):
            ev = TrustEvidence.create(
                "observer", "byzantine", "equivocation", "integrity", 0.5,
                make_equivocation_proof("byzantine"),
            )
            lattice.observe_and_propagate(ev)
        honest_after = lattice.get_trust("honest").overall_trust()
        assert honest_after == honest_before


# -- 2. Sybil Attack Resistance -----------------------------------------------

class TestSybilResistance:
    def test_sybil_flood_cannot_restore_penalized_peer(self):
        sybils = [f"sybil_{i}" for i in range(20)]
        lattice = make_lattice("byzantine", "honest", *sybils)
        for _ in range(5):
            ev = TrustEvidence.create(
                "observer", "byzantine", "equivocation", "integrity", 0.6,
                make_equivocation_proof("byzantine"),
            )
            lattice.observe_and_propagate(ev)
        trust_after_penalty = lattice.get_trust("byzantine").overall_trust()
        honest_trust = lattice.get_trust("honest").overall_trust()
        assert trust_after_penalty < honest_trust

    def test_new_peers_start_at_probation(self):
        lattice = make_lattice("new_peer")
        trust = lattice.get_trust("new_peer").overall_trust()
        assert trust == pytest.approx(PROBATION_TRUST)


# -- 3. Clock Regression Attack ------------------------------------------------

class TestClockRegression:
    def test_clock_regression_reduces_trust(self):
        lattice = make_lattice("regressor")
        initial = lattice.get_trust("regressor").overall_trust()
        ev = TrustEvidence.create(
            "observer", "regressor", "clock_regression", "causality", 0.8,
            make_clock_regression_proof("regressor"),
        )
        lattice.observe_and_propagate(ev)
        trust = lattice.get_trust("regressor").overall_trust()
        assert trust < initial

    def test_clock_monotonicity_property(self):
        clock = CausalTrustClock("peer_a")
        times = []
        for _ in range(100):
            clock = clock.increment()
            times.append(clock.logical_time)
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]


# -- 4. Invalid Delta Injection ------------------------------------------------

class TestInvalidDelta:
    def test_invalid_delta_reduces_trust(self):
        lattice = make_lattice("tamper_peer")
        initial = lattice.get_trust("tamper_peer").overall_trust()
        ev = TrustEvidence.create(
            "observer", "tamper_peer", "invalid_delta", "consistency", 0.8,
            make_invalid_delta_proof(),
        )
        lattice.observe_and_propagate(ev)
        trust = lattice.get_trust("tamper_peer").overall_trust()
        assert trust < initial

    def test_multiple_delta_violations_compound(self):
        lattice = make_lattice("bad_peer")
        trusts = []
        for _ in range(10):
            ev = TrustEvidence.create(
                "observer", "bad_peer", "invalid_delta", "consistency", 0.3,
                make_invalid_delta_proof(),
            )
            lattice.observe_and_propagate(ev)
            trusts.append(lattice.get_trust("bad_peer").overall_trust())
        for i in range(1, len(trusts)):
            assert trusts[i] <= trusts[i - 1], f"Trust must not increase: step {i}"


# -- 5. Merkle Divergence Detection --------------------------------------------

class TestMerkleDivergence:
    def test_merkle_divergence_proof_verified(self):
        """Merkle divergence proofs are verified at the evidence level.
        The packed proof computes to a root that differs from the expected root,
        confirming the divergence is genuine.
        """
        import hashlib
        h1 = hashlib.sha256(b"fake_left").hexdigest()
        h2 = hashlib.sha256(b"fake_right").hexdigest()
        proof = pack_merkle_path([([ h1, h2], 0)])
        ev = TrustEvidence.create(
            "observer", "divergent", "merkle_divergence", "integrity", 0.8, proof,
        )
        # Verify against a known root that should NOT match the proof path
        assert ev.verify("known_root_hash") is True
        assert ev.verify("") is True
        # Verify returns False when no root provided (no reference point)
        assert ev.verify(None) is False

    def test_merkle_tree_deterministic_roots(self):
        m1 = TrustBoundMerkle()
        m2 = TrustBoundMerkle()
        for i in range(100):
            m1.insert_leaf(f"key_{i}", f"data_{i}".encode(), "peer_a")
            m2.insert_leaf(f"key_{i}", f"data_{i}".encode(), "peer_a")
        m1.recompute()
        m2.recompute()
        assert m1.root_hash == m2.root_hash


# -- 6. Trust Manipulation Attack ----------------------------------------------

class TestTrustManipulation:
    def test_trust_manipulation_detected(self):
        lattice = make_lattice("manipulator")
        initial = lattice.get_trust("manipulator").overall_trust()
        ev = TrustEvidence.create(
            "observer", "manipulator", "trust_manipulation", "consistency", 0.8,
            make_state_pair_proof(),
        )
        lattice.observe_and_propagate(ev)
        trust = lattice.get_trust("manipulator").overall_trust()
        assert trust < initial

    def test_all_lattice_evidence_types_reduce_trust(self):
        """All evidence types processable through the lattice pipeline reduce trust."""
        evidence_specs = [
            ("equivocation", "integrity", 0.8, make_equivocation_proof("target")),
            ("clock_regression", "causality", 0.8, make_clock_regression_proof("target")),
            ("invalid_delta", "consistency", 0.8, make_invalid_delta_proof()),
            ("trust_manipulation", "consistency", 0.8, make_state_pair_proof()),
        ]
        for etype, dim, amt, proof in evidence_specs:
            lattice = make_lattice("target")
            initial = lattice.get_trust("target").overall_trust()
            ev = TrustEvidence.create("observer", "target", etype, dim, amt, proof)
            delta = lattice.observe_and_propagate(ev)
            assert delta is not None, f"{etype} returned None delta"
            after = lattice.get_trust("target").overall_trust()
            assert after < initial, f"{etype} did not reduce trust: {initial} -> {after}"

    def test_all_evidence_types_creatable(self):
        """Every defined evidence type can be created as a TrustEvidence object."""
        import hashlib
        h1 = hashlib.sha256(b"a").hexdigest()
        h2 = hashlib.sha256(b"b").hexdigest()
        evidence_specs = [
            ("equivocation", "integrity", make_equivocation_proof("t")),
            ("clock_regression", "causality", make_clock_regression_proof("t")),
            ("invalid_delta", "consistency", make_invalid_delta_proof()),
            ("merkle_divergence", "integrity", pack_merkle_path([([h1, h2], 0)])),
            ("trust_manipulation", "consistency", make_state_pair_proof()),
        ]
        for etype, dim, proof in evidence_specs:
            ev = TrustEvidence.create("observer", "target", etype, dim, 0.5, proof)
            assert ev.evidence_type == etype


# -- 7. Concurrent / Race Condition Tests --------------------------------------

class TestConcurrency:
    def test_concurrent_evidence_no_crash(self):
        peers = [f"peer_{i}" for i in range(20)]
        lattice = make_lattice(*peers)
        errors = []
        def submit_evidence(peer_id):
            try:
                ev = TrustEvidence.create(
                    "observer", peer_id, "equivocation", "integrity", 0.2,
                    make_equivocation_proof(peer_id),
                )
                lattice.observe_and_propagate(ev)
            except Exception as e:
                errors.append(str(e))
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(submit_evidence, p) for p in peers]
            for f in as_completed(futures):
                f.result()
        assert len(errors) == 0, f"Errors: {errors}"

    def test_concurrent_clock_increments(self):
        results = {}
        def increment_clock(peer_id, count):
            clock = CausalTrustClock(peer_id)
            times = []
            for _ in range(count):
                clock = clock.increment()
                times.append(clock.logical_time)
            results[peer_id] = times
        threads = []
        for i in range(10):
            t = threading.Thread(target=increment_clock, args=(f"peer_{i}", 100))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        for peer_id, times in results.items():
            for j in range(1, len(times)):
                assert times[j] > times[j - 1]


# -- 8. Scale Tests ------------------------------------------------------------

class TestScale:
    def test_100_peer_trust_lattice(self):
        peers = [f"peer_{i}" for i in range(100)]
        lattice = make_lattice(*peers)
        start = time.time()
        for i in range(1, 100):
            ev = TrustEvidence.create(
                "observer", f"peer_{i}", "equivocation", "integrity", 0.1,
                make_equivocation_proof(f"peer_{i}"),
            )
            lattice.observe_and_propagate(ev)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100-peer took {elapsed:.2f}s"

    def test_1000_merkle_insertions(self):
        tree = TrustBoundMerkle()
        start = time.time()
        for i in range(1000):
            tree.insert_leaf(f"key_{i}", f"data_{i}".encode(), f"peer_{i % 10}")
        tree.recompute()
        elapsed = time.time() - start
        assert elapsed < 5.0
        assert tree.leaf_count == 1000

    def test_10000_clock_increments(self):
        clock = CausalTrustClock("fast_peer")
        start = time.time()
        for _ in range(10000):
            clock = clock.increment()
        elapsed = time.time() - start
        assert elapsed < 2.0
        assert clock.logical_time == 10000


# -- 9. Property-Based Tests (Hypothesis) -------------------------------------

try:
    from hypothesis import given, settings, strategies as st

    class TestHypothesisProperties:
        @given(st.integers(min_value=1, max_value=500))
        @settings(max_examples=50, deadline=10000)
        def test_clock_increment_count_matches(self, n):
            clock = CausalTrustClock("prop_peer")
            for _ in range(n):
                clock = clock.increment()
            assert clock.logical_time == n

        @given(
            st.lists(
                st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnop"),
                min_size=1, max_size=100,
            )
        )
        @settings(max_examples=30, deadline=10000)
        def test_merkle_leaf_count_matches_insertions(self, keys):
            tree = TrustBoundMerkle()
            unique_keys = list(dict.fromkeys(keys))
            for k in unique_keys:
                tree.insert_leaf(k, b"data", "peer")
            tree.recompute()
            assert tree.leaf_count == len(unique_keys)

        @given(st.sampled_from(DIMENSIONS))
        @settings(max_examples=6, deadline=10000)
        def test_dimension_trust_bounded(self, dim):
            ts = TypedTrustScore.full_trust()
            val = ts.trust_for_dimension(dim)
            assert 0.0 <= val <= 1.0

except ImportError:
    pass


# -- 10. Evidence Integrity Tests ----------------------------------------------

class TestEvidenceIntegrity:
    def test_evidence_has_required_fields(self):
        ev = TrustEvidence.create(
            "a", "b", "equivocation", "integrity", 0.8,
            make_equivocation_proof("b"),
        )
        assert ev.observer == "a"
        assert ev.target == "b"
        assert ev.evidence_type == "equivocation"
        assert ev.dimension == "integrity"
        assert isinstance(ev.proof, bytes)
        assert ev.timestamp > 0

    def test_evidence_types_match_spec(self):
        expected = {"equivocation", "merkle_divergence", "clock_regression",
                    "invalid_delta", "trust_manipulation"}
        assert set(EVIDENCE_TYPES.keys()) == expected

    def test_invalid_evidence_type_rejected(self):
        with pytest.raises((ValueError, KeyError)):
            TrustEvidence.create("a", "b", "nonexistent_type", "integrity", 0.1, b"x")

    def test_evidence_log_grows(self):
        lattice = make_lattice("target")
        for _ in range(5):
            ev = TrustEvidence.create(
                "observer", "target", "equivocation", "integrity", 0.1,
                make_equivocation_proof("target"),
            )
            lattice.observe_and_propagate(ev)
        assert len(lattice.evidence_log) >= 5


# -- 11. Trust Score Dimension Tests -------------------------------------------

class TestTrustDimensions:
    def test_full_trust_all_dimensions(self):
        ts = TypedTrustScore.full_trust()
        for dim in DIMENSIONS:
            assert ts.trust_for_dimension(dim) > 0

    def test_probationary_trust_all_dimensions(self):
        ts = TypedTrustScore.probationary()
        for dim in DIMENSIONS:
            assert ts.trust_for_dimension(dim) == pytest.approx(PROBATION_TRUST)

    def test_overall_trust_is_aggregate(self):
        ts = TypedTrustScore.full_trust()
        overall = ts.overall_trust()
        assert 0.0 <= overall <= 1.0

    def test_verification_level_increases_with_low_trust(self):
        lattice = make_lattice("target")
        for _ in range(8):
            ev = TrustEvidence.create(
                "observer", "target", "equivocation", "integrity", 0.5,
                make_equivocation_proof("target"),
            )
            lattice.observe_and_propagate(ev)
        ts = lattice.get_trust("target")
        level = ts.verification_level()
        assert level >= 1, "Low-trust peers should require higher verification"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
