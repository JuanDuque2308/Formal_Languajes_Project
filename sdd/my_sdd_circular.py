"""Circularity experiment (Step 6 of the assignment).

Same SDD as my_sdd.py, but ONE rule is changed:

    N -> DR :   R.acc = D.v          (original)
    N -> DR :   R.acc = R.val + D.v  (mutated)

The SDD is still well formed (it passes the static validator: R.acc is still
an inherited attribute of a body symbol, defined exactly once), but now
R.acc depends on R.val, and R.val depends -- through the chain of R's down
to R -> e, where R.val = R.acc -- on R.acc again. Every parse tree has a
cycle in its dependency graph, and the evaluator must report it.
"""
from sdd import my_sdd
from sdd.spec import build_sdd

TABLE = dict(my_sdd.TABLE)
TABLE["N->DR"] = [
    ("R.base", ["N.base"], lambda b: b, "R.base = N.base"),
    ("R.acc", ["R.val", "D.v"], lambda val, v: val + v, "R.acc = R.val + D.v   <-- MUTATED"),
    ("N.val", ["R.val"], lambda v: v, "N.val = R.val"),
    ("N.ok", ["D.v", "N.base", "R.ok"], lambda v, b, ok: v < b and ok,
     "N.ok = (D.v < N.base) and R.ok"),
]

SDD_CIRCULAR = build_sdd(my_sdd.GRAMMAR, my_sdd.SYNTHESIZED, my_sdd.INHERITED, TABLE,
                         main_attr="val", name="number in an arbitrary base (circular)")
