"""Regression tests for the homeostasis / SEC convergence fix.

Background
----------
``TrustHomeostasis.normalize`` performs a global, peer-set-dependent, non-monotone
rescale (``scale = peer_count / total``). A previous version applied it *inside*
``DeltaTrustLattice.merge`` (and the evidence-recording paths), overwriting the
GCounter join with a rescaled result. That broke the join-semilattice the lattice's
Strong-Eventual-Consistency guarantee rests on: two replicas merging the same
evidence in different orders / from different peer subsets could converge to
*different* states.

The fix keeps the stored lattice a pure GCounter join (merge and record are
monotone joins) and exposes homeostasis as a DERIVED READ (``normalized_scores``),
computed deterministically from the converged state. ``get_trust`` returns the raw,
evidence-based, convergent score (what security / clock decisions must use); the
conserved-budget view is separate and for allocation only.
"""
import hashlib

from crdt_merge.e4.delta_trust_lattice import DeltaTrustLattice
from crdt_merge.e4.typed_trust import TypedTrustScore, TrustHomeostasis


def _lattice(peer, evidence):
    L = DeltaTrustLattice(peer)
    for p, ev in evidence.items():
        L._trust_scores[p] = TypedTrustScore(_evidence=ev)
    return L


def test_merge_is_order_independent_across_peer_subsets():
    """merge must be commutative/associative: same evidence, any order -> same root.

    This is the property the in-merge homeostasis normalization broke. The three
    replicas below deliberately see *different* peer subsets, which is what made
    the old ``peer_count/total`` rescale order-dependent.
    """
    A = _lattice("A", {"x": {"integrity": {"o": 0.2}}})
    B = _lattice("B", {"x": {"integrity": {"o": 0.4}}, "y": {"integrity": {"o": 0.1}}})
    C = _lattice("C", {"z": {"integrity": {"o": 0.6}}})

    r1 = A.merge(B).merge(C).compute_trust_root()
    r2 = C.merge(B).merge(A).compute_trust_root()
    r3 = B.merge(C).merge(A).compute_trust_root()
    assert r1 == r2 == r3


def test_merge_is_idempotent():
    A = _lattice("A", {"x": {"integrity": {"o": 0.3}}, "y": {"gossip": {"o": 0.2}}})
    assert A.merge(A).compute_trust_root() == A.compute_trust_root()


def test_get_trust_reflects_raw_evidence_not_conserved_budget():
    """A lone peer with evidence stays degraded: homeostasis must not rescale it
    up to a conserved budget in the security-read path."""
    L = DeltaTrustLattice("me", initial_peers={"eve"})
    L._trust_scores["eve"] = TypedTrustScore(
        _evidence={"integrity": {"o": 0.7}}
    )
    assert L.get_trust("eve").trust_for_dimension("integrity") == pytest_approx(0.3)


def test_normalized_scores_preserves_conserved_budget_as_derived_view():
    """The conserved-budget feature survives -- as a derived read that does not
    touch the stored lattice."""
    L = DeltaTrustLattice("me")
    L._trust_scores = {
        "alice": TypedTrustScore(_evidence={"integrity": {"o": 0.1}}),
        "bob": TypedTrustScore(_evidence={"integrity": {"o": 0.3}}),
        "carol": TypedTrustScore(_evidence={"integrity": {"o": 0.5}}),
    }
    before_root = L.compute_trust_root()
    view = L.normalized_scores()
    total = sum(view[p].trust_for_dimension("integrity") for p in view)
    assert total == pytest_approx(3.0, abs=0.4)          # budget conserved
    assert L.compute_trust_root() == before_root         # stored state untouched


def test_normalized_view_is_deterministic_across_replicas():
    """Two replicas with the same converged raw state derive the identical
    normalized view (so the conserved-budget read is itself convergent)."""
    A = _lattice("A", {"x": {"integrity": {"o": 0.2}}, "y": {"integrity": {"o": 0.5}}})
    B = _lattice("B", {"y": {"integrity": {"o": 0.5}}, "x": {"integrity": {"o": 0.2}}})
    va = A.normalized_scores()
    vb = B.normalized_scores()
    for p in set(va) | set(vb):
        assert va[p].serialize() == vb[p].serialize()


# tiny local approx to avoid a hard pytest import dependency in the helper name
def pytest_approx(value, abs=1e-6):
    import pytest
    return pytest.approx(value, abs=abs)
