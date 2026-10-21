from __future__ import annotations
import json
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from voice.eleven_auth import save_key

BASE = Path(__file__).resolve().parent
CFG = BASE / "config" / "default.json"
VOICE_ID = "8UH1CSGj7v69E1F7Yo6d"

def main():
    root = tk.Tk()
    root.title("V — Configurar Voz Personalizada")
    root.geometry("650x310")
    root.resizable(False, False)
    tk.Label(root, text="V — VOZ PERSONALIZADA", font=("Segoe UI", 15, "bold")).pack(pady=(18, 4))
    tk.Label(root, text=f"Voice ID: {VOICE_ID}", font=("Consolas", 10)).pack()
    tk.Label(root, text="Cole sua ElevenLabs API Key. Ela fica protegida pelo Windows DPAPI.", font=("Segoe UI", 9)).pack(pady=(10, 12))
    frame = tk.Frame(root); frame.pack(fill="x", padx=24)
    entry = tk.Entry(frame, show="•", font=("Consolas", 11)); entry.pack(side="left", fill="x", expand=True)
    def paste():
        try:
            entry.delete(0, "end"); entry.insert(0, root.clipboard_get().strip())
        except Exception as exc:
            messagebox.showerror("V", f"Não consegui ler a área de transferência:\n{exc}")
    tk.Button(frame, text="COLAR", command=paste, width=10).pack(side="left", padx=(8,0))
    show=tk.BooleanVar(value=False)
    tk.Checkbutton(root,text="Mostrar chave",variable=show,command=lambda: entry.config(show="" if show.get() else "•")).pack(pady=8)
    tk.Label(root,text="Perfil: Eleven Flash v2.5 • pt-BR • baixa latência",font=("Segoe UI",9)).pack()
    def save():
        key=entry.get().strip()
        if len(key)<20:
            messagebox.showerror("V","A chave parece vazia ou curta demais."); return
        try:
            cfg=json.loads(CFG.read_text(encoding="utf-8"))
            cfg.setdefault("voice",{})["tts_profile"]="elevenlabs_custom"
            cfg["voice"]["tts_eleven_voice_id"]=VOICE_ID
            CFG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
            info=save_key(key, BASE/"config"/"elevenlabs_key.dat")
            messagebox.showinfo("V",f"Voz do V configurada.\nProteção: {info['scheme']}\n\nAgora rode testar_voz_v.bat.")
            root.destroy()
        except Exception as exc:
            messagebox.showerror("V",f"Falha ao salvar:\n{type(exc).__name__}: {exc}")
    tk.Button(root,text="SALVAR E USAR COMO VOZ DO V",command=save,width=30,height=2).pack(pady=14)
    tk.Label(root,text="A API Key não é gravada no default.json e não deve ser compartilhada.",font=("Segoe UI",8)).pack()
    root.mainloop()

if __name__ == "__main__": main()
