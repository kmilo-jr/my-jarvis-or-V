from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config" / "default.json"

KNOWN_PTBR = [
    ("pt-BR-AntonioNeural", "Male"),
    ("pt-BR-DonatoNeural", "Male"),
    ("pt-BR-FabioNeural", "Male"),
    ("pt-BR-HumbertoNeural", "Male"),
    ("pt-BR-JulioNeural", "Male"),
    ("pt-BR-NicolauNeural", "Male"),
    ("pt-BR-ValerioNeural", "Male"),
]


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_ptbr_voices():
    import edge_tts
    voices = asyncio.run(edge_tts.list_voices())
    out = []
    for v in voices:
        if str(v.get("Locale", "")).lower() == "pt-br":
            out.append((str(v.get("ShortName", "")), str(v.get("Gender", ""))))
    out.sort(key=lambda x: (x[1] != "Male", x[0]))
    return out


def speak_sample(voice, rate, pitch, volume, text):
    import edge_tts
    from edge_playback.win32_playback import play_mp3_win32

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        ).save_sync(str(path))
        play_mp3_win32(str(path))
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("V — Configurar voz Edge-TTS 7.2.8")
        self.geometry("690x500")
        self.resizable(False, False)
        self.cfg = load_config()
        vcfg = self.cfg.setdefault("voice", {})

        self.voice_var = tk.StringVar(value=vcfg.get("tts_edge_voice", "pt-BR-AntonioNeural"))
        self.rate_var = tk.StringVar(value=vcfg.get("tts_edge_rate", "+10%"))
        self.pitch_var = tk.StringVar(value=vcfg.get("tts_edge_pitch", "-10Hz"))
        self.volume_var = tk.StringVar(value=vcfg.get("tts_edge_volume", "+0%"))
        self.status_var = tk.StringVar(value="Edge-TTS 7.2.8 — pronto")

        pad = {"padx": 16, "pady": 7}
        ttk.Label(self, text="V — EDGE-TTS VOICE LAB", font=("Segoe UI", 16, "bold")).pack(pady=(18, 4))
        ttk.Label(self, text="Escolha uma voz pt-BR, ouça a amostra e salve no V.").pack()

        frame = ttk.Frame(self)
        frame.pack(fill="x", padx=24, pady=18)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Voz:").grid(row=0, column=0, sticky="w", **pad)
        self.combo = ttk.Combobox(frame, textvariable=self.voice_var, width=48)
        self.combo.grid(row=0, column=1, sticky="ew", **pad)
        self.set_voice_values(KNOWN_PTBR)
        ttk.Button(frame, text="Atualizar lista online", command=self.refresh_online).grid(row=0, column=2, padx=8)

        ttk.Label(frame, text="Velocidade:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.rate_var, width=20).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(frame, text="Ex.: +10% / +15% / -5%").grid(row=1, column=2, sticky="w")

        ttk.Label(frame, text="Grave/agudo:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.pitch_var, width=20).grid(row=2, column=1, sticky="w", **pad)
        ttk.Label(frame, text="Ex.: -10Hz / -18Hz / +5Hz").grid(row=2, column=2, sticky="w")

        ttk.Label(frame, text="Volume:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.volume_var, width=20).grid(row=3, column=1, sticky="w", **pad)
        ttk.Label(frame, text="Ex.: +0% / +10% / -10%").grid(row=3, column=2, sticky="w")

        ttk.Label(frame, text="Frase de teste:").grid(row=4, column=0, sticky="nw", **pad)
        self.text = tk.Text(frame, width=54, height=4, wrap="word")
        self.text.grid(row=4, column=1, columnspan=2, sticky="ew", **pad)
        self.text.insert("1.0", "Boa tarde. Já estou por aqui. O que temos para hoje?")

        buttons = ttk.Frame(self)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="▶ Ouvir amostra", command=self.preview).pack(side="left", padx=8)
        ttk.Button(buttons, text="Salvar no V", command=self.save).pack(side="left", padx=8)
        ttk.Button(buttons, text="V Natural", command=lambda: self.apply_preset("natural")).pack(side="left", padx=6)
        ttk.Button(buttons, text="Mais grave", command=lambda: self.apply_preset("dark")).pack(side="left", padx=6)
        ttk.Button(buttons, text="Mais rápido", command=lambda: self.apply_preset("fast")).pack(side="left", padx=6)

        ttk.Separator(self).pack(fill="x", padx=24, pady=14)
        ttk.Label(self, textvariable=self.status_var, font=("Segoe UI", 10)).pack()
        ttk.Label(self, text="Esta versão usa o edge-tts 7.2.8 que veio no arquivo enviado por você.", foreground="#555").pack(pady=(6, 0))

    def set_voice_values(self, pairs):
        values = [f"{name}  [{gender}]" for name, gender in pairs if name]
        self.combo["values"] = values
        current = self.voice_var.get().split("  [", 1)[0]
        # preserve exact configured short name
        self.voice_var.set(current)

    def selected_voice(self):
        return self.voice_var.get().split("  [", 1)[0].strip()

    def refresh_online(self):
        self.status_var.set("Buscando vozes pt-BR no serviço Edge...")
        def job():
            try:
                voices = fetch_ptbr_voices()
                if not voices:
                    raise RuntimeError("nenhuma voz pt-BR retornada")
                self.after(0, lambda: self.set_voice_values(voices))
                self.after(0, lambda: self.status_var.set(f"{len(voices)} vozes pt-BR encontradas."))
            except Exception as exc:
                self.after(0, lambda: self.status_var.set(f"Falha ao atualizar: {exc}"))
        threading.Thread(target=job, daemon=True).start()

    def preview(self):
        voice = self.selected_voice()
        text = " ".join(self.text.get("1.0", "end").split()).strip()
        if not voice or not text:
            messagebox.showwarning("V", "Escolha uma voz e escreva uma frase de teste.")
            return
        self.status_var.set(f"Gerando amostra com {voice}...")
        def job():
            try:
                speak_sample(voice, self.rate_var.get().strip(), self.pitch_var.get().strip(), self.volume_var.get().strip(), text)
                self.after(0, lambda: self.status_var.set("Amostra concluída."))
            except Exception as exc:
                self.after(0, lambda: self.status_var.set(f"Falha no teste: {exc}"))
        threading.Thread(target=job, daemon=True).start()

    def save(self):
        voice = self.selected_voice()
        if not voice:
            return
        cfg = load_config()
        vcfg = cfg.setdefault("voice", {})
        vcfg["tts_profile"] = "edge_tts_728"
        vcfg["tts_edge_voice"] = voice
        vcfg["tts_edge_rate"] = self.rate_var.get().strip() or "+10%"
        vcfg["tts_edge_pitch"] = self.pitch_var.get().strip() or "-10Hz"
        vcfg["tts_edge_volume"] = self.volume_var.get().strip() or "+0%"
        vcfg["tts_playback"] = "win32_mci"
        save_config(cfg)
        self.status_var.set(f"Salvo: {voice}")
        messagebox.showinfo("V", f"Voz salva no V:\n{voice}")

    def apply_preset(self, preset):
        self.voice_var.set("pt-BR-AntonioNeural")
        self.volume_var.set("+0%")
        if preset == "dark":
            self.rate_var.set("+10%")
            self.pitch_var.set("-18Hz")
            label = "Mais grave"
        elif preset == "fast":
            self.rate_var.set("+16%")
            self.pitch_var.set("-6Hz")
            label = "Mais rápido"
        else:
            self.rate_var.set("+10%")
            self.pitch_var.set("-10Hz")
            label = "V Natural"
        self.status_var.set(f"Preset {label} carregado. Ouça e depois clique em Salvar no V.")


if __name__ == "__main__":
    App().mainloop()
