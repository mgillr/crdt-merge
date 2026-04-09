# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI handlers for the ``merkle`` command group.

Subcommands
-----------
- ``merkle build <file>``                -- build a Merkle tree and output JSON
- ``merkle diff <tree_a> <tree_b>``      -- diff two serialised Merkle trees
- ``merkle compare <file_a> <file_b>``   -- compare two datasets via Merkle trees
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_build(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Build a MerkleTree from a data file and write its JSON representation."""
    from crdt_merge.merkle import MerkleTree  # lazy
    from crdt_merge.cli import _util  # lazy

    key_col = args.key

    try:
        data = _util.load_data(args.file)
    except Exception as exc:
        formatter.error(f"Failed to load data from {args.file!r}: {exc}")
        sys.exit(1)

    if not data:
        formatter.error("Input file contains no records.")
        sys.exit(1)

    if key_col and key_col not in data[0]:
        formatter.error(
            f"Key column {key_col!r} not found in data. "
            f"Available columns: {', '.join(data[0].keys())}"
        )
        sys.exit(1)

    try:
        tree = MerkleTree.from_records(data, key=key_col)
    except Exception as exc:
        formatter.error(f"Failed to build Merkle tree: {exc}")
        sys.exit(1)

    tree_json = tree.to_dict()

    output_path = args.output
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(tree_json, fh, indent=2, default=str)
                fh.write("\n")
            formatter.success(f"Merkle tree written to {output_path}")
        except OSError as exc:
            formatter.error(f"Could not write to {output_path!r}: {exc}")
            sys.exit(1)
    else:
        formatter.json(tree_json)

    formatter.message(
        f"Tree built from {len(data)} records "
        f"(root hash: {tree.root_hash[:16]}...)"
    )


def handle_diff(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Load two serialised Merkle trees and display their differences."""
    from crdt_merge.merkle import MerkleTree, merkle_diff  # lazy

    def _load_tree(path: str) -> MerkleTree:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                tree_dict = json.load(fh)
            return MerkleTree.from_dict(tree_dict)
        except json.JSONDecodeError as exc:
            formatter.error(f"Invalid JSON in {path!r}: {exc}")
            sys.exit(1)
        except (OSError, KeyError, TypeError) as exc:
            formatter.error(f"Failed to load tree from {path!r}: {exc}")
            sys.exit(1)

    tree_a = _load_tree(args.tree_a)
    tree_b = _load_tree(args.tree_b)

    try:
        diffs = merkle_diff(tree_a, tree_b)
    except Exception as exc:
        formatter.error(f"Diff computation failed: {exc}")
        sys.exit(1)

    # MerkleDiff is a dataclass, not a list -- check is_identical property
    is_identical = getattr(diffs, "is_identical", None)
    if is_identical is True or (hasattr(diffs, "num_differences") and diffs.num_differences == 0):
        formatter.success("Trees are identical -- no differences found.")
        return

    # Build rows from the MerkleDiff dataclass fields
    if hasattr(diffs, "to_dict"):
        formatter.json(diffs.to_dict())
    else:
        formatter.json({"result": str(diffs)})


def handle_compare(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Compare two data files by building Merkle trees and diffing them."""
    from crdt_merge.merkle import compare_datasets  # lazy
    from crdt_merge.cli import _util  # lazy

    key_col = args.key

    try:
        data_a = _util.load_data(args.file_a)
    except Exception as exc:
        formatter.error(f"Failed to load {args.file_a!r}: {exc}")
        sys.exit(1)

    try:
        data_b = _util.load_data(args.file_b)
    except Exception as exc:
        formatter.error(f"Failed to load {args.file_b!r}: {exc}")
        sys.exit(1)

    try:
        diffs = compare_datasets(data_a, data_b, key=key_col)
    except Exception as exc:
        formatter.error(f"Comparison failed: {exc}")
        sys.exit(1)

    # MerkleDiff is a dataclass, not a list
    is_identical = getattr(diffs, "is_identical", None)
    if is_identical is True or (hasattr(diffs, "num_differences") and diffs.num_differences == 0):
        formatter.success("Datasets are identical.")
        return

    n = getattr(diffs, "num_differences", "?")
    formatter.message(f"Found {n} difference(s) between {args.file_a} and {args.file_b}:")
    if hasattr(diffs, "to_dict"):
        formatter.json(diffs.to_dict())
    else:
        formatter.json({"result": str(diffs)})


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_HANDLER_MAP = {
    "build": handle_build,
    "diff": handle_diff,
    "compare": handle_compare,
}

# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``merkle`` command and its sub-subparsers."""
    merkle_parser = subparsers.add_parser(
        "merkle",
        help="Build, diff, and compare Merkle trees for dataset reconciliation.",
        epilog=(
            "Examples:\n"
            "  crdt-merge merkle build data.json --key id --output tree.json\n"
            "  crdt-merge merkle diff tree_a.json tree_b.json\n"
            "  crdt-merge merkle compare site_a.csv site_b.csv --key user_id\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = merkle_parser.add_subparsers(dest="merkle_sub", metavar="SUBCOMMAND")

    # --- merkle build ---
    build_parser = sub.add_parser(
        "build",
        help="Build a Merkle tree from a data file.",
        epilog=(
            "Examples:\n"
            "  crdt-merge merkle build users.json --key id\n"
            "  crdt-merge merkle build users.csv --key email --output tree.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    build_parser.add_argument(
        "file",
        metavar="FILE",
        help="Input data file (CSV, JSON, JSONL, or Parquet).",
    )
    build_parser.add_argument(
        "--key",
        metavar="COL",
        default=None,
        help="Column to use as the record key for tree construction.",
    )
    build_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write the Merkle tree JSON to this file (default: stdout).",
    )
    build_parser.set_defaults(merkle_handler="build", handler=handle_build)

    # --- merkle diff ---
    diff_parser = sub.add_parser(
        "diff",
        help="Diff two serialised Merkle tree JSON files.",
        epilog=(
            "Examples:\n"
            "  crdt-merge merkle diff tree_v1.json tree_v2.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    diff_parser.add_argument(
        "tree_a",
        metavar="TREE_A",
        help="Path to the first Merkle tree JSON file.",
    )
    diff_parser.add_argument(
        "tree_b",
        metavar="TREE_B",
        help="Path to the second Merkle tree JSON file.",
    )
    diff_parser.set_defaults(merkle_handler="diff", handler=handle_diff)

    # --- merkle compare ---
    compare_parser = sub.add_parser(
        "compare",
        help="Compare two data files via Merkle tree construction and diff.",
        epilog=(
            "Examples:\n"
            "  crdt-merge merkle compare site_a.json site_b.json --key id\n"
            "  crdt-merge merkle compare replica1.csv replica2.csv --key user_id\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compare_parser.add_argument(
        "file_a",
        metavar="FILE_A",
        help="Path to the first data file.",
    )
    compare_parser.add_argument(
        "file_b",
        metavar="FILE_B",
        help="Path to the second data file.",
    )
    compare_parser.add_argument(
        "--key",
        metavar="COL",
        default=None,
        help="Column to use as the record key.",
    )
    compare_parser.set_defaults(merkle_handler="compare", handler=handle_compare)
