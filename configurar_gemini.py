from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from brain.gemini_auth import save_key

BASE = Path(__file__).resolve().parent


def main():
    root = tk.Tk()
    root.title("V — Configurar Gemini")
    root.geometry("620x270")
    root.resizable(False, False)

    tk.Label(root, text="GEMINI HYBRID BRAIN", font=("Segoe UI", 15, "bold")).pack(pady=(18, 4))
    tk.Label(root, text="Cole sua Gemini API Key. Ela será protegida com o Windows DPAPI para este usuário.", font=("Segoe UI", 9)).pack(pady=(0, 12))

    frame = tk.Frame(root)
    frame.pack(fill="x", padx=24)
    entry = tk.Entry(frame, show="•", font=("Consolas", 11))
    entry.pack(side="left", fill="x", expand=True)

    def paste():
        try:
            text = root.clipboard_get().strip()
            entry.delete(0, "end")
            entry.insert(0, text)
        except Exception as exc:
            messagebox.showerror("V", f"Não consegui ler a área de transferência:\n{exc}")

    tk.Button(frame, text="COLAR", command=paste, width=10).pack(side="left", padx=(8, 0))

    show = tk.BooleanVar(value=False)
    def toggle():
        entry.config(show="" if show.get() else "•")
    tk.Checkbutton(root, text="Mostrar chave", variable=show, command=toggle).pack(pady=8)

    status = tk.Label(root, text="Modelo padrão: gemini-2.5-flash", font=("Segoe UI", 9))
    status.pack()

    def save():
        key = entry.get().strip()
        if len(key) < 20:
            messagebox.showerror("V", "A chave parece vazia ou curta demais.")
            return
        try:
            info = save_key(key, BASE / "config" / "gemini_key.dat")
            messagebox.showinfo("V", f"API Key salva.\nProteção: {info['scheme']}\n\nAgora rode testar_gemini.bat.")
            root.destroy()
        except Exception as exc:
            messagebox.showerror("V", f"Falha ao salvar a chave:\n{type(exc).__name__}: {exc}")

    tk.Button(root, text="SALVAR API KEY", command=save, width=24, height=2).pack(pady=12)
    tk.Label(root, text="A chave não é gravada no default.json e não aparece nos logs.", font=("Segoe UI", 8)).pack()
    root.mainloop()


if __name__ == "__main__":
    main()
