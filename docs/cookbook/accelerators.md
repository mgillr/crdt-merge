# Accelerator Recipes

## Recipe 1: DuckDB SQL Merge

```python
import duckdb
from crdt_merge.accelerators.duckdb_udf import DuckDBMergeUDF

conn = duckdb.connect()

# Create sample tables
conn.sql("CREATE TABLE users_a (id INT, name VARCHAR, email VARCHAR)")
conn.sql("INSERT INTO users_a VALUES (1, 'Alice', 'alice@old.com'), (2, 'Bob', 'bob@co.com')")
conn.sql("CREATE TABLE users_b (id INT, name VARCHAR, email VARCHAR)")
conn.sql("INSERT INTO users_b VALUES (1, 'Alice', 'alice@new.com'), (3, 'Charlie', 'charlie@co.com')")

# Register CRDT merge UDFs on the connection
udf = DuckDBMergeUDF(connection=conn)
udf.register()

# Merge the two tables using LWW strategy for the email column
result = udf.merge_tables("users_a", "users_b", key="id", strategies={"email": "LWW"})
print(result)
```

## Recipe 2: Polars Native Merge

```python
import polars as pl
from crdt_merge import merge

df_a = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
df_b = pl.DataFrame({"id": [1, 3], "name": ["Alicia", "Charlie"]})

result = merge(df_a, df_b, key="id")  # Auto-detects Polars
```

## Recipe 3: Arrow Flight Server

```python
from crdt_merge.accelerators.flight_server import FlightMergeServer

# Create and start the server (non-blocking)
server = FlightMergeServer(host="0.0.0.0", port=8815)
server.start()

# List available flight endpoints and strategies
print(server.list_flights())

# Server exposes do_merge() for merging data over gRPC.
# Clients connect via FlightMergeClient:
#   from crdt_merge.accelerators.flight_server import FlightMergeClient
#   client = FlightMergeClient("grpc://localhost:8815")
#   result = client.merge(left, right, key="id", strategies={"email": "LWW"})

# Stop the server when done
server.stop()
```

## Recipe 4: Streamlit Dashboard

```python
import streamlit as st
from crdt_merge.accelerators.streamlit_ui import StreamlitMergeUI

# Create the merge UI component
ui = StreamlitMergeUI(title="CRDT Merge Explorer")

# Render the interactive merge widget (returns merged rows or None)
result = ui.render(df_a, df_b, key="id", strategies={"email": "LWW"})

if result is not None:
    st.dataframe(result)
```

## Recipe 5: dbt Package Integration

Generate cross-database dbt macros and models that implement CRDT merge
strategies. Works with Snowflake, BigQuery, Postgres, and DuckDB.

```python
from crdt_merge.accelerators.dbt_package import DbtMergeGenerator

# Create a generator (optionally pin a warehouse; omit for auto-detect via target.type)
gen = DbtMergeGenerator(warehouse="snowflake")

# Generate a dbt Jinja macro that merges two staging models on customer_id
macro_sql = gen.generate_macro(
    sources=["stg_east", "stg_west"],
    key="customer_id",
    strategies={"name": "lww", "revenue": "max", "tags": "union"},
    timestamp_column="_merged_at",
)
print(macro_sql)  # Complete Jinja macro ready to drop into your dbt project

# Generate a pre-built dbt model that materialises the merge as a table
model_sql = gen.generate_model(
    model_name="merged_customers",
    sources=["stg_east", "stg_west"],
    key="customer_id",
    strategies={"name": "lww", "revenue": "max"},
    materialization="table",
)
print(model_sql)

# Generate the packages.yml snippet to include crdt_merge in your dbt project
packages_yml = gen.generate_packages_yml()
print(packages_yml)

# Generate a schema.yml entry with tests for the merge model
schema_yml = gen.generate_schema_yml(
    model_name="merged_customers",
    key="customer_id",
    strategies={"name": "lww", "revenue": "max"},
)
print(schema_yml)
```

## Recipe 6: Airbyte Merge Destination

Use CRDT merge as a custom Airbyte destination — incoming records are
automatically merged with existing data using configurable strategies.

