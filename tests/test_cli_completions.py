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

"""Tests for crdt_merge.cli._completions — generate_completion()."""

from __future__ import annotations

import pytest

from crdt_merge.cli._completions import (
    _COMMANDS,
    _GLOBAL_OPTIONS,
    _SUBCOMMANDS,
    generate_completion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(shell: str) -> str:
    """Return the completion script for *shell*, asserting it's a non-empty str."""
    result = generate_completion(shell)
    assert isinstance(result, str)
    assert result.strip()
    return result


# ---------------------------------------------------------------------------
# generate_completion() basic return-value contract
# ---------------------------------------------------------------------------

class TestGenerateCompletionBasic:
    def test_bash_returns_non_empty_string(self):
        result = generate_completion("bash")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_zsh_returns_non_empty_string(self):
        result = generate_completion("zsh")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_fish_returns_non_empty_string(self):
        result = generate_completion("fish")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_shell_raises_value_error(self):
        with pytest.raises(ValueError):
            generate_completion("powershell")

    def test_unknown_shell_error_message_names_shell(self):
        with pytest.raises(ValueError, match="powershell"):
            generate_completion("powershell")

    def test_unknown_shell_error_message_lists_supported(self):
        with pytest.raises(ValueError) as exc_info:
            generate_completion("tcsh")
        msg = str(exc_info.value)
        assert "bash" in msg
        assert "zsh" in msg
        assert "fish" in msg

    def test_empty_string_shell_raises_value_error(self):
        with pytest.raises(ValueError):
            generate_completion("")


# ---------------------------------------------------------------------------
# Bash completion content
# ---------------------------------------------------------------------------

class TestBashCompletion:
    def test_bash_contains_function_definition(self):
        script = _get("bash")
        assert "_crdt_merge_complete" in script

    def test_bash_registers_complete_command(self):
        script = _get("bash")
        assert "complete -F _crdt_merge_complete" in script

    def test_bash_references_binary_name(self):
        script = _get("bash")
        assert "crdt-merge" in script or "crdt_merge" in script

    def test_bash_contains_compgen(self):
        script = _get("bash")
        assert "compgen" in script

    def test_bash_contains_all_top_level_commands(self):
        script = _get("bash")
        for cmd in _COMMANDS:
            assert cmd in script, f"Command {cmd!r} missing from bash completion"

    def test_bash_contains_global_options(self):
        script = _get("bash")
        assert "--help" in script
        assert "--format" in script

    def test_bash_contains_subcommands_for_verify(self):
        script = _get("bash")
        for sub in _SUBCOMMANDS["verify"]:
            assert sub in script, f"Subcommand verify/{sub!r} missing from bash completion"

    def test_bash_contains_subcommands_for_config(self):
        script = _get("bash")
        for sub in _SUBCOMMANDS["config"]:
            assert sub in script, f"Subcommand config/{sub!r} missing from bash completion"

    def test_bash_contains_case_statement(self):
        script = _get("bash")
        assert "case" in script

    def test_bash_contains_init_completion(self):
        script = _get("bash")
        assert "_init_completion" in script


# ---------------------------------------------------------------------------
# Zsh completion content
# ---------------------------------------------------------------------------

class TestZshCompletion:
    def test_zsh_starts_with_compdef(self):
        script = _get("zsh")
        assert "#compdef crdt-merge" in script

    def test_zsh_contains_function_definition(self):
        script = _get("zsh")
        assert "_crdt-merge()" in script or "_crdt-merge ()" in script

    def test_zsh_references_binary_name(self):
        script = _get("zsh")
        assert "crdt-merge" in script

    def test_zsh_contains_all_top_level_commands(self):
        script = _get("zsh")
        for cmd in _COMMANDS:
            assert cmd in script, f"Command {cmd!r} missing from zsh completion"

    def test_zsh_contains_format_option(self):
        script = _get("zsh")
        assert "--format" in script

    def test_zsh_lists_output_formats(self):
        script = _get("zsh")
        for fmt in ("table", "json", "csv", "jsonl"):
            assert fmt in script, f"Format {fmt!r} missing from zsh completion"

    def test_zsh_contains_arguments_directive(self):
        script = _get("zsh")
        assert "_arguments" in script

    def test_zsh_contains_subcommands_for_merkle(self):
        script = _get("zsh")
        for sub in _SUBCOMMANDS["merkle"]:
            assert sub in script, f"Subcommand merkle/{sub!r} missing from zsh completion"

    def test_zsh_uses_describe_for_commands(self):
        script = _get("zsh")
        assert "_describe" in script

    def test_zsh_contains_state_machine(self):
        script = _get("zsh")
        assert "state" in script


# ---------------------------------------------------------------------------
# Fish completion content
# ---------------------------------------------------------------------------

class TestFishCompletion:
    def test_fish_disables_file_completion(self):
        script = _get("fish")
        assert "complete -c crdt-merge -f" in script

    def test_fish_references_binary_name(self):
        script = _get("fish")
        assert "crdt-merge" in script

    def test_fish_contains_all_top_level_commands(self):
        script = _get("fish")
        for cmd in _COMMANDS:
            assert cmd in script, f"Command {cmd!r} missing from fish completion"

    def test_fish_contains_global_option_version(self):
        script = _get("fish")
        # fish uses "-l version" style; check that the version option is registered
        assert "version" in script

    def test_fish_contains_format_option(self):
        script = _get("fish")
        assert "--format" in script or "-l format" in script

    def test_fish_uses_fish_seen_subcommand_from(self):
        script = _get("fish")
        assert "__fish_seen_subcommand_from" in script

    def test_fish_uses_fish_use_subcommand(self):
        script = _get("fish")
        assert "__fish_use_subcommand" in script

    def test_fish_contains_subcommands_for_accel(self):
        script = _get("fish")
        for sub in _SUBCOMMANDS["accel"]:
            assert sub in script, f"Subcommand accel/{sub!r} missing from fish completion"

    def test_fish_contains_subcommands_for_clock(self):
        script = _get("fish")
        for sub in _SUBCOMMANDS["clock"]:
            assert sub in script, f"Subcommand clock/{sub!r} missing from fish completion"


# ---------------------------------------------------------------------------
# Cross-shell invariants
# ---------------------------------------------------------------------------

class TestCrossShellInvariants:
    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_all_shells_contain_merge_command(self, shell):
        script = _get(shell)
        assert "merge" in script

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_all_shells_contain_binary_name(self, shell):
        script = _get(shell)
        assert "crdt-merge" in script or "crdt_merge" in script

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_all_shells_are_multiline(self, shell):
        script = _get(shell)
        assert "\n" in script

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_all_shells_contain_completion_subcommands(self, shell):
        # The "completion" command's subcommands include the shell names themselves
        script = _get(shell)
        for sub in _SUBCOMMANDS["completion"]:
            assert sub in script, (
                f"completion subcommand {sub!r} missing from {shell} completion"
            )

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_all_shells_contain_all_global_options(self, shell):
        script = _get(shell)
        # --format and --version are present in all three shell templates
        assert "--format" in script or "format" in script
        assert "--version" in script or "version" in script
