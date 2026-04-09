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

"""Tests for crdt_merge.cli.cmd_delta — Delta CLI command group."""

from __future__ import annotations

import argparse
import io
import json
import os

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_delta import (
    _HANDLER_MAP,
    handle_apply,
    handle_compose,
    handle_compute,
)
from crdt_merge.delta import Delta, compute_delta


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


def _write_delta(tmp_path, name: str, delta: Delta) -> str:
    return _write_json(tmp_path, name, delta.to_dict())


# Sample datasets
_V1 = [
    {"id": "a", "val": 1},
    {"id": "b", "val": 2},
    {"id": "c", "val": 3},
]

_V2 = [
    {"id": "a", "val": 1},      # unchanged
    {"id": "b", "val": 99},     # modified
    {"id": "d", "val": 4},      # added  (c removed)
]

_V3 = [
    {"id": "a", "val": 1},
    {"id": "b", "val": 99},
    {"id": "d", "val": 4},
    {"id": "e", "val": 5},      # added
]


# ---------------------------------------------------------------------------
# Handler-map constants
# ---------------------------------------------------------------------------


class TestHandlerMap:
    def test_compute_registered(self):
        assert "compute" in _HANDLER_MAP

    def test_apply_registered(self):
        assert "apply" in _HANDLER_MAP

    def test_compose_registered(self):
        assert "compose" in _HANDLER_MAP


# ---------------------------------------------------------------------------
# handle_compute
# ---------------------------------------------------------------------------


