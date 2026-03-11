# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI commands for gossip protocol operations (state management, sync, digest).

Registered sub-commands
-----------------------
* ``gossip init``   -- Initialize an empty gossip state file.
* ``gossip update`` -- Update a key in the gossip state.
* ``gossip digest`` -- Output a digest summary of the gossip state.
* ``gossip sync``   -- Synchronize two gossip states via anti-entropy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from crdt_merge.cli._output import OutputFormatter

EPILOG = """\
examples:
  %(prog)s init --node node-1 --state-file state_a.json
  %(prog)s update state_a.json username '"alice"'
  %(prog)s update state_a.json config '{"timeout": 30}'
  %(prog)s digest state_a.json
  %(prog)s sync state_a.json state_b.json --output reconciled.json
"""

# ---------------------------------------------------------------------------
# Lazy imports
# ---------------------------------------------------------------------------

_DEPENDENCY_MSG = (
    "Error: crdt_merge.gossip is not installed.\n"
    "Install it with:  pip install crdt-merge[gossip]"
)


def _lazy_import_gossip():
    """Lazily import gossip module to avoid heavy dependencies at CLI startup."""
    try:
        from crdt_merge.gossip import GossipEntry, GossipState, anti_entropy
    except ImportError as exc:
        print(_DEPENDENCY_MSG, file=sys.stderr)
        raise SystemExit(1) from exc
    return GossipState, GossipEntry, anti_entropy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_state_file(path: str):
    """Load a ``GossipState`` from a JSON file."""
    GossipState, _, _ = _lazy_import_gossip()
    filepath = Path(path)
    if not filepath.exists():
        print(f"Error: state file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    return GossipState.from_dict(data)


def _save_state_file(state, path: str) -> None:
    """Serialize a ``GossipState`` to a JSON file."""
    filepath = Path(path)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_init(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Create an empty GossipState and save it to a JSON file."""
    GossipState, _, _ = _lazy_import_gossip()

    state = GossipState(node_id=args.node)
    _save_state_file(state, args.state_file)

    formatter.success(
        f"Initialized gossip state for node '{args.node}' at {args.state_file}"
    )


def handle_update(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Load state, update a key with the given JSON value, and save."""
    state = _load_state_file(args.state_file)

    try:
        value = json.loads(args.value_json)
    except json.JSONDecodeError as exc:
        print(
            f"Error: invalid JSON value: {args.value_json}\n"
            f"  Detail: {exc}\n"
            f"  Hint: wrap strings in double quotes, e.g. '\"hello\"'",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    state.update(args.key, value)
    _save_state_file(state, args.state_file)

    formatter.success(f"Updated key '{args.key}' in {args.state_file}")


def handle_digest(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Load state and output a digest summary."""
    state = _load_state_file(args.state_file)

    digest = state.digest()
    digest_data = digest if isinstance(digest, dict) else digest.to_dict()
    formatter.json(digest_data)


def handle_sync(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Load local and remote states, run anti-entropy, and output reconciled state."""
    _, _, anti_entropy = _lazy_import_gossip()

    local_state = _load_state_file(args.local_state)
    remote_state = _load_state_file(args.remote_state)

    local_digest = local_state.digest()
    remote_digest = remote_state.digest()
    diff = anti_entropy(local_digest, remote_digest)

    if args.output:
        import json as _json
        with open(args.output, "w", encoding="utf-8") as fh:
            _json.dump(diff, fh, indent=2)
            fh.write("\n")
        formatter.success(f"Anti-entropy diff written to {args.output}")
    else:
        formatter.json(diff)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``gossip`` sub-commands (init, update, digest, sync)."""
    gossip_parser = subparsers.add_parser(
        "gossip",
        help="Gossip protocol state management and synchronization",
        epilog=EPILOG,
        formatter_class=lambda prog: __import__(
            "argparse"
        ).RawDescriptionHelpFormatter(prog, max_help_position=40),
    )
    gossip_sub = gossip_parser.add_subparsers(dest="gossip_command", required=True)

    # -- gossip init ----------------------------------------------------------
    init_p = gossip_sub.add_parser(
        "init",
        help="Initialize an empty gossip state file",
    )
    init_p.add_argument(
        "--node",
        required=True,
        help="Node identifier for this gossip state",
    )
    init_p.add_argument(
        "--state-file",
        required=True,
        metavar="PATH",
        help="Output file path for the gossip state JSON",
    )
    init_p.set_defaults(handler=handle_init)

    # -- gossip update --------------------------------------------------------
    update_p = gossip_sub.add_parser(
        "update",
        help="Update a key in the gossip state",
    )
    update_p.add_argument("state_file", help="Path to the gossip state JSON file")
    update_p.add_argument("key", help="Key to update")
    update_p.add_argument(
        "value_json",
        help="Value as a JSON literal (e.g. '\"hello\"', '42', '{\"a\": 1}')",
    )
    update_p.set_defaults(handler=handle_update)

    # -- gossip digest --------------------------------------------------------
    digest_p = gossip_sub.add_parser(
        "digest",
        help="Output a digest summary of the gossip state",
    )
    digest_p.add_argument("state_file", help="Path to the gossip state JSON file")
    digest_p.set_defaults(handler=handle_digest)

    # -- gossip sync ----------------------------------------------------------
    sync_p = gossip_sub.add_parser(
        "sync",
        help="Synchronize two gossip states via anti-entropy",
    )
    sync_p.add_argument("local_state", help="Path to the local state JSON file")
    sync_p.add_argument("remote_state", help="Path to the remote state JSON file")
    sync_p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Output file path for the reconciled state (default: stdout)",
    )
    sync_p.set_defaults(handler=handle_sync)
