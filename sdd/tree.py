"""Parse trees built from the output of our own parsers.

* LL(1) (Algorithm 4.34) outputs a leftmost derivation: the productions in
  the order a preorder, left-to-right construction of the tree uses them.
* SLR(1) (Algorithm 4.44) outputs reductions, i.e. a rightmost derivation in
  reverse. Reversed, it is the order of a preorder construction that expands
  children right-to-left.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grammar import EPSILON, Production, is_nonterminal
from sdd.spec import LEXVAL


@dataclass(eq=False)
class Node:
    symbol: str
    production: Production | None = None   # only for nonterminals
    children: list["Node"] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)
    id: int = -1

    @property
    def label(self) -> str:
        return f"{self.symbol}#{self.id}"

    @property
    def is_epsilon(self) -> bool:
        return self.symbol == EPSILON and self.production is None


def build_tree(derivation: list[Production], tokens: list[str], kind: str) -> Node:
    """kind = 'leftmost' (LL(1) derivation) or 'reductions' (SLR(1) output)."""
    if kind == "leftmost":
        prods = iter(derivation)
        toks = iter(tokens)
        right_to_left = False
    elif kind == "reductions":
        prods = iter(reversed(derivation))     # rightmost derivation
        toks = iter(reversed(tokens))          # leaves are met right-to-left
        right_to_left = True
    else:
        raise ValueError(kind)

    def build(symbol: str) -> Node:
        if not is_nonterminal(symbol):
            t = next(toks)
            assert t == symbol, f"leaf {symbol!r} does not match token {t!r}"
            return Node(symbol, attrs={LEXVAL: t})
        p = next(prods)
        assert p.head == symbol, f"expected a production of {symbol}, got {p}"
        node = Node(symbol, p)
        if not p.body:
            node.children = [Node(EPSILON)]    # epsilon leaf, no attributes
        elif right_to_left:
            node.children = [build(X) for X in reversed(p.body)][::-1]
        else:
            node.children = [build(X) for X in p.body]
        return node

    root = build(derivation[0].head if kind == "leftmost" else derivation[-1].head)
    number_nodes(root)
    return root


def number_nodes(root: Node) -> None:
    """Give every node an id in preorder (root = 0)."""
    counter = 0
    stack = [root]
    while stack:
        n = stack.pop()
        n.id = counter
        counter += 1
        stack.extend(reversed(n.children))


def preorder(root: Node):
    stack = [(root, 0)]
    while stack:
        n, depth = stack.pop()
        yield n, depth
        stack.extend((c, depth + 1) for c in reversed(n.children))


def format_value(v: Any) -> str:
    return repr(v) if isinstance(v, str) else str(v)


def annotated_tree_lines(root: Node) -> list[str]:
    """One node per line, indented by depth, with its attributes."""
    out = []
    for n, depth in preorder(root):
        line = "  " * depth + n.label
        if n.production is not None:
            line += f"  [{n.production}]"
        if n.attrs:
            line += "  " + " ".join(f"{k}={format_value(v)}" for k, v in sorted(n.attrs.items()))
        out.append(line)
    return out
