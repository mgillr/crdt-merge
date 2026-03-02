"""Stress tests for large datasets (100K+ rows). Marked as slow."""
import pytest

@pytest.mark.slow
def test_large_dataset_lww_commutativity():
    """LWW merge is commutative for 100K+ rows."""
    pytest.importorskip("crdt_merge.dataframe")
    from crdt_merge.dataframe import merge as df_merge
    from crdt_merge.strategies import MergeSchema, LWW

    N = 100_000
    a = [{"id": str(i), "value": i, "_ts": float(i % 2)} for i in range(N)]
    b = [{"id": str(i), "value": i * 2, "_ts": float(1 - i % 2)} for i in range(N)]

    schema = MergeSchema(default=LWW())
    result_ab = df_merge(a, b, key="id", schema=schema, timestamp_col="_ts")
    result_ba = df_merge(b, a, key="id", schema=schema, timestamp_col="_ts")

    # Sort both by id for comparison
    result_ab_sorted = sorted(result_ab, key=lambda x: int(x["id"]))
    result_ba_sorted = sorted(result_ba, key=lambda x: int(x["id"]))

    assert len(result_ab_sorted) == len(result_ba_sorted), "Same number of records"
    for r_ab, r_ba in zip(result_ab_sorted, result_ba_sorted):
        assert r_ab["id"] == r_ba["id"]
        assert r_ab["value"] == r_ba["value"], f"Commutativity failure at id={r_ab['id']}"


@pytest.mark.slow
def test_large_dataset_does_not_oom():
    """Merge of 100K rows stays within reasonable memory."""
    pytest.importorskip("crdt_merge.dataframe")
    from crdt_merge.dataframe import merge as df_merge
    from crdt_merge.strategies import MergeSchema, LWW

    N = 100_000
    a = [{"id": str(i), "val": i} for i in range(N)]
    b = [{"id": str(i + N // 2), "val": i} for i in range(N)]

    result = df_merge(a, b, key="id", schema=MergeSchema(default=LWW()))
    assert result is not None
    assert len(result) > 0
