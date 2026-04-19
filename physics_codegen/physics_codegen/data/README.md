# Conversion Table Data

`conversion_catalog.json` is the JSON-backed lookup table for the equation UI and CLI.

What it does:
- maps raw math tokens such as `ρ`, `√`, `∑`, `^`, and `=` to normalized forms
- explains the Python or SymPy form shown in the generated output
- gives the GUI a consistent source for the symbol table shown on the right side

Main fields:
- `token`: raw token from the user's equation
- `normalized`: normalized token used by the rewrite/parser layer
- `python`: how that token is represented in generated Python/SymPy code
- `kind`: token category such as `identifier`, `operator`, `function`, or `constant`
- `description`: short explanation used in docs and table output

If you want to support more notation, add entries to `conversion_catalog.json`. The dynamic table builder will still include numbers and unknown identifiers even if they are not listed here.
