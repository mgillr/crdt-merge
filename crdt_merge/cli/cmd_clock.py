# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for distributed clock operations (vector clocks, dotted version vectors).

Registered sub-commands
-----------------------
* ``clock create`` -- Create a new VectorClock or DottedVersionVector.
* ``clock merge``  -- Merge two serialized clock files.
* ``clock compare`` -- Compare two clocks and report causal ordering.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from crdt_merge.cli._output import OutputFormatter

CLOCK_TYPES = ("vectorclock", "dvv")

EPILOG = """\
examples:
  %(prog)s create vectorclock --node node-1 --output clock_a.json
  %(prog)s create dvv --node node-2 --output clock_b.json
  %(prog)s merge clock_a.json clock_b.json
  %(prog)s compare clock_a.json clock_b.json
"""

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_DEPENDENCY_MSG = (
    "Error: crdt_merge.clocks is not installed.\n"
    "Install it with:  pip install crdt-merge[clocks]"
)


def _lazy_import_clocks():
    """Lazily import clock types to avoid heavy dependencies at CLI startup."""
    try:
        from crdt_merge.clocks import DottedVersionVector, Ordering, VectorClock
    except ImportError as exc:
        print(_DEPENDENCY_MSG, file=sys.stderr)
        raise SystemExit(1) from exc
    return VectorClock, DottedVersionVector, Ordering


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_clock_file(path: str) -> dict:
    """Load a clock from a JSON file, returning the deserialized dict."""
    filepath = Path(path)
    if not filepath.exists():
        print(f"Error: clock file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _instantiate_clock(data: dict):
    """Instantiate the correct clock type from deserialized JSON data.

    Uses the ``"type"`` key in *data* to select between ``VectorClock``
    (default) and ``DottedVersionVector``.
    """
    VectorClock, DottedVersionVector, _ = _lazy_import_clocks()
    clock_type = data.get("type", "vectorclock")
    if clock_type == "dvv":
        return DottedVersionVector.from_dict(data)
    return VectorClock.from_dict(data)


def _write_json(data: dict, path: str | Path) -> None:
    """Serialize *data* as pretty-printed JSON to *path*."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_create(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Create a new clock, initialize it with a node, and serialize to JSON."""
    VectorClock, DottedVersionVector, _ = _lazy_import_clocks()

    clock_type = args.type.lower()
    if clock_type not in CLOCK_TYPES:
        print(
            f"Error: unsupported clock type '{clock_type}'. "
            f"Choose from: {', '.join(CLOCK_TYPES)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if clock_type == "vectorclock":
        # increment() returns a new immutable VectorClock with the counter set
        clock = VectorClock().increment(args.node)
    else:
        base = VectorClock().increment(args.node)
        clock = DottedVersionVector(base=base, dot=(args.node, 1))
    serialized = clock.to_dict()

    output_path = Path(args.output)
    _write_json(serialized, output_path)

    formatter.success(f"Created {clock_type} clock for node '{args.node}' at {output_path}")


def handle_merge(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Load two clock files, merge them, and output the result."""
    _lazy_import_clocks()  # validate availability

    data_a = _load_clock_file(args.clock_a)
    data_b = _load_clock_file(args.clock_b)

    clock_a = _instantiate_clock(data_a)
    clock_b = _instantiate_clock(data_b)

    merged = clock_a.merge(clock_b)
    formatter.json(merged.to_dict())


def handle_compare(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Compare two clocks and print the causal ordering."""
    _, _, Ordering = _lazy_import_clocks()

    data_a = _load_clock_file(args.clock_a)
    data_b = _load_clock_file(args.clock_b)

    clock_a = _instantiate_clock(data_a)
    clock_b = _instantiate_clock(data_b)

    ordering = clock_a.compare(clock_b)

    ordering_labels = {
        Ordering.BEFORE: "BEFORE",
        Ordering.AFTER: "AFTER",
        Ordering.CONCURRENT: "CONCURRENT",
        Ordering.EQUAL: "EQUAL",
    }

    label = ordering_labels.get(ordering, str(ordering))
    formatter.message(label)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``clock`` sub-commands (create, merge, compare)."""
    clock_parser = subparsers.add_parser(
        "clock",
        help="Distributed clock operations (VectorClock, DVV)",
        epilog=EPILOG,
        formatter_class=lambda prog: __import__(
            "argparse"
        ).RawDescriptionHelpFormatter(prog, max_help_position=40),
    )
    clock_sub = clock_parser.add_subparsers(dest="clock_command", required=True)

    # -- clock create ---------------------------------------------------------
    create_p = clock_sub.add_parser(
        "create",
        help="Create a new distributed clock",
    )
    create_p.add_argument(
        "type",
        choices=CLOCK_TYPES,
        help="Clock type: vectorclock or dvv (dotted version vector)",
    )
    create_p.add_argument(
        "--node",
        required=True,
        help="Node identifier to initialize the clock with",
    )
    create_p.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output file path for the serialized clock JSON",
    )
    create_p.set_defaults(handler=handle_create)

    # -- clock merge ----------------------------------------------------------
    merge_p = clock_sub.add_parser(
        "merge",
        help="Merge two clocks and output the result",
    )
    merge_p.add_argument("clock_a", help="Path to the first clock JSON file")
    merge_p.add_argument("clock_b", help="Path to the second clock JSON file")
    merge_p.set_defaults(handler=handle_merge)

    # -- clock compare --------------------------------------------------------
    cmp_p = clock_sub.add_parser(
        "compare",
        help="Compare two clocks and print ordering (BEFORE|AFTER|CONCURRENT|EQUAL)",
    )
    cmp_p.add_argument("clock_a", help="Path to the first clock JSON file")
    cmp_p.add_argument("clock_b", help="Path to the second clock JSON file")
    cmp_p.set_defaults(handler=handle_compare)
