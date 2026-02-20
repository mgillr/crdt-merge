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

"""Tests for crdt_merge.cli.cmd_gossip — gossip protocol CLI commands."""

from __future__ import annotations

import io
import json
import os
import types

import pytest

from crdt_merge.cli import main
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli.cmd_gossip import (
    _load_state_file,
    _save_state_file,
    handle_digest,
    handle_init,
    handle_sync,
    handle_update,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter(stream: io.StringIO | None = None) -> OutputFormatter:
    return OutputFormatter(format="json", color=False, stream=stream or io.StringIO())


def _make_args(**kwargs) -> types.SimpleNamespace:
    return types.SimpleNamespace(**kwargs)


def _write_gossip_state(tmp_path, name: str, node_id: str = "n1") -> str:
    """Create a minimal GossipState JSON file and return its path."""
    from crdt_merge.gossip import GossipState
    state = GossipState(node_id=node_id)
    p = str(tmp_path / name)
    with open(p, "w") as f:
        json.dump(state.to_dict(), f)
    return p


def _write_gossip_state_with_data(tmp_path, name: str, node_id: str, key: str, value) -> str:
    """Create a GossipState with one entry and return its path."""
    from crdt_merge.gossip import GossipState
    state = GossipState(node_id=node_id)
    state.update(key, value)
    p = str(tmp_path / name)
    with open(p, "w") as f:
        json.dump(state.to_dict(), f)
    return p


# ---------------------------------------------------------------------------
# 1. _save_state_file / _load_state_file round-trip
# ---------------------------------------------------------------------------

class TestStateFileIO:
    def test_save_and_reload(self, tmp_path):
        from crdt_merge.gossip import GossipState
        state = GossipState(node_id="test-node")
        path = str(tmp_path / "state.json")
        _save_state_file(state, path)
        loaded = _load_state_file(path)
        assert loaded.node_id == "test-node"

    def test_load_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            _load_state_file(str(tmp_path / "ghost.json"))
        assert exc_info.value.code == 1

    def test_load_invalid_json_exits(self, tmp_path):
        p = str(tmp_path / "corrupt.json")
        with open(p, "w") as f:
            f.write("{not valid json,,}")
        with pytest.raises(SystemExit) as exc_info:
            _load_state_file(p)
        assert exc_info.value.code == 1

    def test_save_creates_parent_dirs(self, tmp_path):
        from crdt_merge.gossip import GossipState
        state = GossipState(node_id="n1")
        path = str(tmp_path / "deep" / "dir" / "state.json")
        _save_state_file(state, path)
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# 2. handle_init
# ---------------------------------------------------------------------------

class TestHandleInit:
    def test_creates_state_file(self, tmp_path):
        path = str(tmp_path / "init_state.json")
        args = _make_args(node="node-A", state_file=path)
        handle_init(args, _make_formatter())
        assert os.path.exists(path)

    def test_state_file_has_correct_node(self, tmp_path):
        path = str(tmp_path / "node_b.json")
        args = _make_args(node="node-B", state_file=path)
        handle_init(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["node_id"] == "node-B"

    def test_state_file_is_empty_initially(self, tmp_path):
        path = str(tmp_path / "empty.json")
        args = _make_args(node="n0", state_file=path)
        handle_init(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["entries"] == {}

    def test_success_message_on_stderr(self, tmp_path, capsys):
        path = str(tmp_path / "msg.json")
        args = _make_args(node="my-node", state_file=path)
        handle_init(args, _make_formatter())
        captured = capsys.readouterr()
        assert "my-node" in captured.err


# ---------------------------------------------------------------------------
# 3. handle_update
# ---------------------------------------------------------------------------

class TestHandleUpdate:
    def test_update_string_value(self, tmp_path):
        path = _write_gossip_state(tmp_path, "upd.json", "n1")
        args = _make_args(state_file=path, key="username", value_json='"alice"')
        handle_update(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["entries"]["username"]["value"] == "alice"

    def test_update_integer_value(self, tmp_path):
        path = _write_gossip_state(tmp_path, "upd_int.json", "n1")
        args = _make_args(state_file=path, key="count", value_json="42")
        handle_update(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["entries"]["count"]["value"] == 42

    def test_update_dict_value(self, tmp_path):
        path = _write_gossip_state(tmp_path, "upd_dict.json", "n1")
        args = _make_args(state_file=path, key="config", value_json='{"timeout": 30}')
        handle_update(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["entries"]["config"]["value"] == {"timeout": 30}

    def test_update_invalid_json_exits(self, tmp_path):
        path = _write_gossip_state(tmp_path, "bad_val.json", "n1")
        args = _make_args(state_file=path, key="k", value_json="not-json-{{{")
        with pytest.raises(SystemExit) as exc_info:
            handle_update(args, _make_formatter())
        assert exc_info.value.code == 1

    def test_update_missing_state_file_exits(self, tmp_path):
        args = _make_args(
            state_file=str(tmp_path / "ghost.json"),
            key="k",
            value_json='"v"',
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_update(args, _make_formatter())
        assert exc_info.value.code == 1

    def test_update_increments_clock(self, tmp_path):
        path = _write_gossip_state(tmp_path, "clock_upd.json", "n1")
        args = _make_args(state_file=path, key="k", value_json='"v"')
        handle_update(args, _make_formatter())
        data = json.loads(open(path).read())
        assert data["clock"]["clocks"]["n1"] >= 1


# ---------------------------------------------------------------------------
# 4. handle_digest
# ---------------------------------------------------------------------------

class TestHandleDigest:
    def test_digest_empty_state(self, tmp_path):
        path = _write_gossip_state(tmp_path, "empty.json", "n1")
        buf = io.StringIO()
        args = _make_args(state_file=path)
        handle_digest(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        # Empty state produces an empty digest dict
        assert isinstance(result, dict)

    def test_digest_contains_key_after_update(self, tmp_path):
        path = _write_gossip_state_with_data(tmp_path, "data.json", "n1", "mykey", "myval")
        buf = io.StringIO()
        args = _make_args(state_file=path)
        handle_digest(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        assert "mykey" in result

    def test_digest_missing_file_exits(self, tmp_path):
        args = _make_args(state_file=str(tmp_path / "gone.json"))
        with pytest.raises(SystemExit) as exc_info:
            handle_digest(args, _make_formatter())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 5. handle_sync
# ---------------------------------------------------------------------------

class TestHandleSync:
    def test_sync_stdout(self, tmp_path):
        local = _write_gossip_state_with_data(tmp_path, "local.json", "n1", "x", 1)
        remote = _write_gossip_state_with_data(tmp_path, "remote.json", "n2", "y", 2)
        buf = io.StringIO()
        args = _make_args(local_state=local, remote_state=remote, output=None)
        handle_sync(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        assert "missing_local" in result or "missing_remote" in result or "different" in result

    def test_sync_to_output_file(self, tmp_path):
        local = _write_gossip_state_with_data(tmp_path, "local2.json", "n1", "a", 10)
        remote = _write_gossip_state_with_data(tmp_path, "remote2.json", "n2", "b", 20)
        out = str(tmp_path / "diff.json")
        args = _make_args(local_state=local, remote_state=remote, output=out)
        handle_sync(args, _make_formatter())
        assert os.path.exists(out)
        data = json.loads(open(out).read())
        assert isinstance(data, dict)

    def test_sync_identical_states(self, tmp_path):
        """Two states with the same key/value produce an empty diff."""
        local = _write_gossip_state_with_data(tmp_path, "lx.json", "n1", "shared", 99)
        # Build a second state file manually with the same content
        import shutil
        remote = str(tmp_path / "rx.json")
        shutil.copy(local, remote)
        buf = io.StringIO()
        args = _make_args(local_state=local, remote_state=remote, output=None)
        handle_sync(args, _make_formatter(buf))
        result = json.loads(buf.getvalue())
        # No missing entries on either side, no differences
        assert result.get("missing_local", []) == []
        assert result.get("missing_remote", []) == []

    def test_sync_missing_local_exits(self, tmp_path):
        remote = _write_gossip_state(tmp_path, "remote.json")
        args = _make_args(
            local_state=str(tmp_path / "ghost.json"),
            remote_state=remote,
            output=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_sync(args, _make_formatter())
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# 6. CLI integration via main()
# ---------------------------------------------------------------------------

class TestCLIMain:
    def test_gossip_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "gossip" in captured.out.lower()

    def test_gossip_init_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "init", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--node" in captured.out

    def test_gossip_update_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "update", "--help"])
        assert exc_info.value.code == 0

    def test_gossip_digest_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "digest", "--help"])
        assert exc_info.value.code == 0

    def test_gossip_sync_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "sync", "--help"])
        assert exc_info.value.code == 0

    def test_gossip_init_via_main(self, tmp_path, capsys):
        path = str(tmp_path / "via_main.json")
        main(["gossip", "init", "--node", "main-node", "--state-file", path])
        assert os.path.exists(path)
        data = json.loads(open(path).read())
        assert data["node_id"] == "main-node"

    def test_gossip_init_missing_node_errors(self, tmp_path, capsys):
        path = str(tmp_path / "no_node.json")
        with pytest.raises(SystemExit) as exc_info:
            main(["gossip", "init", "--state-file", path])
        assert exc_info.value.code != 0
