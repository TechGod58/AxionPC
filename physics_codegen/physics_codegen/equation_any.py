from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .quantum_grammar import normalize_quantum_notation
from .naming import pythonize_identifier


class ParseError(ValueError):
    pass


def _try_import_sympy():
    try:
        import sympy as sp
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
        return sp, parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
    except Exception:
        return None, None, None, None, None


@dataclass
class Parsed:
    sp: Any
    eq: Any
    solved: Optional[Any]
    dep_name: str
    x: Any
    t: Any
    params: List[str]
    notes: List[str]
    normalized_input: str
    rewritten_input: str


_SUBSCRIPT_DIGITS = {"₀":"_0","₁":"_1","₂":"_2","₃":"_3","₄":"_4","₅":"_5","₆":"_6","₇":"_7","₈":"_8","₉":"_9"}
GREEK_MAP = {"τ":"tau","α":"alpha","β":"beta","γ":"gamma","δ":"delta","μ":"mu","ρ":"rho","φ":"phi","ω":"omega","λ":"lambda","Ω":"Omega"}
UNICODE_MAP = {
    "ψ":"psi","Ψ":"Psi","ϕ":"phi","ℏ":"hbar","ħ":"hbar","Ħ":"hbar","π":"pi","∂":"d","²":"^2","³":"^3",
    "−":"-","×":" cross ","·":"*","⋅":"*","∗":"*","√":"sqrt","∞":"oo","∑":"Sum","Σ":"Sum","∇":"grad",
    "≈":" = ","≃":" = ","≅":" = ","∼":" ~ ","∨":" or ","∫":"Integral","〖":"[","〗":"]","⟨":"(","⟩":")","⋯":" ","…":" ","∈":" in ","ℓ":"l", "′":"", "″":"",
    "\u200b":"","\u205f":" ","\u2061":"","\ufeff":"","�":""
}
LATEX_MAP = {
    r"\displaystyle":"", r"\left":"", r"\right":"", r"\cdot":"*", r"\times":" cross ", r"\nabla":"grad", r"\partial":"d",
    r"\Psi":"Psi", r"\psi":"psi", r"\rho":"rho", r"\phi":"phi", r"\theta":"theta", r"\lambda":"lambda", r"\mu":"mu",
    r"\epsilon":"epsilon", r"\hbar":"hbar", r"\pi":"pi", r"\approx":" = ", r"\sim":" ~ ", r"\neq":" != ",
    r"\leq":" <= ", r"\geq":" >= ",
}
_ALLOWED_AFTER = set()
_FUNCTION_CALL_NAMES = (
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "coth", "sech", "csch",
    "exp", "log", "sqrt", "Abs",
    "erf", "erfc", "det", "trace", "rank", "diag",
    "sign", "arg", "Min", "Max", "binomial",
    "Limit", "Prod", "Product", "Mod", "gcd", "lcm", "floor", "ceiling",
    "Expectation", "Var", "Cov", "Pr",
    "argmin", "argmax", "Min_over", "Max_over",
)
_BRACKET_CALL_NAMES = ("Expectation", "Pr", "Var", "Cov")
_OPERATORNAME_REWRITE_MAP = {
    "e": "Expectation",
    "pr": "Pr",
    "var": "Var",
    "cov": "Cov",
    "det": "det",
    "tr": "trace",
    "trace": "trace",
    "rank": "rank",
    "diag": "diag",
    "argmin": "argmin",
    "argmax": "argmax",
    "gcd": "gcd",
    "lcm": "lcm",
    "sgn": "sign",
    "span": "span",
    "ker": "ker",
    "im": "im",
    "dim": "dim",
}


def _strip_comments_and_join_lines(s: str) -> str:
    return " ".join([ln.split("#",1)[0].strip() for ln in s.splitlines() if ln.split("#",1)[0].strip()]).strip()


@lru_cache(maxsize=1)
def _load_external_symbol_maps() -> tuple[dict[str, str], dict[str, str]]:
    path = Path(__file__).resolve().parent / "data" / "symbol_definitions.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}

    unicode_map = payload.get("unicode_map", {}) or {}
    latex_map = payload.get("latex_map", {}) or {}
    if not isinstance(unicode_map, dict) or not isinstance(latex_map, dict):
        return {}, {}
    return dict(unicode_map), dict(latex_map)


def _balance_check(s: str) -> Tuple[bool, str]:
    pairs={")":"(","]":"[","}":"{"}; stack=[]
    for ch in s:
        if ch in "([{": stack.append(ch)
        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]: return False, f"Unmatched closing '{ch}'"
            stack.pop()
    if stack: return False, f"Unmatched opening '{stack[-1]}'"
    return True, ""


def _report_unsupported_unicode(s: str) -> None:
    bad={}
    for ch in s:
        if ord(ch)>127 and ch not in _ALLOWED_AFTER and not ch.isspace(): bad[ch]=bad.get(ch,0)+1
    if bad:
        items=", ".join([f"{repr(k)}(U+{ord(k):04X})x{v}" for k,v in bad.items()])
        raise ParseError(f"Unsupported Unicode characters after normalization: {items}")


def _strip_latex_display_wrappers(s: str) -> str:
    s = re.sub(r"^\s*\\\[\s*", "", s)
    s = re.sub(r"\s*\\\]\s*$", "", s)
    s = re.sub(r"^\s*\\\(\s*", "", s)
    s = re.sub(r"\s*\\\)\s*$", "", s)
    s = re.sub(r"^\s*\$\$\s*", "", s)
    s = re.sub(r"\s*\$\$\s*$", "", s)
    s = re.sub(r"^\s*\$(?!\$)\s*", "", s)
    s = re.sub(r"\s*(?<!\$)\$\s*$", "", s)
    return s.strip()


