# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Config and completion CLI commands."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register config and completion commands."""
    _register_config(subparsers)
    _register_completion(subparsers)


# ── config ────────────────────────────────────────────────

def _register_config(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "config", help="Configuration management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge config show\n"
            "  crdt-merge config path\n"
            "  crdt-merge config init --global\n"
            "  crdt-merge config init --local\n"
        ),
    )
    sp = p.add_subparsers(dest="config_cmd")

    show_p = sp.add_parser("show", help="Display effective configuration")
    show_p.set_defaults(handler=handle_config_show)

    path_p = sp.add_parser("path", help="Print config file locations")
    path_p.set_defaults(handler=handle_config_path)

    init_p = sp.add_parser("init", help="Create default config file")
    init_group = init_p.add_mutually_exclusive_group()
    init_group.add_argument("--global", dest="global_config", action="store_true",
                             help="Write to ~/.crdt-merge.toml")
    init_group.add_argument("--local", dest="local_config", action="store_true",
                             help="Write to ./.crdt-merge.toml")
    init_p.set_defaults(handler=handle_config_init)


def handle_config_show(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._config import load_config

    config = load_config(getattr(args, "config", None))

    rows = []
    for section, values in sorted(config.items()):
        if isinstance(values, dict):
            for key, val in sorted(values.items()):
                rows.append({
                    "Section": section,
                    "Key": key,
                    "Value": str(val),
                })
        else:
            rows.append({
                "Section": "-",
                "Key": section,
                "Value": str(values),
            })

    formatter.auto(rows, title="Effective Configuration")


def handle_config_path(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._config import get_config_paths

    global_path = os.path.expanduser("~/.crdt-merge.toml")
    local_path = os.path.join(os.getcwd(), ".crdt-merge.toml")

    rows = [
        {
            "Location": "Global",
            "Path": global_path,
            "Exists": "Yes" if os.path.exists(global_path) else "No",
        },
        {
            "Location": "Project",
            "Path": local_path,
            "Exists": "Yes" if os.path.exists(local_path) else "No",
        },
    ]

    explicit = getattr(args, "config", None)
    if explicit:
        rows.append({
            "Location": "Explicit",
            "Path": explicit,
            "Exists": "Yes" if os.path.exists(explicit) else "No",
        })

    formatter.auto(rows, title="Config File Locations")


def handle_config_init(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._config import write_default_config

    if args.global_config:
        path = os.path.expanduser("~/.crdt-merge.toml")
    elif args.local_config:
        path = os.path.join(os.getcwd(), ".crdt-merge.toml")
    else:
        path = os.path.join(os.getcwd(), ".crdt-merge.toml")

    if os.path.exists(path):
        formatter.warning(f"Config file already exists: {path}")
        formatter.message("Use a text editor to modify it.")
        return

    write_default_config(path)
    formatter.success(f"Default config created: {path}")


# ── completion ────────────────────────────────────────────

def _register_completion(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "completion", help="Generate shell completion scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  eval \"$(crdt-merge completion bash)\"\n"
            "  crdt-merge completion zsh >> ~/.zshrc\n"
            "  crdt-merge completion fish > ~/.config/fish/completions/crdt-merge.fish\n"
        ),
    )
    p.add_argument("shell", choices=["bash", "zsh", "fish"],
                    help="Shell type")
    p.set_defaults(handler=handle_completion)


def handle_completion(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._completions import generate_completion
    script = generate_completion(args.shell)
    sys.stdout.write(script)
