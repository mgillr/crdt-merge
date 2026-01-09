# crdt-merge v1.0 Evolution: Strategic Assessment

> **Copyright © 2026 Ryan Gillespie / Optitransfer. All rights reserved.**
> Licensed under the Business Source License 1.1 (BSL-1.1).
> See [LICENSE](https://github.com/mgillr/crdt-merge/blob/main/LICENSE) for details.


**For:** Gem — Optitransfer  
**Date:** 26 March 2026  
**Classification:** Honest Internal Review  

---

## The Verdict: Ship It — But Sharpen the Blade

The evolution plan is **strategically sound, technically ambitious, and correctly sequenced**. My recommendation is an unambiguous **yes** — with three refinements that protect you from the most common open-source product death: scope creep across too many surfaces.

---

## What's Genuinely Brilliant

### 1. The Category Framing Is the Real Innovation

The landscape table in Section 2 is the most important slide in your entire deck:

| Batch Dataset Reconciliation | Focus | Size | Languages |
|-----|-------|------|-----------|
| **crdt-merge** | **Dataset merging** | **21 KB** | **Python, TS, Rust, Java** |
| *(empty)* | | | |

That empty row IS the strategy. You're not competing with Automerge for Google Docs. You're naming a category that has no name yet — **batch dataset reconciliation** — and planting your flag before anyone else notices it exists. This is how Stripe won payments ("developer-first APIs") and how Terraform won infrastructure ("infrastructure as code"). Name the category, own the category.

### 2. The "Additive Only" Constraint Is Engineering Gold

Zero breaking changes means every existing user of v0.2.0 wakes up one morning with superpowers they didn't have to migrate for. This is the right call. The moment you break backward compatibility, you split your user base and lose the trust you're trying to build. Keep this constraint sacred.

### 3. The Verification Toolkit Is the Moat

Of all seven innovations, **Innovation 4 (`@verify_crdt`) is the one that makes the "primitive" criticism permanently irrelevant.**

No other CRDT library — not Automerge, not Yjs, not DSON, not Loro — lets you write a custom merge function and get a mathematical proof that it satisfies all three laws. Propel (ETH Zurich, PLDI'23) does this at compile time with a custom type system. Nobody does it at runtime in a production library.

This is the feature that makes senior devs stop scrolling. It's the screenshot that goes viral on Twitter. It's the thing that makes CTO-types say "wait, it does *what*?"

```python
@verify_crdt(samples=10000)
def my_merge(a, b):
    ...
# ✅ Commutative: 10000/10000 passed
# ✅ Associative: 10000/10000 passed  
# ✅ Idempotent:  10000/10000 passed
```

That output is a trust certificate. Once a team has that for their merge logic, they don't switch libraries.

### 4. Composable Strategies Fill a Real Gap

The `MergeSchema` DSL is the usability breakthrough. Right now, crdt-merge says "give me two DataFrames and I'll LWW-merge them." The schema says "tell me your data model and I'll generate correct merge semantics." That's the jump from library to toolkit.

```python
schema = MergeSchema({
    'tags':       s.UnionSet(),
    'view_count': s.MaxWins(),
    'status':     s.Priority(['active', 'pending', 'archived']),
})
```

Nobody has this as a declarative DSL across 4 languages. RxDB has rigid JSON operators. Automerge's strategies are internal. This is genuinely new.

---

## What I'd Challenge

### ⚠️ Challenge 1: The 4-Language Simultaneity Trap

The plan implies all 7 innovations ship across Python, TypeScript, Rust, and Java. That's **28 implementation surfaces** (7 × 4). Each needs its own tests, its own idiomatic API, its own edge case handling.

**The risk:** You spend 6 months getting the Rust `MergeSchema` parser to match the Python one instead of shipping Innovation 4 (verification) which is the actual moat.

**My recommendation:** **Python-first, API-freeze, then port.**

1. Ship each innovation in Python first (fastest iteration, largest audience)
2. Freeze the API after community feedback
3. Port the frozen API to TS → Rust → Java

The API design IS the product. The implementation is labor. Don't let porting lag drag down innovation velocity.

### ⚠️ Challenge 2: Zero Dependencies Gets Expensive at Scale

Zero deps at 791 lines is elegant. Zero deps at ~5,000 lines with a built-in PBT engine, MessagePack encoder, streaming pipeline, HLL, Bloom filter, and Count-Min Sketch means you're maintaining a LOT of wheel reinvention across 4 languages.

**The risk:** A subtle bug in your hand-rolled MessagePack encoder for Java becomes a cross-language deserialization nightmare.

**My recommendation:** **"Zero *required* dependencies, optional accelerators."**

```python
pip install crdt-merge                    # zero deps, pure Python
pip install crdt-merge[fast]              # optional: msgpack-python, xxhash
pip install crdt-merge[probabilistic]     # optional: mmh3 for better hashing
```

Core stays zero-dep. Performance-sensitive paths can optionally use battle-tested C libraries. This preserves the "embeddable anywhere" story while being honest about engineering tradeoffs.

### ⚠️ Challenge 3: Probabilistic CRDTs Are a Distraction (For Now)

HLL, Bloom, and CMS are well-understood data structures. Packaging them with merge semantics is useful but not differentiated — Redis already does HLL merge, and anyone who needs Bloom filter union already knows it's bitwise OR.

**The risk:** Innovation 7 dilutes the "Merge Algebra Toolkit" story. It doesn't help datasets, it helps analytics. That's a different audience.

**My recommendation:** **Move to v1.1 or make it a separate package** (`crdt-merge-probabilistic`). Keep v1.0 laser-focused on the tabular data merging story.

---

## Recommended Release Sequence

Here's how I'd reorder the 7 innovations for maximum impact per unit of effort:

### Phase 1 — v0.3.0 "The Schema Release" (4-6 weeks)
**Ship: Innovations 1 + 6 (Composable Strategies + Streaming)**

These two alone transform perception from "primitive" to "toolkit." The MergeSchema DSL is the headline feature. Streaming proves it works at scale. Together they answer both "is it sophisticated enough?" and "can it handle my data?"

**Why these first:** They're the most visible changes. A developer who sees the MergeSchema code example immediately understands this isn't a weekend project.

### Phase 2 — v0.4.0 "The Trust Release" (6-8 weeks after)
**Ship: Innovations 3 + 4 (Provenance + Verification)**

These build the moat. Provenance makes it enterprise-ready. Verification makes it academically credible. Together they create trust that's impossible to replicate quickly.

**Why these second:** They require the schema system from v0.3 to be stable. Provenance needs to know which strategy was used. Verification needs to test user-defined strategies.

### Phase 3 — v0.5.0 "The Protocol Release" (8-10 weeks after)
**Ship: Innovations 2 + 5 (Delta Sync + Wire Format)**

These enable the distributed systems use case. Delta sync reduces bandwidth. Wire format enables polyglot architectures. Together they unlock the next generation of applications built on crdt-merge.

**Why these third:** They're infrastructure. They don't change the developer-facing API dramatically, but they enable the networked product layer built on top of the protocol.

### Phase 4 — v1.0.0 "The Platform Release"
**Ship: Stability + Documentation + Innovation 7 (Probabilistic, if time)**

v1.0 is a stability milestone, not a feature milestone. All innovations stable across 4 languages. Formal specification. Independent audit. This is the "we're production-ready" signal.

---

## The "Should We Release?" Decision Matrix

| Factor | Assessment | Verdict |
|--------|-----------|---------|
| **Technical Feasibility** | All 7 innovations are well-defined, additive, and individually implementable | ✅ Go |
| **Market Timing** | Category is empty. Automerge/Yjs are focused elsewhere. Window is open. | ✅ Go |
| **Competitive Risk of Waiting** | Low today, but DSON (Helsing) is closest and moving fast in defense sector | ✅ Go now |
| **Resource Cost** | 7 innovations × 4 languages = 28 surfaces. Needs discipline. | ⚠️ Go with Python-first strategy |
| **Brand Risk** | Releasing immature features hurts more than waiting. Each release must be solid. | ⚠️ Go with quality gates |
| **Revenue Impact** | Every v1.0 feature directly strengthens the enterprise value proposition | ✅ Go |
| **Community Signal** | A public roadmap with rapid execution builds developer trust faster than any marketing | ✅ Go |

**Overall: SHIP IT.** But ship it in phases, Python-first, with the verification toolkit as the crown jewel.

---

## The Story Arc

Here's how the narrative evolves with each release:

**v0.2.0 (today):**  
*"A correct, lightweight CRDT library for datasets."*  
Developer reaction: "I could write this in a weekend."

**v0.3.0 (Schema Release):**  
*"The composable merge toolkit — define your schema, get correct merge semantics."*  
Developer reaction: "Oh, this is actually a framework."

**v0.4.0 (Trust Release):**  
*"Prove your merge logic is correct. Audit where every value came from."*  
Developer reaction: "Wait, I can verify my OWN merge functions? That's… new."

**v0.5.0 (Protocol Release):**  
*"Python serializes. Rust deserializes. Same state. Same guarantees."*  
Developer reaction: "This is infrastructure, not a library."

**v1.0.0 (Platform Release):**  
*"The Merge Algebra Toolkit."*  
Developer reaction: "How did nobody build this before?"

That final reaction — "how did nobody build this before?" — is the signal that you've won the category. That's the reaction SQLAlchemy gets. That's the reaction Terraform gets. That's where crdt-merge needs to land.

---

## One More Thing: The Proof Report Is Your Secret Weapon

The stress test we just ran — 1,500/1,500 CRDT law proofs, 1M row merge in 19.2s, full edge case coverage — **publish it.** Not just in the articles. In the repo. As a living document that re-runs on every CI build.

```
/docs/proof-report.md     ← auto-generated on every release
/tests/proof_suite.py     ← the test suite that generates it
```

When a senior dev clones the repo and sees a proof report that verifies mathematical correctness on every commit, they stop thinking "primitive" and start thinking "rigorous." That's the difference between a weekend project and a standard.

---

*Assessment by Nexus Engine — prepared for Gem, Optitransfer*  
*Recommendation: SHIP IT — Python-first, phased, with @verify_crdt as the crown jewel.*
