# Reverse Reachability Entropy Analysis (RREA)

> **Team 4 Method** — Novel technique combining network flow analysis with information theory  
> **Version:** 2.0 (Hardened — engine mandate, phase enforcement added)  
> **Engine location:** `research/team4_rrea_engine.py` | Persistent: `/agent/home/team4_rrea_engine.py`

---

## ⛔ CRITICAL: ENGINE MANDATE

```
WRONG: Writing a new ~100-line "simplified RREA" inline script
WRONG: Implementing only Phases 1-6 and skipping Phases 7-8
WRONG: Using basic Shannon entropy without Ping Entropy

RIGHT: Running the actual engine:
   python3 research/team4_rrea_engine.py /path/to/source /path/to/docs

RIGHT: All 8 phases complete with non-empty outputs
RIGHT: Both Shannon entropy AND Ping entropy computed
```

### Why You Cannot Write a Simplified Version

The `team4_rrea_engine.py` is 556 lines because it handles:
- **Indirect calls:** `getattr(obj, name)()`, callbacks, `map(func, ...)`
- **Super calls:** `super().method()` resolution through MRO
- **Decorator tracking:** `@property`, `@classmethod`, `@staticmethod` edge generation
- **Ping Entropy:** Novel PageRank-style attenuation that produces different priority rankings than basic Shannon entropy
- **Class hierarchy edges:** Inheritance creates implicit call paths
- **Attribute access edges:** `self.foo` and `module.bar` tracked as dependencies
- **Propagation path tracing:** Phase 6 with depth limits and cycle detection