def _rewrite_latex_text_blocks(s: str) -> str:
    # Convert common text-like LaTeX commands into parser-safe identifiers.
    # Example: \text{kg} -> txt_kg
    pattern = re.compile(r"\\(text|mathrm|operatorname)\s*\{([^{}]*)\}")

    def _replace(match: re.Match[str]) -> str:
        command = match.group(1).strip().lower()
        payload = match.group(2).strip()
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", payload).strip("_")
        if not cleaned:
            return " "
        if command == "operatorname":
            mapped = _OPERATORNAME_REWRITE_MAP.get(cleaned.lower())
            if mapped:
                return f" {mapped} "
        if cleaned[0].isdigit():
            cleaned = f"n_{cleaned}"
        return f" txt_{cleaned} "

    while True:
        nxt = pattern.sub(_replace, s)
        if nxt == s:
            return s
        s = nxt


def _extract_braced(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    buf: List[str] = []
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
            if depth > 1:
                buf.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(buf), i + 1
            buf.append(ch)
        else:
            buf.append(ch)
        i += 1
    return None, start


def _rewrite_latex_fractions(s: str) -> str:
    pattern = re.compile(r"\\(?:d|t)?frac\s*")
    while True:
        match = pattern.search(s)
        if not match:
            return s
        numerator, next_i = _extract_braced(s, match.end())
        if numerator is None:
            s = s[:match.start()] + "(" + s[match.end():]
            continue
        denominator, end_i = _extract_braced(s, next_i)
        if denominator is None:
            s = s[:match.start()] + "(" + numerator + ")" + s[next_i:]
            continue
        replacement = f"(({_rewrite_latex_fractions(numerator)}))/(({_rewrite_latex_fractions(denominator)}))"
        s = s[:match.start()] + replacement + s[end_i:]


def _rewrite_latex_binomials(s: str) -> str:
    pattern = re.compile(r"\\(?:binom|choose)\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    while True:
        nxt = pattern.sub(r"binomial(\1, \2)", s)
        if nxt == s:
            return s
        s = nxt


def _rewrite_math_function_calls(s: str) -> str:
    for fn in _FUNCTION_CALL_NAMES:
        # Convert fn{arg} -> fn(arg)
        s = re.sub(rf"\b{re.escape(fn)}\s*\{{([^{{}}]+)\}}", rf"{fn}(\1)", s)
        # Convert fn x -> fn(x) for single-token arguments.
        s = re.sub(
            rf"\b{re.escape(fn)}\s+([A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?)\b",
            rf"{fn}(\1)",
            s,
        )
    return s


def _rewrite_prime_identifiers(s: str) -> str:
    s = s.replace("\u2032", "'").replace("\u2033", "''")

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        primes = match.group(2)
        count = len(primes)
        suffix = "_prime" if count == 1 else f"_prime{count}"
        return f"{name}{suffix}"

    return re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)('{1,})", _replace, s)


def _cleanup_escaped_latex_punctuation(s: str) -> str:
    # Pasted snippets can contain doubled escapes. Normalize first.
    s = re.sub(r"\\{2,}", r"\\", s)

    # Remove inline-math wrappers and escaped punctuation often copied from docs.
    s = s.replace(r"\(", " ").replace(r"\)", " ")
    s = s.replace(r"\[", " ").replace(r"\]", " ")
    s = s.replace(r"\^", "^")
    s = s.replace(r"\_", "_")
    s = s.replace(r"\.", ".")
    s = re.sub(r"\\(?![A-Za-z])", " ", s)
    return s


def _cleanup_latex_spacing_commands(s: str) -> str:
    # Common LaTeX spacing commands that should not affect math meaning.
    s = re.sub(r"\\(?:,|;|:|!|quad|qquad)\b", " ", s)
    s = re.sub(r"\\\s*,", " ", s)
    s = re.sub(r"\\\s*;", " ", s)
    s = re.sub(r"\\\s*:", " ", s)
    s = re.sub(r"\\\s*!", " ", s)
    return s


def _cleanup_operator_punctuation_artifacts(s: str) -> str:
    # OCR / copy artifacts sometimes leave punctuation after unary operators:
    # e.g. "- .((G M m))/((r))". Drop that punctuation when it is clearly not a separator.
    return re.sub(r"([=+\-*/^])\s*[.,;:]\s*(?=[(\w])", r"\1 ", s)


def _rewrite_bracket_function_calls(s: str, notes: List[str]) -> str:
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, _BRACKET_CALL_NAMES)) + r")\s*\[([^\[\]]+)\]")
    changed = False
    while True:
        nxt = pattern.sub(r"\1(\2)", s)
        if nxt == s:
            break
        changed = True
        s = nxt
    if changed:
        notes.append("Rewrote bracketed function notation fn[...] into fn(...).")
    return s


def _rewrite_mod_notation(s: str, notes: List[str]) -> str:
    pattern = re.compile(r"\b([A-Za-z0-9_)\]]+)\s+mod\s+([A-Za-z0-9_(\[]+)\b")
    if pattern.search(s):
        s = pattern.sub(r"Mod(\1, \2)", s)
        notes.append("Rewrote modular arithmetic notation into Mod(a, n).")
    return s


def _rewrite_optimization_notation(s: str, notes: List[str]) -> str:
    original = s
    s = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\^\s*\{\s*\*\s*\}", r"\1_star", s)
    s = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\^\s*\*", r"\1_star", s)
    s = re.sub(r"\b(argmin|argmax)\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*\([^()]*\))?)", r"\1(\2)", s)
    s = re.sub(
        r"\b(Min|Max)_([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*\([^()]*\))?)",
        r"\1_over(\2, \3)",
        s,
    )
    if s != original:
        notes.append("Rewrote optimization notation (x^*, argmin/argmax, min_x/max_x) into callable forms.")
    return s


