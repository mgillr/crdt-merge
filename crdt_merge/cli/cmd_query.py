# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for MergeQL query parsing and execution.

Registered sub-commands
-----------------------
* ``query`` -- Parse and execute a MergeQL query, optionally explaining its plan.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from crdt_merge.cli._output import OutputFormatter

EPILOG = """\
examples:
  %(prog)s "MERGE a, b ON id"
  %(prog)s "MERGE a, b ON id STRATEGY name='lww', score='max'"
  %(prog)s --file query.mql --register a=data_a.json --register b=data_b.json
  %(prog)s "MERGE a, b ON id" --explain
  %(prog)s "MERGE a, b ON id WHERE score > 80 LIMIT 100"
"""

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_DEPENDENCY_MSG = (
    "Error: crdt_merge.mergeql is not installed.\n"
    "Install it with:  pip install crdt-merge[mergeql]"
)


def _lazy_import_mergeql():
    """Lazily import MergeQL module to avoid heavy dependencies at CLI startup."""
    try:
        from crdt_merge.mergeql import MergeQL, MergeQLParser, MergeQLResult
    except ImportError as exc:
        print(_DEPENDENCY_MSG, file=sys.stderr)
        raise SystemExit(1) from exc
    return MergeQL, MergeQLParser, MergeQLResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_data(path: str):
    """Load data from a file path, delegating to the CLI utility loader.

    Falls back to basic JSON loading when ``crdt_merge.cli._util`` is
    unavailable.
    """
    try:
        from crdt_merge.cli._util import load_data
    except ImportError:
        import json

        filepath = Path(path)
        if not filepath.exists():
            print(f"Error: data file not found: {path}", file=sys.stderr)
            raise SystemExit(1)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            print(f"Error: failed to parse {path}: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    else:
        return load_data(path)


def _parse_register_flags(register_list: list[str] | None) -> dict[str, str]:
    """Parse ``--register NAME=PATH`` flags into a ``{name: path}`` mapping.

    Exits with a clear error when a flag does not contain an ``=`` separator
    or when name/path components are empty.
    """
    if not register_list:
        return {}

    result: dict[str, str] = {}
    for entry in register_list:
        if "=" not in entry:
            print(
                f"Error: invalid --register format: '{entry}'\n"
                f"  Expected format: NAME=PATH (e.g. --register a=data_a.json)",
                file=sys.stderr,
            )
            raise SystemExit(1)

        name, path = entry.split("=", 1)
        name = name.strip()
        path = path.strip()

        if not name:
            print(f"Error: empty register name in: '{entry}'", file=sys.stderr)
            raise SystemExit(1)
        if not path:
            print(
                f"Error: empty path for register '{name}' in: '{entry}'",
                file=sys.stderr,
            )
            raise SystemExit(1)

        result[name] = path
    return result


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def handle_query(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Parse and execute a MergeQL query, or explain its query plan."""
    MergeQL, MergeQLParser, _ = _lazy_import_mergeql()

    # -- determine query source -----------------------------------------------
    if args.file:
        query_path = Path(args.file)
        if not query_path.exists():
            print(f"Error: query file not found: {args.file}", file=sys.stderr)
            raise SystemExit(1)
        try:
            query_string = query_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"Error: failed to read query file: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
    elif args.mergeql_string:
        query_string = args.mergeql_string
    else:
        print(
            "Error: no query provided. Supply a query string or use --file.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if not query_string:
        print("Error: query is empty.", file=sys.stderr)
        raise SystemExit(1)

    # -- parse registers ------------------------------------------------------
    registers = _parse_register_flags(args.register)

    # -- parse the query ------------------------------------------------------
    parser = MergeQLParser()
    try:
        parsed = parser.parse(query_string)
    except Exception as exc:
        print(f"Error: failed to parse MergeQL query: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    # -- build the execution engine and register data sources -----------------
    engine = MergeQL()
    for name, path in registers.items():
        data = _load_data(path)
        engine.register(name, data)

    # -- explain mode: show query plan without executing ----------------------
    if args.explain:
        try:
            plan = engine.explain(query_string)
            plan_data = plan if isinstance(plan, dict) else {"plan": str(plan)}
        except Exception as exc:
            plan_data = {"plan": str(exc)}
        formatter.json(plan_data)
        return

    # -- execute the query ----------------------------------------------------
    try:
        result = engine.execute(query_string)
    except Exception as exc:
        print(f"Error: query execution failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    # -- output results -------------------------------------------------------
    if hasattr(result, "data") and isinstance(result.data, list):
        # MergeQLResult dataclass -- show merged rows as a table
        formatter.auto(result.data)
        formatter.message(
            f"Merged {result.sources_merged} sources, "
            f"{len(result.data)} rows, "
            f"{result.conflicts} conflict(s) resolved in "
            f"{result.merge_time_ms:.1f}ms"
        )
    elif hasattr(result, "to_dict"):
        formatter.json(result.to_dict())
    elif hasattr(result, "value"):
        formatter.json(result.value)
    else:
        formatter.json({"result": str(result)})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register the ``query`` command."""
    query_p = subparsers.add_parser(
        "query",
        help="Parse and execute MergeQL queries",
        epilog=EPILOG,
        formatter_class=lambda prog: __import__(
            "argparse"
        ).RawDescriptionHelpFormatter(prog, max_help_position=40),
    )
    query_p.add_argument(
        "mergeql_string",
        nargs="?",
        default=None,
        help="MergeQL query string to execute",
    )
    query_p.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help="Read the MergeQL query from a file instead of a positional argument",
    )
    query_p.add_argument(
        "--register",
        action="append",
        metavar="NAME=PATH",
        help="Register a data source by name (repeatable, e.g. --register a=data.json)",
    )
    query_p.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Show the query plan without executing",
    )
    query_p.set_defaults(handler=handle_query)
