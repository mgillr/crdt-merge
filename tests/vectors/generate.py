"""Writes the protocol vector files for ORSet, LWWMap and AgentState.

    python tests/vectors/generate.py [output-dir]

The input states are written by hand in wire form (fixed tags, fixed timestamps), loaded by the
Python reference, and written back out. ``value`` and every merge ``result`` are computed by the
reference, so the files record what the reference does, never what someone expects it to do.

Canonical form, which every edition must re-emit byte for byte:
  * UTF-8 JSON, keys sorted, two-space indent, a trailing newline;
  * the tag lists of an or_set (``elements`` values and ``tombstones``) sorted;
  * numbers that print the same in Python, JavaScript and Rust: whole numbers are integers, and
    no float is whole or needs an exponent. (Python prints 2.0 where JavaScript prints 2.)
"""
import json
import os
import sys

from crdt_merge.agentic import AgentState
from crdt_merge.core import LWWMap, ORSet

SCHEMA = "protocol-vectors/1"
REFERENCE = {"orset": ORSet, "lwwmap": LWWMap, "agentstate": AgentState}
WIRE_TYPE = {"orset": "or_set", "lwwmap": "lww_map", "agentstate": "agent_state"}

T1, T2, T3 = "0000000000a1", "0000000000b2", "0000000000c3"
TS0 = 1700000000.5


# ---------------------------------------------------------------------------------------
# Canonical form and the reference's observable value
# ---------------------------------------------------------------------------------------

def canonical(node):
    """Normalise a wire dict: sort the tag lists of every or_set."""
    if isinstance(node, dict):
        out = {k: canonical(v) for k, v in node.items()}
        if node.get("type") == "or_set":
            out["elements"] = {k: sorted(v) for k, v in out.get("elements", {}).items()}
            if "tombstones" in out:
                out["tombstones"] = sorted(out["tombstones"])
        return out
    if isinstance(node, list):
        return [canonical(v) for v in node]
    return node


def observable(kind, state):
    """What a reader of the state sees, in JSON-friendly form."""
    if kind == "orset":
        return sorted(str(e) for e in state.value)
    if kind == "lwwmap":
        return {k: state.value[k] for k in sorted(state.value)}
    facts = {k: f.to_dict() for k, f in sorted(state.list_facts().items())}
    return {
        "facts": facts,
        "tags": sorted(state.tags),
        "counters": {k: state.counter_value(k) for k in sorted(state._counters)},
        "messages": len(state.messages),
    }


def dumps(doc):
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _load(kind, wire):
    return REFERENCE[kind].from_dict(json.loads(json.dumps(wire)))


def _state_vector(kind, name, description, wire):
    state = _load(kind, wire)
    return {
        "name": name,
        "description": description,
        "state": canonical(state.to_dict()),
        "value": observable(kind, state),
    }


def _merge_vector(kind, name, description, a, b):
    sa, sb = _load(kind, a), _load(kind, b)
    return {
        "name": name,
        "description": description,
        "a": canonical(sa.to_dict()),
        "b": canonical(sb.to_dict()),
        "result": canonical(sa.merge(sb).to_dict()),
    }


# ---------------------------------------------------------------------------------------
# ORSet
# ---------------------------------------------------------------------------------------

def orset(elements, tombstones=None, element_types=None):
    d = {"type": "or_set", "elements": elements}
    if element_types:
        d["element_types"] = element_types
    if tombstones:
        d["tombstones"] = list(tombstones)
    return d


