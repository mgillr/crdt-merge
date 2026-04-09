# SPDX-License-Identifier: BUSL-1.1
# Tests for docs/guides/ code examples using synthetic numpy data.
# Covers: federated-model-merging.md, lora-adapter-merging.md,
#         continual-learning-without-forgetting.md

from __future__ import annotations

import numpy as np
import pytest

np.random.seed(42)

# ---------------------------------------------------------------------------
# Shared synthetic data (regenerated per test via fixtures to avoid leakage)
# ---------------------------------------------------------------------------

def _tensor(shape=(100,), seed=42):
    rng = np.random.default_rng(seed)
    return rng.standard_normal(shape).astype(np.float32)


# ===========================================================================
# Guide 1: federated-model-merging.md
# ===========================================================================

class TestFederatedQuickStart:
    """Guide: Quick Start — CRDT-Compliant Model Merge."""

    def test_three_teams_add_contributions(self):
        """Each team can create a CRDTMergeState and add a tensor."""
        from crdt_merge.model import CRDTMergeState

        math_tensors = _tensor((100,), seed=1)
        code_tensors = _tensor((100,), seed=2)
        reasoning_tensors = _tensor((100,), seed=3)
        fixed_code_tensors = _tensor((100,), seed=4)

        team_a = CRDTMergeState("weight_average")
        team_b = CRDTMergeState("weight_average")
        team_c = CRDTMergeState("weight_average")

        team_a.add(math_tensors, model_id="llama-math-v2", weight=0.4)
        team_b.add(code_tensors, model_id="llama-code-v3", weight=0.35)
        team_c.add(reasoning_tensors, model_id="llama-reason-v1", weight=0.25)

        # Team B removes and replaces -- no coordinator needed
        team_b.remove("llama-code-v3")
        team_b.add(fixed_code_tensors, model_id="llama-code-v4", weight=0.35)

        # Sync: all three teams merge in different orders
        merged_ab = team_a.merge(team_b)
        merged_abc = merged_ab.merge(team_c)

        merged_ba = team_b.merge(team_a)
        merged_bac = merged_ba.merge(team_c)

        resolved_abc = merged_abc.resolve()
        resolved_bac = merged_bac.resolve()

        # Both resolve paths should produce the same result (CRDT convergence)
        np.testing.assert_array_almost_equal(resolved_abc, resolved_bac)

    def test_merge_returns_self(self):
        """merge() mutates self in-place and returns self (mutable semantics per architecture spec)."""
        from crdt_merge.model import CRDTMergeState

        a = CRDTMergeState("weight_average")
        a.add(_tensor(seed=10), model_id="m1")
        b = CRDTMergeState("weight_average")
        b.add(_tensor(seed=11), model_id="m2")

        merged = a.merge(b)
        assert merged is a  # in-place mutation, returns self
        assert "m1" in a.model_ids
        assert "m2" in a.model_ids

    def test_remove_before_add_works(self):
        """remove() tombstones a model_id so it's excluded from resolve."""
        from crdt_merge.model import CRDTMergeState

        t1 = _tensor(seed=20)
        t2 = _tensor(seed=21)

        state = CRDTMergeState("weight_average")
        state.add(t1, model_id="v1", weight=1.0)
        state.remove("v1")
        state.add(t2, model_id="v2", weight=1.0)

        result = state.resolve()
        # After removing v1 and adding v2, result should equal t2
        np.testing.assert_array_almost_equal(result, t2, decimal=5)

    def test_commutativity_of_add_order(self):
        """Adding contributions in different orders gives identical resolve."""
        from crdt_merge.model import CRDTMergeState

        t1 = _tensor(seed=30)
        t2 = _tensor(seed=31)

        state_ab = CRDTMergeState("weight_average")
        state_ab.add(t1, model_id="m1", weight=0.5)
        state_ab.add(t2, model_id="m2", weight=0.5)

        state_ba = CRDTMergeState("weight_average")
        state_ba.add(t2, model_id="m2", weight=0.5)
        state_ba.add(t1, model_id="m1", weight=0.5)

        np.testing.assert_array_almost_equal(
            state_ab.resolve(), state_ba.resolve()
        )


