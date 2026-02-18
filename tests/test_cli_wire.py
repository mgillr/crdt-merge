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

"""Tests for crdt_merge.cli.cmd_wire — Wire CLI command group."""

from __future__ import annotations

import argparse
import io
import json
import os

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_wire import (
    WIRE_CRDT_TYPES,
    _CRDT_CLASS_MAP,
    _HANDLER_MAP,
    handle_deserialize,
    handle_inspect,
    handle_serialize,
    handle_size,
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


def _serialize_generic(tmp_path, data: dict, compress: bool = False) -> str:
    """Serialise *data* as the 'generic' type and return the .crdt path."""
    json_path = _write_json(tmp_path, "payload.json", data)
    out_path = os.path.join(str(tmp_path), "payload.crdt")
    fmt = _make_formatter()
    handle_serialize(
        argparse.Namespace(
            file=json_path,
            type="generic",
            output=out_path,
            compress=compress,
        ),
        fmt,
    )
    return out_path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestWireConstants:
    def test_wire_crdt_types_non_empty(self):
        assert len(WIRE_CRDT_TYPES) > 0

    def test_generic_type_present(self):
        assert "generic" in WIRE_CRDT_TYPES

    def test_crdt_class_map_keys(self):
        for name in ("gcounter", "pncounter", "lww", "orset", "lwwmap"):
            assert name in _CRDT_CLASS_MAP

    def test_handler_map_all_subcommands(self):
        for key in ("serialize", "deserialize", "inspect", "size"):
            assert key in _HANDLER_MAP


# ---------------------------------------------------------------------------
# handle_serialize
# ---------------------------------------------------------------------------


class TestHandleSerialize:
    def test_serialize_generic_creates_file(self, tmp_path, capsys):
        out = _serialize_generic(tmp_path, {"key": "value"})
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_serialize_generic_success_message(self, tmp_path, capsys):
        json_path = _write_json(tmp_path, "d.json", {"x": 1})
        out_path = os.path.join(str(tmp_path), "d.crdt")
        fmt = _make_formatter()
        handle_serialize(
            argparse.Namespace(file=json_path, type="generic", output=out_path, compress=False),
            fmt,
        )
        captured = capsys.readouterr()
        assert "bytes" in captured.err.lower() or out_path in captured.err

    def test_serialize_with_compression(self, tmp_path, capsys):
        json_path = _write_json(tmp_path, "comp.json", {"data": "x" * 200})
        out_path = os.path.join(str(tmp_path), "comp.crdt")
        fmt = _make_formatter()
        handle_serialize(
            argparse.Namespace(file=json_path, type="generic", output=out_path, compress=True),
            fmt,
        )
        assert os.path.exists(out_path)
        captured = capsys.readouterr()
        assert "compress" in captured.err.lower()

    def test_serialize_missing_input_exits_1(self, tmp_path, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_serialize(
                argparse.Namespace(
                    file="/no/such/file.json",
                    type="generic",
                    output=None,
                    compress=False,
                ),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_serialize_invalid_json_exits_1(self, tmp_path, capsys):
        bad = os.path.join(str(tmp_path), "bad.json")
        with open(bad, "w") as fh:
            fh.write("not-json{{{")
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_serialize(
                argparse.Namespace(file=bad, type="generic", output=None, compress=False),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_serialize_default_output_name(self, tmp_path, capsys):
        """When no --output given, default path is <input-stem>.crdt."""
        json_path = _write_json(tmp_path, "state.json", {"v": 1})
        expected = os.path.join(str(tmp_path), "state.crdt")
        fmt = _make_formatter()
        handle_serialize(
            argparse.Namespace(file=json_path, type="generic", output=None, compress=False),
            fmt,
        )
        assert os.path.exists(expected)


# ---------------------------------------------------------------------------
# handle_deserialize
# ---------------------------------------------------------------------------


class TestHandleDeserialize:
    def test_deserialize_roundtrip_to_stdout(self, tmp_path):
        payload = {"hello": "world", "count": 42}
        crdt_path = _serialize_generic(tmp_path, payload)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_deserialize(
            argparse.Namespace(file=crdt_path, output=None),
            fmt,
        )
        result = json.loads(buf.getvalue())
        assert isinstance(result, (dict, list))

    def test_deserialize_writes_output_file(self, tmp_path, capsys):
        crdt_path = _serialize_generic(tmp_path, {"k": "v"})
        out_path = os.path.join(str(tmp_path), "out.json")
        fmt = _make_formatter()
        handle_deserialize(
            argparse.Namespace(file=crdt_path, output=out_path),
            fmt,
        )
        assert os.path.exists(out_path)
        captured = capsys.readouterr()
        assert out_path in captured.err

    def test_deserialize_missing_file_exits_1(self, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_deserialize(
                argparse.Namespace(file="/no/such/file.crdt", output=None),
                fmt,
            )
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_inspect
# ---------------------------------------------------------------------------


class TestHandleInspect:
    def test_inspect_valid_wire_file(self, tmp_path):
        crdt_path = _serialize_generic(tmp_path, {"type": "test"})
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_inspect(argparse.Namespace(file=crdt_path), fmt)
        output = buf.getvalue()
        assert len(output) > 0

    def test_inspect_missing_file_exits_1(self, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_inspect(argparse.Namespace(file="/no/such/file.crdt"), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_size
# ---------------------------------------------------------------------------


class TestHandleSize:
    def test_size_returns_byte_count(self, tmp_path):
        crdt_path = _serialize_generic(tmp_path, {"data": "x" * 100})
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_size(argparse.Namespace(file=crdt_path), fmt)
        output = buf.getvalue()
        assert len(output) > 0
        parsed = json.loads(output)
        # Result is a list of dicts (auto mode) or a dict
        info = parsed[0] if isinstance(parsed, list) else parsed
        assert "file_size_bytes" in info or "total_bytes" in info

    def test_size_missing_file_exits_1(self, capsys):
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_size(argparse.Namespace(file="/no/such/file.crdt"), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI integration — main() and --help
# ---------------------------------------------------------------------------


class TestWireCLI:
    def test_wire_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "wire" in captured.out.lower()

    def test_wire_serialize_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "serialize", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_wire_deserialize_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "deserialize", "--help"])
        assert exc_info.value.code == 0

    def test_wire_inspect_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "inspect", "--help"])
        assert exc_info.value.code == 0

    def test_wire_size_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "size", "--help"])
        assert exc_info.value.code == 0

    def test_wire_serialize_missing_type_exits_nonzero(self, tmp_path, capsys):
        json_path = _write_json(tmp_path, "d.json", {"x": 1})
        with pytest.raises(SystemExit) as exc_info:
            main(["wire", "serialize", json_path])  # --type is required
        assert exc_info.value.code != 0

    def test_wire_serialize_via_main(self, tmp_path, capsys):
        json_path = _write_json(tmp_path, "wire_test.json", {"val": 7})
        out_path = os.path.join(str(tmp_path), "wire_test.crdt")
        main(["wire", "serialize", json_path, "--type", "generic", "--output", out_path])
        assert os.path.exists(out_path)
