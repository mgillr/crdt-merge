# HF Dataset Feature Test Results

**Date**: 2026-03-31
**Datasets**: IMDB 5K (stanfordnlp/imdb), AG News 5K (fancyzhx/ag_news)
**crdt-merge version**: 0.9.2
**Backend**: numpy (pure-python fallback)

## Summary

| Scenario | Tests | PASS | FAIL |
|----------|-------|------|------|
| IMDB embeddings (500×64) | 26 | 26 | 0 |
| AG News embeddings (500×64) | 26 | 26 | 0 |
| IMDB label predictions (500×1) | 26 | 26 | 0 |
| AG News label predictions (500×1) | 26 | 26 | 0 |
| **Total** | **104** | **104** | **0** |

## Test Methodology

1. Loaded IMDB 5K and AG News 5K from HuggingFace
2. Created synthetic embeddings (dim=64) simulating 3 model outputs on same data
3. Created label prediction variants from 3 "models" with noise injection
4. Tested all 26 merge strategies across all scenarios
5. Validated output shapes, checked for NaN/Inf values

## Performance Notes

- Evolutionary strategies (evolutionary_merge, genetic_merge) take ~24s on 500×64 embeddings
- Most deterministic strategies complete in <100ms even on 500×64 tensors
- Label prediction merges (500×1) are sub-millisecond for all non-evolutionary strategies
