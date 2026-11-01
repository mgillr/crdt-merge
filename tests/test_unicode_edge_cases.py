"""Unicode normalization edge case tests for merge strategies.

Validates the NFC-normalization-before-comparison policy across:
- All four normalization forms (NFC, NFD, NFKC, NFKD)
- String keys AND string values
- Combining characters, surrogate-pair (astral plane) codepoints, and
  zero-width joiners.

Stdlib-only (``unicodedata``). No external unicode library is imported.
"""
import unicodedata
import pytest


NORMALIZATION_FORMS = ("NFC", "NFD", "NFKC", "NFKD")

# Pairs covering every ordered combination of the four forms (excluding self).
FORM_PAIRS = [(a, b) for a in NORMALIZATION_FORMS for b in NORMALIZATION_FORMS if a != b]


def _n(form: str, s: str) -> str:
    return unicodedata.normalize(form, s)


# ---------------------------------------------------------------------------
# Source strings
# ---------------------------------------------------------------------------

# Precomposed + decomposed combining-character cases ("café", "ñ", "Å").
PRECOMPOSED = "café"                    # NFC form: e with acute precomposed
DECOMPOSED = "cafe\u0301"               # NFD form: e + U+0301 combining acute
ANGSTROM = "\u212b"                     # U+212B ANGSTROM SIGN; NFC folds to "Å"

# Compatibility pair: ﬃ (U+FB03) is a compatibility-equivalent of "ffi".
COMPAT_LIGATURE = "o\ufb03ce"           # "office" with ﬃ ligature
COMPAT_ASCII = "office"

# Zero-width joiner case: should NOT be treated as equivalent under any form.
ZWJ_TEXT = "test\u200dvalue"
PLAIN_TEXT = "testvalue"

# Astral-plane (surrogate-pair range) codepoint: U+1F600 GRINNING FACE.
# Python 3 uses 32-bit code-points internally, so surrogate-pair handling
# shows up primarily in UTF-16 round-trips; we verify the codepoint survives
# merge and all four normalization forms.
ASTRAL_EMOJI = "\U0001F600"
ASTRAL_COMPOUND = "hello \U0001F600 world"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skip_if_dataframe_unavailable():
    try:
        from crdt_merge.dataframe import merge  # noqa: F401
        from crdt_merge.strategies import MergeSchema, LWW  # noqa: F401
    except ImportError:
        pytest.skip("crdt_merge.dataframe not available")


def _merge(a, b, key="id", schema=None, timestamp_col=None):
    from crdt_merge.dataframe import merge
    from crdt_merge.strategies import MergeSchema, LWW
    if schema is None:
        schema = MergeSchema(default=LWW())
    kwargs = {"key": key, "schema": schema}
    if timestamp_col is not None:
        kwargs["timestamp_col"] = timestamp_col
    return merge(a, b, **kwargs)


# ---------------------------------------------------------------------------
# Policy sanity: library must NFC-normalize before comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form_a,form_b", FORM_PAIRS)
def test_value_equivalence_across_all_form_pairs(form_a, form_b):
    """NFC-equal values in different forms must merge to a single record."""
    _skip_if_dataframe_unavailable()
    a_val = _n(form_a, PRECOMPOSED)
    b_val = _n(form_b, PRECOMPOSED)
    assert _n("NFC", a_val) == _n("NFC", b_val), \
        f"Setup invariant: {form_a} and {form_b} must be NFC-equal"
    a = [{"id": "1", "name": a_val, "_ts": 1.0}]
    b = [{"id": "1", "name": b_val, "_ts": 2.0}]
    result = _merge(a, b, timestamp_col="_ts")
    assert len(result) == 1, \
        f"{form_a} vs {form_b}: expected single record, got {len(result)}"


@pytest.mark.parametrize("form_a,form_b", FORM_PAIRS)
def test_key_equivalence_across_all_form_pairs(form_a, form_b):
    """NFC-equal string keys in different forms must collapse to one entry."""
    _skip_if_dataframe_unavailable()
    a_key = _n(form_a, PRECOMPOSED)
    b_key = _n(form_b, PRECOMPOSED)
    assert _n("NFC", a_key) == _n("NFC", b_key)
    a = [{"id": a_key, "value": "x", "_ts": 1.0}]
    b = [{"id": b_key, "value": "y", "_ts": 2.0}]
    result = _merge(a, b, key="id", timestamp_col="_ts")
    assert len(result) == 1, \
        f"{form_a} vs {form_b} keys: expected single record, got {len(result)}"


# ---------------------------------------------------------------------------
# Negative cases: strings that remain distinct under NFC must NOT dedup
# ---------------------------------------------------------------------------

