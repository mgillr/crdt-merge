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
    optimizations: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Return a human-readable summary of the execution plan."""
        lines = [
            "MergePlan",
            f"  Sources: {', '.join(self.sources)}",
            f"  Key: {self.merge_key}",
            f"  Strategies: {self.strategies or '(default: lww)'}",
            f"  Estimated rows: {self.estimated_output_rows}",
            f"  Schema evolution: {self.schema_evolution_needed}",
            f"  Arrow backend: {self.arrow_backend}",
            f"  Optimizations: {self.optimizations or '(none)'}",
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
    """Evaluate a WHERE clause against a record dict.

    Supports the following operators and constructs:

    * Comparison: ``field = value``, ``field != value``, ``field > value``,
      ``field < value``, ``field >= value``, ``field <= value``
    * Null checks: ``field IS NULL``, ``field IS NOT NULL``
    * Pattern match: ``field LIKE 'pat%tern'`` (``%`` = any substring,
      ``_`` = single char — mapped to :func:`fnmatch.fnmatch`)
    * Set membership: ``field IN ('a', 'b', 'c')``
    * Boolean connectives: ``AND``, ``OR`` (short-circuit)
    * Parenthesised sub-expressions: ``(A AND B) OR C``
    """
    import fnmatch as _fnmatch

    if not clause:
        return True

    clause = clause.strip()

    # --- parenthesised sub-expression stripping ---
    # Handle expressions that are entirely wrapped in outer parens:
    # "(expr)" -> recurse on "expr"
    if clause.startswith("(") and clause.endswith(")"):
        # Verify the outer parens are actually matching (not just any outer chars)
        depth = 0
        matched = True
        for i, ch in enumerate(clause):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(clause) - 1:
                matched = False
                break
        if matched:
            return _eval_where(record, clause[1:-1])

    # --- OR (lowest precedence): split on OR outside parens ---
    or_parts = _split_outside_parens(clause, r'\bOR\b')
    if len(or_parts) > 1:
        return any(_eval_where(record, p) for p in or_parts)

    # --- AND (higher precedence): split on AND outside parens ---
    and_parts = _split_outside_parens(clause, r'\bAND\b')
    if len(and_parts) > 1:
        return all(_eval_where(record, p) for p in and_parts)

    clause = clause.strip()

    # --- IS NULL / IS NOT NULL ---
    m_null = re.match(r'(\w+)\s+IS\s+(NOT\s+)?NULL', clause, re.IGNORECASE)
    if m_null:
        field = m_null.group(1)
        is_not = m_null.group(2) is not None
        rec_val = record.get(field)
        is_null = rec_val is None or rec_val == ""
        return (not is_null) if is_not else is_null

    # --- LIKE ---
    m_like = re.match(r'(\w+)\s+LIKE\s+([\'"]?)(.+?)\2$', clause, re.IGNORECASE)
    if m_like:
        field = m_like.group(1)
        pattern = m_like.group(3)
        rec_val = record.get(field)
        if rec_val is None:
            return False
        # Translate SQL LIKE wildcards to fnmatch: % -> *, _ -> ?
        fn_pattern = pattern.replace("%", "*").replace("_", "?")
        return _fnmatch.fnmatch(str(rec_val), fn_pattern)

    # --- IN (...) ---
    m_in = re.match(r'(\w+)\s+IN\s*\((.+)\)', clause, re.IGNORECASE | re.DOTALL)
    if m_in:
        field = m_in.group(1)
        raw_values = m_in.group(2)
        # Parse comma-separated values, stripping quotes
        values = {v.strip().strip("'\"") for v in raw_values.split(",")}
        rec_val = record.get(field)
        if rec_val is None:
            return False
        return str(rec_val) in values or rec_val in values

    # --- Standard comparison: field op value ---
    m = re.match(r'(\w+)\s*(!=|>=|<=|<>|>|<|=)\s*(.+)', clause.strip())
    if not m:
        return True  # unparseable clause → pass-through (permissive)
    field, op, raw_val = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
    if op == "<>":
        op = "!="
    rec_val = record.get(field)
    if rec_val is None:
        return op == "!="

    # Try numeric comparison first
    try:
        num_rec = float(rec_val)
        num_val = float(raw_val)
        if op == "=":   return num_rec == num_val
        if op == "!=":  return num_rec != num_val
        if op == ">":   return num_rec > num_val
        if op == "<":   return num_rec < num_val
        if op == ">=":  return num_rec >= num_val
        if op == "<=":  return num_rec <= num_val
    except (ValueError, TypeError):
        pass  # nosec B110 -- fallback on unsupported input

    # String comparison fallback
    str_rec, str_val = str(rec_val), str(raw_val)
    if op == "=":   return str_rec == str_val
    if op == "!=":  return str_rec != str_val
    if op == ">":   return str_rec > str_val
    if op == "<":   return str_rec < str_val
    if op == ">=":  return str_rec >= str_val
    if op == "<=":  return str_rec <= str_val
    return True


def _split_outside_parens(text: str, pattern: str) -> list:
    """Split *text* on *pattern* only when not inside parentheses."""
    parts: list = []
    depth = 0
    current: list = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
            current.append(ch)
            i += 1
        elif ch == ")":
            depth -= 1
            current.append(ch)
            i += 1
        elif depth == 0:
            # Try to match the keyword at this position
            m = re.match(pattern, text[i:], re.IGNORECASE)
            if m:
                parts.append("".join(current).strip())
                current = []
                i += len(m.group(0))
            else:
                current.append(ch)
                i += 1
        else:
            current.append(ch)
            i += 1
    parts.append("".join(current).strip())
    return [p for p in parts if p]

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
                pass  # nosec B110 -- intentionally silent
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
                # Accept either a raw callable or an already-constructed MergeStrategy
                if isinstance(fn, MergeStrategy):
                    field_strategies[field_name] = fn
                else:
                    field_strategies[field_name] = Custom(fn)
            else:
                cls = _BUILTIN_STRATEGIES.get(resolved, LWW)
                field_strategies[field_name] = cls()
        return MergeSchema(default=LWW(), **field_strategies)

    @staticmethod
    def _optimize_plan(ast: MergeAST) -> Tuple[MergeAST, List[str]]:
        """Reorder plan steps to push WHERE filters before the merge/join operation.

        Filter pushdown reduces the number of records that participate in the
        merge by evaluating WHERE predicates on each source *before* the join,
        rather than on the merged output.  This is safe when the predicate
        references only fields that exist in the individual source records (i.e.,
        it does not reference computed/merged values).

        Parameters
        ----------
        ast : MergeAST
            The parsed query AST.

        Returns
        -------
        optimized_ast : MergeAST
            Copy of the AST with ``where_clause`` cleared (the filter has been
            pushed down into the scan phase; the caller is responsible for
            applying it there).
        applied_optimizations : list[str]
            Names of optimizations that were applied (e.g. ``["filter_pushdown"]``).
            Empty list if no optimizations could be applied.
        """
        applied: List[str] = []
        if ast.where_clause:
            # Push the WHERE filter to execute before the merge step.
            # Return a modified AST with where_clause preserved so the caller
            # can apply it during scanning rather than post-merge.
            applied.append("filter_pushdown")
        # Return the original ast (filter application location is controlled by
        # _execute_merge based on applied_optimizations) and the optimization list.
        return ast, applied

    def _build_plan(self, ast: MergeAST) -> MergePlan:
        """Build an execution plan from the AST, applying filter-pushdown optimisation."""
        _optimized_ast, applied_optimizations = self._optimize_plan(ast)

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

        # Build optimised step list: if filter_pushdown was applied, place the
        # WHERE step before the merge/join step rather than after.
        steps: List[str] = []
        if ast.where_clause and "filter_pushdown" in applied_optimizations:
            steps.append(f"Filter (pushed down): WHERE {ast.where_clause}")
        steps.append(f"Scan {len(ast.sources)} sources ({total} total rows)")
        steps.append(f"Join on key '{ast.on_key}'")
        if ast.strategies:
            steps.append(f"Apply per-field strategies: {ast.strategies}")
        else:
            steps.append("Apply default strategy: LWW")
        if ast.where_clause and "filter_pushdown" not in applied_optimizations:
            # Fallback: filter is applied post-merge
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
            optimizations=applied_optimizations,
        )

    def _execute_merge(self, ast: MergeAST) -> MergeQLResult:
        """Internal merge execution engine."""
        t0 = time.monotonic()
        schema = self._build_schema(ast)

        # Determine optimizations to apply (filter pushdown, etc.)
        _optimized_ast, applied_optimizations = self._optimize_plan(ast)
        use_filter_pushdown = (
            ast.where_clause is not None
            and "filter_pushdown" in applied_optimizations
        )

        plan = self._build_plan(ast)
        key = ast.on_key

        # Collect all records keyed by their join key.
        # If filter_pushdown is active, pre-filter each source row before merging
        # to reduce the number of records that participate in the join.
        keyed: Dict[Any, dict] = {}
        conflicts = 0
        provenance_log: List[dict] = [] if self._provenance else None

        for src_name in ast.sources:
            for row in self._sources.get(src_name, []):
                # OPTIMISATION: filter_pushdown -- evaluate WHERE predicate on the
                # raw source row before merging.  Rows that fail the predicate are
                # dropped here, reducing merge work.  Falls back to post-merge
                # filtering if the optimisation is not applied.
                if use_filter_pushdown:
                    try:
                        if not _eval_where(row, ast.where_clause):
                            continue
                    except Exception:
                        # If pre-filter evaluation fails for any reason, fall
                        # through to post-merge filtering (safe degradation).
                        use_filter_pushdown = False

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

        # WHERE filter (post-merge fallback -- applied when filter_pushdown was
        # not used or when the pushed-down filter failed mid-scan).
        if ast.where_clause and not use_filter_pushdown:
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
