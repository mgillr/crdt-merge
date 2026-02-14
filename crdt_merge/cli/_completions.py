# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Shell completion script generators for bash, zsh, and fish."""

from __future__ import annotations


# All top-level commands
_COMMANDS = [
    "merge", "diff", "dedup", "stream", "json", "query",
    "verify", "merkle", "wire", "delta", "clock", "gossip",
    "model", "migrate", "hub",
    "audit", "provenance", "compliance", "encrypt", "decrypt", "unmerge", "rbac",
    "observe", "accel", "config", "completion",
    "doctor", "health", "repl", "wizard",
]

_SUBCOMMANDS = {
    "json": ["merge", "merge-lines"],
    "verify": ["crdt", "commutative", "associative", "idempotent", "convergence", "all"],
    "merkle": ["build", "diff", "compare"],
    "wire": ["serialize", "deserialize", "inspect", "size"],
    "delta": ["compute", "apply", "compose"],
    "clock": ["create", "merge", "compare"],
    "gossip": ["init", "update", "digest", "sync"],
    "model": ["merge", "strategies", "safety", "lora", "pipeline"],
    "hub": ["push", "pull", "merge"],
    "audit": ["log", "export"],
    "provenance": ["show", "export"],
    "compliance": ["check", "report"],
    "unmerge": ["rollback", "forget"],
    "rbac": ["init", "check"],
    "observe": ["metrics", "export", "drift"],
    "accel": ["list", "duckdb", "sqlite", "polars", "flight", "airbyte", "dbt"],
    "config": ["show", "path", "init"],
    "completion": ["bash", "zsh", "fish"],
    "wizard": ["merge", "schema", "model", "pipeline"],
}

_GLOBAL_OPTIONS = [
    "--version", "--config", "--format", "--no-color",
    "--quiet", "--verbose", "--output", "--help",
]


def generate_completion(shell: str) -> str:
    """Generate a completion script for the given shell."""
    generators = {
        "bash": _generate_bash,
        "zsh": _generate_zsh,
        "fish": _generate_fish,
    }
    gen = generators.get(shell)
    if not gen:
        raise ValueError(f"Unsupported shell: {shell}. Use bash, zsh, or fish.")
    return gen()


def _generate_bash() -> str:
    cmds = " ".join(_COMMANDS)
    opts = " ".join(_GLOBAL_OPTIONS)

    subcmd_cases = []
    for cmd, subs in _SUBCOMMANDS.items():
        subs_str = " ".join(subs)
        subcmd_cases.append(f'        {cmd}) COMPREPLY=($(compgen -W "{subs_str}" -- "$cur")) ;;')

    subcmd_block = "\n".join(subcmd_cases)

    return f'''# crdt-merge bash completion
# Add to ~/.bashrc: eval "$(crdt-merge completion bash)"

_crdt_merge_complete() {{
    local cur prev words cword
    _init_completion || return

    local commands="{cmds}"
    local global_opts="{opts}"

    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$commands $global_opts" -- "$cur"))
        return
    fi

    local cmd="${{words[1]}}"

    # Subcommand completion
    if [[ $cword -eq 2 ]]; then
        case "$cmd" in
{subcmd_block}
            *) COMPREPLY=($(compgen -f -- "$cur")) ;;
        esac
        return
    fi

    # File completion for everything else
    COMPREPLY=($(compgen -f -- "$cur"))
}}

complete -F _crdt_merge_complete crdt-merge
'''


def _generate_zsh() -> str:
    cmds_desc = []
    for cmd in _COMMANDS:
        cmds_desc.append(f"'{cmd}:{cmd} command'")
    cmds_str = " ".join(cmds_desc)

    subcmd_cases = []
    for cmd, subs in _SUBCOMMANDS.items():
        subs_quoted = " ".join(f"'{s}'" for s in subs)
        subcmd_cases.append(f"        {cmd}) _values 'subcommand' {subs_quoted} ;;")

    subcmd_block = "\n".join(subcmd_cases)

    return f'''#compdef crdt-merge
# crdt-merge zsh completion
# Add to ~/.zshrc: eval "$(crdt-merge completion zsh)"

_crdt-merge() {{
    local -a commands
    commands=({cmds_str})

    _arguments -C \\
        '--version[Show version]' \\
        '--config[Config file path]:file:_files' \\
        '--format[Output format]:(table json csv jsonl parquet)' \\
        '--no-color[Disable colors]' \\
        '(-q --quiet){{-q,--quiet}}[Suppress output]' \\
        '(-v --verbose){{-v,--verbose}}[Verbose output]' \\
        '(-o --output){{-o,--output}}[Output file]:file:_files' \\
        '1:command:->command' \\
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' commands
            ;;
        args)
            case $words[1] in
{subcmd_block}
                *) _files ;;
            esac
            ;;
    esac
}}

_crdt-merge "$@"
'''


def _generate_fish() -> str:
    lines = [
        "# crdt-merge fish completion",
        '# Save to: ~/.config/fish/completions/crdt-merge.fish',
        "",
        "# Disable file completion by default",
        "complete -c crdt-merge -f",
        "",
        "# Global options",
        "complete -c crdt-merge -l version -d 'Show version'",
        "complete -c crdt-merge -l config -r -d 'Config file path'",
        "complete -c crdt-merge -l format -x -a 'table json csv jsonl parquet' -d 'Output format'",
        "complete -c crdt-merge -l no-color -d 'Disable colors'",
        "complete -c crdt-merge -s q -l quiet -d 'Suppress output'",
        "complete -c crdt-merge -s v -l verbose -d 'Verbose output'",
        "complete -c crdt-merge -s o -l output -r -d 'Output file'",
        "",
        "# Commands",
    ]

    for cmd in _COMMANDS:
        lines.append(
            f"complete -c crdt-merge -n '__fish_use_subcommand' "
            f"-a {cmd} -d '{cmd} command'"
        )

    lines.append("")
    lines.append("# Subcommands")

    for cmd, subs in _SUBCOMMANDS.items():
        for sub in subs:
            lines.append(
                f"complete -c crdt-merge "
                f"-n '__fish_seen_subcommand_from {cmd}' "
                f"-a {sub} -d '{sub}'"
            )

    lines.append("")
    return "\n".join(lines)
