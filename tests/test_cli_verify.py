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

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""Tests for crdt_merge.cli.cmd_verify — Verify CLI command group."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_verify import (
    CRDT_TYPES,
    _HANDLER_MAP,
    _PROPERTY_NAMES,
    _format_result,
    _resolve_dotted_path,
    handle_all,
    handle_associative,
    handle_commutative,
    handle_convergence,
    handle_idempotent,
    handle_verify_crdt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_formatter(stream=None) -> OutputFormatter:
    """Return a plain JSON formatter writing to *stream* (or a new StringIO)."""
    buf = stream or io.StringIO()
    return OutputFormatter(format="json", color=False, stream=buf)


def _write_json(tmp_path, name: str, data) -> str:
    """Write *data* as JSON and return the file path."""
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as fh:
        json.dump(data, fh)
    return p


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_crdt_types_non_empty(self):
        assert len(CRDT_TYPES) > 0

    def test_crdt_types_expected_entries(self):
        for name in ("gcounter", "pncounter", "lww", "orset", "lwwmap"):
            assert name in CRDT_TYPES

    def test_property_names_all_present(self):
        for name in ("commutative", "associative", "idempotent", "convergence"):
            assert name in _PROPERTY_NAMES

    def test_handler_map_keys(self):
        for key in ("crdt", "commutative", "associative", "idempotent", "convergence", "all"):
            assert key in _HANDLER_MAP


# ---------------------------------------------------------------------------
# _resolve_dotted_path
# ---------------------------------------------------------------------------


class TestResolveDottedPath:
    def test_resolves_builtin_function(self):
        fn = _resolve_dotted_path("os.path.join")
        import os.path
        assert fn is os.path.join

    def test_resolves_class(self):
        cls = _resolve_dotted_path("crdt_merge.core.GCounter")
        from crdt_merge.core import GCounter
        assert cls is GCounter

    def test_invalid_no_dot_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid dotted path"):
            _resolve_dotted_path("nodots")

    def test_missing_module_raises_import_error(self):
        with pytest.raises(ImportError):
            _resolve_dotted_path("nonexistent_module_xyz.func")

    def test_missing_attribute_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            _resolve_dotted_path("os.path.nonexistent_func_xyz")


# ---------------------------------------------------------------------------
# _format_result
# ---------------------------------------------------------------------------


class TestFormatResult:
    def _make_result(self, passed, trials=10, failures=0, message=""):
        """Return a minimal duck-typed result object."""
        class _R:
            property_name = "commutativity"
        r = _R()
        r.passed = passed
        r.trials = trials
        r.failures = failures
        r.message = message
        return r

    def test_pass_writes_to_stderr(self, capsys):
        fmt = _make_formatter()
        _format_result(self._make_result(passed=True, trials=50), fmt)
        captured = capsys.readouterr()
        assert "PASS" in captured.err

    def test_fail_writes_to_stderr(self, capsys):
        fmt = _make_formatter()
        _format_result(self._make_result(passed=False, trials=50, failures=3), fmt)
        captured = capsys.readouterr()
        assert "FAIL" in captured.err

    def test_fail_with_message_shows_detail(self, capsys):
        fmt = _make_formatter()
        _format_result(self._make_result(passed=False, message="counterexample found"), fmt)
        captured = capsys.readouterr()
        assert "counterexample found" in captured.err

    def test_unknown_result_shape_falls_back(self, capsys):
        fmt = _make_formatter()
        _format_result("raw string result", fmt)
        captured = capsys.readouterr()
        assert "raw string result" in captured.err


# ---------------------------------------------------------------------------
# handle_verify_crdt -- built-in CRDT types
# ---------------------------------------------------------------------------


class TestHandleVerifyCrdt:
    def _args(self, crdt_type: str, trials: int = 10) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.crdt_type = crdt_type
        ns.trials = trials
        ns.verbose = False
        return ns

    @pytest.mark.parametrize("crdt_type", list(CRDT_TYPES))
    def test_all_builtin_types_pass(self, crdt_type, capsys):
        fmt = _make_formatter()
        handle_verify_crdt(self._args(crdt_type, trials=20), fmt)
        captured = capsys.readouterr()
        assert "PASS" in captured.err

    def test_unknown_crdt_type_exits_1(self, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_verify_crdt(self._args("unknown_crdt_xyz"), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Property handlers via data file
# ---------------------------------------------------------------------------


class TestPropertyHandlers:
    """Tests for commutative / associative / idempotent / convergence handlers."""

    def _write_data(self, tmp_path, name="data.json"):
        records = [{"id": i, "val": i * 2} for i in range(5)]
        return _write_json(tmp_path, name, records)

    def _args(self, data_path: str, merge_fn: str, trials: int = 10) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.data = data_path
        ns.merge_fn = merge_fn
        ns.trials = trials
        ns.verbose = False
        return ns

    def test_commutative_runs_and_reports_result(self, tmp_path, capsys):
        """The commutative handler should run and write a PASS/FAIL verdict."""
        data = self._write_data(tmp_path)
        fmt = _make_formatter()
        # The merge fn may pass or fail; either way the handler must not crash
        # with an unexpected exception -- only a possible SystemExit(1) on FAIL.
        try:
            handle_commutative(
                self._args(data, "crdt_merge.strategies.LWW"),
                fmt,
            )
        except SystemExit as exc:
            assert exc.code == 1  # failed verification is the only allowed exit
        captured = capsys.readouterr()
        assert "PASS" in captured.err or "FAIL" in captured.err

    def test_associative_bad_merge_fn_exits(self, tmp_path, capsys):
        data = self._write_data(tmp_path)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_associative(
                self._args(data, "nonexistent_module_xyz.merge_fn"),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_missing_data_file_exits_1(self, capsys):
        fmt = _make_formatter()
        ns = argparse.Namespace(
            data="/nonexistent/path/data.json",
            merge_fn="crdt_merge.strategies.LWW",
            trials=10,
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_idempotent(ns, fmt)
        assert exc_info.value.code == 1

    def test_bad_dotted_path_exits_1(self, tmp_path, capsys):
        data = self._write_data(tmp_path)
        fmt = _make_formatter()
        ns = argparse.Namespace(data=data, merge_fn="nodots", trials=5)
        with pytest.raises(SystemExit) as exc_info:
            handle_convergence(ns, fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI integration -- main() and --help
# ---------------------------------------------------------------------------


class TestVerifyCLI:
    def test_verify_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["verify", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "verify" in captured.out.lower()

    def test_verify_crdt_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["verify", "crdt", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_verify_crdt_gcounter_via_main(self, capsys):
        # When all properties pass, main() returns normally (no SystemExit).
        # When they fail it exits with code 1.  Either outcome is acceptable;
        # we only require no unexpected exception.
        try:
            main(["verify", "crdt", "gcounter", "--trials", "5"])
        except SystemExit as exc:
            assert exc.code in (0, 1)

    def test_verify_commutative_missing_required_args_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["verify", "commutative"])
        assert exc_info.value.code != 0

    def test_verify_crdt_invalid_type_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["verify", "crdt", "badtype"])
        assert exc_info.value.code != 0
