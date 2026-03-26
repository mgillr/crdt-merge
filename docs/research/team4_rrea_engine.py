#!/usr/bin/env python3
"""
TEAM 4: Reverse Reachability Entropy Analysis (RREA)
=====================================================
Innovation: Ping Entropy + Reverse Propagation Path Mapping

Novel method that treats the codebase as a directed graph and works BACKWARDS
from every public API endpoint through all execution paths. At each node,
Shannon entropy measures how many diverse paths converge — identifying:

1. CHOKEPOINT NODES — high entropy (many paths converge)
   → Most critical symbols to document (high user impact)
2. DEAD CODE — zero inbound paths from any public endpoint
   → Unreachable symbols, potential legacy/cleanup targets
3. SHADOW DEPENDENCIES — symbols reachable from only 1 endpoint
   → Hidden single-points-of-failure in the API
4. ENTROPY-WEIGHTED DOC PRIORITY — rank every symbol by reachability
   → Data-driven documentation prioritization

Theory:
  H(node) = -Σ p(path_i) * log2(p(path_i))
  where p(path_i) = paths_through_node_from_endpoint_i / total_paths_through_node

  High H = many diverse endpoints depend on this node (critical chokepoint)
  Low H  = only one endpoint uses this node (leaf/utility)
  Zero   = dead code (unreachable from any public API)

What this catches that Teams 1-3 cannot:
  - AST (Team 1): Only sees syntax structure, not runtime reachability
  - Regex (Team 2): Only sees text patterns, no graph relationships
  - GDEPA (Team 3): Builds forward graph but doesn't compute entropy or trace
    reverse propagation paths from endpoints back through the call chain

Team 4 roles:
  - Entropy Analyst: Computes and interprets Shannon entropy scores
  - Path Tracer: Maps all propagation paths endpoint → leaf
  - Dead Code Hunter: Identifies unreachable symbols
  - Doc Reconciler: Cross-references findings with existing docs

Usage:
  python3 team4_rrea_engine.py /path/to/source /path/to/docs
"""

import ast
import os
import sys
import json
import math
from collections import defaultdict, deque
from pathlib import Path


