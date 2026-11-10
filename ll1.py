"""LL(1) test, predictive parsing table and table-driven predictive parser.

* LL(1) condition: beginning of Section 4.4.3.
* Table construction: Algorithm 4.31.
* Parsing: Algorithm 4.34 (non-recursive, stack + table), Section 4.4.4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from first_follow import first_of_string
from grammar import END, EPSILON, Grammar, Production, is_nonterminal


@dataclass
class TraceStep:
    matched: str
    stack: str
    input: str
    action: str


@dataclass
class ParseResult:
    accepted: bool
    derivation: list[Production] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)


class LL1:
    def __init__(self, g: Grammar, first: dict[str, set[str]],
                 follow: dict[str, set[str]]):
        self.g, self.first, self.follow = g, first, follow
        self.violations: list[str] = self._check_condition()
        self.table: dict[tuple[str, str], list[Production]] = self._build_table()
        self.conflicts = {k: v for k, v in self.table.items() if len(v) > 1}

    @property
    def is_ll1(self) -> bool:
        # The two checks agree on every grammar whose nonterminals are all
        # reachable from S. (For an unreachable A with two e-alternatives,
        # FOLLOW(A) is empty, so condition 2 fails but the table has no
        # conflict.) We follow the book's definition and require both.
        return not self.violations and not self.conflicts

    # ------------------------------------------------------------------
    def _check_condition(self) -> list[str]:
        """A grammar is LL(1) iff for every pair of distinct productions
        A -> alpha | beta (Section 4.4.3):
          1. FIRST(alpha) and FIRST(beta) share no terminal;
          2. at most one of alpha and beta derives the empty string;
          3. if beta =>* e, FIRST(alpha) and FOLLOW(A) are disjoint
             (and symmetrically).
        Returns a list of human-readable violations (empty = LL(1))."""
        violations = []
        for A in self.g.nonterminals:
            for p, q in combinations(self.g.by_head[A], 2):
                fa = first_of_string(p.body, self.first)
                fb = first_of_string(q.body, self.first)
                common = (fa & fb) - {EPSILON}
                if common:
                    violations.append(f"(1) FIRST({p}) and FIRST({q}) share {sorted(common)}")
                if EPSILON in fa and EPSILON in fb:
                    violations.append(f"(2) both {p} and {q} derive e")
                for x, fx, y, fy in ((p, fa, q, fb), (q, fb, p, fa)):
                    if EPSILON in fy:
                        common = (fx - {EPSILON}) & self.follow[A]
                        if common:
                            violations.append(
                                f"(3) {y} derives e and FIRST({x}) meets FOLLOW({A}) in {sorted(common)}")
        return violations

    def _build_table(self) -> dict[tuple[str, str], list[Production]]:
        """Algorithm 4.31: for each production A -> alpha,
        1. for each terminal a in FIRST(alpha), add A -> alpha to M[A, a];
        2. if e in FIRST(alpha), for each b in FOLLOW(A) (terminal or $),
           add A -> alpha to M[A, b].
        Entries with more than one production are conflicts."""
        table: dict[tuple[str, str], list[Production]] = {}
        for p in self.g.productions:
            f = first_of_string(p.body, self.first)
            targets = f - {EPSILON}
            if EPSILON in f:
                targets |= self.follow[p.head]
            for a in sorted(targets):
                cell = table.setdefault((p.head, a), [])
                if p not in cell:
                    cell.append(p)
        return table

    # ------------------------------------------------------------------
    def parse(self, tokens: list[str], want_trace: bool = False) -> ParseResult:
        """Algorithm 4.34: table-driven predictive parsing.

        The stack initially holds S on top of $. The derivation returned is the
        leftmost derivation (the productions output by the algorithm)."""
        if any(t not in self.g.terminals for t in tokens):
            return ParseResult(False)
        w = tokens + [END]
        ip = 0
        stack = [END, self.g.start]          # top of stack = end of the list
        derivation: list[Production] = []
        trace: list[TraceStep] = []

        def log(action: str) -> None:
            if want_trace:
                trace.append(TraceStep("".join(w[:ip]), " ".join(reversed(stack)),
                                       "".join(w[ip:]), action))

        X = stack[-1]
        while X != END:                       # stack is not empty
            a = w[ip]
            if X == a:                        # match a terminal
                log(f"match {a}")
                stack.pop()
                ip += 1
            elif not is_nonterminal(X):       # X is a terminal different from a
                log("error")
                return ParseResult(False, derivation, trace)
            elif not self.table.get((X, a)):  # M[X, a] is an error entry
                log("error")
                return ParseResult(False, derivation, trace)
            else:                             # M[X, a] = X -> Y1 Y2 ... Yk
                p = self.table[(X, a)][0]
                log(f"output {p}")
                derivation.append(p)
                stack.pop()
                stack.extend(reversed(p.body))   # Y1 ends on top
            X = stack[-1]
        accepted = w[ip] == END
        log("accept" if accepted else "error")
        return ParseResult(accepted, derivation, trace)

    # ------------------------------------------------------------------
    def table_lines(self) -> list[str]:
        cols = self.g.terminals + [END]
        header = ["", *cols]
        rows = [header]
        for A in self.g.nonterminals:
            row = [A]
            for a in cols:
                cell = self.table.get((A, a), [])
                row.append(" | ".join(str(p) for p in cell))
            rows.append(row)
        return render_table(rows)


def render_table(rows: list[list[str]]) -> list[str]:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    out = []
    for k, r in enumerate(rows):
        out.append("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        if k == 0:
            out.append("  ".join("-" * w for w in widths))
    return out
