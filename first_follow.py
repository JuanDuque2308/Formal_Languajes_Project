"""FIRST and FOLLOW sets -- Aho et al., Section 4.4.2.

Both are computed as fixed points: the rules of the book are applied over and
over until no set changes.
"""
from __future__ import annotations

from grammar import END, EPSILON, Grammar, is_nonterminal


def compute_first(g: Grammar) -> dict[str, set[str]]:
    """FIRST(X) for every grammar symbol X (Section 4.4.2, rules 1-3)."""
    first: dict[str, set[str]] = {}
    # Rule 1: if X is a terminal, FIRST(X) = {X}.
    for a in g.terminals:
        first[a] = {a}
    for A in g.nonterminals:
        first[A] = set()

    changed = True
    while changed:
        changed = False
        for p in g.productions:
            # Rules 2 and 3: X -> Y1 Y2 ... Yk (k = 0 is the epsilon-production).
            before = len(first[p.head])
            first[p.head] |= first_of_string(p.body, first)
            if len(first[p.head]) != before:
                changed = True
    return first


def first_of_string(symbols: tuple[str, ...] | list[str],
                    first: dict[str, set[str]]) -> set[str]:
    """FIRST(X1 X2 ... Xn) (end of Section 4.4.2).

    Add the non-epsilon symbols of FIRST(X1); if epsilon is in FIRST(X1) add
    those of FIRST(X2), and so on. Epsilon belongs to the result only if it is
    in FIRST(Xi) for every i (in particular, FIRST(epsilon) = {epsilon}).
    """
    result: set[str] = set()
    for X in symbols:
        fx = first[X]
        result |= fx - {EPSILON}
        if EPSILON not in fx:
            return result
    result.add(EPSILON)
    return result


def compute_follow(g: Grammar, first: dict[str, set[str]]) -> dict[str, set[str]]:
    """FOLLOW(A) for every nonterminal A (Section 4.4.2, rules 1-3)."""
    follow: dict[str, set[str]] = {A: set() for A in g.nonterminals}
    # Rule 1: $ is in FOLLOW(S).
    follow[g.start].add(END)

    changed = True
    while changed:
        changed = False
        for p in g.productions:
            for i, B in enumerate(p.body):
                if not is_nonterminal(B):
                    continue
                beta = p.body[i + 1:]
                first_beta = first_of_string(beta, first)
                before = len(follow[B])
                # Rule 2: A -> alpha B beta  =>  FIRST(beta) - {e} in FOLLOW(B).
                follow[B] |= first_beta - {EPSILON}
                # Rule 3: A -> alpha B, or A -> alpha B beta with e in FIRST(beta)
                #         =>  FOLLOW(A) in FOLLOW(B).
                if EPSILON in first_beta:
                    follow[B] |= follow[p.head]
                if len(follow[B]) != before:
                    changed = True
    return follow


def format_set(s: set[str]) -> str:
    """Terminals in ASCII order, then 'e' (if present), then '$' (if present).

    Note: a plain sorted() would put '$' (ASCII 36) first, so the two special
    symbols are taken out and appended at the end.
    """
    items = sorted(x for x in s if x not in (EPSILON, END))
    if EPSILON in s:
        items.append(EPSILON)
    if END in s:
        items.append(END)
    return "{" + ", ".join(items) + "}"


# The assignment says "one line per nonterminal ... for each of the two sets".
# GROUPED = all First lines, then all Follow lines. Set to False to print
# First(A), Follow(A), First(B), Follow(B), ... instead (ask the professor).
SETS_GROUPED = True


def sets_report(g: Grammar, first: dict[str, set[str]],
                follow: dict[str, set[str]]) -> list[str]:
    firsts = [f"First({A}) = {format_set(first[A])}" for A in g.nonterminals]
    follows = [f"Follow({A}) = {format_set(follow[A])}" for A in g.nonterminals]
    if SETS_GROUPED:
        return firsts + follows
    return [line for pair in zip(firsts, follows) for line in pair]
