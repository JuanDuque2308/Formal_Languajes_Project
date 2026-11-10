"""Tests for Item 3: SDD validation, dependency graph, evaluation, circularity."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import analyze, parse_tree                       # noqa: E402
from grammar import grammar_from_text                      # noqa: E402
from sdd.depgraph import CircularSDD, evaluate              # noqa: E402
from sdd.my_sdd import GRAMMAR, SDD_BASE, TABLE, SYNTHESIZED, INHERITED  # noqa: E402
from sdd.my_sdd_circular import SDD_CIRCULAR                # noqa: E402
from sdd.spec import build_sdd, classify, symbol_names, validate  # noqa: E402

A = analyze(grammar_from_text(GRAMMAR))


def value(line, parser="T", sdd=SDD_BASE):
    root = parse_tree(A, line, parser)
    if root is None:
        return None
    evaluate(root, sdd)
    return root.attrs["val"], root.attrs["ok"]


class TestGrammarRequirements(unittest.TestCase):
    def test_g1_g2(self):
        g = A.g
        self.assertGreaterEqual(len(g.nonterminals), 3)
        self.assertGreaterEqual(len(g.productions), 6)
        self.assertTrue(A.ll1.is_ll1)
        self.assertTrue(A.slr.is_slr1)
        self.assertTrue(any("R" in p.body for p in g.by_head["R"]))  # recursive


class TestValidation(unittest.TestCase):
    def test_ours_is_valid(self):
        self.assertEqual(validate(SDD_BASE, A.g), [])
        self.assertEqual(validate(SDD_CIRCULAR, A.g), [])

    def test_classification(self):
        s, l, _ = classify(SDD_BASE, A.g)
        self.assertEqual((s, l), (False, True))
        s, l, _ = classify(SDD_CIRCULAR, A.g)
        self.assertEqual((s, l), (False, False))

    def _broken(self, key, specs, inherited=INHERITED):
        t = dict(TABLE)
        t[key] = specs
        return validate(build_sdd(GRAMMAR, SYNTHESIZED, inherited, t, "val", "x"), A.g)

    def test_missing_definition(self):
        errs = self._broken("R->e", [("R.val", ["R.acc"], lambda x: x, "")])
        self.assertTrue(any("R.ok is defined 0 times" in e for e in errs))

    def test_double_definition(self):
        errs = self._broken("R->e", [("R.val", ["R.acc"], lambda x: x, ""),
                                     ("R.val", ["R.acc"], lambda x: x, ""),
                                     ("R.ok", [], lambda: True, "")])
        self.assertTrue(any("R.val is defined 2 times" in e for e in errs))

    def test_wrong_target(self):
        # Defining an inherited attribute of the head is not allowed.
        errs = self._broken("R->e", [("R.val", ["R.acc"], lambda x: x, ""),
                                     ("R.ok", [], lambda: True, ""),
                                     ("R.acc", [], lambda: 0, "")])
        self.assertTrue(any("neither a synthesized" in e for e in errs))

    def test_inherited_on_start(self):
        errs = self._broken("R->e", TABLE["R->e"], inherited={**INHERITED, "S": {"x"}})
        self.assertTrue(any("must not have inherited" in e for e in errs))

    def test_symbol_names(self):
        g = grammar_from_text("2\nS -> N:N\nP -> (P)P e\n")
        names = {str(p): symbol_names(p) for p in g.productions}
        self.assertEqual(names["S -> N:N"], ["S", "N1", ":", "N2"])
        self.assertEqual(names["P -> (P)P"], ["P", "(", "P1", ")", "P2"])


class TestEvaluation(unittest.TestCase):
    def test_strings(self):
        cases = {
            "2:0": (0, True),            # shortest string of the language
            "8:17": (15, True),
            "2:1011": (11, True),
            "12:11": (13, True),          # multi-digit base
            "9:9": ("error: digit >= base", False),            # digit not smaller than its base
            "2:" + "1" * 60: (2 ** 60 - 1, True),   # deep recursion
        }
        for line, expected in cases.items():
            for parser in "TB":
                with self.subTest(line=line, parser=parser):
                    self.assertEqual(value(line, parser), expected)

    def test_not_in_language(self):
        for line in ["8", "8:", ":1", "8:1x", "e", "8::1"]:
            self.assertIsNone(parse_tree(A, line, "T"))
            self.assertIsNone(parse_tree(A, line, "B"))

    def test_same_tree_from_both_parsers(self):
        t1 = parse_tree(A, "10:123", "T")
        t2 = parse_tree(A, "10:123", "B")
        from sdd.tree import annotated_tree_lines
        self.assertEqual(annotated_tree_lines(t1), annotated_tree_lines(t2))

    def test_order_is_topological(self):
        root = parse_tree(A, "8:17", "T")
        graph, steps = evaluate(root, SDD_BASE)
        pos = {s.vertex: i for i, s in enumerate(steps)}
        self.assertEqual(len(pos), len(graph.vertices))
        for u, v in graph.edge_list():
            self.assertLess(pos[u], pos[v])

    def test_circular_detected(self):
        root = parse_tree(A, "8:17", "T")
        with self.assertRaises(CircularSDD) as ctx:
            evaluate(root, SDD_CIRCULAR)
        cycle = ctx.exception.cycle
        self.assertEqual(cycle[0], cycle[-1])
        g = ctx.exception.graph
        for u, v in zip(cycle, cycle[1:]):
            self.assertIn(v, g.edges[u])          # it really is a cycle


if __name__ == "__main__":
    unittest.main()
