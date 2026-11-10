"""Dependency graph of an annotated parse tree and its evaluation.

* Section 5.2.1: one vertex per attribute of each node; for each rule
  instantiated at a node, an edge from every attribute it uses to the
  attribute it defines.
* Section 5.2.2: any topological sort of the graph is a valid evaluation
  order; if the graph has a cycle there is no such order (circular SDD).

The evaluator is generic: everything it knows about the SDD comes from the
`SDD` data structure (sdd/spec.py).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any

from sdd.spec import LEXVAL, SDD, Rule
from sdd.tree import Node, preorder

Vertex = tuple[int, str]            # (node id, attribute name)


@dataclass
class DepGraph:
    nodes: dict[int, Node]
    vertices: list[Vertex] = field(default_factory=list)
    edges: dict[Vertex, list[Vertex]] = field(default_factory=dict)   # from -> [to]
    # vertex -> (rule, node where the rule is instantiated). Leaves' lexval
    # vertices have no rule: their value is given by the scanner.
    rule_of: dict[Vertex, tuple[Rule, Node]] = field(default_factory=dict)

    def add_vertex(self, v: Vertex) -> None:
        if v not in self.edges:
            self.edges[v] = []
            self.vertices.append(v)

    def add_edge(self, u: Vertex, v: Vertex) -> None:
        self.add_vertex(u)
        self.add_vertex(v)
        self.edges[u].append(v)

    def name(self, v: Vertex) -> str:
        return f"{self.nodes[v[0]].label}.{v[1]}"

    def edge_list(self) -> list[tuple[Vertex, Vertex]]:
        return [(u, v) for u in self.vertices for v in self.edges[u]]


class CircularSDD(Exception):
    def __init__(self, graph: DepGraph, cycle: list[Vertex]):
        self.graph, self.cycle = graph, cycle
        super().__init__("SDD is circular: " + " -> ".join(graph.name(v) for v in cycle))


def build_graph(root: Node, sdd: SDD) -> DepGraph:
    g = DepGraph(nodes={n.id: n for n, _ in preorder(root)})
    for n, _ in preorder(root):
        if n.production is None:
            if LEXVAL in n.attrs:                 # terminal leaf: value already known
                g.add_vertex((n.id, LEXVAL))
            continue
        symbols = [n, *[c for c in n.children if not c.is_epsilon]]
        for rule in sdd.rules.get(n.production.key, []):
            target = (symbols[rule.target.pos].id, rule.target.name)
            g.add_vertex(target)
            g.rule_of[target] = (rule, n)
            for d in rule.deps:
                g.add_edge((symbols[d.pos].id, d.name), target)
    return g


def topological_order(g: DepGraph) -> list[Vertex]:
    """Kahn's algorithm. Among the vertices ready at each moment we always
    take the smallest (node id, attribute), so the order is deterministic.
    Raises CircularSDD with one concrete cycle if the graph is not a DAG."""
    indeg = {v: 0 for v in g.vertices}
    for u in g.vertices:
        for v in g.edges[u]:
            indeg[v] += 1
    ready = [v for v in g.vertices if indeg[v] == 0]
    heapq.heapify(ready)
    order: list[Vertex] = []
    while ready:
        u = heapq.heappop(ready)
        order.append(u)
        for v in g.edges[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, v)
    if len(order) < len(g.vertices):
        remaining = {v for v in g.vertices if indeg[v] > 0}
        raise CircularSDD(g, find_cycle(g, remaining))
    return order


def find_cycle(g: DepGraph, candidates: set[Vertex]) -> list[Vertex]:
    """Iterative DFS restricted to the vertices Kahn could not remove.
    Returns a cycle v0 -> v1 -> ... -> v0 (first vertex repeated at the end)."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {v: WHITE for v in candidates}
    for start in sorted(candidates):
        if color[start] != WHITE:
            continue
        path = [start]
        iters = [iter(g.edges[start])]
        color[start] = GREY
        while path:
            for v in iters[-1]:
                if v not in candidates:
                    continue
                if color[v] == GREY:                 # back edge: cycle found
                    return path[path.index(v):] + [v]
                if color[v] == WHITE:
                    color[v] = GREY
                    path.append(v)
                    iters.append(iter(g.edges[v]))
                    break
            else:
                color[path.pop()] = BLACK
                iters.pop()
    return []


@dataclass
class EvalStep:
    vertex: Vertex
    value: Any
    rule_text: str          # '' for lexval (given by the scanner)
    production: str = ""    # production of the node where the rule is instantiated


def evaluate(root: Node, sdd: SDD) -> tuple[DepGraph, list[EvalStep]]:
    """Builds the dependency graph, sorts it topologically and evaluates the
    attributes in that order (never in a fixed recursive order)."""
    g = build_graph(root, sdd)
    order = topological_order(g)
    steps: list[EvalStep] = []
    for v in order:
        node = g.nodes[v[0]]
        if v not in g.rule_of:
            if v[1] != LEXVAL:
                raise ValueError(f"attribute {g.name(v)} is used but no rule defines it")
            steps.append(EvalStep(v, node.attrs[LEXVAL], ""))
            continue
        rule, at = g.rule_of[v]
        symbols = [at, *[c for c in at.children if not c.is_epsilon]]
        args = [symbols[d.pos].attrs[d.name] for d in rule.deps]
        node.attrs[v[1]] = rule.fn(*args)
        steps.append(EvalStep(v, node.attrs[v[1]], rule.text, str(at.production)))
    return g, steps