class TestFederatedPharmaScenario:
    """Guide: Cross-Organisation Model Collaboration — pharma scenario."""

    def test_pharma_dare_ties_with_base(self):
        """dare_ties strategy resolves when a base tensor is provided."""
        from crdt_merge.model import CRDTMergeState

        base = _tensor((100,), seed=0)
        w_a = _tensor((100,), seed=1)
        w_b = _tensor((100,), seed=2)
        w_c = _tensor((100,), seed=3)

        pharma_a = CRDTMergeState("dare_ties", base=base)
        pharma_a.add(w_a, model_id="pf-model-v4", weight=0.4,
                     metadata={"training_samples": 50000, "domain": "oncology"})

        pharma_b = CRDTMergeState("dare_ties", base=base)
        pharma_b.add(w_b, model_id="pf-model-v7", weight=0.35,
                     metadata={"training_samples": 38000, "domain": "cardiology"})

        pharma_c = CRDTMergeState("dare_ties", base=base)
        pharma_c.add(w_c, model_id="pf-model-v2", weight=0.25,
                     metadata={"training_samples": 29000, "domain": "neurology"})

        merged = pharma_a.merge(pharma_b).merge(pharma_c)
        result = merged.resolve()
        assert result.shape == (100,)

    def test_wire_serialize_deserialize(self):
        """CRDTMergeState can be serialized and deserialized via wire protocol."""
        from crdt_merge.model import CRDTMergeState
        from crdt_merge.wire import serialize, deserialize

        state = CRDTMergeState("weight_average")
        state.add(_tensor(seed=40), model_id="model-a", weight=0.4)

        wire_bytes = serialize(state)
        assert isinstance(wire_bytes, bytes)

        recovered = deserialize(wire_bytes)
        assert recovered is not None


class TestContinualLearningInFederatedGuide:
    """Guide: Continual Learning Across Deployments (federated guide section)."""

    def test_continual_merge_absorb_and_export(self):
        """ContinualMerge accepts absorb() calls and exports a merged model."""
        from crdt_merge.model.continual import ContinualMerge

        base_model = {
            "layer1": _tensor((10, 10), seed=50).reshape(10, 10),
            "layer2": _tensor((10,), seed=51),
        }

        cm = ContinualMerge(
            base_model=base_model,
            strategy="weight_average",
        )

        # Simulate regional updates
        for i in range(3):
            update = {
                "layer1": _tensor((10, 10), seed=60 + i).reshape(10, 10),
                "layer2": _tensor((10,), seed=70 + i),
            }
            cm.absorb(update, name=f"update-server{i}", weight=0.2)

        result = cm.export()
        assert set(result.keys()) == {"layer1", "layer2"}


class TestVerifyCRDT:
    """Guide: Verifying CRDT Compliance."""

    def test_verify_crdt_passes(self):
        """verify_crdt should pass commutativity, associativity, idempotency."""
        from crdt_merge.verify import verify_crdt
        from crdt_merge.model import CRDTMergeState

        def gen_state():
            state = CRDTMergeState("weight_average")
            state.add(
                np.random.randn(10, 10).astype(np.float32),
                model_id="model",
            )
            return state

        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=gen_state,
            trials=20,
        )
        assert result.passed
        assert result.commutativity.passed

    def test_verify_crdt_total_trials_positive(self):
        """total_trials should be positive after running verify_crdt."""
        from crdt_merge.verify import verify_crdt
        from crdt_merge.model import CRDTMergeState

        result = verify_crdt(
            merge_fn=lambda a, b: a.merge(b),
            gen_fn=lambda: CRDTMergeState("weight_average"),
            trials=5,
        )
        assert result.total_trials > 0


# ===========================================================================
# Guide 2: lora-adapter-merging.md
# ===========================================================================

