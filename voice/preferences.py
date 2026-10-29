from app_paths import ROOT
import json
from pathlib import Path


VOICE_PRESETS = {
    "jarvis": {
        "label": "Jarvis · elegante e controlado",
        "speed": 98,
        "tts_eleven_stability": 0.62,
        "tts_eleven_similarity_boost": 0.82,
        "tts_eleven_style": 0.08,
        "tts_edge_pitch": "-14Hz",
        "tts_short_pitch": "-12Hz",
        "tts_question_pitch": "-8Hz",
        "tts_long_pitch": "-14Hz",
        "tts_edge_volume": "+0%",
        "tts_piper_length_scale": 1.02,
        "tts_dynamic_prosody": True,
    },
    "ultron": {
        "label": "Ultron · grave e sintético",
        "speed": 91,
        "tts_eleven_stability": 0.78,
        "tts_eleven_similarity_boost": 0.76,
        "tts_eleven_style": 0.16,
        "tts_edge_pitch": "-28Hz",
        "tts_short_pitch": "-25Hz",
        "tts_question_pitch": "-20Hz",
        "tts_long_pitch": "-28Hz",
        "tts_edge_volume": "-2%",
        "tts_piper_length_scale": 1.12,
        "tts_dynamic_prosody": False,
    },
    "v_natural": {
        "label": "V · natural",
        "speed": 100,
        "tts_eleven_stability": 0.48,
        "tts_eleven_similarity_boost": 0.78,
        "tts_eleven_style": 0.0,
        "tts_edge_pitch": "-10Hz",
        "tts_short_pitch": "-8Hz",
        "tts_question_pitch": "-6Hz",
        "tts_long_pitch": "-10Hz",
        "tts_edge_volume": "+0%",
        "tts_piper_length_scale": 1.0,
        "tts_dynamic_prosody": True,
    },
    "v_prime": {
        "label": "V Prime · original",
        "speed": 99,
        "tts_eleven_stability": 0.68,
        "tts_eleven_similarity_boost": 0.84,
        "tts_eleven_style": 0.06,
        "tts_edge_pitch": "-16Hz",
        "tts_short_pitch": "-12Hz",
        "tts_question_pitch": "-7Hz",
        "tts_long_pitch": "-15Hz",
        "tts_edge_volume": "+0%",
        "tts_piper_length_scale": 1.01,
        "tts_dynamic_prosody": True,
    },
}


def preset_defaults(name):
    key = str(name or "jarvis").strip().lower()
    if key not in VOICE_PRESETS:
        raise ValueError("Escolha um perfil de voz válido.")
    return {k: v for k, v in VOICE_PRESETS[key].items() if k != "label"}


def selected_xtts_voice(config):
    key = str(config.get("tts_xtts_voice", "v_prime") or "v_prime").strip().lower()
    return "v_alt" if key in {"v_alt", "alt", "second", "2"} else "v_prime"


def setup_voice_selector(combo, config):
    for key, label in (("v_prime", "V Prime · original (XTTS)"), ("v_alt", "V Alt · motor antigo (XTTS)")):
        index = combo.findData(key)
        if index >= 0:
            combo.setItemText(index, label)
    combo.addItem("V Alt · nova voz local (Qwen)", "qwen_alt")
    combo.addItem("ElevenLabs · voz personalizada", "elevenlabs")
    combo.addItem("Windows · português offline", "windows")
    combo.addItem("Edge · voz natural online", "edge")
    profile = str(config.get("tts_profile", "")).lower()
    key = "elevenlabs" if profile in {"elevenlabs_custom", "elevenlabs", "v_custom", "v_voice"} else "qwen_alt" if profile == "qwen_local" else "windows" if profile == "windows_sapi" else "edge" if profile.startswith("edge") else selected_xtts_voice(config)
    combo.setCurrentIndex(combo.findData(key))


def selection_settings(key):
    if key == "elevenlabs":
        return {"tts_profile": "elevenlabs_custom", "tts_xtts_enabled": False, "tts_eleven_fallback_edge": False}
    if key == "qwen_alt":
        return {"tts_profile": "qwen_local", "tts_xtts_enabled": False, "tts_xtts_voice": "v_alt"}
    if key in {"windows", "edge"}:
        return {"tts_profile": "windows_sapi" if key == "windows" else "edge_tts_728", "tts_xtts_enabled": False}
    if key not in {"v_prime", "v_alt"}:
        raise ValueError("Escolha uma voz válida.")
    return {"tts_xtts_voice": key, "tts_profile": "xtts_local", "tts_xtts_enabled": True}


def voice_speed(config, xtts_voice=None):
    """Read the rate for the engine and sample that will actually speak."""
    if xtts_voice == "qwen_alt" or (xtts_voice is None and config.get("tts_profile") == "qwen_local"):
        return 100
    if xtts_voice == "windows" or (xtts_voice is None and config.get("tts_profile") == "windows_sapi"):
        return max(90, min(115, 100 + int(config.get("tts_fallback_rate", 0)) * 5))
    if xtts_voice in {"v_prime", "v_alt"} or (xtts_voice is None and str(config.get("tts_profile", "")).lower() == "xtts_local"):
        selected = xtts_voice or selected_xtts_voice(config)
        value = config.get("tts_xtts_speed_alt", config.get("tts_xtts_speed", 1.0)) if selected == "v_alt" else config.get("tts_xtts_speed", 1.0)
    else:
        value = config.get("tts_eleven_speed", 1.0)
    return max(90, min(115, round(float(value) * 100)))


def voice_preferences(speed, expressive, narrate, preset="jarvis", xtts_voice=None):
    if type(speed) is not int or not 90 <= speed <= 115:
        raise ValueError("Escolha um ritmo entre 90% e 115%.")
    if type(expressive) is not bool or type(narrate) is not bool:
        raise ValueError("Preferência de voz inválida.")
    rate = f"{speed - 100:+d}%"
    changes = preset_defaults(preset)
    changes.update({"tts_voice_preset": str(preset).lower(), "tts_eleven_speed": speed / 100, "tts_edge_rate": rate,
            "tts_short_rate": rate, "tts_question_rate": rate, "tts_long_rate": rate,
            "tts_piper_length_scale": round(100 / speed, 3),
            "tts_fallback_rate": round((speed - 100) / 5),
            "tts_dynamic_prosody": bool(expressive), "task_progress_voice": narrate})
    if xtts_voice is not None:
        key = str(xtts_voice).strip().lower()
        changes.update(selection_settings(key))
        if key in {"v_prime", "v_alt"}:
            changes["tts_xtts_speed_alt" if key == "v_alt" else "tts_xtts_speed"] = speed / 100
    return changes


def save_preferences(engine, speed, expressive, narrate, path=None, preset="jarvis", xtts_voice=None):
    path = Path(path) if path else ROOT / "config/default.json"
    changes = voice_preferences(speed, expressive, narrate, preset, xtts_voice=xtts_voice)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("voice", {}).update(changes)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    engine.stop_speaking()
    engine.config.update(changes)
    if engine.config.get('tts_profile') == 'qwen_local':
        engine.warmup_tts()


def save_xtts_voice(engine, xtts_voice, path=None):
    """Select a local sample and activate its speech engine."""
    key = str(xtts_voice or "").strip().lower()
    changes = selection_settings(key)
    path = Path(path) if path else ROOT / "config/default.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("voice", {}).update(changes)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    engine.stop_speaking()
    engine.config.update(changes)
    if engine.config.get('tts_profile') == 'qwen_local':
        engine.warmup_tts()
    return key
