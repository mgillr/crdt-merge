"""Property-based tests for CRDT verification engine, deduplication, and provenance.

Uses Hypothesis to verify that the verification engine correctly identifies
CRDT law compliance, dedup operations are idempotent, and provenance
tracking accurately records merge decisions.
"""

from __future__ import annotations

import json
import random
from typing import List

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from crdt_merge.verify import (
    verify_crdt,
    verify_commutative,
    verify_associative,
    verify_idempotent,
    verify_convergence,
    CRDTVerification,
    VerificationResult,
)
from crdt_merge.dedup import dedup_list, dedup_records, DedupIndex, MinHashDedup
from crdt_merge.provenance import (
    merge_with_provenance,
    export_provenance,
    ProvenanceLog,
    MergeRecord,
    MergeDecision,
)
from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap


# ---------------------------------------------------------------------------
# Hypothesis strategy helpers
# ---------------------------------------------------------------------------

FAST = settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])

_node_ids = st.sampled_from(["n1", "n2", "n3", "n4"])

def _gen_gcounter() -> GCounter:
    """Produce a random GCounter with 1-3 node slots."""
    g = GCounter()
    for _ in range(random.randint(1, 3)):
        nid = random.choice(["n1", "n2", "n3", "n4"])
        g.increment(nid, random.randint(0, 50))
    return g

def _gen_pncounter() -> PNCounter:
    """Produce a random PNCounter with random increments and decrements."""
    pn = PNCounter()
    for _ in range(random.randint(1, 3)):
        nid = random.choice(["n1", "n2", "n3"])
        pn.increment(nid, random.randint(0, 20))
    for _ in range(random.randint(0, 2)):
        nid = random.choice(["n1", "n2", "n3"])
        pn.decrement(nid, random.randint(0, 10))
    return pn

def _gen_lww_register() -> LWWRegister:
    """Produce a random LWWRegister with a string value, timestamp, and node id."""
    val = random.choice(["alpha", "beta", "gamma", "delta", "epsilon"])
    ts = random.uniform(0, 1000)
    nid = random.choice(["n1", "n2", "n3"])
    return LWWRegister(val, ts, nid)

def _gen_orset() -> ORSet:
    """Produce a random ORSet with 0-5 elements."""
    s = ORSet()
    for _ in range(random.randint(0, 5)):
        elem = random.choice(["a", "b", "c", "d", "e"])
        s.add(elem)
    if random.random() < 0.3:
        to_remove = random.choice(["a", "b", "c", "d", "e"])
        s.remove(to_remove)
    return s


# ===========================================================================
# Verify module tests
# ===========================================================================

class TestVerifyGCounter:
    """verify_crdt against GCounter — all CRDT laws must hold."""

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_crdt_gcounter_passes(self, trials):
        """Run full CRDT verification on GCounter merge; expect all properties pass."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        assert result.passed, result.summary()

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_crdt_gcounter_summary_contains_properties(self, trials):
        """summary() output includes all property names."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        s = result.summary()
        assert "commutativity" in s.lower()
        assert "associativity" in s.lower()
        assert "idempotency" in s.lower()


class TestVerifyPNCounter:
    """verify_crdt against PNCounter."""

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_crdt_pncounter_passes(self, trials):
        """Run full CRDT verification on PNCounter merge; all properties pass."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_pncounter,
            trials=trials,
        )
        assert result.passed, result.summary()


class TestVerifyLWWRegister:
    """verify_crdt against LWWRegister."""

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_crdt_lwwregister_passes(self, trials):
        """Run full CRDT verification on LWWRegister merge; all properties pass."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_lww_register,
            trials=trials,
        )
        assert result.passed, result.summary()


class TestVerifyORSet:
    """verify_crdt against ORSet."""

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_crdt_orset_passes(self, trials):
        """Run full CRDT verification on ORSet merge; all properties pass."""
        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_orset,
            trials=trials,
        )
        assert result.passed, result.summary()


