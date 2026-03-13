# Design Decisions — Key Rationale

## D-001: Six-Layer Architecture
**Decision**: Organize code into 6 distinct layers with strict dependency direction.
**Rationale**: Each layer can be used independently. A user who only needs DataFrame merging doesn't need to install torch or cryptography. Layers build bottom-up with no circular dependencies.
**Trade-off**: Some duplication (e.g., provenance exists at both Layer 1 and Layer 4 for model-specific provenance).

## D-002: CRDT-First Design
**Decision**: Use CRDT mathematics as the foundation for all merge operations.
**Rationale**: CRDTs provide mathematical guarantees of convergence (commutative, associative, idempotent). This means merges always produce consistent results regardless of execution order.
**Trade-off**: CRDTs can be less intuitive than simple "last write wins" for users unfamiliar with distributed systems theory.

## D-003: Strategy Pattern for Conflict Resolution
**Decision**: Use composable per-field strategies via MergeSchema.
**Rationale**: Different fields in the same record may need different conflict resolution. A `score` field should use MaxWins while a `name` field should use LWW. MergeSchema makes this declarative.
**Trade-off**: Adds complexity vs. a single global strategy.

## D-004: Zero-Dependency Core
**Decision**: Layer 1 uses only Python stdlib.
**Rationale**: Minimizes installation friction and dependency conflicts. Users can use CRDT primitives without installing pandas, pyarrow, or torch.
**Trade-off**: Some optimizations are left to higher layers (e.g., vectorized operations in Arrow engine).

## D-005: Optional Heavy Dependencies
**Decision**: pandas, pyarrow, polars, torch, etc. are all optional.
**Rationale**: The library serves diverse use cases. A data engineer needs pandas but not torch. An ML engineer needs torch but not DuckDB. Optional extras minimize the install footprint.
**Trade-off**: More complex packaging (`extras_require` in setup.py) and conditional imports throughout the codebase.

## D-006: Enterprise Features as Wrappers
**Decision**: Audit, encryption, RBAC, and observability are implemented as wrappers around core merge operations, not baked in.
**Rationale**: Enterprise features should be opt-in, not forced on all users. The wrapper pattern means the core merge path has zero overhead when enterprise features aren't needed.
**Trade-off**: Wrapper composition order matters (RBAC → Audit → Encryption → Observe → Merge).

## D-007: Model Merge as Largest Layer
**Decision**: Layer 4 (AI/Model) is the largest layer at ~13,126 AST lines (44% of codebase).
**Rationale**: Model merging is the most complex domain, with 26+ strategies covering different mathematical approaches (linear interpolation, SLERP, evolutionary, calibration, etc.).
**Trade-off**: This layer may need decomposition if it continues to grow. Consider extracting `model/` as a separate package.

### Layer 4 Size Rationale

Layer 4 (AI/Model) is the largest layer at ~13,126 AST lines, representing approximately 44% of the total codebase (29,768 AST lines). This concentration is architectural by design:

1. **26 merge strategies** — Each strategy (linear interpolation, SLERP, TIES, DARE, evolutionary, calibration, subspace, unlearning, etc.) requires its own mathematical implementation with test coverage
2. **8 accelerator integrations** — DuckDB, dbt, Polars, Flight, Airbyte, DuckLake, SQLite, Streamlit — each with its own adapter layer
3. **HuggingFace Hub integration** — Model card generation, dataset support, hub upload/download
4. **Federated learning** — Flower FL plugin with full CRDT-aware aggregation
5. **GPU support** — CUDA/MPS tensor merge operations

The layer is already decomposed into well-defined sub-packages:
- `model/strategies/` — 9 strategy modules (base, basic, weighted, evolutionary, calibration, subspace, unlearning)
- `model/targets/` — Target-specific merge logic (HuggingFace models)
- `accelerators/` — 8 standalone accelerator integrations
- `hub/` — HuggingFace Hub integration (2 modules)
- `context/` — Agent context management (5 modules)

This decomposition ensures each sub-package remains focused and independently testable despite the overall layer size.

## D-008: Deterministic Tie-Breaking Everywhere
**Decision**: All merge operations with equal inputs produce deterministic output.
**Rationale**: Non-determinism in merge operations breaks the commutativity guarantee. Using lexicographic string comparison for tie-breaking ensures `merge(A, B) == merge(B, A)` even when timestamps are identical.
**Trade-off**: Lexicographic comparison can be unintuitive (e.g., `"node9" > "node10"`).

---

*Design Decisions v1.0*