def _rewrite_limit_notation(s: str, notes: List[str]) -> str:
    with_rhs = re.match(
        r"^\s*Limit\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s,()]+)\s+(.+?)\s*=\s*(.+)\s*$",
        s,
    )
    if with_rhs:
        var, point, expr, rhs = with_rhs.groups()
        notes.append("Rewrote limit notation into Limit(expr, var, point).")
        return f"Limit({expr.strip()}, {var}, {point}) = {rhs.strip()}"

    without_rhs = re.match(r"^\s*Limit\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s,()]+)\s+(.+)\s*$", s)
    if without_rhs:
        var, point, expr = without_rhs.groups()
        notes.append("Rewrote limit notation into Limit(expr, var, point).")
        return f"Limit({expr.strip()}, {var}, {point})"
    return s


def _rewrite_sum_notation(s: str, notes: List[str]) -> str:
    with_rhs = re.match(
        r"^\s*Sum_\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s]+)\s*\^?\s*([^\s]+)\s+(.+?)\s*=\s*(.+)\s*$",
        s,
    )
    if with_rhs:
        idx, lo, hi, expr, rhs = with_rhs.groups()
        notes.append("Rewrote indexed sum notation into Sum(expr, (i, lo, hi)).")
        return f"Sum({expr.strip()}, ({idx}, {lo}, {hi})) = {rhs.strip()}"

    without_rhs = re.match(
        r"^\s*Sum_\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s]+)\s*\^?\s*([^\s]+)\s+(.+)\s*$",
        s,
    )
    if without_rhs:
        idx, lo, hi, expr = without_rhs.groups()
        notes.append("Rewrote indexed sum notation into Sum(expr, (i, lo, hi)).")
        return f"Sum({expr.strip()}, ({idx}, {lo}, {hi}))"
    return s


def _rewrite_integral_notation(s: str, notes: List[str]) -> str:
    # Separator between integrand and the 'd<var>' differential: whitespace
    # OR '*' (the latter appears when the implicit-multiplication pass rewrites
    # ')\s*d' to ')*d' before this rewriter runs).
    _SEP = r"[\s*]+"

    bounded_with_rhs = re.match(
        r"^\s*Integral_\s*([^\s]+)\s*\^\s*([^\s]+)\s+(.+?)" + _SEP + r"d([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)\s*$",
        s,
    )
    if bounded_with_rhs:
        lo, hi, expr, var, rhs = bounded_with_rhs.groups()
        notes.append("Rewrote bounded integral notation into Integral(expr, (x, lo, hi)).")
        return f"Integral({expr.strip()}, ({var}, {lo}, {hi})) = {rhs.strip()}"

    bounded_without_rhs = re.match(
        r"^\s*Integral_\s*([^\s]+)\s*\^\s*([^\s]+)\s+(.+?)" + _SEP + r"d([A-Za-z_][A-Za-z0-9_]*)\s*$",
        s,
    )
    if bounded_without_rhs:
        lo, hi, expr, var = bounded_without_rhs.groups()
        notes.append("Rewrote bounded integral notation into Integral(expr, (x, lo, hi)).")
        return f"Integral({expr.strip()}, ({var}, {lo}, {hi}))"

    plain_with_rhs = re.match(
        r"^\s*Integral\s+(.+?)" + _SEP + r"d([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)\s*$",
        s,
    )
    if plain_with_rhs:
        expr, var, rhs = plain_with_rhs.groups()
        notes.append("Rewrote integral notation into Integral(expr, x).")
        return f"Integral({expr.strip()}, {var}) = {rhs.strip()}"

    plain_without_rhs = re.match(
        r"^\s*Integral\s+(.+?)" + _SEP + r"d([A-Za-z_][A-Za-z0-9_]*)\s*$",
        s,
    )
    if plain_without_rhs:
        expr, var = plain_without_rhs.groups()
        notes.append("Rewrote integral notation into Integral(expr, x).")
        return f"Integral({expr.strip()}, {var})"
    return s


# ---------------------------------------------------------------------------
# Derivative rewriter
# ---------------------------------------------------------------------------
# After normalize_text, the partial-derivative symbol ∂ has already been mapped
# to 'd' and Unicode superscripts have been folded to '^2', '^3'. We operate on
# that normalized form and promote Leibniz notation into SymPy Derivative(...)
# calls.
#
# Accepted shapes (all with optional whitespace between tokens):
#   first-order:          dPsi/dt        d Psi / d t       dy/dx
#   second-order:         d^2Psi/dx^2    d^2 y / dx^2      d^2 y/dx^2
#   mixed partial:        d^2 u / dx dy  d^2u/dx dy
#
# Design constraints:
# * glued form (d<name> with no whitespace) only accepts a name that is a
#   single lowercase letter OR starts with an uppercase letter. This matches
#   physics convention (dy, dx, du, df, dPsi, dPhi) and rejects English words
#   that start with 'd' (density/diameter, distance/duration, drift/decay).
# * spaced form (d <name>) accepts any identifier because the whitespace
#   disambiguates.
# * both ends of the whole d.../d... construct are guarded by a LEFT/RIGHT
#   boundary so that tokens like 'dt' on their own, or fractions like 'r = d/2',
#   are never touched.
# ---------------------------------------------------------------------------

