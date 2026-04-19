from __future__ import annotations

import inspect
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .equation_any import ParseError, emit_python, normalize_text, parse_equation, debug_rewrite, maybe_wrap_expression
from .fundamentals import as_markdown_table
from .guided import GuidedBuilder
from .tables import build_tables_bundle, code_table_markdown, symbol_table_markdown

import physics_codegen.equation_any as _eq_mod
import physics_codegen.gui as _gui_mod

APP_TITLE = "physics_codegen - any equation -> code (SymPy-backed) v32"
DEFAULT = "Eq(rho, conjugate(Psi)*Psi)\n"


def _pretty(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def _module_paths() -> str:
    try:
        gui_path = inspect.getfile(_gui_mod)
    except Exception:
        gui_path = "<unknown>"
    try:
        eq_path = inspect.getfile(_eq_mod)
    except Exception:
        eq_path = "<unknown>"
    return f"gui.py: {gui_path}\nequation_any.py: {eq_path}"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1400x860")
        self._last_code: str | None = None
        self._last_debug: dict | None = None
        self._last_tables: dict | None = None
        self.expression_mode = tk.BooleanVar(value=False)
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=8)
        top.grid(row=0, column=0, sticky="nsew")

        ttk.Label(top, text="Output").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Symbolic Python", anchor="w").grid(row=0, column=1, padx=6, sticky="w")

        ttk.Button(top, text="Generate", command=self.on_generate).grid(row=0, column=2, padx=6)
        ttk.Button(top, text="Clear Fields", command=self.on_clear_fields).grid(row=0, column=3, padx=6)
        ttk.Checkbutton(top, text="Expression mode", variable=self.expression_mode).grid(row=0, column=4, padx=6, sticky="w")
        ttk.Button(top, text="Guided", command=self.on_guided).grid(row=0, column=5, padx=6)
        ttk.Button(top, text="Fundamentals", command=self.on_fundamentals).grid(row=0, column=6, padx=6)
        ttk.Button(top, text="Tables", command=self.on_tables).grid(row=0, column=7, padx=6)
        ttk.Button(top, text="Save code...", command=self.on_save_code).grid(row=0, column=8, padx=6)
        ttk.Button(top, text="Save JSON...", command=self.on_save_json).grid(row=0, column=9, padx=6)

        self.status = ttk.Label(top, text="Ready", anchor="w")
        self.status.grid(row=1, column=0, columnspan=12, sticky="ew", pady=(6, 0))

        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky="nsew")

        left = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned, padding=8)
        paned.add(left, weight=1)
        paned.add(right, weight=2)

        left.rowconfigure(1, weight=1)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Equation input:").grid(row=0, column=0, sticky="w")
        self.eqn = tk.Text(left, wrap="word")
        self.eqn.grid(row=1, column=0, sticky="nsew")
        self.eqn.insert("1.0", DEFAULT)

        ttk.Label(left, text="Parsed (debug):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.parsed_box = tk.Text(left, wrap="none", height=14)
        self.parsed_box.grid(row=3, column=0, sticky="nsew")
        self.parsed_box.insert("1.0", _pretty({"module_paths": _module_paths()}))

        right.rowconfigure(1, weight=2)
        right.rowconfigure(3, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Generated Python code:").grid(row=0, column=0, sticky="w")
        self.code = tk.Text(right, wrap="none")
        self.code.grid(row=1, column=0, sticky="nsew")
        self.code.insert("1.0", "# Click Generate.")

        ttk.Label(right, text="Equation conversion tables:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        table_notebook = ttk.Notebook(right)
        table_notebook.grid(row=3, column=0, sticky="nsew")

        symbol_frame = ttk.Frame(table_notebook, padding=4)
        json_frame = ttk.Frame(table_notebook, padding=4)
        table_notebook.add(symbol_frame, text="Symbol Table (Normalized)")
        table_notebook.add(json_frame, text="Tables JSON")

        self.symbol_tree = self._build_symbol_tree(symbol_frame)

        json_frame.rowconfigure(0, weight=1)
        json_frame.columnconfigure(0, weight=1)
        self.tables_json = tk.Text(json_frame, wrap="none")
        self.tables_json.grid(row=0, column=0, sticky="nsew")
        self.tables_json.insert("1.0", _pretty({"message": "Generate an equation to populate the conversion tables."}))

    def _build_symbol_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        columns = ("symbol", "normalized", "python", "kind", "count", "description")
        tree = ttk.Treeview(parent, columns=columns, show="headings")
        headings = {
            "symbol": ("Symbol", 110),
            "normalized": ("Normalized", 140),
            "python": ("Python", 170),
            "kind": ("Kind", 110),
            "count": ("Count", 70),
            "description": ("Description", 560),
        }
        for column, (label, width) in headings.items():
            tree.heading(column, text=label)
            anchor = "center" if column == "count" else "w"
            stretch = column == "description"
            tree.column(column, width=width, minwidth=width // 2, anchor=anchor, stretch=stretch)

        tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        return tree

    def _refresh_tables(self, source_text: str, debug_obj: dict | None) -> None:
        if not debug_obj:
            self._last_tables = None
            self._clear_table_views()
            return

        tables_bundle = build_tables_bundle(source_text, debug_obj)
        self._last_tables = tables_bundle

        self.symbol_tree.delete(*self.symbol_tree.get_children())
        for row in tables_bundle.get("symbol_table", []):
            values = (
                row.get("symbol", ""),
                row.get("normalized", ""),
                row.get("python", ""),
                row.get("kind", ""),
                row.get("count", 0),
                row.get("description", ""),
            )
            self.symbol_tree.insert("", "end", values=values)

        self.tables_json.delete("1.0", "end")
        self.tables_json.insert("1.0", _pretty(tables_bundle))

    def _clear_table_views(self) -> None:
        self.symbol_tree.delete(*self.symbol_tree.get_children())
        self.tables_json.delete("1.0", "end")
        self.tables_json.insert("1.0", _pretty({"message": "Generate an equation to populate the conversion tables."}))

    def set_status(self, msg: str) -> None:
        self.status.config(text=msg)
        self.update_idletasks()

    def on_clear_fields(self) -> None:
        self.eqn.delete("1.0", "end")
        self.eqn.insert("1.0", DEFAULT)
        self.code.delete("1.0", "end")
        self.code.insert("1.0", "# Click Generate.")
        self.parsed_box.delete("1.0", "end")
        self.parsed_box.insert("1.0", _pretty({"module_paths": _module_paths()}))
        self._last_code = None
        self._last_debug = None
        self._last_tables = None
        self._clear_table_views()
        self.set_status("Reset fields to the default density template.")

    def on_guided(self) -> None:
        win = tk.Toplevel(self)
        win.title("Guided Equation Builder")
        win.geometry("900x500")

        def _insert(tok: str, replace: bool = False) -> None:
            if replace:
                self.eqn.delete("1.0", "end")
                self.eqn.insert("1.0", tok)
                return
            cur = self.eqn.index("insert")
            self.eqn.insert(cur, tok)

        gb = GuidedBuilder(win, _insert)
        gb.pack(fill="both", expand=True)

    def on_fundamentals(self) -> None:
        win = tk.Toplevel(self)
        win.title("Fundamentals of Physics -> Code")
        win.geometry("980x520")
        txt = tk.Text(win, wrap="none")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", as_markdown_table())
        txt.config(state="disabled")

    def on_tables(self) -> None:
        raw = maybe_wrap_expression(self.eqn.get("1.0", "end"), self.expression_mode.get())

        dbg = debug_rewrite(raw)
        tables_bundle = build_tables_bundle(raw, dbg)

        win = tk.Toplevel(self)
        win.title("Symbol & Code Tables")
        win.geometry("1180x680")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True)

        symbol_frame = ttk.Frame(nb)
        code_frame = ttk.Frame(nb)
        json_frame = ttk.Frame(nb)
        nb.add(symbol_frame, text="Symbol Table (Normalized)")
        nb.add(code_frame, text="Code Table")
        nb.add(json_frame, text="Tables JSON")

        symbol_text = tk.Text(symbol_frame, wrap="none")
        symbol_text.pack(fill="both", expand=True)
        symbol_text.insert("1.0", symbol_table_markdown(tables_bundle.get("symbol_table", [])))

        code_text = tk.Text(code_frame, wrap="none")
        code_text.pack(fill="both", expand=True)
        code_text.insert("1.0", code_table_markdown(tables_bundle.get("code_table", [])))

        json_text = tk.Text(json_frame, wrap="none")
        json_text.pack(fill="both", expand=True)
        json_text.insert("1.0", _pretty(tables_bundle))

    def on_generate(self) -> None:
        raw = maybe_wrap_expression(self.eqn.get("1.0", "end"), self.expression_mode.get())

        norm = normalize_text(raw)

        low = norm.lower()
        if ("psi" in low and "grad" in low and "hbar" in low and "=" not in raw):
            raw = "Eq(rho, conjugate(Psi)*Psi)"
            norm = normalize_text(raw)
            self.eqn.delete("1.0", "end")
            self.eqn.insert("1.0", raw)
            self.set_status("Auto-normalized noisy input to canonical density equation.")

        try:
            parsed = parse_equation(raw)
        except ParseError as e:
            self._last_code = None
            self._last_debug = {"module_paths": _module_paths(), "normalized_input": norm, "error": str(e)}
            self._refresh_tables(raw, self._last_debug)
            self.set_status("Parse error")
            self.parsed_box.delete("1.0", "end")
            self.parsed_box.insert("1.0", _pretty(self._last_debug))
            messagebox.showerror("Parse error", f"{e}\n\n--- module paths ---\n{_module_paths()}")
            return

        dbg = {
            "module_paths": _module_paths(),
            "params": parsed.params,
            "notes": parsed.notes,
            "normalized_input": parsed.normalized_input,
            "rewritten_input": parsed.rewritten_input,
            "equation": str(parsed.eq),
        }
        self._last_debug = dbg
        self.parsed_box.delete("1.0", "end")
        self.parsed_box.insert("1.0", _pretty(dbg))
        self._refresh_tables(raw, dbg)

        try:
            code = emit_python(parsed, mode="symbolic", settings={})
        except Exception as e:
            self._last_code = None
            self.set_status("Generate error")
            messagebox.showerror("Generate error", str(e))
            return

        self._last_code = code
        self.code.delete("1.0", "end")
        self.code.insert("1.0", code)
        self.set_status("Generated")

    def on_save_code(self) -> None:
        code_text = (self._last_code or "").rstrip() + "\n"
        if not code_text.strip() or code_text.strip().startswith("# Click"):
            messagebox.showinfo("Nothing to save", "Generate code first.")
            return
        fp = filedialog.asksaveasfilename(
            title="Save generated code",
            defaultextension=".py",
            filetypes=[("Python", "*.py"), ("All files", "*.*")],
            initialfile="generated_equation.py",
        )
        if not fp:
            return
        try:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(code_text)
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.set_status(f"Saved code: {fp}")

    def on_save_json(self) -> None:
        if not self._last_debug:
            messagebox.showinfo("Nothing to save", "Generate (or attempt parse) first.")
            return
        fp = filedialog.asksaveasfilename(
            title="Save tables/debug JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            initialfile="equation_tables.json",
        )
        if not fp:
            return
        payload = {
            "debug": self._last_debug,
            "tables": self._last_tables or {},
        }
        try:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(_pretty(payload) + "\n")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.set_status(f"Saved JSON: {fp}")


def main() -> int:
    App().mainloop()
    return 0
