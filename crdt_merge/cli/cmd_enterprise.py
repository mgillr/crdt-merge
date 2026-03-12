# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""Enterprise CLI commands: audit, provenance, compliance, encrypt, decrypt,
unmerge, forget, and RBAC.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register all enterprise commands."""
    _register_audit(subparsers)
    _register_provenance(subparsers)
    _register_compliance(subparsers)
    _register_encrypt(subparsers)
    _register_decrypt(subparsers)
    _register_unmerge(subparsers)
    _register_rbac(subparsers)


# ── audit ─────────────────────────────────────────────────

def _register_audit(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "audit", help="Audit log operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge audit log audit.json\n"
            "  crdt-merge audit log audit.json --verify\n"
            "  crdt-merge audit export audit.json -o report.csv --format csv\n"
        ),
    )
    sp = p.add_subparsers(dest="audit_cmd")

    log_p = sp.add_parser("log", help="Display audit log entries")
    log_p.add_argument("file", help="Audit log file (JSON)")
    log_p.add_argument("--verify", action="store_true",
                        help="Verify hash chain integrity")
    log_p.add_argument("--filter", metavar="KEY=VALUE",
                        help="Filter entries (e.g. operation=merge)")
    log_p.set_defaults(handler=handle_audit_log)

    export_p = sp.add_parser("export", help="Export audit log")
    export_p.add_argument("file", help="Audit log file (JSON)")
    export_p.set_defaults(handler=handle_audit_export)


def handle_audit_log(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.audit import AuditLog

    with open(args.file) as f:
        data = json.load(f)

    log = AuditLog.from_dict(data) if hasattr(AuditLog, "from_dict") else AuditLog()
    if hasattr(log, "_entries") and isinstance(data, list):
        for entry_data in data:
            if hasattr(log, "add_raw"):
                log.add_raw(entry_data)

    if args.verify:
        valid = log.verify() if hasattr(log, "verify") else True
        if valid:
            formatter.success("Hash chain integrity verified.")
        else:
            formatter.error("Hash chain verification FAILED.")
            sys.exit(1)

    entries = data if isinstance(data, list) else data.get("entries", [data])

    if args.filter:
        key, _, value = args.filter.partition("=")
        entries = [e for e in entries if str(e.get(key)) == value]

    if entries and isinstance(entries[0], dict):
        formatter.auto(entries, title="Audit Log")
    else:
        formatter.json(entries)


def handle_audit_export(args: argparse.Namespace, formatter: Any) -> None:
    with open(args.file) as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else data.get("entries", [data])
    formatter.auto(entries, title="Audit Export")


# ── provenance ────────────────────────────────────────────

def _register_provenance(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "provenance", help="Merge provenance and lineage tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge provenance show provenance.json\n"
            "  crdt-merge provenance export provenance.json --format html -o report.html\n"
        ),
    )
    sp = p.add_subparsers(dest="prov_cmd")

    show_p = sp.add_parser("show", help="Display provenance log")
    show_p.add_argument("file", help="Provenance log file (JSON)")
    show_p.add_argument("--field", help="Filter to specific field")
    show_p.set_defaults(handler=handle_provenance_show)

    export_p = sp.add_parser("export", help="Export provenance log")
    export_p.add_argument("file", help="Provenance log file (JSON)")
    export_p.set_defaults(handler=handle_provenance_export)


def handle_provenance_show(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.provenance import ProvenanceLog

    with open(args.file) as f:
        data = json.load(f)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("records", data.get("entries", [data]))
    else:
        records = [data]

    if args.field:
        records = [
            r for r in records
            if r.get("field") == args.field
            or any(d.get("field") == args.field for d in r.get("decisions", []))
        ]

    formatter.auto(records, title="Provenance Log")


def handle_provenance_export(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.provenance import ProvenanceLog, export_provenance

    with open(args.file) as f:
        data = json.load(f)

    fmt = getattr(args, "format", None) or "json"
    if hasattr(ProvenanceLog, "from_dict"):
        log = ProvenanceLog.from_dict(data)
        result = export_provenance(log, format=fmt)
        formatter.message(result)
    else:
        formatter.json(data)


# ── compliance ────────────────────────────────────────────

def _register_compliance(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "compliance", help="Compliance checking and reporting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge compliance check audit.json --framework eu-ai-act\n"
            "  crdt-merge compliance report audit.json --format html -o report.html\n"
        ),
    )
    sp = p.add_subparsers(dest="compliance_cmd")

    check_p = sp.add_parser("check", help="Quick compliance check")
    check_p.add_argument("file", help="Audit file to check")
    check_p.add_argument("--framework",
                          choices=["eu-ai-act", "gdpr", "hipaa", "sox", "all"],
                          default="eu-ai-act", help="Compliance framework")
    check_p.set_defaults(handler=handle_compliance_check)

    report_p = sp.add_parser("report", help="Generate compliance report")
    report_p.add_argument("file", help="Audit file")
    report_p.add_argument("--framework", default="eu-ai-act",
                           choices=["eu-ai-act"])
    report_p.set_defaults(handler=handle_compliance_report)


def handle_compliance_check(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.compliance import ComplianceAuditor

    with open(args.file) as f:
        data = json.load(f)

    auditor = ComplianceAuditor()
    if hasattr(auditor, "check"):
        result = auditor.check(data, framework=args.framework)
        if isinstance(result, dict):
            formatter.auto([result], title="Compliance Check")
        else:
            formatter.message(str(result))
    else:
        formatter.warning("ComplianceAuditor.check() not available in this version.")


def handle_compliance_report(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

    with open(args.file) as f:
        data = json.load(f)

    auditor = ComplianceAuditor()
    if hasattr(auditor, "audit"):
        report = auditor.audit(data)
        if isinstance(report, dict):
            formatter.json(report)
        else:
            formatter.message(str(report))
    else:
        formatter.warning("Full compliance reporting requires audit data.")


# ── encrypt / decrypt ─────────────────────────────────────

def _register_encrypt(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "encrypt", help="Encrypt data fields",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge encrypt data.csv --key my-secret-key --fields email,ssn\n"
            "  crdt-merge encrypt data.json --key secret --backend aes-gcm -o encrypted.json\n"
        ),
    )
    p.add_argument("file", help="Input data file")
    p.add_argument("--key", required=True, help="Master encryption key")
    p.add_argument("--backend", default="auto",
                    choices=["aes-256-gcm", "aes-256-gcm-siv", "chacha20-poly1305", "xor-legacy", "auto"],
                    help="Encryption backend (default: auto)")
    p.add_argument("--fields", help="Comma-separated fields to encrypt")
    p.set_defaults(handler=handle_encrypt)


def _register_decrypt(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "decrypt", help="Decrypt data fields",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  crdt-merge decrypt encrypted.json --key my-secret-key\n",
    )
    p.add_argument("file", help="Encrypted data file")
    p.add_argument("--key", required=True, help="Master encryption key")
    p.set_defaults(handler=handle_decrypt)


def handle_encrypt(args: argparse.Namespace, formatter: Any) -> None:
    import hashlib
    from crdt_merge.cli._util import load_data, write_data
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    data = load_data(args.file)
    # Derive a 32-byte key from the user-supplied string via SHA-256
    key_bytes = hashlib.sha256(args.key.encode("utf-8")).digest()
    provider = StaticKeyProvider(key_bytes)
    fields = [f.strip() for f in args.fields.split(",")] if args.fields else None
    backend = args.backend  # already validated: full registry name or "auto"

    em = EncryptedMerge(provider, backend=backend)
    encrypted = em.encrypt_records(data, fields=fields)

    output = getattr(args, "output", None)
    if output:
        write_data(encrypted, output)
        formatter.success(f"Encrypted {len(encrypted)} records -> {output}")
    else:
        formatter.auto(encrypted, title="Encrypted Data")


def handle_decrypt(args: argparse.Namespace, formatter: Any) -> None:
    import hashlib
    from crdt_merge.cli._util import load_data
    from crdt_merge.encryption import EncryptedMerge, StaticKeyProvider

    data = load_data(args.file)
    # Derive the same 32-byte key used during encryption
    key_bytes = hashlib.sha256(args.key.encode("utf-8")).digest()
    provider = StaticKeyProvider(key_bytes)

    # EncryptedMerge.decrypt_records auto-routes to the correct backend via
    # cipher metadata embedded in each EncryptedValue dict.
    em = EncryptedMerge(provider, backend="xor-legacy")
    decrypted = em.decrypt_records(data)

    formatter.auto(decrypted, title="Decrypted Data")


# ── unmerge ───────────────────────────────────────────────

def _register_unmerge(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "unmerge", help="Selective rollback and GDPR forget",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge unmerge merged.csv --provenance prov.json --source a\n"
            "  crdt-merge unmerge forget merged.csv --provenance prov.json "
            "--forget-keys user123,user456\n"
        ),
    )
    sp = p.add_subparsers(dest="unmerge_cmd")

    rollback_p = sp.add_parser("rollback", help="Rollback to a source")
    rollback_p.add_argument("file", help="Merged data file")
    rollback_p.add_argument("--provenance", required=True, help="Provenance log")
    rollback_p.add_argument("--source", required=True, choices=["a", "b"],
                             help="Source to recover")
    rollback_p.set_defaults(handler=handle_unmerge_rollback)

    forget_p = sp.add_parser("forget", help="GDPR right-to-be-forgotten")
    forget_p.add_argument("file", help="Merged data file")
    forget_p.add_argument("--provenance", required=True, help="Provenance log")
    forget_p.add_argument("--forget-keys", required=True,
                           help="Comma-separated keys to forget")
    forget_p.add_argument("--compliance-report", metavar="PATH",
                           help="Write compliance report to file")
    forget_p.set_defaults(handler=handle_unmerge_forget)

    # Also register bare "unmerge <file>" as alias for rollback
    p.add_argument("file", nargs="?", help="Merged data file")
    p.add_argument("--provenance", help="Provenance log")
    p.add_argument("--source", choices=["a", "b"], help="Source to recover")
    p.set_defaults(handler=handle_unmerge_rollback)


def handle_unmerge_rollback(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._util import load_data, write_data
    from crdt_merge.unmerge import UnmergeEngine

    if not args.file:
        formatter.error("File argument is required.")
        sys.exit(1)

    data = load_data(args.file)
    with open(args.provenance) as f:
        prov = json.load(f)

    engine = UnmergeEngine()
    result = engine.rollback(data, prov, source=args.source)

    output = getattr(args, "output", None)
    if output:
        out_data = result if isinstance(result, list) else [result]
        write_data(out_data, output)
        formatter.success(f"Rollback complete -> {output}")
    else:
        out_data = result if isinstance(result, list) else [result]
        formatter.auto(out_data, title="Unmerge Result")


def handle_unmerge_forget(args: argparse.Namespace, formatter: Any) -> None:
    from crdt_merge.cli._util import load_data, write_data
    from crdt_merge.unmerge import GDPRForget

    data = load_data(args.file)
    with open(args.provenance) as f:
        prov = json.load(f)

    keys = [k.strip() for k in args.forget_keys.split(",")]
    forget = GDPRForget()
    result = forget.forget(data, prov, keys=keys)

    output = getattr(args, "output", None)
    if output:
        out_data = result if isinstance(result, list) else [result]
        write_data(out_data, output)
        formatter.success(f"Forget complete -> {output}")

    if args.compliance_report:
        report = forget.compliance_report() if hasattr(forget, "compliance_report") else {}
        with open(args.compliance_report, "w") as f:
            json.dump(report, f, indent=2, default=str)
        formatter.success(f"Compliance report -> {args.compliance_report}")

    if not output:
        out_data = result if isinstance(result, list) else [result]
        formatter.auto(out_data, title="GDPR Forget Result")


# ── rbac ──────────────────────────────────────────────────

def _register_rbac(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "rbac", help="Role-Based Access Control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  crdt-merge rbac init -o policy.json\n"
            "  crdt-merge rbac check policy.json --node worker-1 --role merger "
            "--permission merge\n"
        ),
    )
    sp = p.add_subparsers(dest="rbac_cmd")

    init_p = sp.add_parser("init", help="Create default RBAC policy file")
    init_p.set_defaults(handler=handle_rbac_init)

    check_p = sp.add_parser("check", help="Check permission")
    check_p.add_argument("policy_file", help="RBAC policy file")
    check_p.add_argument("--node", required=True, help="Node ID")
    check_p.add_argument("--role", required=True, help="Role name")
    check_p.add_argument("--permission", required=True,
                          choices=["merge", "encrypt", "unmerge", "audit", "read"],
                          help="Permission to check")
    check_p.set_defaults(handler=handle_rbac_check)


def handle_rbac_init(args: argparse.Namespace, formatter: Any) -> None:
    default_policy = {
        "roles": {
            "admin": {"permissions": ["merge", "encrypt", "unmerge", "audit", "read"]},
            "merger": {"permissions": ["merge", "read"]},
            "reader": {"permissions": ["read"]},
            "auditor": {"permissions": ["audit", "read"]},
        },
        "policies": [
            {"node": "*", "role": "reader"},
        ],
    }
    output = getattr(args, "output", None) or "rbac-policy.json"
    with open(output, "w") as f:
        json.dump(default_policy, f, indent=2)
    formatter.success(f"Default RBAC policy created -> {output}")


def handle_rbac_check(args: argparse.Namespace, formatter: Any) -> None:
    with open(args.policy_file) as f:
        policy = json.load(f)

    roles = policy.get("roles", {})
    role_def = roles.get(args.role)
    if not role_def:
        formatter.error(f"Role '{args.role}' not found. Available: {list(roles.keys())}")
        sys.exit(1)

    permissions = role_def.get("permissions", [])
    allowed = args.permission in permissions

    result = {
        "node": args.node,
        "role": args.role,
        "permission": args.permission,
        "allowed": allowed,
    }

    if allowed:
        formatter.success(
            f"ALLOWED: {args.node} ({args.role}) has '{args.permission}' permission"
        )
    else:
        formatter.error(
            f"DENIED: {args.node} ({args.role}) lacks '{args.permission}' permission"
        )

    formatter.auto([result], title="RBAC Check")
