"""Protocol vectors for ORSet, LWWMap and AgentState (WP03-01).

The vectors are the wire form of each type, written by the Python reference. Other editions copy
the files at a pinned commit and must read every ``state`` and re-emit it byte-identically.

This test never writes into ``tests/vectors``. It runs the generator into a temporary directory and
compares every file byte for byte with the committed one, so the test fails when the generator and the
committed files drift apart. To refresh the files after an intended change, run
``python tests/vectors/generate.py`` and commit the result.
"""
import importlib.util
import json
import math
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
VECTOR_DIR = os.path.join(HERE, "vectors")
TYPES = ("orset", "lwwmap", "agentstate")
WIRE_TYPE = {"orset": "or_set", "lwwmap": "lww_map", "agentstate": "agent_state"}


def _load_generator():
    path = os.path.join(VECTOR_DIR, "generate.py")
    spec = importlib.util.spec_from_file_location("protocol_vector_generate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen():
    return _load_generator()


def _read_all(directory):
    return {t: open(os.path.join(directory, f"{t}.json"), "rb").read() for t in TYPES}


@pytest.fixture(scope="module")
def generated(gen, tmp_path_factory):
    """Run the generator into a temporary directory and return the bytes of the three files."""
    out = tmp_path_factory.mktemp("generated_vectors")
    gen.write_all(str(out))
    return _read_all(str(out))


@pytest.fixture(scope="module")
def written():
    """The committed files, as they are on disk. Nothing here writes to them."""
    return _read_all(VECTOR_DIR)


def test_committed_vectors_match_the_generator(generated, written):
    """The committed files are exactly what the generator writes, byte for byte."""
    committed_json = sorted(n for n in os.listdir(VECTOR_DIR) if n.endswith(".json"))
    assert committed_json == sorted(f"{t}.json" for t in TYPES), "unexpected or missing vector files"
    for t in TYPES:
        assert written[t] == generated[t], (
            f"tests/vectors/{t}.json differs from the generator output; "
            "run python tests/vectors/generate.py and commit the result, or revert the edit"
        )


def _walk(node):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_one_file_per_type_is_written(written):
    for t in TYPES:
        assert written[t], f"{t}.json is empty"
        assert written[t].endswith(b"\n")


def test_regeneration_is_byte_identical(gen, generated, tmp_path):
    gen.write_all(str(tmp_path))
    for t in TYPES:
        assert (tmp_path / f"{t}.json").read_bytes() == generated[t], f"{t}.json changed on regeneration"


def test_regeneration_in_a_fresh_process_is_byte_identical(generated, tmp_path):
    """Nothing depends on hash randomisation or on the time of the run."""
    code = (
        "import importlib.util,sys;"
        f"s=importlib.util.spec_from_file_location('g',{os.path.join(VECTOR_DIR, 'generate.py')!r});"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "m.write_all(sys.argv[1])"
    )
    env = dict(os.environ, PYTHONHASHSEED="12345")
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True, env=env)
    for t in TYPES:
        assert (tmp_path / f"{t}.json").read_bytes() == generated[t]


@pytest.mark.parametrize("t", TYPES)
def test_file_layout(written, t):
    doc = json.loads(written[t])
    assert doc["schema"] == "protocol-vectors/1"
    assert doc["type"] == t
    assert doc["wire_type"] == WIRE_TYPE[t]
    assert len(doc["vectors"]) >= 6
    names = [v["name"] for v in doc["vectors"]] + [m["name"] for m in doc["merges"]]
    assert len(names) == len(set(names)), "vector names must be unique"
    assert doc["merges"], "each file carries merge vectors as well as state vectors"


@pytest.mark.parametrize("t", TYPES)
def test_files_are_canonical_json(written, t):
    """Sorted keys, two-space indent, UTF-8, trailing newline: what every edition re-emits."""
    doc = json.loads(written[t])
    assert written[t] == (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


@pytest.mark.parametrize("t", TYPES)
def test_numbers_print_the_same_in_every_language(written, t):
    """No whole-number floats and no exponent forms, which Python, JS and Rust print differently."""
    raw = written[t].decode("utf-8")
    for node in _walk(json.loads(raw)):
        if isinstance(node, float):
            assert not node.is_integer(), f"whole-number float {node!r}"
            assert "e" not in repr(node).lower(), f"exponent form {node!r}"
            assert math.isfinite(node) and 1e-4 <= abs(node) < 1e15, node


@pytest.mark.parametrize("t", TYPES)
def test_every_state_round_trips_through_the_reference(gen, written, t):
    """Reading a vector state and re-emitting it in canonical form gives the same state."""
    ref = gen.REFERENCE[t]
    for v in json.loads(written[t])["vectors"]:
        assert v["state"]["type"] == WIRE_TYPE[t]
        again = gen.canonical(ref.from_dict(json.loads(json.dumps(v["state"]))).to_dict())
        assert again == v["state"], v["name"]


@pytest.mark.parametrize("t", TYPES)
def test_recorded_values_match_the_reference(gen, written, t):
    ref = gen.REFERENCE[t]
    for v in json.loads(written[t])["vectors"]:
        assert gen.observable(t, ref.from_dict(json.loads(json.dumps(v["state"])))) == v["value"], v["name"]


@pytest.mark.parametrize("t", TYPES)
def test_merge_vectors_match_the_reference(gen, written, t):
    ref = gen.REFERENCE[t]
    for m in json.loads(written[t])["merges"]:
        a = ref.from_dict(json.loads(json.dumps(m["a"])))
        b = ref.from_dict(json.loads(json.dumps(m["b"])))
        assert gen.canonical(a.merge(b).to_dict()) == m["result"], m["name"]
        assert gen.canonical(b.merge(a).to_dict()) == m["result"], m["name"] + " (reversed)"


def test_the_orset_vectors_cover_the_cases_other_editions_get_wrong(written):
    doc = json.loads(written["orset"])
    names = {v["name"] for v in doc["vectors"]} | {m["name"] for m in doc["merges"]}
    for needed in (
        "empty",
        "two_tags_for_one_element",
        "removed_element",
        "non_ascii_element",
        "integer_element",
        "stale_replica_does_not_resurrect",
        "concurrent_add_survives_remove",
    ):
        assert needed in names, needed


def test_the_lwwmap_vectors_cover_ties_and_tombstones(written):
    doc = json.loads(written["lwwmap"])
    names = {v["name"] for v in doc["vectors"]} | {m["name"] for m in doc["merges"]}
    for needed in ("empty", "tombstone_hides_register", "newer_register_beats_tombstone",
                   "equal_timestamp_node_id_breaks_tie", "nested_value"):
        assert needed in names, needed


def test_the_agentstate_vectors_cover_every_component(written):
    doc = json.loads(written["agentstate"])
    seen = set()
    for v in doc["vectors"]:
        s = v["state"]
        if s["facts"]["registers"]:
            seen.add("facts")
        if s["tags"]["elements"]:
            seen.add("tags")
        if s["counters"]:
            seen.add("counters")
        if s["messages"]:
            seen.add("messages")
    assert seen == {"facts", "tags", "counters", "messages"}
