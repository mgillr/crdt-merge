# SPDX-License-Identifier: BUSL-1.1
# Copyright 2026 Ryan Gillespie / Optitransfer
#
# Change Date: 2028-03-29
# Change License: Apache License, Version 2.0

"""CLI handlers for the ``verify`` command group.

Subcommands
-----------
- ``verify crdt <type>``       -- verify a built-in CRDT type
- ``verify commutative``       -- check commutativity of a custom merge fn
- ``verify associative``       -- check associativity of a custom merge fn
- ``verify idempotent``        -- check idempotency of a custom merge fn
- ``verify convergence``       -- check eventual convergence
- ``verify all``               -- run all four property checks
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crdt_merge.cli._output import OutputFormatter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRDT_TYPES = ("gcounter", "pncounter", "lww", "orset", "lwwmap")

_PROPERTY_NAMES = ("commutative", "associative", "idempotent", "convergence")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_dotted_path(dotted: str):
    """Import and return the object at *dotted* (e.g. ``pkg.mod.func``)."""
    module_path, _, attr_name = dotted.rpartition(".")
    if not module_path:
        raise ValueError(
            f"Invalid dotted path {dotted!r}: expected 'module.attribute'"
        )
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"Could not import module {module_path!r}: {exc}"
        ) from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise AttributeError(
            f"Module {module_path!r} has no attribute {attr_name!r}"
        ) from exc


def _format_result(result, formatter: OutputFormatter) -> None:
    """Render a VerificationResult through the formatter."""
    row = {
        "property": getattr(result, "property_name", str(result)),
        "passed": getattr(result, "passed", None),
        "trials": getattr(result, "trials", None),
        "failures": getattr(result, "failures", 0),
        "message": getattr(result, "message", ""),
    }
    passed = row["passed"]
    if passed is True:
        formatter.success(
            f"PASS  {row['property']}  "
            f"({row['trials']} trials, {row['failures']} failures)"
        )
    elif passed is False:
        formatter.error(
            f"FAIL  {row['property']}  "
            f"({row['trials']} trials, {row['failures']} failures)"
        )
        if row["message"]:
            formatter.message(f"  Detail: {row['message']}")
    else:
        # Fallback for unexpected result shapes.
        formatter.message(str(result))


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_verify_crdt(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Verify a built-in CRDT type satisfies all CRDT properties."""
    import random
    from crdt_merge.verify import verify_crdt  # lazy

    crdt_type = args.crdt_type
    trials = args.trials

    # Build merge_fn and gen_fn for the requested CRDT type
    try:
        from crdt_merge.core import GCounter, PNCounter, LWWRegister, ORSet, LWWMap

        if crdt_type == "gcounter":
            def gen_fn():
                gc = GCounter()
                for _ in range(random.randint(1, 5)):  # nosec B311 -- simulation/verification, not security
                    gc.increment("node-" + str(random.randint(1, 3)))  # nosec B311 -- simulation/verification, not security
                return gc
            merge_fn = lambda a, b: a.merge(b)
            class_name = "GCounter"

        elif crdt_type == "pncounter":
            def gen_fn():
                pc = PNCounter()
                for _ in range(random.randint(1, 5)):  # nosec B311 -- simulation/verification, not security
                    if random.random() > 0.3:  # nosec B311 -- simulation/verification, not security
                        pc.increment("node-" + str(random.randint(1, 3)))  # nosec B311 -- simulation/verification, not security
                    else:
                        pc.decrement("node-" + str(random.randint(1, 3)))  # nosec B311 -- simulation/verification, not security
                return pc
            merge_fn = lambda a, b: a.merge(b)
            class_name = "PNCounter"

        elif crdt_type == "lww":
            def gen_fn():
                return LWWRegister(
                    value=random.choice(["a", "b", "c", 1, 2, 3]),  # nosec B311 -- simulation/verification, not security
                    timestamp=random.random() * 1000,  # nosec B311 -- simulation/verification, not security
                    node_id="node-" + str(random.randint(1, 3)),  # nosec B311 -- simulation/verification, not security
                )
            merge_fn = lambda a, b: a.merge(b)
            class_name = "LWWRegister"

        elif crdt_type == "orset":
            def gen_fn():
                s = ORSet()
                for i in range(random.randint(1, 5)):  # nosec B311 -- simulation/verification, not security
                    s.add(f"item-{i}")
                return s
            merge_fn = lambda a, b: a.merge(b)
            class_name = "ORSet"

        elif crdt_type == "lwwmap":
            def gen_fn():
                m = LWWMap()
                for i in range(random.randint(1, 3)):  # nosec B311 -- simulation/verification, not security
                    m.set(f"key{i}", random.randint(1, 100))  # nosec B311 -- simulation/verification, not security
                return m
            merge_fn = lambda a, b: a.merge(b)
            class_name = "LWWMap"

        else:
            formatter.error(f"Unknown CRDT type: {crdt_type!r}")
            sys.exit(1)

    except (ImportError, AttributeError) as exc:
        formatter.error(f"Cannot load CRDT type {crdt_type!r}: {exc}")
        sys.exit(1)

    formatter.message(f"Verifying {class_name} ({trials} trials) ...")

    try:
        result = verify_crdt(merge_fn, gen_fn, trials=trials)
    except Exception as exc:
        formatter.error(f"Verification failed with error: {exc}")
        sys.exit(1)

    _format_result(result, formatter)

    if hasattr(result, "passed") and not result.passed:
        sys.exit(1)


