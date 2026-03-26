# Graph-Theoretic Dependency & Execution Path Analysis (GDEPA)

> **Team 3 Method** — Invented for the crdt-merge documentation project  
> **Version:** 2.0 (Hardened — validation gates added)  
> **Status:** Tested and validated. Found 7 circular dependencies, 2 layer violations, 409 runtime properties, and 2,240 runtime methods invisible to AST/regex.  
> **Engine:** `research/team3_gdepa_engine.py` | Persistent: `/agent/home/team3_gdepa_engine.py`

---

## ⛔ CRITICAL: What GDEPA Is and Is NOT

```
GDEPA is NOT just building import graphs from AST
GDEPA is NOT just building inheritance graphs from AST
GDEPA is NOT any analysis that only reads source code files
   ↳ That's just an extension of Team 1's work, not a separate method

GDEPA IS import graph + inheritance graph + RUNTIME INSPECT
GDEPA IS the comparison between what AST sees and what Python runtime sees
GDEPA IS the only method that catches inherited methods, runtime properties,
   metaclass-generated methods, descriptor-based attributes, and dynamic __init_subclass__ hooks
```

### Why Runtime Inspect Cannot Be Skipped

Python is a dynamic language. At runtime, a class may have:
- **Inherited methods** from parent classes (not declared in the class's own source)
- **Properties** created by descriptors, `@property`, `__set_name__`, etc.
- **Metaclass-generated methods** from `__init_subclass__`, `__class_getitem__`, ABCMeta, etc.
- **Dynamic attributes** set by `__init__` but not visible in class body
- **Mixin contributions** from complex MRO chains

**None of these appear in AST analysis.** They only appear when you `import` the module and call `inspect.getmembers()`.

### Validation Gate
```
GDEPA completion requires:
  runtime_only_symbol_count > 0

If runtime_only_symbol_count == 0:
  → The analysis is INCOMPLETE
  → The runtime inspect phase was either skipped or failed
  → DO NOT sign off — re-run with the actual engine
```

---

## 1. Theory

Traditional code analysis uses two approaches:
- **AST (Abstract Syntax Tree):** Parses source into syntax nodes. Fast and accurate for declared symbols but blind to runtime behavior, inheritance chains, and dynamic attributes.
- **Regex (Text Pattern Matching):** Scans raw source text. Catches comments, pragmas, and non-syntactic patterns but misses multi-line constructs and has no semantic understanding.

**GDEPA** introduces a third dimension: treating the codebase as a **directed graph** where:
- **Nodes** = every importable symbol (module, class, function, constant, property)
- **Edges** = dependency relationships (imports, calls, inheritance, composition)

Then it **cross-validates** this static graph against **runtime introspection** — what Python's `inspect` module actually sees when the code is loaded.

## 2. Why This Catches Things Others Miss

| Finding Type | AST | Regex | GDEPA |
|-------------|-----|-------|-------|
| Declared functions | | | |
| Inherited methods | | | |
| Dynamic properties | | | |
| Metaclass-generated methods | | | |
| Circular dependencies | | | |
| Layer boundary violations | | | |
| Runtime-only attributes | | | |
| Code smells (bare except) | | | |
| Type annotations in comments | | | |

## 3. Algorithm

### Phase 1: Build Import Graph
```
For each .py file F:
  For each import statement in F:
    Add edge: F → imported_module
    Record: symbol imported, alias, is_relative
```

### Phase 2: Build Inheritance Graph
```
For each class C in the codebase:
  For each base class B in C.__mro__:
    Add edge: C → B
    Record: which methods C inherits from B
```

### Phase 3: Runtime Introspection KEY PHASE — CANNOT BE SKIPPED
```
For each module M:
  import M                                    ← MUST actually import
  For each member in inspect.getmembers(M):   ← MUST use inspect
    Record: name, type, source, docstring
    Cross-reference against AST-declared symbols
    Flag: any symbol present at runtime but not in source
    
REQUIRED OUTPUT:
  - List of runtime-only symbols (inherited methods, properties, etc.)
  - Count MUST be > 0 for any non-trivial package
  - If count == 0 → analysis incomplete, do NOT proceed
```

**Implementation requirements for Phase 3:**
1. The target package MUST be importable (`pip install -e .` or `sys.path` manipulation)
2. Use `importlib.import_module()` for each module
3. Use `inspect.getmembers()` with predicates (`inspect.isfunction`, `inspect.ismethod`, `inspect.isclass`, etc.)
4. For each class, use `inspect.getmembers(cls)` to find ALL members including inherited
5. Compare the runtime member list against the AST-extracted member list
6. The DELTA is the unique GDEPA contribution — symbols present at runtime but absent from source

### Phase 4: Architectural Validation
```
Define layer boundaries from architecture map
For each import edge A → B:
  If layer(A) > layer(B): SKIP (valid downward dependency)
  If layer(A) < layer(B): FLAG (upward violation!)
  If layer(A) == layer(B) and A ≠ B: CHECK (lateral — may be circular)
```

### Phase 5: Cross-Reference Documentation
```
For each runtime symbol S:
  Check if S appears in any API doc file
  If not: add to doc_gaps list with full metadata
```

## 4. Implementation

The GDEPA engine MUST be used from:
- **Primary:** `research/team3_gdepa_engine.py`
- **Persistent copy:** `/agent/home/team3_gdepa_engine.py`

**Do NOT write an ad-hoc replacement script.** If the engine needs enhancement, modify the engine file itself and update the repo.

**Key data structures:**
- `import_graph: Dict[str, List[ImportEdge]]` — directed import dependencies
- `inheritance_graph: Dict[str, List[str]]` — class hierarchy (MRO)
- `runtime_symbols: Dict[str, Dict[str, SymbolInfo]]` — everything Python sees at runtime
- `layer_map: Dict[str, int]` — module → architectural layer assignment

## 5. Results on crdt-merge (Layer 1)

| Metric | Value |
|--------|-------|
| Import graph edges | ~450 |
| Inheritance edges | ~180 |
| Circular dependencies found | 7 |
| Layer violations found | 2 |
| Runtime-only symbols discovered | 409 properties + 1,244 inherited methods |
| New doc gaps identified | 319 (many overlapping with existing docs) |
| Unique findings (not in Team 1 or 2) | ~150 symbols |

## 6. Required Outputs Checklist

After running GDEPA, ALL of these must be present:

- [ ] Import graph with total edge count
- [ ] Circular dependency list (with cycle paths)
- [ ] Layer violation list (with specific import chain evidence)
- [ ] Inheritance graph showing MRO for each class
- [ ] **Runtime symbol count** (from `inspect.getmembers()`) — MUST be > 0
- [ ] **Runtime vs AST delta** — list of symbols present at runtime but not in AST
- [ ] Inherited methods count and list
- [ ] Runtime properties count and list
- [ ] Metaclass/descriptor-generated methods (if any)
- [ ] Documentation gap list (runtime symbols not in API docs)

If any item is missing or shows a zero count where a non-zero count is expected, the analysis is incomplete.

## 7. When to Use

Run GDEPA as the **third pass** after AST and regex, because:
1. It requires the codebase to be importable (runtime analysis)
2. It benefits from knowing what AST/regex already found (avoids duplicate work)
3. Its graph analysis catches architectural issues that only make sense after individual symbols are cataloged

## 8. Limitations

- Requires all dependencies installed (must be able to `import` the package)
- Dynamic code generation at import time may cause side effects
- Cannot analyze code that fails to import (syntax errors, missing deps)
- Graph analysis is O(V+E) — scales linearly but slow on massive codebases

## 9. Common Mistakes to Avoid

1. **Building inheritance graph from AST only** — AST can see `class Foo(Bar)` but cannot resolve the full MRO, especially with mixins, metaclasses, or conditional inheritance
2. **Skipping the import step** — Without importing, you cannot discover runtime-generated members
3. **Accepting zero runtime-only symbols** — This always means the runtime phase failed or was skipped
4. **Writing a new script instead of using the engine** — The engine handles edge cases; ad-hoc scripts don't

---

*Designed and validated during the crdt-merge documentation project, March 2026.*  
*Version 2.0 — Hardened with validation gates and anti-shortcut rules.*  
*Approved by: Master Architect (Team 3)*