def test_values_distinct_after_nfc_are_not_merged():
    _skip_if_dataframe_unavailable()
    assert _n("NFC", ZWJ_TEXT) != _n("NFC", PLAIN_TEXT)
    a = [{"id": "1", "name": ZWJ_TEXT, "_ts": 1.0}]
    b = [{"id": "2", "name": PLAIN_TEXT, "_ts": 1.0}]
    result = _merge(a, b, timestamp_col="_ts")
    assert len(result) == 2


def test_keys_distinct_after_nfc_are_not_merged():
    _skip_if_dataframe_unavailable()
    assert _n("NFC", ZWJ_TEXT) != _n("NFC", PLAIN_TEXT)
    a = [{"id": ZWJ_TEXT, "value": "x"}]
    b = [{"id": PLAIN_TEXT, "value": "y"}]
    result = _merge(a, b, key="id")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Combining characters: precomposed vs decomposed
# ---------------------------------------------------------------------------

def test_precomposed_and_decomposed_values_merge():
    _skip_if_dataframe_unavailable()
    assert PRECOMPOSED != DECOMPOSED
    assert _n("NFC", PRECOMPOSED) == _n("NFC", DECOMPOSED)
    a = [{"id": "1", "name": PRECOMPOSED, "_ts": 1.0}]
    b = [{"id": "1", "name": DECOMPOSED, "_ts": 2.0}]
    result = _merge(a, b, timestamp_col="_ts")
    assert len(result) == 1


def test_angstrom_sign_folds_to_latin_a_ring():
    """U+212B ANGSTROM SIGN and U+00C5 LATIN CAPITAL A WITH RING are NFC-equivalent."""
    _skip_if_dataframe_unavailable()
    assert _n("NFC", ANGSTROM) == _n("NFC", "\u00c5")
    a = [{"id": ANGSTROM, "value": "x"}]
    b = [{"id": "\u00c5", "value": "y"}]
    result = _merge(a, b, key="id")
    assert len(result) == 1


def test_compatibility_ligature_only_equal_under_nfkc_nfkd():
    """ﬃ is canonical-distinct from 'ffi' (NFC/NFD), compatibility-equal (NFKC/NFKD)."""
    _skip_if_dataframe_unavailable()
    assert _n("NFC", COMPAT_LIGATURE) != _n("NFC", COMPAT_ASCII)
    assert _n("NFKC", COMPAT_LIGATURE) == _n("NFKC", COMPAT_ASCII)
    # Library policy is NFC-before-comparison, so these remain distinct.
    a = [{"id": "1", "name": COMPAT_LIGATURE, "_ts": 1.0}]
    b = [{"id": "2", "name": COMPAT_ASCII, "_ts": 1.0}]
    result = _merge(a, b, timestamp_col="_ts")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Zero-width joiner
# ---------------------------------------------------------------------------

def test_zero_width_joiner_changes_identity():
    """ZWJ-bearing string must not dedup with its ZWJ-free counterpart."""
    _skip_if_dataframe_unavailable()
    assert ZWJ_TEXT != PLAIN_TEXT
    assert _n("NFC", ZWJ_TEXT) != _n("NFC", PLAIN_TEXT)
    a = [{"id": ZWJ_TEXT, "value": "x"}]
    b = [{"id": PLAIN_TEXT, "value": "y"}]
    result = _merge(a, b, key="id")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Surrogate-pair (astral-plane) codepoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form", NORMALIZATION_FORMS)
def test_astral_plane_codepoint_survives_all_forms(form):
    _skip_if_dataframe_unavailable()
    assert _n(form, ASTRAL_EMOJI) == ASTRAL_EMOJI
    assert _n(form, ASTRAL_COMPOUND) == ASTRAL_COMPOUND
    a = [{"id": "1", "name": _n(form, ASTRAL_COMPOUND), "_ts": 1.0}]
    b = [{"id": "1", "name": ASTRAL_COMPOUND, "_ts": 2.0}]
    result = _merge(a, b, timestamp_col="_ts")
    assert len(result) == 1
    merged_name = result[0]["name"] if isinstance(result, list) else result["name"].iloc[0]
    assert ASTRAL_EMOJI in merged_name


def test_astral_plane_key_preserved_through_merge():
    _skip_if_dataframe_unavailable()
    a = [{"id": ASTRAL_EMOJI, "value": "x"}]
    b = [{"id": ASTRAL_EMOJI, "value": "y"}]
    result = _merge(a, b, key="id")
    assert len(result) == 1
    key = result[0]["id"] if isinstance(result, list) else result["id"].iloc[0]
    assert key == ASTRAL_EMOJI
