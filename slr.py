"""SLR(1) parser -- Aho et al., Sections 4.5 and 4.6.

* LR(0) items, CLOSURE (Fig. 4.32), GOTO and the canonical collection of
  sets of LR(0) items (Fig. 4.33), Section 4.6.2.
* SLR-parsing table ACTION/GOTO: Algorithm 4.46, Section 4.6.4.
* LR-parsing algorithm: Algorithm 4.44, Section 4.6.3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from grammar import END, Grammar, Production, is_nonterminal
from ll1 import render_table

AUG_START = "S'"   # two characters: can never clash with an input nonterminal


@dataclass(frozen=True)
class Item:
    """An LR(0) item A -> alpha . beta: a production and a dot position."""

    prod: Production
    dot: int

    def next_symbol(self) -> str | None:
        b = self.prod.body
        return b[self.dot] if self.dot < len(b) else None

    def __str__(self) -> str:
        b = list(self.prod.body)
        b.insert(self.dot, ".")
        return f"{self.prod.head} -> {' '.join(b)}"


# An ACTION entry: ("s", j) shift to state j, ("r", production) reduce,
# ("acc", None) accept.
Action = tuple[str, object]


def action_str(act: Action) -> str:
    kind, arg = act
    if kind == "s":
        return f"s{arg}"
    if kind == "r":
        return f"r({arg})"
    return "acc"


@dataclass
class Conflict:
    state: int
    symbol: str
    actions: list[Action]

    def __str__(self) -> str:
        kind = "reduce/reduce" if all(a[0] == "r" for a in self.actions) else "shift/reduce"
        return (f"state {self.state}, symbol {self.symbol}: {kind} "
                f"[{', '.join(action_str(a) for a in self.actions)}]")


@dataclass
class TraceStep:
    stack: str
    symbols: str
    input: str
    action: str


@dataclass
class ParseResult:
    accepted: bool
    reductions: list[Production] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)


class SLR:
    def __init__(self, g: Grammar, follow: dict[str, set[str]]):
        self.g, self.follow = g, follow
        # Augmented grammar G': new start symbol S' and production S' -> S.
        self.aug = Production(-1, AUG_START, (g.start,))
        self.states: list[tuple[Item, ...]] = []        # items in closure order
        self.transitions: dict[tuple[int, str], int] = {}
        self._canonical_collection()
        self.action: dict[tuple[int, str], list[Action]] = {}
        self.goto_table: dict[tuple[int, str], int] = {}
        self._build_tables()
        self.conflicts = [Conflict(s, a, acts)
                          for (s, a), acts in sorted(self.action.items(),
                                                     key=lambda kv: (kv[0][0], kv[0][1]))
                          if len(acts) > 1]

    @property
    def is_slr1(self) -> bool:
        return not self.conflicts

    # ------------------------------------------------------------------
    # Section 4.6.2
    def closure(self, items: list[Item]) -> tuple[Item, ...]:
        """Fig. 4.32: repeat, for each item A -> alpha . B beta in J and each
        production B -> gamma, add B -> . gamma to J, until nothing is added."""
        J = list(items)
        seen = set(J)
        i = 0
        while i < len(J):                 # J grows while we scan it
            B = J[i].next_symbol()
            if B is not None and is_nonterminal(B):
                for p in self.g.by_head[B]:
                    it = Item(p, 0)
                    if it not in seen:
                        seen.add(it)
                        J.append(it)
            i += 1
        return tuple(J)

    def goto(self, I: tuple[Item, ...], X: str) -> tuple[Item, ...]:
        """GOTO(I, X): closure of all [A -> alpha X . beta] such that
        [A -> alpha . X beta] is in I."""
        kernel = [Item(it.prod, it.dot + 1) for it in I if it.next_symbol() == X]
        return self.closure(kernel) if kernel else ()

    def _canonical_collection(self) -> None:
        """Fig. 4.33: C = {CLOSURE({[S' -> . S]})}; repeat, for each set I in C
        and each grammar symbol X, add GOTO(I, X) if it is non-empty and new.

        States are numbered in BFS order and, inside a state, the symbols are
        tried in the order in which they first appear after a dot. This
        reproduces the numbering of Fig. 4.31 of the book."""
        index: dict[frozenset[Item], int] = {}
        I0 = self.closure([Item(self.aug, 0)])
        self.states.append(I0)
        index[frozenset(I0)] = 0
        i = 0
        while i < len(self.states):
            I = self.states[i]
            symbols: list[str] = []
            for it in I:
                X = it.next_symbol()
                if X is not None and X not in symbols:
                    symbols.append(X)
            for X in symbols:
                J = self.goto(I, X)
                key = frozenset(J)
                if key not in index:
                    index[key] = len(self.states)
                    self.states.append(J)
                self.transitions[(i, X)] = index[key]
            i += 1

    # ------------------------------------------------------------------
    # Section 4.6.4, Algorithm 4.46
    def _add(self, state: int, a: str, act: Action) -> None:
        cell = self.action.setdefault((state, a), [])
        if act not in cell:
            cell.append(act)

    def _build_tables(self) -> None:
        for i, I in enumerate(self.states):
            for it in I:
                a = it.next_symbol()
                if a is not None and not is_nonterminal(a):
                    # (a) [A -> alpha . a beta] in Ii and GOTO(Ii, a) = Ij
                    self._add(i, a, ("s", self.transitions[(i, a)]))
                elif a is None and it.prod.head != AUG_START:
                    # (b) [A -> alpha .] in Ii, A != S': reduce on FOLLOW(A)
                    for b in sorted(self.follow[it.prod.head]):
                        self._add(i, b, ("r", it.prod))
                elif a is None:
                    # (c) [S' -> S .] in Ii: ACTION[i, $] = accept
                    self._add(i, END, ("acc", None))
            # GOTO for nonterminals: GOTO(Ii, A) = Ij
            for A in self.g.nonterminals:
                if (i, A) in self.transitions:
                    self.goto_table[(i, A)] = self.transitions[(i, A)]

    # ------------------------------------------------------------------
    # Section 4.6.3, Algorithm 4.44
    def parse(self, tokens: list[str], want_trace: bool = False) -> ParseResult:
        """LR-parsing algorithm. The stack holds states; a parallel stack of
        grammar symbols is kept only to print the trace (Fig. 4.38).
        Returns the reductions performed: the rightmost derivation in reverse."""
        if any(t not in self.g.terminals for t in tokens):
            return ParseResult(False)
        w = tokens + [END]
        ip = 0
        states = [0]
        symbols: list[str] = []
        reductions: list[Production] = []
        trace: list[TraceStep] = []

        def log(text: str) -> None:
            if want_trace:
                trace.append(TraceStep(" ".join(map(str, states)), "".join(symbols),
                                       "".join(w[ip:]), text))

        while True:
            s, a = states[-1], w[ip]
            acts = self.action.get((s, a))
            if not acts:
                log("error")
                return ParseResult(False, reductions, trace)
            kind, arg = acts[0]
            if kind == "s":                         # shift
                log(f"shift {arg}")
                states.append(arg)                  # type: ignore[arg-type]
                symbols.append(a)
                ip += 1
            elif kind == "r":                       # reduce A -> beta
                p: Production = arg                 # type: ignore[assignment]
                log(f"reduce by {p}")
                if p.body:
                    del states[-len(p.body):]
                    del symbols[-len(p.body):]
                states.append(self.goto_table[(states[-1], p.head)])
                symbols.append(p.head)
                reductions.append(p)
            else:                                   # accept
                log("accept")
                return ParseResult(True, reductions, trace)

    # ------------------------------------------------------------------
    def automaton_lines(self) -> list[str]:
        out = []
        for i, I in enumerate(self.states):
            out.append(f"I{i}:")
            for it in I:
                out.append(f"    {it}")
            for (s, X), j in self.transitions.items():
                if s == i:
                    out.append(f"    goto({X}) = I{j}")
        return out

    def table_lines(self) -> list[str]:
        terms = self.g.terminals + [END]
        nts = self.g.nonterminals
        rows = [["state", *terms, *nts]]
        for i in range(len(self.states)):
            row = [str(i)]
            for a in terms:
                row.append(" | ".join(action_str(x) for x in self.action.get((i, a), [])))
            for A in nts:
                j = self.goto_table.get((i, A))
                row.append("" if j is None else str(j))
            rows.append(row)
        return render_table(rows)
