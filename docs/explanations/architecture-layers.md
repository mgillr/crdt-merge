# Why 6-Layer Architecture?

## Design Goals

1. **Minimal dependencies per use case**: A data engineer shouldn't need torch. An ML engineer shouldn't need DuckDB.
2. **Progressive adoption**: Start with Layer 1 primitives, add layers as needed.
3. **Clear separation of concerns**: Core math vs. data formats vs. network vs. ML vs. enterprise vs. compliance.

## Layer Rationale

### Layer 1 (Core): The Foundation
Pure Python, zero dependencies. Anyone can use CRDTs without installing anything extra. This layer is the mathematical foundation — every other layer depends on it.

### Layer 2 (Engines): Real-World Data
Bridges the gap between abstract CRDTs and real data formats (DataFrames, Arrow, Parquet). Optional dependencies (pandas, pyarrow) only needed here.

### Layer 3 (Transport): Distributed Systems
When data needs to move across networks. Serialization, gossip, Merkle trees, delta compression. Only needed for distributed deployments.

### Layer 4 (AI/Model): Machine Learning
The largest layer by far (56% of code). ML model merging is complex — 26+ strategies, LoRA support, continual learning, federated learning, GPU acceleration. Separated because it requires torch and transformers.

### Layer 5 (Enterprise): Production
Security, auditing, access control, observability. Only needed for enterprise deployments. Wrapped around lower layers — zero overhead when not used.

### Layer 6 (Compliance): Regulation
Regulatory compliance is kept separate because it's highly specialized and changes frequently. GDPR, HIPAA, SOX, and EU AI Act each have different requirements.
