# physics_codegen

`physics_codegen` converts typed math equations into SymPy-flavored Python code and shows how the input was rewritten along the way.

This project started around quantum/physics notation, but the current goal is broader: accept general equations and make the conversion process visible and auditable.

## What the app does

- accepts plain algebra, physics notation, and many common Unicode math symbols
- includes JSON-backed symbol definitions for college-level topics:
  basic math, algebra, geometry/trig, calculus, linear algebra, proofs/logic, discrete math, probability/statistics, number theory, optimization, differential equations, plus physics domains
- normalizes the equation into a SymPy-friendly form
- generates Python code for the parsed equation
- shows a symbol table on the right side of the GUI so you can see how each symbol, operator, and number is represented in code
- exposes the same table data as JSON for saving or CLI use

## Main files

- `physics_codegen/gui.py`: desktop GUI
- `physics_codegen/equation_any.py`: normalization, rewrite, parse, and code generation
- `physics_codegen/tables.py`: builds the symbol/code tables
- `physics_codegen/data/conversion_catalog.json`: JSON-backed conversion catalog used by the GUI and CLI
- `physics_codegen/data/symbol_definitions.json`: extensible Unicode/LaTeX mapping table used by the parser

## Run the GUI

From the project folder:

```powershell
python -m pip install -r requirements.txt
python -m physics_codegen.cli gui
```

Or use:

```powershell
run_gui.bat
```

## Build a portable Windows app

From the project folder:

```powershell
python -m pip install -r requirements-packaging.txt
build_portable.bat
```

This creates:
- `dist/AxionPhysicsCodegen/` (portable folder)
- `dist/AxionPhysicsCodegen_portable.zip` (portable zip)

On a work PC, open the folder and double-click:
- `Run_PhysicsCodegen.bat` or
- `AxionPhysicsCodegen.exe`

No installation is required for the portable build.

## Optional MSI installer

If you specifically want a Windows installer package:

```powershell
build_installer.bat
```

This additionally creates:

- `dist/AxionPhysicsCodegen-Setup.msi`

For the MSI workflow and WiX details, see:

- `installer/INSTALLER_README.md`

## Generate table JSON from the CLI

```powershell
python -m physics_codegen.cli tables --text "ρ = Ψ*Ψ + 2/3"
python -m physics_codegen.cli tables --text "F = m*a + b*c - 5" --out generated\tables.json
```

The JSON output includes:

- `source_input`
- `normalized_input`
- `rewritten_input`
- `notes`
- `symbol_table`
- `code_table`

## Symbol table behavior

The right-side symbol table is meant to answer:

- what token was found in the source equation
- what normalized form the parser used
- what Python or SymPy representation was generated
- what kind of token it is

Numbers are listed too, not just named symbols.

## Notes

- the generated code targets SymPy-style symbolic expressions
- if a normalized identifier would collide with a Python keyword, the emitted Python variable name is made safe with a trailing underscore
- the conversion catalog can be extended by editing `physics_codegen/data/conversion_catalog.json`