```python
from crdt_merge.accelerators.airbyte import AirbyteMergeDestination

# Create the destination connector
dest = AirbyteMergeDestination(default_key="id", default_strategy="lww")

# Validate the connector spec and connection config
spec = dest.get_spec()
print(spec["connectionSpecification"]["title"])  # "CRDT Merge Destination"

ok, err = dest.check_connection({"default_key": "id", "default_strategy": "lww"})
assert ok and err is None

# Configure a stream with per-column strategy overrides
dest.configure_stream(
    "users",
    key_column="id",
    strategies={"email": "lww", "score": "max"},
    default_strategy="lww",
)

# Write an initial batch of records
dest.write("users", [
    {"id": 1, "email": "alice@old.com", "score": 80},
    {"id": 2, "email": "bob@co.com",    "score": 70},
])

# Write a second batch — conflicts are resolved automatically
result = dest.write("users", [
    {"id": 1, "email": "alice@new.com", "score": 95},  # email→LWW, score→Max
    {"id": 3, "email": "charlie@co.com", "score": 60},
])
print(result.records_merged, "records merged,", result.conflicts_resolved, "conflicts resolved")

# Read back the merged stream
for record in dest.read_stream("users"):
    print(record)
```

## Recipe 7: DuckLake Conflict Resolver

Snapshot-based field-level conflict resolution for DuckLake, with Merkle
change detection, branching, and a full audit trail.

```python
from crdt_merge.accelerators.ducklake import DuckLakeConflictResolver
from crdt_merge.strategies import MergeSchema, LWW, MaxWins

# Define a schema: LWW by default, MaxWins for the salary column
schema = MergeSchema(default=LWW(), salary=MaxWins())
resolver = DuckLakeConflictResolver(schema=schema)

# Register two snapshots representing data from different sources
resolver.register_snapshot("east", [
    {"id": 1, "name": "Alice", "salary": 90_000},
    {"id": 2, "name": "Bob",   "salary": 80_000},
])
resolver.register_snapshot("west", [
    {"id": 1, "name": "Alicia", "salary": 95_000},
    {"id": 3, "name": "Charlie", "salary": 70_000},
])

# Detect field-level changes between the two snapshots
diff = resolver.detect_changes("east", "west", key="id")
print(f"{diff.num_changes} change(s) detected")
for fc in diff.modified_fields:
    print(f"  key={fc.key} field={fc.field}: {fc.value_a!r} → {fc.value_b!r}")

# Merge the snapshots — conflicts are resolved per the schema
result = resolver.merge_snapshots("east", "west", key="id")
print(f"Merged {result.total_rows} rows, {result.conflicts_resolved} conflicts resolved")
for row in result.data:
    print(row)

# Inspect the audit trail to see which source won each conflict
for entry in resolver.audit_trail():
    print(entry)

# Create branches for isolated editing, then merge them
resolver.branch("east", "feature-a")
resolver.branch("east", "feature-b")
# (simulate edits on each branch via update_branch)
merged = resolver.merge_branches("feature-a", "feature-b", key="id")
print(f"Branch merge: {merged.total_rows} rows")
```

## Recipe 8: SQLite Extension

Local-first CRDT merge for SQLite — create merge-aware tables, insert with
automatic conflict resolution, sync between databases, and inspect vector clocks.

```python
from crdt_merge.accelerators.sqlite_ext import SQLiteCRDTMerge

# Create two independent SQLite nodes (in-memory for this demo)
node_a = SQLiteCRDTMerge(db_path=":memory:")
node_b = SQLiteCRDTMerge(db_path=":memory:")

# Register CRDT merge functions (crdt_lww, crdt_max, crdt_min, crdt_merge)
node_a.register()
node_b.register()

# Create a CRDT-managed table on each node with per-column strategies
for node in (node_a, node_b):
    node.create_crdt_table(
        "users",
        columns={"name": "TEXT", "salary": "REAL"},
        key="id",
        strategies={"salary": "max", "name": "lww"},
    )

# Insert records on node A
node_a.merge_insert("users", [
    {"id": "1", "name": "Alice", "salary": 90_000},
    {"id": "2", "name": "Bob",   "salary": 80_000},
], node_id="node_a")

# Insert a conflicting record on node B
node_b.merge_insert("users", [
    {"id": "1", "name": "Alicia", "salary": 95_000},
], node_id="node_b")

# Merge-insert node B's data into node A — conflicts auto-resolve
node_a.merge_insert(
    "users",
    node_b.read_table("users"),
    node_id="node_b",
)

# Read the merged result (salary→max wins, name→lww wins)
for row in node_a.read_table("users"):
    print(row)

# Inspect the vector clock for a specific record
clock = node_a.get_clock("users", "1")
print("Vector clock for id=1:", clock)  # e.g. {"node_a": 1, "node_b": 1}

# Compact: remove orphaned clock entries for deleted keys
stats = node_a.compact("users")
print("Clock entries removed:", stats["clock_entries_removed"])

# You can also merge two plain SQLite tables directly
merged = node_a.merge_tables("users", "users", key="id", strategies={"salary": "max"})
print("Table merge result:", merged)
```
