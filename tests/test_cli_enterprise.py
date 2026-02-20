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

"""Tests for crdt_merge.cli.cmd_enterprise — Enterprise CLI commands."""

from __future__ import annotations

import argparse
import io
import json
import os

import pytest

from crdt_merge.cli.cmd_enterprise import (
    handle_audit_log,
    handle_audit_export,
    handle_rbac_init,
    handle_rbac_check,
    register,
)
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter(stream: io.StringIO | None = None) -> OutputFormatter:
    return OutputFormatter(format="json", color=False, stream=stream or io.StringIO())


def _write_json(tmp_path, name: str, data) -> str:
    p = os.path.join(str(tmp_path), name)
    with open(p, "w") as f:
        json.dump(data, f)
    return p


_SAMPLE_AUDIT_LOG = [
    {"operation": "merge", "timestamp": "2026-01-01T00:00:00Z", "user": "alice", "hash": "abc123"},
    {"operation": "read",  "timestamp": "2026-01-02T00:00:00Z", "user": "bob",   "hash": "def456"},
]

_SAMPLE_RBAC_POLICY = {
    "roles": {
        "admin":   {"permissions": ["merge", "encrypt", "unmerge", "audit", "read"]},
        "merger":  {"permissions": ["merge", "read"]},
        "reader":  {"permissions": ["read"]},
        "auditor": {"permissions": ["audit", "read"]},
    },
    "policies": [{"node": "*", "role": "reader"}],
}


# ---------------------------------------------------------------------------
# audit log tests
# ---------------------------------------------------------------------------

class TestHandleAuditLog:
    def test_displays_all_entries(self, tmp_path, capsys):
        p = _write_json(tmp_path, "audit.json", _SAMPLE_AUDIT_LOG)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, verify=False, filter=None)
        handle_audit_log(args, fmt)
        output = stream.getvalue()
        assert "merge" in output or "alice" in output

    def test_filter_by_operation(self, tmp_path, capsys):
        p = _write_json(tmp_path, "audit.json", _SAMPLE_AUDIT_LOG)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, verify=False, filter="operation=merge")
        handle_audit_log(args, fmt)
        output = stream.getvalue()
        data = json.loads(output)
        assert all(e["operation"] == "merge" for e in data)

    def test_filter_no_match_returns_empty(self, tmp_path):
        p = _write_json(tmp_path, "audit.json", _SAMPLE_AUDIT_LOG)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p, verify=False, filter="operation=nonexistent")
        handle_audit_log(args, fmt)
        output = stream.getvalue()
        data = json.loads(output)
        assert data == []

    def test_missing_file_raises(self, tmp_path):
        fmt = _make_formatter()
        args = argparse.Namespace(
            file=str(tmp_path / "missing.json"), verify=False, filter=None
        )
        with pytest.raises((FileNotFoundError, OSError)):
            handle_audit_log(args, fmt)


# ---------------------------------------------------------------------------
# audit export tests
# ---------------------------------------------------------------------------

class TestHandleAuditExport:
    def test_export_outputs_entries(self, tmp_path):
        p = _write_json(tmp_path, "audit.json", _SAMPLE_AUDIT_LOG)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p)
        handle_audit_export(args, fmt)
        output = stream.getvalue()
        assert "merge" in output or "alice" in output

    def test_export_dict_input(self, tmp_path):
        data = {"entries": _SAMPLE_AUDIT_LOG}
        p = _write_json(tmp_path, "audit_dict.json", data)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(file=p)
        handle_audit_export(args, fmt)
        output = stream.getvalue()
        # Should have unpacked the entries
        assert output.strip() != ""


# ---------------------------------------------------------------------------
# rbac init tests
# ---------------------------------------------------------------------------

class TestHandleRbacInit:
    def test_init_creates_policy_file(self, tmp_path):
        out = str(tmp_path / "policy.json")
        fmt = _make_formatter()
        args = argparse.Namespace(output=out)
        handle_rbac_init(args, fmt)
        assert os.path.exists(out)
        with open(out) as f:
            policy = json.load(f)
        assert "roles" in policy
        assert "admin" in policy["roles"]

    def test_init_default_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fmt = _make_formatter()
        args = argparse.Namespace(output=None)
        handle_rbac_init(args, fmt)
        assert os.path.exists(tmp_path / "rbac-policy.json")

    def test_init_policy_has_required_roles(self, tmp_path):
        out = str(tmp_path / "policy.json")
        fmt = _make_formatter()
        args = argparse.Namespace(output=out)
        handle_rbac_init(args, fmt)
        with open(out) as f:
            policy = json.load(f)
        roles = policy["roles"]
        for role in ("admin", "merger", "reader", "auditor"):
            assert role in roles


# ---------------------------------------------------------------------------
# rbac check tests
# ---------------------------------------------------------------------------

class TestHandleRbacCheck:
    def test_allowed_permission(self, tmp_path, capsys):
        p = _write_json(tmp_path, "policy.json", _SAMPLE_RBAC_POLICY)
        fmt = _make_formatter()
        args = argparse.Namespace(
            policy_file=p, node="worker-1", role="admin", permission="merge"
        )
        handle_rbac_check(args, fmt)
        captured = capsys.readouterr()
        assert "ALLOWED" in captured.err or "allowed" in captured.err.lower()

    def test_denied_permission(self, tmp_path, capsys):
        p = _write_json(tmp_path, "policy.json", _SAMPLE_RBAC_POLICY)
        fmt = _make_formatter()
        args = argparse.Namespace(
            policy_file=p, node="worker-1", role="reader", permission="merge"
        )
        handle_rbac_check(args, fmt)
        captured = capsys.readouterr()
        assert "DENIED" in captured.err or "denied" in captured.err.lower()

    def test_unknown_role_exits(self, tmp_path, capsys):
        p = _write_json(tmp_path, "policy.json", _SAMPLE_RBAC_POLICY)
        fmt = _make_formatter()
        args = argparse.Namespace(
            policy_file=p, node="worker-1", role="ghost", permission="read"
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_rbac_check(args, fmt)
        assert exc_info.value.code == 1

    def test_result_contains_node_and_role(self, tmp_path):
        p = _write_json(tmp_path, "policy.json", _SAMPLE_RBAC_POLICY)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(
            policy_file=p, node="worker-1", role="merger", permission="read"
        )
        handle_rbac_check(args, fmt)
        output = stream.getvalue()
        assert "worker-1" in output
        assert "merger" in output


# ---------------------------------------------------------------------------
# CLI / --help tests
# ---------------------------------------------------------------------------

class TestEnterpriseCLI:
    def test_audit_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["audit", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "audit" in captured.out.lower()

    def test_rbac_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["rbac", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "rbac" in captured.out.lower() or "role" in captured.out.lower()

    def test_compliance_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["compliance", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "compliance" in captured.out.lower()

    def test_encrypt_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["encrypt", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "encrypt" in captured.out.lower() or "key" in captured.out.lower()

    def test_decrypt_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["decrypt", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "decrypt" in captured.out.lower() or "key" in captured.out.lower()

    def test_unmerge_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["unmerge", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "unmerge" in captured.out.lower() or "rollback" in captured.out.lower()

    def test_register_adds_all_enterprise_subparsers(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        # All enterprise commands should be reachable via --help
        for cmd in ("audit", "provenance", "compliance", "encrypt", "decrypt", "rbac"):
            with pytest.raises(SystemExit) as exc_info:
                parser.parse_args([cmd, "--help"])
            assert exc_info.value.code == 0