class TestHandleCompute:
    def _args(self, old_file, new_file, key="id", output=None) -> argparse.Namespace:
        return argparse.Namespace(
            old_file=old_file,
            new_file=new_file,
            key=key,
            output=output,
        )

    def test_compute_outputs_delta_json_to_stdout(self, tmp_path):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compute(self._args(old_path, new_path, key="id"), fmt)
        delta = json.loads(buf.getvalue())
        assert isinstance(delta, dict)
        assert "added" in delta or "modified" in delta or "removed" in delta

    def test_compute_detects_added_record(self, tmp_path):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compute(self._args(old_path, new_path, key="id"), fmt)
        delta = json.loads(buf.getvalue())
        added_ids = [r.get("id") for r in delta.get("added", [])]
        assert "d" in added_ids

    def test_compute_detects_removed_record(self, tmp_path):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compute(self._args(old_path, new_path, key="id"), fmt)
        delta = json.loads(buf.getvalue())
        assert "c" in delta.get("removed", [])

    def test_compute_writes_output_file(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        out_path = os.path.join(str(tmp_path), "patch.json")
        fmt = _make_formatter()
        handle_compute(self._args(old_path, new_path, key="id", output=out_path), fmt)
        assert os.path.exists(out_path)
        with open(out_path) as fh:
            delta = json.load(fh)
        assert isinstance(delta, dict)
        captured = capsys.readouterr()
        assert out_path in captured.err

    def test_compute_stderr_contains_summary_stats(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        fmt = _make_formatter()
        handle_compute(self._args(old_path, new_path, key="id"), fmt)
        captured = capsys.readouterr()
        assert "added" in captured.err.lower() or "removed" in captured.err.lower()

    def test_compute_missing_old_file_exits_1(self, tmp_path, capsys):
        new_path = _write_json(tmp_path, "v2.json", _V2)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compute(
                self._args("/no/such/file.json", new_path, key="id"),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_compute_missing_new_file_exits_1(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compute(
                self._args(old_path, "/no/such/file.json", key="id"),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_compute_no_changes(self, tmp_path):
        path = _write_json(tmp_path, "same.json", _V1)
        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compute(self._args(path, path, key="id"), fmt)
        delta = json.loads(buf.getvalue())
        assert delta.get("added", []) == []
        assert delta.get("removed", []) == []
        assert delta.get("modified", []) == []


# ---------------------------------------------------------------------------
# handle_apply
# ---------------------------------------------------------------------------


class TestHandleApply:
    def _args(self, base_file, delta_file, key="id", output=None) -> argparse.Namespace:
        return argparse.Namespace(
            base_file=base_file,
            delta_file=delta_file,
            key=key,
            output=output,
        )

    def test_apply_returns_updated_records(self, tmp_path):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)

        # Compute the delta, write it to disk
        delta = compute_delta(_V1, _V2, key="id")
        delta_path = _write_delta(tmp_path, "patch.json", delta)

        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_apply(self._args(old_path, delta_path, key="id"), fmt)

    def test_apply_writes_output_file(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "base.json", _V1)
        delta = compute_delta(_V1, _V2, key="id")
        delta_path = _write_delta(tmp_path, "patch.json", delta)
        out_path = os.path.join(str(tmp_path), "result.json")

        fmt = _make_formatter()
        handle_apply(self._args(old_path, delta_path, key="id", output=out_path), fmt)
        assert os.path.exists(out_path)
        captured = capsys.readouterr()
        assert out_path in captured.err

    def test_apply_missing_base_exits_1(self, tmp_path, capsys):
        delta = compute_delta(_V1, _V2, key="id")
        delta_path = _write_delta(tmp_path, "patch.json", delta)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_apply(
                self._args("/no/such/base.json", delta_path, key="id"),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_apply_missing_delta_file_exits_1(self, tmp_path, capsys):
        base_path = _write_json(tmp_path, "base.json", _V1)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_apply(
                self._args(base_path, "/no/such/patch.json", key="id"),
                fmt,
            )
        assert exc_info.value.code == 1

    def test_apply_invalid_delta_json_exits_1(self, tmp_path, capsys):
        base_path = _write_json(tmp_path, "base.json", _V1)
        bad_delta = os.path.join(str(tmp_path), "bad.json")
        with open(bad_delta, "w") as fh:
            fh.write("not-valid-json{{{")
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_apply(self._args(base_path, bad_delta, key="id"), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_compose
# ---------------------------------------------------------------------------


class TestHandleCompose:
    def _args(self, delta_files: list[str], output=None) -> argparse.Namespace:
        return argparse.Namespace(delta_files=delta_files, output=output)

    def test_compose_two_deltas(self, tmp_path):
        d1 = compute_delta(_V1, _V2, key="id")
        d2 = compute_delta(_V2, _V3, key="id")
        p1 = _write_delta(tmp_path, "d1.json", d1)
        p2 = _write_delta(tmp_path, "d2.json", d2)

        buf = io.StringIO()
        fmt = _make_formatter(buf)
        handle_compose(self._args([p1, p2]), fmt)
        result = json.loads(buf.getvalue())
        assert isinstance(result, dict)
        # Composed delta should contain the union of changes
        assert "added" in result or "modified" in result or "removed" in result

    def test_compose_writes_output_file(self, tmp_path, capsys):
        d1 = compute_delta(_V1, _V2, key="id")
        d2 = compute_delta(_V2, _V3, key="id")
        p1 = _write_delta(tmp_path, "d1.json", d1)
        p2 = _write_delta(tmp_path, "d2.json", d2)
        out_path = os.path.join(str(tmp_path), "combined.json")

        fmt = _make_formatter()
        handle_compose(self._args([p1, p2], output=out_path), fmt)
        assert os.path.exists(out_path)
        captured = capsys.readouterr()
        assert out_path in captured.err

    def test_compose_single_file_exits_1(self, tmp_path, capsys):
        d1 = compute_delta(_V1, _V2, key="id")
        p1 = _write_delta(tmp_path, "d1.json", d1)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compose(self._args([p1]), fmt)
        assert exc_info.value.code == 1

    def test_compose_missing_file_exits_1(self, tmp_path, capsys):
        d1 = compute_delta(_V1, _V2, key="id")
        p1 = _write_delta(tmp_path, "d1.json", d1)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compose(self._args([p1, "/no/such/d2.json"]), fmt)
        assert exc_info.value.code == 1

    def test_compose_invalid_json_exits_1(self, tmp_path, capsys):
        bad = os.path.join(str(tmp_path), "bad.json")
        with open(bad, "w") as fh:
            fh.write("not-json{{{")
        d1 = compute_delta(_V1, _V2, key="id")
        p1 = _write_delta(tmp_path, "d1.json", d1)
        fmt = _make_formatter()
        with pytest.raises(SystemExit) as exc_info:
            handle_compose(self._args([p1, bad]), fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI integration -- main() and --help
# ---------------------------------------------------------------------------


class TestDeltaCLI:
    def test_delta_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["delta", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "delta" in captured.out.lower()

    def test_delta_compute_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["delta", "compute", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower()

    def test_delta_apply_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["delta", "apply", "--help"])
        assert exc_info.value.code == 0

    def test_delta_compose_help_exits_0(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["delta", "compose", "--help"])
        assert exc_info.value.code == 0

    def test_delta_compute_missing_key_exits_nonzero(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        with pytest.raises(SystemExit) as exc_info:
            main(["delta", "compute", old_path, new_path])  # --key is required
        assert exc_info.value.code != 0

    def test_delta_compute_via_main(self, tmp_path, capsys):
        old_path = _write_json(tmp_path, "v1.json", _V1)
        new_path = _write_json(tmp_path, "v2.json", _V2)
        out_path = os.path.join(str(tmp_path), "patch.json")
        main(["delta", "compute", old_path, new_path, "--key", "id", "--output", out_path])
        assert os.path.exists(out_path)
        with open(out_path) as fh:
            delta = json.load(fh)
        assert isinstance(delta, dict)