def _run_property_check(
    property_name: str,
    args: argparse.Namespace,
    formatter: OutputFormatter,
) -> object:
    """Run a single property verification and return the result."""
    from crdt_merge.cli import _util  # lazy
    from crdt_merge import verify as verify_mod  # lazy

    fn_map = {
        "commutative": "verify_commutative",
        "associative": "verify_associative",
        "idempotent": "verify_idempotent",
        "convergence": "verify_convergence",
    }

    verify_fn = getattr(verify_mod, fn_map[property_name])

    # Load data.
    try:
        data = _util.load_data(args.data)
    except Exception as exc:
        formatter.error(f"Failed to load data from {args.data!r}: {exc}")
        sys.exit(1)

    # Resolve the merge function.
    try:
        merge_fn = _resolve_dotted_path(args.merge_fn)
    except (ValueError, ImportError, AttributeError) as exc:
        formatter.error(str(exc))
        sys.exit(1)

    trials = args.trials
    formatter.message(
        f"Checking {property_name} ({trials} trials) ..."
    )

    try:
        result = verify_fn(data, merge_fn, trials=trials)
    except Exception as exc:
        formatter.error(
            f"Verification of {property_name} failed with error: {exc}"
        )
        sys.exit(1)

    return result


def handle_commutative(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Check that a merge function is commutative."""
    result = _run_property_check("commutative", args, formatter)
    _format_result(result, formatter)
    if hasattr(result, "passed") and not result.passed:
        sys.exit(1)


def handle_associative(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Check that a merge function is associative."""
    result = _run_property_check("associative", args, formatter)
    _format_result(result, formatter)
    if hasattr(result, "passed") and not result.passed:
        sys.exit(1)


def handle_idempotent(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Check that a merge function is idempotent."""
    result = _run_property_check("idempotent", args, formatter)
    _format_result(result, formatter)
    if hasattr(result, "passed") and not result.passed:
        sys.exit(1)


def handle_convergence(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Check that a merge function achieves convergence."""
    result = _run_property_check("convergence", args, formatter)
    _format_result(result, formatter)
    if hasattr(result, "passed") and not result.passed:
        sys.exit(1)


def handle_all(args: argparse.Namespace, formatter: OutputFormatter) -> None:
    """Run all four property verifications sequentially."""
    any_failed = False
    results = []

    for prop in _PROPERTY_NAMES:
        result = _run_property_check(prop, args, formatter)
        _format_result(result, formatter)
        results.append(result)
        if hasattr(result, "passed") and not result.passed:
            any_failed = True

    formatter.message("")
    passed = sum(1 for r in results if getattr(r, "passed", False))
    total = len(results)
    formatter.message(f"Summary: {passed}/{total} properties passed.")

    if any_failed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Subparser registration
# ---------------------------------------------------------------------------

_HANDLER_MAP = {
    "crdt": handle_verify_crdt,
    "commutative": handle_commutative,
    "associative": handle_associative,
    "idempotent": handle_idempotent,
    "convergence": handle_convergence,
    "all": handle_all,
}


def _add_property_parser(
    sub: argparse._SubParsersAction,
    name: str,
    *,
    help_text: str,
    epilog: str,
) -> argparse.ArgumentParser:
    """Create a sub-subparser for a single property verification command."""
    parser = sub.add_parser(
        name,
        help=help_text,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data",
        required=True,
        metavar="PATH",
        help="Path to the data file (CSV, JSON, JSONL, or Parquet).",
    )
    parser.add_argument(
        "--merge-fn",
        required=True,
        metavar="DOTTED_PATH",
        help="Dotted import path to the merge function (e.g. mymod.merge).",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1000,
        metavar="INT",
        help="Number of randomised trials to run (default: 1000).",
    )
    parser.set_defaults(verify_handler=name, handler=_HANDLER_MAP[name])
    return parser


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``verify`` command and its sub-subparsers."""
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify CRDT properties and merge-function correctness.",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify crdt gcounter --trials 5000\n"
            "  crdt-merge verify commutative --data rows.json --merge-fn mymod.merge\n"
            "  crdt-merge verify all --data rows.json --merge-fn mymod.merge --trials 500\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = verify_parser.add_subparsers(dest="verify_sub", metavar="SUBCOMMAND")

    # --- verify crdt ---
    crdt_parser = sub.add_parser(
        "crdt",
        help="Verify a built-in CRDT type satisfies all CRDT laws.",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify crdt gcounter\n"
            "  crdt-merge verify crdt orset --trials 5000 --verbose\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    crdt_parser.add_argument(
        "crdt_type",
        choices=CRDT_TYPES,
        metavar="TYPE",
        help=f"CRDT type to verify. Choices: {', '.join(CRDT_TYPES)}.",
    )
    crdt_parser.add_argument(
        "--trials",
        type=int,
        default=1000,
        metavar="INT",
        help="Number of randomised trials to run (default: 1000).",
    )
    crdt_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Print detailed per-trial output.",
    )
    crdt_parser.set_defaults(verify_handler="crdt", handler=handle_verify_crdt)

    # --- verify commutative ---
    _add_property_parser(
        sub,
        "commutative",
        help_text="Verify that merge(a, b) == merge(b, a).",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify commutative --data rows.json --merge-fn mymod.merge\n"
            "  crdt-merge verify commutative --data rows.csv --merge-fn pkg.fn --trials 2000\n"
        ),
    )

    # --- verify associative ---
    _add_property_parser(
        sub,
        "associative",
        help_text="Verify that merge(merge(a, b), c) == merge(a, merge(b, c)).",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify associative --data rows.json --merge-fn mymod.merge\n"
        ),
    )

    # --- verify idempotent ---
    _add_property_parser(
        sub,
        "idempotent",
        help_text="Verify that merge(a, a) == a.",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify idempotent --data rows.json --merge-fn mymod.merge\n"
        ),
    )

    # --- verify convergence ---
    _add_property_parser(
        sub,
        "convergence",
        help_text="Verify that all orderings converge to the same result.",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify convergence --data rows.json --merge-fn mymod.merge\n"
        ),
    )

    # --- verify all ---
    _add_property_parser(
        sub,
        "all",
        help_text="Run all four property verifications.",
        epilog=(
            "Examples:\n"
            "  crdt-merge verify all --data rows.json --merge-fn mymod.merge\n"
            "  crdt-merge verify all --data rows.csv --merge-fn pkg.fn --trials 500\n"
        ),
    )
