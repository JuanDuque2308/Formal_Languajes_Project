"""Representation of a syntax-directed definition (SDD) as *data*.

Section 5.1.1 of the book: an SDD associates attributes with grammar symbols
and semantic rules with productions. Here each production (identified by its
key, e.g. 'R->DR') owns a list of `Rule`s; each rule says which attribute it
defines, which attributes it uses and which Python function computes it.
The evaluator (depgraph.py) never looks inside a particular SDD.

Attribute references use the book's naming: in a production the head is
written with its plain name and repeated symbols of the body get subscripts
1, 2, ... in left-to-right order. Examples:

    R -> D R      head 'R', body 'D', 'R1'
    P -> ( P ) P  head 'P', body '(', 'P1', ')', 'P2'
    S -> N : N    head 'S', body 'N1', ':', 'N2'
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from grammar import Grammar, Production, is_nonterminal

LEXVAL = "lexval"   # the only attribute of a terminal: the character itself


@dataclass(frozen=True)
class AttrRef:
    """Attribute `name` of the symbol at position `pos` of a production:
    0 = head, 1..k = symbols of the body."""

    pos: int
    name: str


@dataclass(frozen=True)
class Rule:
    target: AttrRef
    deps: tuple[AttrRef, ...]
    fn: Callable[..., Any]          # called with the values of deps, in order
    text: str = ""                  # the rule as written, for the report/output


@dataclass
class SDD:
    grammar_text: str                       # grammar in the format of Sec. 2.2
    synthesized: dict[str, set[str]]        # nonterminal -> synthesized attrs
    inherited: dict[str, set[str]]          # nonterminal -> inherited attrs
    rules: dict[str, list[Rule]] = field(default_factory=dict)  # prod key -> rules
    main_attr: str = "val"                  # main synthesized attribute of S
    name: str = "SDD"


# ----------------------------------------------------------------------
# Helper to write rules with the book's names instead of positions.

def symbol_names(p: Production) -> list[str]:
    """Names of the symbols of p: index 0 = head, then the body."""
    symbols = [p.head, *p.body]
    names = []
    for i, X in enumerate(symbols):
        if i > 0 and symbols.count(X) > 1:
            k = sum(1 for Y in symbols[1:i + 1] if Y == X)
            names.append(f"{X}{k}")
        else:
            names.append(X)
    return names


def resolve(p: Production, ref: str) -> AttrRef:
    """'R1.acc' -> AttrRef(position of R1 in p, 'acc')."""
    sym, _, attr = ref.rpartition(".")
    names = symbol_names(p)
    if sym not in names:
        raise SDDError(f"{p}: unknown symbol {sym!r} in {ref!r} (symbols: {names})")
    return AttrRef(names.index(sym), attr)


def make_rule(p: Production, target: str, deps: list[str],
              fn: Callable[..., Any], text: str = "") -> Rule:
    return Rule(resolve(p, target), tuple(resolve(p, d) for d in deps), fn,
                text or f"{target} = f({', '.join(deps)})")


class SDDError(ValueError):
    pass


RuleSpec = tuple[str, list[str], Callable[..., Any], str]   # target, deps, fn, text


def build_sdd(grammar_text: str, synthesized: dict[str, set[str]],
              inherited: dict[str, set[str]], table: dict[str, list[RuleSpec]],
              main_attr: str, name: str) -> SDD:
    """Turns a table {production key: [(target, deps, fn, text), ...]}, written
    with the book's symbol names, into an SDD with resolved positions."""
    from grammar import grammar_from_text
    g = grammar_from_text(grammar_text)
    prods = {p.key: p for p in g.productions}
    rules: dict[str, list[Rule]] = {}
    for key, specs in table.items():
        if key not in prods:
            raise SDDError(f"{key!r} is not a production of the SDD's grammar")
        rules[key] = [make_rule(prods[key], t, d, f, txt) for t, d, f, txt in specs]
    return SDD(grammar_text, synthesized, inherited, rules, main_attr, name)


# ----------------------------------------------------------------------
# Static validation (Section 5.1.1 and Step 2 of the assignment).

