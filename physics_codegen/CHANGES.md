# AxionPC physics_codegen — patch log

**Drop-in replacement for the `physics_codegen/` directory.**
Working directory: the one that contains `physics_codegen/`, `tests/`, `tools/`, etc.

## Run instructions

```
cd physics_codegen
python -m pip install -r requirements.txt

# CLI sanity check
python -m physics_codegen.cli rewrite --text "i*ℏ*∂Ψ/∂t = -ℏ²/(2*m) * ∂²Ψ/∂x² + V*Ψ"

# Rewriter corpus (parser/rewriter assertions)
python tests/run_quantum_corpus.py

# Validation corpus (dimensional analysis + numerical sampling)
python tools/qa/run_converter_validation.py
```

All three must pass on a clean install. Reports land in `generated/`.

## Scoreboard, before -> after

```
Rewriter corpus:    3/4  ->  7/7   (added 3 cases; fixed pre-existing sum_plain_ocr)
Validation corpus:  2/2  ->  2/2   (no change in coverage, runner now v2-aware)
Full regression:    new  ->  17/17 (14 positive physics cases + 3 negative guards)
BOMs in tree:       11   ->  0
Missing function:   dump_codepoints (CLI --dump-codepoints crashed) -> fixed
```

## Bugs fixed

### 1. Derivative rewriter was a stub — broke physics silently

`_rewrite_derivatives` in the shipped `equation_any.py` was `return s` (line
533, pre-patch). Result: Schrödinger's equation parsed without error but
produced structurally wrong SymPy because `∂Ψ/∂t` became a symbol named
`dPsi` divided by a symbol named `dt`, not `Derivative(Psi, t)`.

This is the category of bug that is worse than a crash — output looks plausible
and is silently wrong.

Fix: new `_rewrite_leibniz_derivatives` called from
`_rewrite_college_math_structures`. Five patterns:

* mixed partial: `d^2 u / dx dy` -> `Derivative(u, x, y)`
* 2nd order: `d^2 F / dX^2` -> `Derivative(F, X, 2)` (glued or spaced)
* 1st order: `dF/dX` -> `Derivative(F, X)` (glued or spaced)
* parenthesized forms for LaTeX `\frac` output: `((d^2 y))/((dx^2))`
* OCR fallback for slash-less Leibniz: `d A ^ d t` -> `Derivative(A, t)`

Boundary guards reject English words starting with 'd': `density/diameter`,
`distance/duration`, `drift/decay`, `dose/day` all stay as-is. The glued form
only accepts names that are a single lowercase letter or start with uppercase
(physics convention: dy, du, dx, dPsi, dPhi). The spaced form accepts any
identifier because whitespace disambiguates.

### 2. `Integral sin(x) dx = ...` failed to parse

`_rewrite_integral_notation` expected whitespace before `dx`, but an earlier
pass in `normalize_text` (the implicit-multiplication insertion) had already
rewritten `)` + space + letter to `)*letter`, turning `sin(x) dx` into
`sin(x)*dx`. The integral regex never matched.

Fix: integral separator regex accepts whitespace OR `*`. Spaced form still
works, `*`-glued form now also works.

### 3. `,..,` range placeholder silently lost its space (pre-existing)

`V(x1,x2,..,xN,t)` was supposed to normalize to `V(x1,x2, xN,t)` (comma,
space, identifier). It was producing `V(x1,x2,xN,t)` (no space). Root cause:
two dotdot rewrites in `normalize_text` ran in the wrong order — the generic
`..` -> `, ` rule fired first on `,..,` and produced `,, ,`, which later
comma-cleanup passes then collapsed to a single comma.

Fix: the specific `,\s*\.\.+\s*,` -> `, ` rule runs before the generic one.

### 4. `dump_codepoints` missing — CLI `rewrite --dump-codepoints` crashed

