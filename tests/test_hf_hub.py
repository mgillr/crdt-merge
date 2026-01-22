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

"""Tests for HuggingFace Hub integration: model cards, merge hub, targets."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

import pytest

from crdt_merge.hub.model_card import AutoModelCard, ModelCardConfig, _dict_to_yaml
from crdt_merge.hub.hf import HFMergeHub, HFMergeResult, _require_hf_hub, _HF_INSTALL_MSG
from crdt_merge.hub import HFMergeHub as HFMergeHubImport
from crdt_merge.hub import AutoModelCard as AutoModelCardImport
from crdt_merge.hub import ModelCardConfig as ModelCardConfigImport
from crdt_merge.model.targets import HfSource, HfTarget
from crdt_merge.model.targets.hf import _require_hf_hub as _require_hf_hub_targets
from crdt_merge.model.provenance import ProvenanceTracker, ProvenanceSummary, LayerProvenance
from crdt_merge.model.core import ModelMerge, ModelCRDT, ModelMergeSchema, MergeResult
from crdt_merge.model.strategies import list_strategies, get_strategy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_provenance(
    overall_conflict: float = 0.25,
    dominant_model: int = 0,
    layers: int = 3,
) -> ProvenanceSummary:
    """Build a realistic ProvenanceSummary for testing."""
    per_layer = {}
    ranking = []
    for i in range(layers):
        name = f"layer{i}.weight"
        lp = LayerProvenance(
            layer_name=name,
            strategy_used="weight_average",
            dominant_source=0,
            contribution_map={0: 0.6, 1: 0.4},
            conflict_score=overall_conflict + i * 0.01,
            metadata={"num_sources": 2},
        )
        per_layer[name] = lp
        ranking.append(name)

    return ProvenanceSummary(
        overall_conflict=overall_conflict,
        dominant_model=dominant_model,
        layer_conflict_ranking=ranking,
        per_layer=per_layer,
    )


SOURCES_2 = ["user/modelA", "user/modelB"]
SOURCES_3 = ["org/base", "user/finetuned-1", "user/finetuned-2"]


# ===========================================================================
# AutoModelCard Tests
# ===========================================================================


class TestAutoModelCardInit:
    """Test AutoModelCard initialization."""

    def test_default_config(self):
        card = AutoModelCard()
        assert card.config.include_lineage is True
        assert card.config.include_strategies is True
        assert card.config.include_crdt_badge is True
        assert card.config.include_eu_ai_act is False
        assert card.config.language == "en"
        assert card.config.license == "apache-2.0"

    def test_custom_config(self):
        cfg = ModelCardConfig(
            include_eu_ai_act=True,
            language="fr",
            license="mit",
            tags=["custom"],
        )
        card = AutoModelCard(config=cfg)
        assert card.config.include_eu_ai_act is True
        assert card.config.language == "fr"
        assert card.config.tags == ["custom"]


class TestAutoModelCardGenerate:
    """Test model card markdown generation."""

    def test_basic_generation(self):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "---" in md
        assert "# Merged Model" in md
        assert "weight_average" in md
        assert "`user/modelA`" in md
        assert "`user/modelB`" in md

    def test_generation_with_provenance(self):
        prov = _make_provenance()
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
            weights=[0.6, 0.4],
            verified=True,
        )
        assert "## Merge Details" in md
        assert "## Strategy" in md
        assert "## CRDT Verification" in md
        assert "## Provenance" in md
        assert "0.6" in md
        assert "0.4" in md
        assert "verified-brightgreen" in md

    def test_generation_unverified(self):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_2, strategy="slerp", verified=False)
        assert "unverified-yellow" in md

    def test_generation_verified(self):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_2, strategy="slerp", verified=True)
        assert "verified-brightgreen" in md

    def test_generation_three_sources(self):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_3, strategy="ties")
        assert "3 source models" in md
        assert "`org/base`" in md

    def test_generation_with_weights(self):
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            weights=[0.7, 0.3],
        )
        assert "0.7" in md
        assert "0.3" in md

    def test_generation_no_lineage(self):
        cfg = ModelCardConfig(include_lineage=False)
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "## Merge Details" not in md

    def test_generation_no_strategies(self):
        cfg = ModelCardConfig(include_strategies=False)
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "## Strategy" not in md

    def test_generation_no_crdt_badge(self):
        cfg = ModelCardConfig(include_crdt_badge=False)
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "## CRDT Verification" not in md

    def test_generation_with_eu_ai_act(self):
        cfg = ModelCardConfig(include_eu_ai_act=True)
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "## EU AI Act Traceability" in md
        assert "schema.org" in md
        assert "json" in md.lower()

    def test_generation_with_base_card(self):
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            base_card="This is the original model card content.",
        )
        assert "This is the original model card content." in md
        assert "# Merged Model" in md

    def test_equal_weights_default(self):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "equal" in md

    def test_provenance_per_layer_table(self):
        prov = _make_provenance(layers=2)
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        assert "layer0.weight" in md
        assert "layer1.weight" in md
        assert "<details>" in md

    def test_provenance_conflict_ranking(self):
        prov = _make_provenance(layers=3)
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        assert "Highest-conflict layers" in md


class TestAutoModelCardMetadata:
    """Test metadata generation."""

    def test_default_metadata(self):
        card = AutoModelCard()
        meta = card.generate_metadata(sources=SOURCES_2, strategy="weight_average")
        assert meta["library_name"] == "crdt-merge"
        assert "merge" in meta["tags"]
        assert "crdt-merge" in meta["tags"]
        assert "merge-strategy-weight_average" in meta["tags"]
        assert meta["license"] == "apache-2.0"
        assert meta["language"] == "en"

    def test_metadata_with_custom_tags(self):
        cfg = ModelCardConfig(tags=["custom1", "custom2"])
        card = AutoModelCard(config=cfg)
        meta = card.generate_metadata(sources=SOURCES_2, strategy="slerp")
        assert "custom1" in meta["tags"]
        assert "custom2" in meta["tags"]
        assert "merge-strategy-slerp" in meta["tags"]

    def test_metadata_with_provenance(self):
        prov = _make_provenance(overall_conflict=0.333)
        card = AutoModelCard()
        meta = card.generate_metadata(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        assert "merge_details" in meta
        details = meta["merge_details"]
        assert details["strategy"] == "weight_average"
        assert details["sources"] == SOURCES_2
        assert details["overall_conflict"] == 0.333
        assert details["dominant_model"] == 0

    def test_metadata_without_provenance(self):
        card = AutoModelCard()
        meta = card.generate_metadata(sources=SOURCES_2, strategy="ties")
        details = meta["merge_details"]
        assert "overall_conflict" not in details

    def test_metadata_license(self):
        cfg = ModelCardConfig(license="mit")
        card = AutoModelCard(config=cfg)
        meta = card.generate_metadata(sources=SOURCES_2, strategy="linear")
        assert meta["license"] == "mit"


class TestAutoModelCardJsonLd:
    """Test JSON-LD generation for EU AI Act."""

    def test_basic_json_ld(self):
        card = AutoModelCard()
        ld = card.to_json_ld(sources=SOURCES_2, strategy="weight_average")
        assert ld["@context"] == "https://schema.org"
        assert ld["@type"] == "SoftwareApplication"
        assert ld["name"] == "Merged Model"
        assert len(ld["isBasedOn"]) == 2
        assert ld["isBasedOn"][0]["name"] == "user/modelA"

    def test_json_ld_additional_properties(self):
        card = AutoModelCard()
        ld = card.to_json_ld(sources=SOURCES_2, strategy="slerp")
        props = {p["name"]: p["value"] for p in ld["additionalProperty"]}
        assert props["merge_strategy"] == "slerp"
        assert props["num_sources"] == 2

    def test_json_ld_with_provenance(self):
        prov = _make_provenance(overall_conflict=0.42)
        card = AutoModelCard()
        ld = card.to_json_ld(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        props = {p["name"]: p["value"] for p in ld["additionalProperty"]}
        assert "overall_conflict_score" in props
        assert props["overall_conflict_score"] == 0.42
        assert "dominant_model_index" in props

    def test_json_ld_three_sources(self):
        card = AutoModelCard()
        ld = card.to_json_ld(sources=SOURCES_3, strategy="ties")
        assert len(ld["isBasedOn"]) == 3

    def test_json_ld_serializable(self):
        prov = _make_provenance()
        card = AutoModelCard()
        ld = card.to_json_ld(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        # Must be JSON-serializable
        serialized = json.dumps(ld)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["@context"] == "https://schema.org"

    def test_json_ld_creator_info(self):
        card = AutoModelCard()
        ld = card.to_json_ld(sources=SOURCES_2, strategy="weight_average")
        assert ld["creator"]["name"] == "crdt-merge"
        assert "github.com" in ld["creator"]["url"]


# ===========================================================================
# ModelCardConfig Tests
# ===========================================================================


class TestModelCardConfig:
    """Test ModelCardConfig dataclass."""

    def test_defaults(self):
        cfg = ModelCardConfig()
        assert cfg.include_lineage is True
        assert cfg.include_strategies is True
        assert cfg.include_crdt_badge is True
        assert cfg.include_eu_ai_act is False
        assert cfg.language == "en"
        assert cfg.license == "apache-2.0"
        assert cfg.tags == []

    def test_custom_values(self):
        cfg = ModelCardConfig(
            include_lineage=False,
            include_strategies=False,
            include_crdt_badge=False,
            include_eu_ai_act=True,
            language="de",
            license="bsl-1.1",
            tags=["special", "model"],
        )
        assert cfg.include_lineage is False
        assert cfg.include_eu_ai_act is True
        assert cfg.language == "de"
        assert cfg.license == "bsl-1.1"
        assert len(cfg.tags) == 2

    def test_tags_are_independent(self):
        """Ensure default tags list is not shared between instances."""
        cfg1 = ModelCardConfig()
        cfg2 = ModelCardConfig()
        cfg1.tags.append("mutated")
        assert "mutated" not in cfg2.tags

    def test_all_sections_disabled(self):
        cfg = ModelCardConfig(
            include_lineage=False,
            include_strategies=False,
            include_crdt_badge=False,
        )
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "## Merge Details" not in md
        assert "## Strategy" not in md
        assert "## CRDT Verification" not in md
        # Frontmatter and title still present
        assert "---" in md
        assert "# Merged Model" in md


# ===========================================================================
# _dict_to_yaml Tests
# ===========================================================================


class TestDictToYaml:
    """Test minimal YAML serializer."""

    def test_simple_values(self):
        result = _dict_to_yaml({"key": "value", "num": 42})
        assert "key: value" in result
        assert "num: 42" in result

    def test_list_values(self):
        result = _dict_to_yaml({"items": ["a", "b", "c"]})
        assert "  - a" in result
        assert "  - b" in result
        assert "  - c" in result

    def test_nested_dict(self):
        result = _dict_to_yaml({"outer": {"inner": "val"}})
        assert "outer:" in result
        assert "  inner: val" in result

    def test_bool_values(self):
        result = _dict_to_yaml({"flag": True, "off": False})
        assert "flag: true" in result
        assert "off: false" in result

    def test_float_values(self):
        result = _dict_to_yaml({"score": 0.95})
        assert "score: 0.95" in result


# ===========================================================================
# HFMergeResult Tests
# ===========================================================================


class TestHFMergeResult:
    """Test HFMergeResult dataclass."""

    def test_creation(self):
        prov = _make_provenance()
        result = HFMergeResult(
            state_dict={"w": [1, 2, 3]},
            provenance=prov,
            model_card="# Card",
            repo_url="https://huggingface.co/user/model",
        )
        assert result.state_dict == {"w": [1, 2, 3]}
        assert result.provenance.overall_conflict == 0.25
        assert result.model_card == "# Card"
        assert result.repo_url == "https://huggingface.co/user/model"

    def test_optional_fields(self):
        result = HFMergeResult(
            state_dict={},
            provenance=None,
            model_card="",
        )
        assert result.provenance is None
        assert result.repo_url is None


# ===========================================================================
# HFMergeHub Tests (mock-based)
# ===========================================================================


class TestHFMergeHubInit:
    """Test HFMergeHub initialization."""

    def test_default_init(self):
        hub = HFMergeHub()
        assert hub.cache_dir is None

    def test_with_token(self):
        hub = HFMergeHub(token="test-token")
        assert hub.token == "test-token"

    def test_with_cache_dir(self):
        hub = HFMergeHub(cache_dir="/tmp/test_cache")
        assert hub.cache_dir == "/tmp/test_cache"

    def test_token_from_env(self):
        import os
        old = os.environ.get("HF_TOKEN")
        try:
            os.environ["HF_TOKEN"] = "env-token-xyz"
            hub = HFMergeHub()
            assert hub.token == "env-token-xyz"
        finally:
            if old is None:
                os.environ.pop("HF_TOKEN", None)
            else:
                os.environ["HF_TOKEN"] = old


class TestHFMergeHubMerge:
    """Test HFMergeHub.merge() with mocked HF API."""

    def test_merge_too_few_sources(self):
        hub = HFMergeHub(token="test")
        with pytest.raises(ValueError, match="At least two"):
            hub.merge(sources=["single/model"])

    def test_merge_invalid_strategy(self):
        hub = HFMergeHub(token="test")
        with pytest.raises(ValueError, match="Unknown strategy"):
            hub.merge(sources=SOURCES_2, strategy="nonexistent_strategy_xyz")

    def test_merge_valid_strategy_names(self):
        """All available strategies should be accepted without errors (before pull)."""
        strategies = list_strategies()
        assert "weight_average" in strategies
        assert "slerp" in strategies
        assert "ties" in strategies
        assert len(strategies) >= 25

    @patch.object(HFMergeHub, "pull_weights")
    def test_merge_calls_pull_for_each_source(self, mock_pull):
        mock_pull.return_value = {"layer.weight": [1.0, 2.0]}
        hub = HFMergeHub(token="test")
        result = hub.merge(sources=SOURCES_2, strategy="weight_average")
        assert mock_pull.call_count == 2
        assert isinstance(result, HFMergeResult)
        assert result.model_card != ""
        assert result.repo_url is None  # No destination

    @patch.object(HFMergeHub, "push_weights", return_value="https://huggingface.co/dest/model")
    @patch.object(HFMergeHub, "pull_weights")
    def test_merge_with_destination(self, mock_pull, mock_push):
        mock_pull.return_value = {"layer.weight": [1.0, 2.0]}
        hub = HFMergeHub(token="test")
        result = hub.merge(
            sources=SOURCES_2,
            strategy="weight_average",
            destination="dest/model",
            private=True,
        )
        mock_push.assert_called_once()
        assert result.repo_url == "https://huggingface.co/dest/model"

    @patch.object(HFMergeHub, "pull_weights")
    def test_merge_no_model_card(self, mock_pull):
        mock_pull.return_value = {"layer.weight": [1.0, 2.0]}
        hub = HFMergeHub(token="test")
        result = hub.merge(
            sources=SOURCES_2,
            strategy="weight_average",
            auto_model_card=False,
        )
        assert result.model_card == ""

    @patch.object(HFMergeHub, "pull_weights")
    def test_merge_with_weights(self, mock_pull):
        mock_pull.return_value = {"layer.weight": [1.0, 2.0]}
        hub = HFMergeHub(token="test")
        result = hub.merge(
            sources=SOURCES_2,
            strategy="weight_average",
            weights=[0.7, 0.3],
        )
        assert isinstance(result, HFMergeResult)


class TestHFMergeHubHfApiRequired:
    """Test that _hub_api raises ImportError when huggingface_hub is absent."""

    def test_require_hf_hub_missing(self):
        import sys
        # Temporarily hide huggingface_hub
        saved = sys.modules.get("huggingface_hub")
        sys.modules["huggingface_hub"] = None
        try:
            with pytest.raises(ImportError, match="pip install huggingface_hub"):
                _require_hf_hub()
        finally:
            if saved is None:
                sys.modules.pop("huggingface_hub", None)
            else:
                sys.modules["huggingface_hub"] = saved


class TestHFMergeHubListModels:
    """Test list_merge_models with mock."""

    def test_list_models_mock(self):
        mock_api = MagicMock()
        mock_model = MagicMock()
        mock_model.id = "user/merged-model"
        mock_model.author = "user"
        mock_model.tags = ["merge"]
        mock_model.downloads = 100
        mock_api.list_models.return_value = [mock_model]

        hub = HFMergeHub(token="test")
        hub._hub_api = MagicMock(return_value=mock_api)
        results = hub.list_merge_models(author="user", limit=5)

        assert len(results) == 1
        assert results[0]["id"] == "user/merged-model"
        assert results[0]["author"] == "user"
        assert results[0]["downloads"] == 100


# ===========================================================================
# HfSource / HfTarget Tests (mock-based)
# ===========================================================================


class TestHfSource:
    """Test HfSource adapter."""

    def test_init(self):
        src = HfSource("user/model", revision="main", token="tok")
        assert src.repo_id == "user/model"
        assert src.revision == "main"
        assert src.token == "tok"

    def test_init_defaults(self):
        src = HfSource("user/model")
        assert src.revision is None

    def test_require_hf_hub_missing(self):
        import sys
        saved = sys.modules.get("huggingface_hub")
        sys.modules["huggingface_hub"] = None
        try:
            with pytest.raises(ImportError, match="pip install huggingface_hub"):
                _require_hf_hub_targets()
        finally:
            if saved is None:
                sys.modules.pop("huggingface_hub", None)
            else:
                sys.modules["huggingface_hub"] = saved


class TestHfTarget:
    """Test HfTarget adapter."""

    def test_init(self):
        tgt = HfTarget("user/dest", token="tok", private=True)
        assert tgt.repo_id == "user/dest"
        assert tgt.token == "tok"
        assert tgt.private is True

    def test_init_defaults(self):
        tgt = HfTarget("user/dest")
        assert tgt.private is False


# ===========================================================================
# Integration tests with real crdt_merge APIs
# ===========================================================================


class TestModelCardWithRealProvenance:
    """Test model card generation using real crdt_merge provenance APIs."""

    def test_tracker_to_model_card(self):
        """Build a ProvenanceTracker, generate summary, feed to model card."""
        tracker = ProvenanceTracker()
        tracker.track_merge(
            "layer0.weight",
            tensors=[[1, 2], [3, 4]],
            weights=[0.5, 0.5],
            strategy_name="weight_average",
        )
        tracker.track_merge(
            "layer1.weight",
            tensors=[[5, 6], [7, 8]],
            weights=[0.6, 0.4],
            strategy_name="weight_average",
        )
        summary = tracker.summary()
        assert isinstance(summary, ProvenanceSummary)
        assert len(summary.per_layer) == 2

        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=summary,
            weights=[0.5, 0.5],
            verified=True,
        )
        assert "layer0.weight" in md
        assert "layer1.weight" in md
        assert "## Provenance" in md
        assert "verified-brightgreen" in md

    def test_tracker_to_json_ld(self):
        """Real provenance summary used in JSON-LD generation."""
        tracker = ProvenanceTracker()
        tracker.track_merge(
            "attn.weight",
            tensors=[[1, 0], [0, 1]],
            weights=[0.5, 0.5],
            strategy_name="weight_average",
        )
        summary = tracker.summary()

        card = AutoModelCard()
        ld = card.to_json_ld(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=summary,
        )
        props = {p["name"]: p["value"] for p in ld["additionalProperty"]}
        assert "overall_conflict_score" in props
        assert isinstance(props["overall_conflict_score"], float)

    def test_metadata_with_real_provenance(self):
        tracker = ProvenanceTracker()
        tracker.track_merge(
            "block.linear",
            tensors=[[0.5], [0.5]],
            weights=[0.5, 0.5],
            strategy_name="weight_average",
        )
        summary = tracker.summary()

        card = AutoModelCard()
        meta = card.generate_metadata(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=summary,
        )
        assert meta["merge_details"]["dominant_model"] == summary.dominant_model


class TestModelMergeToModelCard:
    """End-to-end: ModelMerge → provenance → model card."""

    def test_merge_result_provenance_to_card(self):
        """Run an actual merge with ModelCRDT and generate a model card."""
        schema = ModelMergeSchema(strategies={"default": "weight_average"})
        merger = ModelCRDT(schema)

        w1 = {"a.weight": [1.0, 2.0, 3.0], "b.weight": [4.0, 5.0, 6.0]}
        w2 = {"a.weight": [7.0, 8.0, 9.0], "b.weight": [10.0, 11.0, 12.0]}

        result = merger.merge([w1, w2], weights=[0.5, 0.5])
        assert isinstance(result, MergeResult)

        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=result.provenance,
            weights=[0.5, 0.5],
            verified=True,
        )
        assert "# Merged Model" in md
        assert "weight_average" in md

    def test_merge_with_different_strategies(self):
        """Verify model card works with different strategy names."""
        for strat_name in ["weight_average", "linear"]:
            schema = ModelMergeSchema(strategies={"default": strat_name})
            merger = ModelMerge(schema)
            w1 = {"x": [1.0, 2.0]}
            w2 = {"x": [3.0, 4.0]}
            result = merger.merge([w1, w2])
            card = AutoModelCard()
            md = card.generate(
                sources=SOURCES_2,
                strategy=strat_name,
                provenance=result.provenance,
            )
            assert strat_name in md

    def test_merge_ties_requires_base(self):
        """Verify ties strategy works with base_model param."""
        schema = ModelMergeSchema(strategies={"default": "ties"})
        merger = ModelMerge(schema)
        base = {"x": [0.0, 0.0]}
        w1 = {"x": [1.0, 2.0]}
        w2 = {"x": [3.0, 4.0]}
        result = merger.merge([w1, w2], base_model=base)
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="ties",
            provenance=result.provenance,
        )
        assert "ties" in md


class TestMultipleStrategiesModelCard:
    """Test model card with provenance from different strategies per layer."""

    def test_mixed_strategy_provenance(self):
        per_layer = {
            "attn.weight": LayerProvenance(
                layer_name="attn.weight",
                strategy_used="slerp",
                dominant_source=0,
                contribution_map={0: 0.7, 1: 0.3},
                conflict_score=0.1,
                metadata={},
            ),
            "ffn.weight": LayerProvenance(
                layer_name="ffn.weight",
                strategy_used="ties",
                dominant_source=1,
                contribution_map={0: 0.4, 1: 0.6},
                conflict_score=0.4,
                metadata={},
            ),
        }
        summary = ProvenanceSummary(
            overall_conflict=0.25,
            dominant_model=0,
            layer_conflict_ranking=["ffn.weight", "attn.weight"],
            per_layer=per_layer,
        )
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="slerp",
            provenance=summary,
        )
        # Strategy distribution should show both strategies
        assert "slerp" in md
        assert "ties" in md
        assert "attn.weight" in md
        assert "ffn.weight" in md


# ===========================================================================
# Hub __init__ imports
# ===========================================================================


class TestHubImports:
    """Test that hub __init__ exports the right symbols."""

    def test_hf_merge_hub_import(self):
        assert HFMergeHubImport is HFMergeHub

    def test_auto_model_card_import(self):
        assert AutoModelCardImport is AutoModelCard

    def test_model_card_config_import(self):
        assert ModelCardConfigImport is ModelCardConfig


class TestTargetsImports:
    """Test model/targets __init__ exports."""

    def test_hf_source_import(self):
        from crdt_merge.model.targets import HfSource as Imported
        assert Imported is HfSource

    def test_hf_target_import(self):
        from crdt_merge.model.targets import HfTarget as Imported
        assert Imported is HfTarget


# ===========================================================================
# Edge cases and error handling
# ===========================================================================


class TestEdgeCases:
    """Edge cases for model card and hub operations."""

    def test_empty_tags(self):
        cfg = ModelCardConfig(tags=[])
        card = AutoModelCard(config=cfg)
        meta = card.generate_metadata(sources=SOURCES_2, strategy="weight_average")
        assert "merge" in meta["tags"]

    def test_many_sources(self):
        sources = [f"user/model-{i}" for i in range(10)]
        card = AutoModelCard()
        md = card.generate(sources=sources, strategy="weight_average")
        assert "10 source models" in md

    def test_provenance_no_per_layer(self):
        """Provenance with empty per_layer should still generate card."""
        prov = ProvenanceSummary(
            overall_conflict=0.0,
            dominant_model=0,
            layer_conflict_ranking=[],
            per_layer={},
        )
        card = AutoModelCard()
        md = card.generate(
            sources=SOURCES_2,
            strategy="weight_average",
            provenance=prov,
        )
        assert "## Provenance" in md
        assert "0.0000" in md

    def test_model_card_special_characters_in_source(self):
        sources = ["org/model-with-dashes", "user/model_with_underscores"]
        card = AutoModelCard()
        md = card.generate(sources=sources, strategy="weight_average")
        assert "model-with-dashes" in md
        assert "model_with_underscores" in md

    def test_generate_metadata_returns_dict(self):
        card = AutoModelCard()
        meta = card.generate_metadata(sources=SOURCES_2, strategy="slerp")
        assert isinstance(meta, dict)
        assert isinstance(meta["tags"], list)
        assert isinstance(meta["merge_details"], dict)

    def test_json_ld_no_provenance(self):
        card = AutoModelCard()
        ld = card.to_json_ld(sources=SOURCES_2, strategy="weight_average")
        props = {p["name"]: p["value"] for p in ld["additionalProperty"]}
        assert "overall_conflict_score" not in props

    def test_provenance_summary_fields(self):
        prov = _make_provenance()
        assert isinstance(prov.overall_conflict, float)
        assert isinstance(prov.dominant_model, int)
        assert isinstance(prov.layer_conflict_ranking, list)
        assert isinstance(prov.per_layer, dict)


class TestAllConfigCombinations:
    """Test various configuration combinations."""

    @pytest.mark.parametrize("include_lineage", [True, False])
    @pytest.mark.parametrize("include_strategies", [True, False])
    @pytest.mark.parametrize("include_crdt_badge", [True, False])
    def test_config_combination(self, include_lineage, include_strategies, include_crdt_badge):
        cfg = ModelCardConfig(
            include_lineage=include_lineage,
            include_strategies=include_strategies,
            include_crdt_badge=include_crdt_badge,
        )
        card = AutoModelCard(config=cfg)
        md = card.generate(sources=SOURCES_2, strategy="weight_average")
        assert "# Merged Model" in md
        if include_lineage:
            assert "## Merge Details" in md
        else:
            assert "## Merge Details" not in md

    @pytest.mark.parametrize("strategy", ["weight_average", "slerp", "ties", "dare", "linear"])
    def test_card_for_each_strategy(self, strategy):
        card = AutoModelCard()
        md = card.generate(sources=SOURCES_2, strategy=strategy)
        assert strategy in md

    @pytest.mark.parametrize("lang", ["en", "fr", "de", "zh"])
    def test_language_metadata(self, lang):
        cfg = ModelCardConfig(language=lang)
        card = AutoModelCard(config=cfg)
        meta = card.generate_metadata(sources=SOURCES_2, strategy="weight_average")
        assert meta["language"] == lang
