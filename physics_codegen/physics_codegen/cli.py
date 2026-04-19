from __future__ import annotations

import argparse
import json
import os
import sys
import traceback


def _write_json_maybe(obj, out_path: str | None) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        try:
            print(text)
        except UnicodeEncodeError:
            fallback = text.encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(sys.stdout.encoding or "utf-8", errors="ignore")
            print(fallback)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="physics_codegen")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("gui")

    p_rewrite = sub.add_parser("rewrite")
    p_rewrite.add_argument("--text", required=True)
    p_rewrite.add_argument("--dump-codepoints", action="store_true")
    p_rewrite.add_argument("--out-json", default=None)
    p_rewrite.add_argument(
        "--expression-mode",
        action="store_true",
        help="Treat input as expression and wrap as Eq(expr, 0) when needed.",
    )

    p_fund = sub.add_parser("fundamentals")
    p_fund.add_argument("--format", choices=["json", "markdown"], default="markdown")
    p_fund.add_argument("--out", default=None)

    p_tables = sub.add_parser("tables", help="Generate symbol/code tables from equation text")
    p_tables.add_argument("--text", required=True)
    p_tables.add_argument("--format", choices=["json", "markdown"], default="json")
    p_tables.add_argument("--out", default=None)
    p_tables.add_argument("--expression-mode", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "rewrite":
        try:
            from .equation_any import debug_rewrite, dump_codepoints, maybe_wrap_expression

            text_in = maybe_wrap_expression(args.text, args.expression_mode)

            out = debug_rewrite(text_in)
            if args.dump_codepoints:
                out["codepoints_normalized"] = dump_codepoints(out["normalized_input"])
            _write_json_maybe(out, args.out_json)
            return 0
        except Exception:
            traceback.print_exc()
            return 2

    if args.cmd == "fundamentals":
        try:
            from .fundamentals import FUNDAMENTALS, as_markdown_table

            if args.format == "json":
                _write_json_maybe(FUNDAMENTALS, args.out)
            else:
                text = as_markdown_table()
                if args.out:
                    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
                    with open(args.out, "w", encoding="utf-8") as f:
                        f.write(text + "\n")
                else:
                    print(text)
            return 0
        except Exception:
            traceback.print_exc()
            return 2

    if args.cmd == "tables":
        try:
            from .equation_any import debug_rewrite, maybe_wrap_expression
            from .tables import build_tables_bundle, symbol_table_markdown, code_table_markdown

            text_in = maybe_wrap_expression(args.text, args.expression_mode)

            dbg = debug_rewrite(text_in)
            bundle = build_tables_bundle(text_in, dbg)
            if args.format == "json":
                _write_json_maybe(bundle, args.out)
            else:
                text = (
                    "## Symbol Table\n\n"
                    + symbol_table_markdown(bundle.get("symbol_table", []))
                    + "\n\n## Code Table\n\n"
                    + code_table_markdown(bundle.get("code_table", []))
                    + "\n"
                )
                if args.out:
                    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
                    with open(args.out, "w", encoding="utf-8") as f:
                        f.write(text)
                else:
                    print(text)
            return 0
        except Exception:
            traceback.print_exc()
            return 2

    if args.cmd == "gui":
        try:
            from .gui import main as gui_main
            return gui_main()
        except Exception:
            traceback.print_exc()
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
