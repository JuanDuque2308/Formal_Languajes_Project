"""Context-free grammar representation and reader.

Input format (Section 2.2 of the assignment):

    n
    <NT> -> <alt_1> <alt_2> ...

Conventions: nonterminals are upper-case letters, the start symbol is 'S',
terminals are single non-upper-case characters, 'e' stands for epsilon and
'$' is the end marker (neither of them is ever a terminal).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

EPSILON = "e"
END = "$"
START = "S"


def is_nonterminal(symbol: str) -> bool:
    """Grammar symbols of the input are single characters; 'S'' (augmented) is longer."""
    return symbol[:1].isupper()


@dataclass(frozen=True)
class Production:
    """A production head -> body. An epsilon-production has an empty body."""

    index: int            # position in Grammar.productions (augmented one: -1)
    head: str
    body: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.head} -> {''.join(self.body) if self.body else EPSILON}"

    @property
    def key(self) -> str:
        """Compact key used by the SDD tables, e.g. 'R->DR' or 'R->e'."""
        return f"{self.head}->{''.join(self.body) if self.body else EPSILON}"


@dataclass
class Grammar:
    productions: list[Production]
    nonterminals: list[str]           # alphabetical order
    terminals: list[str]              # ASCII order
    by_head: dict[str, list[Production]] = field(default_factory=dict)
    start: str = START

    @staticmethod
    def from_rules(rules: list[tuple[str, list[str]]]) -> "Grammar":
        """Build a grammar from [(head, [alternative, ...]), ...]."""
        productions: list[Production] = []
        by_head: dict[str, list[Production]] = {}
        terminals: set[str] = set()
        for head, alternatives in rules:
            by_head.setdefault(head, [])
            for alt in alternatives:
                body = () if alt == EPSILON else tuple(alt)
                p = Production(len(productions), head, body)
                productions.append(p)
                by_head[head].append(p)
                terminals.update(s for s in body if not is_nonterminal(s))
        return Grammar(
            productions=productions,
            nonterminals=sorted(by_head),
            terminals=sorted(terminals),
            by_head=by_head,
        )

    def __str__(self) -> str:
        lines = []
        for head in self.nonterminals:
            alts = [("".join(p.body) or EPSILON) for p in self.by_head[head]]
            lines.append(f"{head} -> {' '.join(alts)}")
        return "\n".join(lines)


class LineReader:
    """Reads lines one at a time; returns None at end of file.

    Trailing '\\n' and '\\r' are removed so that files with Windows line
    endings behave exactly like Unix ones.
    """

    def __init__(self, stream: Iterable[str]):
        self._it: Iterator[str] = iter(stream)

    def readline(self) -> str | None:
        try:
            return next(self._it).rstrip("\r\n")
        except StopIteration:
            return None


class GrammarError(ValueError):
    pass


def parse_rule_line(line: str) -> tuple[str, list[str]]:
    if "->" not in line:
        raise GrammarError(f"missing '->' in line: {line!r}")
    left, right = line.split("->", 1)
    head = left.strip()
    if len(head) != 1 or not head.isupper():
        raise GrammarError(f"invalid nonterminal: {head!r}")
    alternatives = right.split()
    if not alternatives:
        raise GrammarError(f"no alternatives for {head}")
    return head, alternatives


def read_grammar(reader: LineReader) -> Grammar:
    line = reader.readline()
    while line is not None and not line.strip():   # tolerate leading blank lines
        line = reader.readline()
    if line is None:
        raise GrammarError("empty input")
    n = int(line.strip())
    if n <= 0:
        raise GrammarError("n must be positive")
    rules = []
    for _ in range(n):
        line = reader.readline()
        if line is None:
            raise GrammarError("unexpected end of input while reading productions")
        rules.append(parse_rule_line(line))
    return Grammar.from_rules(rules)


def grammar_from_text(text: str) -> Grammar:
    return read_grammar(LineReader(text.splitlines()))


def tokenize(line: str) -> list[str]:
    """An input string is a sequence of one-character terminals.
    The line 'e' denotes the empty string."""
    s = line.strip()
    return [] if s == EPSILON else list(s)
