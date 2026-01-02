# Copyright 2026 Ryan Gillespie / Optitransfer
# SPDX-License-Identifier: BUSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/mgillr/crdt-merge/blob/main/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# On 2028-03-29 this file converts to Apache License, Version 2.0.

"""
MergeQL — SQL-like interface for CRDT merge operations.

Instead of writing Python code, users express merges as SQL statements:

    from crdt_merge.mergeql import MergeQL

    ql = MergeQL()
    ql.register("users_nyc", nyc_data)
    ql.register("users_london", london_data)

    result = ql.execute('''
        MERGE users_nyc, users_london
        ON id
        STRATEGY name='lww', salary='max', status='custom:priority_resolver'
    ''')

Supported syntax:
    MERGE source1, source2 [, sourceN...]
    ON key_column
    [STRATEGY field1='strategy1', field2='strategy2']
    [WHERE condition]
    [LIMIT n]
    [MAP old_col -> new_col]

    EXPLAIN MERGE ...  (returns MergePlan without executing)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from crdt_merge.strategies import (
    MergeSchema, MergeStrategy, LWW, MaxWins, MinWins,
    UnionSet, Concat, Priority, LongestWins, Custom,
)

# ---------------------------------------------------------------------------
# Strategy name → class mapping (lowercase for case-insensitive lookup)
# ---------------------------------------------------------------------------
_BUILTIN_STRATEGIES: Dict[str, type] = {
    "lww": LWW,
    "max": MaxWins,
    "maxwins": MaxWins,
    "min": MinWins,
    "minwins": MinWins,
    "union": UnionSet,
    "unionset": UnionSet,
    "concat": Concat,
    "priority": Priority,
    "longest": LongestWins,
    "longestwins": LongestWins,
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MergeQLError(Exception):
    """Base exception for MergeQL errors."""
    pass


class MergeQLSyntaxError(MergeQLError):
    """Raised when MergeQL query has syntax errors."""
    pass


class MergeQLValidationError(MergeQLError):
    """Raised when MergeQL query references invalid sources or strategies."""
    pass


# ---------------------------------------------------------------------------
# AST Nodes
# ---------------------------------------------------------------------------

@dataclass
class MergeAST:
    """Abstract syntax tree for a MergeQL statement."""
    sources: List[str]
    on_key: str
    strategies: Dict[str, str] = field(default_factory=dict)
    where_clause: Optional[str] = None
    explain: bool = False
    schema_mapping: Optional[Dict[str, str]] = None
    limit: Optional[int] = None


@dataclass
class MergePlan:
    """Execution plan for a MergeQL query."""
    sources: List[str]
    source_sizes: Dict[str, int]
    merge_key: str
    strategies: Dict[str, str]
    estimated_output_rows: int
    schema_evolution_needed: bool
    arrow_backend: bool
    steps: List[str]

    def __str__(self) -> str:
        lines = [
            "MergePlan",
            f"  Sources: {', '.join(self.sources)}",
            f"  Key: {self.merge_key}",
            f"  Strategies: {self.strategies or '(default: lww)'}",
            f"  Estimated rows: {self.estimated_output_rows}",
            f"  Schema evolution: {self.schema_evolution_needed}",
            f"  Arrow backend: {self.arrow_backend}",
            "  Steps:",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"    {i}. {step}")
        return "\n".join(lines)


@dataclass
class MergeQLResult:
    """Result of a MergeQL execution."""
    data: List[dict]
    plan: MergePlan
    conflicts: int
    provenance: Optional[List[dict]] = None
    merge_time_ms: float = 0.0
    sources_merged: int = 0


# ---------------------------------------------------------------------------
# Tokenizer helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
      '(?:[^'\\]|\\.)*'      # single-quoted string
    | "(?:[^"\\]|\\.)*"       # double-quoted string
    | ->                      # arrow for MAP clause
    | [(),=]                  # single-char punctuation
    | [^\s,()='"-]+           # bare word / number
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class MergeQLParser:
    """Parse MergeQL SQL-like syntax into AST nodes.

    Supported syntax:
        MERGE source1, source2 [, sourceN...]
        ON key_column
        [STRATEGY field1='strategy1', field2='strategy2']
        [WHERE condition]
        [LIMIT n]
        [MAP old_col -> new_col]

        EXPLAIN MERGE ...  (returns MergePlan without executing)
    """

    KEYWORDS = {"MERGE", "ON", "STRATEGY", "WHERE", "LIMIT", "MAP", "EXPLAIN"}

    def parse(self, query: str) -> MergeAST:
        """Parse a MergeQL query string into an AST.

        Args:
            query: SQL-like merge statement

        Returns:
            MergeAST node

        Raises:
            MergeQLSyntaxError: If query is malformed
            MergeQLValidationError: If query references unknown sources
        """
        if query is None or not query.strip():
            raise MergeQLSyntaxError("Empty query")

        tokens = self._tokenize(query)
        if not tokens:
            raise MergeQLSyntaxError("Empty query")

        pos = 0
        explain = False

        # Check for EXPLAIN prefix
        if tokens[pos].upper() == "EXPLAIN":
            explain = True
            pos += 1
            if pos >= len(tokens):
                raise MergeQLSyntaxError("Expected MERGE after EXPLAIN")

        # Expect MERGE keyword
        if pos >= len(tokens) or tokens[pos].upper() != "MERGE":
            raise MergeQLSyntaxError(
                f"Expected MERGE keyword, got '{tokens[pos]}'" if pos < len(tokens)
                else "Expected MERGE keyword"
            )
        pos += 1

        # Parse sources
        sources, pos = self._parse_sources(tokens, pos)
        if not sources:
            raise MergeQLSyntaxError("No sources specified after MERGE")

        # Expect ON keyword
        if pos >= len(tokens) or tokens[pos].upper() != "ON":
            raise MergeQLSyntaxError("Expected ON keyword after source list")
        pos += 1

        if pos >= len(tokens):
            raise MergeQLSyntaxError("Expected key column after ON")
        on_key = tokens[pos]
        pos += 1

        # Parse optional clauses
        strategies: Dict[str, str] = {}
        where_clause: Optional[str] = None
        limit: Optional[int] = None
        schema_mapping: Optional[Dict[str, str]] = None

        while pos < len(tokens):
            kw = tokens[pos].upper()
            if kw == "STRATEGY":
                pos += 1
                strategies, pos = self._parse_strategies(tokens, pos)
            elif kw == "WHERE":
                pos += 1
                where_clause, pos = self._parse_where(tokens, pos)
            elif kw == "LIMIT":
                pos += 1
                if pos >= len(tokens):
                    raise MergeQLSyntaxError("Expected number after LIMIT")
                try:
                    limit = int(tokens[pos])
                except ValueError:
                    raise MergeQLSyntaxError(f"LIMIT must be an integer, got '{tokens[pos]}'")
                pos += 1
            elif kw == "MAP":
                pos += 1
                schema_mapping, pos = self._parse_mapping(tokens, pos)
            else:
                raise MergeQLSyntaxError(f"Unexpected token '{tokens[pos]}'")

        return MergeAST(
            sources=sources,
            on_key=on_key,
            strategies=strategies,
            where_clause=where_clause,
            explain=explain,
            schema_mapping=schema_mapping,
            limit=limit,
        )

    def _tokenize(self, query: str) -> List[str]:
        """Split query into tokens."""
        raw = _TOKEN_RE.findall(query)
        # Strip surrounding quotes from quoted strings but keep content
        cleaned: List[str] = []
        for t in raw:
            if (t.startswith("'") and t.endswith("'")) or (t.startswith('"') and t.endswith('"')):
                cleaned.append(t[1:-1])
            else:
                cleaned.append(t)
        return cleaned

    def _parse_sources(self, tokens: List[str], pos: int) -> Tuple[List[str], int]:
        """Parse MERGE source1, source2, ..."""
        sources: List[str] = []
        while pos < len(tokens):
            tok = tokens[pos]
            if tok.upper() in self.KEYWORDS:
                break
            if tok == ",":
                pos += 1
                continue
            sources.append(tok)
            pos += 1
        return sources, pos

    def _parse_strategies(self, tokens: List[str], pos: int) -> Tuple[Dict[str, str], int]:
        """Parse STRATEGY field='strategy', ..."""
        strategies: Dict[str, str] = {}
        while pos < len(tokens):
            tok = tokens[pos]
            if tok.upper() in self.KEYWORDS:
                break
            if tok == ",":
                pos += 1
                continue
            # Expect field=strategy or field='strategy'
            field_name = tok
            pos += 1
            if pos >= len(tokens) or tokens[pos] != "=":
                raise MergeQLSyntaxError(
                    f"Expected '=' after field name '{field_name}' in STRATEGY clause"
                )
            pos += 1
            if pos >= len(tokens):
                raise MergeQLSyntaxError(
                    f"Expected strategy name after '{field_name}='"
                )
            strategy_name = tokens[pos]
            pos += 1
            strategies[field_name] = strategy_name
        return strategies, pos

    def _parse_where(self, tokens: List[str], pos: int) -> Tuple[Optional[str], int]:
        """Parse WHERE clause — collects everything until next keyword."""
        parts: List[str] = []
        while pos < len(tokens):
            if tokens[pos].upper() in self.KEYWORDS:
                break
            parts.append(tokens[pos])
            pos += 1
        clause = " ".join(parts) if parts else None
        return clause, pos

    def _parse_mapping(self, tokens: List[str], pos: int) -> Tuple[Optional[Dict[str, str]], int]:
        """Parse MAP old_col -> new_col, ..."""
        mapping: Dict[str, str] = {}
        while pos < len(tokens):
            tok = tokens[pos]
            if tok.upper() in self.KEYWORDS:
                break
            if tok == ",":
                pos += 1
                continue
            old_col = tok
            pos += 1
            if pos >= len(tokens) or tokens[pos] != "->":
                raise MergeQLSyntaxError(
                    f"Expected '->' after '{old_col}' in MAP clause"
                )
            pos += 1
            if pos >= len(tokens):
                raise MergeQLSyntaxError(
                    f"Expected new column name after '{old_col} ->'"
                )
            new_col = tokens[pos]
            pos += 1
            mapping[old_col] = new_col
        return mapping if mapping else None, pos


# ---------------------------------------------------------------------------
# WHERE clause evaluator (simple expressions on record dicts)
# ---------------------------------------------------------------------------

def _eval_where(record: dict, clause: str) -> bool:
    """Evaluate a simple WHERE clause against a record dict.

    Supports: field = value, field != value, field > value, field < value,
              field >= value, field <= value, and AND/OR connectives.
    """
    if not clause:
        return True

    clause = clause.strip()

    # Handle AND / OR (very simple — no parentheses)
    # Split on AND first (higher precedence grouping)
    or_parts = re.split(r'\bOR\b', clause, flags=re.IGNORECASE)
    if len(or_parts) > 1:
        return any(_eval_where(record, p) for p in or_parts)

    and_parts = re.split(r'\bAND\b', clause, flags=re.IGNORECASE)
    if len(and_parts) > 1:
        return all(_eval_where(record, p) for p in and_parts)

    # Single comparison
    m = re.match(r'(\w+)\s*(!=|>=|<=|>|<|=)\s*(.+)', clause.strip())
    if not m:
        return True  # unparseable → pass through
    field, op, raw_val = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
    rec_val = record.get(field)
    if rec_val is None:
        return False

    # Try numeric comparison
    try:
        num_rec = float(rec_val)
        num_val = float(raw_val)
        if op == "=":
            return num_rec == num_val
        if op == "!=":
            return num_rec != num_val
        if op == ">":
            return num_rec > num_val
        if op == "<":
            return num_rec < num_val
        if op == ">=":
            return num_rec >= num_val
        if op == "<=":
            return num_rec <= num_val
    except (ValueError, TypeError):
        pass

    # String comparison
    str_rec = str(rec_val)
    if op == "=":
        return str_rec == raw_val
    if op == "!=":
        return str_rec != raw_val
    if op == ">":
        return str_rec > raw_val
    if op == "<":
        return str_rec < raw_val
    if op == ">=":
        return str_rec >= raw_val
    if op == "<=":
        return str_rec <= raw_val
    return True


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MergeQL:
    """SQL-like interface for CRDT merge operations.

    MergeQL makes CRDT merge accessible to SQL users. Register data sources,
    then execute merge operations using familiar SQL syntax.

    Example:
        ql = MergeQL()
        ql.register("east", east_data)
        ql.register("west", west_data)
        result = ql.execute("MERGE east, west ON id STRATEGY name='lww'")
    """

    def __init__(self, *, arrow_backend: bool = False, provenance: bool = True) -> None:
        """Initialize MergeQL engine.

        Args:
            arrow_backend: Use Arrow engine for large datasets (requires arrow.py)
            provenance: Automatically track merge provenance
        """
        self._sources: Dict[str, Any] = {}
        self._parser = MergeQLParser()
        self._arrow_backend = arrow_backend
        self._provenance = provenance
        self._custom_strategies: Dict[str, Callable] = {}

    # ----- source management -----

    def register(self, name: str, data: Any) -> None:
        """Register a data source for merge operations.

        Args:
            name: Source identifier (used in MERGE statements)
            data: List of dicts, DataFrame, or Arrow table

        Raises:
            ValueError: If name is empty or data is invalid
        """
        if not name or not isinstance(name, str):
            raise ValueError("Source name must be a non-empty string")
        if data is None:
            raise ValueError("Data cannot be None")
        # Normalise to list-of-dicts
        self._sources[name] = self._to_records(data)

    def unregister(self, name: str) -> None:
        """Remove a registered data source."""
        self._sources.pop(name, None)

    def list_sources(self) -> List[str]:
        """List all registered source names."""
        return list(self._sources.keys())

    def source_info(self, name: str) -> Dict[str, Any]:
        """Get info about a registered source (row count, columns, etc)."""
        if name not in self._sources:
            raise MergeQLValidationError(f"Source '{name}' not registered")
        records = self._sources[name]
        columns: List[str] = []
        if records:
            columns = sorted({k for r in records for k in r.keys()})
        return {
            "name": name,
            "rows": len(records),
            "columns": columns,
        }

    # ----- strategy management -----

    def register_strategy(self, name: str, func: Callable) -> None:
        """Register a custom merge strategy for use in STRATEGY clauses.

        Args:
            name: Strategy name (used as STRATEGY field='custom:name')
            func: Strategy function with signature (val_a, val_b, ...) -> resolved
        """
        if not name:
            raise ValueError("Strategy name must be non-empty")
        self._custom_strategies[name] = func

    # ----- execution -----

    def execute(self, query: str) -> MergeQLResult:
        """Execute a MergeQL query.

        Args:
            query: SQL-like merge statement

        Returns:
            MergeQLResult with merged data, plan, and provenance

        Raises:
            MergeQLSyntaxError: If query syntax is invalid
            MergeQLValidationError: If sources or strategies not found
        """
        ast = self._parser.parse(query)
        self._validate_ast(ast)

        if ast.explain:
            plan = self._build_plan(ast)
            return MergeQLResult(
                data=[],
                plan=plan,
                conflicts=0,
                sources_merged=len(ast.sources),
            )

        return self._execute_merge(ast)

    def explain(self, query: str) -> MergePlan:
        """Show execution plan without running the merge.

        Args:
            query: SQL-like merge statement

        Returns:
            MergePlan with estimated costs and steps
        """
        ast = self._parser.parse(query)
        self._validate_ast(ast)
        return self._build_plan(ast)

    # ----- internal helpers -----

    @staticmethod
    def _to_records(data: Any) -> List[dict]:
        """Convert input data to list-of-dicts."""
        if isinstance(data, list):
            return list(data)
        # DataFrame-like
        if hasattr(data, "to_dict"):
            try:
                return data.to_dict("records")
            except Exception:
                pass
        # Iterable
        try:
            return list(data)
        except TypeError:
            raise ValueError(f"Cannot convert {type(data).__name__} to list-of-dicts")

    def _validate_ast(self, ast: MergeAST) -> None:
        """Validate the AST against registered sources and strategies."""
        for src in ast.sources:
            if src not in self._sources:
                raise MergeQLValidationError(f"Source '{src}' not registered")
        for field_name, strat_name in ast.strategies.items():
            resolved_name = strat_name.lower()
            if resolved_name.startswith("custom:"):
                custom_name = strat_name[7:]
                if custom_name not in self._custom_strategies:
                    raise MergeQLValidationError(
                        f"Custom strategy '{custom_name}' not registered"
                    )
            elif resolved_name not in _BUILTIN_STRATEGIES:
                raise MergeQLValidationError(
                    f"Unknown strategy '{strat_name}' for field '{field_name}'"
                )

    def _build_schema(self, ast: MergeAST) -> MergeSchema:
        """Convert AST strategies into a MergeSchema."""
        field_strategies: Dict[str, MergeStrategy] = {}
        for field_name, strat_name in ast.strategies.items():
            resolved = strat_name.lower()
            if resolved.startswith("custom:"):
                custom_name = strat_name[7:]
                fn = self._custom_strategies[custom_name]
                field_strategies[field_name] = Custom(fn)
            else:
                cls = _BUILTIN_STRATEGIES.get(resolved, LWW)
                field_strategies[field_name] = cls()
        return MergeSchema(default=LWW(), **field_strategies)

    def _build_plan(self, ast: MergeAST) -> MergePlan:
        """Build an execution plan from the AST."""
        source_sizes = {s: len(self._sources.get(s, [])) for s in ast.sources}
        total = sum(source_sizes.values())
        # Estimate output: max of any single source (overlapping keys merge)
        est = max(source_sizes.values()) if source_sizes else 0

        # Determine if schema evolution is needed (different column sets)
        all_cols: List[set] = []
        for src_name in ast.sources:
            recs = self._sources.get(src_name, [])
            cols = set()
            for r in recs:
                cols.update(r.keys())
            all_cols.append(cols)
        schema_evolution = len(all_cols) >= 2 and any(c != all_cols[0] for c in all_cols[1:])

        steps = [
            f"Scan {len(ast.sources)} sources ({total} total rows)",
            f"Join on key '{ast.on_key}'",
        ]
        if ast.strategies:
            steps.append(f"Apply per-field strategies: {ast.strategies}")
        else:
            steps.append("Apply default strategy: LWW")
        if ast.where_clause:
            steps.append(f"Filter: WHERE {ast.where_clause}")
        if ast.schema_mapping:
            steps.append(f"Rename columns: {ast.schema_mapping}")
        if ast.limit is not None:
            steps.append(f"Limit output to {ast.limit} rows")

        return MergePlan(
            sources=list(ast.sources),
            source_sizes=source_sizes,
            merge_key=ast.on_key,
            strategies=dict(ast.strategies),
            estimated_output_rows=est,
            schema_evolution_needed=schema_evolution,
            arrow_backend=self._arrow_backend,
            steps=steps,
        )

    def _execute_merge(self, ast: MergeAST) -> MergeQLResult:
        """Internal merge execution engine."""
        t0 = time.monotonic()
        schema = self._build_schema(ast)
        plan = self._build_plan(ast)
        key = ast.on_key

        # Collect all records keyed by their join key
        keyed: Dict[Any, dict] = {}
        conflicts = 0
        provenance_log: List[dict] = [] if self._provenance else None

        for src_name in ast.sources:
            for row in self._sources.get(src_name, []):
                k = row.get(key)
                if k is None:
                    continue
                if k in keyed:
                    existing = keyed[k]
                    merged = schema.resolve_row(existing, row)
                    # Count conflicts
                    for col in set(existing.keys()) | set(row.keys()):
                        va = existing.get(col)
                        vb = row.get(col)
                        if va is not None and vb is not None and va != vb:
                            conflicts += 1
                            if provenance_log is not None:
                                provenance_log.append({
                                    "key": k,
                                    "field": col,
                                    "value_a": va,
                                    "value_b": vb,
                                    "resolved": merged.get(col),
                                    "strategy": schema.strategy_for(col).name(),
                                    "source": src_name,
                                })
                    keyed[k] = merged
                else:
                    keyed[k] = dict(row)
                    if provenance_log is not None:
                        provenance_log.append({
                            "key": k,
                            "field": "*",
                            "source": src_name,
                            "action": "insert",
                        })

        result_data = list(keyed.values())

        # WHERE filter
        if ast.where_clause:
            result_data = [r for r in result_data if _eval_where(r, ast.where_clause)]

        # MAP column rename
        if ast.schema_mapping:
            renamed = []
            for r in result_data:
                new_r = {}
                for col, val in r.items():
                    new_col = ast.schema_mapping.get(col, col)
                    new_r[new_col] = val
                renamed.append(new_r)
            result_data = renamed

        # LIMIT
        if ast.limit is not None:
            result_data = result_data[: ast.limit]

        elapsed_ms = (time.monotonic() - t0) * 1000

        return MergeQLResult(
            data=result_data,
            plan=plan,
            conflicts=conflicts,
            provenance=provenance_log if self._provenance else None,
            merge_time_ms=round(elapsed_ms, 3),
            sources_merged=len(ast.sources),
        )


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

__all__ = [
    "MergeQL",
    "MergeQLParser",
    "MergeAST",
    "MergePlan",
    "MergeQLResult",
    "MergeQLError",
    "MergeQLSyntaxError",
    "MergeQLValidationError",
]