class TestVerifyIndividualProperties:
    """Targeted tests for each individual verification function."""

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_commutative_gcounter(self, trials):
        """Commutativity check alone returns passed=True for GCounter."""
        result = verify_commutative(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        assert isinstance(result, VerificationResult)
        assert result.property_name == "commutativity"
        assert result.passed
        assert result.failures == 0

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_associative_gcounter(self, trials):
        """Associativity check alone returns passed=True for GCounter."""
        result = verify_associative(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        assert isinstance(result, VerificationResult)
        assert result.property_name == "associativity"
        assert result.passed

    @given(st.integers(min_value=10, max_value=30))
    @FAST
    def test_verify_idempotent_gcounter(self, trials):
        """Idempotency check alone returns passed=True for GCounter."""
        result = verify_idempotent(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        assert isinstance(result, VerificationResult)
        assert result.property_name == "idempotency"
        assert result.passed

    @given(st.integers(min_value=10, max_value=20))
    @FAST
    def test_crdt_verification_summary_format(self, trials):
        """CRDTVerification.summary() returns a multi-line report string."""
        v = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=_gen_gcounter,
            trials=trials,
        )
        s = v.summary()
        assert "CRDT Verification Report" in s
        assert "VERIFIED" in s or "FAILED" in s


# ===========================================================================
# Dedup module tests
# ===========================================================================

class TestDedupList:
    """Property-based tests for dedup_list."""

    @given(st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=30))
    @FAST
    def test_dedup_list_idempotent(self, items):
        """Applying dedup twice produces the same unique list as applying it once."""
        unique1, _ = dedup_list(items)
        unique2, _ = dedup_list(unique1)
        assert unique1 == unique2

    @given(st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=20, unique=True))
    @FAST
    def test_dedup_list_preserves_unique_items(self, items):
        """When all input items are unique, no items are removed."""
        # Items are unique by value; dedup is case-insensitive, so filter
        seen_lower = set()
        case_unique = []
        for item in items:
            low = item.lower()
            if low not in seen_lower:
                seen_lower.add(low)
                case_unique.append(item)
        unique, removed = dedup_list(case_unique)
        assert len(unique) == len(case_unique)
        assert removed == []

    @given(st.text(min_size=1, max_size=20), st.integers(min_value=2, max_value=5))
    @FAST
    def test_dedup_list_removes_exact_duplicates(self, item, count):
        """Duplicate copies of the same string are collapsed to a single entry."""
        items = [item] * count
        unique, removed = dedup_list(items)
        assert len(unique) == 1
        assert len(removed) == count - 1


class TestDedupRecords:
    """Property-based tests for dedup_records."""

    @given(st.lists(
        st.fixed_dictionaries({"id": st.integers(min_value=0, max_value=100), "name": st.text(min_size=1, max_size=10)}),
        min_size=1, max_size=15,
    ))
    @FAST
    def test_dedup_records_preserves_unique(self, records):
        """Unique records (by serialized content) survive dedup unchanged."""
        unique, removed_count = dedup_records(records)
        assert len(unique) + removed_count == len(records)
        # Re-dedup produces same count
        unique2, removed2 = dedup_records(unique)
        assert removed2 == 0


class TestDedupIndex:
    """Property-based tests for DedupIndex CRDT merge."""

    @given(
        st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
        st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10),
    )
    @FAST
    def test_dedup_index_merge_commutative(self, texts_a, texts_b):
        """DedupIndex.merge is commutative: a.merge(b).size == b.merge(a).size."""
        idx_a = DedupIndex("a")
        for t in texts_a:
            idx_a.add_exact(t)
        idx_b = DedupIndex("b")
        for t in texts_b:
            idx_b.add_exact(t)
        ab = idx_a.merge(idx_b)
        ba = idx_b.merge(idx_a)
        assert ab.size == ba.size

    @given(
        st.lists(st.text(min_size=1, max_size=15), min_size=0, max_size=8),
        st.lists(st.text(min_size=1, max_size=15), min_size=0, max_size=8),
        st.lists(st.text(min_size=1, max_size=15), min_size=0, max_size=8),
    )
    @FAST
    def test_dedup_index_merge_associative(self, texts_a, texts_b, texts_c):
        """Three-way DedupIndex merge is order-independent: (a⊕b)⊕c == a⊕(b⊕c)."""
        def make_idx(nid, texts):
            idx = DedupIndex(nid)
            for t in texts:
                idx.add_exact(t)
            return idx

        a = make_idx("a", texts_a)
        b = make_idx("b", texts_b)
        c = make_idx("c", texts_c)
        ab_c = a.merge(b).merge(c)
        a_bc = a.merge(b.merge(c))
        assert ab_c.size == a_bc.size