`cli.py` imports `dump_codepoints` from `equation_any` but the function was
never defined. Any invocation of `--dump-codepoints` raised ImportError before
it could do any work. Also, the plain `rewrite` path imported the same symbol
and crashed even when the flag wasn't used.

Fix: added `dump_codepoints` in `equation_any.py`. Returns per-character
Unicode diagnostics (codepoint, decimal, category, name).

### 5. Dead regex removed

Line 441 (pre-patch) had a derivative-looking regex with no `/` between the
two `d` groups — that regex only matched the specific OCR form where the
division bar is lost. I initially removed it thinking it was dead code, then
discovered the `commutator_heisenberg_ocr` test case depends on it, and
restored it as an explicit OCR fallback with tighter guards.

## BOM strip

10 files had UTF-8 BOMs (`\ufeff` byte-order mark at file start). On Windows
this is invisible; on Linux and macOS it breaks shebangs, poisons `json.load`,
and forces downstream consumers to use `utf-8-sig` everywhere. Stripped.

Affected files:
* `physics_codegen/cli.py`
* `physics_codegen/fundamentals.py`
* `physics_codegen/guided.py`
* `physics_codegen/quantum_grammar.py`
* `physics_codegen/equation_any.py`
* `tests/converter_validation_cases_v1.json`
* `tests/quantum_corpus_v1.json`
* `tests/run_quantum_corpus.py`
* `tools/qa/run_converter_validation.py`
* `tools/run_symbol_ingestion_smoke.py`

Legacy corpus files kept in place for backward compatibility. The generated
report in `generated/quantum_corpus_report.json` was also BOM-polluted because
the runner wrote with `encoding='utf-8-sig'` — that's been switched to plain
`utf-8`.

## New test corpus format (v2)

Two new files with a shared versioned envelope:

### `tests/rewriter_corpus_v2.json` (kind: "rewriter_corpus")

Parser and rewriter assertions. 7 cases including full Schrödinger, SHM in
Leibniz notation, and integral-with-RHS coverage that didn't exist before.

### `tests/validation_corpus_v2.json` (kind: "validation_corpus")

Semantic and physical validation with dimensional analysis metadata and
numerical samplers. Same 2 cases as v1 wrapped in the new envelope.

### Envelope shape

```json
{
  "schema_version": 2,
  "kind": "rewriter_corpus" | "validation_corpus",
  "description": "...",
  "schema": {"required": [...], "optional": [...]},
  "cases": [...]
}
```

Both runners autodetect the format: versioned envelope preferred, legacy flat
list accepted. Migration is zero-break. The `kind` field is validated against
the expected kind so you can't accidentally feed a validation corpus to the
rewriter runner.

## Architecture note for the next pass

`_rewrite_college_math_structures` pipeline order now matters:
`bracket -> mod -> optim -> limit -> sum -> integral -> derivative`.

Integral runs before derivative because the spaced `d<var>` form at the end
of an integral (`Integral ... dx`) would otherwise compete with the Leibniz
first-order derivative pattern (`d<name>/d<name>`). Integral absorbs its own
differential first; anything that still looks like Leibniz notation after
that is genuine. Keep this invariant if you add new rewriters.

## What is still incomplete

1. **`equation_parser.py` (42 lines) and `core.py` (4 lines) remain vestigial.**
   The real work is in `equation_any.py`. They should either be deleted or
   documented as stubs. I didn't touch them to keep this patch focused.

2. **The prebuilt `dist/AxionPhysicsCodegen/` in the zip is stale.** If you
   ship this patch, regenerate the portable build via `build_portable.bat`
   so the bundled exe uses the fixed code.

3. **Derivative rewriter does not yet handle `\partial` in LaTeX fraction
   form that escapes `\frac` expansion.** The most common shapes work; exotic
   edge cases with nested `\frac{\partial^2 f}{\partial x \partial y}` may
   still need hand-coaxing. Not in the test corpus yet.
