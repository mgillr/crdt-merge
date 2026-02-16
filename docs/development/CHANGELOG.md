# Changelog

## v0.9.2 (Current)

### Added
- EU AI Act compliance reporting (`EUAIActReport`)
- 8 accelerator integrations (DuckDB, dbt, Polars, Flight, Airbyte, DuckLake, SQLite, Streamlit)
- Flower federated learning plugin
- Context management package (`context/`)
- MergeQL DSL for SQL-like merge queries
- Conflict visualization (`viz.py`)

### Changed
- Model strategies expanded to 26+
- Observability module expanded with DriftDetector, HealthCheck
- Wire protocol version bumped to v1

### Fixed
- VectorClock zero-counter normalization
- MergeSchema serialization edge cases

## v0.9.1

### Added
- Enterprise wrappers (audit, encryption, RBAC, observability, unmerge)
- GDPR forget functionality
- Model merge pipeline

## v0.9.0

### Added
- Initial model merge support
- Agentic AI state management
- HuggingFace Hub integration

## v0.8.x

### Added
- Streaming merge engines
- Arrow and Parquet engines
- Gossip and Merkle sync protocols

## v0.7.x

### Added
- Core CRDT primitives
- Merge strategies and MergeSchema
- DataFrame merge engine
