# Contributing to crdt-merge

Thank you for your interest in contributing to crdt-merge! We welcome contributions from the community.

## Getting Started

### Prerequisites

- Python 3.9+
- Git

### Setting Up Your Development Environment

```bash
# Clone the repository
git clone https://github.com/mgillr/crdt-merge.git
cd crdt-merge

# Install in development mode with all dependencies
pip install -e ".[dev,all]"

# Verify everything works
pytest tests/ -v
```

## Before You Submit a PR

### 1. Sign the CLA

You must sign the [Contributor License Agreement](CLA.md) before your first PR can be merged. This is a one-time process — simply leave a comment on your first PR stating:

> I have read the CLA document and I hereby sign the CLA.

### 2. Run the Tests

```bash
# Run the full test suite
pytest tests/ -v

# Run CRDT compliance tests specifically (these MUST pass)
pytest tests/test_crdt_compliance.py -v

# Run model merge tests if you touched model code
pytest tests/test_model*.py -v
```

**CRDT compliance must be maintained.** Any PR that breaks commutativity, associativity, or idempotency for any strategy will not be merged.

### 3. Follow the Code Style

- All new Python files must include the BSL-1.1 license header (see any existing file for the template)
- Use lazy imports for optional dependencies (see `_polars_engine.py` for examples)
- Maintain the zero-dependency core — never add required dependencies to `[project.dependencies]`
- Add type hints where practical
- Keep the `to_dict()` / `from_dict()` serialization pattern for new data types

### 4. Add Tests

- Every new feature needs tests
- Every bug fix needs a regression test
- CRDT-related changes need compliance verification tests

## What We're Looking For

We especially welcome contributions in these areas:

- **New merge strategies** — Must pass all 3 CRDT laws via the two-layer architecture
- **Ecosystem integrations** — Connectors for data tools, ML frameworks, agent frameworks
- **Performance improvements** — Benchmarked, not speculative
- **Documentation** — Examples, tutorials, API clarifications
- **Bug reports** — Detailed reproduction steps appreciated

## Reporting Issues

Please use [GitHub Issues](https://github.com/mgillr/crdt-merge/issues) and include:
- Python version and OS
- crdt-merge version (`pip show crdt-merge`)
- Minimal reproduction code
- Expected vs. actual behavior

## License

By contributing, you agree that your contributions will be licensed under the [Business Source License 1.1](LICENSE), subject to the terms of the [CLA](CLA.md).

## Questions?

- Open a [GitHub Discussion](https://github.com/mgillr/crdt-merge/discussions) (if enabled)
- Email: data@optitransfer.ch

---

*Thank you for helping make crdt-merge better. Every contribution matters.*
