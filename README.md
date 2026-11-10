# SI2002 Formal Languages — Project: FIRST/FOLLOW, LL(1), SLR(1) and SDD evaluation

Implementation of the algorithms of Aho, Lam, Sethi and Ullman, *Compilers: Principles,
Techniques, and Tools* (2nd ed.), Sections 4.4, 4.5, 4.6, 5.1 and 5.2.

## Authors

- Juan José Duque Marín
- Juan Lucas Ramírez Romero
- Samuel Pulgarin

## Environment

| Item | Version used |
| --- | --- |
| Operating system | Linux (kernel 6.x, x86_64) — *TODO: add the OS each member used (e.g. Windows 11 / macOS 14)* |
| Language | Python 3.13.x (also tested with Python 3.11; requires Python ≥ 3.10) |
| Libraries | Python standard library only (no parser generators or parsing libraries) |
| Report | LaTeX (pdfLaTeX, TeX Live) |
| Visualizer (optional) | Any modern browser; no internet connection needed (no CDN) |

There is nothing to build or install: the project is plain Python.

## Project layout

```
main.py              command-line program (Items 1, 2 and 3)
grammar.py           grammar reader and data structures (Production, Grammar)
first_follow.py      FIRST and FOLLOW sets (Section 4.4.2)
ll1.py               LL(1) test (4.4.3), table (Alg. 4.31), predictive parser (Alg. 4.34)
slr.py               LR(0) items, CLOSURE/GOTO (Figs. 4.32-4.33), SLR table (Alg. 4.46),
                     LR parser (Alg. 4.44)
core.py              runs everything on a grammar and exports JSON (used by the visualizer)
sdd/spec.py          SDD as data (AttrRef, Rule, SDD), static validator, S/L classification
sdd/tree.py          parse tree built from the output of our parsers
sdd/depgraph.py      dependency graph, topological sort (Kahn), cycle detection, evaluation
sdd/my_sdd.py        our SDD (number in an arbitrary base)
sdd/my_sdd_circular.py   the same SDD with one rule changed so that it is circular
viz/                 optional local web visualizer (standard-library HTTP server + HTML/JS)
tests/               unit tests (unittest)
examples/            input files used in this README and in the report
report.pdf           the report
```

## Running Items 1 and 2

The program reads the grammar and then the strings from standard input, exactly as described in
Section 2.2 of the assignment:

```bash
python3 main.py < examples/example1.txt
python3 main.py < examples/example2.txt
python3 main.py < examples/example3.txt
```

or interactively (type the grammar, then the strings; an empty line ends the strings, the line
`e` is the empty string):

```bash
python3 main.py
```

On Windows use `python` (or `py`) instead of `python3`; in PowerShell redirect with
`Get-Content examples\example1.txt | python main.py`.

### Flags

| Flag | Effect |
| --- | --- |
| `--sets` | after reading the grammar, print `First(A) = {...}` and `Follow(A) = {...}` for every nonterminal, then continue normally |
| `--trace` | for each string, print the parsing steps (stack, input, action), as in Figs. 4.21 and 4.38 of the book |
| `--verbose` | print the LL(1) table, the LR(0) automaton, the SLR(1) table and any conflicts |
| `--export-json FILE` | write the whole analysis as JSON |

Without flags the output is exactly the one required by the assignment.

Example:

```bash
python3 main.py --sets < examples/example2.txt
```

## Running Item 3 (SDD)

Our SDD computes the value of a number written in an arbitrary base: the input `b:digits` means
"`digits` read in base `b`", where `b` is written in decimal (`8:17` → 15, `2:1011` → 11,
`12:11` → 13). The grammar is in `examples/sdd_grammar.txt`.

```bash
python3 main.py --sdd < examples/sdd_hand.txt        # the example worked by hand in the report
python3 main.py --sdd < examples/sdd_tests.txt       # the test strings of the report
python3 main.py --sdd --parser B < examples/sdd_hand.txt   # build the tree with the SLR(1) parser
python3 main.py --sdd --circular < examples/sdd_hand.txt   # circularity experiment
```

The program reads the grammar (format of Section 2.2) and then strings until an empty line.
For each string it prints `no` if the string is not in the language; otherwise it prints the
annotated parse tree (one node per line, indented by depth), the evaluation order (a topological
sort of the dependency graph) and the value of `S.val`. If the dependency graph has a cycle it
prints `SDD is circular:` followed by one concrete cycle.

To change the SDD, edit only `sdd/my_sdd.py`; the evaluator does not know anything about it.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests compare our results with the book (Example 4.30, Figs. 4.17, 4.21, 4.31, 4.37 and
4.38), check the exact input/output of the three examples of the assignment and the four
classification cases, and test the SDD (validator, evaluation with both parsers, topological
order, circularity).

## Visualizer (optional)

```bash
python3 -m viz.server            # then open http://localhost:8000
python3 -m viz.server --port 9000
```

It shows the FIRST/FOLLOW sets, the LL(1) and SLR(1) tables (conflicts in red), the LR(0)
automaton, and the parse tree with its dependency graph. The **Step** / **Play** buttons evaluate
the attributes one at a time in topological order; with *Use the mutated (circular) SDD* the cycle
is shown in red. Drag to pan and scroll to zoom.

## Use of generative AI tools

*TODO (team): review and complete this section so that it describes exactly what you did.*

- **Claude (Anthropic)** was used to review the assignment against the book, to write the
  specification checklist of the project, and to generate a first version of the code, the tests,
  the visualizer and a draft of the report from that specification.
- *Describe here how the team studied the book sections, did the hand-worked examples, reviewed and
  modified the generated code, and which parts each member is responsible for.*