_DERIV_LEFT = r"(?:^|(?<=[\s=+\-*/(\[,{]))"
_DERIV_RIGHT = r"(?=\s|[=+\-*/)\],}]|$)"
_DERIV_NAME_GLUED = r"(?:[A-Z]\w*|[a-z])"
_DERIV_NAME_SPACED = r"[A-Za-z_]\w*"
_DERIV_NAME = (
    r"(?:\s+(" + _DERIV_NAME_SPACED + r")|(" + _DERIV_NAME_GLUED + r"))"
)

_DERIV_PATTERNS = [
    # Mixed partial: d{^2} F / d X d Y  -> Derivative(F, X, Y)
    (
        re.compile(
            _DERIV_LEFT
            + r"d\s*\^?\s*2\s*" + _DERIV_NAME
            + r"\s*/\s*d" + _DERIV_NAME
            + r"\s*d" + _DERIV_NAME
            + _DERIV_RIGHT
        ),
        lambda m: "Derivative({}, {}, {})".format(
            m.group(1) or m.group(2),
            m.group(3) or m.group(4),
            m.group(5) or m.group(6),
        ),
    ),
    # Second order: d{^2} F / d X{^2}  -> Derivative(F, X, 2)
    (
        re.compile(
            _DERIV_LEFT
            + r"d\s*\^?\s*2\s*" + _DERIV_NAME
            + r"\s*/\s*d" + _DERIV_NAME
            + r"\s*\^?\s*2"
            + _DERIV_RIGHT
        ),
        lambda m: "Derivative({}, {}, 2)".format(
            m.group(1) or m.group(2),
            m.group(3) or m.group(4),
        ),
    ),
    # First order: d F / d X  -> Derivative(F, X)
    (
        re.compile(
            _DERIV_LEFT
            + r"d" + _DERIV_NAME
            + r"\s*/\s*d" + _DERIV_NAME
            + _DERIV_RIGHT
        ),
        lambda m: "Derivative({}, {})".format(
            m.group(1) or m.group(2),
            m.group(3) or m.group(4),
        ),
    ),
    # Parenthesized second order: ((d^2 F))/((dX^2))  (produced by LaTeX \frac expansion)
    (
        re.compile(
            _DERIV_LEFT
            + r"\(+\s*d\s*\^?\s*2\s*" + _DERIV_NAME + r"\s*\)+"
            + r"\s*/\s*"
            + r"\(+\s*d" + _DERIV_NAME + r"\s*\^?\s*2\s*\)+"
            + _DERIV_RIGHT
        ),
        lambda m: "Derivative({}, {}, 2)".format(
            m.group(1) or m.group(2),
            m.group(3) or m.group(4),
        ),
    ),
    # Parenthesized first order: (dF)/(dX)
    (
        re.compile(
            _DERIV_LEFT
            + r"\(+\s*d" + _DERIV_NAME + r"\s*\)+"
            + r"\s*/\s*"
            + r"\(+\s*d" + _DERIV_NAME + r"\s*\)+"
            + _DERIV_RIGHT
        ),
        lambda m: "Derivative({}, {})".format(
            m.group(1) or m.group(2),
            m.group(3) or m.group(4),
        ),
    ),
]


def _rewrite_leibniz_derivatives(s: str, notes: List[str]) -> str:
    original = s
    for pat, repl in _DERIV_PATTERNS:
        s = pat.sub(repl, s)
    # OCR fallback: Leibniz notation where the division bar was lost.
    # Shape: 'd <F> ^? d <V>' with no slash. The '^' between the two d's is
    # the residue of an OCR'd ^ that originally exponentiated the numerator.
    # Guards: both names must be short (single uppercase letter or single
    # lowercase letter) so this doesn't fire on algebraic expressions like
    # 'd_a + d_b' or on longer English words.
    ocr_fallback = re.compile(
        _DERIV_LEFT
        + r"d\s+([A-Z]|[a-z])\s*\^\s*d\s+([A-Z]|[a-z])"
        + _DERIV_RIGHT
    )
    before = s
    s = ocr_fallback.sub(lambda m: f"Derivative({m.group(1)}, {m.group(2)})", s)
    if s != original:
        notes.append("Rewrote Leibniz derivative notation (d/dx, \u2202/\u2202t) into Derivative(fn, var[, order]).")
    if s != before:
        notes.append("Applied OCR derivative fallback (slash-less d<F>^d<V> -> Derivative(F, V)).")
    return s


def _rewrite_college_math_structures(s: str, notes: List[str]) -> str:
    s = _rewrite_bracket_function_calls(s, notes)
    s = _rewrite_mod_notation(s, notes)
    s = _rewrite_optimization_notation(s, notes)
    s = _rewrite_limit_notation(s, notes)
    s = _rewrite_sum_notation(s, notes)
    s = _rewrite_integral_notation(s, notes)
    s = _rewrite_leibniz_derivatives(s, notes)
    return s


def _safe_unary_callable(sp, fn_name: str):
    builtin = getattr(sp, fn_name, None)
    symbolic = sp.Function(fn_name)

    def _call(arg):
        if callable(builtin):
            try:
                return builtin(arg)
            except Exception:
                pass
        return symbolic(arg)

    return _call


