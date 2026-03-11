# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Observability CLI commands: doctor/health, observe metrics/export/drift."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register observability commands."""
    _register_doctor(subparsers)
    _register_health(subparsers)
    _register_observe(subparsers)


# ── doctor / health ───────────────────────────────────────

def _register_doctor(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "doctor", help="Check environment, dependencies, and accelerators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  crdt-merge doctor\n  crdt-merge doctor --fix\n",
    )
    p.add_argument("--fix", action="store_true",
                    help="Suggest pip install commands for missing extras")
    p.set_defaults(handler=handle_doctor)


def _register_health(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("health", help="Alias for doctor")
    p.add_argument("--fix", action="store_true")
    p.set_defaults(handler=handle_doctor)


def handle_doctor(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._doctor import run_doctor
    results = run_doctor()

    rows = []
    fixes = []
    for item in results:
        status = "OK" if item["available"] else "MISSING"
        rows.append({
            "Component": item["name"],
            "Status": status,
            "Version": item.get("version", "-"),
            "Extra": item.get("extra", "-"),
        })
        if not item["available"] and item.get("install_cmd"):
            fixes.append(item["install_cmd"])

    formatter.auto(rows, title="System Health Check")

    if fixes and args.fix:
        formatter.message("\nSuggested fixes:")
        for fix in fixes:
            formatter.message(f"  {fix}")


# ── observe ───────────────────────────────────────────────

def _register_observe(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "observe", help="Observability: metrics, export, drift detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge observe metrics metrics.json --summary\n"
            "  crdt-merge observe export metrics.json --format prometheus\n"
            "  crdt-merge observe drift metrics.json\n"
        ),
    )
    sp = p.add_subparsers(dest="observe_cmd")

    metrics_p = sp.add_parser("metrics", help="Display merge metrics")
    metrics_p.add_argument("file", help="Metrics file (JSON)")
    metrics_p.add_argument("--summary", action="store_true",
                            help="Show summary only")
    metrics_p.set_defaults(handler=handle_observe_metrics)

    export_p = sp.add_parser("export", help="Export metrics")
    export_p.add_argument("file", help="Metrics file (JSON)")
    export_p.add_argument("--format", dest="export_format",
                           choices=["prometheus", "json"], default="json")
    export_p.set_defaults(handler=handle_observe_export)

    drift_p = sp.add_parser("drift", help="Detect merge drift")
    drift_p.add_argument("file", help="Metrics file (JSON)")
    drift_p.set_defaults(handler=handle_observe_drift)


def handle_observe_metrics(args: argparse.Namespace, formatter: Any) -> None:
    with open(args.file) as f:
        data = json.load(f)

    metrics = data if isinstance(data, list) else data.get("metrics", [data])

    if args.summary:
        total = len(metrics)
        formatter.message(f"Total metrics entries: {total}")
        if metrics and isinstance(metrics[0], dict):
            keys = set()
            for m in metrics:
                keys.update(m.keys())
            formatter.message(f"Fields: {sorted(keys)}")
    else:
        formatter.auto(metrics, title="Merge Metrics")


def handle_observe_export(args: argparse.Namespace, formatter: Any) -> None:
    with open(args.file) as f:
        data = json.load(f)

    if args.export_format == "prometheus":
        from crdt_merge.observability import PrometheusExporter
        exporter = PrometheusExporter()
        metrics = data if isinstance(data, list) else data.get("metrics", [data])
        if hasattr(exporter, "export_metrics"):
            output = exporter.export_metrics(metrics)
        else:
            lines = []
            for m in metrics:
                for k, v in m.items():
                    if isinstance(v, (int, float)):
                        lines.append(f"crdt_merge_{k} {v}")
            output = "\n".join(lines)
        formatter.message(output)
    else:
        formatter.json(data)


def handle_observe_drift(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.observability import DriftDetector

    with open(args.file) as f:
        data = json.load(f)

    detector = DriftDetector()
    metrics = data if isinstance(data, list) else data.get("metrics", [data])

    if hasattr(detector, "detect"):
        report = detector.detect(metrics)
        if hasattr(report, "__dict__"):
            formatter.auto([report.__dict__], title="Drift Report")
        else:
            formatter.json(report if isinstance(report, (dict, list)) else str(report))
    else:
        formatter.warning("DriftDetector.detect() not available in this version.")