class TestLoRAQuickStart:
    """Guide: Quick Start — LoRA merge_adapters."""

    def test_merge_two_adapters_same_rank(self):
        """merge_adapters works with two same-rank adapters."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        adapter_a = {
            "q_proj": {
                "lora_A": np.random.randn(4, 10).astype(np.float32),
                "lora_B": np.random.randn(10, 4).astype(np.float32),
            },
        }
        adapter_b = {
            "q_proj": {
                "lora_A": np.random.randn(4, 10).astype(np.float32),
                "lora_B": np.random.randn(10, 4).astype(np.float32),
            },
        }

        schema = LoRAMergeSchema(strategies={"q_proj": "weight_average"})
        merger = LoRAMerge(schema=schema)
        merged = merger.merge_adapters([adapter_a, adapter_b], weights=[0.6, 0.4])

        assert "q_proj" in merged
        assert "lora_A" in merged["q_proj"]
        assert "lora_B" in merged["q_proj"]
        assert merged["q_proj"]["lora_A"].shape == (4, 10)

    def test_merge_adapters_different_ranks_adaptive(self):
        """Adaptive rank harmonization picks weight-proportional rank."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        adapter_a = {
            "q_proj": {
                "lora_A": np.random.randn(64, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 64).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(64, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 64).astype(np.float32),
            },
        }
        adapter_b = {
            "q_proj": {
                "lora_A": np.random.randn(16, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 16).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(16, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 16).astype(np.float32),
            },
        }
        adapter_c = {
            "q_proj": {
                "lora_A": np.random.randn(32, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 32).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(32, 768).astype(np.float32),
                "lora_B": np.random.randn(768, 32).astype(np.float32),
            },
        }

        schema = LoRAMergeSchema(
            strategies={"q_proj": "weight_average", "v_proj": "weight_average"}
        )
        merger = LoRAMerge(schema=schema)
        merged = merger.merge_adapters(
            adapters=[adapter_a, adapter_b, adapter_c],
            weights=[0.5, 0.25, 0.25],
            rank_strategy="adaptive",
        )

        # adaptive rank = round(64*0.5 + 16*0.25 + 32*0.25) = round(44) = 44
        assert merged["q_proj"]["lora_A"].shape[0] == 44


class TestLoRARankHarmonization:
    """Guide: Cookbook — All Rank Harmonization Strategies."""

    @pytest.fixture
    def adapters_and_weights(self):
        adapters = [
            {
                "layer": {
                    "lora_A": np.random.randn(64, 128).astype(np.float32),
                    "lora_B": np.random.randn(128, 64).astype(np.float32),
                }
            },
            {
                "layer": {
                    "lora_A": np.random.randn(16, 128).astype(np.float32),
                    "lora_B": np.random.randn(128, 16).astype(np.float32),
                }
            },
            {
                "layer": {
                    "lora_A": np.random.randn(32, 128).astype(np.float32),
                    "lora_B": np.random.randn(128, 32).astype(np.float32),
                }
            },
        ]
        return adapters, [0.5, 0.25, 0.25]

    def _merger(self):
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema
        return LoRAMerge(schema=LoRAMergeSchema(strategies={"layer": "weight_average"}))

    def test_rank_max(self, adapters_and_weights):
        """max rank strategy: target rank = max(64, 16, 32) = 64."""
        adapters, weights = adapters_and_weights
        result = self._merger().merge_adapters(adapters, weights, rank_strategy="max")
        assert result["layer"]["lora_A"].shape[0] == 64

    def test_rank_min(self, adapters_and_weights):
        """min rank strategy: target rank = min(64, 16, 32) = 16."""
        adapters, weights = adapters_and_weights
        result = self._merger().merge_adapters(adapters, weights, rank_strategy="min")
        assert result["layer"]["lora_A"].shape[0] == 16

    def test_rank_mean(self, adapters_and_weights):
        """mean rank strategy: target rank = round(mean(64,16,32)) = 37."""
        adapters, weights = adapters_and_weights
        result = self._merger().merge_adapters(adapters, weights, rank_strategy="mean")
        assert result["layer"]["lora_A"].shape[0] == 37

    def test_rank_adaptive(self, adapters_and_weights):
        """adaptive rank strategy: rank = round(64*0.5 + 16*0.25 + 32*0.25) = 44."""
        adapters, weights = adapters_and_weights
        result = self._merger().merge_adapters(adapters, weights, rank_strategy="adaptive")
        # actual weighted sum: 64*0.5 + 16*0.25 + 32*0.25 = 44
        assert result["layer"]["lora_A"].shape[0] == 44