def normalize_text(s: str) -> str:
    ext_unicode_map, ext_latex_map = _load_external_symbol_maps()
    merged_latex_map = dict(LATEX_MAP)
    merged_latex_map.update(ext_latex_map)
    merged_unicode_map = dict(UNICODE_MAP)
    merged_unicode_map.update(ext_unicode_map)
    s=_strip_comments_and_join_lines(s)
    s=_strip_latex_display_wrappers(s)
    s=_cleanup_latex_spacing_commands(s)
    s=_cleanup_escaped_latex_punctuation(s)
    s=_rewrite_latex_text_blocks(s)
    s=_rewrite_latex_fractions(s)
    s=_rewrite_latex_binomials(s)
    s=_rewrite_prime_identifiers(s)
    s,_=normalize_quantum_notation(s)
    s=s.replace("\u03b8","theta").replace("\u0398","Theta")
    for k,v in sorted(merged_latex_map.items(), key=lambda kv: len(kv[0]), reverse=True): s=s.replace(k,v)
    s=s.replace(r"\\begin{pmatrix}", "(")
    s=s.replace(r"\\end{pmatrix}", ")")
    s=s.replace("&", ",")
    s=s.replace(r"\\\\", ";")
    s=s.replace("\\{", " { ").replace("\\}"," } ")
    s=re.sub(r"([A-Za-z]\w*)\s*\^\s*\{\s*\*\s*\}", r"conjugate(\1)", s)
    s=re.sub(r"([A-Za-z]\w*)\s*\^\s*\(\s*\*\s*\)", r"conjugate(\1)", s)
    s=re.sub(r"\^\s*\{\s*([0-9A-Za-z_]+)\s*\}", r"^\1", s)
    s=re.sub(r"\^\s*\(\s*([0-9A-Za-z_]+)\s*\)", r"^\1", s)
    s=s.replace("{"," ").replace("}"," ")
    for k,v in _SUBSCRIPT_DIGITS.items(): s=s.replace(k,v)
    for k,v in GREEK_MAP.items(): s=s.replace(k,v)
    for k,v in merged_unicode_map.items(): s=s.replace(k,v)

    s=re.sub(r"\bi(?=\s*hbar\b)", "I", s)
    s=re.sub(r"([A-Za-z]\w*)\s*\^(?=\s*[,\)\]])", r"\1", s)
    s=re.sub(r"\[\s*([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)\s*\]", r"Commutator(\1, \2)", s)

    s=re.sub(r"\b([A-Za-z]\w*)\s+in\s*\{\s*([^\}]+)\s*\}", r"Contains(\1, FiniteSet(\2))", s)
    for _ in range(6):
        s2=re.sub(r"\|\s*([^|]+?)\s*\|", r"Abs(\1)", s)
        if s2==s: break
        s=s2

    s=s.replace('\\\\','\\')
    s=re.sub(r"\)\s*([A-Za-z_])", r")*\1", s)
    if s.count('(')>s.count(')'): s=s+(')'*(s.count('(')-s.count(')')))
    if s.startswith("(") and s.endswith(")"): s=s[1:-1].strip()
    # Order matters: the comma-bounded range rule must run before the generic
    # dotdot rule. Otherwise ',..,' becomes ',, ,' and later cleanup strips it
    # to ',' — losing the single-space marker downstream code relies on.
    s=re.sub(r",\s*\.\.+\s*,", ", ", s)
    s=re.sub(r"\s*\.\.\s*", ", ", s)  # dotdot range placeholder
    s=re.sub(r"\s+", " ", s)
    s=s.replace("==","=")
    s=re.sub(r"\s*(?:<=>|<->|=>|->|<-)\s*", " = ", s)
    s=re.sub(r"\binf\b","oo",s,flags=re.IGNORECASE)
    s = _cleanup_operator_punctuation_artifacts(s)
    s = re.sub(r"\b(div|curl|grad|laplacian)\s+([A-Za-z_][A-Za-z0-9_]*)\b", r"\1(\2)", s)
    s = _rewrite_math_function_calls(s)
    s = re.sub(r"\s*[;,\.]+\s*(?=,)", "", s)
    s = re.sub(r"\s*[;,\.]+\s*(?=[)\]}])", "", s)
    s = re.sub(r"\s*[;,\.]+\s*$", "", s)
    return s.strip()


def maybe_wrap_expression(text: str, expression_mode: bool) -> str:
    raw = (text or "").strip()
    if not expression_mode:
        return raw
    if raw.lstrip().startswith(("Eq(", "eq(")):
        return raw

    normalized = normalize_text(raw)
    relation_ops = ("=", "!=", "<=", ">=", "<", ">", "->", "<-", "<->", "=>", "<=>")
    if any(op in normalized for op in relation_ops):
        return raw
    if normalized.lstrip().startswith(("Contains(", "And(", "Or(")):
        return raw
    return f"Eq({raw}, 0)"


def _split_top_level_equals(s: str) -> List[str]:
    parts=[]; buf=[]; depth=0
    for ch in s:
        if ch in "([{": depth+=1
        elif ch in ")]}": depth=max(0,depth-1)
        if ch=="=" and depth==0: parts.append("".join(buf)); buf=[]; continue
        buf.append(ch)
    parts.append("".join(buf)); return parts


def _handle_chained_equals(s: str, notes: List[str]) -> str:
    parts=[p.strip() for p in _split_top_level_equals(s)]
    if len(parts)>=3:
        notes.append(f"Chained equality detected; using first and last terms, dropped {len(parts)-2} middle term(s).")
        return f"{parts[0]} = {parts[-1]}"
    return s


def _rewrite_word_sum(s: str, notes: List[str]) -> str:
    s=re.sub(r"\bSum\s*_", "Sum_", s)
    plain=re.compile(r"\bSum\s+([A-Za-z]\w*)\s+([A-Za-z]\w*|\d+)\s+([A-Za-z]\w*|\d+)")
    while True:
        m=plain.search(s)
        if not m: break
        i_sym,lo,hi=m.group(1),m.group(2),m.group(3)
        tail=s[m.end():]; nxt=plain.search(tail)
        expr,rest=(tail[:nxt.start()].strip(),tail[nxt.start():]) if nxt else (tail.strip(),"")
        if not expr: break
        s=s[:m.start()]+f"Sum({expr}, ({i_sym}, {lo}, {hi}))"+rest
        notes.append("Rewrote OCR/plain Sum i lo hi into SymPy Sum(expr, (i, lo, hi)).")
    return s