class CallGraphBuilder(ast.NodeVisitor):
    """Build a call/reference graph from AST — tracks what each function/method calls."""
    
    def __init__(self, module_name):
        self.module = module_name
        self.current_scope = module_name
        self.edges = []  # (caller, callee, edge_type)
        self.all_symbols = set()
        self.public_symbols = set()
        self.dunder_all = None
        self.scope_stack = [module_name]
        self.imports = {}
        self.class_bases = {}
        self.decorators = defaultdict(list)
        
    def _fqn(self, name):
        return f"{self.scope_stack[-1]}.{name}"
    
    def visit_Import(self, node):
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        mod = node.module or ''
        for alias in node.names:
            local = alias.asname or alias.name
            self.imports[local] = f"{mod}.{alias.name}"
        self.generic_visit(node)
    
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == '__all__':
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    self.dunder_all = [
                        elt.value for elt in node.value.elts 
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
            elif isinstance(target, ast.Name) and not target.id.startswith('_'):
                fqn = self._fqn(target.id)
                self.all_symbols.add(fqn)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        fqn = self._fqn(node.name)
        self.all_symbols.add(fqn)
        self.scope_stack.append(fqn)
        
        # Track decorators
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                self.decorators[fqn].append(dec.id)
            elif isinstance(dec, ast.Attribute):
                self.decorators[fqn].append(dec.attr)
        
        # Track inheritance edges
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_ref = self.imports.get(base.id, f"{self.module}.{base.id}")
                bases.append(base_ref)
                self.edges.append((fqn, base_ref, 'inherits'))
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                base_ref = f"{self.imports.get(base.value.id, base.value.id)}.{base.attr}"
                bases.append(base_ref)
                self.edges.append((fqn, base_ref, 'inherits'))
        self.class_bases[fqn] = bases
        
        self.generic_visit(node)
        self.scope_stack.pop()
    
    def visit_FunctionDef(self, node):
        fqn = self._fqn(node.name)
        self.all_symbols.add(fqn)
        self.scope_stack.append(fqn)
        
        # Track decorators
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                self.decorators[fqn].append(dec.id)
                # @property creates implicit attribute access patterns
                if dec.id == 'property':
                    self.edges.append((self.scope_stack[-2] if len(self.scope_stack) > 1 else self.module, fqn, 'property'))
        
        self.generic_visit(node)
        self.scope_stack.pop()
    
    visit_AsyncFunctionDef = visit_FunctionDef
    
    def visit_Call(self, node):
        caller = self.scope_stack[-1]
        callee = None
        
        if isinstance(node.func, ast.Name):
            name = node.func.id
            callee = self.imports.get(name, f"{self.module}.{name}")
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                prefix = self.imports.get(node.func.value.id, node.func.value.id)
                callee = f"{prefix}.{node.func.attr}"
            else:
                callee = f"?.{node.func.attr}"
        
        if callee:
            self.edges.append((caller, callee, 'calls'))
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            prefix = self.imports.get(node.value.id, node.value.id)
            ref = f"{prefix}.{node.attr}"
            caller = self.scope_stack[-1]
            self.edges.append((caller, ref, 'accesses'))
        self.generic_visit(node)
    
    def finalize(self):
        if self.dunder_all is not None:
            for name in self.dunder_all:
                self.public_symbols.add(f"{self.module}.{name}")
        else:
            for sym in self.all_symbols:
                parts = sym.split('.')
                if len(parts) == 2 and not parts[1].startswith('_'):
                    self.public_symbols.add(sym)


def build_full_graph(source_root):
    """Build complete call graph across all modules."""
    all_edges = []
    all_symbols = set()
    public_endpoints = set()
    module_symbols = defaultdict(set)
    module_info = {}
    
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
                builder = CallGraphBuilder(mod_name)
                builder.visit(tree)
                builder.finalize()
                
                all_edges.extend(builder.edges)
                all_symbols.update(builder.all_symbols)
                public_endpoints.update(builder.public_symbols)
                for sym in builder.all_symbols:
                    module_symbols[mod_name].add(sym)
                module_info[mod_name] = {
                    'symbols': len(builder.all_symbols),
                    'public': len(builder.public_symbols),
                    'edges': len(builder.edges),
                    'has_all': builder.dunder_all is not None,
                    'classes': [s for s in builder.all_symbols if any(
                        isinstance(n, ast.ClassDef) and f"{mod_name}.{n.name}" == s
                        for n in ast.walk(tree)
                    )]
                }
            except Exception as e:
                print(f"  WARN: Failed to parse {mod_name}: {e}", file=sys.stderr)
    
    return all_edges, all_symbols, public_endpoints, module_symbols, module_info


def compute_reverse_reachability(edges, all_symbols, public_endpoints):
    """For each symbol, compute which public endpoints can reach it via BFS."""
    forward_graph = defaultdict(set)
    reverse_graph = defaultdict(set)
    
    for caller, callee, edge_type in edges:
        forward_graph[caller].add(callee)
        reverse_graph[callee].add(caller)
    
    endpoint_reaches = {}
    symbol_reached_by = defaultdict(set)
    
    for endpoint in public_endpoints:
        visited = set()
        queue = deque([endpoint])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            for neighbor in forward_graph.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        endpoint_reaches[endpoint] = visited
        for sym in visited:
            symbol_reached_by[sym].add(endpoint)
    
    return endpoint_reaches, symbol_reached_by, forward_graph, reverse_graph


def compute_shannon_entropy(symbol_reached_by, public_endpoints):
    """
    Compute Shannon entropy for each symbol.
    H(node) = log2(number_of_endpoints_reaching_it) / log2(total_endpoints)
    Normalized to [0, 1] range.
    """
    total = max(len(public_endpoints), 1)
    log_total = math.log2(total) if total > 1 else 1
    
    entropy = {}
    for symbol, endpoints in symbol_reached_by.items():
        n = len(endpoints)
        if n <= 1:
            entropy[symbol] = 0.0
        else:
            entropy[symbol] = math.log2(n) / log_total
    
    return entropy


def find_dead_code(all_symbols, symbol_reached_by, public_endpoints):
    """Symbols not reachable from ANY public endpoint."""
    reachable = set(symbol_reached_by.keys()) | public_endpoints
    return all_symbols - reachable


def trace_propagation_paths(forward_graph, public_endpoints):
    """
    Trace all propagation paths from endpoints to leaf nodes.
    Returns paths and per-symbol path counts for priority weighting.
    """
    all_paths = []
    symbol_path_count = defaultdict(int)
    
    for endpoint in public_endpoints:
        stack = [(endpoint, [endpoint])]
        visited_edges = set()
        
        while stack:
            node, path = stack.pop()
            neighbors = forward_graph.get(node, set())
            
            if not neighbors or len(path) > 15:
                all_paths.append(path)
                for sym in path:
                    symbol_path_count[sym] += 1
            else:
                for neighbor in neighbors:
                    edge = (node, neighbor)
                    if edge not in visited_edges:
                        visited_edges.add(edge)
                        stack.append((neighbor, path + [neighbor]))
    
    return all_paths, symbol_path_count


def compute_ping_entropy(forward_graph, reverse_graph, all_symbols, public_endpoints):
    """
    NOVEL: Ping Entropy — simulate "pings" from every endpoint through the graph.
    Each node accumulates ping counts. The entropy of the ping distribution
    reveals information flow bottlenecks.
    
    Unlike simple reachability, ping entropy accounts for:
    - Fan-out (a node calling many things distributes its ping)
    - Fan-in (a node called by many things accumulates pings)
    - Path length (deeper nodes get attenuated pings)
    
    This is analogous to PageRank but purpose-built for code documentation priority.
    """
    ping_counts = defaultdict(lambda: defaultdict(float))  # node -> {source_endpoint: count}
    
    ATTENUATION = 0.85  # ping weakens with depth (like PageRank damping)
    
    for endpoint in public_endpoints:
        # BFS with attenuation
        queue = deque([(endpoint, 1.0)])
        visited = set()
        
        while queue:
            node, strength = queue.popleft()
            if node in visited or strength < 0.01:
                continue
            visited.add(node)
            ping_counts[node][endpoint] += strength
            
            neighbors = forward_graph.get(node, set())
            if neighbors:
                distributed = strength * ATTENUATION / len(neighbors)
                for neighbor in neighbors:
                    if neighbor not in visited:
                        queue.append((neighbor, distributed))
    
    # Compute entropy of ping distribution per node
    ping_entropy = {}
    for node, sources in ping_counts.items():
        total = sum(sources.values())
        if total == 0 or len(sources) <= 1:
            ping_entropy[node] = 0.0
            continue
        
        h = 0.0
        for source, count in sources.items():
            p = count / total
            if p > 0:
                h -= p * math.log2(p)
        
        # Normalize
        max_h = math.log2(len(sources)) if len(sources) > 1 else 1
        ping_entropy[node] = h / max_h if max_h > 0 else 0.0
    
    return ping_entropy, ping_counts


def check_doc_coverage(symbol, doc_root):
    """Check if a symbol's name appears in any doc file."""
    parts = symbol.split('.')
    sym_name = parts[-1]
    
    for root, dirs, files in os.walk(doc_root):
        for fname in files:
            if not fname.endswith('.md'):
                continue
            try:
                with open(os.path.join(root, fname)) as f:
                    if sym_name in f.read():
                        return True
            except Exception:
                pass
    return False


def main():
    source_root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/crdt-merge/crdt_merge"
    doc_root = sys.argv[2] if len(sys.argv) > 2 else "/agent/home/CRDT-Mapping_Docs/api-reference"
    
    print("=" * 70)
    print("TEAM 4: REVERSE REACHABILITY ENTROPY ANALYSIS (RREA)")
    print("  with Ping Entropy & Reverse Propagation Path Mapping")
    print("=" * 70)
    
    # Phase 1: Build call graph
    print("\n[Phase 1] Building complete call graph...")
    edges, all_symbols, public_endpoints, module_symbols, module_info = build_full_graph(source_root)
    print(f"  Symbols: {len(all_symbols)}")
    print(f"  Public API endpoints: {len(public_endpoints)}")
    print(f"  Edges: {len(edges)} (calls={sum(1 for _,_,t in edges if t=='calls')}, "
          f"inherits={sum(1 for _,_,t in edges if t=='inherits')}, "
          f"accesses={sum(1 for _,_,t in edges if t=='accesses')}, "
          f"property={sum(1 for _,_,t in edges if t=='property')})")
    
    # Phase 2: Reverse reachability
    print("\n[Phase 2] Computing reverse reachability...")
    endpoint_reaches, symbol_reached_by, fwd, rev = \
        compute_reverse_reachability(edges, all_symbols, public_endpoints)
    reachable = set(symbol_reached_by.keys())
    print(f"  Reachable: {len(reachable)}")
    print(f"  Unreachable: {len(all_symbols - reachable - public_endpoints)}")
    
    # Phase 3: Shannon entropy
    print("\n[Phase 3] Computing Shannon entropy...")
    shannon = compute_shannon_entropy(symbol_reached_by, public_endpoints)
    high_shannon = [(s, h) for s, h in sorted(shannon.items(), key=lambda x: -x[1]) if h > 0.5]
    print(f"  High-entropy chokepoints (H > 0.5): {len(high_shannon)}")
    
    # Phase 4: Ping entropy (NOVEL)
    print("\n[Phase 4] Computing Ping Entropy (novel method)...")
    ping_entropy, ping_counts = compute_ping_entropy(fwd, rev, all_symbols, public_endpoints)
    high_ping = [(s, h) for s, h in sorted(ping_entropy.items(), key=lambda x: -x[1]) if h > 0.5]
    print(f"  High ping-entropy nodes: {len(high_ping)}")
    
    # Phase 5: Dead code
    print("\n[Phase 5] Dead code detection...")
    dead = find_dead_code(all_symbols, symbol_reached_by, public_endpoints)
    print(f"  Dead code: {len(dead)}")
    
    # Phase 6: Propagation paths
    print("\n[Phase 6] Tracing propagation paths...")
    paths, path_counts = trace_propagation_paths(fwd, public_endpoints)
    shadow = {s: list(eps) for s, eps in symbol_reached_by.items() if len(eps) == 1}
    print(f"  Paths: {len(paths)}")
    print(f"  Shadow deps: {len(shadow)}")
    
    # Phase 7: Doc cross-reference
    print("\n[Phase 7] Cross-referencing with documentation...")
    undoc_chokepoints = []
    # Check top symbols by COMBINED entropy (Shannon + Ping averaged)
    combined = {}
    for sym in all_symbols:
        s_h = shannon.get(sym, 0)
        p_h = ping_entropy.get(sym, 0)
        combined[sym] = (s_h + p_h) / 2
    
    for sym, score in sorted(combined.items(), key=lambda x: -x[1])[:150]:
        if score > 0.2 and not check_doc_coverage(sym, doc_root):
            undoc_chokepoints.append({
                'symbol': sym,
                'combined_entropy': round(score, 4),
                'shannon_entropy': round(shannon.get(sym, 0), 4),
                'ping_entropy': round(ping_entropy.get(sym, 0), 4),
                'endpoint_count': len(symbol_reached_by.get(sym, set()))
            })
    
    undoc_dead = [s for s in sorted(dead)[:60] if not check_doc_coverage(s, doc_root)]
    
    print(f"  Undocumented chokepoints: {len(undoc_chokepoints)}")
    print(f"  Undocumented dead code: {len(undoc_dead)}")
    
    # Build report
    report = {
        "method": "RREA — Reverse Reachability Entropy Analysis with Ping Entropy",
        "team": "Team 4 — Entropy Analysts",
        "innovation": "Ping Entropy combines PageRank-style attenuation with Shannon entropy "
                      "to find information flow bottlenecks invisible to structural analysis",
        "stats": {
            "total_symbols": len(all_symbols),
            "public_endpoints": len(public_endpoints),
            "total_edges": len(edges),
            "edge_breakdown": {
                "calls": sum(1 for _,_,t in edges if t == 'calls'),
                "inherits": sum(1 for _,_,t in edges if t == 'inherits'),
                "accesses": sum(1 for _,_,t in edges if t == 'accesses'),
                "property": sum(1 for _,_,t in edges if t == 'property')
            },
            "reachable": len(reachable),
            "dead_code": len(dead),
            "high_shannon_entropy": len(high_shannon),
            "high_ping_entropy": len(high_ping),
            "shadow_dependencies": len(shadow),
            "propagation_paths": len(paths),
            "undocumented_chokepoints": len(undoc_chokepoints),
            "undocumented_dead_code": len(undoc_dead)
        },
        "entropy_distribution": {
            "shannon": {
                "zero": sum(1 for h in shannon.values() if h == 0),
                "low": sum(1 for h in shannon.values() if 0 < h <= 0.3),
                "medium": sum(1 for h in shannon.values() if 0.3 < h <= 0.6),
                "high": sum(1 for h in shannon.values() if 0.6 < h <= 0.8),
                "critical": sum(1 for h in shannon.values() if h > 0.8)
            },
            "ping": {
                "zero": sum(1 for h in ping_entropy.values() if h == 0),
                "low": sum(1 for h in ping_entropy.values() if 0 < h <= 0.3),
                "medium": sum(1 for h in ping_entropy.values() if 0.3 < h <= 0.6),
                "high": sum(1 for h in ping_entropy.values() if 0.6 < h <= 0.8),
                "critical": sum(1 for h in ping_entropy.values() if h > 0.8)
            }
        },
        "top_chokepoints_by_combined_entropy": [
            {"symbol": s, "combined": round(c, 4), 
             "shannon": round(shannon.get(s, 0), 4),
             "ping": round(ping_entropy.get(s, 0), 4),
             "endpoints": len(symbol_reached_by.get(s, set()))}
            for s, c in sorted(combined.items(), key=lambda x: -x[1])[:30]
        ],
        "dead_code": sorted(list(dead))[:50],
        "shadow_dependencies": [
            {"symbol": s, "only_endpoint": eps[0]}
            for s, eps in sorted(shadow.items())[:30]
        ],
        "undocumented_chokepoints": undoc_chokepoints,
        "undocumented_dead_code": undoc_dead,
        "path_examples": [[str(n) for n in p] for p in paths[:15]]
    }
    
    out_path = '/tmp/team4_rrea_report.json'
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Summary
    print("\n" + "=" * 70)
    print("RREA ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"\n  📊 Shannon Entropy Distribution:")
    for band, count in report["entropy_distribution"]["shannon"].items():
        print(f"     {band}: {count}")
    print(f"\n  📊 Ping Entropy Distribution:")
    for band, count in report["entropy_distribution"]["ping"].items():
        print(f"     {band}: {count}")
    print(f"\n  🔴 CRITICAL FINDINGS:")
    print(f"     Dead code (unreachable): {len(dead)}")
    print(f"     Undocumented chokepoints: {len(undoc_chokepoints)}")
    print(f"     Shadow dependencies: {len(shadow)}")
    if undoc_chokepoints:
        print(f"\n  ⚠️  TOP UNDOCUMENTED CHOKEPOINTS:")
        for item in undoc_chokepoints[:10]:
            print(f"     {item['symbol']} (combined H={item['combined_entropy']}, "
                  f"shannon={item['shannon_entropy']}, ping={item['ping_entropy']})")
    if dead:
        print(f"\n  💀 DEAD CODE SAMPLES:")
        for sym in sorted(dead)[:10]:
            print(f"     {sym}")
    
    print(f"\n  Report: {out_path}")


if __name__ == '__main__':
    main()
