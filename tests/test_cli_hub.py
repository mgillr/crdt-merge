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

"""Tests for crdt_merge.cli.cmd_hub — HuggingFace Hub CLI commands."""

from __future__ import annotations

import argparse
import io
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from crdt_merge.cli.cmd_hub import (
    _resolve_token,
    handle_push,
    handle_pull,
    handle_merge,
    register,
)
from crdt_merge.cli._output import OutputFormatter
from crdt_merge.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_formatter() -> OutputFormatter:
    return OutputFormatter(format="json", color=False, stream=io.StringIO())


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = {
        "token": None,
        "private": False,
        "commit_message": None,
        "output": None,
        "revision": None,
        "strategy": None,
        "push_to": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Token resolution tests
# ---------------------------------------------------------------------------

class TestResolveToken:
    def test_explicit_token_wins(self, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        args = _make_args(token="explicit-tok")
        assert _resolve_token(args) == "explicit-tok"

    def test_hf_token_env_fallback(self, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "env-tok")
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        args = _make_args(token=None)
        assert _resolve_token(args) == "env-tok"

    def test_huggingface_token_env_fallback(self, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.setenv("HUGGINGFACE_TOKEN", "hf-env-tok")
        args = _make_args(token=None)
        assert _resolve_token(args) == "hf-env-tok"

    def test_explicit_token_overrides_env(self, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "env-tok")
        args = _make_args(token="explicit-tok")
        assert _resolve_token(args) == "explicit-tok"

    def test_no_token_returns_none(self, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        args = _make_args(token=None)
        result = _resolve_token(args)
        assert result is None


# ---------------------------------------------------------------------------
# handle_push tests
# ---------------------------------------------------------------------------

class TestHandlePush:
    def test_push_missing_local_path_exits(self, tmp_path, capsys):
        fmt = _make_formatter()
        args = _make_args(
            local_model=str(tmp_path / "nonexistent"),
            repo_id="org/model",
        )
        with pytest.raises(SystemExit) as exc_info:
            handle_push(args, fmt)
        assert exc_info.value.code == 1

    def test_push_missing_hub_dependency_exits(self, tmp_path, capsys):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        fmt = _make_formatter()
        args = _make_args(local_model=str(model_dir), repo_id="org/model")

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", side_effect=SystemExit(1)):
            with pytest.raises(SystemExit) as exc_info:
                handle_push(args, fmt)
        assert exc_info.value.code == 1

    def test_push_no_token_prints_warning(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)

        model_dir = tmp_path / "model"
        model_dir.mkdir()
        fmt = _make_formatter()
        args = _make_args(local_model=str(model_dir), repo_id="org/model")

        mock_api = MagicMock()
        mock_hub_instance = MagicMock()
        mock_hub_instance._hub_api.return_value = mock_api
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            handle_push(args, fmt)

        captured = capsys.readouterr()
        assert "Warning" in captured.err or "token" in captured.err.lower()

    def test_push_api_error_exits(self, tmp_path, capsys):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        fmt = _make_formatter()
        args = _make_args(
            local_model=str(model_dir),
            repo_id="org/model",
            token="tok",
        )

        mock_api = MagicMock()
        mock_api.create_repo.side_effect = RuntimeError("network error")
        mock_hub_instance = MagicMock()
        mock_hub_instance._hub_api.return_value = mock_api
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            with pytest.raises(SystemExit) as exc_info:
                handle_push(args, fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_pull tests
# ---------------------------------------------------------------------------

class TestHandlePull:
    def test_pull_missing_hub_dependency_exits(self, capsys):
        fmt = _make_formatter()
        args = _make_args(repo_id="org/model", output=None, revision=None)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", side_effect=SystemExit(1)):
            with pytest.raises(SystemExit) as exc_info:
                handle_pull(args, fmt)
        assert exc_info.value.code == 1

    def test_pull_default_output_path(self, capsys):
        fmt = _make_formatter()
        args = _make_args(repo_id="my-org/my-model", output=None, revision=None)

        mock_api = MagicMock()
        mock_api.snapshot_download.return_value = "/tmp/my-org--my-model"
        mock_hub_instance = MagicMock()
        mock_hub_instance._hub_api.return_value = mock_api
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            handle_pull(args, fmt)

        call_kwargs = mock_api.snapshot_download.call_args[1]
        assert call_kwargs["repo_id"] == "my-org/my-model"
        # output derives from repo_id when not provided
        assert "my-org" in call_kwargs["local_dir"] or "--" in call_kwargs["local_dir"]

    def test_pull_with_revision(self, capsys):
        fmt = _make_formatter()
        args = _make_args(repo_id="org/model", output="/tmp/out", revision="v1.0")

        mock_api = MagicMock()
        mock_api.snapshot_download.return_value = "/tmp/out"
        mock_hub_instance = MagicMock()
        mock_hub_instance._hub_api.return_value = mock_api
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            handle_pull(args, fmt)

        call_kwargs = mock_api.snapshot_download.call_args[1]
        assert call_kwargs["revision"] == "v1.0"

    def test_pull_api_error_exits(self, capsys):
        fmt = _make_formatter()
        args = _make_args(repo_id="org/model", output=None, revision=None)

        mock_api = MagicMock()
        mock_api.snapshot_download.side_effect = RuntimeError("connection refused")
        mock_hub_instance = MagicMock()
        mock_hub_instance._hub_api.return_value = mock_api
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            with pytest.raises(SystemExit) as exc_info:
                handle_pull(args, fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# handle_merge tests
# ---------------------------------------------------------------------------

class TestHandleMerge:
    def _mock_hub_class(self, result):
        mock_hub_instance = MagicMock()
        mock_hub_instance.merge.return_value = result
        return MagicMock(return_value=mock_hub_instance)

    def test_merge_calls_hub_with_both_sources(self, capsys):
        fmt = _make_formatter()
        args = _make_args(
            repo_a="org/model-a",
            repo_b="org/model-b",
            strategy=None,
            push_to=None,
            token="tok",
        )

        mock_result = MagicMock()
        mock_result.state_dict = {"layer.weight": None}
        mock_result.model_card = None
        mock_result.repo_url = None
        mock_hub_class = self._mock_hub_class(mock_result)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            handle_merge(args, fmt)

        call_kwargs = mock_hub_class.return_value.merge.call_args[1]
        assert "org/model-a" in call_kwargs["sources"]
        assert "org/model-b" in call_kwargs["sources"]

    def test_merge_with_strategy(self, capsys):
        fmt = _make_formatter()
        args = _make_args(
            repo_a="org/a",
            repo_b="org/b",
            strategy="slerp",
            push_to=None,
            token="tok",
        )

        mock_result = MagicMock()
        mock_result.state_dict = {}
        mock_result.model_card = None
        mock_hub_class = self._mock_hub_class(mock_result)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class), \
             patch("crdt_merge.cli._progress.ProgressBar") as mock_pb:
            mock_pb.return_value.finish = MagicMock()
            handle_merge(args, fmt)

        call_kwargs = mock_hub_class.return_value.merge.call_args[1]
        assert call_kwargs["strategy"] == "slerp"

    def test_merge_push_to_requires_token(self, capsys, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        fmt = _make_formatter()
        args = _make_args(
            repo_a="org/a",
            repo_b="org/b",
            strategy=None,
            push_to="org/merged",
            token=None,
        )

        mock_hub_class = MagicMock()
        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class):
            with pytest.raises(SystemExit) as exc_info:
                handle_merge(args, fmt)
        assert exc_info.value.code == 1

    def test_merge_api_error_exits(self, capsys):
        fmt = _make_formatter()
        args = _make_args(
            repo_a="org/a",
            repo_b="org/b",
            strategy=None,
            push_to=None,
            token="tok",
        )

        mock_hub_instance = MagicMock()
        mock_hub_instance.merge.side_effect = RuntimeError("merge failed")
        mock_hub_class = MagicMock(return_value=mock_hub_instance)

        with patch("crdt_merge.cli.cmd_hub._lazy_import_hub", return_value=mock_hub_class), \
             patch("crdt_merge.cli._progress.ProgressBar") as mock_pb:
            mock_pb.return_value.finish = MagicMock()
            with pytest.raises(SystemExit) as exc_info:
                handle_merge(args, fmt)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI (argparse) / --help tests
# ---------------------------------------------------------------------------

class TestHubCLI:
    def test_hub_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["hub", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "push" in captured.out.lower() or "pull" in captured.out.lower()

    def test_hub_push_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["hub", "push", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "local_model" in captured.out or "repo_id" in captured.out or "push" in captured.out.lower()

    def test_hub_pull_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["hub", "pull", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "repo_id" in captured.out or "pull" in captured.out.lower()

    def test_hub_merge_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["hub", "merge", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "repo_a" in captured.out or "merge" in captured.out.lower()

    def test_register_adds_hub_subparser(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        register(sub)
        # Should parse hub push without error (besides missing required args)
        with pytest.raises(SystemExit):
            parser.parse_args(["hub"])