def _rewrite_integral_region(s: str, notes: List[str]) -> str:
    return s


def _rewrite_cross(s: str) -> str:
    return s


def _detect_derivative_context(s: str) -> bool:
    return "Derivative(" in s


def _infer_dep_name(s: str) -> str:
    return "u"


def _rewrite_derivatives(s: str, dep_name: str, enable_functionify: bool) -> str:
    return s


def _add_dynamic_functions(sp, local: Dict[str, Any], s: str):
    for m in re.finditer(r"\b([A-Za-z]\w*)\s*\(", s):
        name=m.group(1)
        if name in local: continue
        if name in (
            "Derivative", "Eq", "Sum", "Integral", "sin", "cos", "tan", "cot", "sec", "csc",
            "asin", "acos", "atan", "sinh", "cosh", "tanh", "coth", "sech", "csch",
            "exp", "log", "sqrt", "Abs", "cross", "conjugate", "Commutator", "Contains", "FiniteSet",
            "erf", "erfc", "det", "trace", "rank", "diag", "sign", "arg", "Min", "Max", "binomial",
            "Limit", "Prod", "Product", "Mod", "gcd", "lcm", "floor", "ceiling",
            "Expectation", "Var", "Cov", "Pr", "argmin", "argmax", "Min_over", "Max_over",
        ):
            continue
        local[name]=sp.Function(name)


def _add_bare_symbol_identifiers(sp, local: Dict[str, Any], s: str):
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", s):
        name = m.group(1)
        if name in local:
            continue
        if name in ("and", "or", "not", "in", "True", "False"):
            continue
        # Function calls are handled separately by _add_dynamic_functions.
        tail = s[m.end():]
        if tail.lstrip().startswith("("):
            continue
        local[name] = sp.Symbol(name, real=True)


def _sanitize_python_identifiers(expr: str, notes: List[str]) -> tuple[str, Dict[str, str]]:
    alias_map: Dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        safe = pythonize_identifier(token)
        if safe != token:
            alias_map[token] = safe
            return safe
        return token

    sanitized = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", _replace, expr)
    if alias_map:
        pairs = ", ".join(f"{src}->{dst}" for src, dst in sorted(alias_map.items()))
        notes.append(f"Sanitized Python keyword identifiers for parsing: {pairs}.")
    return sanitized, alias_map


def _classroom_fallback_rewrite(expr: str) -> tuple[str, list[str]]:
    notes=[]; t=(expr or "").strip()
    if "=" not in t and not t.lstrip().startswith("Eq("):
        t=f"Eq({t}, 0)"; notes.append("Fallback wrapped expression as Eq(expr, 0).")
    return t,notes


def debug_rewrite(text: str) -> dict:
    notes=[]; normalized=normalize_text(text)
    rewritten=_rewrite_college_math_structures(normalized, notes)
    rewritten=_handle_chained_equals(rewritten, notes)
    rewritten=_rewrite_word_sum(rewritten, notes)
    if "=" not in rewritten and not rewritten.lstrip().startswith("Eq("):
        rewritten=f"Eq({rewritten}, 0)"
    return {"normalized_input":normalized,"rewritten_input":rewritten,"notes":notes,"derivative_context":False,"dep_name":""}


def dump_codepoints(s: str) -> List[Dict[str, Any]]:
    """Return per-codepoint diagnostics for a string. Used by CLI --dump-codepoints."""
    import unicodedata
    out: List[Dict[str, Any]] = []
    for ch in s:
        cp = ord(ch)
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = ""
        out.append({
            "char": ch,
            "codepoint": f"U+{cp:04X}",
            "decimal": cp,
            "category": unicodedata.category(ch),
            "name": name,
        })
    return out


