# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for JSON-specific merge operations.

Registered sub-commands
-----------------------
* ``json merge``        -- Deep-merge two JSON documents.
* ``json merge-lines``  -- Merge two JSON-Lines files by key.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register the ``json`` command group with its sub-commands."""

    json_parser = subparsers.add_parser(
        "json",
        help="JSON-specific merge operations.",
        description=(
            "Commands for merging JSON documents and JSON-Lines files "
            "using CRDT semantics."
        ),
    )

    json_sub = json_parser.add_subparsers(dest="json_command")

    # -- json merge ---------------------------------------------------------
    merge_p = json_sub.add_parser(
        "merge",
        help="Deep-merge two JSON documents.",
        description=(
            "Recursively merge two JSON files.  Objects are merged "
            "key-by-key; arrays and scalars use last-writer-wins by default."
        ),
    )
    merge_p.add_argument("file_a", help="Path to the first JSON file.")
    merge_p.add_argument("file_b", help="Path to the second JSON file.")
    merge_p.add_argument(
        "--prefer",
        choices=["a", "b"],
        default=None,
        help="Which file wins on scalar conflicts (default: deep merge).",
    )
    merge_p.add_argument(
        "--array-strategy",
        choices=["concat", "union", "replace"],
        default="union",
        help="Strategy for merging arrays (default: union).",
    )
    merge_p.set_defaults(handler=handle_json_merge)

    # -- json merge-lines ---------------------------------------------------
    ml_p = json_sub.add_parser(
        "merge-lines",
        help="Merge two JSON-Lines files by key.",
        description=(
            "Match records across two .jsonl files using --key, then merge "
            "each pair of matching records."
        ),
    )
    ml_p.add_argument("file_a", help="Path to the first JSONL file.")
    ml_p.add_argument("file_b", help="Path to the second JSONL file.")
    ml_p.add_argument(
        "--key", "-k",
        required=True,
        help="JSON field name used to match records across files.",
    )
    ml_p.add_argument(
        "--prefer",
        choices=["a", "b"],
        default=None,
        help="Which file wins on scalar conflicts.",
    )
    ml_p.set_defaults(handler=handle_json_merge_lines)

    # When ``json`` is invoked without a sub-command, print help.
    json_parser.set_defaults(
        handler=lambda _args, _fmt: json_parser.print_help()
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    """Load and parse a JSON file, exiting on error.

    Parameters
    ----------
    path:
        Filesystem path to the JSON file.

    Returns
    -------
    Any
        The parsed JSON value.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(
            f"error: invalid JSON in {path}: {exc.msg} "
            f"(line {exc.lineno}, col {exc.colno})",
            file=sys.stderr,
        )
        raise SystemExit(1)


def handle_json_merge(
    args: argparse.Namespace,
    formatter: "OutputFormatter",
) -> None:
    """Execute the ``json merge`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.json_merge import merge_dicts  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            f"error: json merge requires crdt_merge.json_merge: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    doc_a = _load_json(args.file_a)
    doc_b = _load_json(args.file_b)

    if not isinstance(doc_a, dict) or not isinstance(doc_b, dict):
        print(
            "error: json merge expects both files to contain JSON objects "
            "(dicts), not arrays or scalars.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    merge_kwargs: dict[str, Any] = {}
    if args.prefer is not None:
        merge_kwargs["prefer"] = args.prefer
    if args.array_strategy is not None:
        merge_kwargs["array_strategy"] = args.array_strategy

    result = merge_dicts(doc_a, doc_b, **merge_kwargs)

    output_path: Optional[str] = getattr(args, "output", None)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    else:
        formatter.auto(result)


def handle_json_merge_lines(
    args: argparse.Namespace,
    formatter: "OutputFormatter",
) -> None:
    """Execute the ``json merge-lines`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.json_merge import merge_json_lines  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            f"error: json merge-lines requires crdt_merge.json_merge: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    merge_kwargs: dict[str, Any] = {"key": args.key}
    if args.prefer is not None:
        merge_kwargs["prefer"] = args.prefer

    try:
        result = merge_json_lines(args.file_a, args.file_b, **merge_kwargs)
    except FileNotFoundError as exc:
        print(f"error: file not found: {exc.filename}", file=sys.stderr)
        raise SystemExit(1) from exc

    output_path: Optional[str] = getattr(args, "output", None)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as fh:
            for record in result:
                fh.write(json.dumps(record, ensure_ascii=False))
                fh.write("\n")
    else:
        formatter.auto(result)
