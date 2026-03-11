# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""crdt-merge CLI — production-grade command-line interface.

Entry point for the ``crdt-merge`` command. Builds the full argparse tree,
loads configuration, initialises the output formatter, and dispatches to
the appropriate command handler.

Usage::

    crdt-merge merge a.csv b.csv --key id
    crdt-merge model strategies
    crdt-merge doctor
    crdt-merge repl
"""

from __future__ import annotations

import sys
from typing import Optional


def main(argv: Optional[list] = None) -> None:
    """Entry point for the crdt-merge CLI.

    Args:
        argv: Command-line arguments. If ``None``, uses ``sys.argv[1:]``.
    """
    from crdt_merge.cli._parser import build_parser
    from crdt_merge.cli._config import load_config
    from crdt_merge.cli._output import OutputFormatter

    parser = build_parser()
    args = parser.parse_args(argv)

    # Load config with precedence: global < project < explicit < env < flags
    config = load_config(getattr(args, "config", None))

    # Determine output format with auto-detection
    fmt = args.format
    if fmt is None:
        # Check config
        fmt = config.get("cli", {}).get("format")
    if fmt is None:
        # Auto-detect: table for TTY, json for pipes
        fmt = "table" if sys.stdout.isatty() else "json"

    # Determine color
    color = not args.no_color
    config_color = config.get("cli", {}).get("color")
    if config_color is not None and not isinstance(config_color, bool):
        config_color = str(config_color).lower() not in ("0", "false", "no")
    if config_color is False:
        color = False
    if not sys.stdout.isatty():
        color = False

    # Build formatter
    output_path = getattr(args, "output", None)
    formatter = OutputFormatter(
        format=fmt,
        color=color,
        stream=sys.stdout,
        output_path=output_path,
    )

    # Dispatch
    handler = getattr(args, "handler", None)
    if handler is None:
        # No command given — show help
        parser.print_help()
        sys.exit(0)

    try:
        handler(args, formatter)
    except KeyboardInterrupt:
        sys.exit(130)
    except ImportError as exc:
        _handle_import_error(exc, formatter, args)
        sys.exit(1)
    except Exception as exc:
        if getattr(args, "verbose", 0) >= 2:
            import traceback
            traceback.print_exc()
        else:
            formatter.error(str(exc))
        sys.exit(1)


def _handle_import_error(
    exc: ImportError, formatter: object, args: object
) -> None:
    """Format ImportError with helpful install instructions."""
    from crdt_merge.cli._util import EXTRA_PACKAGES

    msg = str(exc)
    missing_pkg = ""

    # Try to extract package name from "No module named 'foo'"
    if "No module named" in msg:
        missing_pkg = msg.split("'")[1].split(".")[0] if "'" in msg else ""

    # Find the extra that provides this package
    install_hint = ""
    for extra, packages in EXTRA_PACKAGES.items():
        if missing_pkg in packages:
            install_hint = f"pip install crdt-merge[{extra}]"
            break

    if install_hint:
        formatter.error(  # type: ignore[attr-defined]
            f"{msg}\n\n  This feature requires an optional dependency.\n"
            f"  Install with: {install_hint}"
        )
    else:
        formatter.error(str(exc))  # type: ignore[attr-defined]
