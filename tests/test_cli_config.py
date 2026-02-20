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

"""Tests for crdt_merge.cli.cmd_config — Config and completion CLI commands."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

import pytest

from crdt_merge.cli.cmd_config import (
    handle_config_show,
    handle_config_path,
    handle_config_init,
    handle_completion,
    register,
)
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter(stream: io.StringIO | None = None) -> OutputFormatter:
    return OutputFormatter(format="json", color=False, stream=stream or io.StringIO())


# ---------------------------------------------------------------------------
# handle_config_show tests
# ---------------------------------------------------------------------------

class TestHandleConfigShow:
    def test_show_returns_default_config_keys(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_show(args, fmt)
        output = stream.getvalue()
        data = json.loads(output)
        # Should contain rows with Section/Key/Value columns
        assert isinstance(data, list)
        assert len(data) > 0
        assert "Section" in data[0]
        assert "Key" in data[0]
        assert "Value" in data[0]

    def test_show_contains_cli_section(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_show(args, fmt)
        data = json.loads(stream.getvalue())
        sections = [row["Section"] for row in data]
        assert "cli" in sections

    def test_show_contains_merge_section(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_show(args, fmt)
        data = json.loads(stream.getvalue())
        sections = [row["Section"] for row in data]
        assert "merge" in sections

    def test_show_with_explicit_config_file(self, tmp_path):
        cfg = tmp_path / "custom.toml"
        cfg.write_text('[cli]\nformat = "csv"\n')
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=str(cfg))
        handle_config_show(args, fmt)
        data = json.loads(stream.getvalue())
        values_map = {(r["Section"], r["Key"]): r["Value"] for r in data}
        assert values_map.get(("cli", "format")) == "csv"


# ---------------------------------------------------------------------------
# handle_config_path tests
# ---------------------------------------------------------------------------

class TestHandleConfigPath:
    def test_path_returns_global_and_project(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_path(args, fmt)
        data = json.loads(stream.getvalue())
        locations = [row["Location"] for row in data]
        assert "Global" in locations
        assert "Project" in locations

    def test_path_global_row_has_home_dir(self):
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_path(args, fmt)
        data = json.loads(stream.getvalue())
        global_row = next(r for r in data if r["Location"] == "Global")
        assert os.path.expanduser("~") in global_row["Path"]

    def test_path_explicit_config_adds_explicit_row(self, tmp_path):
        cfg = tmp_path / "explicit.toml"
        cfg.write_text("")
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=str(cfg))
        handle_config_path(args, fmt)
        data = json.loads(stream.getvalue())
        locations = [row["Location"] for row in data]
        assert "Explicit" in locations

    def test_path_exists_column_accurate(self, tmp_path, monkeypatch):
        # Point cwd to tmp_path so project path doesn't accidentally exist
        monkeypatch.chdir(tmp_path)
        stream = io.StringIO()
        fmt = _make_formatter(stream)
        args = argparse.Namespace(config=None)
        handle_config_path(args, fmt)
        data = json.loads(stream.getvalue())
        project_row = next(r for r in data if r["Location"] == "Project")
        project_file = tmp_path / ".crdt-merge.toml"
        expected = "Yes" if project_file.exists() else "No"
        assert project_row["Exists"] == expected


# ---------------------------------------------------------------------------
# handle_config_init tests
# ---------------------------------------------------------------------------

class TestHandleConfigInit:
    def test_init_local_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fmt = _make_formatter()
        args = argparse.Namespace(global_config=False, local_config=True)
        handle_config_init(args, fmt)
        assert (tmp_path / ".crdt-merge.toml").exists()

    def test_init_global_creates_file_in_home(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setattr(os.path, "expanduser",
                            lambda p: p.replace("~", str(fake_home)))
        fmt = _make_formatter()
        args = argparse.Namespace(global_config=True, local_config=False)
        handle_config_init(args, fmt)
        assert (fake_home / ".crdt-merge.toml").exists()

    def test_init_default_falls_back_to_local(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fmt = _make_formatter()
        args = argparse.Namespace(global_config=False, local_config=False)
        handle_config_init(args, fmt)
        assert (tmp_path / ".crdt-merge.toml").exists()

    def test_init_existing_file_warns(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        existing = tmp_path / ".crdt-merge.toml"
        existing.write_text("[cli]\nformat = 'table'\n")
        fmt = _make_formatter()
        args = argparse.Namespace(global_config=False, local_config=True)
        handle_config_init(args, fmt)
        captured = capsys.readouterr()
        assert "already exists" in captured.err or "Warning" in captured.err

    def test_init_file_contains_toml_sections(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        fmt = _make_formatter()
        args = argparse.Namespace(global_config=False, local_config=True)
        handle_config_init(args, fmt)
        content = (tmp_path / ".crdt-merge.toml").read_text()
        assert "[cli]" in content
        assert "[merge]" in content


# ---------------------------------------------------------------------------
# handle_completion tests
# ---------------------------------------------------------------------------

class TestHandleCompletion:
    def test_bash_completion_contains_crdt_merge(self, capsys):
        fmt = _make_formatter()
        args = argparse.Namespace(shell="bash")
        handle_completion(args, fmt)
        captured = capsys.readouterr()
        assert "crdt-merge" in captured.out or "crdt_merge" in captured.out

    def test_zsh_completion_output(self, capsys):
        fmt = _make_formatter()
        args = argparse.Namespace(shell="zsh")
        handle_completion(args, fmt)
        captured = capsys.readouterr()
        assert "crdt" in captured.out

    def test_fish_completion_output(self, capsys):
        fmt = _make_formatter()
        args = argparse.Namespace(shell="fish")
        handle_completion(args, fmt)
        captured = capsys.readouterr()
        assert "crdt-merge" in captured.out


# ---------------------------------------------------------------------------
# CLI / --help tests
# ---------------------------------------------------------------------------

class TestConfigCLI:
    def test_config_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["config", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "config" in captured.out.lower()

    def test_config_show_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["config", "show", "--help"])
        assert exc_info.value.code == 0

    def test_config_path_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["config", "path", "--help"])
        assert exc_info.value.code == 0

    def test_config_init_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["config", "init", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "global" in captured.out.lower() or "local" in captured.out.lower()

    def test_completion_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["completion", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "bash" in captured.out or "zsh" in captured.out or "fish" in captured.out

    def test_completion_bash_via_main(self, capsys):
        main(["completion", "bash"])
        captured = capsys.readouterr()
        assert "crdt-merge" in captured.out or "crdt_merge" in captured.out

    def test_register_adds_config_and_completion(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        for cmd in ("config", "completion"):
            with pytest.raises(SystemExit):
                parser.parse_args([cmd, "--help"])
