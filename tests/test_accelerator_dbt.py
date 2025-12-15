# Copyright 2026 Ryan Gillespie
# Licensed under Apache-2.0

"""Tests for crdt_merge.accelerators.dbt_package — dbt macro generator.

No external dependencies are required to run these tests.
"""

import pytest

from crdt_merge.accelerators.dbt_package import (
    DbtMergeGenerator,
    MacroConfig,
    ModelConfig,
    _STRATEGY_MAP,
    _SUPPORTED_WAREHOUSES,
)
from crdt_merge.accelerators import ACCELERATOR_REGISTRY


# ===================================================================
# TestDbtMergeGenerator — 25 tests
# ===================================================================


class TestDbtMergeGenerator:
    """Tests for the DbtMergeGenerator accelerator."""

    # -- Construction & protocol -------------------------------------------

    def test_init_default(self):
        gen = DbtMergeGenerator()
        assert gen._warehouse is None

    def test_init_with_warehouse(self):
        gen = DbtMergeGenerator(warehouse="snowflake")
        assert gen._warehouse == "snowflake"

    def test_init_warehouse_case_insensitive(self):
        gen = DbtMergeGenerator(warehouse="BigQuery")
        assert gen._warehouse == "bigquery"

    def test_init_invalid_warehouse_raises(self):
        with pytest.raises(ValueError, match="Unsupported warehouse"):
            DbtMergeGenerator(warehouse="oracle")

    def test_registered_in_accelerator_registry(self):
        assert "dbt_package" in ACCELERATOR_REGISTRY

    def test_health_check(self):
        gen = DbtMergeGenerator()
        hc = gen.health_check()
        assert hc["name"] == "dbt_package"
        assert hc["version"] == "0.7.0"
        assert hc["status"] == "ok"
        assert "snowflake" in hc["supported_warehouses"]

    def test_is_available(self):
        gen = DbtMergeGenerator()
        assert gen.is_available() is True

    # -- generate_macro ----------------------------------------------------

    def test_generate_macro_basic(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["stg_east", "stg_west"],
            key="customer_id",
            strategies={"name": "lww", "revenue": "max"},
        )
        assert "crdt_merge_stg_east_stg_west" in sql
        assert "customer_id" in sql
        assert "greatest" in sql  # max strategy
        assert "__crdt_max_ts" in sql  # lww needs timestamp CTE

    def test_generate_macro_custom_name(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["a", "b"],
            key="id",
            strategies={"val": "max"},
            macro_name="my_custom_merge",
        )
        assert "my_custom_merge" in sql

    def test_generate_macro_min_strategy(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"price": "min"},
        )
        assert "least" in sql

    def test_generate_macro_union_strategy(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"tags": "union"},
        )
        assert "concat_ws" in sql

    def test_generate_macro_concat_strategy(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"notes": "concat"},
        )
        assert "concat_ws" in sql

    def test_generate_macro_longest_strategy(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"desc": "longest"},
        )
        assert "length" in sql

    def test_generate_macro_three_sources(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["a", "b", "c"],
            key="id",
            strategies={"v": "max"},
        )
        assert "a" in sql and "b" in sql and "c" in sql
        assert "full outer join" in sql

    def test_generate_macro_requires_two_sources(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="At least two sources"):
            gen.generate_macro(sources=["only_one"], key="id", strategies={"v": "max"})

    def test_generate_macro_empty_sources_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="At least two sources"):
            gen.generate_macro(sources=[], key="id", strategies={"v": "max"})

    def test_generate_macro_empty_key_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="Key column"):
            gen.generate_macro(sources=["a", "b"], key="", strategies={"v": "max"})

    def test_generate_macro_invalid_strategy_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="Unknown strategy"):
            gen.generate_macro(
                sources=["a", "b"],
                key="id",
                strategies={"v": "nonexistent"},
            )

    # -- generate_resolver_macros ------------------------------------------

    def test_generate_resolver_macros(self):
        gen = DbtMergeGenerator()
        macros = gen.generate_resolver_macros()
        assert "crdt_resolve_lww" in macros
        assert "crdt_resolve_max" in macros
        assert "crdt_resolve_min" in macros
        assert "crdt_resolve_union" in macros
        assert "crdt_resolve_concat" in macros
        assert "crdt_resolve_longest" in macros
        assert "crdt_resolve_priority" in macros

    # -- generate_model ----------------------------------------------------

    def test_generate_model(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_model(
            model_name="merged_customers",
            sources=["stg_east", "stg_west"],
            key="id",
            strategies={"name": "lww", "revenue": "max"},
        )
        assert "merged_customers" in sql
        assert "materialized=" in sql

    def test_generate_model_incremental(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_model(
            model_name="inc_model",
            sources=["a", "b"],
            key="id",
            strategies={"v": "max"},
            materialization="incremental",
        )
        assert "incremental" in sql

    # -- generate_packages_yml ---------------------------------------------

    def test_generate_packages_yml(self):
        gen = DbtMergeGenerator()
        yml = gen.generate_packages_yml()
        assert "packages:" in yml
        assert "crdt_merge" in yml
        assert "0.7.0" in yml

    def test_generate_packages_yml_custom(self):
        gen = DbtMergeGenerator()
        yml = gen.generate_packages_yml(package_name="my_pkg", version="1.2.3")
        assert "my_pkg" in yml
        assert "1.2.3" in yml

    # -- generate_schema_yml -----------------------------------------------

    def test_generate_schema_yml(self):
        gen = DbtMergeGenerator()
        yml = gen.generate_schema_yml(
            model_name="merged_users",
            key="user_id",
            strategies={"name": "lww", "score": "max"},
        )
        assert "merged_users" in yml
        assert "user_id" in yml
        assert "unique" in yml
        assert "not_null" in yml
        assert "lww" in yml

    # -- Utility methods ---------------------------------------------------

    def test_list_supported_strategies(self):
        gen = DbtMergeGenerator()
        strats = gen.list_supported_strategies()
        assert "lww" in strats
        assert "max" in strats
        assert "min" in strats

    def test_list_supported_warehouses(self):
        gen = DbtMergeGenerator()
        wh = gen.list_supported_warehouses()
        assert set(wh) == {"snowflake", "bigquery", "postgres", "duckdb"}


# ===================================================================
# TestMacroConfig — extra coverage
# ===================================================================


class TestMacroConfig:
    """Test the MacroConfig dataclass validation."""

    def test_normalises_strategies(self):
        cfg = MacroConfig(
            sources=["a", "b"],
            key="id",
            strategies={"a": "maxwins", "b": "minwins"},
        )
        assert cfg.strategies["a"] == "max"
        assert cfg.strategies["b"] == "min"

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            MacroConfig(
                sources=["a", "b"],
                key="id",
                strategies={"x": "bogus"},
            )
