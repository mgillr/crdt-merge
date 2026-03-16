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

"""Tests for crdt_merge.model.formats — MergeKit compatibility layer."""

from __future__ import annotations

import pytest

from crdt_merge.model.formats import (
    REVERSE_STRATEGY_MAP,
    STRATEGY_MAP,
    export_mergekit_config,
    import_mergekit_config,
)
from crdt_merge.model.core import ModelMergeSchema


# ---------------------------------------------------------------------------
# Strategy maps
# ---------------------------------------------------------------------------

class TestStrategyMaps:
    def test_strategy_map_non_empty(self):
        assert len(STRATEGY_MAP) > 0

    def test_reverse_strategy_map_non_empty(self):
        assert len(REVERSE_STRATEGY_MAP) > 0

    def test_slerp_round_trips(self):
        crdt_name = STRATEGY_MAP["slerp"]
        mk_name = REVERSE_STRATEGY_MAP[crdt_name]
        assert mk_name == "slerp"

    def test_ties_round_trips(self):
        crdt_name = STRATEGY_MAP["ties"]
        mk_name = REVERSE_STRATEGY_MAP[crdt_name]
        assert mk_name == "ties"

    def test_dare_maps_to_dare_linear(self):
        assert REVERSE_STRATEGY_MAP.get("dare") == "dare_linear"


# ---------------------------------------------------------------------------
# import_mergekit_config — happy paths
# ---------------------------------------------------------------------------

class TestImportMergekitConfig:
    def test_basic_linear_config(self):
        config = {
            "merge_method": "linear",
            "models": [{"model": "path/a"}, {"model": "path/b"}],
        }
        schema, extra = import_mergekit_config(config)
        assert isinstance(schema, ModelMergeSchema)
        assert extra["crdt_strategy"] == "linear"

    def test_model_paths_extracted(self):
        config = {
            "merge_method": "slerp",
            "models": [{"model": "model/a"}, {"model": "model/b"}],
        }
        _, extra = import_mergekit_config(config)
        assert extra["model_paths"] == ["model/a", "model/b"]

    def test_model_weights_extracted(self):
        config = {
            "merge_method": "linear",
            "models": [
                {"model": "a", "weight": 0.4},
                {"model": "b", "weight": 0.6},
            ],
        }
        _, extra = import_mergekit_config(config)
        assert extra["model_weights"] == [0.4, 0.6]

    def test_default_weight_is_one(self):
        config = {
            "merge_method": "linear",
            "models": [{"model": "a"}],
        }
        _, extra = import_mergekit_config(config)
        assert extra["model_weights"] == [1.0]

    def test_parameters_passed_through(self):
        config = {
            "merge_method": "ties",
            "models": [],
            "parameters": {"density": 0.5, "lambda": 0.3},
        }
        _, extra = import_mergekit_config(config)
        assert extra["parameters"]["density"] == 0.5
        assert extra["parameters"]["lambda"] == 0.3

    def test_base_model_extracted(self):
        config = {
            "merge_method": "task_arithmetic",
            "models": [],
            "base_model": "path/to/base",
        }
        _, extra = import_mergekit_config(config)
        assert extra["base_model"] == "path/to/base"

    def test_dtype_extracted(self):
        config = {
            "merge_method": "linear",
            "models": [],
            "dtype": "float16",
        }
        _, extra = import_mergekit_config(config)
        assert extra["dtype"] == "float16"

    def test_method_alias_accepted(self):
        config = {"method": "slerp", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["crdt_strategy"] == "slerp"

    def test_empty_models_list_accepted(self):
        config = {"merge_method": "linear", "models": []}
        schema, extra = import_mergekit_config(config)
        assert extra["model_paths"] == []

    def test_string_model_entries_accepted(self):
        config = {"merge_method": "linear", "models": ["path/a", "path/b"]}
        _, extra = import_mergekit_config(config)
        assert extra["model_paths"] == ["path/a", "path/b"]

    def test_non_dict_input_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict or YAML string"):
            import_mergekit_config(42)


# ---------------------------------------------------------------------------
# import_mergekit_config — slices
# ---------------------------------------------------------------------------

class TestImportMergekitConfigSlices:
    def test_slices_with_filter_create_per_layer_strategies(self):
        config = {
            "merge_method": "linear",
            "models": [],
            "slices": [
                {"filter": "layers.0", "merge_method": "slerp"},
            ],
        }
        schema, extra = import_mergekit_config(config)
        assert "slices" in extra
        raw = schema.to_dict()
        assert "layers.0" in raw
        assert raw["layers.0"] == "slerp"

    def test_default_strategy_set_even_with_slices(self):
        config = {
            "merge_method": "ties",
            "models": [],
            "slices": [],
        }
        schema, _ = import_mergekit_config(config)
        raw = schema.to_dict()
        assert raw.get("default") == "ties"


# ---------------------------------------------------------------------------
# export_mergekit_config
# ---------------------------------------------------------------------------

class TestExportMergekitConfig:
    def test_basic_export_has_merge_method(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        config = export_mergekit_config(schema)
        assert "merge_method" in config

    def test_default_strategy_becomes_merge_method(self):
        schema = ModelMergeSchema(strategies={"default": "slerp"})
        config = export_mergekit_config(schema)
        assert config["merge_method"] == "slerp"

    def test_models_list_included_when_provided(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        config = export_mergekit_config(schema, models=["path/a", "path/b"])
        assert config["models"] == [{"model": "path/a"}, {"model": "path/b"}]

    def test_per_layer_strategies_become_slices(self):
        schema = ModelMergeSchema(strategies={
            "default": "linear",
            "layers.0": "slerp",
        })
        config = export_mergekit_config(schema)
        assert "slices" in config
        filters = [s["filter"] for s in config["slices"]]
        assert "layers.0" in filters

    def test_parameters_key_present(self):
        schema = ModelMergeSchema(strategies={"default": "linear"})
        config = export_mergekit_config(schema)
        assert "parameters" in config

    def test_roundtrip_default_strategy(self):
        schema = ModelMergeSchema(strategies={"default": "ties"})
        exported = export_mergekit_config(schema)
        re_imported, extra = import_mergekit_config(exported)
        assert extra["crdt_strategy"] == "ties"
