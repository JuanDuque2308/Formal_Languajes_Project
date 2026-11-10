"""Tests for Items 1 and 2, checked against the book and the assignment.

Run from the project root:  python3 -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import analyze                                   # noqa: E402
from first_follow import format_set, sets_report            # noqa: E402
from grammar import grammar_from_text, tokenize             # noqa: E402

# Grammar (4.28) of the book with E -> S, E' -> A, T' -> B and id -> i.
BOOK_428 = """5
S -> TA
A -> +TA e
T -> FB
B -> *FB e
F -> (S) i
"""
# Grammar (4.1) of the book with E -> S and id -> i (= Example 1 of the assignment).
BOOK_41 = """3
S -> S+T T
T -> T*F F
F -> (S) i
"""
EX2 = """3
S -> AB
A -> aA d
B -> bBc e
"""
EX3 = """1
S -> SS a
"""
LL_NOT_SLR = """3
S -> AaAb BbBa
A -> e
B -> e
"""


def run_main(stdin: str, *args: str) -> str:
    r = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), *args],
                       input=stdin, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


class TestFirstFollow(unittest.TestCase):
    def test_book_example_4_30(self):
        """Example 4.30: FIRST and FOLLOW of grammar (4.28)."""
        a = analyze(grammar_from_text(BOOK_428))
        self.assertEqual(a.first["F"], {"(", "i"})
        self.assertEqual(a.first["T"], {"(", "i"})
        self.assertEqual(a.first["S"], {"(", "i"})
        self.assertEqual(a.first["A"], {"+", "e"})
        self.assertEqual(a.first["B"], {"*", "e"})
        self.assertEqual(a.follow["S"], {")", "$"})
        self.assertEqual(a.follow["A"], {")", "$"})
        self.assertEqual(a.follow["T"], {"+", ")", "$"})
        self.assertEqual(a.follow["B"], {"+", ")", "$"})
        self.assertEqual(a.follow["F"], {"+", "*", ")", "$"})

    def test_format_order(self):
        # '$' must go last although it is the smallest in ASCII.
        self.assertEqual(format_set({"$", "e", "b", "a", "(", "1"}), "{(, 1, a, b, e, $}")
        self.assertEqual(format_set(set()), "{}")

    def test_sets_output_example2(self):
        out = run_main(EX2 + "Q\n", "--sets").splitlines()
        self.assertEqual(out[:6], [
            "First(A) = {a, d}", "First(B) = {b, e}", "First(S) = {a, d}",
            "Follow(A) = {b, $}", "Follow(B) = {c, $}", "Follow(S) = {$}"])
        self.assertEqual(out[6], "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):")

    def test_follow_needs_several_passes(self):
        # FOLLOW(C) depends on FOLLOW(B), which depends on FOLLOW(A),
        # given in the "wrong" order for a single pass.
        g = grammar_from_text("4\nC -> c\nB -> bC\nA -> aB\nS -> Ax\n")
        a = analyze(g)
        self.assertEqual(a.follow["C"], {"x"})

    def test_all_epsilon(self):
        a = analyze(grammar_from_text("2\nS -> AA\nA -> e\n"))
        self.assertEqual(a.first["S"], {"e"})
        self.assertEqual(a.follow["A"], {"$"})


class TestLL1(unittest.TestCase):
    def test_book_table_fig_4_17(self):
        a = analyze(grammar_from_text(BOOK_428))
        self.assertTrue(a.ll1.is_ll1)
        t = {k: str(v[0]) for k, v in a.ll1.table.items()}
        expected = {
            ("S", "i"): "S -> TA", ("S", "("): "S -> TA",
            ("A", "+"): "A -> +TA", ("A", ")"): "A -> e", ("A", "$"): "A -> e",
            ("T", "i"): "T -> FB", ("T", "("): "T -> FB",
            ("B", "+"): "B -> e", ("B", "*"): "B -> *FB", ("B", ")"): "B -> e", ("B", "$"): "B -> e",
            ("F", "i"): "F -> i", ("F", "("): "F -> (S)",
        }
        self.assertEqual(t, expected)

    def test_book_moves_fig_4_21(self):
        """Fig. 4.21: moves on id + id * id (11 productions output, 5 matches)."""
        a = analyze(grammar_from_text(BOOK_428))
        r = a.ll1.parse(tokenize("i+i*i"), want_trace=True)
        self.assertTrue(r.accepted)
        self.assertEqual([str(p) for p in r.derivation], [
            "S -> TA", "T -> FB", "F -> i", "B -> e", "A -> +TA", "T -> FB", "F -> i",
            "B -> *FB", "F -> i", "B -> e", "A -> e"])
        self.assertEqual(r.trace[0].stack, "S $")

    def test_left_recursion_not_ll1(self):
        a = analyze(grammar_from_text(BOOK_41))
        self.assertFalse(a.ll1.is_ll1)

    def test_duplicate_alternative(self):
        a = analyze(grammar_from_text("1\nS -> a a\n"))
        self.assertFalse(a.ll1.is_ll1)
        self.assertFalse(a.slr.is_slr1)

    def test_condition_3(self):
        # S -> Aa, A -> a e : FIRST(a) meets FOLLOW(A) = {a}
        a = analyze(grammar_from_text("2\nS -> Aa\nA -> a e\n"))
        self.assertFalse(a.ll1.is_ll1)
        self.assertTrue(any(v.startswith("(3)") for v in a.ll1.violations))


class TestSLR(unittest.TestCase):
    def test_book_automaton_fig_4_31(self):
        a = analyze(grammar_from_text(BOOK_41))
        self.assertEqual(len(a.slr.states), 12)
        tr = a.slr.transitions
        # Same numbering as Fig. 4.31.
        self.assertEqual([tr[(0, X)] for X in "STF(i"], [1, 2, 3, 4, 5])
        self.assertEqual(tr[(1, "+")], 6)
        self.assertEqual(tr[(2, "*")], 7)
        self.assertEqual(tr[(4, "S")], 8)
        self.assertEqual(tr[(6, "T")], 9)
        self.assertEqual(tr[(7, "F")], 10)
        self.assertEqual(tr[(8, ")")], 11)

    def test_book_table_fig_4_37(self):
        a = analyze(grammar_from_text(BOOK_41))
        self.assertTrue(a.slr.is_slr1)
        from slr import action_str
        act = {k: action_str(v[0]) for k, v in a.slr.action.items()}
        self.assertEqual(act[(0, "i")], "s5")
        self.assertEqual(act[(1, "$")], "acc")
        self.assertEqual(act[(2, "+")], "r(S -> T)")
        self.assertEqual(act[(2, "*")], "s7")
        self.assertEqual(act[(9, ")")], "r(S -> S+T)")
        self.assertEqual(act[(11, "$")], "r(F -> (S))")
        self.assertEqual(len(act), 36)          # non-blank ACTION entries of Fig. 4.37
        self.assertEqual(a.slr.goto_table, {(0, "S"): 1, (0, "T"): 2, (0, "F"): 3,
                                            (4, "S"): 8, (4, "T"): 2, (4, "F"): 3,
                                            (6, "T"): 9, (6, "F"): 3, (7, "F"): 10})

    def test_book_moves_fig_4_38(self):
        a = analyze(grammar_from_text(BOOK_41))
        r = a.slr.parse(tokenize("i*i+i"), want_trace=True)
        self.assertTrue(r.accepted)
        self.assertEqual(len(r.trace), 14)      # Fig. 4.38 has 14 lines
        self.assertEqual(r.trace[-1].action, "accept")

    def test_conflicts_reported(self):
        a = analyze(grammar_from_text(LL_NOT_SLR))
        self.assertTrue(a.ll1.is_ll1)
        self.assertFalse(a.slr.is_slr1)
        self.assertTrue(all("reduce/reduce" in str(c) for c in a.slr.conflicts))


class TestCLI(unittest.TestCase):
    """Exact input/output of Section 2.2 and the examples of Section 5."""

    def test_example_1(self):
        out = run_main(BOOK_41 + "i+i\n(i)\n(i+i)*i)\n\n")
        self.assertEqual(out, "Grammar is SLR(1).\nyes\nyes\nno\n")

    def test_example_2(self):
        out = run_main(EX2 + "T\nd\nadbc\na\n\nQ\n")
        p = "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):\n"
        self.assertEqual(out, p + "yes\nyes\nno\n" + p)

    def test_example_2_both_parsers(self):
        out = run_main(EX2 + "T\nd\nadbc\na\n\nB\nd\nadbc\na\ne\n\nQ\n")
        p = "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):\n"
        self.assertEqual(out, p + "yes\nyes\nno\n" + p + "yes\nyes\nno\nno\n" + p)

    def test_example_3(self):
        self.assertEqual(run_main(EX3), "Grammar is neither LL(1) nor SLR(1).\n")

    def test_ll1_only(self):
        out = run_main(LL_NOT_SLR + "ab\nba\naa\n\n")
        self.assertEqual(out, "Grammar is LL(1).\nyes\nyes\nno\n")

    def test_empty_string_and_first_line_not_S(self):
        out = run_main("2\nA -> aA e\nS -> Ab\nb\naab\ne\n\n", )
        self.assertTrue(out.startswith("Select a parser"))
        out = run_main("2\nA -> aA e\nS -> A\nT\ne\na\nb\n\nQ\n")
        self.assertEqual(out.splitlines()[1:4], ["yes", "yes", "no"])

    def test_symbols_outside_grammar_and_crlf(self):
        out = run_main(BOOK_41.replace("\n", "\r\n") + "i+x\ni$\ni\n\n")
        self.assertEqual(out, "Grammar is SLR(1).\nno\nno\nyes\n")

    def test_s_to_epsilon(self):
        out = run_main("1\nS -> e\nT\ne\na\n\nQ\n")
        self.assertEqual(out.splitlines()[1:3], ["yes", "no"])

    def test_eof_without_empty_line(self):
        self.assertEqual(run_main(BOOK_41 + "i"), "Grammar is SLR(1).\nyes\n")


if __name__ == "__main__":
    unittest.main()
