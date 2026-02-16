# Contributing to crdt-merge

## Development Setup

```bash
git clone https://github.com/mgillr/crdt-merge.git
cd crdt-merge
pip install -e ".[dev,all]"
pre-commit install
```

## Running Tests

```bash
pytest tests/                     # All tests
pytest tests/test_core.py         # Specific module
pytest tests/ -k "test_gcounter"  # Specific test
pytest tests/ --pbt               # Property-based tests
```

## Code Style

- Python 3.8+ compatible
- Type hints required for all public APIs
- Docstrings required for all public classes and functions
- `pre-commit` hooks enforce formatting

## Pull Request Process

1. Fork and create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation
5. Submit PR with description of changes

## Architecture Guidelines

- Layer boundaries must be respected (no upward imports)
- New modules should declare their layer in the module docstring
- Zero-dependency requirement for Layer 1 must be maintained
