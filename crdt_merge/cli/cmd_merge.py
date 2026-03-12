# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for merging, diffing, deduplication, and streaming.

Registered sub-commands
-----------------------
* ``merge``  -- CRDT-aware merge of two data files.
* ``diff``   -- Compute a structured diff between two data files.
* ``dedup``  -- Remove duplicate records from a single file.
* ``stream`` -- Streaming merge of two sources with batched output.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``merge``, ``diff``, ``dedup``, and ``stream`` commands."""

    _register_merge(subparsers)
    _register_diff(subparsers)
    _register_dedup(subparsers)
    _register_stream(subparsers)


# -- merge ------------------------------------------------------------------

def _register_merge(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "merge",
        help="CRDT-aware merge of two data files.",
        description=(
            "Merge two CSV, JSON, or Parquet files using CRDT strategies. "
            "Rows are matched by --key; conflicts are resolved per-column "
            "using the --strategy flag or a --schema file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  crdt-merge merge a.csv b.csv --key id\n"
            "  crdt-merge merge a.csv b.csv -k id --prefer latest\n"
            "  crdt-merge merge a.csv b.csv -k id --strategy name=LWW "
            "--strategy score=MAX\n"
            "  crdt-merge merge a.json b.json -k id --provenance "
            "--audit -o merged.json\n"
        ),
    )
    p.add_argument("file_a", help="Path to the first input file.")
    p.add_argument("file_b", help="Path to the second input file.")
    p.add_argument(
        "--key", "-k",
        required=True,
        help="Column name (or comma-separated names) used as the merge key.",
    )
    p.add_argument(
        "--prefer",
        choices=["a", "b", "latest"],
        default=None,
        help="Global conflict-resolution preference (default: CRDT semantics).",
    )
    p.add_argument(
        "--strategy",
        action="append",
        metavar="COL=STRATEGY",
        default=None,
        help=(
            "Per-column strategy override.  May be repeated.  "
            "Example: --strategy score=MAX --strategy name=LWW"
        ),
    )
    p.add_argument(
        "--dedup",
        action="store_true",
        default=False,
        help="De-duplicate the merged result before writing output.",
    )
    p.add_argument(
        "--schema",
        metavar="PATH",
        default=None,
        help="Path to a YAML/JSON merge-schema file.",
    )
    p.add_argument(
        "--timestamp-col",
        metavar="COL",
        default=None,
        help="Column containing timestamps (used by LWW / --prefer latest).",
    )
    p.add_argument(
        "--provenance",
        action="store_true",
        default=False,
        help="Attach provenance metadata to every output row.",
    )
    p.add_argument(
        "--audit",
        action="store_true",
        default=False,
        help="Write an audit log alongside the merged output.",
    )
    p.add_argument(
        "--encrypt",
        metavar="KEY",
        default=None,
        help="Encrypt the output file with the given key.",
    )
    p.add_argument(
        "--encrypt-backend",
        choices=["fernet", "age", "gpg"],
        default="fernet",
        help="Encryption backend to use (default: fernet).",
    )
    p.set_defaults(handler=handle_merge)


# -- diff -------------------------------------------------------------------

def _register_diff(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "diff",
        help="Compute a structured diff between two data files.",
        description=(
            "Compare two files row-by-row using a merge key and report "
            "added, removed, and changed records."
        ),
    )
    p.add_argument("file_a", help="Path to the base file.")
    p.add_argument("file_b", help="Path to the comparison file.")
    p.add_argument(
        "--key", "-k",
        required=True,
        help="Column name used as the diff key.",
    )
    p.add_argument(
        "--only",
        choices=["added", "removed", "changed"],
        default=None,
        help="Limit output to a single change type.",
    )
    p.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Print summary statistics instead of the full diff.",
    )
    p.set_defaults(handler=handle_diff)


# -- dedup ------------------------------------------------------------------

def _register_dedup(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "dedup",
        help="Remove duplicate records from a file.",
        description=(
            "Deduplicate records using exact matching, fuzzy matching, "
            "or MinHash locality-sensitive hashing."
        ),
    )
    p.add_argument("file", help="Path to the input file.")
    p.add_argument(
        "--method",
        choices=["exact", "fuzzy", "minhash"],
        default="exact",
        help="Deduplication method (default: exact).",
    )
    p.add_argument(
        "--key",
        default=None,
        help="Column(s) to consider for dedup (default: all columns).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Similarity threshold for fuzzy/minhash methods (default: 0.8).",
    )
    p.add_argument(
        "--num-perm",
        type=int,
        default=128,
        help="Number of permutations for MinHash (default: 128).",
    )
    p.set_defaults(handler=handle_dedup)


# -- stream -----------------------------------------------------------------

def _register_stream(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "stream",
        help="Streaming merge of two data sources.",
        description=(
            "Merge two potentially large or unbounded sources using a "
            "batched streaming approach.  Suitable for files that do not "
            "fit in memory."
        ),
    )
    p.add_argument("source_a", help="Path or URI of the first source.")
    p.add_argument("source_b", help="Path or URI of the second source.")
    p.add_argument(
        "--key", "-k",
        required=True,
        help="Column name used as the merge key.",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Number of rows per batch (default: 5000).",
    )
    p.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Print throughput and merge statistics on completion.",
    )
    p.set_defaults(handler=handle_stream)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _parse_strategy_flags(
    raw: Optional[List[str]],
) -> Optional[Dict[str, str]]:
    """Parse ``['col=STRATEGY', ...]`` into ``{'col': 'STRATEGY', ...}``.

    Returns ``None`` when *raw* is ``None`` or empty.

    Raises
    ------
    SystemExit
        If a flag cannot be split on ``=``.
    """
    if not raw:
        return None

    mapping: Dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            print(
                f"error: invalid --strategy value {entry!r}; "
                "expected COL=STRATEGY",
                file=sys.stderr,
            )
            raise SystemExit(2)
        col, strategy = entry.split("=", 1)
        mapping[col.strip()] = strategy.strip().upper()
    return mapping


def handle_merge(args: argparse.Namespace, formatter: "OutputFormatter") -> None:
    """Execute the ``merge`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.cli._util import load_data, write_data
    except ImportError as exc:
        print(f"error: missing required module: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        from crdt_merge.cli._progress import spinner
    except ImportError:
        # Graceful degradation -- provide a no-op context manager.
        from contextlib import nullcontext as spinner  # type: ignore[misc]

    from crdt_merge.dataframe import merge as dataframe_merge  # type: ignore[import-untyped]

    # -- load inputs --------------------------------------------------------
    with spinner("Loading file A..."):  # type: ignore[call-arg]
        data_a = load_data(args.file_a)
    with spinner("Loading file B..."):  # type: ignore[call-arg]
        data_b = load_data(args.file_b)

    # -- build merge kwargs -------------------------------------------------
    merge_kwargs: Dict[str, Any] = {
        "key": args.key,
    }

    if args.prefer is not None:
        merge_kwargs["prefer"] = args.prefer

    if args.timestamp_col is not None:
        merge_kwargs["timestamp_col"] = args.timestamp_col

    # Per-column strategy overrides
    strategy_map = _parse_strategy_flags(args.strategy)
    if strategy_map is not None:
        try:
            from crdt_merge.strategies import MergeSchema  # type: ignore[import-untyped]

            merge_kwargs["schema"] = MergeSchema.from_dict(strategy_map)
        except ImportError:
            # Fall back to passing the raw dict; the merge function may
            # accept it directly.
            merge_kwargs["strategies"] = strategy_map

    if args.schema is not None:
        try:
            from crdt_merge.strategies import MergeSchema  # type: ignore[import-untyped]

            merge_kwargs["schema"] = MergeSchema.from_file(args.schema)
        except ImportError as exc:
            print(
                f"error: --schema requires crdt_merge.strategies: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

    # -- merge --------------------------------------------------------------
    with spinner("Merging..."):  # type: ignore[call-arg]
        if args.provenance:
            try:
                from crdt_merge.dataframe import merge_with_provenance  # type: ignore[import-untyped]

                result = merge_with_provenance(data_a, data_b, **merge_kwargs)
            except ImportError as exc:
                print(
                    f"error: --provenance requires "
                    f"crdt_merge.dataframe.merge_with_provenance: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from exc
        else:
            result = dataframe_merge(data_a, data_b, **merge_kwargs)

    # -- optional dedup -----------------------------------------------------
    if args.dedup:
        try:
            from crdt_merge.dedup import dedup_records  # type: ignore[import-untyped]

            result, _ = dedup_records(result)
        except ImportError as exc:
            print(
                f"error: --dedup requires crdt_merge.dedup: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

    # -- output -------------------------------------------------------------
    output_path: Optional[str] = getattr(args, "output", None)
    if output_path:
        write_data(result, output_path)
    else:
        formatter.auto(result)


def handle_diff(args: argparse.Namespace, formatter: "OutputFormatter") -> None:
    """Execute the ``diff`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.cli._util import load_data
    except ImportError as exc:
        print(f"error: missing required module: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    from crdt_merge.dataframe import diff as dataframe_diff  # type: ignore[import-untyped]

    data_a = load_data(args.file_a)
    data_b = load_data(args.file_b)

    diff_result = dataframe_diff(data_a, data_b, key=args.key)

    # Filter to a single change type if requested.
    if args.only is not None:
        diff_result = {
            k: v for k, v in diff_result.items() if k == args.only
        }

    if args.stats:
        summary_rows = []
        for category, rows in diff_result.items():
            count = len(rows) if isinstance(rows, list) else rows
            summary_rows.append({"category": category, "count": count})
        formatter.auto(summary_rows, title="Diff Summary")
    else:
        # Print summary first
        if "summary" in diff_result:
            formatter.message(str(diff_result["summary"]))

        # Show each section as a table
        for section in ("added", "removed", "modified"):
            items = diff_result.get(section, [])
            if items and isinstance(items, list):
                formatter.message(f"\n{section.upper()} ({len(items)}):")
                if section == "modified":
                    display = []
                    for m in items:
                        row: Dict[str, Any] = {"key": m.get("key", "")}
                        for col, vals in m.get("changes", {}).items():
                            row[f"{col}_old"] = vals.get("old", "")
                            row[f"{col}_new"] = vals.get("new", "")
                        display.append(row)
                    formatter.auto(display)
                else:
                    formatter.auto(items)


def handle_dedup(args: argparse.Namespace, formatter: "OutputFormatter") -> None:
    """Execute the ``dedup`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.cli._util import load_data, write_data
    except ImportError as exc:
        print(f"error: missing required module: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    data = load_data(args.file)

    try:
        from crdt_merge.dedup import dedup_records  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            f"error: dedup command requires crdt_merge.dedup: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    dedup_kwargs: Dict[str, Any] = {"method": args.method}
    if args.key is not None:
        dedup_kwargs["key"] = args.key
    if args.method in ("fuzzy", "minhash"):
        dedup_kwargs["threshold"] = args.threshold
    if args.method == "minhash":
        dedup_kwargs["num_perm"] = args.num_perm

    # dedup_records returns (deduplicated_list, n_removed)
    dedup_kwargs.pop("key", None)  # dedup_records has no key param
    result, n_removed = dedup_records(data, **dedup_kwargs)

    output_path: Optional[str] = getattr(args, "output", None)
    if output_path:
        write_data(result, output_path)
        formatter.success(f"Deduplicated {len(data)} → {len(result)} rows ({n_removed} removed) → {output_path}")
    else:
        formatter.auto(result)
        formatter.message(f"Removed {n_removed} duplicate(s). {len(result)} unique rows.")


def handle_stream(args: argparse.Namespace, formatter: "OutputFormatter") -> None:
    """Execute the ``stream`` sub-command.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        Output formatter bound to the current session.
    """
    try:
        from crdt_merge.streaming import merge_stream, StreamStats  # type: ignore[import-untyped]
    except ImportError as exc:
        print(
            f"error: stream command requires crdt_merge.streaming: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    try:
        from crdt_merge.cli._progress import ProgressBar
    except ImportError:
        ProgressBar = None  # type: ignore[assignment,misc]

    try:
        from crdt_merge.cli._util import write_data, load_data
    except ImportError as exc:
        print(f"error: missing required module: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        source_a = load_data(args.source_a)
        source_b = load_data(args.source_b)
    except Exception as exc:
        print(f"error: failed to load source data: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    stats = StreamStats()
    progress = ProgressBar(desc="Streaming merge") if ProgressBar is not None else None

    output_path: Optional[str] = getattr(args, "output", None)
    batches_written = 0

    try:
        for batch in merge_stream(
            source_a,
            source_b,
            key=args.key,
            batch_size=args.batch_size,
            stats=stats,
        ):
            batches_written += 1
            if progress is not None:
                progress.update(batches_written)

            if output_path:
                # Append each batch to the output file.
                write_data(batch, output_path, append=(batches_written > 1))
            else:
                formatter.auto(batch)
    finally:
        if progress is not None:
            progress.finish()

    if args.stats:
        formatter.auto(stats.to_dict())
