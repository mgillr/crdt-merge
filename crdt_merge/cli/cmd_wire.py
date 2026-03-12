# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI handlers for the ``wire`` command group.

Subcommands
-----------
- ``wire serialize <file>``    -- serialise a CRDT/data to binary wire format
- ``wire deserialize <file>``  -- deserialise a binary wire file to JSON
- ``wire inspect <file>``      -- peek at the wire format type header
- ``wire size <file>``         -- show wire format size statistics
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
# Constants
# ---------------------------------------------------------------------------

WIRE_CRDT_TYPES = ("gcounter", "pncounter", "lww", "orset", "lwwmap", "generic")

_CRDT_CLASS_MAP = {
    "gcounter": "GCounter",
    "pncounter": "PNCounter",
    "lww": "LWWRegister",
    "orset": "ORSet",
    "lwwmap": "LWWMap",
}

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_serialize(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Serialise input data to the crdt-merge binary wire format."""
    from crdt_merge.wire import serialize  # lazy

    input_path = args.file
    crdt_type = args.type
    output_path = args.output
    compress = args.compress

    # Load the input JSON.
    try:
        with open(input_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        formatter.error(f"Invalid JSON in {input_path!r}: {exc}")
        sys.exit(1)
    except OSError as exc:
        formatter.error(f"Could not read {input_path!r}: {exc}")
        sys.exit(1)

    # For typed CRDTs, construct the appropriate instance.
    payload = data
    if crdt_type != "generic":
        import importlib

        class_name = _CRDT_CLASS_MAP.get(crdt_type)
        if class_name is None:
            formatter.error(f"Unknown CRDT type {crdt_type!r}.")
            sys.exit(1)

        try:
            crdt_mod = importlib.import_module("crdt_merge.core")
            crdt_cls = getattr(crdt_mod, class_name)
        except (ImportError, AttributeError) as exc:
            formatter.error(f"Cannot load CRDT class {class_name!r}: {exc}")
            sys.exit(1)

        try:
            payload = crdt_cls.from_dict(data) if hasattr(crdt_cls, "from_dict") else crdt_cls(data)
        except Exception as exc:
            formatter.error(
                f"Failed to construct {class_name} from input data: {exc}"
            )
            sys.exit(1)

    # Serialise.
    try:
        wire_bytes = serialize(payload, compress=compress)
    except Exception as exc:
        formatter.error(f"Serialisation failed: {exc}")
        sys.exit(1)

    # Determine output path.
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".crdt"

    try:
        with open(output_path, "wb") as fh:
            fh.write(wire_bytes)
    except OSError as exc:
        formatter.error(f"Could not write to {output_path!r}: {exc}")
        sys.exit(1)

    formatter.success(
        f"Serialised {crdt_type} to {output_path} "
        f"({len(wire_bytes):,} bytes"
        f"{', compressed' if compress else ''})"
    )


def handle_deserialize(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Deserialise a binary wire file and output its contents as JSON."""
    from crdt_merge.wire import deserialize  # lazy

    input_path = args.file
    output_path = args.output

    try:
        with open(input_path, "rb") as fh:
            wire_bytes = fh.read()
    except OSError as exc:
        formatter.error(f"Could not read {input_path!r}: {exc}")
        sys.exit(1)

    try:
        obj = deserialize(wire_bytes)
    except Exception as exc:
        formatter.error(f"Deserialisation failed: {exc}")
        sys.exit(1)

    # Convert to a JSON-friendly representation.
    if hasattr(obj, "to_dict"):
        result = obj.to_dict()
    elif hasattr(obj, "__dict__"):
        result = obj.__dict__
    else:
        result = obj

    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as fh:
                json.dump(result, fh, indent=2, default=str)
                fh.write("\n")
            formatter.success(f"Deserialised output written to {output_path}")
        except OSError as exc:
            formatter.error(f"Could not write to {output_path!r}: {exc}")
            sys.exit(1)
    else:
        formatter.json(result)


def handle_inspect(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Inspect a wire format file and display its type information."""
    from crdt_merge.wire import peek_type  # lazy

    input_path = args.file

    try:
        with open(input_path, "rb") as fh:
            wire_bytes = fh.read()
    except OSError as exc:
        formatter.error(f"Could not read {input_path!r}: {exc}")
        sys.exit(1)

    try:
        type_info = peek_type(wire_bytes)
    except Exception as exc:
        formatter.error(f"Failed to inspect wire format: {exc}")
        sys.exit(1)

    # type_info may be a string, dict, or named object.
    if isinstance(type_info, str):
        info = {"type": type_info, "file": input_path}
    elif isinstance(type_info, dict):
        info = type_info
        info.setdefault("file", input_path)
    else:
        info = {
            "type": getattr(type_info, "type_name", str(type_info)),
            "version": getattr(type_info, "version", None),
            "compressed": getattr(type_info, "compressed", None),
            "file": input_path,
        }
        # Remove None values for cleaner output.
        info = {k: v for k, v in info.items() if v is not None}

    formatter.auto([info], title="Wire Format Inspection")


def handle_size(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Display size statistics for a wire format file."""
    from crdt_merge.wire import wire_size  # lazy

    input_path = args.file

    try:
        with open(input_path, "rb") as fh:
            wire_bytes = fh.read()
    except OSError as exc:
        formatter.error(f"Could not read {input_path!r}: {exc}")
        sys.exit(1)

    try:
        stats = wire_size(wire_bytes)
    except Exception as exc:
        formatter.error(f"Failed to compute size stats: {exc}")
        sys.exit(1)

    # stats may be a dict or an object with attributes.
    if isinstance(stats, dict):
        size_info = stats
    else:
        size_info = {
            "total_bytes": getattr(stats, "total_bytes", len(wire_bytes)),
            "header_bytes": getattr(stats, "header_bytes", None),
            "payload_bytes": getattr(stats, "payload_bytes", None),
            "compression_ratio": getattr(stats, "compression_ratio", None),
        }
        size_info = {k: v for k, v in size_info.items() if v is not None}

    size_info["file"] = input_path
    size_info["file_size_bytes"] = os.path.getsize(input_path)

    formatter.auto([size_info], title="Wire Format Size")


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_HANDLER_MAP = {
    "serialize": handle_serialize,
    "deserialize": handle_deserialize,
    "inspect": handle_inspect,
    "size": handle_size,
}

# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``wire`` command and its sub-subparsers."""
    wire_parser = subparsers.add_parser(
        "wire",
        help="Serialise, deserialise, and inspect the crdt-merge binary wire format.",
        epilog=(
            "Examples:\n"
            "  crdt-merge wire serialize state.json --type gcounter --output state.crdt\n"
            "  crdt-merge wire deserialize state.crdt --output state_out.json\n"
            "  crdt-merge wire inspect state.crdt\n"
            "  crdt-merge wire size state.crdt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = wire_parser.add_subparsers(dest="wire_sub", metavar="SUBCOMMAND")

    # --- wire serialize ---
    ser_parser = sub.add_parser(
        "serialize",
        help="Serialise a JSON file to binary wire format.",
        epilog=(
            "Examples:\n"
            "  crdt-merge wire serialize counter.json --type gcounter\n"
            "  crdt-merge wire serialize data.json --type generic --compress\n"
            "  crdt-merge wire serialize state.json --type lwwmap --output state.crdt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ser_parser.add_argument(
        "file",
        metavar="FILE",
        help="Input JSON file to serialise.",
    )
    ser_parser.add_argument(
        "--type", "-t",
        choices=WIRE_CRDT_TYPES,
        required=True,
        metavar="TYPE",
        help=(
            "CRDT type for serialisation. "
            f"Choices: {', '.join(WIRE_CRDT_TYPES)}."
        ),
    )
    ser_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Output file path (default: <input>.crdt).",
    )
    ser_parser.add_argument(
        "--compress", "-c",
        action="store_true",
        default=False,
        help="Enable compression on the wire payload.",
    )
    ser_parser.set_defaults(wire_handler="serialize", handler=handle_serialize)

    # --- wire deserialize ---
    deser_parser = sub.add_parser(
        "deserialize",
        help="Deserialise a binary wire file to JSON.",
        epilog=(
            "Examples:\n"
            "  crdt-merge wire deserialize state.crdt\n"
            "  crdt-merge wire deserialize state.crdt --output state.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    deser_parser.add_argument(
        "file",
        metavar="FILE",
        help="Binary wire format file to deserialise.",
    )
    deser_parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        help="Write JSON output to this file (default: stdout).",
    )
    deser_parser.set_defaults(wire_handler="deserialize", handler=handle_deserialize)

    # --- wire inspect ---
    inspect_parser = sub.add_parser(
        "inspect",
        help="Inspect the type header of a wire format file.",
        epilog=(
            "Examples:\n"
            "  crdt-merge wire inspect state.crdt\n"
            "  crdt-merge wire inspect payload.bin\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    inspect_parser.add_argument(
        "file",
        metavar="FILE",
        help="Binary wire format file to inspect.",
    )
    inspect_parser.set_defaults(wire_handler="inspect", handler=handle_inspect)

    # --- wire size ---
    size_parser = sub.add_parser(
        "size",
        help="Show size statistics for a wire format file.",
        epilog=(
            "Examples:\n"
            "  crdt-merge wire size state.crdt\n"
            "  crdt-merge wire size compressed_payload.crdt\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    size_parser.add_argument(
        "file",
        metavar="FILE",
        help="Binary wire format file to analyse.",
    )
    size_parser.set_defaults(wire_handler="size", handler=handle_size)
