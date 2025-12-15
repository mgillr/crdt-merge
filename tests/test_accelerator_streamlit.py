# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.accelerators.streamlit_ui — Streamlit visual merge UI.

Streamlit is mocked throughout so tests run without ``pip install streamlit``.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock streamlit before importing the module under test
# ---------------------------------------------------------------------------

_mock_st = MagicMock()
_mock_st.__version__ = "1.35.0"
_mock_st.columns.return_value = (MagicMock(), MagicMock())
_mock_st.columns.return_value[0].__enter__ = MagicMock(return_value=None)
_mock_st.columns.return_value[0].__exit__ = MagicMock(return_value=False)
_mock_st.columns.return_value[1].__enter__ = MagicMock(return_value=None)
_mock_st.columns.return_value[1].__exit__ = MagicMock(return_value=False)
_mock_st.selectbox.return_value = "lww"
_mock_st.button.return_value = False


sys.modules["streamlit"] = _mock_st  # type: ignore[assignment]

from crdt_merge.accelerators.streamlit_ui import (
    StreamlitMergeUI,
    _to_records,
    _detect_conflicts,
    _resolve_merge,
)
from crdt_merge.strategies import MergeSchema, LWW, MaxWins


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _left_data():
    return [
        {"id": 1, "name": "Alice", "salary": 100},
        {"id": 2, "name": "Bob", "salary": 200},
    ]

def _right_data():
    return [
        {"id": 1, "name": "Alicia", "salary": 120},
        {"id": 3, "name": "Charlie", "salary": 300},
    ]


# ---------------------------------------------------------------------------
# Tests (20)
# ---------------------------------------------------------------------------

class TestStreamlitMergeUI:
    def test_create_default(self):
        ui = StreamlitMergeUI()
        assert ui.name == "streamlit_ui"
        assert ui.version == "0.7.0"

    def test_create_with_schema(self):
        schema = MergeSchema(default=LWW(), salary=MaxWins())
        ui = StreamlitMergeUI(schema=schema, title="My Merge")
        assert repr(ui) == "StreamlitMergeUI(title='My Merge')"

    def test_health_check_available(self):
        ui = StreamlitMergeUI()
        hc = ui.health_check()
        assert hc["streamlit_available"] is True
        assert hc["status"] == "ok"

    def test_is_available(self):
        ui = StreamlitMergeUI()
        assert ui.is_available() is True

    def test_to_records_list(self):
        data = [{"a": 1}]
        assert _to_records(data) == data

    def test_to_records_unsupported_type(self):
        with pytest.raises(TypeError):
            _to_records(42)

    def test_detect_conflicts(self):
        conflicts, cols = _detect_conflicts(_left_data(), _right_data(), "id")
        assert len(conflicts) == 2  # name + salary for id=1
        fields = {c["field"] for c in conflicts}
        assert "name" in fields
        assert "salary" in fields

    def test_detect_conflicts_no_overlap(self):
        left = [{"id": 1, "x": 1}]
        right = [{"id": 2, "x": 2}]
        conflicts, _ = _detect_conflicts(left, right, "id")
        assert len(conflicts) == 0

    def test_resolve_merge_basic(self):
        schema = MergeSchema()
        merged = _resolve_merge(_left_data(), _right_data(), "id", schema)
        keys = [r["id"] for r in merged]
        assert set(keys) == {1, 2, 3}

    def test_resolve_merge_with_max(self):
        schema = MergeSchema(salary=MaxWins())
        merged = _resolve_merge(_left_data(), _right_data(), "id", schema)
        r1 = next(r for r in merged if r["id"] == 1)
        assert r1["salary"] == 120  # max(100, 120)

    def test_render_no_merge(self):
        """render returns None when button is not clicked."""
        _mock_st.button.return_value = False
        ui = StreamlitMergeUI()
        result = ui.render(_left_data(), _right_data(), key="id")
        assert result is None

    def test_render_with_merge(self):
        """render returns merged data when button is clicked."""
        _mock_st.button.return_value = True
        ui = StreamlitMergeUI()
        result = ui.render(_left_data(), _right_data(), key="id")
        assert result is not None
        assert len(result) == 3
        _mock_st.button.return_value = False  # reset

    def test_render_with_strategies(self):
        _mock_st.button.return_value = True
        ui = StreamlitMergeUI()
        result = ui.render(_left_data(), _right_data(), key="id",
                           strategies={"salary": "max"})
        assert result is not None
        r1 = next(r for r in result if r["id"] == 1)
        assert r1["salary"] == 120
        _mock_st.button.return_value = False

    def test_render_conflicts_display(self):
        ui = StreamlitMergeUI()
        conflicts = [{"key": 1, "field": "name", "left_value": "A", "right_value": "B"}]
        ui.render_conflicts(conflicts)
        _mock_st.markdown.assert_called()

    def test_render_provenance(self):
        ui = StreamlitMergeUI()
        prov = [{"key": 1, "decisions": [{"field": "name", "source": "a", "value": "A"}]}]
        ui.render_provenance(prov)
        _mock_st.subheader.assert_called()

    def test_export_parquet_csv_fallback(self):
        """Without pyarrow, falls back to CSV download."""
        with patch.dict(sys.modules, {"pyarrow": None}):
            ui = StreamlitMergeUI()
            ui.export_parquet([{"id": 1, "name": "Alice"}])
            # Should attempt to create a download button
            _mock_st.download_button.assert_called()

    def test_registered_in_registry(self):
        from crdt_merge.accelerators import ACCELERATOR_REGISTRY
        assert "streamlit_ui" in ACCELERATOR_REGISTRY

    def test_columns_display(self):
        """Verify side-by-side columns are created."""
        _mock_st.button.return_value = False
        ui = StreamlitMergeUI()
        ui.render(_left_data(), _right_data(), key="id")
        _mock_st.columns.assert_called()

    def test_header_title(self):
        _mock_st.button.return_value = False
        ui = StreamlitMergeUI(title="Test Title")
        ui.render(_left_data(), _right_data(), key="id")
        _mock_st.header.assert_called_with("Test Title")

    def test_resolve_merge_unique_rows(self):
        schema = MergeSchema()
        merged = _resolve_merge(_left_data(), _right_data(), "id", schema)
        # id=2 only in left, id=3 only in right
        r2 = next(r for r in merged if r["id"] == 2)
        assert r2["name"] == "Bob"
        r3 = next(r for r in merged if r["id"] == 3)
        assert r3["name"] == "Charlie"
