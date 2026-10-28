from pathlib import Path
import json, shutil

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
candidates = [PARENT / "V_PROTOTYPE_1_1_GEMINI_HYBRID_BRAIN"]
old = next((p for p in candidates if p.exists()), None)
if not old:
    print("Pasta V_PROTOTYPE_1_1_GEMINI_HYBRID_BRAIN nao encontrada ao lado desta pasta.")
    raise SystemExit(1)

# Secrets/tokens and persistent user data
for rel in ["config/gemini_key.dat", "config/spotify_token.json", "data/memory.json", "data/conversation_history.json"]:
    src, dst = old / rel, HERE / rel
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("Copiado:", rel)

# Preserve Spotify client id and user-specific settings, but keep new Gemini latency settings.
oldcfg = old / "config/default.json"
newcfg = HERE / "config/default.json"
if oldcfg.exists() and newcfg.exists():
    a=json.loads(oldcfg.read_text(encoding="utf-8"))
    b=json.loads(newcfg.read_text(encoding="utf-8"))
    for section in ("spotify_api", "voice", "memory", "personality"):
        if section in a:
            b[section]=a[section]
    newcfg.write_text(json.dumps(b,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Configuracoes pessoais preservadas; Gemini Fast Response mantido.")
print("Migracao 1.1 -> 1.1.1 concluida.")
