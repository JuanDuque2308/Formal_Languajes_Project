"""Local web visualizer (optional). Standard library only.

    python3 -m viz.server [--port 8000]

then open http://localhost:8000. The page talks to one endpoint:

    GET /api/analyze?grammar=...&string=...&parser=T|B&circular=0|1

which returns the JSON produced by core.analysis_json / core.sdd_json.
The CLI (main.py) does not depend on this module.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import analysis_json, analyze, sdd_json        # noqa: E402
from grammar import GrammarError, grammar_from_text      # noqa: E402
from sdd.my_sdd import SDD_BASE                          # noqa: E402
from sdd.my_sdd_circular import SDD_CIRCULAR             # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def handle_analyze(q: dict[str, list[str]]) -> dict:
    text = q.get("grammar", [""])[0]
    try:
        g = grammar_from_text(text)
    except (GrammarError, ValueError) as exc:
        return {"error": f"Invalid grammar: {exc}"}
    a = analyze(g)
    result = {"analysis": analysis_json(a)}
    line = q.get("string", [""])[0].strip()
    if line:
        parser = q.get("parser", ["T"])[0]
        if parser == "T" and not a.ll1.is_ll1 and a.slr.is_slr1:
            parser = "B"
        if parser == "B" and not a.slr.is_slr1 and a.ll1.is_ll1:
            parser = "T"
        if not (a.ll1.is_ll1 or a.slr.is_slr1):
            result["sdd_error"] = "The grammar is neither LL(1) nor SLR(1)."
        else:
            sdd = SDD_CIRCULAR if q.get("circular", ["0"])[0] == "1" else SDD_BASE
            result["sdd"] = sdd_json(sdd, a, line, parser)
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/analyze":
            try:
                data = handle_analyze(parse_qs(url.query, keep_blank_values=True))
            except Exception as exc:          # report instead of killing the server
                data = {"error": f"{type(exc).__name__}: {exc}"}
            self._send(200, json.dumps(data).encode(), "application/json")
            return
        name = "index.html" if url.path in ("/", "/index.html") else None
        if name is None:
            self._send(404, b"not found", "text/plain")
            return
        with open(os.path.join(STATIC, name), "rb") as f:
            self._send(200, f.read(), "text/html; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:  # keep the console quiet
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Visualizer running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
