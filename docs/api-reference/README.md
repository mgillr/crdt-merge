# API Reference — Index

Complete API documentation for crdt-merge v0.9.2, organized by architectural layer.

## Layers

| Layer | Directory | Modules | LOC |
|-------|-----------|---------|-----|
| [Layer 1: Core CRDT](layer1-core/) | `layer1-core/` | 7 | 2,614 |
| [Layer 2: Merge Engines](layer2-engines/) | `layer2-engines/` | 8 | 3,984 |
| [Layer 3: Sync & Transport](layer3-transport/) | `layer3-transport/` | 5 | 2,626 |
| [Layer 4: AI / Model / Agent](layer4-ai/) | `layer4-ai/` | 16+ | 18,410 |
| [Layer 5: Enterprise](layer5-enterprise/) | `layer5-enterprise/` | 5 | 3,323 |
| [Layer 6: Compliance](layer6-compliance/) | `layer6-compliance/` | 1 | 932 |
| [Accelerators](accelerators/) | `accelerators/` | 8 | 4,465 |
| [CLI](cli/) | `cli/` | 1 | 548 |

## Conventions

- **Module path**: Full Python import path (e.g., `crdt_merge.core`)
- **Signatures**: Include all parameters with types and defaults
- **CRDT compliance**: Noted where applicable (commutative, associative, idempotent)
- **Known issues**: Referenced by ID from `gap-analysis/BUGS_AND_ISSUES.md`
