# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Interactive REPL for the crdt-merge CLI.

Provides a ``crdt>`` prompt with readline tab completion, command history,
and full access to all CLI commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import readline
import shlex
import sys
from typing import Any, List, Optional


# Commands available in the REPL
_REPL_COMMANDS = [
    "merge", "diff", "dedup", "stream", "json", "query",
    "verify", "merkle", "wire", "delta", "clock", "gossip",
    "model", "migrate", "hub",
    "audit", "provenance", "compliance", "encrypt", "decrypt", "unmerge", "rbac",
    "observe", "accel", "config", "doctor", "health", "wizard",
]

_DOT_COMMANDS = [".help", ".exit", ".quit", ".history", ".clear", ".load", ".save"]

_DEFAULT_HISTORY = os.path.expanduser("~/.crdt-merge-history")


class REPLCompleter:
    """Tab completer for the REPL."""

    def __init__(self) -> None:
        self._options = _REPL_COMMANDS + _DOT_COMMANDS
        self._matches: List[str] = []

    def complete(self, text: str, state: int) -> Optional[str]:
        if state == 0:
            if text:
                self._matches = [c for c in self._options if c.startswith(text)]
            else:
                self._matches = list(self._options)
        try:
            return self._matches[state]
        except IndexError:
            return None


def start_repl(
    parser: Any,
    formatter: Any,
    config: dict,
    history_path: Optional[str] = None,
) -> None:
    """Start the interactive REPL.

    Args:
        parser: The argparse parser (for dispatching commands).
        formatter: The OutputFormatter instance.
        config: The loaded config dict.
        history_path: Path to the history file.
    """
    hist_path = history_path or _DEFAULT_HISTORY

    # Setup readline
    completer = REPLCompleter()
    readline.set_completer(completer.complete)
    readline.parse_and_bind("tab: complete")

    # Load history
    try:
        if os.path.exists(hist_path):
            readline.read_history_file(hist_path)
    except OSError:
        pass

    # Print banner
    try:
        from crdt_merge import __version__
        version = __version__
    except ImportError:
        version = "unknown"

    print(f"crdt-merge v{version} | Interactive REPL")
    print("Type .help for commands, .exit to quit")
    print()

    last_result = None

    while True:
        try:
            line = input("crdt> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        # Handle dot commands
        if line.startswith("."):
            parts = line.split(None, 1)
            dot_cmd = parts[0].lower()

            if dot_cmd in (".exit", ".quit"):
                break
            elif dot_cmd == ".help":
                _print_repl_help()
            elif dot_cmd == ".history":
                _print_history()
            elif dot_cmd == ".clear":
                subprocess.run(["clear" if os.name != "nt" else "cls"], check=False)
            elif dot_cmd == ".load":
                if len(parts) > 1:
                    last_result = _load_file(parts[1], formatter)
                else:
                    formatter.error("Usage: .load <file>")
            elif dot_cmd == ".save":
                if len(parts) > 1 and last_result is not None:
                    _save_result(last_result, parts[1], formatter)
                else:
                    formatter.error("Usage: .save <file> (requires a previous result)")
            else:
                formatter.error(f"Unknown command: {dot_cmd}")
            continue

        # Parse and dispatch as a CLI command
        try:
            argv = shlex.split(line)
        except ValueError as e:
            formatter.error(f"Parse error: {e}")
            continue

        try:
            args = parser.parse_args(argv)
            handler = getattr(args, "handler", None)
            if handler:
                result = handler(args, formatter)
                if result is not None:
                    last_result = result
            else:
                parser.parse_args(argv + ["--help"])
        except SystemExit:
            # argparse calls sys.exit on --help or errors
            pass
        except Exception as e:
            formatter.error(str(e))

    # Save history
    try:
        readline.write_history_file(hist_path)
    except OSError:
        pass

    print("Goodbye.")


def _print_repl_help() -> None:
    """Print REPL help."""
    print()
    print("REPL Commands:")
    print("  .help           Show this help")
    print("  .exit / .quit   Exit the REPL")
    print("  .history        Show command history")
    print("  .clear          Clear the screen")
    print("  .load <file>    Load a data file into _")
    print("  .save <file>    Save last result to file")
    print()
    print("CLI Commands (same as command line):")
    for i in range(0, len(_REPL_COMMANDS), 6):
        chunk = _REPL_COMMANDS[i:i+6]
        print("  " + "  ".join(f"{c:<14}" for c in chunk))
    print()
    print("Examples:")
    print('  merge a.csv b.csv --key id')
    print('  dedup data.csv --method fuzzy --threshold 0.9')
    print('  model strategies')
    print('  query "MERGE a.csv WITH b.csv ON id"')
    print()


def _print_history() -> None:
    """Print readline history."""
    length = readline.get_current_history_length()
    for i in range(1, length + 1):
        item = readline.get_history_item(i)
        if item:
            print(f"  {i:4d}  {item}")


def _load_file(path: str, formatter: Any) -> Optional[list]:
    """Load a file and return its contents."""
    try:
        from crdt_merge.cli._util import load_data
        data = load_data(path)
        formatter.success(f"Loaded {len(data)} records from {path}")
        return data
    except Exception as e:
        formatter.error(str(e))
        return None


def _save_result(data: Any, path: str, formatter: Any) -> None:
    """Save result to file."""
    try:
        from crdt_merge.cli._util import write_data
        if isinstance(data, list):
            write_data(data, path)
        else:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        formatter.success(f"Saved to {path}")
    except Exception as e:
        formatter.error(str(e))
