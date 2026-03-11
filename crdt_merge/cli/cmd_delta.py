# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI handlers for the ``delta`` command group.

Subcommands
-----------
- ``delta compute <old> <new>``             -- compute a delta between two files
- ``delta apply <base> <delta>``            -- apply a delta to a base file
- ``delta compose <delta_files>...``        -- compose multiple deltas into one
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_compute(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Compute the delta between an old and new version of a dataset."""
    from crdt_merge.delta import compute_delta  # lazy
    from crdt_merge.cli import _util  # lazy

    key_col = args.key

    try:
        old_data = _util.load_data(args.old_file)
    except Exception as exc:
        formatter.error(f"Failed to load old file {args.old_file!r}: {exc}")
        sys.exit(1)

    try:
        new_data = _util.load_data(args.new_file)
    except Exception as exc:
        formatter.error(f"Failed to load new file {args.new_file!r}: {exc}")
        sys.exit(1)

    try:
        delta = compute_delta(old_data, new_data, key=key_col)
    except Exception as exc:
        formatter.error(f"Delta computation failed: {exc}")
        sys.exit(1)

    # Serialise the delta.
    delta_out = delta.to_dict() if hasattr(delta, "to_dict") else delta

    output_path = args.output
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(delta_out, fh, indent=2, default=str)
                fh.write("\n")
            formatter.success(f"Delta written to {output_path}")
        except OSError as exc:
            formatter.error(f"Could not write to {output_path!r}: {exc}")
            sys.exit(1)
    else:
        formatter.json(delta_out)

    # Summary stats.
    if hasattr(delta, "added"):
        n_added = len(delta.added) if delta.added else 0
        n_removed = len(delta.removed) if hasattr(delta, "removed") and delta.removed else 0
        n_changed = len(delta.changed) if hasattr(delta, "changed") and delta.changed else 0
        formatter.message(
            f"Delta: {n_added} added, {n_removed} removed, {n_changed} changed"
        )


def handle_apply(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Apply a delta file to a base dataset."""
    from crdt_merge.delta import apply_delta, Delta  # lazy
    from crdt_merge.cli import _util  # lazy

    try:
        base_data = _util.load_data(args.base_file)
    except Exception as exc:
        formatter.error(f"Failed to load base file {args.base_file!r}: {exc}")
        sys.exit(1)

    # Load the delta (always JSON).
    try:
        with open(args.delta_file, "r", encoding="utf-8") as fh:
            delta_dict = json.load(fh)
    except json.JSONDecodeError as exc:
        formatter.error(f"Invalid JSON in delta file {args.delta_file!r}: {exc}")
        sys.exit(1)
    except OSError as exc:
        formatter.error(f"Could not read delta file {args.delta_file!r}: {exc}")
        sys.exit(1)

    # Reconstruct the Delta object.
    try:
        delta = Delta.from_dict(delta_dict) if hasattr(Delta, "from_dict") else delta_dict
    except Exception as exc:
        formatter.error(f"Failed to parse delta: {exc}")
        sys.exit(1)

    key_col = args.key

    try:
        result = apply_delta(base_data, delta, key=key_col)
    except Exception as exc:
        formatter.error(f"Delta application failed: {exc}")
        sys.exit(1)

    output_path = args.output
    if output_path:
        try:
            _util.write_data(result, output_path)
            formatter.success(
                f"Applied delta to {len(base_data)} records, "
                f"wrote {len(result)} records to {output_path}"
            )
        except Exception as exc:
            formatter.error(f"Could not write output to {output_path!r}: {exc}")
            sys.exit(1)
    else:
        formatter.auto(result)
        formatter.message(
            f"Applied delta: {len(base_data)} base records -> {len(result)} result records"
        )


def handle_compose(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Compose multiple delta files into a single combined delta."""
    from crdt_merge.delta import compose_deltas, Delta  # lazy

    deltas = []
    for path in args.delta_files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                delta_dict = json.load(fh)
        except json.JSONDecodeError as exc:
            formatter.error(f"Invalid JSON in {path!r}: {exc}")
            sys.exit(1)
        except OSError as exc:
            formatter.error(f"Could not read {path!r}: {exc}")
            sys.exit(1)

        try:
            delta = Delta.from_dict(delta_dict) if hasattr(Delta, "from_dict") else delta_dict
        except Exception as exc:
            formatter.error(f"Failed to parse delta from {path!r}: {exc}")
            sys.exit(1)

        deltas.append(delta)

    if len(deltas) < 2:
        formatter.error("At least two delta files are required for composition.")
        sys.exit(1)

    try:
        composed = compose_deltas(deltas)
    except Exception as exc:
        formatter.error(f"Delta composition failed: {exc}")
        sys.exit(1)

    composed_out = composed.to_dict() if hasattr(composed, "to_dict") else composed

    output_path = args.output
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(composed_out, fh, indent=2, default=str)
                fh.write("\n")
            formatter.success(
                f"Composed {len(deltas)} deltas into {output_path}"
            )
        except OSError as exc:
            formatter.error(f"Could not write to {output_path!r}: {exc}")
            sys.exit(1)
    else:
        formatter.json(composed_out)

    formatter.message(f"Composed {len(deltas)} delta files successfully.")


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_HANDLER_MAP = {
    "compute": handle_compute,
    "apply": handle_apply,
    "compose": handle_compose,
}

# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``delta`` command and its sub-subparsers."""
    delta_parser = subparsers.add_parser(
        "delta",
        help="Compute, apply, and compose deltas for incremental dataset sync.",
        epilog=(
            "Examples:\n"
            "  crdt-merge delta compute old.json new.json --key id --output patch.json\n"
            "  crdt-merge delta apply base.json patch.json --key id --output updated.json\n"
            "  crdt-merge delta compose d1.json d2.json d3.json --output combined.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = delta_parser.add_subparsers(dest="delta_sub", metavar="SUBCOMMAND")

    # --- delta compute ---
    compute_parser = sub.add_parser(
        "compute",
        help="Compute the delta between two versions of a dataset.",
        epilog=(
            "Examples:\n"
            "  crdt-merge delta compute v1.json v2.json --key id\n"
            "  crdt-merge delta compute old.csv new.csv --key email --output delta.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compute_parser.add_argument(
        "old_file",
        metavar="OLD_FILE",
        help="Path to the older version of the dataset.",
    )
    compute_parser.add_argument(
        "new_file",
        metavar="NEW_FILE",
        help="Path to the newer version of the dataset.",
    )
    compute_parser.add_argument(
        "--key", "-k",
        required=True,
        metavar="COL",
        help="Column name used as the record key for diffing.",
    )
    compute_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write the computed delta to this file (default: stdout).",
    )
    compute_parser.set_defaults(delta_handler="compute", handler=handle_compute)

    # --- delta apply ---
    apply_parser = sub.add_parser(
        "apply",
        help="Apply a delta file to a base dataset.",
        epilog=(
            "Examples:\n"
            "  crdt-merge delta apply base.json patch.json --key id\n"
            "  crdt-merge delta apply base.csv patch.json --key id --output updated.csv\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    apply_parser.add_argument(
        "base_file",
        metavar="BASE_FILE",
        help="Path to the base dataset.",
    )
    apply_parser.add_argument(
        "delta_file",
        metavar="DELTA_FILE",
        help="Path to the delta file (JSON).",
    )
    apply_parser.add_argument(
        "--key", "-k",
        required=True,
        metavar="COL",
        help="Column name used as the record key.",
    )
    apply_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write the resulting dataset to this file (default: stdout).",
    )
    apply_parser.set_defaults(delta_handler="apply", handler=handle_apply)

    # --- delta compose ---
    compose_parser = sub.add_parser(
        "compose",
        help="Compose multiple delta files into a single delta.",
        epilog=(
            "Examples:\n"
            "  crdt-merge delta compose d1.json d2.json --output combined.json\n"
            "  crdt-merge delta compose d1.json d2.json d3.json d4.json -o all.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compose_parser.add_argument(
        "delta_files",
        nargs="+",
        metavar="DELTA_FILE",
        help="Two or more delta files to compose (in order).",
    )
    compose_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write the composed delta to this file (default: stdout).",
    )
    compose_parser.set_defaults(delta_handler="compose", handler=handle_compose)
