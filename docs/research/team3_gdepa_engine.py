#!/usr/bin/env python3
"""
TEAM 3: Graph-Theoretic Dependency & Execution Path Analysis (GDEPA)
=====================================================================
The key differentiator of GDEPA is RUNTIME INTROSPECTION.
Static-only analysis (import graphs, inheritance graphs from AST) is NOT GDEPA.

GDEPA requires:
  1. Building import graph (static)
  2. Building inheritance graph (static + runtime MRO)
  3. RUNTIME INSPECT — importing modules and calling inspect.getmembers()
  4. Comparing runtime symbols against AST symbols to find the DELTA
  5. Architectural validation (circular deps, layer violations)

The DELTA (runtime-only symbols) is the unique contribution. If delta = 0,
the analysis is incomplete.

Usage:
  python3 team3_gdepa_engine.py /path/to/source [/path/to/docs] [--layer-map LAYER_MAP.md]
"""

import ast
import os
import sys
import json
import inspect
import importlib
import importlib.util
from collections import defaultdict
from pathlib import Path


# ============================================================================
# Phase 1: Import Graph Builder (Static)
# ============================================================================

class ImportGraphBuilder(ast.NodeVisitor):
    """Extract import relationships from AST."""

    def __init__(self, module_name):
        self.module = module_name
        self.imports = []  # (from_module, to_module, symbol, is_relative)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((self.module, alias.name, alias.name, False))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ''
        for alias in node.names:
            target = f"{mod}.{alias.name}" if mod else alias.name
            self.imports.append((self.module, target, alias.name, node.level > 0))
        self.generic_visit(node)


# ============================================================================
# Phase 2: AST Symbol Extractor (for comparison with runtime)
# ============================================================================

class ASTSymbolExtractor(ast.NodeVisitor):
    """Extract all symbols declared in source via AST."""

    def __init__(self, module_name):
        self.module = module_name
        self.symbols = {}  # name -> {type, lineno, ...}
        self.classes = {}  # class_name -> {methods, bases, ...}
        self.scope_stack = [module_name]
        self.imports = {}

    def _fqn(self, name):
        return f"{self.scope_stack[-1]}.{name}"

    def visit_ImportFrom(self, node):
        mod = node.module or ''
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = f"{mod}.{alias.name}"
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = alias.name
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        fqn = self._fqn(node.name)
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(self.imports.get(base.id, base.id))
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                bases.append(f"{base.value.id}.{base.attr}")
        
        self.classes[node.name] = {
            'fqn': fqn,
            'bases': bases,
            'methods': [],
            'properties': [],
            'class_methods': [],
            'static_methods': [],
            'lineno': node.lineno
        }
        self.symbols[fqn] = {'type': 'class', 'lineno': node.lineno, 'name': node.name}

        self.scope_stack.append(fqn)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [
                    d.id if isinstance(d, ast.Name) else
                    d.attr if isinstance(d, ast.Attribute) else '?'
                    for d in child.decorator_list
                ]
                method_info = {'name': child.name, 'decorators': decorators, 'lineno': child.lineno}
                
                if 'property' in decorators:
                    self.classes[node.name]['properties'].append(child.name)
                elif 'classmethod' in decorators:
                    self.classes[node.name]['class_methods'].append(child.name)
                elif 'staticmethod' in decorators:
                    self.classes[node.name]['static_methods'].append(child.name)
                else:
                    self.classes[node.name]['methods'].append(child.name)
                
                mfqn = f"{fqn}.{child.name}"
                self.symbols[mfqn] = {'type': 'method', 'lineno': child.lineno, 'name': child.name}
        
        self.scope_stack.pop()
        # Don't call generic_visit — we already handled child functions above
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)

    def visit_FunctionDef(self, node):
        if len(self.scope_stack) == 1:  # top-level function
            fqn = self._fqn(node.name)
            self.symbols[fqn] = {'type': 'function', 'lineno': node.lineno, 'name': node.name}
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        if len(self.scope_stack) == 1:  # module-level
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fqn = self._fqn(target.id)
                    self.symbols[fqn] = {'type': 'variable', 'lineno': node.lineno, 'name': target.id}
        self.generic_visit(node)


