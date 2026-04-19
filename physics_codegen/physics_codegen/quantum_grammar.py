from __future__ import annotations
import re

QUANTUM_MAP = {
    '⟨': 'bra(',
    '⟩': ')',
    '⟪': 'bra(',
    '⟫': ')',
    '⟦': '[',
    '⟧': ']',
    '⋯': ' ',
    '…': ' ',
    '†': 'dagger',
    '⊗': ' kron ',
    '∑': 'Sum',
    '∫': 'Integral',
    '∂': 'd',
    '∇': 'grad',
}


def normalize_quantum_notation(s: str) -> tuple[str, list[str]]:
    notes = []
    t = s or ''
    for k, v in QUANTUM_MAP.items():
        if k in t:
            t = t.replace(k, v)
            notes.append(f'mapped {k} -> {v}')

    # Convert simple bra-ket: bra(psi)|phi> -> bra(psi)*phi
    t2 = re.sub(r'bra\(([^\)]+)\)\s*\|\s*([A-Za-z_][A-Za-z0-9_]*)', r'bra(\1)*\2', t)
    if t2 != t:
        notes.append('rewrote simple bra-ket product')
        t = t2

    # Normalize repeated spaces
    t = re.sub(r'\s+', ' ', t).strip()
    return t, notes