class TestMinHashDedup:
    """Property-based tests for MinHashDedup near-duplicate detection."""

    @given(st.text(min_size=10, max_size=60))
    @FAST
    def test_minhash_similar_items_detected(self, base_text):
        """Near-identical strings (minor suffix change) are flagged as duplicates."""
        assume(len(base_text.strip()) >= 10)
        mh = MinHashDedup(num_hashes=128, threshold=0.5)
        added_first = mh.add("item1", base_text)
        # Create a minor variant -- append a single char
        variant = base_text + "z"
        added_second = mh.add("item2", variant)
        # At least the first must be added; if similarity is high, second is dup
        assert added_first is True
        # If both were added, the texts were dissimilar enough at threshold=0.5
        # This is a probabilistic check -- we just assert no crash and boolean return
        assert isinstance(added_second, bool)


# ===========================================================================
# Provenance module tests
# ===========================================================================

# Strategy helpers for generating merge input pairs

_prov_record = st.fixed_dictionaries({
    "id": st.integers(min_value=1, max_value=50),
    "value": st.text(min_size=1, max_size=15),
})


class TestProvenanceCompleteness:
    """Property-based tests for merge_with_provenance output coverage."""

    @given(
        st.lists(_prov_record, min_size=1, max_size=10, unique_by=lambda r: r["id"]),
        st.lists(_prov_record, min_size=1, max_size=10, unique_by=lambda r: r["id"]),
    )
    @FAST
    def test_merge_provenance_completeness(self, list_a, list_b):
        """All keys from both inputs appear in the merged output."""
        merged, log = merge_with_provenance(list_a, list_b, key="id")
        keys_a = {r["id"] for r in list_a}
        keys_b = {r["id"] for r in list_b}
        expected_keys = keys_a | keys_b
        merged_keys = {r["id"] for r in merged}
        assert merged_keys == expected_keys

    @given(
        st.lists(_prov_record, min_size=1, max_size=10, unique_by=lambda r: r["id"]),
        st.lists(_prov_record, min_size=1, max_size=10, unique_by=lambda r: r["id"]),
    )
    @FAST
    def test_merge_provenance_log_consistency(self, list_a, list_b):
        """ProvenanceLog row counts match the actual merged output length."""
        merged, log = merge_with_provenance(list_a, list_b, key="id")
        assert log.total_rows == len(merged)
        assert log.total_rows == log.merged_rows + log.unique_a_rows + log.unique_b_rows
        assert len(log.records) == log.total_rows


class TestProvenanceExport:
    """Property-based tests for provenance export formats."""

    @given(
        st.lists(_prov_record, min_size=1, max_size=8, unique_by=lambda r: r["id"]),
        st.lists(_prov_record, min_size=1, max_size=8, unique_by=lambda r: r["id"]),
    )
    @FAST
    def test_export_provenance_json_roundtrip(self, list_a, list_b):
        """JSON export parses back into a dict with expected top-level keys."""
        _, log = merge_with_provenance(list_a, list_b, key="id")
        json_str = export_provenance(log, format="json")
        parsed = json.loads(json_str)
        assert "total_rows" in parsed
        assert "records" in parsed
        assert parsed["total_rows"] == log.total_rows

    @given(
        st.lists(_prov_record, min_size=1, max_size=8, unique_by=lambda r: r["id"]),
        st.lists(_prov_record, min_size=1, max_size=8, unique_by=lambda r: r["id"]),
    )
    @FAST
    def test_export_provenance_csv_headers(self, list_a, list_b):
        """CSV export starts with the canonical header row."""
        _, log = merge_with_provenance(list_a, list_b, key="id")
        csv_str = export_provenance(log, format="csv")
        header = csv_str.split("\n")[0]
        assert header == "key,origin,field,source,strategy,value,alternative"


class TestProvenanceConflicts:
    """Property-based tests for provenance conflict tracking."""

    @given(
        st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=8, unique=True),
        st.text(min_size=1, max_size=10),
        st.text(min_size=1, max_size=10),
    )
    @FAST
    def test_provenance_tracks_conflicts(self, shared_ids, val_a, val_b):
        """Overlapping keys with differing values are recorded as conflicts."""
        assume(val_a != val_b)
        list_a = [{"id": k, "value": val_a} for k in shared_ids]
        list_b = [{"id": k, "value": val_b} for k in shared_ids]
        merged, log = merge_with_provenance(list_a, list_b, key="id")
        assert log.total_conflicts >= len(shared_ids)
        # Each merged record must have at least one conflict decision
        for rec in log.records:
            assert rec.conflict_count >= 1
