from __future__ import annotations

import tkinter as tk
from tkinter import ttk


TOKENS = [
    'rho', 'Psi', 'conjugate(Psi)', 'grad(Psi)', 'hbar', 'I', 'm',
    '(', ')', '+', '-', '*', '/', '^2', '=', 'Eq(', ', 0)'
]

TEMPLATES = {
    'Density (quantum)': 'Eq(rho, conjugate(Psi)*Psi)',
    'Simple force law': 'Eq(F, m*a)',
    'Wave-like term': 'Eq(u_tt, c^2*u_xx)',
}


class GuidedBuilder(ttk.Frame):
    def __init__(self, master, insert_callback):
        super().__init__(master)
        self.insert_callback = insert_callback
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=6, pady=6)

        ttk.Label(top, text='Template').pack(side='left')
        self.template = tk.StringVar(value='Density (quantum)')
        cb = ttk.Combobox(top, textvariable=self.template, values=list(TEMPLATES.keys()), state='readonly', width=28)
        cb.pack(side='left', padx=6)
        ttk.Button(top, text='Insert Template', command=self.on_insert_template).pack(side='left', padx=4)

        body = ttk.LabelFrame(self, text='Token Pad')
        body.pack(fill='both', expand=True, padx=6, pady=6)

        cols = 6
        for i, tok in enumerate(TOKENS):
            r, c = divmod(i, cols)
            ttk.Button(body, text=tok, command=lambda t=tok: self.insert_callback(t)).grid(row=r, column=c, padx=4, pady=4, sticky='ew')

        for c in range(cols):
            body.columnconfigure(c, weight=1)

    def on_insert_template(self):
        val = TEMPLATES[self.template.get()]
        self.insert_callback(val, replace=True)
        try:
            from tkinter import messagebox
            messagebox.showinfo('Guided Builder', 'Template inserted into main equation input.')
        except Exception:
            pass
        # close builder so user can see updated equation box
        self.winfo_toplevel().destroy()

