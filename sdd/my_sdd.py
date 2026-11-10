"""Our SDD: value of a number written in an arbitrary base.

An input  b:d1d2...dk  means "the digits d1...dk read in base b", where the
base b itself is written in decimal. Examples:  2:1011 -> 11,  8:17 -> 15,
12:11 -> 13. S.ok is false if some digit is not smaller than its base.

Grammar (4 nonterminals, 14 productions, R is recursive; LL(1) and SLR(1)):

    S -> N:N
    N -> DR
    R -> DR e
    D -> 0 1 2 3 4 5 6 7 8 9

Attributes
    N.base  inherited    int   base in which the digits of N are read
    R.base  inherited    int   same base, passed down the list of digits
    R.acc   inherited    int   value of the digits to the left of R (Horner)
    D.v     synthesized  int   numeric value of the digit
    R.val   synthesized  int   value of the whole digit list
    N.val   synthesized  int   value of the number
    R.ok    synthesized  bool  all digits of the list are < base
    N.ok    synthesized  bool  all digits of N are < base
    S.val   synthesized  int   value of the number, or an error message if
                               some digit is not smaller than its base (main attribute)
    S.ok    synthesized  bool  both numbers are well formed

Changing the SDD only requires changing this file: the evaluator knows
nothing about it.
"""
from sdd.spec import RuleSpec, build_sdd

GRAMMAR = """4
S -> N:N
N -> DR
R -> DR e
D -> 0 1 2 3 4 5 6 7 8 9
"""

SYNTHESIZED = {"S": {"val", "ok"}, "N": {"val", "ok"}, "R": {"val", "ok"}, "D": {"v"}}
INHERITED = {"N": {"base"}, "R": {"base", "acc"}}

TABLE: dict[str, list[RuleSpec]] = {
    "S->N:N": [
        ("N1.base", [], lambda: 10, "N1.base = 10"),
        ("N2.base", ["N1.val"], lambda v: v, "N2.base = N1.val"),
        ("S.val", ["N2.val", "N1.ok", "N2.ok"],
         lambda v, ok1, ok2: v if ok1 and ok2 else "error: digit >= base",
         "S.val = N2.val if N1.ok and N2.ok else error"),
        ("S.ok", ["N1.ok", "N2.ok"], lambda a, b: a and b, "S.ok = N1.ok and N2.ok"),
    ],
    "N->DR": [
        ("R.base", ["N.base"], lambda b: b, "R.base = N.base"),
        ("R.acc", ["D.v"], lambda v: v, "R.acc = D.v"),
        ("N.val", ["R.val"], lambda v: v, "N.val = R.val"),
        ("N.ok", ["D.v", "N.base", "R.ok"], lambda v, b, ok: v < b and ok,
         "N.ok = (D.v < N.base) and R.ok"),
    ],
    "R->DR": [
        ("R1.base", ["R.base"], lambda b: b, "R1.base = R.base"),
        ("R1.acc", ["R.acc", "R.base", "D.v"], lambda acc, b, v: acc * b + v,
         "R1.acc = R.acc * R.base + D.v"),
        ("R.val", ["R1.val"], lambda v: v, "R.val = R1.val"),
        ("R.ok", ["D.v", "R.base", "R1.ok"], lambda v, b, ok: v < b and ok,
         "R.ok = (D.v < R.base) and R1.ok"),
    ],
    "R->e": [
        ("R.val", ["R.acc"], lambda acc: acc, "R.val = R.acc"),
        ("R.ok", [], lambda: True, "R.ok = true"),
    ],
}
for _d in "0123456789":
    TABLE[f"D->{_d}"] = [(f"D.v", [f"{_d}.lexval"], lambda c: int(c),
                          f"D.v = int({_d}.lexval)")]

SDD_BASE = build_sdd(GRAMMAR, SYNTHESIZED, INHERITED, TABLE, main_attr="val",
                     name="number in an arbitrary base")
