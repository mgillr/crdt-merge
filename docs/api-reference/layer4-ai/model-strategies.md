# crdt_merge.model.strategies — All 26+ Model Merge Strategies

**Package**: `crdt_merge/model/strategies/`
**Layer**: 4 — AI / Model / Agent
**Modules**: 9 strategy modules
**Dependencies**: `torch`, `numpy`

---

## Overview

26+ strategies for merging ML model weights, organized into categories.

---

## Base

### BaseStrategy (Abstract)
```python
class BaseStrategy:
    def merge(self, tensors: List[Tensor], weights: Optional[List[float]] = None, **kwargs) -> Tensor
    def name(self) -> str
```

---

## Basic Strategies (`strategies/basic.py`)

| Strategy | Description |
|----------|-------------|
| `UniformMerge` | Simple average of all model weights |
| `WeightedAverage` | Weighted average with user-specified weights |
| `MedianMerge` | Element-wise median |

## Weighted Strategies (`strategies/weighted.py`)

| Strategy | Description |
|----------|-------------|
| `TaskArithmetic` | Task vector arithmetic (Ilharco et al.) |
| `TiesMerge` | TIES: Trim, Elect Sign, Merge (Yadav et al.) |
| `DareMerge` | DARE: Drop and Rescale (Yu et al.) |
| `FisherMerge` | Fisher information weighted merge |

## Subspace Strategies (`strategies/subspace.py`)

| Strategy | Description |
|----------|-------------|
| `PCAMerge` | PCA-based subspace alignment |
| `SVDMerge` | SVD decomposition merge |
| `SubspaceAlignment` | Align model subspaces before merging |

## Evolutionary Strategies (`strategies/evolutionary.py`)

| Strategy | Description |
|----------|-------------|
| `EvolutionaryMerge` | Genetic algorithm-based weight selection |
| `CMAESMerge` | CMA-ES optimization for merge weights |
| `RandomSearchMerge` | Random search over merge configurations |

## Calibration Strategies (`strategies/calibration.py`)

| Strategy | Description |
|----------|-------------|
| `CalibrationMerge` | Calibrate merge weights using validation data |
| `TemperatureScaling` | Temperature scaling for output calibration |
| `IsotonicCalibration` | Isotonic regression calibration |

## Continual Learning Strategies (`strategies/continual.py`)

| Strategy | Description |
|----------|-------------|
| `EWCMerge` | Elastic Weight Consolidation |
| `SIMerge` | Synaptic Intelligence |
| `PackNetMerge` | PackNet-style selective merging |

## Unlearning Strategies (`strategies/unlearning.py`)

| Strategy | Description |
|----------|-------------|
| `GradientAscentUnlearn` | Gradient ascent on forget set |
| `FisherForget` | Fisher information-based forgetting |
| `SISAUnlearn` | SISA: Sharded, Isolated, Sliced, Aggregated |

## Safety Strategies (`strategies/safety.py`)

| Strategy | Description |
|----------|-------------|
| `SafetyConstrainedMerge` | Merge with safety constraints |
| `AlignmentPreserving` | Preserve alignment properties during merge |
| `RobustnessAware` | Consider robustness metrics during merging |


## Analysis Notes
