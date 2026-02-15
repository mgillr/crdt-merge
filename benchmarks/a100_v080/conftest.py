# These benchmark functions (test_commutativity, etc.) are not pytest tests —
# they return PropertyResult values and are called by the run_benchmark.py
# script.  Prevent pytest from collecting them.
collect_ignore_glob = ["test_crdt_laws_granular.py"]
