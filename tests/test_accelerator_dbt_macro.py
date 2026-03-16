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

"""Tests for crdt_merge.accelerators.dbt_package — DbtMergeGenerator (dbt macro API).

Covers DbtMergeGenerator initialization, generate_macro(), generate_model(),
generate_packages_yml(), generate_schema_yml(), generate_resolver_macros(),
MacroConfig validation, and registry integration.  No external dependencies needed.
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
# TestDbtMergeGeneratorInit
# ===================================================================

class TestDbtMergeGeneratorInit:
    """Initialization and protocol compliance."""

    def test_default_warehouse_is_none(self):
        gen = DbtMergeGenerator()
        assert gen._warehouse is None

    def test_warehouse_stored_lowercase(self):
        gen = DbtMergeGenerator(warehouse="Snowflake")
        assert gen._warehouse == "snowflake"

    def test_all_supported_warehouses_accepted(self):
        for wh in _SUPPORTED_WAREHOUSES:
            gen = DbtMergeGenerator(warehouse=wh)
            assert gen._warehouse == wh

    def test_invalid_warehouse_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported warehouse"):
            DbtMergeGenerator(warehouse="redshift")

    def test_is_available_always_true(self):
        assert DbtMergeGenerator().is_available() is True

    def test_registered_in_accelerator_registry(self):
        assert "dbt_package" in ACCELERATOR_REGISTRY

    def test_registry_class_is_dbt_merge_generator(self):
        assert ACCELERATOR_REGISTRY["dbt_package"] is DbtMergeGenerator


# ===================================================================
# TestHealthCheck
# ===================================================================

class TestHealthCheck:
    """health_check() return value."""

    def test_health_check_name(self):
        hc = DbtMergeGenerator().health_check()
        assert hc["name"] == "dbt_package"

    def test_health_check_version(self):
        hc = DbtMergeGenerator().health_check()
        assert hc["version"] == "0.7.0"

    def test_health_check_status_ok(self):
        hc = DbtMergeGenerator().health_check()
        assert hc["status"] == "ok"

    def test_health_check_contains_supported_warehouses(self):
        hc = DbtMergeGenerator().health_check()
        for wh in _SUPPORTED_WAREHOUSES:
            assert wh in hc["supported_warehouses"]

    def test_health_check_warehouse_auto_when_none(self):
        hc = DbtMergeGenerator().health_check()
        assert hc["warehouse"] == "auto"

    def test_health_check_warehouse_set_when_configured(self):
        hc = DbtMergeGenerator(warehouse="duckdb").health_check()
        assert hc["warehouse"] == "duckdb"


# ===================================================================
# TestGenerateMacro
# ===================================================================

class TestGenerateMacro:
    """generate_macro() output correctness."""

    def test_macro_name_from_sources(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["src_a", "src_b"],
            key="id",
            strategies={"v": "max"},
        )
        assert "crdt_merge_src_a_src_b" in sql

    def test_custom_macro_name(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["a", "b"],
            key="id",
            strategies={"v": "max"},
            macro_name="my_merge",
        )
        assert "my_merge" in sql

    def test_key_column_present(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="customer_id",
            strategies={"score": "max"},
        )
        assert "customer_id" in sql

    def test_max_strategy_generates_greatest(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"score": "max"},
        )
        assert "greatest" in sql

    def test_min_strategy_generates_least(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"price": "min"},
        )
        assert "least" in sql

    def test_lww_strategy_generates_max_ts_cte(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"name": "lww"},
        )
        assert "__crdt_max_ts" in sql

    def test_union_strategy_generates_concat_ws(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"tags": "union"},
        )
        assert "concat_ws" in sql

    def test_concat_strategy_generates_concat_ws(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"notes": "concat"},
        )
        assert "concat_ws" in sql

    def test_longest_strategy_generates_length(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["s1", "s2"],
            key="id",
            strategies={"bio": "longest"},
        )
        assert "length" in sql

    def test_three_sources_all_appear(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["a", "b", "c"],
            key="id",
            strategies={"v": "max"},
        )
        for src in ("a", "b", "c"):
            assert src in sql

    def test_three_sources_use_full_outer_join(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_macro(
            sources=["a", "b", "c"],
            key="id",
            strategies={"v": "max"},
        )
        assert "full outer join" in sql

    def test_single_source_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="At least two sources"):
            gen.generate_macro(sources=["only"], key="id", strategies={"v": "max"})

    def test_empty_sources_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="At least two sources"):
            gen.generate_macro(sources=[], key="id", strategies={"v": "max"})

    def test_empty_key_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="Key column"):
            gen.generate_macro(sources=["a", "b"], key="", strategies={"v": "max"})

    def test_unknown_strategy_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError, match="Unknown strategy"):
            gen.generate_macro(
                sources=["a", "b"],
                key="id",
                strategies={"v": "bogus_strategy"},
            )


# ===================================================================
# TestGenerateResolverMacros
# ===================================================================

class TestGenerateResolverMacros:
    """generate_resolver_macros() completeness."""

    def test_lww_resolver_present(self):
        macros = DbtMergeGenerator().generate_resolver_macros()
        assert "crdt_resolve_lww" in macros

    def test_max_resolver_present(self):
        assert "crdt_resolve_max" in DbtMergeGenerator().generate_resolver_macros()

    def test_min_resolver_present(self):
        assert "crdt_resolve_min" in DbtMergeGenerator().generate_resolver_macros()

    def test_union_resolver_present(self):
        assert "crdt_resolve_union" in DbtMergeGenerator().generate_resolver_macros()

    def test_concat_resolver_present(self):
        assert "crdt_resolve_concat" in DbtMergeGenerator().generate_resolver_macros()

    def test_longest_resolver_present(self):
        assert "crdt_resolve_longest" in DbtMergeGenerator().generate_resolver_macros()

    def test_priority_resolver_present(self):
        assert "crdt_resolve_priority" in DbtMergeGenerator().generate_resolver_macros()


# ===================================================================
# TestGenerateModel
# ===================================================================

class TestGenerateModel:
    """generate_model() SQL output."""

    def test_model_name_in_output(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_model(
            model_name="merged_orders",
            sources=["src1", "src2"],
            key="order_id",
            strategies={"amount": "max"},
        )
        assert "merged_orders" in sql

    def test_materialized_config_present(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_model(
            model_name="m",
            sources=["a", "b"],
            key="id",
            strategies={"v": "max"},
        )
        assert "materialized=" in sql

    def test_incremental_materialization(self):
        gen = DbtMergeGenerator()
        sql = gen.generate_model(
            model_name="m",
            sources=["a", "b"],
            key="id",
            strategies={"v": "max"},
            materialization="incremental",
        )
        assert "incremental" in sql

    def test_single_source_raises(self):
        gen = DbtMergeGenerator()
        with pytest.raises(ValueError):
            gen.generate_model(
                model_name="m",
                sources=["only_one"],
                key="id",
                strategies={"v": "max"},
            )


# ===================================================================
# TestGeneratePackagesYml
# ===================================================================

class TestGeneratePackagesYml:
    """generate_packages_yml() output."""

    def test_packages_key_present(self):
        yml = DbtMergeGenerator().generate_packages_yml()
        assert "packages:" in yml

    def test_default_package_name(self):
        yml = DbtMergeGenerator().generate_packages_yml()
        assert "crdt_merge" in yml

    def test_default_version_string(self):
        yml = DbtMergeGenerator().generate_packages_yml()
        assert "0.7.0" in yml

    def test_custom_package_name(self):
        yml = DbtMergeGenerator().generate_packages_yml(package_name="my_dbt_pkg")
        assert "my_dbt_pkg" in yml

    def test_custom_version(self):
        yml = DbtMergeGenerator().generate_packages_yml(version="2.0.0")
        assert "2.0.0" in yml


# ===================================================================
# TestGenerateSchemaYml
# ===================================================================

class TestGenerateSchemaYml:
    """generate_schema_yml() output."""

    def test_model_name_present(self):
        yml = DbtMergeGenerator().generate_schema_yml(
            model_name="merged_customers",
            key="customer_id",
            strategies={"name": "lww"},
        )
        assert "merged_customers" in yml

    def test_key_column_present(self):
        yml = DbtMergeGenerator().generate_schema_yml(
            model_name="m",
            key="user_id",
            strategies={"name": "lww"},
        )
        assert "user_id" in yml

    def test_unique_and_not_null_tests(self):
        yml = DbtMergeGenerator().generate_schema_yml(
            model_name="m",
            key="id",
            strategies={"x": "max"},
        )
        assert "unique" in yml
        assert "not_null" in yml

    def test_strategy_name_in_description(self):
        yml = DbtMergeGenerator().generate_schema_yml(
            model_name="m",
            key="id",
            strategies={"score": "max"},
        )
        assert "max" in yml

    def test_custom_description(self):
        yml = DbtMergeGenerator().generate_schema_yml(
            model_name="m",
            key="id",
            strategies={},
            description="My custom description",
        )
        assert "My custom description" in yml


# ===================================================================
# TestListMethods
# ===================================================================

class TestListMethods:
    """list_supported_strategies() and list_supported_warehouses()."""

    def test_list_supported_strategies_contains_lww(self):
        assert "lww" in DbtMergeGenerator().list_supported_strategies()

    def test_list_supported_strategies_contains_max(self):
        assert "max" in DbtMergeGenerator().list_supported_strategies()

    def test_list_supported_warehouses_matches_constant(self):
        wh = DbtMergeGenerator().list_supported_warehouses()
        assert set(wh) == set(_SUPPORTED_WAREHOUSES)


# ===================================================================
# TestMacroConfig
# ===================================================================

class TestMacroConfig:
    """MacroConfig dataclass validation."""

    def test_strategy_aliases_normalised(self):
        cfg = MacroConfig(
            sources=["a", "b"],
            key="id",
            strategies={"price": "maxwins", "count": "minwins"},
        )
        assert cfg.strategies["price"] == "max"
        assert cfg.strategies["count"] == "min"

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            MacroConfig(
                sources=["a", "b"],
                key="id",
                strategies={"x": "nonexistent"},
            )

    def test_default_timestamp_column(self):
        cfg = MacroConfig(sources=["a", "b"], key="id", strategies={"v": "max"})
        assert cfg.timestamp_column == "_merged_at"

    def test_custom_macro_name_stored(self):
        cfg = MacroConfig(
            sources=["a", "b"],
            key="id",
            strategies={"v": "max"},
            macro_name="custom",
        )
        assert cfg.macro_name == "custom"
