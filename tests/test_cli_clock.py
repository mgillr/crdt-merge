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

"""Tests for crdt_merge.cli.cmd_clock — distributed clock CLI commands."""

from __future__ import annotations

import io
import json
import os
import types

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_clock import (
    CLOCK_TYPES,
    _instantiate_clock,
    _load_clock_file,
    _write_json,
    handle_compare,
    handle_create,
    handle_merge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter(stream: io.StringIO | None = None) -> OutputFormatter:
    """Return a plain JSON formatter writing to an in-memory buffer."""
    return OutputFormatter(format="json", color=False, stream=stream or io.StringIO())


def _write_clock_json(tmp_path, name: str, data: dict) -> str:
    """Write a clock dict to a JSON file and return its path."""
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as f:
        json.dump(data, f)
    return p


def _vectorclock_dict(node: str = "n1", count: int = 1) -> dict:
    return {"type": "vector_clock", "clocks": {node: count}}


def _dvv_dict(node: str = "n1") -> dict:
    # Matches the shape produced by DottedVersionVector.to_dict():
    # dot is serialized as a two-element list [node_id, counter].
    return {
        "type": "dotted_version_vector",
        "base": {"type": "vector_clock", "clocks": {node: 1}},
        "dot": [node, 1],
    }


def _make_args(**kwargs) -> types.SimpleNamespace:
    return types.SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# 1. CLOCK_TYPES constant
# ---------------------------------------------------------------------------

class TestClockTypes:
    def test_contains_vectorclock(self):
        assert "vectorclock" in CLOCK_TYPES

    def test_contains_dvv(self):
        assert "dvv" in CLOCK_TYPES

    def test_exactly_two_types(self):
        assert len(CLOCK_TYPES) == 2


# ---------------------------------------------------------------------------
# 2. _write_json helper
# ---------------------------------------------------------------------------

class TestWriteJson:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "out.json"
        _write_json({"hello": "world"}, path)
        assert path.exists()

    def test_content_is_valid_json(self, tmp_path):
        path = tmp_path / "data.json"
        payload = {"type": "vector_clock", "clocks": {"a": 1}}
        _write_json(payload, path)
        loaded = json.loads(path.read_text())
        assert loaded == payload

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "clock.json"
        _write_json({"x": 1}, path)
        assert path.exists()

    def test_trailing_newline(self, tmp_path):
        path = tmp_path / "nl.json"
        _write_json({"k": "v"}, path)
        assert path.read_text().endswith("\n")


# ---------------------------------------------------------------------------
# 3. _load_clock_file helper
# ---------------------------------------------------------------------------

class TestLoadClockFile:
    def test_loads_valid_json(self, tmp_path):
        p = _write_clock_json(tmp_path, "vc.json", _vectorclock_dict())
        data = _load_clock_file(p)
        assert data["type"] == "vector_clock"

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            _load_clock_file(str(tmp_path / "nonexistent.json"))
        assert exc_info.value.code == 1

    def test_invalid_json_exits(self, tmp_path):
        p = str(tmp_path / "bad.json")
        with open(p, "w") as f:
            f.write("not valid json {{{")
        with pytest.raises(SystemExit) as exc_info:
            _load_clock_file(p)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 4. _instantiate_clock helper
# ---------------------------------------------------------------------------

class TestInstantiateClock:
    def test_instantiates_vectorclock(self):
        from crdt_merge.clocks import VectorClock
        clock = _instantiate_clock(_vectorclock_dict("node1"))
        assert isinstance(clock, VectorClock)

    def test_instantiates_dvv(self):
        from crdt_merge.clocks import DottedVersionVector
        # _instantiate_clock dispatches on data["type"] == "dvv" (the CLI tag),
        # not the serialized "dotted_version_vector" type string.
        data = _dvv_dict("node1")
        data["type"] = "dvv"
        clock = _instantiate_clock(data)
        assert isinstance(clock, DottedVersionVector)

    def test_defaults_to_vectorclock_when_no_type(self):
        from crdt_merge.clocks import VectorClock
        # dict without a "type" key falls back to VectorClock
        clock = _instantiate_clock({"clocks": {"a": 1}})
        assert isinstance(clock, VectorClock)


# ---------------------------------------------------------------------------
# 5. handle_create
# ---------------------------------------------------------------------------

class TestHandleCreate:
    def test_create_vectorclock(self, tmp_path):
        out = str(tmp_path / "vc.json")
        args = _make_args(type="vectorclock", node="node-1", output=out)
        handle_create(args, _make_formatter())
        assert os.path.exists(out)
        data = json.loads(open(out).read())
        assert data["clocks"]["node-1"] == 1

    def test_create_dvv(self, tmp_path):
        out = str(tmp_path / "dvv.json")
        args = _make_args(type="dvv", node="node-2", output=out)
        handle_create(args, _make_formatter())
        assert os.path.exists(out)
        data = json.loads(open(out).read())
        assert data["type"] == "dotted_version_vector"

    def test_create_invalid_type_exits(self, tmp_path):
        out = str(tmp_path / "bad.json")
        args = _make_args(type="lamportclock", node="n1", output=out)
        with pytest.raises(SystemExit) as exc_info:
            handle_create(args, _make_formatter())
        assert exc_info.value.code == 1

    def test_create_success_message_written(self, tmp_path, capsys):
        out = str(tmp_path / "vc2.json")
        args = _make_args(type="vectorclock", node="alpha", output=out)
        handle_create(args, _make_formatter())
        captured = capsys.readouterr()
        assert "alpha" in captured.err


# ---------------------------------------------------------------------------
# 6. handle_merge
# ---------------------------------------------------------------------------

class TestHandleMerge:
    def test_merge_two_vectorclocks(self, tmp_path):
        a = _write_clock_json(tmp_path, "a.json", _vectorclock_dict("n1", 2))
        b = _write_clock_json(tmp_path, "b.json", _vectorclock_dict("n2", 3))
        buf = io.StringIO()
        args = _make_args(clock_a=a, clock_b=b)
        handle_merge(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        # Merged clock should contain both nodes
        assert result["clocks"]["n1"] == 2
        assert result["clocks"]["n2"] == 3

    def test_merge_identical_clocks(self, tmp_path):
        data = _vectorclock_dict("n1", 5)
        a = _write_clock_json(tmp_path, "a.json", data)
        b = _write_clock_json(tmp_path, "b.json", data)
        buf = io.StringIO()
        args = _make_args(clock_a=a, clock_b=b)
        handle_merge(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        assert result["clocks"]["n1"] == 5

    def test_merge_missing_file_exits(self, tmp_path):
        a = _write_clock_json(tmp_path, "a.json", _vectorclock_dict())
        args = _make_args(clock_a=a, clock_b=str(tmp_path / "missing.json"))
        with pytest.raises(SystemExit) as exc_info:
            handle_merge(args, _make_formatter())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 7. handle_compare
# ---------------------------------------------------------------------------

class TestHandleCompare:
    def test_compare_concurrent_clocks(self, tmp_path, capsys):
        a = _write_clock_json(tmp_path, "a.json", _vectorclock_dict("n1"))
        b = _write_clock_json(tmp_path, "b.json", _vectorclock_dict("n2"))
        args = _make_args(clock_a=a, clock_b=b)
        handle_compare(args, _make_formatter())
        captured = capsys.readouterr()
        assert "CONCURRENT" in captured.err

    def test_compare_equal_clocks(self, tmp_path, capsys):
        data = _vectorclock_dict("n1", 1)
        a = _write_clock_json(tmp_path, "a.json", data)
        b = _write_clock_json(tmp_path, "b.json", data)
        args = _make_args(clock_a=a, clock_b=b)
        handle_compare(args, _make_formatter())
        captured = capsys.readouterr()
        assert "EQUAL" in captured.err

    def test_compare_missing_file_exits(self, tmp_path):
        a = _write_clock_json(tmp_path, "a.json", _vectorclock_dict())
        args = _make_args(clock_a=a, clock_b=str(tmp_path / "missing.json"))
        with pytest.raises(SystemExit) as exc_info:
            handle_compare(args, _make_formatter())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 8. CLI integration via main()
# ---------------------------------------------------------------------------

class TestCLIMain:
    def test_clock_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["clock", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "clock" in captured.out.lower()

    def test_clock_create_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["clock", "create", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--node" in captured.out

    def test_clock_merge_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["clock", "merge", "--help"])
        assert exc_info.value.code == 0

    def test_clock_compare_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["clock", "compare", "--help"])
        assert exc_info.value.code == 0

    def test_clock_create_via_main(self, tmp_path, capsys):
        out = str(tmp_path / "main_vc.json")
        # main() returns normally (no SystemExit) on success
        main(["clock", "create", "vectorclock", "--node", "x", "--output", out])
        assert os.path.exists(out)
        data = json.loads(open(out).read())
        assert data["clocks"]["x"] == 1

    def test_clock_create_missing_node_arg(self, tmp_path, capsys):
        out = str(tmp_path / "missing_node.json")
        with pytest.raises(SystemExit) as exc_info:
            main(["clock", "create", "vectorclock", "--output", out])
        # argparse required-arg error exits non-zero
        assert exc_info.value.code != 0
