# All Constants and Enums

## Enums

### crdt_merge.clocks.Ordering
```python
class Ordering(Enum):
    BEFORE = "before"
    AFTER = "after"
    CONCURRENT = "concurrent"
    EQUAL = "equal"
```

## Constants

### Version
```python
crdt_merge.__version__ = "0.9.2"
```

### Wire Protocol
```python
WIRE_MAGIC = 0x43524454    # "CRDT" in ASCII
WIRE_VERSION = 0x0001      # Protocol version 1
```

### CRDT Type IDs (Wire Protocol)
```python
TYPE_GCOUNTER = 0x01
TYPE_PNCOUNTER = 0x02
TYPE_LWW_REGISTER = 0x03
TYPE_OR_SET = 0x04
TYPE_LWW_MAP = 0x05
TYPE_VECTOR_CLOCK = 0x06
TYPE_MERGE_SCHEMA = 0x10
TYPE_DATAFRAME_STATE = 0x20
```

### Default Values
```python
DEFAULT_STRATEGY = LWW()                    # Default merge strategy
DEFAULT_SEPARATOR = ","                      # Default UnionSet separator
DEFAULT_CONCAT_SEPARATOR = " | "             # Default Concat separator
DEFAULT_HLL_PRECISION = 14                   # HyperLogLog precision
DEFAULT_BLOOM_CAPACITY = 10000               # Bloom filter capacity
DEFAULT_BLOOM_ERROR_RATE = 0.01              # Bloom filter error rate
DEFAULT_CMS_WIDTH = 1000                     # Count-Min Sketch width
DEFAULT_CMS_DEPTH = 5                        # Count-Min Sketch depth
DEFAULT_MINHASH_PERMS = 128                  # MinHash permutations
DEFAULT_MINHASH_THRESHOLD = 0.5              # MinHash similarity threshold
DEFAULT_PROMETHEUS_PORT = 9090               # Prometheus exporter port
DEFAULT_MODEL_STRATEGY = "linear"            # Default model merge strategy
DEFAULT_GPU_DTYPE = "float16"                # Default GPU dtype
DEFAULT_FEDERATED_STRATEGY = "fedavg"        # Default FL strategy
```
