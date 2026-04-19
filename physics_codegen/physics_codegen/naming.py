from __future__ import annotations

import keyword
import re

_INVALID_IDENTIFIER_CHARS = re.compile(r"\W")


def pythonize_identifier(name: str) -> str:
    candidate = _INVALID_IDENTIFIER_CHARS.sub("_", name or "")
    if not candidate:
        candidate = "symbol"
    if candidate[0].isdigit():
        candidate = f"_{candidate}"
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_"
    return candidate
