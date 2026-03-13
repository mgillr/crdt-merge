# Troubleshooting Guide

## Common Issues

### Q: Merge results are not deterministic
**A**: Ensure you're using the same `timestamp_col` and `node_a`/`node_b` values. CRDT merges are deterministic given the same inputs.

### Q: Custom strategy lost after serialization
**A**: This is a known limitation (LAY1-003). Custom strategies using Python functions cannot be serialized. They fall back to LWW after `to_dict()`/`from_dict()`. Workaround: re-create the schema with Custom strategies after deserialization.

### Q: Timestamps seem wrong — old data winning
**A**: Check `_safe_parse_ts()` behavior. Invalid timestamps silently become `0.0` (LAY1-005). Verify your timestamp format is one of: int, float, numeric string, ISO-8601.

### Q: "node9" beats "node10" in tie-breaking
**A**: Tie-breaking uses lexicographic string comparison (LAY1-001). `"node9" > "node10"` because `"9" > "1"` character-by-character. Use zero-padded names: `"node09"`, `"node10"`.

### Q: ORSet remove doesn't work as expected
**A**: ORSet uses add-wins semantics. A concurrent add and remove of the same element will result in the element being present. This is by design — it's the CRDT guarantee.

### Q: Merge is slow on large DataFrames
**A**: See [Performance Tuning](performance-tuning.md). Consider:
1. Using Polars instead of pandas
2. Using `arrow_merge()` for columnar data
3. Using `parallel_merge()` for multi-core
4. Using `merge_sorted_stream()` for pre-sorted data

### Q: Import error for optional dependency
**A**: Many modules have optional dependencies. Install the right extra:
```bash
pip install crdt-merge[arrow]   # pyarrow
pip install crdt-merge[model]   # torch
pip install crdt-merge[all]     # everything
```
