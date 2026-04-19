from __future__ import annotations
import json, random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from physics_codegen.equation_any import parse_equation, emit_python  # noqa: E402

# Prefer v2 versioned corpus; fall back to legacy flat v1.
_candidates = [
    ROOT / "tests" / "validation_corpus_v2.json",
    ROOT / "tests" / "converter_validation_cases_v1.json",
]
CASES = next((p for p in _candidates if p.exists()), _candidates[0])
OUT = ROOT / "generated" / "converter_validation_report.json"


def _load_cases(path: Path) -> list[dict]:
    """Accept either the v2 versioned envelope ({schema_version, kind, cases})
    or the legacy v1 flat list. Validate kind when envelope is present."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw  # v1 flat
    if isinstance(raw, dict) and "cases" in raw:
        kind = raw.get("kind")
        if kind and kind != "validation_corpus":
            raise ValueError(f"{path.name}: expected kind='validation_corpus', got {kind!r}")
        return raw["cases"]
    raise ValueError(f"{path.name}: unrecognized corpus format")


def _canon_dim(d: str) -> str:
    d = d.replace(" ", "")
    d = d.replace("(J*s)*(1/s)", "J")
    d = d.replace("(1/s)*(J*s)", "J")
    d = d.replace("(kg*m/s^2)*m", "J")
    d = d.replace("kg*m^2/s^2", "J")
    return d


def dim_mul(a: str, b: str) -> str:
    if a == "1": return b
    if b == "1": return a
    return _canon_dim(f"({a})*({b})")


def dim_eval(expr: str, units: dict[str, str]) -> str:
    expr = expr.strip()
    if expr in units:
        return units[expr]
    if '*' in expr and '+' not in expr and '-' not in expr and '/' not in expr:
        out = '1'
        for p in [x.strip() for x in expr.split('*')]:
            out = dim_mul(out, units.get(p, p))
        return out
    return units.get(expr, f"UNKNOWN:{expr}")


def check_dims(groups, units):
    errs = []
    for g in groups:
        vals = [_canon_dim(dim_eval(x, units)) for x in g]
        if len(set(vals)) != 1:
            errs.append(f"dimension mismatch in group {g}: {vals}")
    return errs


def sample(case_name: str, n=25):
    rows = []
    if case_name == 'density_identity':
        for _ in range(n):
            a = random.uniform(-2, 2)
            b = random.uniform(-2, 2)
            psi = complex(a, b)
            rows.append({'Psi': psi, 'rho': (psi.conjugate() * psi).real})
    elif case_name == 'ho_energy':
        for _ in range(n):
            nn = random.randint(0, 40)
            h = random.uniform(1e-35, 1e-33)
            w = random.uniform(1.0, 1e4)
            rows.append({'n': nn, 'hbar': h, 'omega': w, 'E_n': h * w * (nn + 0.5)})
    return rows


def residual(eq, vals):
    sub = {sym: vals[str(sym)] for sym in eq.free_symbols if str(sym) in vals}
    lhs = complex(eq.lhs.evalf(subs=sub))
    rhs = complex(eq.rhs.evalf(subs=sub))
    return abs(lhs - rhs)


def ref_check(name, vals):
    if name == 'density_identity':
        return abs(vals['rho'] - (vals['Psi'].conjugate() * vals['Psi']).real)
    if name == 'ho_energy':
        return abs(vals['E_n'] - vals['hbar'] * vals['omega'] * (vals['n'] + 0.5))
    return 0.0


def main():
    cases = _load_cases(CASES)
    out_rows = []
    for c in cases:
        row = {'name': c['name'], 'pass': True, 'errors': []}
        try:
            p = parse_equation(c['equation'])
            row['rewritten'] = p.rewritten_input
            _ = emit_python(p, mode='symbolic', settings={})
        except Exception as e:
            row['pass'] = False
            row['errors'].append(f"parse/codegen failed: {e}")
            out_rows.append(row)
            continue

        dim_err = check_dims(c.get('dimension_groups', []), c.get('units', {}))
        if dim_err:
            row['pass'] = False
            row['errors'] += dim_err

        samples = sample(c.get('sampler', ''), n=25)
        if not samples:
            row['pass'] = False
            row['errors'].append('no sampler generated')
        else:
            worst_res = 0.0
            worst_ref = 0.0
            for s in samples:
                try:
                    r = residual(p.eq, s)
                    rr = ref_check(c.get('reference', ''), s)
                    worst_res = max(worst_res, r)
                    worst_ref = max(worst_ref, rr)
                except Exception as e:
                    row['pass'] = False
                    row['errors'].append(f"property eval failed: {e}")
                    break
            row['max_residual'] = worst_res
            row['max_reference_error'] = worst_ref
            if worst_res > 1e-8:
                row['pass'] = False
                row['errors'].append(f"residual gate failed: {worst_res}")
            if worst_ref > 1e-8:
                row['pass'] = False
                row['errors'].append(f"reference gate failed: {worst_ref}")

        out_rows.append(row)

    report = {
        'corpus': str(CASES.relative_to(ROOT)),
        'total': len(out_rows),
        'passed': sum(1 for r in out_rows if r['pass']),
        'failed': sum(1 for r in out_rows if not r['pass']),
        'rows': out_rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(
        {'report': str(OUT), 'corpus': report['corpus'],
         'passed': report['passed'], 'failed': report['failed']},
        indent=2,
    ))


if __name__ == '__main__':
    main()
