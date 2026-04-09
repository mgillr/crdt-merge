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

"""
Composable Merge Strategies — per-field conflict resolution DSL.

Define a MergeSchema with different strategies per column. When two values
conflict, the strategy for that column determines the winner.

Every strategy satisfies CRDT merge semantics:
  - Commutative:  resolve(A, B) == resolve(B, A)
  - Associative:  resolve(resolve(A, B), C) == resolve(A, resolve(B, C))
  - Idempotent:   resolve(A, A) == A

Usage:
    from crdt_merge.strategies import MergeSchema, LWW, MaxWins, UnionSet

    schema = MergeSchema(
        default=LWW(),
        name=LWW(),
        score=MaxWins(),
        tags=UnionSet(separator=","),
        version=MaxWins(),
        notes=Concat(separator=" | "),
        status=Priority(["draft", "review", "approved", "published"]),
    )

    merged = merge(df_a, df_b, key="id", schema=schema)
"""

from __future__ import annotations
import copy
import time
from typing import Any, Callable, Dict, List, Optional, Union

__all__ = ["MergeStrategy", "LWW", "MaxWins", "MinWins", "UnionSet", "Concat", "Priority", "LongestWins", "Custom", "MergeSchema"]

def _safe_parse_ts(value: Any) -> float:
    """Parse timestamp to float — handles numeric, ISO-8601, None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            pass
        from datetime import datetime as _dt

        try:
            return _dt.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError, TypeError):
            pass
    if hasattr(value, 'timestamp'):
        try:
            return float(value.timestamp())
        except (TypeError, OSError):
            pass
    # Parsing failed -- fall back to epoch 0.0 for backward compatibility,
    # but emit a warning so the caller knows something unexpected happened.
    import warnings
    warnings.warn(
        f"_safe_parse_ts: could not parse timestamp value {value!r} "
        f"(type={type(value).__name__}); falling back to 0.0. "
        f"This may hide bugs — consider passing numeric or ISO-8601 timestamps.",
        UserWarning,
        stacklevel=2,
    )
    return 0.0

class MergeStrategy:
    """Base class for merge strategies. Subclass and implement resolve()."""

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        """Resolve a conflict between two values. Must be commutative, associative, idempotent."""
        raise NotImplementedError

    def name(self) -> str:
        return self.__class__.__name__

class LWW(MergeStrategy):
    """Last-Writer-Wins — latest timestamp wins. Tie-break: deterministic value comparison."""

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        if ts_b > ts_a:
            return val_b
        elif ts_a > ts_b:
            return val_a
        # Timestamps equal: deterministic value-based tie-break for commutativity.
        # Using max(str(v)) ensures resolve(A,B) == resolve(B,A) regardless of
        # argument position -- critical for CRDT guarantee.
        str_a, str_b = str(val_a), str(val_b)
        if str_a != str_b:
            return val_a if str_a >= str_b else val_b
        return val_a

class MaxWins(MergeStrategy):
    """Higher value wins. Works with numbers and comparable types."""

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        if val_a is None:
            return val_b
        if val_b is None:
            return val_a
        try:
            return val_a if val_a >= val_b else val_b
        except TypeError:
            # Incomparable types: deterministic tiebreak via repr
            return val_a if str(val_a) >= str(val_b) else val_b

class MinWins(MergeStrategy):
    """Lower value wins. Works with numbers and comparable types."""

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        if val_a is None:
            return val_b
        if val_b is None:
            return val_a
        try:
            return val_a if val_a <= val_b else val_b
        except TypeError:
            return val_a if str(val_a) <= str(val_b) else val_b

class UnionSet(MergeStrategy):
    """Merge separated values as a set union. Sorted for determinism."""

    def __init__(self, separator: str = ","):
        self.separator = separator

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        set_a = self._to_set(val_a)
        set_b = self._to_set(val_b)
        merged = sorted(set_a | set_b)
        return self.separator.join(merged)

    def _to_set(self, val: Any) -> set:
        if val is None:
            return set()
        return {s.strip() for s in str(val).split(self.separator) if s.strip()}

class Concat(MergeStrategy):
    """Concatenate both values with dedup. Sorted for commutativity."""

    def __init__(self, separator: str = " | ", dedup: bool = True):
        self.separator = separator
        self.dedup = dedup

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        parts_a = [p.strip() for p in str(val_a).split(self.separator)] if val_a else []
        parts_b = [p.strip() for p in str(val_b).split(self.separator)] if val_b else []
        if self.dedup:
            seen = set()
            unique = []
            for p in parts_a + parts_b:
                if p and p not in seen:
                    seen.add(p)
                    unique.append(p)
            # Sort for commutativity: merge(A,B) == merge(B,A)
            return self.separator.join(sorted(unique))
        # Without dedup: still sort for commutativity
        return self.separator.join(sorted(parts_a + parts_b))

class Priority(MergeStrategy):
    """
    Ranked priority — higher index in the priority list wins.

    Usage:
        s = Priority(["draft", "review", "approved", "published"])
        s.resolve("draft", "published")  # → "published" (index 3 > index 0)

    Unknown values get index -1 (always lose to known values).
    Commutative: the same value wins regardless of argument order.
    """

    def __init__(self, levels: List[str]):
        self.levels = list(levels)
        self._index = {v: i for i, v in enumerate(levels)}

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        rank_a = self._index.get(str(val_a), -1)
        rank_b = self._index.get(str(val_b), -1)
        if rank_a > rank_b:
            return val_a
        elif rank_b > rank_a:
            return val_b
        # Equal rank: deterministic tiebreak via string comparison for commutativity
        return val_a if str(val_a) >= str(val_b) else val_b

class LongestWins(MergeStrategy):
    """Longer string wins. Equal length falls back to LWW."""

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        la = len(str(val_a)) if val_a is not None else 0
        lb = len(str(val_b)) if val_b is not None else 0
        if la > lb:
            return val_a
        elif lb > la:
            return val_b
        # Same length: LWW fallback
        return LWW().resolve(val_a, val_b, ts_a, ts_b, node_a, node_b)

class Custom(MergeStrategy):
    """
    User-provided merge function.

    The fn receives (val_a, val_b, ts_a, ts_b, node_a, node_b).
    Simpler functions taking just (val_a, val_b) also work.
    """

    def __init__(self, fn: Callable):
        self._fn = fn

    def resolve(self, val_a: Any, val_b: Any, ts_a: float = 0.0, ts_b: float = 0.0,
                node_a: str = "a", node_b: str = "b") -> Any:
        try:
            return self._fn(val_a, val_b, ts_a=ts_a, ts_b=ts_b, node_a=node_a, node_b=node_b)
        except TypeError:
            # Simple fn(a, b) signature
            return self._fn(val_a, val_b)

# ---------------------------------------------------------------------------
# Registry for serialization
# ---------------------------------------------------------------------------

_STRATEGY_REGISTRY: Dict[str, type] = {
    "LWW": LWW,
    "MaxWins": MaxWins,
    "MinWins": MinWins,
    "UnionSet": UnionSet,
    "Concat": Concat,
    "Priority": Priority,
    "LongestWins": LongestWins,
    "Custom": Custom,
}

class MergeSchema:
    """
    Declarative per-field strategy mapping.

    Usage:
        schema = MergeSchema(
            default=LWW(),
            name=LWW(),
            score=MaxWins(),
            tags=UnionSet(),
            status=Priority(["draft", "review", "published"]),
        )

        strat = schema.strategy_for("score")  # → MaxWins
        strat = schema.strategy_for("unknown_col")  # → LWW (default)

        # Merge an entire row pair
        merged_row = schema.resolve_row(row_a, row_b, timestamp_col="_ts")
    """

    def __init__(self, default: Optional[MergeStrategy] = None, **field_strategies: MergeStrategy):
        self._default = default or LWW()
        self._strategies: Dict[str, MergeStrategy] = dict(field_strategies)

    def strategy_for(self, field: str) -> MergeStrategy:
        """Get the strategy for a field, or the default."""
        return self._strategies.get(field, self._default)

    def set_strategy(self, field: str, strategy: MergeStrategy) -> None:
        """Set strategy for a specific field."""
        self._strategies[field] = strategy

    @property
    def default(self) -> MergeStrategy:
        return self._default

    @property
    def fields(self) -> Dict[str, MergeStrategy]:
        return dict(self._strategies)

    def resolve_row(
        self,
        row_a: dict,
        row_b: dict,
        timestamp_col: Optional[str] = None,
        node_a: str = "a",
        node_b: str = "b",
    ) -> dict:
        """
        Merge two rows using per-field strategies.

        Returns a new dict with each field resolved according to its strategy.

        Nested structures are handled recursively:
          - If both values for a field are dicts, resolve_row is applied recursively.
          - If both values for a field are lists, elements are merged element-wise
            (extra elements from the longer list are appended).
        """
        ts_a = _safe_parse_ts(row_a.get(timestamp_col)) if timestamp_col else 0.0
        ts_b = _safe_parse_ts(row_b.get(timestamp_col)) if timestamp_col else 0.0
        all_keys = set(row_a.keys()) | set(row_b.keys())
        result = {}
        for k in all_keys:
            va = row_a.get(k)
            vb = row_b.get(k)
            if va is None:
                result[k] = vb
            elif vb is None:
                result[k] = va
            elif va == vb:
                result[k] = va
            elif isinstance(va, dict) and isinstance(vb, dict) and k not in self._strategies:
                # Recursively merge nested dicts only when no per-field strategy is registered.
                # A registered strategy takes priority over structural recursion.
                result[k] = self.resolve_row(va, vb, timestamp_col=timestamp_col,
                                             node_a=node_a, node_b=node_b)
            elif isinstance(va, list) and isinstance(vb, list):
                # Element-wise merge for lists; extra elements from the longer
                # list are appended as-is.
                merged_list = []
                for i in range(max(len(va), len(vb))):
                    ea = va[i] if i < len(va) else None
                    eb = vb[i] if i < len(vb) else None
                    if ea is None:
                        merged_list.append(eb)
                    elif eb is None:
                        merged_list.append(ea)
                    elif ea == eb:
                        merged_list.append(ea)
                    elif isinstance(ea, dict) and isinstance(eb, dict):
                        merged_list.append(
                            self.resolve_row(ea, eb, timestamp_col=timestamp_col,
                                             node_a=node_a, node_b=node_b)
                        )
                    else:
                        strat = self.strategy_for(k)
                        merged_list.append(strat.resolve(ea, eb, ts_a, ts_b, node_a, node_b))
                result[k] = merged_list
            else:
                strat = self.strategy_for(k)
                result[k] = strat.resolve(va, vb, ts_a, ts_b, node_a, node_b)
        return result

    def to_dict(self) -> dict:
        """Serialize schema to dict for storage/transmission."""
        d = {}
        for field, strat in self._strategies.items():
            if isinstance(strat, Custom):
                import warnings
                warnings.warn(
                    f"Custom strategy for field '{field}' cannot be fully serialized. "
                    f"It will deserialize as LWW. Register a named strategy instead.",
                    UserWarning, stacklevel=2,
                )
            entry = {"strategy": strat.__class__.__name__}
            # Preserve custom strategy name through round-trips
            if isinstance(strat, Custom):
                custom_name = getattr(strat, '_custom_strategy_name', None)
                if custom_name:
                    entry["_custom_strategy_name"] = custom_name
                elif hasattr(strat, '_fn') and hasattr(strat._fn, '__name__'):
                    entry["_custom_strategy_name"] = strat._fn.__name__
            # Also preserve the name for deserialized custom strategies stored
            # as LWW placeholders (from a previous round-trip)
            stored_name = getattr(strat, '_custom_strategy_name', None)
            if stored_name and not isinstance(strat, Custom):
                entry["_custom_strategy_name"] = stored_name
            if isinstance(strat, UnionSet):
                entry["separator"] = strat.separator
            elif isinstance(strat, Concat):
                entry["separator"] = strat.separator
                entry["dedup"] = strat.dedup
            elif isinstance(strat, Priority):
                entry["levels"] = strat.levels
            d[field] = entry
        d["__default__"] = {"strategy": self._default.__class__.__name__}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MergeSchema:
        """Deserialize schema from dict."""
        d = dict(d)  # shallow copy to avoid mutating the input
        default_info = d.pop("__default__", {"strategy": "LWW"})
        default_cls = _STRATEGY_REGISTRY.get(default_info["strategy"], LWW)
        default = default_cls()

        strategies = {}
        for field, info in d.items():
            strat_cls = _STRATEGY_REGISTRY.get(info["strategy"], LWW)
            if strat_cls == Custom:
                # DEF-011: Custom strategies can't be deserialized -- use LWW
                # fallback but preserve the original strategy name so it
                # survives further round-trips.  Warning is deferred until the
                # strategy is actually invoked (not on deserialization).
                fallback = LWW()
                custom_name = info.get("_custom_strategy_name")
                if custom_name:
                    fallback._custom_strategy_name = custom_name  # type: ignore[attr-defined]  # dynamic attr set on strategy for debugging/introspection
                strategies[field] = fallback
            elif strat_cls == UnionSet:
                strategies[field] = UnionSet(separator=info.get("separator", ","))
            elif strat_cls == Concat:
                strategies[field] = Concat(separator=info.get("separator", " | "), dedup=info.get("dedup", True))
            elif strat_cls == Priority:
                strategies[field] = Priority(levels=info.get("levels", []))
            else:
                strategies[field] = strat_cls()
        return cls(default=default, **strategies)

    def __repr__(self):
        fields = ", ".join(f"{k}={v.name()}" for k, v in self._strategies.items())
        return f"MergeSchema(default={self._default.name()}, {fields})"