# ============================================================================
# Phase 3: Runtime Introspection (THE KEY PHASE)
# ============================================================================

def runtime_inspect_module(module_path, module_name, package_root):
    """
    Import a module and inspect its runtime members.
    Returns dict of all runtime symbols vs what AST would see.
    
    THIS IS THE KEY GDEPA CONTRIBUTION.
    Without this, you're just doing extended Team 1 analysis.
    """
    results = {
        'module': module_name,
        'imported': False,
        'import_error': None,
        'runtime_symbols': {},
        'classes': {},
        'error_details': None
    }
    
    # Ensure the package root is on sys.path
    parent = str(Path(package_root).parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    
    try:
        mod = importlib.import_module(module_name)
        results['imported'] = True
    except Exception as e:
        results['import_error'] = str(e)
        results['error_details'] = type(e).__name__
        return results
    
    # Get ALL runtime members
    try:
        members = inspect.getmembers(mod)
        for name, obj in members:
            sym_type = 'unknown'
            if inspect.isclass(obj):
                sym_type = 'class'
            elif inspect.isfunction(obj):
                sym_type = 'function'
            elif inspect.ismethod(obj):
                sym_type = 'method'
            elif inspect.ismodule(obj):
                sym_type = 'module'
            elif isinstance(obj, property):
                sym_type = 'property'
            elif callable(obj):
                sym_type = 'callable'
            else:
                sym_type = 'data'
            
            # Determine where the symbol actually comes from
            source_module = None
            try:
                if hasattr(obj, '__module__'):
                    source_module = obj.__module__
            except Exception:
                pass
            
            results['runtime_symbols'][name] = {
                'type': sym_type,
                'source_module': source_module,
                'is_imported': source_module and source_module != module_name,
                'has_docstring': bool(getattr(obj, '__doc__', None)),
                'qualname': getattr(obj, '__qualname__', name),
            }
            
            # Deep inspect classes for inherited members
            if inspect.isclass(obj) and (not source_module or source_module == module_name):
                class_info = {
                    'mro': [c.__name__ for c in inspect.getmro(obj)],
                    'all_methods': [],
                    'all_properties': [],
                    'inherited_methods': [],
                    'inherited_properties': [],
                    'own_methods': [],
                    'own_properties': [],
                }
                
                try:
                    class_members = inspect.getmembers(obj)
                    for mname, mobj in class_members:
                        if mname.startswith('__') and mname.endswith('__'):
                            continue  # skip dunders for now
                        
                        is_property = isinstance(
                            inspect.getattr_static(obj, mname, None),
                            (property, classmethod, staticmethod)
                        )
                        
                        # Determine if inherited
                        declaring_class = None
                        for klass in inspect.getmro(obj):
                            if mname in klass.__dict__:
                                declaring_class = klass.__name__
                                break
                        
                        is_inherited = declaring_class and declaring_class != obj.__name__
                        
                        if isinstance(inspect.getattr_static(obj, mname, None), property):
                            class_info['all_properties'].append(mname)
                            if is_inherited:
                                class_info['inherited_properties'].append({
                                    'name': mname, 'from': declaring_class
                                })
                            else:
                                class_info['own_properties'].append(mname)
                        elif callable(mobj) or isinstance(
                            inspect.getattr_static(obj, mname, None), 
                            (classmethod, staticmethod)
                        ):
                            class_info['all_methods'].append(mname)
                            if is_inherited:
                                class_info['inherited_methods'].append({
                                    'name': mname, 'from': declaring_class
                                })
                            else:
                                class_info['own_methods'].append(mname)
                except Exception as e:
                    class_info['inspect_error'] = str(e)
                
                results['classes'][name] = class_info
    except Exception as e:
        results['import_error'] = f"inspect failed: {e}"
    
    return results


# ============================================================================
# Phase 4: Architectural Validation
# ============================================================================

def find_circular_deps(import_graph):
    """Find all circular dependency cycles using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()
    path = []
    
    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        for neighbor in import_graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
        
        path.pop()
        rec_stack.discard(node)
    
    for node in import_graph:
        if node not in visited:
            dfs(node)
    
    return cycles


def check_layer_violations(import_graph, layer_map):
    """Check for upward imports (lower layer importing from higher layer)."""
    violations = []
    for source, targets in import_graph.items():
        source_layer = layer_map.get(source, -1)
        for target in targets:
            target_layer = layer_map.get(target, -1)
            if source_layer >= 0 and target_layer >= 0 and source_layer < target_layer:
                violations.append({
                    'source': source,
                    'source_layer': source_layer,
                    'target': target,
                    'target_layer': target_layer,
                    'violation': f"Layer {source_layer} imports from Layer {target_layer}"
                })
    return violations


# ============================================================================
# Phase 5: Delta Computation (Runtime vs AST)
# ============================================================================

def compute_delta(ast_symbols, runtime_results):
    """
    Compare AST-extracted symbols with runtime-inspected symbols.
    The DELTA is GDEPA's unique contribution.
    """
    delta = {
        'runtime_only': [],          # Present at runtime, not in AST
        'ast_only': [],              # In AST but not at runtime (unlikely but possible)
        'inherited_methods': [],     # Methods inherited from parent classes
        'inherited_properties': [],  # Properties inherited from parent classes
        'total_inherited_methods': 0,
        'total_inherited_properties': 0,
        'total_runtime_only': 0,
    }
    
    ast_names = set()
    for sym_info in ast_symbols.values():
        ast_names.add(sym_info.get('name', ''))
    
    runtime_names = set()
    for name, info in runtime_results.get('runtime_symbols', {}).items():
        if not name.startswith('_'):
            runtime_names.add(name)
            if name not in ast_names and not info.get('is_imported'):
                delta['runtime_only'].append({
                    'name': name,
                    'type': info['type'],
                    'source_module': info.get('source_module'),
                })
    
    # Collect inherited members from class inspection
    for class_name, class_info in runtime_results.get('classes', {}).items():
        for method in class_info.get('inherited_methods', []):
            delta['inherited_methods'].append({
                'class': class_name,
                'method': method['name'],
                'inherited_from': method['from']
            })
        for prop in class_info.get('inherited_properties', []):
            delta['inherited_properties'].append({
                'class': class_name,
                'property': prop['name'],
                'inherited_from': prop['from']
            })
    
    delta['total_inherited_methods'] = len(delta['inherited_methods'])
    delta['total_inherited_properties'] = len(delta['inherited_properties'])
    delta['total_runtime_only'] = len(delta['runtime_only'])
    
    return delta


# ============================================================================
# Main Engine
# ============================================================================

def main():
    source_root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/crdt-merge/crdt_merge"
    doc_root = sys.argv[2] if len(sys.argv) > 2 else "/tmp/CRDT-Mapping_Docs/api-reference"
    
    print("=" * 70)
    print("TEAM 3: GRAPH-THEORETIC DEPENDENCY & EXECUTION PATH ANALYSIS (GDEPA)")
    print("  with Runtime Introspection (the key differentiator)")
    print("=" * 70)
    
    package_name = Path(source_root).name
    package_root = source_root
    
    # ---- Phase 1: Build Import Graph ----
    print("\n[Phase 1] Building import graph...")
    import_graph = defaultdict(list)
    all_modules = {}
    
    for root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for fname in files:
            if not fname.endswith('.py'):
                continue
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, os.path.dirname(source_root))
            mod_name = rel.replace('/', '.').replace('.py', '')
            if mod_name.endswith('.__init__'):
                mod_name = mod_name[:-9]
            
            try:
                with open(fpath) as f:
                    source = f.read()
                tree = ast.parse(source, filename=fpath)
                
                # Import graph
                ig = ImportGraphBuilder(mod_name)
                ig.visit(tree)
                for _, target, _, _ in ig.imports:
                    if target.startswith(package_name):
                        import_graph[mod_name].append(target)
                
                # AST symbols
                ext = ASTSymbolExtractor(mod_name)
                ext.visit(tree)
                all_modules[mod_name] = {
                    'path': fpath,
                    'ast_symbols': ext.symbols,
                    'ast_classes': ext.classes,
                }
            except Exception as e:
                print(f"  WARN: Failed to parse {mod_name}: {e}", file=sys.stderr)
    
    total_edges = sum(len(v) for v in import_graph.values())
    print(f"  Modules: {len(all_modules)}")
    print(f"  Import edges: {total_edges}")
    
    # ---- Phase 2: Circular Dependencies & Architecture ----
    print("\n[Phase 2] Checking circular dependencies...")
    cycles = find_circular_deps(dict(import_graph))
    print(f"  Circular dependencies found: {len(cycles)}")
    for i, cycle in enumerate(cycles[:10]):
        print(f"    Cycle {i+1}: {' → '.join(cycle)}")
    
    # ---- Phase 3: RUNTIME INTROSPECTION (KEY PHASE) ----
    print("\n[Phase 3] Runtime introspection (KEY GDEPA PHASE)...")
    print(f"  Importing package from: {source_root}")
    
    # Install the package if possible
    setup_py = os.path.join(os.path.dirname(source_root), 'setup.py')
    pyproject = os.path.join(os.path.dirname(source_root), 'pyproject.toml')
    if os.path.exists(pyproject) or os.path.exists(setup_py):
        print("  Attempting pip install -e ...")
        os.system(f"cd {os.path.dirname(source_root)} && pip install -e . --quiet 2>/dev/null")
    else:
        # Just add to path
        parent = str(Path(source_root).parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
    
    runtime_results = {}
    import_failures = []
    
    for mod_name in sorted(all_modules.keys()):
        result = runtime_inspect_module(
            all_modules[mod_name]['path'], 
            mod_name, 
            package_root
        )
        runtime_results[mod_name] = result
        if not result['imported']:
            import_failures.append((mod_name, result.get('import_error', 'unknown')))
    
    imported_count = sum(1 for r in runtime_results.values() if r['imported'])
    failed_count = len(import_failures)
    print(f"  Successfully imported: {imported_count} / {len(all_modules)}")
    if failed_count:
        print(f"  Import failures: {failed_count}")
        for mod, err in import_failures[:10]:
            print(f"    {mod}: {err}")
    
    # ---- Phase 4: Compute Delta (Runtime vs AST) ----
    print("\n[Phase 4] Computing runtime vs AST delta...")
    
    total_inherited_methods = 0
    total_inherited_properties = 0
    total_runtime_only = 0
    all_deltas = {}
    
    for mod_name, mod_info in all_modules.items():
        if mod_name in runtime_results and runtime_results[mod_name]['imported']:
            delta = compute_delta(mod_info['ast_symbols'], runtime_results[mod_name])
            all_deltas[mod_name] = delta
            total_inherited_methods += delta['total_inherited_methods']
            total_inherited_properties += delta['total_inherited_properties']
            total_runtime_only += delta['total_runtime_only']
    
    print(f"  Total inherited methods: {total_inherited_methods}")
    print(f"  Total inherited properties: {total_inherited_properties}")
    print(f"  Total runtime-only symbols: {total_runtime_only}")
    
    # VALIDATION GATE
    if total_inherited_methods == 0 and total_runtime_only == 0 and imported_count > 5:
        print("\n  ⚠️  WARNING: Zero runtime-only symbols detected!")
        print("  ⚠️  This likely means runtime inspection failed or package couldn't import.")
        print("  ⚠️  GDEPA analysis may be INCOMPLETE.")
    
    # ---- Phase 5: Cross-reference with documentation ----
    print("\n[Phase 5] Cross-referencing with documentation...")
    
    undocumented = []
    if os.path.isdir(doc_root):
        doc_content = ""
        for root, dirs, files in os.walk(doc_root):
            for fname in files:
                if fname.endswith('.md'):
                    try:
                        with open(os.path.join(root, fname)) as f:
                            doc_content += f.read() + "\n"
                    except Exception:
                        pass
        
        # Check inherited methods
        for mod_name, delta in all_deltas.items():
            for method in delta.get('inherited_methods', []):
                search = f"{method['class']}.{method['method']}"
                if search not in doc_content and method['method'] not in doc_content:
                    undocumented.append({
                        'type': 'inherited_method',
                        'class': method['class'],
                        'name': method['method'],
                        'from': method['inherited_from'],
                        'module': mod_name
                    })
            for prop in delta.get('inherited_properties', []):
                search = f"{prop['class']}.{prop['property']}"
                if search not in doc_content and prop['property'] not in doc_content:
                    undocumented.append({
                        'type': 'inherited_property',
                        'class': prop['class'],
                        'name': prop['property'],
                        'from': prop['inherited_from'],
                        'module': mod_name
                    })
    
    print(f"  Undocumented inherited symbols: {len(undocumented)}")
    
    # ---- Build Report ----
    report = {
        "method": "GDEPA — Graph-Theoretic Dependency & Execution Path Analysis",
        "team": "Team 3 — Architects",
        "version": "2.0",
        "key_contribution": "Runtime introspection reveals symbols invisible to static analysis",
        "stats": {
            "total_modules": len(all_modules),
            "modules_imported": imported_count,
            "import_failures": failed_count,
            "import_graph_edges": total_edges,
            "circular_dependencies": len(cycles),
            "total_inherited_methods": total_inherited_methods,
            "total_inherited_properties": total_inherited_properties,
            "total_runtime_only_symbols": total_runtime_only,
            "undocumented_inherited": len(undocumented),
        },
        "validation": {
            "runtime_inspect_executed": imported_count > 0,
            "runtime_only_symbols_nonzero": total_runtime_only > 0 or total_inherited_methods > 0,
            "analysis_complete": (imported_count > 0) and (total_runtime_only > 0 or total_inherited_methods > 0),
        },
        "circular_dependencies": [
            {"cycle": c} for c in cycles[:20]
        ],
        "import_failures": [
            {"module": m, "error": e} for m, e in import_failures
        ],
        "deltas_by_module": {
            mod: {
                "inherited_methods": d["total_inherited_methods"],
                "inherited_properties": d["total_inherited_properties"],
                "runtime_only": d["total_runtime_only"],
            }
            for mod, d in all_deltas.items()
            if d["total_inherited_methods"] > 0 or d["total_runtime_only"] > 0
        },
        "top_inherited_methods": [
            m for d in all_deltas.values() 
            for m in d.get("inherited_methods", [])
        ][:50],
        "undocumented_inherited": undocumented[:100],
    }
    
    out_path = '/tmp/team3_gdepa_report.json'
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Summary
    print("\n" + "=" * 70)
    print("GDEPA ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n  📊 Key Metrics:")
    print(f"     Modules analyzed: {len(all_modules)}")
    print(f"     Successfully imported: {imported_count}")
    print(f"     Import graph edges: {total_edges}")
    print(f"     Circular dependencies: {len(cycles)}")
    print(f"     Inherited methods: {total_inherited_methods}")
    print(f"     Inherited properties: {total_inherited_properties}")
    print(f"     Runtime-only symbols: {total_runtime_only}")
    print(f"     Undocumented inherited: {len(undocumented)}")
    
    if report['validation']['analysis_complete']:
        print(f"\n  ✅ VALIDATION: Analysis complete (runtime symbols found)")
    else:
        print(f"\n  ❌ VALIDATION: Analysis may be INCOMPLETE")
        if imported_count == 0:
            print(f"     → No modules could be imported — check dependencies")
        if total_runtime_only == 0 and total_inherited_methods == 0:
            print(f"     → Zero runtime-only symbols — inspect may have failed")
    
    print(f"\n  Report: {out_path}")


if __name__ == '__main__':
    main()