An ad-hoc script will miss most of these, producing:
- False dead-code counts (can't trace `self.method()` calls)
- Missing shadow dependencies (no attribute access tracking)
- No Ping Entropy (novel method only in the engine)
- No propagation path validation (Phase 7 skipped)

### Validation Gate
```
RREA completion requires:
  - All 8 phases executed
  - Phase 7 report non-empty (propagation issues)
  - Phase 8 report non-empty (doc cross-validation)
  - Both Shannon AND Ping entropy computed
  - Full JSON report saved to /tmp/team4_rrea_report.json

If Phase 7 report is empty → Phase 7 was likely skipped, re-run
If Phase 8 report is empty → Phase 8 was likely skipped, re-run
If only Shannon entropy present → Ping entropy was skipped, use the actual engine
```

---

## 1. Theory

Most code analysis works **forward** — "what does this function call?" RREA works **backwards** — "for every public API endpoint a user can call, what is the complete tree of internal code that MUST execute?"

The innovation is combining **reverse reachability** (graph theory) with **Shannon entropy** (information theory) and **Ping entropy** (novel PageRank-inspired metric) to measure the **criticality** of every symbol in the codebase.

### Core Insight

If a symbol `S` sits on 47 of 50 possible execution paths from public endpoints, it has **high path entropy** and is a critical chokepoint. If `S` sits on 0 paths, it's **dead code**. If `S` is only reachable through one specific argument pattern, it's a **shadow dependency**.

This produces a **documentation priority map** — symbols ranked by how much user-facing behavior they affect.

## 2. What This Catches That Teams 1–3 Miss

| Finding Type | AST | Regex | GDEPA | RREA |
|-------------|-----|-------|-------|------|
| Dead code (unreachable from API) | | | Partial | |
| Critical chokepoints | | | | |
| Shadow dependencies | | | | |
| Documentation priority order | | | | |
| Missing error handling paths | | | | |
| Argument-conditional code paths | | | | |
| Propagation completeness | | | | |

## 3. Algorithm — ALL 8 PHASES MANDATORY

### Phase 1: Identify Public API Surface
```
public_endpoints = []
For each module M in the package:
  If M has __all__:
    public_endpoints += M.__all__
  Else:
    public_endpoints += [name for name in dir(M) if not name.startswith('_')]
  Also include: CLI entry points, plugin hooks, registered factories
```

### Phase 2: Build Call Graph (Forward)
```
call_graph = DirectedGraph()
For each function/method F in codebase:
  Parse F's body for:
    - Direct calls: foo(), self.bar(), Module.baz()
    - Indirect calls: getattr(obj, name)(), callbacks, map(func, ...)
    - Super calls: super().method()
    - Conditional calls: if isinstance(x, T): x.method()
  Add edge: F → each called symbol
```

### Phase 3: Reverse the Graph
```
reverse_graph = call_graph.reverse()
# Now edges go FROM callee TO caller
# Traversal from any node finds all its callers, recursively up to public API
```

### Phase 4: Compute Reachability Sets
```
For each public endpoint E:
  reachable[E] = BFS/DFS from E through call_graph
  # Every symbol in reachable[E] is on E's execution path

For each internal symbol S:
  reached_by[S] = {E for E in public_endpoints if S in reachable[E]}
  reachability_count[S] = len(reached_by[S])
```

### Phase 5: Compute Shannon Entropy + Ping Entropy
```
Shannon Entropy (standard):
  For each internal symbol S:
    p = reachability_count[S] / total_public_endpoints
    if p == 0: entropy[S] = 0 (DEAD CODE)
    elif p == 1: entropy[S] = 0 (UNIVERSAL — used by everything)
    else: entropy[S] = -p * log2(p) - (1-p) * log2(1-p)

Ping Entropy (NOVEL — in engine only):
  Simulate "pings" from every endpoint through the graph with attenuation (damping=0.85)
  Each node accumulates ping counts from each source endpoint
  Compute entropy of the ping distribution per node
  This accounts for fan-out, fan-in, and path length — unlike basic Shannon
  Analogous to PageRank but purpose-built for code documentation priority
```

### Phase 6: Classify Symbols
```
TIERS:
  CRITICAL    = reachability >= 80% of endpoints → must-document chokepoint
  IMPORTANT   = reachability 40-79% → high-priority documentation
  SUPPORTING  = reachability 10-39% → standard documentation  
  SPECIALIZED = reachability 1-9% → niche documentation
  DEAD        = reachability 0% → flag for removal, skip documentation
  SHADOW      = only reachable through specific arg patterns → document the conditions
```

### Phase 7: Propagation Path Validation COMMONLY SKIPPED — DO NOT SKIP
```
For each public endpoint E:
  trace full propagation path: E → f1 → f2 → ... → leaf
  At each node, verify:
    - Is error handling present? (try/except covers the call)
    - Is the return value propagated correctly?
    - Are type transformations documented?
    - Is the docstring consistent with actual behavior?
  Flag any path where:
    - Errors are swallowed silently
    - Return types change unexpectedly  
    - Documentation claims differ from code behavior
```

### Phase 8: Cross-Validate Against Existing Documentation COMMONLY SKIPPED — DO NOT SKIP
```
For each CRITICAL or IMPORTANT symbol:
  Check: does API doc exist?
  Check: does doc mention all callers (upstream context)?
  Check: does doc mention all callees (downstream behavior)?
  Check: is the symbol's tier reflected in doc prominence?
  
For each DEAD symbol:
  Check: does doc exist? If yes → flag as misleading (documenting unused code)
```

---

## 4. Shannon Entropy Interpretation

```
Entropy = 0, Reach = 0%    → Dead code (no path from any endpoint)
Entropy = 0, Reach = 100%  → Universal dependency (every endpoint uses it)
Entropy = 0.5              → Moderate selectivity (used by ~15% or ~85%)
Entropy = 1.0              → Maximum uncertainty (used by exactly 50%)
```

**High-entropy symbols are the most interesting** — they're decision points where some user paths include them and others don't. These are where documentation is most valuable because users can't predict when they'll encounter them.

## 5. Ping Entropy Interpretation

```
Ping Entropy (novel method):
  Measures information flow bottlenecks using attenuated traversal
  
  High Ping Entropy = receives diverse pings from many different endpoints
                      → true information flow bottleneck
  Low Ping Entropy  = receives pings from mostly one endpoint
                      → specialized leaf node
  
  KEY DIFFERENCE FROM SHANNON:
    Shannon only counts binary reachability (reached or not)
    Ping Entropy accounts for:
      - Fan-out (a node calling many things distributes its influence)
      - Fan-in (a node called by many things concentrates information flow)
      - Path length (deeper nodes get weaker pings — depth matters)
    
  Combined Score = (Shannon + Ping) / 2
    → Best single metric for documentation priority
```

## 6. Data Structures

```python
@dataclass
class SymbolAnalysis:
    name: str
    module: str
    symbol_type: str  # function, method, class, property
    reachability_count: int
    reachability_pct: float
    shannon_entropy: float
    ping_entropy: float  # ← novel metric, only from engine
    combined_entropy: float  # (shannon + ping) / 2
    tier: str  # CRITICAL, IMPORTANT, SUPPORTING, SPECIALIZED, DEAD, SHADOW
    reached_by: List[str]  # which public endpoints reach this
    calls: List[str]  # what this symbol calls (forward)
    called_by: List[str]  # what calls this symbol (reverse)
    propagation_issues: List[str]  # errors found in path validation (Phase 7)
    doc_status: str  # documented, missing, incomplete, misleading
```

## 7. Required Outputs Checklist

After running RREA, ALL of these must be present:

- [ ] Forward call graph with edge count breakdown (calls/inherits/accesses/property)
- [ ] Public endpoint count
- [ ] Reachable vs unreachable symbol counts
- [ ] Shannon entropy distribution (zero/low/medium/high/critical bands)
- [ ] **Ping entropy distribution** (zero/low/medium/high/critical bands)
- [ ] Top 30 chokepoints by combined entropy
- [ ] Symbol tier classification counts (CRITICAL/IMPORTANT/SUPPORTING/SPECIALIZED/DEAD/SHADOW)
- [ ] Dead code list with evidence
- [ ] Shadow dependency list with trigger conditions
- [ ] **Propagation path validation report** (Phase 7) — list of issues found
- [ ] **Doc cross-validation report** (Phase 8) — undocumented chokepoints
- [ ] Full JSON report at `/tmp/team4_rrea_report.json`

If any item is missing, the analysis is incomplete.

## 8. Expected Findings for crdt-merge

Based on architecture (6 layers, ~78 modules, ~2,240 runtime methods):

| Tier | Expected Count | Documentation Action |
|------|---------------|---------------------|
| CRITICAL | ~50-80 | Must have complete docs with examples |
| IMPORTANT | ~150-200 | Must have full API docs |
| SUPPORTING | ~300-500 | Standard API reference |
| SPECIALIZED | ~200-400 | Brief reference with usage context |
| DEAD | ~50-100 | Flag for removal, do not document |
| SHADOW | ~20-50 | Document trigger conditions |

## 9. Novelty

This method is novel because:

1. **Reverse direction:** Most tools analyze what code *does*. RREA analyzes what code *is used for* from the user's perspective.
2. **Dual entropy:** Shannon entropy + Ping entropy together produce better priority rankings than either alone.
3. **Ping entropy (original contribution):** PageRank-inspired attenuated traversal applied to code documentation priority is not standard practice.
4. **Propagation validation:** Tracing full paths catches error-handling gaps and type mutation that no individual-symbol analysis can find.
5. **Dead code detection without execution:** Unlike coverage tools (which need test suites), RREA finds unreachable code through static graph analysis alone.

## 10. Limitations

- Call graph construction is conservative (may miss dynamic dispatch)
- `getattr`/`__getattr__` patterns create invisible edges
- Monkey-patching at runtime can alter the graph
- O(V × E) complexity for full reachability — manageable for <100K LOC

## 11. Common Mistakes to Avoid

1. **Writing an inline simplified version** — The engine handles edge cases that take 556 lines to cover; a 100-line version will produce unreliable results
2. **Skipping Phases 7 and 8** — These are the phases that produce actionable findings beyond just entropy scores
3. **Only computing Shannon entropy** — Ping entropy is the novel contribution; without it you're just doing standard reachability analysis
4. **Accepting false dead-code counts** — AST-only call graphs cannot trace `self.method()` or `obj.attr()` calls; high dead-code counts may be false positives from incomplete graph construction
5. **Not saving the JSON report** — The report at `/tmp/team4_rrea_report.json` is the evidence that all phases completed

---

*Designed for the crdt-merge documentation project, March 2026.*  
*Version 2.0 — Hardened with engine mandate, phase enforcement, and validation gates.*  
*Pending proper execution and validation by Team 4.*
