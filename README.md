<!-- WIP-BANNER:START -->
> [!IMPORTANT]
> **Status: Work in Progress**
>
> This repository is under active development. Content, structure, and implementation details may change frequently.
<!-- WIP-BANNER:END -->

# AxionPC

Central workspace repository for AxionPC projects, tools, and supporting scripts.

## Repository purpose

AxionPC is an educational workspace for experimental project tools, with the current active focus on physics code generation and supporting scripts. The repository is public for visibility into the tooling and project structure.

Use is governed by the repository license and licensing notice. Public visibility does not remove the educational-use boundary.

## Included Projects

- `physics_codegen/` - Equation-to-Python converter with SymPy-backed parsing, rewrite debug output, and symbol/code conversion tables.

## Quick Start

For the physics codegen app:

```powershell
cd physics_codegen
python -m pip install -r requirements.txt
python -m physics_codegen.cli gui
```

## Legal / Usage

This repository is **for educational use only**.

- Read [LICENSE](/LICENSE) for the governing terms.
- Read [LICENSING_NOTICE.md](/LICENSING_NOTICE.md) for a short legal summary.
