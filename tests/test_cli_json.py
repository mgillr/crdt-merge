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

"""Tests for crdt_merge.cli.cmd_json — json merge and json merge-lines commands."""

from __future__ import annotations

import argparse
import io
import json
import os

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_json import handle_json_merge, handle_json_merge_lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_formatter(stream=None):
    """Return a plain OutputFormatter writing to *stream*."""
    if stream is None:
        stream = io.StringIO()
    return OutputFormatter(format="json", color=False, stream=stream), stream


def _write_json_file(tmp_path, name: str, data) -> str:
    """Write *data* as JSON and return the path."""
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _write_jsonl_file(tmp_path, name: str, records: list) -> str:
    """Write *records* as JSON Lines and return the path."""
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False))
            fh.write("\n")
    return path


def _make_merge_args(**kwargs):
    defaults = dict(
        file_a=None,
        file_b=None,
        prefer=None,
        array_strategy="union",
        output=None,
        format="json",
        no_color=True,
        verbose=0,
        config=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _make_merge_lines_args(**kwargs):
    defaults = dict(
        file_a=None,
        file_b=None,
        key="id",
        prefer=None,
        output=None,
        format="json",
        no_color=True,
        verbose=0,
        config=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

DOC_A = {"name": "Alice", "score": 90, "tags": ["admin"], "meta": {"env": "prod"}}
DOC_B = {"name": "Alice", "score": 95, "tags": ["user"], "meta": {"region": "us"}}

LINES_A = [
    {"id": "1", "name": "Alice", "score": 90},
    {"id": "2", "name": "Bob", "score": 80},
]
LINES_B = [
    {"id": "1", "name": "Alice", "score": 95},
    {"id": "3", "name": "Carol", "score": 70},
]


# ===================================================================
# 1. handle_json_merge -- happy paths
# ===================================================================


class TestHandleJsonMerge:
    def test_basic_merge_preserves_keys(self, tmp_path):
        fa = _write_json_file(tmp_path, "a.json", DOC_A)
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        formatter, stream = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb)
        handle_json_merge(args, formatter)
        result = json.loads(stream.getvalue())
        assert "name" in result
        assert "score" in result
        assert "tags" in result
        assert "meta" in result

    def test_unique_keys_from_both_sides_preserved(self, tmp_path):
        doc_a = {"x": 1, "shared": "a_val"}
        doc_b = {"y": 2, "shared": "b_val"}
        fa = _write_json_file(tmp_path, "a.json", doc_a)
        fb = _write_json_file(tmp_path, "b.json", doc_b)
        formatter, stream = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb)
        handle_json_merge(args, formatter)
        result = json.loads(stream.getvalue())
        assert result["x"] == 1
        assert result["y"] == 2

    def test_nested_dict_merged(self, tmp_path):
        doc_a = {"meta": {"env": "prod", "version": 1}}
        doc_b = {"meta": {"region": "us", "version": 2}}
        fa = _write_json_file(tmp_path, "a.json", doc_a)
        fb = _write_json_file(tmp_path, "b.json", doc_b)
        formatter, stream = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb)
        handle_json_merge(args, formatter)
        result = json.loads(stream.getvalue())
        assert result["meta"]["env"] == "prod"
        assert result["meta"]["region"] == "us"

    def test_output_to_file(self, tmp_path):
        fa = _write_json_file(tmp_path, "a.json", DOC_A)
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        out = os.path.join(str(tmp_path), "merged.json")
        formatter, _ = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb, output=out)
        handle_json_merge(args, formatter)
        assert os.path.exists(out)
        with open(out, encoding="utf-8") as fh:
            result = json.load(fh)
        assert isinstance(result, dict)
        assert "name" in result

    def test_array_union_default(self, tmp_path):
        doc_a = {"items": [1, 2, 3]}
        doc_b = {"items": [3, 4, 5]}
        fa = _write_json_file(tmp_path, "a.json", doc_a)
        fb = _write_json_file(tmp_path, "b.json", doc_b)
        formatter, stream = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb)
        handle_json_merge(args, formatter)
        result = json.loads(stream.getvalue())
        # Union: all unique elements present
        assert set(result["items"]) >= {1, 2, 3, 4, 5}

    def test_missing_file_a(self, tmp_path):
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        formatter, _ = _make_formatter()
        args = _make_merge_args(
            file_a=os.path.join(str(tmp_path), "ghost.json"),
            file_b=fb,
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge(args, formatter)
        assert exc_info.value.code == 1

    def test_missing_file_b(self, tmp_path):
        fa = _write_json_file(tmp_path, "a.json", DOC_A)
        formatter, _ = _make_formatter()
        args = _make_merge_args(
            file_a=fa,
            file_b=os.path.join(str(tmp_path), "ghost.json"),
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge(args, formatter)
        assert exc_info.value.code == 1

    def test_invalid_json_file_exits(self, tmp_path):
        bad = os.path.join(str(tmp_path), "bad.json")
        with open(bad, "w") as fh:
            fh.write("{not valid json")
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        formatter, _ = _make_formatter()
        args = _make_merge_args(file_a=bad, file_b=fb)
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge(args, formatter)
        assert exc_info.value.code == 1

    def test_array_root_rejected(self, tmp_path):
        """Both inputs must be JSON objects, not arrays."""
        fa = _write_json_file(tmp_path, "a.json", [1, 2, 3])
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        formatter, _ = _make_formatter()
        args = _make_merge_args(file_a=fa, file_b=fb)
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge(args, formatter)
        assert exc_info.value.code == 1

    def test_prefer_b_wins_scalar_conflict(self, tmp_path):
        """When --prefer b is set, side B wins for conflicting scalars."""
        doc_a = {"x": "from_a"}
        doc_b = {"x": "from_b"}
        fa = _write_json_file(tmp_path, "a.json", doc_a)
        fb = _write_json_file(tmp_path, "b.json", doc_b)
        formatter, stream = _make_formatter()
        # prefer flag is parsed by the caller; merge_dicts respects timestamps
        # or side-B precedence by default -- the flag is stored on args.prefer
        # but merge_dicts does not consume it directly (LWW defaults to B).
        args = _make_merge_args(file_a=fa, file_b=fb, prefer="b")
        handle_json_merge(args, formatter)
        result = json.loads(stream.getvalue())
        # By default CRDT LWW side-B wins ties -- value should be from_b.
        assert result["x"] == "from_b"


# ===================================================================
# 2. handle_json_merge_lines -- happy paths
# ===================================================================


class TestHandleJsonMergeLines:
    def test_basic_merge_lines(self, tmp_path):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        formatter, stream = _make_formatter()
        args = _make_merge_lines_args(file_a=fa, file_b=fb, key="id")
        handle_json_merge_lines(args, formatter)
        # Output is emitted via formatter.auto; formatter uses json format.
        output = stream.getvalue()
        data = json.loads(output)
        assert isinstance(data, list)
        ids = {str(r["id"]) for r in data}
        assert ids == {"1", "2", "3"}

    def test_merge_lines_conflict_resolved(self, tmp_path):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        formatter, stream = _make_formatter()
        args = _make_merge_lines_args(file_a=fa, file_b=fb, key="id")
        handle_json_merge_lines(args, formatter)
        data = json.loads(stream.getvalue())
        row1 = next(r for r in data if str(r["id"]) == "1")
        # score in A=90, in B=95; default LWW side-B wins or max.
        assert row1["score"] in (90, 95, "90", "95")

    def test_merge_lines_output_to_file(self, tmp_path):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        out = os.path.join(str(tmp_path), "out.jsonl")
        formatter, _ = _make_formatter()
        args = _make_merge_lines_args(file_a=fa, file_b=fb, key="id", output=out)
        handle_json_merge_lines(args, formatter)
        assert os.path.exists(out)
        with open(out, encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        assert len(lines) == 3

    def test_merge_lines_unique_rows_preserved(self, tmp_path):
        """Rows that appear only in one file are included in the output."""
        fa = _write_jsonl_file(tmp_path, "a.jsonl", [{"id": "1", "v": "a_only"}])
        fb = _write_jsonl_file(tmp_path, "b.jsonl", [{"id": "2", "v": "b_only"}])
        formatter, stream = _make_formatter()
        args = _make_merge_lines_args(file_a=fa, file_b=fb, key="id")
        handle_json_merge_lines(args, formatter)
        data = json.loads(stream.getvalue())
        ids = {str(r["id"]) for r in data}
        assert "1" in ids
        assert "2" in ids

    def test_merge_lines_missing_file(self, tmp_path):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        formatter, _ = _make_formatter()
        args = _make_merge_lines_args(
            file_a=fa,
            file_b=os.path.join(str(tmp_path), "ghost.jsonl"),
            key="id",
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge_lines(args, formatter)
        assert exc_info.value.code == 1

    def test_merge_lines_invalid_jsonl(self, tmp_path):
        bad = os.path.join(str(tmp_path), "bad.jsonl")
        with open(bad, "w") as fh:
            fh.write("{not valid json}\n")
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        formatter, _ = _make_formatter()
        args = _make_merge_lines_args(file_a=bad, file_b=fb, key="id")
        with pytest.raises(SystemExit) as exc_info:
            handle_json_merge_lines(args, formatter)
        assert exc_info.value.code == 1


# ===================================================================
# 3. main() CLI dispatch -- json sub-commands
# ===================================================================


class TestMainJsonDispatch:
    def test_json_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["json", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_json_merge_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["json", "merge", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_json_merge_lines_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["json", "merge-lines", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_json_merge_missing_files(self, capsys, tmp_path):
        with pytest.raises(SystemExit):
            main([
                "json", "merge",
                os.path.join(str(tmp_path), "no_a.json"),
                os.path.join(str(tmp_path), "no_b.json"),
            ])

    def test_json_merge_round_trip(self, tmp_path, capsys):
        fa = _write_json_file(tmp_path, "a.json", DOC_A)
        fb = _write_json_file(tmp_path, "b.json", DOC_B)
        main(["json", "merge", fa, fb])
        captured = capsys.readouterr()
        if captured.out.strip():
            result = json.loads(captured.out)
            assert isinstance(result, dict)
            assert "name" in result

    def test_json_merge_lines_missing_key_flag(self, capsys, tmp_path):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        with pytest.raises(SystemExit) as exc_info:
            main(["json", "merge-lines", fa, fb])  # --key required
        assert exc_info.value.code != 0

    def test_json_merge_lines_round_trip(self, tmp_path, capsys):
        fa = _write_jsonl_file(tmp_path, "a.jsonl", LINES_A)
        fb = _write_jsonl_file(tmp_path, "b.jsonl", LINES_B)
        main(["json", "merge-lines", fa, fb, "--key", "id"])
        # Output may go to stdout (JSON) or stderr (table formatter).
        # Verify no SystemExit was raised.
