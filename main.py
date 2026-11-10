"""Command-line entry point.

    python3 main.py [--sets] [--trace] [--verbose] [--export-json FILE] < input
    python3 main.py --sdd [--circular] [--parser T|B] < input

Without optional flags the program follows Section 2.2 of the assignment
character by character. All optional output goes to stdout but only when the
corresponding flag is given.
"""
from __future__ import annotations

import argparse
import json
import sys

from core import Analysis, analysis_json, analyze, parse_tree
from first_follow import sets_report
from grammar import LineReader, read_grammar, tokenize
from ll1 import render_table
from sdd.depgraph import CircularSDD, evaluate
from sdd.spec import SDD, classify, validate
from sdd.tree import annotated_tree_lines

PROMPT = "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):"


def out(text: str = "") -> None:
    print(text)
    sys.stdout.flush()


def read_strings(reader: LineReader):
    """Strings one per line until an empty line (or end of file)."""
    while True:
        line = reader.readline()
        if line is None or line.strip() == "":
            return
        yield line.strip()


def print_trace(a: Analysis, parser: str, line: str) -> None:
    tokens = tokenize(line)
    if parser == "T":
        r = a.ll1.parse(tokens, want_trace=True)
        rows = [["MATCHED", "STACK", "INPUT", "ACTION"]] + \
               [[s.matched, s.stack, s.input, s.action] for s in r.trace]
    else:
        r = a.slr.parse(tokens, want_trace=True)
        rows = [["STACK", "SYMBOLS", "INPUT", "ACTION"]] + \
               [[s.stack, s.symbols, s.input, s.action] for s in r.trace]
    if len(rows) == 1:
        rows.append(["", "", "".join(tokens) + "$", "error: symbol not in the grammar"])
    for l in render_table(rows):
        out(l)


def parse_loop(a: Analysis, reader: LineReader, parser: str, trace: bool) -> None:
    for line in read_strings(reader):
        tokens = tokenize(line)
        if trace:
            print_trace(a, parser, line)
        ok = (a.ll1 if parser == "T" else a.slr).parse(tokens).accepted
        out("yes" if ok else "no")


def print_verbose(a: Analysis) -> None:
    out("== LL(1) table (Algorithm 4.31) ==")
    for l in a.ll1.table_lines():
        out(l)
    for v in a.ll1.violations:
        out(f"LL(1) violation: {v}")
    out("== LR(0) automaton (Figs. 4.32-4.33) ==")
    for l in a.slr.automaton_lines():
        out(l)
    out("== SLR(1) table (Algorithm 4.46) ==")
    for l in a.slr.table_lines():
        out(l)
    for c in a.slr.conflicts:
        out(f"SLR(1) conflict: {c}")
    out("==")


def run_parsers(args: argparse.Namespace, reader: LineReader) -> None:
    g = read_grammar(reader)
    a = analyze(g)
    if args.sets:
        for l in sets_report(g, a.first, a.follow):
            out(l)
    if args.verbose:
        print_verbose(a)
    if args.export_json:
        with open(args.export_json, "w", encoding="utf-8") as f:
            json.dump(analysis_json(a), f, indent=2)

    is_ll1, is_slr1 = a.ll1.is_ll1, a.slr.is_slr1
    if is_ll1 and is_slr1:                                       # case 1
        while True:
            out(PROMPT)
            choice = reader.readline()
            if choice is None:
                return
            choice = choice.strip().upper()
            if choice == "Q":
                return
            if choice in ("T", "B"):
                parse_loop(a, reader, choice, args.trace)
    elif is_ll1:                                                 # case 2
        out("Grammar is LL(1).")
        parse_loop(a, reader, "T", args.trace)
    elif is_slr1:                                                # case 3
        out("Grammar is SLR(1).")
        parse_loop(a, reader, "B", args.trace)
    else:                                                        # case 4
        out("Grammar is neither LL(1) nor SLR(1).")


def run_sdd(args: argparse.Namespace, reader: LineReader) -> None:
    """Item 3: read the grammar (format of Section 2.2), then strings until an
    empty line. For each string print 'no', or the annotated parse tree, the
    evaluation order and the value of the main attribute of S."""
    if args.circular:
        from sdd.my_sdd_circular import SDD_CIRCULAR as sdd
    else:
        from sdd.my_sdd import SDD_BASE as sdd
    sdd: SDD
    g = read_grammar(reader)
    a = analyze(g)
    errors = validate(sdd, g)
    if errors:
        out("The SDD is not well formed for this grammar:")
        for e in errors:
            out(f"  - {e}")
        return
    parser = args.parser or ("T" if a.ll1.is_ll1 else "B" if a.slr.is_slr1 else None)
    if parser is None or (parser == "T" and not a.ll1.is_ll1) or \
            (parser == "B" and not a.slr.is_slr1):
        out("The grammar cannot be parsed with the selected parser.")
        return
    s_attr, l_attr, reasons = classify(sdd, g)
    out(f"SDD: {sdd.name}")
    out(f"Parser: {'LL(1)' if parser == 'T' else 'SLR(1)'}")
    out(f"S-attributed: {'yes' if s_attr else 'no'}   L-attributed: {'yes' if l_attr else 'no'}")
    for r in reasons:
        out(f"  ({r})")
    out()
    for line in read_strings(reader):
        root = parse_tree(a, line, parser)
        if root is None:
            out("no")
            out()
            continue
        try:
            graph, steps = evaluate(root, sdd)
        except CircularSDD as exc:
            out(f"String: {line}")
            out(str(exc))
            out()
            continue
        out(f"String: {line}")
        out("Annotated parse tree:")
        for l in annotated_tree_lines(root):
            out("  " + l)
        out("Evaluation order (topological sort of the dependency graph):")
        for k, s in enumerate(steps, 1):
            how = f"{s.production}:  {s.rule_text}" if s.rule_text else "lexval, given by the scanner"
            out(f"  {k:3}. {graph.name(s.vertex)} = {s.value!r}    [{how}]")
        out(f"Result: {g.start}.{sdd.main_attr} = {root.attrs[sdd.main_attr]}")
        out()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="FIRST/FOLLOW, LL(1), SLR(1) and SDD evaluation "
                                             "(Aho et al., 2nd ed., Sections 4.4-4.6, 5.1-5.2)")
    ap.add_argument("--sets", action="store_true", help="print FIRST and FOLLOW sets")
    ap.add_argument("--trace", action="store_true", help="print the parsing steps of each string")
    ap.add_argument("--verbose", action="store_true",
                    help="print the LL(1) table, the LR(0) automaton and the SLR(1) table")
    ap.add_argument("--export-json", metavar="FILE", help="write the analysis as JSON")
    ap.add_argument("--sdd", action="store_true", help="Item 3: evaluate our SDD")
    ap.add_argument("--circular", action="store_true",
                    help="with --sdd: use the mutated (circular) SDD")
    ap.add_argument("--parser", choices=["T", "B"], help="with --sdd: force LL(1) (T) or SLR(1) (B)")
    args = ap.parse_args(argv)
    reader = LineReader(sys.stdin)
    if args.sdd:
        run_sdd(args, reader)
    else:
        run_parsers(args, reader)


if __name__ == "__main__":
    main()
