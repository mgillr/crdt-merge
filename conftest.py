# Root conftest.py — project-wide pytest configuration.
#
# Benchmark helpers in benchmarks/a100_v080/test_crdt_laws_granular.py are
# NOT pytest tests; they return PropertyResult values and are invoked by
# run_benchmark.py.  Exclude them from auto-discovery when pytest is run
# without an explicit path (belt-and-suspenders alongside testpaths config).
collect_ignore_glob = ["benchmarks/*/test_crdt_laws_granular.py"]
