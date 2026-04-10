# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Accelerator CLI commands: list, duckdb, sqlite, polars, flight, airbyte, dbt."""

from __future__ import annotations

import argparse
import sys
from typing import Any


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register accelerator commands."""
    p = subparsers.add_parser(
        "accel", help="Manage accelerators and ecosystem integrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge accel list\n"
            "  crdt-merge accel duckdb install\n"
            "  crdt-merge accel flight serve --port 8815\n"
        ),
    )
    sp = p.add_subparsers(dest="accel_cmd")

    # list
    list_p = sp.add_parser("list", help="List all registered accelerators")
    list_p.set_defaults(handler=handle_accel_list)

    # duckdb
    duck_p = sp.add_parser("duckdb", help="DuckDB UDF integration")
    duck_sp = duck_p.add_subparsers(dest="duckdb_cmd")

    duck_install = duck_sp.add_parser("install", help="Register CRDT merge UDFs")
    duck_install.set_defaults(handler=handle_duckdb_install)

    duck_query = duck_sp.add_parser("query", help="Run SQL with CRDT merge UDFs")
    duck_query.add_argument("sql", help="SQL query string")
    duck_query.set_defaults(handler=handle_duckdb_query)

    # sqlite
    sqlite_p = sp.add_parser("sqlite", help="SQLite extension")
    sqlite_sp = sqlite_p.add_subparsers(dest="sqlite_cmd")

    sqlite_install = sqlite_sp.add_parser("install", help="Register extension functions")
    sqlite_install.add_argument("db_path", help="SQLite database path")
    sqlite_install.set_defaults(handler=handle_sqlite_install)

    # polars
    polars_p = sp.add_parser("polars", help="Polars plugin")
    polars_sp = polars_p.add_subparsers(dest="polars_cmd")

    polars_reg = polars_sp.add_parser("register", help="Register plugin expressions")
    polars_reg.set_defaults(handler=handle_polars_register)

    # flight
    flight_p = sp.add_parser("flight", help="Arrow Flight merge server")
    flight_sp = flight_p.add_subparsers(dest="flight_cmd")

    flight_serve = flight_sp.add_parser("serve", help="Start merge server")
    flight_serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    flight_serve.add_argument("--port", type=int, default=8815, help="Bind port")
    flight_serve.set_defaults(handler=handle_flight_serve)

    # airbyte
    airbyte_p = sp.add_parser("airbyte", help="Airbyte connector")
    airbyte_sp = airbyte_p.add_subparsers(dest="airbyte_cmd")

    airbyte_spec = airbyte_sp.add_parser("spec", help="Print connector spec")
    airbyte_spec.set_defaults(handler=handle_airbyte_spec)

    airbyte_check = airbyte_sp.add_parser("check", help="Check connection")
    airbyte_check.add_argument("config", help="Config file path")
    airbyte_check.set_defaults(handler=handle_airbyte_check)

    # dbt
    dbt_p = sp.add_parser("dbt", help="dbt package scaffolding")
    dbt_sp = dbt_p.add_subparsers(dest="dbt_cmd")

    dbt_init = dbt_sp.add_parser("init", help="Scaffold dbt package files")
    dbt_init.set_defaults(handler=handle_dbt_init)


def handle_accel_list(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.accelerators import ACCELERATOR_REGISTRY

    # Force-import known accelerator modules to populate registry
    accel_modules = [
        "crdt_merge.accelerators.duckdb_udf",
        "crdt_merge.accelerators.sqlite_ext",
        "crdt_merge.accelerators.polars_plugin",
        "crdt_merge.accelerators.flight_server",
        "crdt_merge.accelerators.airbyte",
        "crdt_merge.accelerators.dbt_package",
        "crdt_merge.accelerators.ducklake",
        "crdt_merge.accelerators.streamlit_ui",
    ]
    for mod_name in accel_modules:
        try:
            __import__(mod_name)
        except (ImportError, Exception):
            pass  # nosec B110

    rows = []
    for name, cls in ACCELERATOR_REGISTRY.items():
        instance = None
        try:
            instance = cls()
        except Exception:
            pass  # nosec B110 -- intentionally silent

        available = False
        version = "-"
        if instance:
            if hasattr(instance, "is_available"):
                available = instance.is_available()
            version = getattr(instance, "version", "-")

        rows.append({
            "Name": name,
            "Version": version,
            "Available": "Yes" if available else "No",
        })

    if not rows:
        formatter.warning("No accelerators registered.")
        return

    formatter.auto(rows, title="Registered Accelerators")


def handle_duckdb_install(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.duckdb_udf import DuckDBMergeUDF
        udf = DuckDBMergeUDF()
        if hasattr(udf, "install"):
            udf.install()
            formatter.success("DuckDB CRDT merge UDFs registered successfully.")
        else:
            formatter.success("DuckDB accelerator loaded.")
    except ImportError:
        formatter.error("DuckDB not installed. Install with: pip install duckdb")
        sys.exit(1)


def handle_duckdb_query(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.duckdb_udf import DuckDBMergeUDF
        udf = DuckDBMergeUDF()
        if hasattr(udf, "query"):
            result = udf.query(args.sql)
            if isinstance(result, list):
                formatter.auto(result, title="Query Result")
            else:
                formatter.message(str(result))
        else:
            formatter.error("DuckDB query not available.")
    except ImportError:
        formatter.error("DuckDB not installed. Install with: pip install duckdb")
        sys.exit(1)


def handle_sqlite_install(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.sqlite_ext import SQLiteMergeExt
        ext = SQLiteMergeExt()
        if hasattr(ext, "install"):
            ext.install(args.db_path)
            formatter.success(f"SQLite CRDT functions registered in {args.db_path}")
        else:
            formatter.success("SQLite accelerator loaded.")
    except ImportError:
        formatter.error("SQLite accelerator not available.")
        sys.exit(1)


def handle_polars_register(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.polars_plugin import PolarsMergePlugin
        plugin = PolarsMergePlugin()
        if hasattr(plugin, "register"):
            plugin.register()
            formatter.success("Polars CRDT merge expressions registered.")
        else:
            formatter.success("Polars plugin loaded.")
    except ImportError:
        formatter.error(
            "Polars not installed. Install with: pip install crdt-merge[fast]"
        )
        sys.exit(1)


def handle_flight_serve(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.flight_server import FlightMergeServer
        server = FlightMergeServer()
        formatter.message(f"Starting Arrow Flight server on {args.host}:{args.port}...")
        if hasattr(server, "serve"):
            server.serve(host=args.host, port=args.port)
        else:
            formatter.error("FlightMergeServer.serve() not available.")
    except ImportError:
        formatter.error(
            "PyArrow Flight not installed. Install with: pip install pyarrow"
        )
        sys.exit(1)


def handle_airbyte_spec(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.airbyte import AirbyteConnector
        conn = AirbyteConnector()
        if hasattr(conn, "spec"):
            spec = conn.spec()
            formatter.json(spec if isinstance(spec, dict) else {"spec": str(spec)})
        else:
            formatter.warning("Airbyte spec not available.")
    except ImportError:
        formatter.error("Airbyte accelerator not available.")
        sys.exit(1)


def handle_airbyte_check(args: argparse.Namespace, formatter: Any) -> None:
    import json as _json
    try:
        from crdt_merge.accelerators.airbyte import AirbyteConnector
        with open(args.config) as f:
            config = _json.load(f)
        conn = AirbyteConnector()
        if hasattr(conn, "check"):
            result = conn.check(config)
            formatter.json(
                result if isinstance(result, dict) else {"status": str(result)}
            )
        else:
            formatter.warning("Airbyte check not available.")
    except ImportError:
        formatter.error("Airbyte accelerator not available.")
        sys.exit(1)


def handle_dbt_init(args: argparse.Namespace, formatter: Any) -> None:
    try:
        from crdt_merge.accelerators.dbt_package import DbtPackage
        pkg = DbtPackage()
        output = getattr(args, "output", None) or "."
        if hasattr(pkg, "scaffold"):
            pkg.scaffold(output)
            formatter.success(f"dbt package scaffolded in {output}")
        else:
            formatter.success("dbt package accelerator loaded.")
    except ImportError:
        formatter.error("dbt accelerator not available.")
        sys.exit(1)
