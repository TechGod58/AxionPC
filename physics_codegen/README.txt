physics_codegen

This project converts equations into SymPy-based Python code.

It is no longer limited to quantum physics equations. The current direction is:
- accept general equations
- include JSON symbol definitions for college-level math and physics domains
- show how the equation was normalized and rewritten
- show a table of symbols, numbers, and operators with their code representation
- save that table data as JSON

Key files:
- physics_codegen\gui.py
- physics_codegen\equation_any.py
- physics_codegen\tables.py
- physics_codegen\data\conversion_catalog.json
- physics_codegen\data\symbol_definitions.json

Run the GUI from the project folder in source/developer mode:

  python -m pip install -r requirements.txt
  python -m physics_codegen.cli gui

Or, after a portable build exists:

  run_gui.bat

run_gui.bat launches dist\AxionPhysicsCodegen\AxionPhysicsCodegen.exe first.
It only falls back to source/developer mode when the portable EXE is missing.

Build a portable Windows app:

  python -m pip install -r requirements-packaging.txt
  build_portable.bat

Portable output:
- dist\AxionPhysicsCodegen\
- dist\AxionPhysicsCodegen_portable.zip

Launch on any Windows PC:
- Run_PhysicsCodegen.bat
- AxionPhysicsCodegen.exe

No installation is required for the portable build.
The portable folder includes its own Python runtime and bundled SymPy parser dependencies.

Verify portability:
- Run_Portable_Self_Test.bat
- userdata\portable_self_test.json

Optional MSI installer:

  build_installer.bat

Additional installer output:
- dist\AxionPhysicsCodegen-Setup.msi

MSI details:
- installer\INSTALLER_README.md

Generate table JSON from the command line:

  python -m physics_codegen.cli tables --text "ρ = Ψ*Ψ + 2/3"

What the right-side table shows:
- source token
- normalized token
- Python/SymPy representation
- token kind
- count
- short description

The JSON conversion catalog can be edited to support more notation.
