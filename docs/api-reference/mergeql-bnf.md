# SPDX-License-Identifier: BUSL-1.1

# MergeQL BNF Grammar Reference

MergeQL is the SQL-like query language built into crdt-merge. It lets you
express CRDT-aware merge operations as declarative statements rather than
imperative Python code. The parser lives in `crdt_merge/mergeql.py`.

---

## Overview

A MergeQL statement names two or more registered data sources, declares a join
key, and optionally controls per-field conflict resolution, post-merge
filtering, column renaming, and output size. Statements are case-insensitive
for keywords.

```
MERGE src1, src2 ON id
MERGE src1, src2 ON id STRATEGY name='lww', score='max'
MERGE src1, src2, src3 ON id WHERE active = true LIMIT 500
EXPLAIN MERGE a, b ON id STRATEGY salary='max'
```

---

## Full BNF Grammar

The grammar below uses standard BNF notation:
- `::=` defines a production rule
- `|` separates alternatives
- `<non-terminal>` names a grammar symbol
- `"terminal"` is a literal token (case-insensitive for keywords)
- `[item]` denotes zero or one occurrence
- `{item}` denotes zero or more occurrences

```bnf
<statement>
    ::= [<explain-prefix>] <merge-clause>
          <on-clause>
          [<strategy-clause>]
          [<where-clause>]
          [<limit-clause>]
          [<map-clause>]

<explain-prefix>
    ::= "EXPLAIN"

<merge-clause>
    ::= "MERGE" <source-list>

<source-list>
    ::= <identifier> { "," <identifier> }

<on-clause>
    ::= "ON" <identifier>

<strategy-clause>
    ::= "STRATEGY" <strategy-list>

<strategy-list>
    ::= <strategy-assignment> { "," <strategy-assignment> }

<strategy-assignment>
    ::= <identifier> "=" <strategy-name>

<strategy-name>
    ::= <bare-identifier>
      | <quoted-string>

<where-clause>
    ::= "WHERE" <condition>

<condition>
    ::= <or-condition>

<or-condition>
    ::= <and-condition> { "OR" <and-condition> }

<and-condition>
    ::= <primary-condition> { "AND" <primary-condition> }

<primary-condition>
    ::= "(" <condition> ")"
      | <null-check>
      | <like-check>
      | <in-check>
      | <comparison>

<null-check>
    ::= <identifier> "IS" "NULL"
      | <identifier> "IS" "NOT" "NULL"

<like-check>
    ::= <identifier> "LIKE" <pattern>

<pattern>
    ::= <quoted-string>
      | <bare-word>

<in-check>
    ::= <identifier> "IN" "(" <value-list> ")"

<value-list>
    ::= <value> { "," <value> }

<comparison>
    ::= <identifier> <comparison-op> <value>

<comparison-op>
    ::= "="
      | "<>"
      | "!="
      | "<"
      | ">"
      | "<="
      | ">="

<value>
    ::= <quoted-string>
      | <number>
      | <bare-word>

<limit-clause>
    ::= "LIMIT" <integer>

<map-clause>
    ::= "MAP" <mapping-list>

<mapping-list>
    ::= <mapping-pair> { "," <mapping-pair> }

<mapping-pair>
    ::= <identifier> "->" <identifier>

<identifier>
    ::= <bare-identifier>
      | <quoted-string>

<bare-identifier>
    ::= /[^\s,()='"-]+/

<quoted-string>
    ::= "'" { <char> } "'"
      | '"' { <char } '"'

<number>
    ::= /[+-]?[0-9]+(\.[0-9]+)?/

<integer>
    ::= /[0-9]+/
```

---

## Clause Reference

### MERGE ... ON

Required. Names at least two registered sources and the column used as the
join key. Sources that share a key value are merged; sources that do not share
a key value are passed through unchanged.

```
MERGE source1, source2 ON id
MERGE east_region, west_region, central_region ON user_id
```

### STRATEGY

Optional. Assigns a conflict-resolution strategy to individual fields. Fields
not listed use the default strategy (`lww`).

```
STRATEGY field='strategy-name', ...
```

**Built-in strategy names** (case-insensitive):

| Name | Aliases | Description |
|------|---------|-------------|
| `lww` | — | Last-Writer-Wins by timestamp |
| `max` | `maxwins` | Keep the larger value |
| `min` | `minwins` | Keep the smaller value |
| `union` | `unionset` | Union of set values |
| `concat` | — | Concatenate string/list values |
| `priority` | — | Prefer source listed first |
| `longest` | `longestwins` | Keep the longest string |

**Custom strategies** registered via `MergeQL.register_strategy()` are
referenced with the `custom:` prefix:

```
STRATEGY notes='custom:my_resolver'
```

### WHERE