def parse_equation(text: str) -> Parsed:
    sp, parse_expr, std_tx, impl_mul, convert_xor = _try_import_sympy()
    if sp is None: raise ParseError("SymPy not installed. Install: python -m pip install sympy")
    normalized=normalize_text(text)
    if not normalized: raise ParseError("Empty equation input")
    ok,msg=_balance_check(normalized)
    if not ok: raise ParseError(msg)

    notes=[]
    rewritten=_rewrite_college_math_structures(normalized, notes)
    rewritten=_handle_chained_equals(rewritten, notes)
    rewritten=_rewrite_word_sum(rewritten, notes)

    # Membership rescue (single + chained OCR forms)
    if " in " in rewritten and "Contains(" not in rewritten:
        try:
            rewritten = rewritten.replace(":", " ")
            matches = list(re.finditer(r"\b([A-Za-z]\w*)\s+in\s+", rewritten))
            if len(matches) >= 2:
                m1, m2 = matches[0], matches[1]
                v1 = m1.group(1)
                rhs1 = rewritten[m1.end():m2.start()].strip()
                v2 = m2.group(1)
                rhs2 = rewritten[m2.end():].strip()
                rhs1 = rhs1.replace("{", "").replace("}", "")
                rhs2 = rhs2.replace("{", "").replace("}", "")
                rhs1 = re.sub(r"\s*\.\.\s*", ", ", rhs1)
                rhs2 = re.sub(r"\s*\.\.\s*", ", ", rhs2)
                rewritten = f"And(Contains({v1}, FiniteSet({rhs1})), Contains({v2}, FiniteSet({rhs2})))"
                notes.append("Applied chained membership rescue rewrite.")
            else:
                left, right = rewritten.split(" in ", 1)
                m = re.findall(r"([A-Za-z]\w*)", left)
                if m:
                    var = m[-1]
                    right = right.replace("{", "").replace("}", "")
                    right = re.sub(r"\s*\.\.\s*", ", ", right)
                    rewritten = f"Contains({var}, FiniteSet({right}))"
                    notes.append("Applied membership rescue rewrite.")
        except Exception:
            pass

    _report_unsupported_unicode(rewritten)
    if "=" not in rewritten and not rewritten.lstrip().startswith(("Eq(","eq(")):
        if rewritten.lstrip().startswith(("Contains(", "And(", "Or(")):
            rewritten=f"Eq({rewritten}, True)"; notes.append("Predicate input detected; wrapped as Eq(predicate, True).")
        else:
            rewritten=f"Eq({rewritten}, 0)"; notes.append("Expression-only input detected; wrapped as Eq(expr, 0).")
    parse_ready, parse_aliases = _sanitize_python_identifiers(rewritten, notes)
    x,t=sp.Symbol("x",real=True),sp.Symbol("t",real=True)
    det_fn = _safe_unary_callable(sp, "det")
    trace_fn = _safe_unary_callable(sp, "trace")
    rank_fn = _safe_unary_callable(sp, "rank")
    local={"x":x,"t":t,"I":sp.I,"pi":sp.pi,"oo":sp.oo,
           "N":sp.Symbol("N",integer=True,positive=True),"E":sp.Symbol("E",real=True),
           "sqrt":sp.sqrt,"Abs":sp.Abs,"Sum":sp.Sum,"Integral":sp.Integral,"Contains":sp.Contains,"FiniteSet":sp.FiniteSet,"And":sp.And,"Or":sp.Or,"Not":sp.Not,
           "sin":sp.sin,"cos":sp.cos,"tan":sp.tan,"cot":sp.cot,"sec":sp.sec,"csc":sp.csc,
           "asin":sp.asin,"acos":sp.acos,"atan":sp.atan,
           "sinh":sp.sinh,"cosh":sp.cosh,"tanh":sp.tanh,"coth":sp.coth,"sech":sp.sech,"csch":sp.csch,
           "exp":sp.exp,"log":sp.log,"erf":sp.erf,"erfc":sp.erfc,
           "det":det_fn,"trace":trace_fn,"rank":rank_fn,"diag":sp.diag,"binomial":sp.binomial,
           "sign":sp.sign,"arg":sp.arg,
           "Min":sp.Min,"Max":sp.Max,
           "Limit":sp.Limit,"Prod":sp.Product,"Product":sp.Product,"Mod":sp.Mod,
           "gcd":sp.gcd,"lcm":sp.lcm,"floor":sp.floor,"ceiling":sp.ceiling,
           "Expectation":sp.Function("Expectation"),"Var":sp.Function("Var"),"Cov":sp.Function("Cov"),"Pr":sp.Function("Pr"),
           "argmin":sp.Function("argmin"),"argmax":sp.Function("argmax"),
           "Min_over":sp.Function("Min_over"),"Max_over":sp.Function("Max_over"),
           "cross":sp.Function("cross"),"Commutator":sp.Function("Commutator"),"conjugate":sp.conjugate,
           "hbar":sp.Symbol("hbar",positive=True,real=True),"m":sp.Symbol("m",positive=True,real=True),
           "epsilon_0":sp.Symbol("epsilon_0",positive=True,real=True),"mu_0":sp.Symbol("mu_0",positive=True,real=True),"epsilon":sp.Symbol("epsilon",positive=True,real=True)}
    for original, safe in parse_aliases.items():
        if safe not in local:
            local[safe] = sp.Symbol(original, real=True)
    _add_dynamic_functions(sp, local, parse_ready)
    _add_bare_symbol_identifiers(sp, local, parse_ready)
    transformations = std_tx + (impl_mul, convert_xor)

    try:
        if parse_ready.lstrip().startswith(("eq(","Eq(")):
            eq=parse_expr(parse_ready, local_dict=local, transformations=transformations, evaluate=False)
            if not isinstance(eq, sp.Equality): raise ParseError("Parsed 'Eq(...)' did not produce an Equality.")
        else:
            lhs_s, rhs_s = [p.strip() for p in parse_ready.split("=",1)]
            lhs=parse_expr(lhs_s, local_dict=local, transformations=transformations, evaluate=False)
            rhs=parse_expr(rhs_s, local_dict=local, transformations=transformations, evaluate=False)
            eq=sp.Eq(lhs, rhs, evaluate=False)
    except Exception as e:
        try:
            fb_expr, fb_notes = _classroom_fallback_rewrite(parse_ready)
            eq=parse_expr(fb_expr, local_dict=local, transformations=transformations, evaluate=False)
            notes.extend(fb_notes); notes.append("Applied classroom fallback rewrite after parse failure.")
        except Exception:
            raise ParseError(f"SymPy parse failed: {e}\n\nnormalized_input:\n{normalized}\n\nrewritten_input:\n{rewritten}\n\nparse_ready:\n{parse_ready}")

    free_syms=sorted({str(sym) for sym in eq.free_symbols if str(sym) not in ("x","t")})
    return Parsed(sp=sp,eq=eq,solved=None,dep_name="",x=x,t=t,params=list(free_syms),notes=notes,normalized_input=normalized,rewritten_input=rewritten)


