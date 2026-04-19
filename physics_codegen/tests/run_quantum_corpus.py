from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from physics_codegen.equation_any import debug_rewrite, parse_equation  # noqa: E402

# Prefer v2 versioned corpus; fall back to legacy flat v1.
_candidates = [
    ROOT / "tests" / "rewriter_corpus_v2.json",
    ROOT / "tests" / "quantum_corpus_v1.json",
]
corpus_path = next((p for p in _candidates if p.exists()), _candidates[0])
out_path = ROOT / "generated" / "quantum_corpus_report.json"


def _load_cases(path: Path) -> list[dict]:
    """Accept either the v2 versioned envelope ({schema_version, kind, cases})
    or the legacy v1 flat list. Validate kind when envelope is present."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw  # v1 flat
    if isinstance(raw, dict) and "cases" in raw:
        kind = raw.get("kind")
        if kind and kind != "rewriter_corpus":
            raise ValueError(f"{path.name}: expected kind='rewriter_corpus', got {kind!r}")
        return raw["cases"]
    raise ValueError(f"{path.name}: unrecognized corpus format")


cases = _load_cases(corpus_path)
rows = []

for c in cases:
    name = c["name"]
    text = c["input"]
    expect_ok = c.get("expect_parse_ok", True)
    expect_rewrite = c.get("expect_rewritten_contains", [])

    row = {
        "name": name,
        "input": text,
        "expect_parse_ok": expect_ok,
        "parse_ok": False,
        "rewrite_ok": True,
        "errors": [],
    }

    try:
        dbg = debug_rewrite(text)
        row["rewritten_input"] = dbg.get("rewritten_input", "")
        for token in expect_rewrite:
            if token not in row["rewritten_input"]:
                row["rewrite_ok"] = False
                row["errors"].append(f"missing token in rewrite: {token}")
    except Exception as e:
        row["rewrite_ok"] = False
        row["errors"].append(f"debug_rewrite failed: {e}")

    try:
        parsed = parse_equation(text)
        row["parse_ok"] = True
        row["equation"] = str(parsed.eq)
    except Exception as e:
        row["parse_ok"] = False
        row["parse_error"] = str(e)

    if expect_ok and not row["parse_ok"]:
        row["errors"].append("expected parse success")
    if (not expect_ok) and row["parse_ok"]:
        row["errors"].append("expected parse failure")

    row["pass"] = (len(row["errors"]) == 0)
    rows.append(row)

report = {
    "corpus": str(corpus_path.relative_to(ROOT)),
    "total": len(rows),
    "passed": sum(1 for r in rows if r["pass"]),
    "failed": sum(1 for r in rows if not r["pass"]),
    "rows": rows,
}

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(
    {"report": str(out_path), "corpus": report["corpus"], "total": report["total"],
     "passed": report["passed"], "failed": report["failed"]},
    indent=2,
))
