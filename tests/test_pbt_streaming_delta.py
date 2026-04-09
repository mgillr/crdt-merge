"""Property-based tests for streaming merge and delta engine.

Uses Hypothesis to verify CRDT laws hold for batched streaming operations
and that delta compute/apply/compose maintain consistency.
"""

import copy
import itertools

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from crdt_merge.streaming import (
    merge_stream,
    merge_sorted_stream,
    count_stream,
    StreamStats,
)
from crdt_merge.delta import (
    Delta,
    DeltaStore,
    compute_delta,
    apply_delta,
    compose_deltas,
)


# ---------------------------------------------------------------------------
# Hypothesis custom strategies
# ---------------------------------------------------------------------------

@st.composite
def record_list(draw, min_size=0, max_size=15, max_id=50):
    """Generate a list of dicts with unique integer 'id' keys and a 'value' field."""
    ids = draw(st.lists(
        st.integers(min_value=0, max_value=max_id),
        min_size=min_size,
        max_size=max_size,
        unique=True,
    ))
    records = []
    for i in ids:
        val = draw(st.text(min_size=1, max_size=8, alphabet="abcdefgh"))
        records.append({"id": i, "value": val})
    return records


@st.composite
def record_pair(draw, max_size=15, max_id=50):
    """Generate two record lists with potentially overlapping 'id' keys."""
    a = draw(record_list(max_size=max_size, max_id=max_id))
    b = draw(record_list(max_size=max_size, max_id=max_id))
    return a, b


@st.composite
def sorted_record_pair(draw, max_size=15, max_id=50):
    """Generate two record lists sorted by 'id' with potentially overlapping keys."""
    a = draw(record_list(max_size=max_size, max_id=max_id))
    b = draw(record_list(max_size=max_size, max_id=max_id))
    a.sort(key=lambda r: r["id"])
    b.sort(key=lambda r: r["id"])
    return a, b


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_stream(gen):
    """Flatten a batch generator into a single list of records."""
    return list(itertools.chain.from_iterable(gen))


def index_by_key(records, key="id"):
    """Build {key_value: record} dict from a record list."""
    return {r[key]: r for r in records}


# ---------------------------------------------------------------------------
# merge_stream -- CRDT properties
# ---------------------------------------------------------------------------

