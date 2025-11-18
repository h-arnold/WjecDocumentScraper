#!/usr/bin/env python3
"""Find import cycles among local 'src' modules."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

modules = {}


def module_name_from_path(p: Path) -> str:
    rel = p.relative_to(SRC)
    parts = rel.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


for p in SRC.rglob("*.py"):
    if p.name.startswith("_"):
        continue
    try:
        code = p.read_text()
    except Exception:
        continue
    try:
        tree = ast.parse(code)
    except SyntaxError:
        continue
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                name = n.name
                if name.startswith("src."):
                    imports.add(name[4:])
        if isinstance(node, ast.ImportFrom):
            mod = node.module
            if not mod:
                continue
            if mod.startswith("src."):
                imports.add(mod[4:])
            elif mod.startswith("src"):
                imports.add(mod[3:])
    modules[module_name_from_path(p)] = imports

# Build graph

from collections import defaultdict

graph = defaultdict(set)
for m, deps in modules.items():
    for d in deps:
        graph[m].add(d)

# Detect cycles using DFS

visited = set()
stack = []
cycles = set()


def dfs(node, path):
    if node in path:
        cycle = path[path.index(node) :] + [node]
        cycles.add(tuple(cycle))
        return
    if node in visited:
        return
    visited.add(node)
    for n in graph.get(node, ()):
        dfs(n, path + [node])


for node in graph:
    dfs(node, [])

print("Detected cycles:")
for c in cycles:
    print(" -> ".join(c))
print("Graph nodes: ", len(graph))