class TestLoRAPerModuleStrategy:
    """Guide: Cookbook — Per-Module Strategy Assignment."""

    def test_schema_with_multiple_strategies(self):
        """LoRAMergeSchema with multiple module strategies constructs correctly."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        schema = LoRAMergeSchema(strategies={
            "q_proj": "weight_average",
            "k_proj": "weight_average",
            "v_proj": "weight_average",
            "o_proj": "weight_average",
            "gate_proj": "weight_average",
            "up_proj": "weight_average",
            "down_proj": "weight_average",
            "default": "weight_average",
        })
        merger = LoRAMerge(schema=schema)
        assert merger is not None

    def test_merge_two_adapters_per_module(self):
        """Merge two adapters using per-module strategy assignment."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        # Synthetic adapters substituting for mistral_code_adapter / mistral_math_adapter
        r = 4
        dim = 16
        mistral_code = {
            "q_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
        }
        mistral_math = {
            "q_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
        }

        schema = LoRAMergeSchema(strategies={
            "q_proj": "weight_average",
            "v_proj": "weight_average",
            "default": "weight_average",
        })
        merger = LoRAMerge(schema=schema)
        merged = merger.merge_adapters(
            adapters=[mistral_code, mistral_math],
            weights=[0.6, 0.4],
            rank_strategy="adaptive",
        )

        assert "q_proj" in merged
        assert "v_proj" in merged


