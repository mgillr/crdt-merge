# tests/test_guide_provenance_schema.py
# Test suite for:
#   - docs/guides/provenance-complete-ai.md
#   - docs/guides/schema-evolution.md
#   - docs/guides/performance-tuning.md
#
# All examples use synthetic records.  Tests verify that every code snippet
# in the guides can be executed and produces sensible results.

import json
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RECORDS_A = [{"id": "1", "name": "Alice", "score": 10}]
RECORDS_B = [{"id": "1", "name": "Alice", "score": 20}]


# ===========================================================================
# provenance-complete-ai.md
# ===========================================================================

# ---------------------------------------------------------------------------
# Quick Start: Per-Field Merge Provenance
# ---------------------------------------------------------------------------

class TestProvenanceQuickStart:
    """Guide section: 'Quick Start: Per-Field Merge Provenance'."""

    def test_merge_with_provenance_basic(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance

        source_a = [
            {"id": "C001", "revenue": 4_200_000, "risk": "low",    "tier": "enterprise"},
            {"id": "C002", "revenue": 1_800_000, "risk": "medium", "tier": "smb"},
        ]
        source_b = [
            {"id": "C001", "revenue": 4_350_000, "risk": "medium", "tier": "enterprise"},
            {"id": "C003", "revenue": 950_000,   "risk": "low",    "tier": "startup"},
        ]

        merged, log = merge_with_provenance(source_a, source_b, key="id")

        assert log.merged_rows >= 1, "Expected at least one merged row"
        assert log.unique_a_rows >= 1, "C002 should be unique to A"
        assert log.unique_b_rows >= 1, "C003 should be unique to B"
        assert log.total_rows == 3, f"Expected 3 total rows, got {log.total_rows}"
        assert log.duration_ms >= 0

    def test_per_row_conflict_inspection(self):
        from crdt_merge.provenance import merge_with_provenance

        source_a = [{"id": "C001", "revenue": 4_200_000, "risk": "low"}]
        source_b = [{"id": "C001", "revenue": 4_350_000, "risk": "medium"}]

        merged, log = merge_with_provenance(source_a, source_b, key="id")

        conflicting = [r for r in log.records if r.conflict_count > 0]
        assert len(conflicting) >= 1, "Expected at least one conflicting row"

        for record in conflicting:
            for decision in record.conflicts:
                assert decision.field is not None
                assert decision.value is not None
                assert decision.strategy != ""


# ---------------------------------------------------------------------------
# Cookbook: Using Custom Strategies with Provenance
# ---------------------------------------------------------------------------

class TestProvenanceCustomStrategies:
    """Guide section: 'Cookbook: Using Custom Strategies with Provenance'."""

    def test_max_wins_revenue(self):
        from crdt_merge.provenance import merge_with_provenance
        from crdt_merge.strategies import MergeSchema, LWW, MaxWins, MinWins, UnionSet

        schema = MergeSchema(
            default=LWW(),
            revenue=MaxWins(),
            risk_score=MinWins(),
            tags=UnionSet(),
        )

        source_a = [{"id": "1", "revenue": 4200000, "risk_score": 0.3, "tags": ["enterprise"]}]
        source_b = [{"id": "1", "revenue": 4350000, "risk_score": 0.4, "tags": ["vip"]}]

        merged, log = merge_with_provenance(source_a, source_b, key="id", schema=schema)

        assert len(merged) == 1
        assert merged[0]["revenue"] == 4350000, "MaxWins: higher revenue should win"
        assert merged[0]["risk_score"] == 0.3, "MinWins: lower risk_score should win"

    def test_strategy_decisions_recorded(self):
        from crdt_merge.provenance import merge_with_provenance
        from crdt_merge.strategies import MergeSchema, MaxWins, LWW

        schema = MergeSchema(default=LWW(), revenue=MaxWins())
        source_a = [{"id": "1", "revenue": 4200000}]
        source_b = [{"id": "1", "revenue": 4350000}]

        merged, log = merge_with_provenance(source_a, source_b, key="id", schema=schema)

        decisions_by_field = {
            d.field: d
            for record in log.records
            for d in record.decisions
        }
        rev_decision = decisions_by_field.get("revenue")
        assert rev_decision is not None
        assert rev_decision.strategy == "MaxWins", f"Expected MaxWins, got {rev_decision.strategy}"


# ---------------------------------------------------------------------------
# Cookbook: Export Provenance for Compliance
# ---------------------------------------------------------------------------

class TestProvenanceExport:
    """Guide section: 'Cookbook: Export Provenance for Compliance'."""

    def test_export_json(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance

        source_a = [{"id": "P001", "diagnosis": "hypertension", "confidence": 0.91}]
        source_b = [{"id": "P001", "diagnosis": "hypertension+arrhythmia", "confidence": 0.87}]

        merged, log = merge_with_provenance(source_a, source_b, key="id")
        json_report = export_provenance(log, format="json")

        parsed = json.loads(json_report)
        assert "total_rows" in parsed
        assert "records" in parsed

    def test_export_csv(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance

        source_a = [{"id": "P001", "diagnosis": "hypertension", "confidence": 0.91}]
        source_b = [{"id": "P001", "diagnosis": "hypertension+arrhythmia", "confidence": 0.87}]

        merged, log = merge_with_provenance(source_a, source_b, key="id")
        csv_report = export_provenance(log, format="csv")

        lines = csv_report.strip().splitlines()
        assert lines[0] == "key,origin,field,source,strategy,value,alternative"
        assert len(lines) > 1, "Expected at least one data row in CSV"

    def test_export_invalid_format_raises(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance

        source_a = [{"id": "1", "name": "Alice", "score": 10}]
        source_b = [{"id": "1", "name": "Alice", "score": 20}]
        _, log = merge_with_provenance(source_a, source_b, key="id")

        with pytest.raises(ValueError):
            export_provenance(log, format="xml")


# ---------------------------------------------------------------------------
# Immutable Audit Log: Tamper-Evident Chain
# ---------------------------------------------------------------------------

class TestAuditLogBasic:
    """Guide section: 'Immutable Audit Log: Tamper-Evident Chain'."""

    def test_log_operation_and_verify(self):
        import hashlib
        import crdt_merge
        from crdt_merge.audit import AuditLog

        audit = AuditLog(node_id="hospital-node-1")

        records_a = [{"id": "1", "value": 100}]
        records_b = [{"id": "1", "value": 200}]

        merged = crdt_merge.merge(records_a, records_b, key="id")

        audit.log_operation(
            operation="merge",
            input_data={"a": records_a, "b": records_b},
            output_data=merged,
            strategy="lww",
            source_count=2,
        )

        assert audit.verify_chain(), "Audit chain should be valid after log_operation"
        assert len(audit) == 1

    def test_audit_iterable(self):
        from crdt_merge.audit import AuditLog

        audit = AuditLog(node_id="hospital-node-1")
        audit.log_operation("merge", input_data={"x": 1}, output_data={"y": 2})

        entries = list(audit)
        assert len(entries) == 1
        assert entries[0].operation == "merge"

    def test_audit_chain_multiple_entries(self):
        from crdt_merge.audit import AuditLog
        import crdt_merge

        audit = AuditLog(node_id="test-node")
        for i in range(5):
            audit.log_operation(
                "merge",
                input_data={"step": i},
                output_data={"result": i + 1},
            )

        assert len(audit) == 5
        assert audit.verify_chain()


# ---------------------------------------------------------------------------
# Cookbook: AuditedMerge — Automatic Logging
# ---------------------------------------------------------------------------

class TestAuditedMerge:
    """Guide section: 'Cookbook: AuditedMerge — Automatic Logging'."""

    def test_audited_merge_basic(self):
        from crdt_merge.audit import AuditedMerge, AuditLog
        from crdt_merge.strategies import MergeSchema, MaxWins

        audit = AuditLog(node_id="data-pipeline")
        am = AuditedMerge(audit_log=audit)

        schema = MergeSchema(score=MaxWins())

        records_a = [{"id": "U1", "score": 80, "name": "Alice"}]
        records_b = [{"id": "U1", "score": 95, "name": "Alice"}]

        result, audit_entry = am.merge(records_a, records_b, key="id", schema=schema)
        assert result[0]["score"] == 95, "MaxWins: higher score should win"

        assert audit.verify_chain()
        assert len(audit) == 1

    def test_audited_merge_returns_tuple(self):
        from crdt_merge.audit import AuditedMerge, AuditLog

        audit = AuditLog(node_id="data-pipeline")
        am = AuditedMerge(audit_log=audit)

        result, entry = am.merge(RECORDS_A, RECORDS_B, key="id")
        assert result is not None
        assert entry is not None
        assert hasattr(entry, "operation")
        assert entry.operation == "merge"

    def test_audited_merge_filter_by_operation(self):
        """
        The guide references audit.filter_by_operation() but the actual API
        exposes audit.get_entries(operation=...).  This test verifies
        get_entries works equivalently.
        """
        from crdt_merge.audit import AuditedMerge, AuditLog

        audit = AuditLog(node_id="data-pipeline")
        am = AuditedMerge(audit_log=audit)

        am.merge(RECORDS_A, RECORDS_B, key="id")

        merge_entries = audit.get_entries(operation="merge")
        assert len(merge_entries) >= 1, "Expected at least one merge entry"

    def test_audited_merge_multiple_operations(self):
        from crdt_merge.audit import AuditedMerge, AuditLog

        audit = AuditLog(node_id="data-pipeline")
        am = AuditedMerge(audit_log=audit)

        for _ in range(3):
            am.merge(RECORDS_A, RECORDS_B, key="id")

        assert len(audit) == 3
        assert audit.verify_chain()


# ---------------------------------------------------------------------------
# Cookbook: Full Audit Export
# ---------------------------------------------------------------------------

class TestAuditExport:
    """Guide section: 'Cookbook: Full Audit Export'."""

    def test_export_log_to_string(self):
        from crdt_merge.audit import AuditLog

        audit = AuditLog(node_id="prod-merger")
        audit.log_operation("merge", input_data={"x": 1}, output_data={"y": 2})

        export_str = audit.export_log()
        assert isinstance(export_str, str)

        parsed = json.loads(export_str)
        assert "entries" in parsed
        assert len(parsed["entries"]) == 1
        entry = parsed["entries"][0]
        assert "timestamp" in entry
        assert "operation" in entry
        assert "input_hash" in entry
        assert "output_hash" in entry

    def test_export_log_to_file(self, tmp_path):
        from crdt_merge.audit import AuditLog

        audit = AuditLog(node_id="prod-merger")
        audit.log_operation("merge", input_data={"x": 1}, output_data={"y": 2})

        filepath = str(tmp_path / "audit_export.json")
        audit.export_log(filepath=filepath)

        with open(filepath) as f:
            parsed = json.loads(f.read())

        assert "entries" in parsed
        assert len(parsed["entries"]) == 1

    def test_export_log_entry_hash_fields(self):
        from crdt_merge.audit import AuditLog

        audit = AuditLog(node_id="prod-merger")
        audit.log_operation("merge", input_data={"x": 1}, output_data={"y": 2})

        parsed = json.loads(audit.export_log())
        entry = parsed["entries"][0]
        # Verify hash fields are non-empty hex strings
        for field_name in ("input_hash", "output_hash"):
            assert len(entry[field_name]) == 64, f"{field_name} should be SHA-256 hex"


# ---------------------------------------------------------------------------
# Scenario: Financial Audit Trail
# ---------------------------------------------------------------------------

class TestAuditTrailFinancial:
    """Guide section: 'Scenario: Financial Audit Trail for Algorithmic Trading'."""

    def test_trading_system_merge_with_provenance(self):
        from crdt_merge.provenance import merge_with_provenance, export_provenance
        from crdt_merge.strategies import MergeSchema, LWW, MaxWins
        from crdt_merge.audit import AuditedMerge, AuditLog

        audit = AuditLog(node_id="trading-system")
        am = AuditedMerge(audit_log=audit)

        schema = MergeSchema(
            price=LWW(),
            volume=MaxWins(),
            bid=LWW(),
            ask=LWW(),
        )

        feed_bloomberg = [{"symbol": "AAPL", "price": 182.45, "volume": 1200000,
                           "bid": 182.44, "ask": 182.46}]
        feed_reuters   = [{"symbol": "AAPL", "price": 182.47, "volume": 980000,
                           "bid": 182.45, "ask": 182.48}]
        feed_internal  = [{"symbol": "AAPL", "price": 182.46, "volume": 1350000,
                           "bid": 182.44, "ask": 182.47}]

        merged_ab, log_ab = merge_with_provenance(
            feed_bloomberg, feed_reuters, key="symbol", schema=schema)
        merged_all, log_all = merge_with_provenance(
            merged_ab, feed_internal, key="symbol", schema=schema)

        # Highest volume should win the final merge (internal=1350000 > bloomberg=1200000)
        assert merged_all[0]["volume"] == 1350000, (
            f"MaxWins on volume: expected 1350000, got {merged_all[0]['volume']}")

        # Audit chain stays valid even without logging provenance merges through AuditedMerge
        assert audit.verify_chain()

        report = export_provenance(log_all, format="json")
        assert json.loads(report)["total_rows"] == 1


# ---------------------------------------------------------------------------
# AuditLog: log_merge direct usage
# ---------------------------------------------------------------------------

class TestAuditLogMerge:
    """Guide section: 'Architecture — AuditLog' — log_merge method."""

    def test_log_merge_direct(self):
        from crdt_merge.audit import AuditLog
        import crdt_merge

        audit = AuditLog(node_id="test-log-merge")

        left = [{"id": "1", "name": "Alice", "score": 10}]
        right = [{"id": "1", "name": "Alice", "score": 20}]
        result = crdt_merge.merge(left, right, key="id")

        entry = audit.log_merge(left, right, result)
        assert entry.operation == "merge"
        assert audit.verify_chain()
        assert len(audit) == 1

    def test_log_merge_with_schema(self):
        from crdt_merge.audit import AuditLog
        from crdt_merge.strategies import MergeSchema, MaxWins
        import crdt_merge

        audit = AuditLog(node_id="test-log-merge-schema")
        schema = MergeSchema(score=MaxWins())

        left = [{"id": "1", "name": "Alice", "score": 10}]
        right = [{"id": "1", "name": "Alice", "score": 20}]
        result = crdt_merge.merge(left, right, key="id", schema=schema)

        audit.log_merge(left, right, result, schema=schema)
        assert audit.verify_chain()


# ===========================================================================
# schema-evolution.md
# ===========================================================================

# ---------------------------------------------------------------------------
# Schema Policies
# ---------------------------------------------------------------------------

class TestSchemaPolicy:
    """Guide section: 'Schema Policies'."""

    def test_union_policy(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int64", "name": "str"}
        new = {"id": "int64", "email": "str"}

        result = evolve_schema(old, new, policy=SchemaPolicy.UNION)

        assert "id" in result.resolved_schema
        assert "name" in result.resolved_schema
        assert "email" in result.resolved_schema

    def test_intersection_policy(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int64", "name": "str"}
        new = {"id": "int64", "email": "str"}

        result = evolve_schema(old, new, policy=SchemaPolicy.INTERSECTION)

        assert result.resolved_schema == {"id": "int64"}, (
            f"INTERSECTION should keep only common columns, got {result.resolved_schema}")

    def test_left_priority_policy(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int64", "score": "int32"}
        new = {"id": "int64", "score": "float64", "email": "str"}

        result = evolve_schema(old, new, policy=SchemaPolicy.LEFT_PRIORITY)

        # Old (left) type wins for 'score'
        assert result.resolved_schema["score"] == "int32", (
            f"LEFT_PRIORITY: old type should win, got {result.resolved_schema['score']}")
        assert "email" in result.resolved_schema

    def test_right_priority_policy(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        old = {"id": "int64", "score": "int32"}
        new = {"id": "int64", "score": "float64", "email": "str"}

        result = evolve_schema(old, new, policy=SchemaPolicy.RIGHT_PRIORITY)

        # New (right) type wins for 'score'
        assert result.resolved_schema["score"] == "float64", (
            f"RIGHT_PRIORITY: new type should win, got {result.resolved_schema['score']}")


# ---------------------------------------------------------------------------
# widen_type
# ---------------------------------------------------------------------------

class TestWidenType:
    """Guide section: 'The TYPE_WIDENING Map'."""

    def test_widen_int32_to_float64(self):
        from crdt_merge.schema_evolution import widen_type
        assert widen_type("int32", "float64") == "float64"

    def test_widen_int_to_float(self):
        from crdt_merge.schema_evolution import widen_type
        assert widen_type("int", "float") == "float"

    def test_widen_same_type(self):
        from crdt_merge.schema_evolution import widen_type
        assert widen_type("str", "str") == "str"

    def test_widen_incompatible_returns_none(self):
        from crdt_merge.schema_evolution import widen_type
        assert widen_type("str", "int64") is None

    def test_widen_symmetric(self):
        from crdt_merge.schema_evolution import widen_type
        assert widen_type("float64", "int32") == "float64"


# ---------------------------------------------------------------------------
# check_compatibility
# ---------------------------------------------------------------------------

class TestCheckCompatibility:
    """Guide section: 'check_compatibility()'."""

    def test_compatible_with_type_widening(self):
        from crdt_merge.schema_evolution import check_compatibility

        v1 = {"id": "int64", "name": "str", "score": "int32"}
        v2 = {"id": "int64", "name": "str", "score": "float64"}

        ok, reasons = check_compatibility(v1, v2)
        assert ok, f"int32->float64 is safe widening but got: {reasons}"
        assert reasons == []

    def test_incompatible_missing_columns_and_type_conflict(self):
        from crdt_merge.schema_evolution import check_compatibility

        v3 = {"id": "int64", "name": "str", "score": "int32", "data": "bytes"}
        v4 = {"id": "int64", "data": "json"}

        ok, reasons = check_compatibility(v3, v4)
        assert not ok
        assert len(reasons) >= 1
        # Should mention missing columns or incompatible types
        all_text = " ".join(reasons)
        assert "name" in all_text or "score" in all_text or "data" in all_text


# ---------------------------------------------------------------------------
# evolve_schema — core walkthrough
# ---------------------------------------------------------------------------

class TestEvolveSchema:
    """Guide section: 'evolve_schema() Walkthrough'."""

    def test_union_with_type_widening(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        v1 = {"id": "int64", "name": "str", "score": "int32"}
        v2 = {"id": "int64", "name": "str", "score": "float64", "email": "str"}

        result = evolve_schema(v1, v2, policy=SchemaPolicy.UNION)

        assert result.resolved_schema["score"] == "float64", (
            f"score should widen to float64, got {result.resolved_schema['score']}")
        assert result.is_compatible
        assert result.policy_used == SchemaPolicy.UNION
        assert "email" in result.resolved_schema

    def test_changes_list_populated(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        v1 = {"id": "int64", "name": "str", "score": "int32"}
        v2 = {"id": "int64", "name": "str", "score": "float64", "email": "str"}

        result = evolve_schema(v1, v2, policy=SchemaPolicy.UNION)

        change_types = {c.column: c.change_type for c in result.changes}
        assert change_types.get("email") == "added"
        assert change_types.get("score") == "type_changed"

    def test_defaults_for_missing_columns(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        result = evolve_schema(
            old={"id": "int64", "name": "str"},
            new={"id": "int64", "email": "str"},
            policy=SchemaPolicy.UNION,
            defaults={"name": "unknown", "email": ""},
        )

        assert "name" in result.defaults or "email" in result.defaults, (
            f"Expected defaults dict to contain missing columns, got {result.defaults}")

    def test_allow_type_narrowing(self):
        from crdt_merge.schema_evolution import evolve_schema

        result = evolve_schema(
            {"score": "float64"},
            {"score": "int32"},
            allow_type_narrowing=True,
        )

        assert result.is_compatible, "Narrowing should be allowed when flag is set"

    def test_none_schema_treated_as_empty(self):
        from crdt_merge.schema_evolution import evolve_schema

        result = evolve_schema(None, {"id": "int64"})
        assert result.resolved_schema == {"id": "int64"}

    def test_incompatible_types_no_widening_path(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        result = evolve_schema(
            {"data": "bytes"},
            {"data": "json"},
            policy=SchemaPolicy.UNION,
        )

        assert not result.is_compatible
        assert any("data" in w for w in result.warnings)

    def test_intersection_removed_fields_have_none_resolved_type(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        result = evolve_schema(
            {"id": "int64", "legacy_flag": "int32"},
            {"id": "int64", "email": "str"},
            policy=SchemaPolicy.INTERSECTION,
        )

        assert result.resolved_schema == {"id": "int64"}
        changes_by_col = {c.column: c for c in result.changes}
        assert changes_by_col["legacy_flag"].resolved_type is None
        assert changes_by_col["email"].resolved_type is None


# ---------------------------------------------------------------------------
# Concurrent schema merges — pairwise resolution
# ---------------------------------------------------------------------------

class TestConcurrentSchemaMerges:
    """Guide section: 'Concurrent schema changes from multiple nodes'."""

    def test_pairwise_three_node_merge(self):
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        schema_a = {"id": "int64", "name": "str"}
        schema_b = {"id": "int64", "email": "str"}
        schema_c = {"id": "int64", "score": "float64"}

        merged_ab = evolve_schema(schema_a, schema_b, policy=SchemaPolicy.UNION)
        final = evolve_schema(
            merged_ab.resolved_schema, schema_c, policy=SchemaPolicy.UNION)

        assert "id" in final.resolved_schema
        assert "name" in final.resolved_schema
        assert "email" in final.resolved_schema
        assert "score" in final.resolved_schema


# ---------------------------------------------------------------------------
# Cross-Version Merging
# ---------------------------------------------------------------------------

class TestCrossVersionMerging:
    """Guide section: 'Cross-Version Merging'."""

    def test_cross_version_workflow(self):
        from crdt_merge.schema_evolution import evolve_schema, check_compatibility, SchemaPolicy

        v1_schema = {"id": "int64", "name": "str", "score": "int32"}
        v2_schema = {"id": "int64", "name": "str", "score": "float64", "email": "str"}

        # Step 1 — check up-front (not compatible because columns differ)
        ok, reasons = check_compatibility(v1_schema, v2_schema)
        # ok may be False due to extra column in v2; just verify it runs
        assert isinstance(ok, bool)

        # Step 2 — evolve
        evo = evolve_schema(
            v1_schema, v2_schema,
            policy=SchemaPolicy.UNION,
            defaults={"email": ""},
        )

        unified_schema = evo.resolved_schema
        assert "email" in unified_schema
        assert "score" in unified_schema
        assert unified_schema["score"] == "float64"

    def test_schema_registry_all_version_pairs(self):
        import itertools
        from crdt_merge.schema_evolution import evolve_schema, SchemaPolicy

        SCHEMA_REGISTRY = {
            1: {"id": "int64", "name": "str"},
            2: {"id": "int64", "name": "str", "email": "str"},
            3: {"id": "int64", "name": "str", "email": "str", "score": "float64"},
        }

        for va, vb in itertools.combinations(SCHEMA_REGISTRY, 2):
            result = evolve_schema(
                SCHEMA_REGISTRY[va],
                SCHEMA_REGISTRY[vb],
                policy=SchemaPolicy.UNION,
            )
            assert result.is_compatible, (
                f"v{va}->v{vb} should be compatible: {result.warnings}"
            )


# ---------------------------------------------------------------------------
# Testing Schema Migrations
# ---------------------------------------------------------------------------

class TestSchemaMigrationTests:
    """Guide section: 'Testing Schema Migrations'."""

    def test_schema_backward_compatible(self):
        from crdt_merge.schema_evolution import check_compatibility

        CURRENT_SCHEMA = {"id": "int64", "name": "str", "score": "int32"}
        NEW_SCHEMA = {"id": "int64", "name": "str", "score": "float64"}

        # score widening from int32 to float64 is safe
        ok, reasons = check_compatibility(CURRENT_SCHEMA, NEW_SCHEMA)
        assert ok, f"Schema migration is breaking: {reasons}"

    def test_serialise_evolution_result(self, tmp_path):
        from crdt_merge.schema_evolution import evolve_schema

        old_schema = {"id": "int64", "name": "str"}
        new_schema = {"id": "int64", "name": "str", "email": "str"}

        result = evolve_schema(old_schema, new_schema)
        filepath = str(tmp_path / "migration_audit.json")
        with open(filepath, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        with open(filepath) as f:
            loaded = json.load(f)

        assert "resolved_schema" in loaded
        assert "changes" in loaded


# ===========================================================================
# performance-tuning.md
# ===========================================================================

# ---------------------------------------------------------------------------
# Engine Selection — basic merge (pandas path)
# ---------------------------------------------------------------------------

class TestPerformanceTuningBasicMerge:
    """Guide section: 'Engine Selection' — basic merge."""

    def test_basic_merge_list_of_dicts(self):
        from crdt_merge import merge

        df_a = [{"id": "1", "name": "Alice", "score": 10}]
        df_b = [{"id": "1", "name": "Alice", "score": 20}]

        result = merge(df_a, df_b, key="id")
        assert len(result) == 1

    def test_basic_merge_pandas(self):
        pytest.importorskip("pandas")
        import pandas as pd
        from crdt_merge import merge

        df_a = pd.DataFrame([{"id": "1", "name": "Alice", "score": 10}])
        df_b = pd.DataFrame([{"id": "1", "name": "Alice", "score": 20}])

        result = merge(df_a, df_b, key="id")
        assert len(result) == 1

    def test_basic_merge_polars(self):
        pytest.importorskip("polars")
        import polars as pl
        from crdt_merge import merge

        df_a = pl.DataFrame([{"id": "1", "name": "Alice", "score": 10}])
        df_b = pl.DataFrame([{"id": "1", "name": "Alice", "score": 20}])

        result = merge(df_a, df_b, key="id")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Arrow Merge
# ---------------------------------------------------------------------------

class TestArrowMerge:
    """Guide section: 'Use Arrow for Large Data'."""

    def test_arrow_merge_basic(self):
        pa = pytest.importorskip("pyarrow")
        from crdt_merge.arrow import arrow_merge

        table_a = pa.table({"id": ["1"], "name": ["Alice"], "score": [10]})
        table_b = pa.table({"id": ["1"], "name": ["Alice"], "score": [20]})

        result = arrow_merge(table_a, table_b, key="id")
        assert len(result) == 1

    def test_arrow_merge_unique_rows(self):
        pa = pytest.importorskip("pyarrow")
        from crdt_merge.arrow import arrow_merge

        table_a = pa.table({"id": ["1", "2"], "name": ["Alice", "Bob"], "score": [10, 30]})
        table_b = pa.table({"id": ["1", "3"], "name": ["Alice", "Carol"], "score": [20, 40]})

        result = arrow_merge(table_a, table_b, key="id")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Parallel Merge
# ---------------------------------------------------------------------------

class TestParallelMerge:
    """Guide section: 'Parallel Merge'."""

    def test_parallel_merge_basic(self):
        from crdt_merge.parallel import parallel_merge

        df_a = [{"id": str(i), "name": f"User{i}", "score": i} for i in range(10)]
        df_b = [{"id": str(i), "name": f"User{i}", "score": i + 1} for i in range(10)]

        # Note: the guide shows num_workers=8 but the actual param is max_workers
        result = parallel_merge(df_a, df_b, key="id", max_workers=2)
        assert len(result) == 10

    def test_parallel_merge_with_schema(self):
        from crdt_merge.parallel import parallel_merge
        from crdt_merge.strategies import MergeSchema, MaxWins

        schema = MergeSchema(score=MaxWins())
        df_a = [{"id": "1", "name": "Alice", "score": 10}]
        df_b = [{"id": "1", "name": "Alice", "score": 20}]

        result = parallel_merge(df_a, df_b, key="id", schema=schema)
        assert result[0]["score"] == 20, "MaxWins: 20 should beat 10"
