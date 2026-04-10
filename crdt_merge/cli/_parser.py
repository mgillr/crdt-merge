# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Argparse parser tree for the crdt-merge CLI.

Uses a registration pattern: each ``cmd_*.py`` module exports a
``register(subparsers)`` function that adds its commands.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import List

_COMMAND_MODULES: List[str] = [
    "cmd_merge",
    "cmd_json",
    "cmd_query",
    "cmd_verify",
    "cmd_merkle",
    "cmd_wire",
    "cmd_delta",
    "cmd_clock",
    "cmd_gossip",
    "cmd_model",
    "cmd_migrate",
    "cmd_hub",
    "cmd_enterprise",
    "cmd_observe",
    "cmd_accel",
    "cmd_config",
    "_wizard",
]


def _get_version() -> str:
    """Lazy-import the package version to avoid circular imports."""
    try:
        from crdt_merge import __version__  # type: ignore[import-untyped]

        return __version__
    except (ImportError, AttributeError):
        return "0.0.0-dev"


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser.

    Global flags are attached to the root parser.  Each command module in
    :data:`_COMMAND_MODULES` is dynamically imported and its
    ``register(subparsers)`` entry-point is called to wire up sub-commands.

    Returns
    -------
    argparse.ArgumentParser
        The fully-configured CLI parser.
    """
    parser = argparse.ArgumentParser(
        prog="crdt-merge",
        description=(
            "CRDT-based merge toolkit for CSV, JSON, and streaming data."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # -- global flags --------------------------------------------------------
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to a YAML/JSON configuration file.",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv", "jsonl", "parquet"],
        default=None,
        help="Output format (default: table).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable coloured terminal output.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="Suppress informational messages; only emit results and errors.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (may be repeated, e.g. -vv).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=None,
        help="Write output to PATH instead of stdout.",
    )

    # -- sub-commands --------------------------------------------------------
    subparsers = parser.add_subparsers(dest="command")

    for module_name in _COMMAND_MODULES:
        fqn = f"crdt_merge.cli.{module_name}"
        if module_name not in _COMMAND_MODULES:
            continue  # only import from the known command list
        try:
            mod = importlib.import_module(fqn)  # nosemgrep: non-literal-import -- fqn built from _COMMAND_MODULES constant
        except ImportError as exc:
            # The module may simply not exist yet; only surface this when the
            # user has asked for verbose output (we can't know at import time,
            # so we write to stderr as a best-effort hint).
            if "--verbose" in sys.argv or "-v" in sys.argv:
                print(
                    f"crdt-merge: skipping command module {fqn!r} ({exc})",
                    file=sys.stderr,
                )
            continue

        register_fn = getattr(mod, "register", None)
        if register_fn is None:
            if "--verbose" in sys.argv or "-v" in sys.argv:
                print(
                    f"crdt-merge: module {fqn!r} has no register() function",
                    file=sys.stderr,
                )
            continue

        register_fn(subparsers)

    return parser