class TestLoRAProvenance:
    """Guide: Cookbook — Merge With Provenance (nested adapter format)."""

    def test_merge_adapters_with_provenance_nested(self):
        """merge_adapters_with_provenance returns merged dict and provenance."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        schema = LoRAMergeSchema(
            strategies={"q_proj": "weight_average", "default": "weight_average"}
        )
        merger = LoRAMerge(schema=schema)

        # Use nested format (flat format q_proj.lora_A is NOT supported)
        adapters = [
            {
                "q_proj": {
                    "lora_A": np.random.randn(32, 256).astype(np.float32),
                    "lora_B": np.random.randn(256, 32).astype(np.float32),
                }
            },
            {
                "q_proj": {
                    "lora_A": np.random.randn(32, 256).astype(np.float32),
                    "lora_B": np.random.randn(256, 32).astype(np.float32),
                }
            },
        ]

        merged, provenance = merger.merge_adapters_with_provenance(
            adapters=adapters,
            weights=[0.6, 0.4],
            rank_strategy="max",
        )

        assert "q_proj" in merged
        assert "q_proj" in provenance
        prov = provenance["q_proj"]
        assert "strategy" in prov
        assert "dominant_source" in prov
        assert "contribution_map" in prov


class TestLoRAApplyToBase:
    """Guide: Cookbook — Apply Merged Adapter to Base Model."""

    def test_apply_to_base_preserves_shape(self):
        """apply_to_base returns base model with LoRA applied; shape unchanged."""
        from crdt_merge.model.lora import LoRAMerge, LoRAMergeSchema

        dim = 10
        r = 4

        adapter_a = {
            "q_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
        }
        adapter_b = {
            "q_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
            "v_proj": {
                "lora_A": np.random.randn(r, dim).astype(np.float32),
                "lora_B": np.random.randn(dim, r).astype(np.float32),
            },
        }

        base_model = {
            "q_proj.weight": np.random.randn(dim, dim).astype(np.float32),
            "v_proj.weight": np.random.randn(dim, dim).astype(np.float32),
        }

        schema = LoRAMergeSchema(
            strategies={"q_proj": "weight_average", "v_proj": "weight_average"}
        )
        merger = LoRAMerge(schema=schema)
        merged_adapter = merger.merge_adapters(
            adapters=[adapter_a, adapter_b], weights=[0.6, 0.4]
        )

        fused_model = merger.apply_to_base(merged_adapter, base_model)
        assert "q_proj.weight" in fused_model
        assert fused_model["q_proj.weight"].shape == (dim, dim)


class TestLoRAEnterpriseGovernance:
    """Guide: Enterprise Multi-Team LoRA Governance with CRDTMergeState."""

    def test_crdt_state_with_lora_adapters_weight_average(self):
        """CRDTMergeState with weight_average strategy accepts LoRA-like tensors."""
        from crdt_merge.model import CRDTMergeState

        # Flatten adapters to 1-D for CRDTMergeState.add()
        legal_adapter = _tensor((100,), seed=80)
        finance_adapter = _tensor((100,), seed=81)
        hr_adapter = _tensor((100,), seed=82)

        state = CRDTMergeState("weight_average")
        state.add(legal_adapter, model_id="team_legal_may", weight=0.35,
                  metadata={"team": "legal", "month": "2026-05", "rank": 32})
        state.add(finance_adapter, model_id="team_finance_may", weight=0.40,
                  metadata={"team": "finance", "month": "2026-05", "rank": 48})
        state.add(hr_adapter, model_id="team_hr_may", weight=0.25,
                  metadata={"team": "hr", "month": "2026-05", "rank": 16})

        prod_adapter = state.resolve()
        assert prod_adapter.shape == (100,)

        # Month 2: legal team fixes bias -- remove and replace
        state.remove("team_legal_may")
        fixed_legal = _tensor((100,), seed=83)
        state.add(fixed_legal, model_id="team_legal_may_v2", weight=0.35,
                  metadata={"team": "legal", "month": "2026-05", "rank": 32, "version": 2})

        updated_prod = state.resolve()
        assert updated_prod.shape == (100,)
        # Production adapter should change after the fix
        assert not np.allclose(prod_adapter, updated_prod)


# ===========================================================================
# Guide 3: continual-learning-without-forgetting.md
# ===========================================================================

class TestContinualQuickStart:
    """Guide: Quick Start — ContinualMerge with CRDT mode."""

    def test_absorb_two_tasks_crdt_mode(self):
        """Absorb two fine-tunes in CRDT mode and export a merged model."""
        from crdt_merge.model.continual import ContinualMerge

        base_model = {"layer1": np.random.randn(64, 64).astype(np.float32)}
        ft_code = {"layer1": np.random.randn(64, 64).astype(np.float32)}
        ft_math = {"layer1": np.random.randn(64, 64).astype(np.float32)}

        cm = ContinualMerge(
            base_model=base_model,
            strategy="weight_average",
            convergence="crdt",
        )
        cm.absorb(ft_code, name="code_finetune")
        cm.absorb(ft_math, name="math_finetune")

        merged_model = cm.export()
        assert "layer1" in merged_model

    def test_measure_stability_returns_retention(self):
        """measure_stability() returns a StabilityResult with retention in [0,1]."""
        from crdt_merge.model.continual import ContinualMerge

        base_model = {"layer1": np.random.randn(64, 64).astype(np.float32)}
        ft_code = {"layer1": np.random.randn(64, 64).astype(np.float32)}

        cm = ContinualMerge(
            base_model=base_model,
            strategy="weight_average",
            convergence="crdt",
        )
        cm.absorb(ft_code, name="code_finetune")

        stability = cm.measure_stability("code_finetune")
        assert 0.0 <= stability.retention <= 1.0
        assert "layer1" in stability.per_layer


class TestContinualCRDTvsDefault:
    """Guide: Cookbook — CRDT Mode vs Default Mode."""

    def test_crdt_mode_order_independent(self):
        """CRDT mode: absorbing T2 then T3 equals T3 then T2."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.array([1.0, 0.0, 0.0], dtype=np.float32)}
        t2 = {"w": np.array([0.0, 1.0, 0.0], dtype=np.float32)}
        t3 = {"w": np.array([0.0, 0.0, 1.0], dtype=np.float32)}

        cm_a = ContinualMerge(base, strategy="weight_average", convergence="crdt")
        cm_a.absorb(t2, name="t2")
        cm_a.absorb(t3, name="t3")
        result_a = cm_a.export()

        cm_b = ContinualMerge(base, strategy="weight_average", convergence="crdt")
        cm_b.absorb(t3, name="t3")
        cm_b.absorb(t2, name="t2")
        result_b = cm_b.export()

        np.testing.assert_array_almost_equal(result_a["w"], result_b["w"])

    def test_default_mode_order_sensitive(self):
        """Default mode: different absorb orders can produce different results."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.array([1.0, 0.0, 0.0], dtype=np.float32)}
        t2 = {"w": np.array([0.0, 1.0, 0.0], dtype=np.float32)}
        t3 = {"w": np.array([0.0, 0.0, 1.0], dtype=np.float32)}

        cm_a = ContinualMerge(
            base, strategy="weight_average", convergence="default", memory_budget=0.8
        )
        cm_a.absorb(t2, name="t2")
        cm_a.absorb(t3, name="t3")

        cm_b = ContinualMerge(
            base, strategy="weight_average", convergence="default", memory_budget=0.8
        )
        cm_b.absorb(t3, name="t3")
        cm_b.absorb(t2, name="t2")

        result_a = cm_a.export()
        result_b = cm_b.export()
        # In default mode results may differ -- just check they're valid arrays
        assert "w" in result_a
        assert "w" in result_b

    def test_crdt_verify_convergence(self):
        """verify_convergence() returns True in CRDT mode."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.array([1.0, 2.0], dtype=np.float32)}
        cm = ContinualMerge(base, strategy="weight_average", convergence="crdt")
        cm.absorb({"w": np.array([3.0, 4.0], dtype=np.float32)}, name="ft1")
        assert cm.verify_convergence() is True


