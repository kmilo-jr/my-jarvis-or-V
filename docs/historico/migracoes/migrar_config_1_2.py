from __future__ import annotations
import json, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = BASE.parent / "V_PROTOTYPE_1_2_PERSONALITY_NATURAL_VOICE"
if not OLD.exists():
    print("Pasta V_PROTOTYPE_1_2_PERSONALITY_NATURAL_VOICE nao encontrada ao lado desta pasta.")
    raise SystemExit(1)

old_cfg_p = OLD / "config" / "default.json"
new_cfg_p = BASE / "config" / "default.json"
old = json.loads(old_cfg_p.read_text(encoding="utf-8")) if old_cfg_p.exists() else {}
new = json.loads(new_cfg_p.read_text(encoding="utf-8"))

# Preserva credenciais/configurações funcionais, mas mantém a nova personalidade 1.2.1.
for section in ("spotify_api", "memory", "ui"):
    if section in old:
        new[section] = old[section]
# Brain: preserva Gemini/Ollama do usuário.
if "brain" in old:
    new["brain"].update(old["brain"])
# Voice: preserva microfone/reconhecimento; mantém perfil TTS natural novo salvo em 1.2.
if "voice" in old:
    preserve = {
        "model","device","compute_type","language","record_seconds","beam_size",
        "silence_peak","silence_rms","target_peak","max_gain","initial_prompt",
        "continuous_voice_default","wake_words","cpu_threads","calibration_seconds",
        "energy_frame_ms","stream_block_ms","pre_roll_seconds","phrase_end_silence_seconds",
        "max_phrase_seconds","min_phrase_seconds","listen_wait_seconds","speech_start_blocks",
        "speech_start_floor_rms","speech_end_floor_rms","speech_start_noise_mult",
        "speech_end_noise_mult","speech_start_max_rms","speech_end_max_rms","target_rms",
        "term_replacements"
    }
    for k in preserve:
        if k in old["voice"]:
            new["voice"][k] = old["voice"][k]
new_cfg_p.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")

for rel in ("config/gemini_key.dat", "config/spotify_token.json", "data/memory.json", "data/conversation_history.json"):
    src=OLD/rel; dst=BASE/rel
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src,dst)
print("Migracao 1.2 -> 1.2.1 concluida. Gemini, Spotify, memoria e microfone preservados.")