def emit_python(parsed: Parsed, mode: str, settings: Dict[str, Any]) -> str:
    sp=parsed.sp; eq_s=sp.sstr(parsed.eq)
    params=list(dict.fromkeys(parsed.params)); decl=[]; locals_lines=[]
    skip={
        "pi","oo","sqrt","Abs","Sum","Integral","Contains","FiniteSet","Eq","cross","conjugate","Commutator",
        "epsilon_0","mu_0","epsilon","sin","cos","tan","cot","sec","csc","asin","acos","atan",
        "sinh","cosh","tanh","coth","sech","csch","exp","log","erf","erfc","det","trace","rank","diag",
        "binomial","Min","Max","sign","arg","Limit","Prod","Product","Mod","gcd","lcm","floor","ceiling",
        "Expectation","Var","Cov","Pr","argmin","argmax","Min_over","Max_over",
    }
    for name in params:
        if name in skip:
            continue
        python_name = pythonize_identifier(name)
        decl.append(f"{python_name} = sp.Symbol({name!r}, real=True)")
        locals_lines.append(f"    {name!r}: {python_name},")
    lines=[
        "#!/usr/bin/env python3", '"""Generated by physics_codegen (SymPy-backed)."""', "", "from __future__ import annotations", "import sympy as sp", "",
        f"# SymPy {sp.__version__}", "", "pi = sp.pi", "oo = sp.oo", "sqrt = sp.sqrt", "Abs = sp.Abs", "Sum = sp.Sum", "Integral = sp.Integral", "Contains = sp.Contains", "FiniteSet = sp.FiniteSet", "Eq = sp.Eq",
        "sin = sp.sin", "cos = sp.cos", "tan = sp.tan", "cot = sp.cot", "sec = sp.sec", "csc = sp.csc",
        "asin = sp.asin", "acos = sp.acos", "atan = sp.atan",
        "sinh = sp.sinh", "cosh = sp.cosh", "tanh = sp.tanh", "coth = sp.coth", "sech = sp.sech", "csch = sp.csch",
        "exp = sp.exp", "log = sp.log", "erf = sp.erf", "erfc = sp.erfc",
        "def _safe_det(arg):", "    try:", "        return sp.det(arg)", "    except Exception:", "        return sp.Function('det')(arg)",
        "def _safe_trace(arg):", "    try:", "        return sp.trace(arg)", "    except Exception:", "        return sp.Function('trace')(arg)",
        "def _safe_rank(arg):", "    try:", "        return sp.rank(arg)", "    except Exception:", "        return sp.Function('rank')(arg)",
        "det = _safe_det", "trace = _safe_trace", "rank = _safe_rank", "diag = sp.diag", "binomial = sp.binomial",
        "Min = sp.Min", "Max = sp.Max", "sign = sp.sign", "arg = sp.arg",
        "Limit = sp.Limit", "Prod = sp.Product", "Product = sp.Product", "Mod = sp.Mod",
        "gcd = sp.gcd", "lcm = sp.lcm", "floor = sp.floor", "ceiling = sp.ceiling",
        "Expectation = sp.Function('Expectation')", "Var = sp.Function('Var')", "Cov = sp.Function('Cov')", "Pr = sp.Function('Pr')",
        "argmin = sp.Function('argmin')", "argmax = sp.Function('argmax')",
        "Min_over = sp.Function('Min_over')", "Max_over = sp.Function('Max_over')",
        "cross = sp.Function('cross')", "Commutator = sp.Function('Commutator')", "conjugate = sp.conjugate",
        "epsilon_0 = sp.Symbol('epsilon_0', positive=True, real=True)", "mu_0 = sp.Symbol('mu_0', positive=True, real=True)", "epsilon = sp.Symbol('epsilon', positive=True, real=True)", "",
    ]
    if decl: lines += decl + [""]
    lines += [
        "_LOCALS = {", "    'pi': pi,", "    'oo': oo,", "    'sqrt': sqrt,", "    'Abs': Abs,", "    'Sum': Sum,", "    'Integral': Integral,", "    'Contains': Contains,", "    'FiniteSet': FiniteSet,", "    'Eq': Eq,",
        "    'sin': sin,", "    'cos': cos,", "    'tan': tan,", "    'cot': cot,", "    'sec': sec,", "    'csc': csc,",
        "    'asin': asin,", "    'acos': acos,", "    'atan': atan,",
        "    'sinh': sinh,", "    'cosh': cosh,", "    'tanh': tanh,", "    'coth': coth,", "    'sech': sech,", "    'csch': csch,",
        "    'exp': exp,", "    'log': log,", "    'erf': erf,", "    'erfc': erfc,",
        "    'det': det,", "    'trace': trace,", "    'rank': rank,", "    'diag': diag,", "    'binomial': binomial,",
        "    'Min': Min,", "    'Max': Max,", "    'sign': sign,", "    'arg': arg,",
        "    'Limit': Limit,", "    'Prod': Prod,", "    'Product': Product,", "    'Mod': Mod,",
        "    'gcd': gcd,", "    'lcm': lcm,", "    'floor': floor,", "    'ceiling': ceiling,",
        "    'Expectation': Expectation,", "    'Var': Var,", "    'Cov': Cov,", "    'Pr': Pr,",
        "    'argmin': argmin,", "    'argmax': argmax,", "    'Min_over': Min_over,", "    'Max_over': Max_over,",
        "    'cross': cross,", "    'Commutator': Commutator,", "    'conjugate': conjugate,", "    'epsilon_0': epsilon_0,", "    'mu_0': mu_0,", "    'epsilon': epsilon,"
    ]
    lines += locals_lines
    lines += ["}", "", f"eq = sp.sympify({eq_s!r}, locals=_LOCALS)"]
    return "\n".join(lines)+"\n"









