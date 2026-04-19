from __future__ import annotations
import re
from typing import Dict, Any, Tuple

class ParseError(ValueError):
    pass

def _normalize(s: str) -> str:
    s = s.strip()
    s = s.replace("ħ", "hbar").replace("ψ", "psi").replace("∂", "d")
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def parse_equation_to_spec(eqn_text: str) -> Tuple[str, Dict[str, Any]]:
    raw = eqn_text.strip()
    if not raw:
        raise ParseError("Empty equation")

    s = _normalize(raw)

    has_i = "i" in s
    has_hbar = "hbar" in s
    has_dt = ("/dt" in s) or ("dpsi/dt" in s) or ("d psi/dt" in s)
    has_d2x = ("d2psi/dx2" in s) or ("d^2psi/dx^2" in s) or ("d2 psi/dx2" in s) or ("d2psi/dx^2" in s)

    if has_i and has_hbar and has_dt and ("psi" in s) and ("=" in s) and ("m" in s) and has_d2x:
        pot = {"type": "free"}
        if "v(" in s or "v(x" in s or "v*psi" in s or "v psi" in s:
            pot = {"type": "barrier", "V0": 50.0, "a": 0.05, "x0": 0.5}
        spec = {
            "template": "schrodinger_1d_td",
            "target": "python_stdlib",
            "domain": {"L": 1.0, "nx": 801},
            "params": {"m": 1.0, "hbar": 1.0},
            "time": {"dt": 0.0002, "t_end": 0.1},
            "potential": pot,
            "initial_conditions": {"type": "gaussian_packet", "x0": 0.3, "sigma": 0.03, "k0": 80.0},
            "prune": {"threshold": 1e-3},
        }
        return ("schrodinger_1d_td", spec)

    raise ParseError("Unrecognized equation. This GUI MVP recognizes 1D TD Schrödinger only.")