class TestContinualStability:
    """Guide: Cookbook — Measuring Stability (Retention Score)."""

    def test_stability_five_tasks(self):
        """Absorb 5 tasks and measure stability; per_layer keys match layers."""
        from crdt_merge.model.continual import ContinualMerge

        rng = np.random.default_rng(99)
        base = {
            "attn": rng.standard_normal((128, 128)).astype(np.float32),
            "ff": rng.standard_normal((128, 512)).astype(np.float32),
        }

        cm = ContinualMerge(base, strategy="weight_average", convergence="crdt")

        for i in range(5):
            ft = {
                "attn": rng.standard_normal((128, 128)).astype(np.float32),
                "ff": rng.standard_normal((128, 512)).astype(np.float32),
            }
            cm.absorb(ft, name=f"task_{i}", weight=0.1)

        # measure_stability takes the absorbed model's name
        stability = cm.measure_stability("task_0")
        assert 0.0 <= stability.retention <= 1.0
        assert "attn" in stability.per_layer
        assert "ff" in stability.per_layer

    def test_stability_base_not_directly_measurable(self):
        """measure_stability raises KeyError for the internal __base__ name."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.ones(10, dtype=np.float32)}
        cm = ContinualMerge(base, strategy="weight_average", convergence="crdt")
        cm.absorb({"w": np.random.randn(10).astype(np.float32)}, name="task_0")

        # The internal base name is __base__, not "base"
        with pytest.raises(KeyError):
            cm.measure_stability("base")


class TestContinualMemoryBudget:
    """Guide: Cookbook — Memory-Budget Decay (Default Mode)."""

    def test_memory_budget_export_valid(self):
        """ContinualMerge with different memory budgets both export valid dicts."""
        from crdt_merge.model.continual import ContinualMerge

        rng = np.random.default_rng(7)
        base = {"w": np.ones(10, dtype=np.float32)}

        cm_high = ContinualMerge(base, convergence="default", memory_budget=0.95)
        cm_low = ContinualMerge(base, convergence="default", memory_budget=0.5)

        for i in range(6):
            ft = {"w": rng.standard_normal(10).astype(np.float32)}
            cm_high.absorb(ft, name=f"task_{i}")
            cm_low.absorb(ft, name=f"task_{i}")

        s_high = cm_high.measure_stability("__base__")
        s_low = cm_low.measure_stability("__base__")

        assert 0.0 <= s_high.retention <= 1.0
        assert 0.0 <= s_low.retention <= 1.0

    def test_memory_budget_clamped(self):
        """memory_budget is clamped to [0.01, 1.0] without raising."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.ones(5, dtype=np.float32)}
        cm = ContinualMerge(base, convergence="default", memory_budget=1.5)
        assert cm._memory_budget <= 1.0
        cm2 = ContinualMerge(base, convergence="default", memory_budget=-0.5)
        assert cm2._memory_budget >= 0.01