Optional. Filters the *merged* result set. The condition is evaluated after
merge conflict resolution. Operators and constructs:

- Comparison: `field = value`, `field != value`, `field <> value`, `field > value`, `field < value`, `field >= value`, `field <= value`
- Null check: `field IS NULL`, `field IS NOT NULL`
- Pattern match: `field LIKE 'pattern'` — `%` matches any substring, `_` matches a single character
- Set membership: `field IN ('a', 'b', 'c')`
- Boolean logic: `AND`, `OR`, parenthesized sub-expressions `(A AND B) OR C`
- Operator precedence: `AND` binds more tightly than `OR`; parentheses override

Numeric comparisons are attempted first; string comparisons are used as
fallback when either operand is non-numeric.

### LIMIT

Optional. Restricts the output to the first *n* rows (applied after WHERE
filtering).

```
LIMIT 100
LIMIT 1000
```

### MAP

Optional. Renames columns in the merged result using `old_name -> new_name`
pairs. Applied after WHERE filtering and before LIMIT.

```
MAP old_col -> new_col, another_old -> another_new
```

### EXPLAIN prefix

Prepend `EXPLAIN` to any statement to return a `MergePlan` showing the
execution steps and row-count estimates without executing the merge.

```
EXPLAIN MERGE a, b ON id STRATEGY score='max'
```

---

## Examples

### 1. Minimal two-source merge

```sql
MERGE users_nyc, users_london ON id
```

### 2. Three-way merge with custom strategies

```sql
MERGE east, west, central
ON employee_id
STRATEGY name='lww', salary='max', status='priority'
```

### 3. Merge with WHERE filtering

```sql
MERGE snapshot_2024, snapshot_2025
ON record_id
WHERE active = true
```

### 4. Merge with LIMIT

```sql
MERGE orders_old, orders_new
ON order_id
STRATEGY total='max'
LIMIT 500
```

### 5. Merge and filter with OR

```sql
MERGE catalog_a, catalog_b
ON sku
WHERE region = 'EU' OR region = 'UK'
```

### 6. Merge with IS NULL check

```sql
MERGE records_v1, records_v2
ON id
WHERE deleted_at IS NULL
```

### 7. Merge with LIKE pattern

```sql
MERGE contacts_a, contacts_b
ON contact_id
WHERE email LIKE '%@example.com'
```

### 8. Merge with IN clause

```sql
MERGE products_a, products_b
ON product_id
WHERE category IN ('electronics', 'software', 'hardware')
```

### 9. Merge with column rename

```sql
MERGE legacy_data, new_data
ON cust_id
MAP cust_id -> customer_id, fname -> first_name
```

### 10. Merge with combined strategy, filter, and limit

```sql
MERGE sales_q1, sales_q2
ON deal_id
STRATEGY amount='max', stage='lww', notes='concat'
WHERE stage != 'lost'
LIMIT 200
```

### 11. Explain plan

```sql
EXPLAIN MERGE model_a, model_b, model_c
ON entity_id
STRATEGY score='max', label='lww'
```

### 12. Custom strategy reference

```sql
MERGE left_data, right_data
ON primary_key
STRATEGY resolution='custom:my_resolver', priority='priority'
WHERE score >= 50
```

---

## Notes on Supported vs. Planned Features

### Currently Supported

- `MERGE ... ON` with two or more named sources
- `STRATEGY` clause with per-field strategy assignments
- `WHERE` clause with comparison, `IS NULL`, `IS NOT NULL`, `LIKE`, `IN`, `AND`, `OR`, and parenthesized sub-expressions
- `LIMIT` clause
- `MAP` clause for column renaming
- `EXPLAIN` prefix for query plan inspection
- Case-insensitive keywords
- Single-quoted and double-quoted string literals in `STRATEGY` values
- `custom:name` strategy references

### Not Yet Supported (Planned)

- `SELECT` column projection (currently all columns are returned)
- `FROM` keyword alias for `MERGE` (SQL-compatibility mode)
- `ORDER BY` clause for deterministic row ordering
- `GROUP BY` aggregation
- `JOIN` syntax for heterogeneous key-based joins
- Sub-queries
- `NOT` unary operator in WHERE conditions (workaround: use `!=` or `<>`)
- Numeric LIKE patterns
- Multi-column join keys via `ON (col1, col2)` syntax (workaround: comma-separated string in `--key` via CLI)
- `OFFSET` for pagination
- Window functions

### Behavioral Notes

- An unparseable WHERE sub-expression is treated permissively (passes through) rather than raising an error; this allows gradual adoption.
- `<>` is normalized to `!=` internally; both forms are accepted.
- String comparisons use Python's lexicographic ordering when numeric coercion fails.
- The `LIMIT` clause applies after WHERE filtering, not before.
- `MAP` is applied before `LIMIT`.
