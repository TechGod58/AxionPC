import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from physics_codegen.equation_any import debug_rewrite, parse_equation

cases = [
    {"name":"ascii_simple","text":"F = m*a"},
    {"name":"unicode_greek","text":"ρ = ψ*ψ"},
    {"name":"unicode_ops","text":"u_tt = c² u_xx + ∇u"},
    {"name":"latex_basic","text":r"\rho = \Psi^{*}\Psi"},
    {"name":"latex_displaystyle","text":r"{\displaystyle \rho =\left(\Psi \right^{2}=\Psi ^{*}\Psi }"},
    {"name":"bad_symbol_block","text":"A = B ⧉ C"},
]

rows=[]
for c in cases:
    row={"name":c["name"],"text":c["text"]}
    try:
        dbg=debug_rewrite(c["text"])
        row["normalized_input"]=dbg.get("normalized_input","")
        row["rewritten_input"]=dbg.get("rewritten_input","")
        row["notes"]=dbg.get("notes",[])
        try:
            p=parse_equation(c["text"])
            row["parse_ok"]=True
            row["eq"]=str(p.eq)
        except Exception as e:
            row["parse_ok"]=False
            row["parse_error"]=str(e)
    except Exception as e:
        row["rewrite_ok"]=False
        row["rewrite_error"]=str(e)
    rows.append(row)

out={
  "total":len(rows),
  "parse_passed":sum(1 for r in rows if r.get("parse_ok")),
  "parse_failed":sum(1 for r in rows if r.get("parse_ok") is False),
  "rows":rows,
}

out_path=Path(__file__).resolve().parents[1] / "generated" / "symbol_ingestion_smoke.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({"ok":True,"out":str(out_path),"parse_passed":out["parse_passed"],"parse_failed":out["parse_failed"]},indent=2))