class TestMergeStreamProperties:
    """Property-based tests for the unsorted streaming merge pipeline."""

    @given(data=record_pair())
    @settings(max_examples=50)
    def test_commutativity_keys(self, data):
        """Commutativity: stream merge yields identical key sets regardless of source ordering."""
        a, b = data
        keys_ab = {r["id"] for r in collect_stream(merge_stream(iter(a), iter(b), key="id"))}
        keys_ba = {r["id"] for r in collect_stream(merge_stream(iter(b), iter(a), key="id"))}
        assert keys_ab == keys_ba

    @given(data=record_pair())
    @settings(max_examples=50)
    def test_commutativity_values(self, data):
        """Commutativity: resolved record values match regardless of source ordering."""
        a, b = data
        idx_ab = index_by_key(collect_stream(merge_stream(iter(a), iter(b), key="id")))
        idx_ba = index_by_key(collect_stream(merge_stream(iter(b), iter(a), key="id")))
        for k in idx_ab:
            assert idx_ab[k] == idx_ba[k], f"Value mismatch on key {k}"

    @given(data=record_pair())
    @settings(max_examples=50)
    def test_completeness(self, data):
        """Completeness: all unique keys from both sources appear in merged output."""
        a, b = data
        expected_keys = {r["id"] for r in a} | {r["id"] for r in b}
        result_keys = {r["id"] for r in collect_stream(merge_stream(iter(a), iter(b), key="id"))}
        assert result_keys == expected_keys

    @given(records=record_list(max_size=15))
    @settings(max_examples=50)
    def test_idempotency(self, records):
        """Idempotency: merging a dataset with a copy of itself yields identical records."""
        a = copy.deepcopy(records)
        b = copy.deepcopy(records)
        result = index_by_key(collect_stream(merge_stream(iter(a), iter(b), key="id")))
        assert result == index_by_key(records)

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_empty_source_a(self, records):
        """Identity: empty source_a preserves all source_b records."""
        result = collect_stream(merge_stream(iter([]), iter(records), key="id"))
        assert index_by_key(result) == index_by_key(records)

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_empty_source_b(self, records):
        """Identity: empty source_b preserves all source_a records."""
        result = collect_stream(merge_stream(iter(records), iter([]), key="id"))
        assert index_by_key(result) == index_by_key(records)

    @given(data=record_pair(max_size=20), batch_size=st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_batch_size_respected(self, data, batch_size):
        """Batching: no yielded batch exceeds the configured batch_size limit."""
        a, b = data
        for batch in merge_stream(iter(a), iter(b), key="id", batch_size=batch_size):
            assert len(batch) <= batch_size

    @given(data=record_pair())
    @settings(max_examples=50)
    def test_stats_rows_processed(self, data):
        """Statistics: StreamStats.rows_processed matches total output row count."""
        a, b = data
        stats = StreamStats()
        result = collect_stream(merge_stream(iter(a), iter(b), key="id", stats=stats))
        assert stats.rows_processed == len(result)

    @given(data=record_pair())
    @settings(max_examples=50)
    def test_no_duplicate_keys(self, data):
        """Uniqueness: merged output contains no duplicate keys."""
        a, b = data
        result = collect_stream(merge_stream(iter(a), iter(b), key="id"))
        keys = [r["id"] for r in result]
        assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# merge_sorted_stream -- sorted merge-join properties
# ---------------------------------------------------------------------------

class TestMergeSortedStreamProperties:
    """Property-based tests for the sorted streaming merge-join pipeline."""

    @given(data=sorted_record_pair())
    @settings(max_examples=50)
    def test_completeness(self, data):
        """Completeness: sorted merge output includes every unique key from both sources."""
        a, b = data
        expected_keys = {r["id"] for r in a} | {r["id"] for r in b}
        result_keys = {r["id"] for r in collect_stream(merge_sorted_stream(iter(a), iter(b), key="id"))}
        assert result_keys == expected_keys

    @given(data=sorted_record_pair())
    @settings(max_examples=50)
    def test_no_duplicate_keys(self, data):
        """Uniqueness: sorted merge produces no duplicate keys in output."""
        a, b = data
        result = collect_stream(merge_sorted_stream(iter(a), iter(b), key="id"))
        keys = [r["id"] for r in result]
        assert len(keys) == len(set(keys))

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_empty_source_preserves_data(self, records):
        """Identity: sorted merge against empty source preserves all records."""
        records.sort(key=lambda r: r["id"])
        result = collect_stream(merge_sorted_stream(iter(records), iter([]), key="id"))
        assert index_by_key(result) == index_by_key(records)


# ---------------------------------------------------------------------------
# count_stream -- counting accuracy
# ---------------------------------------------------------------------------

class TestCountStreamProperties:
    """Property-based tests for stream counting."""

    @given(records=record_list())
    @settings(max_examples=50)
    def test_accuracy(self, records):
        """Accuracy: count_stream returns the exact number of items in the iterable."""
        assert count_stream(iter(records)) == len(records)

    @given(n=st.integers(min_value=0, max_value=200))
    @settings(max_examples=50)
    def test_range_count(self, n):
        """Accuracy: count_stream on range(n) yields n."""
        assert count_stream(iter(range(n))) == n


# ---------------------------------------------------------------------------
# Delta -- serialization, emptiness, sizing
# ---------------------------------------------------------------------------

class TestDeltaProperties:
    """Property-based tests for Delta dataclass invariants."""

    @given(
        added=record_list(max_size=8),
        modified=record_list(max_size=8),
        removed=st.lists(st.text(min_size=1, max_size=5), max_size=8),
        version=st.integers(min_value=0, max_value=1000),
        source_node=st.text(min_size=0, max_size=10),
    )
    @settings(max_examples=50)
    def test_roundtrip_serialization(self, added, modified, removed, version, source_node):
        """Roundtrip: Delta.from_dict(delta.to_dict()) preserves all fields."""
        delta = Delta(added, modified, removed, version, source_node=source_node)
        restored = Delta.from_dict(delta.to_dict())
        assert restored.added == delta.added
        assert restored.modified == delta.modified
        assert restored.removed == delta.removed
        assert restored.version == delta.version
        assert restored.source_node == delta.source_node

    @given(records=record_list(max_size=15))
    @settings(max_examples=50)
    def test_is_empty_identical_inputs(self, records):
        """Empty delta: compute_delta on identical old and new states produces is_empty=True."""
        delta = compute_delta(records, records, key="id")
        assert delta.is_empty

    @given(
        added=record_list(max_size=5),
        modified=record_list(max_size=5),
        removed=st.lists(st.text(min_size=1, max_size=5), max_size=5),
    )
    @settings(max_examples=50)
    def test_size_correctness(self, added, modified, removed):
        """Size: delta.size equals sum of added, modified, and removed counts."""
        delta = Delta(added, modified, removed)
        assert delta.size == len(added) + len(modified) + len(removed)

    @given(
        added=record_list(max_size=5),
        modified=record_list(max_size=5),
        removed=st.lists(st.text(min_size=1, max_size=5), max_size=5),
    )
    @settings(max_examples=50)
    def test_to_dict_contains_all_keys(self, added, modified, removed):
        """Serialization: to_dict output contains all expected top-level keys."""
        delta = Delta(added, modified, removed, version=1, source_node="n1")
        d = delta.to_dict()
        assert set(d.keys()) == {"added", "modified", "removed", "version", "timestamp", "source_node"}


# ---------------------------------------------------------------------------
# compute_delta + apply_delta -- roundtrip correctness
# ---------------------------------------------------------------------------

class TestDeltaComputeApplyProperties:
    """Property-based tests for delta compute/apply roundtrip consistency."""

    @given(old=record_list(max_size=12, max_id=30), new=record_list(max_size=12, max_id=30))
    @settings(max_examples=50)
    def test_compute_apply_roundtrip(self, old, new):
        """Roundtrip: apply_delta(old, compute_delta(old, new, key), key) reproduces new state."""
        delta = compute_delta(old, new, key="id")
        result = apply_delta(old, delta, key="id")
        assert index_by_key(result) == index_by_key(new)

    @given(
        old=record_list(min_size=1, max_size=10, max_id=30),
        mid=record_list(min_size=1, max_size=10, max_id=30),
        new=record_list(min_size=1, max_size=10, max_id=30),
    )
    @settings(max_examples=50)
    def test_compose_deltas_sequential(self, old, mid, new):
        """Composition: compose(delta(old→mid), delta(mid→new)) applied once equals sequential application."""
        d1 = compute_delta(old, mid, key="id")
        d2 = compute_delta(mid, new, key="id")
        composed = compose_deltas(d1, d2, key="id")
        result_composed = apply_delta(old, composed, key="id")
        result_sequential = apply_delta(apply_delta(old, d1, key="id"), d2, key="id")
        assert index_by_key(result_composed) == index_by_key(result_sequential)

    @given(old=record_list(max_size=10, max_id=30), new=record_list(max_size=10, max_id=30))
    @settings(max_examples=50)
    def test_compose_with_empty_identity(self, old, new):
        """Identity: composing a delta with an empty delta yields equivalent result."""
        d = compute_delta(old, new, key="id")
        composed = compose_deltas(d, Delta(), key="id")
        assert index_by_key(apply_delta(old, composed, key="id")) == index_by_key(
            apply_delta(old, d, key="id")
        )

    @given(records=record_list(min_size=1, max_size=10, max_id=30))
    @settings(max_examples=50)
    def test_apply_empty_delta_is_identity(self, records):
        """Identity: applying an empty delta preserves the original record set."""
        result = apply_delta(records, Delta(), key="id")
        assert index_by_key(result) == index_by_key(records)


# ---------------------------------------------------------------------------
# DeltaStore -- stateful ingestion properties
# ---------------------------------------------------------------------------

class TestDeltaStoreProperties:
    """Property-based tests for stateful DeltaStore ingestion."""

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_first_ingest_returns_none(self, records):
        """Bootstrap: first ingest into a DeltaStore returns None (no prior state to diff)."""
        store = DeltaStore(key="id")
        assert store.ingest(records) is None

    @given(
        first=record_list(min_size=1, max_size=10, max_id=30),
        second=record_list(min_size=1, max_size=10, max_id=30),
        third=record_list(min_size=1, max_size=10, max_id=30),
    )
    @settings(max_examples=50)
    def test_version_increments(self, first, second, third):
        """Versioning: each ingest after the first increments the store version by one."""
        store = DeltaStore(key="id")
        store.ingest(first)
        assert store.version == 0
        store.ingest(second)
        assert store.version == 1
        store.ingest(third)
        assert store.version == 2

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_records_match_last_ingest(self, records):
        """State: DeltaStore.records reflects the most recently ingested dataset."""
        store = DeltaStore(key="id")
        store.ingest(records)
        assert index_by_key(store.records) == index_by_key(records)

    @given(records=record_list(min_size=1, max_size=15))
    @settings(max_examples=50)
    def test_size_matches_record_count(self, records):
        """Size: DeltaStore.size equals the number of unique-keyed records after ingest."""
        store = DeltaStore(key="id")
        store.ingest(records)
        assert store.size == len(records)

    @given(
        first=record_list(min_size=1, max_size=10, max_id=30),
        second=record_list(min_size=1, max_size=10, max_id=30),
    )
    @settings(max_examples=50)
    def test_ingest_delta_matches_compute_delta(self, first, second):
        """Consistency: delta returned by DeltaStore.ingest matches standalone compute_delta."""
        store = DeltaStore(key="id")
        store.ingest(first)
        store_delta = store.ingest(second)
        direct_delta = compute_delta(first, second, key="id")
        assert set(map(str, store_delta.removed)) == set(map(str, direct_delta.removed))
        assert index_by_key(store_delta.added) == index_by_key(direct_delta.added)
        assert index_by_key(store_delta.modified) == index_by_key(direct_delta.modified)