class TestContinualReplace:
    """Guide: Scenario — A/B Test Fine-Tune (replace parameter)."""

    def test_absorb_replace_removes_old_contribution(self):
        """absorb(replace=name) removes named contribution before adding new one."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.ones(10, dtype=np.float32)}
        ft_a = {"w": np.ones(10, dtype=np.float32) * 2}
        ft_b = {"w": np.ones(10, dtype=np.float32) * 3}

        cm = ContinualMerge(base, strategy="weight_average", convergence="crdt")
        cm.absorb(ft_a, name="variant_a", weight=0.5)
        cm.absorb(ft_b, name="variant_b", weight=0.5)

        result_with_b = np.array(cm.export()["w"])

        # Replace variant_b with another copy of ft_a
        cm.absorb(ft_a, name="variant_b_fixed", replace="variant_b")
        result_after = np.array(cm.export()["w"])

        # Result should differ after replacing variant_b
        assert not np.allclose(result_with_b, result_after)

    def test_absorb_history_tracks_replacements(self):
        """absorb() history records the replaced model name."""
        from crdt_merge.model.continual import ContinualMerge

        base = {"w": np.ones(5, dtype=np.float32)}
        ft = {"w": np.ones(5, dtype=np.float32) * 2}

        cm = ContinualMerge(base, strategy="weight_average")
        cm.absorb(ft, name="v1")
        cm.absorb(ft * 2 if False else {"w": np.ones(5, dtype=np.float32) * 4},
                  name="v2", replace="v1")

        replaced_entries = [e for e in cm.history if e.get("replaced")]
        assert len(replaced_entries) == 1
        assert replaced_entries[0]["replaced"] == "v1"


class TestContinualDeltaSync:
    """Guide: Scenario — Delta Sync for Distributed Continual Learning."""

    def test_delta_sync_convergence(self):
        """Two ContinualMerge instances absorbing the same update converge."""
        from crdt_merge.model.continual import ContinualMerge

        rng = np.random.default_rng(123)
        current_global = {"layer1": rng.standard_normal(10).astype(np.float32)}
        us_fine_tune = {"layer1": rng.standard_normal(10).astype(np.float32)}

        eu_west = ContinualMerge(
            base_model=current_global, strategy="weight_average", convergence="crdt"
        )
        us_east = ContinualMerge(
            base_model=current_global, strategy="weight_average", convergence="crdt"
        )

        us_east.absorb(us_fine_tune, name="us_east_update_001", weight=0.1)
        eu_west.absorb(us_fine_tune, name="us_east_update_001", weight=0.1)

        eu_export = eu_west.export()
        us_export = us_east.export()

        np.testing.assert_allclose(
            np.array(eu_export["layer1"]),
            np.array(us_export["layer1"]),
            rtol=1e-5,
        )


class TestContinualFederatedHospital:
    """Guide: Scenario — Federated Continual Learning (hospital example)."""

    def test_global_state_aggregation(self):
        """CRDTMergeState aggregates hospital models; remove retracts one."""
        from crdt_merge.model import CRDTMergeState

        rng = np.random.default_rng(55)
        n_hospitals = 5

        # Simulate pre-exported hospital models (flat tensors)
        hospital_models = {
            f"hospital_{i}": rng.standard_normal(20).astype(np.float32)
            for i in range(n_hospitals)
        }

        global_state = CRDTMergeState("weight_average")
        for hospital_id, local_model in hospital_models.items():
            global_state.add(local_model, model_id=hospital_id, weight=1.0 / n_hospitals)

        global_model = global_state.resolve()
        assert global_model.shape == (20,)

        # Retract hospital_2's contribution
        global_state.remove("hospital_2")
        updated_global = global_state.resolve()
        assert updated_global.shape == (20,)
        # Model should change after retraction
        assert not np.allclose(global_model, updated_global)