def orset_doc():
    vectors = [
        _state_vector("orset", "empty", "no elements", orset({})),
        _state_vector("orset", "single_element", "one element with one tag", orset({"x": [T1]})),
        _state_vector("orset", "two_tags_for_one_element", "concurrent adds of one element",
                      orset({"x": [T2, T1]})),
        _state_vector("orset", "removed_element", "the only tag was removed, so nothing is live",
                      orset({"x": []}, tombstones=[T1])),
        _state_vector("orset", "non_ascii_element", "element names are UTF-8",
                      orset({"na\u00efve-\u043a\u043b\u044e\u0447-\u65e5\u672c": [T1]})),
        _state_vector("orset", "integer_element", "a non-string element records its type",
                      orset({"7": [T1]}, element_types={"7": "int"})),
        _state_vector("orset", "several_elements", "live and removed elements together",
                      orset({"a": [T1], "b": [T2, T3], "c": []}, tombstones=[T1 + "00"])),
    ]
    merges = [
        _merge_vector("orset", "stale_replica_does_not_resurrect",
                      "a replica that still holds a removed tag cannot bring the element back",
                      orset({"x": [T1]}), orset({"x": []}, tombstones=[T1])),
        _merge_vector("orset", "concurrent_add_survives_remove",
                      "a remove only removes the tags its replica had seen",
                      orset({"x": []}, tombstones=[T1]), orset({"x": [T1, T2]})),
        _merge_vector("orset", "disjoint_elements_union", "elements from both sides stay",
                      orset({"x": [T1]}), orset({"y": [T2]})),
        _merge_vector("orset", "identical_states", "merging a state with itself changes nothing",
                      orset({"x": [T1]}), orset({"x": [T1]})),
    ]
    return {"vectors": vectors, "merges": merges}


# ---------------------------------------------------------------------------------------
# LWWMap
# ---------------------------------------------------------------------------------------

def reg(value, ts, node):
    return {"type": "lww_register", "value": value, "timestamp": ts, "node_id": node}


def lwwmap(registers, tombstones=None):
    return {"type": "lww_map", "registers": registers, "tombstones": tombstones or {}}


def lwwmap_doc():
    nested = {"list": [1, 2, {"x": None}], "flag": True, "text": "caf\u00e9", "ratio": 0.25}
    vectors = [
        _state_vector("lwwmap", "empty", "no registers", lwwmap({})),
        _state_vector("lwwmap", "single_register", "one live key",
                      lwwmap({"a": reg("one", TS0 + 1, "n1")})),
        _state_vector("lwwmap", "nested_value", "values are arbitrary JSON",
                      lwwmap({"a": reg(nested, TS0 + 2, "n1")})),
        _state_vector("lwwmap", "non_ascii_key", "keys are UTF-8",
                      lwwmap({"\u00fcber-\u65e5\u672c": reg(1, TS0 + 3, "n1")})),
        _state_vector("lwwmap", "tombstone_hides_register", "a newer tombstone hides the register",
                      lwwmap({"a": reg("old", TS0 + 4, "n1")}, {"a": TS0 + 5})),
        _state_vector("lwwmap", "equal_timestamp_tombstone_hides_register",
                      "a tombstone as new as the register hides it",
                      lwwmap({"a": reg("old", TS0 + 6, "n1")}, {"a": TS0 + 6})),
        _state_vector("lwwmap", "newer_register_beats_tombstone", "a write after the delete is live",
                      lwwmap({"a": reg("new", TS0 + 8, "n1")}, {"a": TS0 + 7})),
    ]
    merges = [
        _merge_vector("lwwmap", "later_write_wins", "the higher timestamp wins",
                      lwwmap({"a": reg("early", TS0 + 1, "n1")}),
                      lwwmap({"a": reg("late", TS0 + 2, "n2")})),
        _merge_vector("lwwmap", "equal_timestamp_node_id_breaks_tie",
                      "equal timestamps are settled by the higher node id, in either order",
                      lwwmap({"a": reg("from-n1", TS0 + 3, "n1")}),
                      lwwmap({"a": reg("from-n2", TS0 + 3, "n2")})),
        _merge_vector("lwwmap", "delete_beats_older_register", "a delete after the write hides it",
                      lwwmap({"a": reg("kept?", TS0 + 4, "n1")}),
                      lwwmap({}, {"a": TS0 + 5})),
        _merge_vector("lwwmap", "disjoint_keys_union", "keys from both sides stay",
                      lwwmap({"a": reg(1, TS0 + 1, "n1")}),
                      lwwmap({"b": reg(2, TS0 + 1, "n2")})),
    ]
    return {"vectors": vectors, "merges": merges}


# ---------------------------------------------------------------------------------------
# AgentState
# ---------------------------------------------------------------------------------------

def fact(value, ts, agent, confidence=0.75):
    return {"value": value, "confidence": confidence, "source_agent": agent, "timestamp": ts}


