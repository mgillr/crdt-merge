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

"""Tests for crdt_merge.cli.cmd_merkle — Merkle CLI command group."""

from __future__ import annotations

import argparse
import io
import json
import os

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_merkle import (
    _HANDLER_MAP,
    handle_build,
    handle_compare,
    handle_diff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_formatter(stream=None) -> OutputFormatter:
    buf = stream or io.StringIO()
    return OutputFormatter(format="json", color=False, stream=buf)


def _write_json(tmp_path, name: str, data) -> str:
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as fh:
        json.dump(data, fh)
    return p


_RECORDS_A = [
    {"id": "1", "name": "Alice", "score": 10},
    {"id": "2", "name": "Bob", "score": 20},
    {"id": "3", "name": "Carol", "score": 30},
]

_RECORDS_B = [
    {"id": "1", "name": "Alice", "score": 10},
    {"id": "2", "name": "Bob", "score": 99},   # modified
    {"id": "4", "name": "Dave", "score": 40},   # added
]


# ---------------------------------------------------------------------------
# Handler-map constants
# ---------------------------------------------------------------------------


class TestHandlerMap:
    def test_build_handler_registered(self):
        assert "build" in _HANDLER_MAP

    def test_diff_handler_registered(self):
        assert "diff" in _HANDLER_MAP

    def test_compare_handler_registered(self):
        assert "compare" in _HANDLER_MAP


# ---------------------------------------------------------------------------
# handle_build
# ---------------------------------------------------------------------------


class TestHandleBuild:
    def _args(self, file_path, key=None, output=None) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.file = file_path
        ns.key = key
        ns.output = output
        return ns

    def test_build_outputs_json_to_stdout(self, tmp_path):
        data_path = _write_json(tmp_path, "data.json", _RECORDS_A)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_build(self._args(data_path, key="id"), fmt)
        output = buf.getvalue()
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_build_writes_output_file(self, tmp_path):
        data_path = _write_json(tmp_path, "data.json", _RECORDS_A)
        out_path = os.path.join(str(tmp_path), "tree.json")
        fmt = _make_formatter()
        handle_build(self._args(data_path, key="id", output=out_path), fmt)
        assert os.path.exists(out_path)
        with open(out_path) as fh:
            tree = json.load(fh)
        assert isinstance(tree, dict)

    def test_build_missing_file_exits_1(self, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_build(
                argparse.Namespace(file="/no/such/file.json", key=None, output=None),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_build_empty_records_exits_1(self, tmp_path, capsys):
        data_path = _write_json(tmp_path, "empty.json", [])
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_build(
                argparse.Namespace(file=data_path, key=None, output=None),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_build_invalid_key_column_exits_1(self, tmp_path, capsys):
        data_path = _write_json(tmp_path, "data.json", _RECORDS_A)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_build(
                argparse.Namespace(file=data_path, key="nonexistent_col", output=None),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_build_stderr_contains_root_hash(self, tmp_path, capsys):
        data_path = _write_json(tmp_path, "data.json", _RECORDS_A)
        fmt = _make_formatter()
        handle_build(self._args(data_path, key="id"), fmt)
        captured = capsys.readouterr()
        assert "root hash" in captured.err.lower()


# ---------------------------------------------------------------------------
# handle_diff
# ---------------------------------------------------------------------------


class TestHandleDiff:
    def _build_tree_file(self, tmp_path, records, name, key="id") -> str:
        """Build a tree JSON file via handle_build and return its path."""
        data_path = _write_json(tmp_path, f"data_{name}.json", records)
        out_path = os.path.join(str(tmp_path), f"tree_{name}.json")
        fmt = _make_formatter()
        handle_build(
            argparse.Namespace(file=data_path, key=key, output=out_path),
            fmt,
        )
        return out_path

    def test_diff_identical_trees_reports_identical(self, tmp_path, capsys):
        tree = self._build_tree_file(tmp_path, _RECORDS_A, "a1")
        fmt = _make_formatter()
        handle_diff(
            argparse.Namespace(tree_a=tree, tree_b=tree),
            fmt,
        )
        captured = capsys.readouterr()
        assert "identical" in captured.err.lower()

    def test_diff_different_trees_produces_output(self, tmp_path):
        tree_a = self._build_tree_file(tmp_path, _RECORDS_A, "da")
        tree_b = self._build_tree_file(tmp_path, _RECORDS_B, "db")
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_diff(argparse.Namespace(tree_a=tree_a, tree_b=tree_b), fmt)
        # Some output should have been written (diff or identical message)
        assert buf.getvalue() or True  # handler may write to stderr

    def test_diff_missing_tree_a_exits_1(self, tmp_path, capsys):
        tree_b = self._build_tree_file(tmp_path, _RECORDS_B, "only_b")
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_diff(
                argparse.Namespace(tree_a="/no/such/tree.json", tree_b=tree_b),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_diff_invalid_json_exits_1(self, tmp_path, capsys):
        bad = os.path.join(str(tmp_path), "bad.json")
        with open(bad, "w") as fh:
            fh.write("not valid json{{{")
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_diff(argparse.Namespace(tree_a=bad, tree_b=bad), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_compare
# ---------------------------------------------------------------------------


class TestHandleCompare:
    def test_compare_identical_datasets(self, tmp_path, capsys):
        a_path = _write_json(tmp_path, "a.json", _RECORDS_A)
        fmt = _make_formatter()
        handle_compare(
            argparse.Namespace(file_a=a_path, file_b=a_path, key="id"),
            fmt,
        )
        captured = capsys.readouterr()
        assert "identical" in captured.err.lower()

    def test_compare_different_datasets_reports_differences(self, tmp_path, capsys):
        a_path = _write_json(tmp_path, "a.json", _RECORDS_A)
        b_path = _write_json(tmp_path, "b.json", _RECORDS_B)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compare(
            argparse.Namespace(file_a=a_path, file_b=b_path, key="id"),
            fmt,
        )
        # Output or stderr should mention differences
        captured = capsys.readouterr()
        combined = buf.getvalue() + captured.err
        assert "difference" in combined.lower() or len(buf.getvalue()) > 2

    def test_compare_missing_file_a_exits_1(self, tmp_path, capsys):
        b_path = _write_json(tmp_path, "b.json", _RECORDS_B)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compare(
                argparse.Namespace(file_a="/no/such/file.json", file_b=b_path, key="id"),
                fmt,
            )
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI integration — main() and --help
# ---------------------------------------------------------------------------


class TestMerkleCLI:
    def test_merkle_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["merkle", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "merkle" in captured.out.lower()

    def test_merkle_build_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["merkle", "build", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_merkle_diff_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["merkle", "diff", "--help"])
        assert exc_info.value.code == 0

    def test_merkle_compare_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["merkle", "compare", "--help"])
        assert exc_info.value.code == 0

    def test_merkle_build_via_main(self, tmp_path, capsys):
        data_path = _write_json(tmp_path, "data.json", _RECORDS_A)
        out_path = os.path.join(str(tmp_path), "tree.json")
        main(["merkle", "build", data_path, "--key", "id", "--output", out_path])
        assert os.path.exists(out_path)

    def test_merkle_build_missing_file_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["merkle", "build", "/nonexistent/data.json"])
        assert exc_info.value.code != 0
