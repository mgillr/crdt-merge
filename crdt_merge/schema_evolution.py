# Copyright 2026 Ryan Gillespie
# SPDX-License-Identifier: Apache-2.0
#
# Commercial licensing: data@optitransfer.ch, rgillespie83@icloud.com

"""Schema drift detection and resolution for evolving datasets.

Supports four policies (UNION, INTERSECTION, LEFT_PRIORITY, RIGHT_PRIORITY)
and integrates with Arrow-style type strings.  Pure standalone module — no
imports from crdt_merge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TYPE_WIDENING: Dict[Tuple[str, str], str] = {
    # int32 ↔ int64
    ("int32", "int64"): "int64",
    ("int64", "int32"): "int64",
    # float32 ↔ float64
    ("float32", "float64"): "float64",
    ("float64", "float32"): "float64",
    # int32 ↔ float32
    ("int32", "float32"): "float32",
    ("float32", "int32"): "float32",
    # int32 ↔ float64
    ("int32", "float64"): "float64",
    ("float64", "int32"): "float64",
    # int64 ↔ float64
    ("int64", "float64"): "float64",
    ("float64", "int64"): "float64",
    # str ↔ str (identity)
    ("str", "str"): "str",
    # int ↔ float (generic Python types)
    ("int", "float"): "float",
    ("float", "int"): "float",
}

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class SchemaPolicy(Enum):
    """Policy for resolving schema drift between two schemas."""

    UNION = "union"                    # Keep all columns from both sides
    INTERSECTION = "intersection"      # Keep only common columns
    LEFT_PRIORITY = "left_priority"    # Left schema primary, add new from right
    RIGHT_PRIORITY = "right_priority"  # Right schema primary, add new from left


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SchemaChange:
    """Describes a single schema change for one column."""

    column: str
    change_type: str  # 'added', 'removed', 'type_changed', 'unchanged'
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    resolved_type: Optional[str] = None
    default_value: Any = None

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain-dict representation."""
        return {
            "column": self.column,
            "change_type": self.change_type,
            "old_type": self.old_type,
            "new_type": self.new_type,
            "resolved_type": self.resolved_type,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SchemaChange":
        """Reconstruct from a plain dict."""
        return cls(
            column=d["column"],
            change_type=d["change_type"],
            old_type=d.get("old_type"),
            new_type=d.get("new_type"),
            resolved_type=d.get("resolved_type"),
            default_value=d.get("default_value"),
        )


@dataclass
class SchemaEvolutionResult:
    """Full result of a schema evolution operation."""

    resolved_schema: Dict[str, str]       # column → type
    changes: List[SchemaChange]           # all detected changes
    defaults: Dict[str, Any]             # column → default value
    policy_used: SchemaPolicy
    is_compatible: bool                   # True when no lossy changes
    warnings: List[str] = field(default_factory=list)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain-dict representation suitable for JSON."""
        return {
            "resolved_schema": dict(self.resolved_schema),
            "changes": [c.to_dict() for c in self.changes],
            "defaults": dict(self.defaults),
            "policy_used": self.policy_used.value,
            "is_compatible": self.is_compatible,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SchemaEvolutionResult":
        """Reconstruct a *SchemaEvolutionResult* from its dict form."""
        return cls(
            resolved_schema=d["resolved_schema"],
            changes=[SchemaChange.from_dict(c) for c in d["changes"]],
            defaults=d.get("defaults", {}),
            policy_used=SchemaPolicy(d["policy_used"]),
            is_compatible=d["is_compatible"],
            warnings=d.get("warnings", []),
        )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def widen_type(type_a: str, type_b: str) -> Optional[str]:
    """Return the widened type that covers both *type_a* and *type_b*.

    Returns *None* when no safe widening is known (incompatible or opaque
    type strings).
    """
    if type_a == type_b:
        return type_a
    return TYPE_WIDENING.get((type_a, type_b))


def check_compatibility(
    schema_a: Dict[str, str],
    schema_b: Dict[str, str],
) -> Tuple[bool, List[str]]:
    """Check whether *schema_a* and *schema_b* can be merged without evolution.

    Two schemas are compatible when they share the same set of columns and
    every shared column either has identical types or can be safely widened.

    Returns ``(is_compatible, reasons)`` where *reasons* lists every
    incompatibility found (empty list when compatible).
    """
    if schema_a is None:
        schema_a = {}
    if schema_b is None:
        schema_b = {}

    reasons: List[str] = []

    keys_a = set(schema_a)
    keys_b = set(schema_b)

    only_a = keys_a - keys_b
    only_b = keys_b - keys_a

    if only_a:
        reasons.append(f"Columns only in schema_a: {sorted(only_a)}")
    if only_b:
        reasons.append(f"Columns only in schema_b: {sorted(only_b)}")

    for col in sorted(keys_a & keys_b):
        ta = schema_a[col]
        tb = schema_b[col]
        if ta != tb and widen_type(ta, tb) is None:
            reasons.append(
                f"Column '{col}': incompatible types {ta!r} vs {tb!r}"
            )

    return (len(reasons) == 0, reasons)


# ---------------------------------------------------------------------------
# Core evolution logic
# ---------------------------------------------------------------------------


def _resolve_type_conflict(
    column: str,
    old_type: str,
    new_type: str,
    allow_type_narrowing: bool,
    warnings: List[str],
) -> Tuple[str, bool]:
    """Resolve a type conflict between *old_type* and *new_type*.

    Returns ``(resolved_type, is_compatible_change)``.
    """
    widened = widen_type(old_type, new_type)
    if widened is not None:
        return widened, True

    # No safe widening available
    if allow_type_narrowing:
        warnings.append(
            f"Column '{column}': type narrowing {old_type!r} -> {new_type!r} "
            f"(allowed by flag)"
        )
        return new_type, True  # caller explicitly opted in

    warnings.append(
        f"Column '{column}': incompatible types {old_type!r} vs {new_type!r}, "
        f"keeping old type {old_type!r}"
    )
    return old_type, False


def evolve_schema(
    old: Dict[str, str],
    new: Dict[str, str],
    policy: SchemaPolicy = SchemaPolicy.UNION,
    defaults: Optional[Dict[str, Any]] = None,
    allow_type_narrowing: bool = False,
) -> SchemaEvolutionResult:
    """Detect and resolve schema drift between *old* and *new*.

    Parameters
    ----------
    old:
        The existing (left) schema mapping column names to type strings.
    new:
        The incoming (right) schema.
    policy:
        How to handle differing column sets. See :class:`SchemaPolicy`.
    defaults:
        Default values for columns that appear in only one side.
    allow_type_narrowing:
        When *False* (default), type narrowing (e.g. float64 → int32) makes
        the result incompatible and emits a warning.  When *True*, the new
        type is accepted.

    Returns
    -------
    SchemaEvolutionResult
    """
    if old is None:
        old = {}
    if new is None:
        new = {}
    if defaults is None:
        defaults = {}

    old_keys = set(old)
    new_keys = set(new)
    common = old_keys & new_keys
    only_old = old_keys - new_keys
    only_new = new_keys - old_keys

    resolved: Dict[str, str] = {}
    changes: List[SchemaChange] = []
    result_defaults: Dict[str, Any] = {}
    warnings: List[str] = []
    is_compatible = True

    # --- handle common columns (all policies) ------------------------------
    for col in sorted(common):
        ot = old[col]
        nt = new[col]
        if ot == nt:
            resolved[col] = ot
            changes.append(SchemaChange(
                column=col,
                change_type="unchanged",
                old_type=ot,
                new_type=nt,
                resolved_type=ot,
            ))
        else:
            # Type conflict
            if policy == SchemaPolicy.LEFT_PRIORITY:
                resolved_type = ot
                compat = True
            elif policy == SchemaPolicy.RIGHT_PRIORITY:
                resolved_type = nt
                compat = True
            else:
                resolved_type, compat = _resolve_type_conflict(
                    col, ot, nt, allow_type_narrowing, warnings,
                )
            if not compat:
                is_compatible = False
            changes.append(SchemaChange(
                column=col,
                change_type="type_changed",
                old_type=ot,
                new_type=nt,
                resolved_type=resolved_type,
            ))
            resolved[col] = resolved_type

    # --- handle columns only in old ----------------------------------------
    for col in sorted(only_old):
        if policy == SchemaPolicy.UNION:
            resolved[col] = old[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="removed",
                old_type=old[col],
                new_type=None,
                resolved_type=old[col],
                default_value=default_val,
            ))
        elif policy == SchemaPolicy.INTERSECTION:
            changes.append(SchemaChange(
                column=col,
                change_type="removed",
                old_type=old[col],
                new_type=None,
                resolved_type=None,
            ))
        elif policy == SchemaPolicy.LEFT_PRIORITY:
            resolved[col] = old[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="removed",
                old_type=old[col],
                new_type=None,
                resolved_type=old[col],
                default_value=default_val,
            ))
        elif policy == SchemaPolicy.RIGHT_PRIORITY:
            resolved[col] = old[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="removed",
                old_type=old[col],
                new_type=None,
                resolved_type=old[col],
                default_value=default_val,
            ))

    # --- handle columns only in new ----------------------------------------
    for col in sorted(only_new):
        if policy == SchemaPolicy.UNION:
            resolved[col] = new[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="added",
                old_type=None,
                new_type=new[col],
                resolved_type=new[col],
                default_value=default_val,
            ))
        elif policy == SchemaPolicy.INTERSECTION:
            changes.append(SchemaChange(
                column=col,
                change_type="added",
                old_type=None,
                new_type=new[col],
                resolved_type=None,
            ))
        elif policy == SchemaPolicy.LEFT_PRIORITY:
            resolved[col] = new[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="added",
                old_type=None,
                new_type=new[col],
                resolved_type=new[col],
                default_value=default_val,
            ))
        elif policy == SchemaPolicy.RIGHT_PRIORITY:
            resolved[col] = new[col]
            default_val = defaults.get(col)
            result_defaults[col] = default_val
            changes.append(SchemaChange(
                column=col,
                change_type="added",
                old_type=None,
                new_type=new[col],
                resolved_type=new[col],
                default_value=default_val,
            ))

    return SchemaEvolutionResult(
        resolved_schema=resolved,
        changes=changes,
        defaults=result_defaults,
        policy_used=policy,
        is_compatible=is_compatible,
        warnings=warnings,
    )
