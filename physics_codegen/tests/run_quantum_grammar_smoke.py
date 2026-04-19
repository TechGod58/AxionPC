import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from physics_codegen.equation_any import normalize_text

corpus_path = ROOT / "tests" / "quantum_corpus_v1.json"
corpus = json.loads(corpus_path.read_text(encoding="utf-8"))

rows = []
for case in corpus:
    normalized = normalize_text(case["text"])
    ok = case["expect_contains"] in normalized
    rows.append(
        {
            "name": case["name"],
            "ok": ok,
            "normalized": normalized,
            "expect": case["expect_contains"],
        }
    )

out = {
    "total": len(rows),
    "passed": sum(1 for row in rows if row["ok"]),
    "failed": sum(1 for row in rows if not row["ok"]),
    "rows": rows,
}
opath = ROOT / "generated" / "quantum_grammar_smoke.json"
opath.parent.mkdir(parents=True, exist_ok=True)
opath.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(
    json.dumps(
        {"ok": out["failed"] == 0, "passed": out["passed"], "failed": out["failed"], "out": str(opath)},
        indent=2,
    )
)
