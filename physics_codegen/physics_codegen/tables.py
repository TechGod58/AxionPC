from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

from .naming import pythonize_identifier

_RESERVED = {
    "Sum",
    "Integral",
    "Derivative",
    "Eq",
    "sqrt",
    "Abs",
    "cross",
    "grad",
    "or",
    "pi",
    "oo",
    "hbar",
    "epsilon",
    "epsilon_0",
    "mu_0",
    "i",
    "I",
    "Contains",
    "FiniteSet",
    "And",
    "Or",
    "conjugate",
    "Commutator",
}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
_TOKEN_RE = re.compile(r"\\[A-Za-z]+|<=|>=|!=|==|\*\*|->|[A-Za-z_][A-Za-z0-9_]*|\d+\.\d+|\d+|[^\sA-Za-z0-9_]")


@lru_cache(maxsize=1)
def load_symbol_catalog() -> Dict[str, object]:
    path = Path(__file__).resolve().parent / "data" / "conversion_catalog.json"
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    entries = payload.get("entries", [])
    payload["entries_by_token"] = {entry["token"]: entry for entry in entries}
    return payload


def _split_top_level(expr: str, seps: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in expr:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)

        if depth == 0 and ch in seps:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = [ch]
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _split_equation(eq: str) -> Tuple[str, str]:
    if "=" in eq:
        lhs, rhs = eq.split("=", 1)
        return lhs.strip(), rhs.strip()
    return eq.strip(), ""


def _strip_leading_sign(term: str) -> str:
    return term[1:].strip() if term[:1] in "+-" else term.strip()


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text or "")


def _ordered_unique(tokens: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for token in tokens:
        if token not in seen:
            ordered.append(token)
            seen.add(token)
    return ordered


def _default_row(token: str, count: int) -> Dict[str, str | int]:
    if _NUMBER_RE.match(token):
        return {
            "symbol": token,
            "normalized": token,
            "python": token,
            "kind": "number",
            "count": count,
            "description": "Numeric literal copied directly into Python code.",
        }

    if _IDENTIFIER_RE.match(token):
        python_name = pythonize_identifier(token)
        description = "Identifier kept as a SymPy symbol name in generated code."
        if token in _RESERVED:
            description = "Reserved SymPy helper or constant used directly in generated code."
        elif python_name != token:
            description = f"Identifier is made Python-safe as {python_name} in generated code."
        return {
            "symbol": token,
            "normalized": token,
            "python": python_name,
            "kind": "identifier" if token not in _RESERVED else "reserved",
            "count": count,
            "description": description,
        }

    return {
        "symbol": token,
        "normalized": token,
        "python": token,
        "kind": "symbol",
        "count": count,
        "description": "Symbol copied as-is into the rewritten expression.",
    }


def build_symbol_table(text: str, debug_obj: Dict | None = None) -> List[Dict[str, str | int]]:
    catalog = load_symbol_catalog()
    entries_by_token = catalog.get("entries_by_token", {})
    counts: Dict[str, int] = {}
    raw_tokens = _tokenize(text)
    for token in raw_tokens:
        counts[token] = counts.get(token, 0) + 1

    rows: List[Dict[str, str | int]] = []
    for token in _ordered_unique(raw_tokens):
        row = dict(entries_by_token.get(token, _default_row(token, counts[token])))
        row["symbol"] = token
        row["count"] = counts[token]

        if token not in entries_by_token and debug_obj:
            rewritten = (debug_obj.get("rewritten_input", "") or "")
            if token and token not in rewritten and row.get("kind") == "symbol":
                row["description"] = "Symbol appears in the source input and is handled during rewrite/parsing."
        rows.append(row)

    return rows


def build_code_table(debug_obj: Dict) -> List[Dict[str, str]]:
    norm = (debug_obj or {}).get("normalized_input", "")
    rew = (debug_obj or {}).get("rewritten_input", "")
    notes = (debug_obj or {}).get("notes", []) or []

    rows: List[Dict[str, str]] = [
        {"stage": "normalized_input", "value": norm},
        {"stage": "rewritten_input", "value": rew},
    ]

    lhs, rhs = _split_equation(rew)
    if lhs:
        rows.append({"stage": "lhs", "value": lhs})
    if rhs:
        rows.append({"stage": "rhs", "value": rhs})

    if lhs:
        lhs_terms = _split_top_level(lhs, "+-")
        for i, term in enumerate(lhs_terms, 1):
            rows.append({"stage": f"lhs_term_{i}", "value": term})
            factors = [factor.strip() for factor in _strip_leading_sign(term).split("*") if factor.strip()]
            for j, factor in enumerate(factors, 1):
                rows.append({"stage": f"lhs_term_{i}_factor_{j}", "value": factor})

    if rhs:
        rhs_terms = _split_top_level(rhs, "+-")
        for i, term in enumerate(rhs_terms, 1):
            rows.append({"stage": f"rhs_term_{i}", "value": term})
            factors = [factor.strip() for factor in _strip_leading_sign(term).split("*") if factor.strip()]
            for j, factor in enumerate(factors, 1):
                rows.append({"stage": f"rhs_term_{i}_factor_{j}", "value": factor})

    for note in notes:
        rows.append({"stage": "rewrite_note", "value": str(note)})

    return rows


def build_tables_bundle(text: str, debug_obj: Dict) -> Dict[str, object]:
    normalized_input = (debug_obj or {}).get("normalized_input", "") or ""
    symbol_rows = build_symbol_table(normalized_input or text, debug_obj)
    code_rows = build_code_table(debug_obj)
    return {
        "catalog_version": load_symbol_catalog().get("version", 1),
        "source_input": text,
        "normalized_input": normalized_input,
        "rewritten_input": (debug_obj or {}).get("rewritten_input", ""),
        "notes": (debug_obj or {}).get("notes", []) or [],
        "symbol_table_source": "normalized_input" if normalized_input else "source_input",
        "symbol_table": symbol_rows,
        "code_table": code_rows,
    }


def symbol_table_markdown(rows: List[Dict[str, str | int]]) -> str:
    lines = [
        "| Symbol | Normalized | Python | Kind | Count | Description |",
        "|---|---|---|---|---:|---|",
    ]
    for row in rows:
        description = str(row.get("description", "")).replace("|", "\\|")
        lines.append(
            f"| {row.get('symbol', '')} | {row.get('normalized', '')} | `{row.get('python', '')}` | "
            f"{row.get('kind', '')} | {row.get('count', 0)} | {description} |"
        )
    return "\n".join(lines)


def code_table_markdown(rows: List[Dict[str, str]]) -> str:
    lines = [
        "| Stage | Value |",
        "|---|---|",
    ]
    for row in rows:
        value = (row.get("value") or "").replace("|", "\\|")
        lines.append(f"| {row.get('stage', '')} | `{value}` |")
    return "\n".join(lines)


def as_json(symbol_rows, code_rows) -> str:
    return json.dumps({"symbol_table": symbol_rows, "code_table": code_rows}, indent=2, ensure_ascii=False)