def facts_map(**facts):
    return lwwmap({k: reg(f, f["timestamp"], f["source_agent"]) for k, f in facts.items()})


def counter(pos, neg=None):
    return {
        "type": "pn_counter",
        "pos": {"type": "g_counter", "counts": pos},
        "neg": {"type": "g_counter", "counts": neg or {}},
    }


def message(text, ts, agent):
    return {"content": text, "role": "agent", "agent_id": agent, "timestamp": ts, "metadata": {}}


def agent(agent_id, facts=None, tags=None, counters=None, messages=None, created=TS0):
    return {
        "type": "agent_state",
        "agent_id": agent_id,
        "facts": facts or lwwmap({}),
        "tags": tags or orset({}),
        "counters": counters or {},
        "messages": messages or [],
        "created_at": created,
    }


def agentstate_doc():
    a, b = "agent-a", "agent-b"
    one_fact = facts_map(color=fact("blue", TS0 + 10, a))
    vectors = [
        _state_vector("agentstate", "empty", "a new state", agent(a)),
        _state_vector("agentstate", "one_fact", "a fact carries value, confidence, source and time",
                      agent(a, facts=one_fact)),
        _state_vector("agentstate", "tags", "tags are an observed-remove set",
                      agent(a, tags=orset({"urgent": [T1], "seen": [T2, T3]}))),
        _state_vector("agentstate", "counters", "a counter has a positive and a negative part",
                      agent(a, counters={"visits": counter({a: 3, b: 2}, {a: 1})})),
        _state_vector("agentstate", "messages", "an append-only message log",
                      agent(a, messages=[message("hello", TS0 + 20, a),
                                         message("na\u00efve \u65e5\u672c", TS0 + 21, a)])),
        _state_vector("agentstate", "all_components", "facts, tags, counters and messages together",
                      agent(a, facts=facts_map(color=fact({"rgb": [0, 0, 255]}, TS0 + 10, a, 0.5)),
                            tags=orset({"urgent": [T1]}),
                            counters={"visits": counter({a: 1})},
                            messages=[message("hello", TS0 + 20, a)])),
    ]
    merges = [
        _merge_vector("agentstate", "later_fact_wins", "the newer fact wins, whichever side holds it",
                      agent(a, facts=facts_map(color=fact("blue", TS0 + 10, a))),
                      agent(b, facts=facts_map(color=fact("green", TS0 + 11, b, 0.5)))),
        _merge_vector("agentstate", "counters_take_the_larger_count_per_node",
                      "counts are merged per node by maximum, so a repeated delivery adds nothing",
                      agent(a, counters={"visits": counter({a: 3, b: 1})}),
                      agent(b, counters={"visits": counter({a: 2, b: 4}, {b: 1})})),
        _merge_vector("agentstate", "tags_union_and_removal", "an observed removal wins over the tag it saw",
                      agent(a, tags=orset({"urgent": [T1]})),
                      agent(b, tags=orset({"urgent": []}, tombstones=[T1]))),
        _merge_vector("agentstate", "identity_and_creation_time",
                      "the merged agent id is the sorted union and created_at is the earlier time",
                      agent(a, created=TS0 + 100), agent(b, created=TS0 + 50)),
        _merge_vector("agentstate", "messages_are_deduplicated",
                      "the same message on both sides appears once",
                      agent(a, messages=[message("hello", TS0 + 20, a)]),
                      agent(b, messages=[message("hello", TS0 + 20, a), message("reply", TS0 + 22, b)])),
    ]
    return {"vectors": vectors, "merges": merges}


# ---------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------

DOCS = {"orset": orset_doc, "lwwmap": lwwmap_doc, "agentstate": agentstate_doc}


def build(kind):
    body = DOCS[kind]()
    return {
        "schema": SCHEMA,
        "type": kind,
        "wire_type": WIRE_TYPE[kind],
        "canonical_form": "UTF-8 JSON, keys sorted, two-space indent, trailing newline, or_set tag lists sorted",
        "vectors": body["vectors"],
        "merges": body["merges"],
    }


def write_all(directory):
    os.makedirs(directory, exist_ok=True)
    for kind in DOCS:
        with open(os.path.join(directory, f"{kind}.json"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dumps(build(kind)))


if __name__ == "__main__":
    write_all(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