def validate(sdd: SDD, g: Grammar) -> list[str]:
    """Returns the list of problems (empty = well-formed). Checks that:
      * S has no inherited attributes;
      * the SDD only talks about productions of the grammar;
      * each rule defines a synthesized attribute of the head or an
        inherited attribute of a nonterminal of the body;
      * each rule only uses attributes of the symbols of its production
        (synthesized/inherited declared for that symbol, or lexval);
      * in every production, every synthesized attribute of the head and
        every inherited attribute of each body nonterminal is defined
        exactly once."""
    errors: list[str] = []
    if sdd.inherited.get(g.start):
        errors.append(f"start symbol {g.start} must not have inherited attributes")
    keys = {p.key: p for p in g.productions}
    for k in sdd.rules:
        if k not in keys:
            errors.append(f"rules given for {k!r}, which is not a production of the grammar")

    def attrs_of(X: str) -> set[str]:
        if not is_nonterminal(X):
            return {LEXVAL}
        return sdd.synthesized.get(X, set()) | sdd.inherited.get(X, set())

    for p in g.productions:
        symbols = [p.head, *p.body]
        defined: dict[tuple[int, str], int] = {}
        for r in sdd.rules.get(p.key, []):
            t = r.target
            if not 0 <= t.pos < len(symbols):
                errors.append(f"{p}: target position {t.pos} out of range")
                continue
            X = symbols[t.pos]
            ok = (t.pos == 0 and t.name in sdd.synthesized.get(X, set())) or \
                 (t.pos > 0 and is_nonterminal(X) and t.name in sdd.inherited.get(X, set()))
            if not ok:
                errors.append(f"{p}: rule '{r.text}' defines {X}.{t.name}, which is neither a "
                              f"synthesized attribute of the head nor an inherited attribute "
                              f"of a body nonterminal")
            defined[(t.pos, t.name)] = defined.get((t.pos, t.name), 0) + 1
            for d in r.deps:
                if not 0 <= d.pos < len(symbols) or d.name not in attrs_of(symbols[d.pos]):
                    errors.append(f"{p}: rule '{r.text}' uses an attribute that its "
                                  f"production does not have ({d})")
        required = [(0, a) for a in sorted(sdd.synthesized.get(p.head, set()))]
        for i, X in enumerate(p.body, start=1):
            if is_nonterminal(X):
                required += [(i, a) for a in sorted(sdd.inherited.get(X, set()))]
        names = symbol_names(p)
        for pos, a in required:
            n = defined.get((pos, a), 0)
            if n != 1:
                errors.append(f"{p}: {names[pos]}.{a} is defined {n} times (must be exactly once)")
    return errors


# ----------------------------------------------------------------------
# Classification (Sections 5.2.3 and 5.2.4). Used to double-check the
# classification argued by hand in the report.

def classify(sdd: SDD, g: Grammar) -> tuple[bool, bool, list[str]]:
    """Returns (is_S_attributed, is_L_attributed, reasons).

    S-attributed: every attribute is synthesized.
    L-attributed: every attribute is synthesized, or inherited such that, in
    a rule of A -> X1 ... Xn defining Xi.a, it only uses (a) inherited
    attributes of the head A, (b) attributes of X1 ... X(i-1), or (c)
    attributes of Xi itself (the book adds: without cycles among them)."""
    reasons: list[str] = []
    s_attr = not any(sdd.inherited.get(X) for X in g.nonterminals)
    if not s_attr:
        reasons.append("not S-attributed: there are inherited attributes")
    l_attr = True
    for p in g.productions:
        names = symbol_names(p)
        for r in sdd.rules.get(p.key, []):
            i = r.target.pos
            if i == 0:
                continue                      # synthesized attribute: always fine
            Xi = [p.head, *p.body][i]
            for d in r.deps:
                # (c) attributes of Xi itself are only allowed if they cannot
                # create a cycle. A synthesized attribute of Xi may depend on
                # its inherited ones, so we conservatively only accept other
                # inherited attributes of Xi.
                ok = (d.pos == 0 and d.name in sdd.inherited.get(p.head, set())) \
                     or (1 <= d.pos < i) \
                     or (d.pos == i and d.name in sdd.inherited.get(Xi, set()))
                if not ok:
                    l_attr = False
                    what = "a synthesized attribute of the head" if d.pos == 0 \
                        else "a synthesized attribute of the same symbol (may be circular)" \
                        if d.pos == i else "a symbol to its right"
                    reasons.append(f"not L-attributed: in {p}, {names[i]}.{r.target.name} "
                                   f"uses {names[d.pos]}.{d.name}, {what}")
    return s_attr, l_attr, reasons
