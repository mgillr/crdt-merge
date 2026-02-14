# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Migration command for the crdt-merge CLI.

Wraps the existing ``crdt_merge.cli.migrate`` module and exposes it as
the ``migrate`` sub-command with an optional ``validate`` action.

Sub-commands
------------
* ``migrate <config>``            -- Run a migration from a config file.
* ``migrate <config> --validate`` -- Validate the config without running it.
* ``migrate <config> --schema``   -- Emit the inferred schema for the config.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register the ``migrate`` sub-command.

    Parameters
    ----------
    subparsers:
        The root-level subparsers action returned by
        :meth:`argparse.ArgumentParser.add_subparsers`.
    """
    p = subparsers.add_parser(
        "migrate",
        help="Run or validate a migration config.",
        description=(
            "Execute a data migration described by a YAML/JSON "
            "configuration file.  The migration engine applies CRDT "
            "merge strategies to reconcile sources into a single target."
        ),
        epilog=(
            "examples:\n"
            "  crdt-merge migrate config.yaml\n"
            "  crdt-merge migrate config.yaml --validate\n"
            "  crdt-merge migrate config.yaml --schema --format json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "config_file",
        help="Path to the migration configuration file (YAML or JSON).",
    )
    p.add_argument(
        "--output", "-o",
        metavar="PATH",
        default=None,
        dest="migrate_output",
        help=(
            "Write migration output to PATH.  Overrides any output path "
            "specified in the config file."
        ),
    )
    p.add_argument(
        "--validate",
        action="store_true",
        default=False,
        help=(
            "Validate the configuration file and exit without running "
            "the migration."
        ),
    )
    p.add_argument(
        "--schema",
        action="store_true",
        default=False,
        help=(
            "Infer and emit the target schema from the config.  "
            "Combine with --format to choose the output representation."
        ),
    )
    p.add_argument(
        "--format",
        choices=["code", "schema", "json"],
        default="json",
        dest="migrate_format",
        help=(
            "Output format for --schema (default: json).  "
            "'code' emits a Python dataclass; 'schema' emits JSON Schema."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Simulate the migration without writing any output.",
    )
    p.set_defaults(handler=handle_migrate)


def handle_migrate(args: argparse.Namespace, formatter: "OutputFormatter") -> None:
    """Execute or validate a migration.

    Parameters
    ----------
    args:
        Parsed CLI arguments.
    formatter:
        An :class:`OutputFormatter` used for output.
    """
    config_path: str = args.config_file

    # ── validate only ─────────────────────────────────────────────────
    if args.validate:
        _do_validate(config_path, formatter)
        return

    # ── schema inference ──────────────────────────────────────────────
    if args.schema:
        _do_schema(config_path, args.migrate_format, formatter)
        return

    # ── full migration ────────────────────────────────────────────────
    _do_migrate(config_path, args, formatter)


# ── internal dispatch ─────────────────────────────────────────────────────


def _do_validate(config_path: str, formatter: "OutputFormatter") -> None:
    """Validate a migration config and report errors.

    Parameters
    ----------
    config_path:
        Path to the configuration file.
    formatter:
        Output formatter for structured results.
    """
    try:
        from crdt_merge.cli.migrate import migrate_config
    except ImportError as exc:
        raise SystemExit(
            "error: migrate requires the crdt_merge.cli.migrate "
            f"module: {exc}"
        ) from exc

    config = migrate_config(config_path)
    errors = config.validate()

    if errors:
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise SystemExit(
            f"error: config validation failed with {len(errors)} error(s)"
        )

    try:
        formatter.auto({"status": "ok", "config": config_path})
    except Exception:
        print(f"ok: {config_path} is valid", file=sys.stderr)


def _do_schema(
    config_path: str,
    fmt: str,
    formatter: "OutputFormatter",
) -> None:
    """Infer and emit the target schema for a migration config.

    Parameters
    ----------
    config_path:
        Path to the configuration file.
    fmt:
        One of ``"code"``, ``"schema"``, or ``"json"``.
    formatter:
        Output formatter.
    """
    try:
        from crdt_merge.cli.migrate import migrate_config_to_schema
    except ImportError as exc:
        raise SystemExit(
            "error: schema inference requires the crdt_merge.cli.migrate "
            f"module: {exc}"
        ) from exc

    schema = migrate_config_to_schema(config_path, output_format=fmt)

    if isinstance(schema, str):
        print(schema, file=sys.stdout)
    else:
        try:
            formatter.auto(schema)
        except Exception:
            import json as _json

            print(
                _json.dumps(schema, indent=2, ensure_ascii=False),
                file=sys.stdout,
            )


def _do_migrate(
    config_path: str,
    args: argparse.Namespace,
    formatter: "OutputFormatter",
) -> None:
    """Run the full migration pipeline.

    Parameters
    ----------
    config_path:
        Path to the configuration file.
    args:
        Full parsed CLI arguments (used for ``--dry-run``,
        ``--migrate_output``, etc.).
    formatter:
        Output formatter.
    """
    try:
        from crdt_merge.cli.migrate import cli_migrate
    except ImportError as exc:
        raise SystemExit(
            "error: migration requires the crdt_merge.cli.migrate "
            f"module: {exc}"
        ) from exc

    output_path = getattr(args, "migrate_output", None) or getattr(
        args, "output", None
    )

    result = cli_migrate(
        config_path,
        output=output_path,
        dry_run=args.dry_run,
    )

    if result is None:
        # cli_migrate handled output internally (e.g. wrote files).
        return

    if output_path:
        try:
            from crdt_merge.cli._util import write_data

            write_data(result, output_path)
        except ImportError:
            import json as _json

            with open(output_path, "w", encoding="utf-8") as fh:
                _json.dump(result, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
    else:
        try:
            formatter.auto(result)
        except Exception:
            print(str(result), file=sys.stdout)
