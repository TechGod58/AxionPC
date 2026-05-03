from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any


SMOKE_CASES = [
    "Eq(rho, conjugate(Psi)*Psi)",
    r"F = \frac{G m_1 m_2}{r^2}",
    "E = m*c^2",
    "integral_0^1 x^2 dx",
    "det(A) = 0",
    "P(A|B) = P(A and B)/P(B)",
]


def _module_info(name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(name)
        return {
            "ok": True,
            "version": getattr(module, "__version__", None),
            "file": getattr(module, "__file__", None),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def run_portable_check() -> dict[str, Any]:
    from .equation_any import emit_python, parse_equation
    from .tables import build_tables_bundle

    package_dir = Path(__file__).resolve().parent
    data_files = [
        package_dir / "data" / "symbol_definitions.json",
        package_dir / "data" / "conversion_catalog.json",
    ]

    report: dict[str, Any] = {
        "ok": True,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "package_dir": str(package_dir),
        "python_version": sys.version,
        "dependencies": {
            "sympy": _module_info("sympy"),
            "numpy": _module_info("numpy"),
            "yaml": _module_info("yaml"),
            "tkinter": _module_info("tkinter"),
        },
        "data_files": [
            {"path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() else None}
            for path in data_files
        ],
        "modules": {},
        "cases": [],
    }

    for name in ("physics_codegen.equation_any", "physics_codegen.tables", "physics_codegen.gui"):
        info = _module_info(name)
        if info.get("ok"):
            try:
                info["inspect_file"] = inspect.getfile(importlib.import_module(name))
            except Exception:
                pass
        report["modules"][name] = info

    for item in report["dependencies"].values():
        if not item.get("ok"):
            report["ok"] = False
    for item in report["data_files"]:
        if not item.get("exists"):
            report["ok"] = False

    for equation in SMOKE_CASES:
        case: dict[str, Any] = {"input": equation, "ok": True}
        try:
            parsed = parse_equation(equation)
            code = emit_python(parsed, mode="symbolic", settings={})
            bundle = build_tables_bundle(equation, {
                "normalized_input": parsed.normalized_input,
                "rewritten_input": parsed.rewritten_input,
                "notes": parsed.notes,
            })
            case.update({
                "rewritten_input": parsed.rewritten_input,
                "equation": str(parsed.eq),
                "params": parsed.params,
                "code_bytes": len(code.encode("utf-8")),
                "symbol_rows": len(bundle.get("symbol_table", [])),
            })
        except Exception as exc:
            case["ok"] = False
            case["error"] = f"{type(exc).__name__}: {exc}"
            report["ok"] = False
        report["cases"].append(case)

    return report


def write_portable_check_report(path: Path) -> dict[str, Any]:
    report = run_portable_check()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
