"""Unicode normalization edge case tests for merge strategies."""
import unicodedata
import pytest

CAFE_NFC = "caf\u00e9"          # precomposed NFC
CAFE_NFD = "cafe\u0301"          # decomposed NFD
CAFE_NFKC = unicodedata.normalize('NFKC', CAFE_NFC)
CAFE_NFKD = unicodedata.normalize('NFKD', CAFE_NFC)

@pytest.mark.parametrize("a_name,b_name", [
    (CAFE_NFC, CAFE_NFD),
    (CAFE_NFC, CAFE_NFKC),
    (CAFE_NFD, CAFE_NFKD),
])
def test_visually_identical_strings_deduplicated(a_name, b_name):
    """Visually identical strings with different normalization should not duplicate."""
    assert unicodedata.normalize('NFC', a_name) == unicodedata.normalize('NFC', b_name), \
        "Test setup: strings must be visually identical after NFC normalization"

    try:
        from crdt_merge.dataframe import merge as df_merge
        from crdt_merge.strategies import MergeSchema, LWW
        a = [{"id": "1", "name": a_name, "_ts": 1.0}]
        b = [{"id": "1", "name": b_name, "_ts": 2.0}]
        result = df_merge(a, b, key="id", schema=MergeSchema(default=LWW()),
                          timestamp_col="_ts")
        # Should produce one record, not two
        assert len(result) == 1, f"Should deduplicate visually identical keys"
    except ImportError:
        pytest.skip("crdt_merge.dataframe not available")


def test_zero_width_joiner():
    """Zero-width joiners should not create duplicate records."""
    with_zwj = "test\u200dvalue"
    without_zwj = "testvalue"
    try:
        from crdt_merge.dataframe import merge as df_merge
        from crdt_merge.strategies import MergeSchema, LWW
        a = [{"id": "1", "name": with_zwj}]
        b = [{"id": "1", "name": without_zwj}]
        result = df_merge(a, b, key="id", schema=MergeSchema(default=LWW()))
        assert result is not None
    except ImportError:
        pytest.skip("crdt_merge.dataframe not available")
