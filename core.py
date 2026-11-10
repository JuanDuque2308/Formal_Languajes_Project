"""Facade that runs Items 1-3 on a grammar and exports the state as JSON.

Used by main.py (CLI) and by the visualizer (viz/server.py). The CLI never
depends on the visualizer; the visualizer only consumes this JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from first_follow import compute_first, compute_follow, format_set
from grammar import END, EPSILON, Grammar, Production, tokenize
from ll1 import LL1
from sdd.depgraph import CircularSDD, evaluate
from sdd.spec import SDD, classify, symbol_names, validate
from sdd.tree import Node, build_tree, preorder
from slr import SLR, action_str


@dataclass
class Analysis:
    g: Grammar
    first: dict[str, set[str]]
    follow: dict[str, set[str]]
    ll1: LL1
    slr: SLR


def analyze(g: Grammar) -> Analysis:
    first = compute_first(g)
    follow = compute_follow(g, first)
    return Analysis(g, first, follow, LL1(g, first, follow), SLR(g, follow))


def parse_tree(a: Analysis, line: str, parser: str) -> Node | None:
    """Parse with our own parser ('T' = LL(1), 'B' = SLR(1)) and build the tree."""
    tokens = tokenize(line)
    if parser == "T":
        r = a.ll1.parse(tokens)
        return build_tree(r.derivation, tokens, "leftmost") if r.accepted else None
    r = a.slr.parse(tokens)
    return build_tree(r.reductions, tokens, "reductions") if r.accepted else None


# ----------------------------------------------------------------------
# JSON export

def _prod(p: Production) -> str:
    return str(p)


def analysis_json(a: Analysis) -> dict[str, Any]:
    g = a.g
    order = lambda s: format_set(s)[1:-1].split(", ") if s else []  # noqa: E731
    return {
        "grammar": str(g),
        "nonterminals": g.nonterminals,
        "terminals": g.terminals,
        "productions": [_prod(p) for p in g.productions],
        "first": {A: order(a.first[A]) for A in g.nonterminals},
        "follow": {A: order(a.follow[A]) for A in g.nonterminals},
        "ll1": {
            "is_ll1": a.ll1.is_ll1,
            "violations": a.ll1.violations,
            "columns": g.terminals + [END],
            "table": {f"{A},{t}": [_prod(p) for p in ps] for (A, t), ps in a.ll1.table.items()},
        },
        "slr": {
            "is_slr1": a.slr.is_slr1,
            "conflicts": [str(c) for c in a.slr.conflicts],
            "states": [[str(it) for it in I] for I in a.slr.states],
            "transitions": [[i, X, j] for (i, X), j in a.slr.transitions.items()],
            "columns": g.terminals + [END],
            "action": {f"{i},{t}": [action_str(x) for x in acts]
                       for (i, t), acts in a.slr.action.items()},
            "goto": {f"{i},{A}": j for (i, A), j in a.slr.goto_table.items()},
        },
    }


def sdd_json(sdd: SDD, a: Analysis, line: str, parser: str) -> dict[str, Any]:
    """Parse tree, dependency graph, evaluation order and values (or cycle)."""
    out: dict[str, Any] = {"sdd": sdd.name, "string": line, "parser": parser}
    errors = validate(sdd, a.g)
    s_attr, l_attr, reasons = classify(sdd, a.g)
    out["validation_errors"] = errors
    out["attributes"] = {
        "synthesized": {X: sorted(v) for X, v in sdd.synthesized.items()},
        "inherited": {X: sorted(v) for X, v in sdd.inherited.items()},
    }
    out["classification"] = {"S": s_attr, "L": l_attr, "reasons": reasons}
    out["rules"] = {}
    for p in a.g.productions:
        out["rules"][str(p)] = [r.text for r in sdd.rules.get(p.key, [])]
    if errors:
        return out
    root = parse_tree(a, line, parser)
    out["accepted"] = root is not None
    if root is None:
        return out
    nodes = []
    for n, depth in preorder(root):
        nodes.append({"id": n.id, "symbol": n.symbol, "depth": depth,
                      "production": str(n.production) if n.production else None,
                      "children": [c.id for c in n.children]})
    out["tree"] = nodes
    try:
        graph, steps = evaluate(root, sdd)
        out["order"] = [{"vertex": list(s.vertex), "name": graph.name(s.vertex),
                         "value": repr(s.value) if isinstance(s.value, str) else s.value,
                         "rule": s.rule_text, "production": s.production} for s in steps]
        out["cycle"] = []
        out["result"] = root.attrs.get(sdd.main_attr)
    except CircularSDD as exc:
        graph = exc.graph
        out["order"] = []
        out["cycle"] = [list(v) for v in exc.cycle]
        out["error"] = str(exc)
    out["vertices"] = [list(v) for v in graph.vertices]
    out["edges"] = [[list(u), list(v)] for u, v in graph.edge_list()]
    return out


__all__ = ["Analysis", "analyze", "parse_tree", "analysis_json", "sdd_json",
           "symbol_names", "EPSILON"]
