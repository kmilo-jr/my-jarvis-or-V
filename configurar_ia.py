from __future__ import annotations
import json, shutil, subprocess, urllib.request, webbrowser
MODEL = "qwen2.5:3b"
def main():
    print("="*55)
    print("V PROTOTYPE 0.8 - CONFIGURACAO DO AI BRAIN")
    print("="*55)
    exe = shutil.which("ollama")
    if not exe:
        print("\nO Ollama ainda nao esta instalado.")
        print("Vou abrir a pagina oficial de download para Windows.")
        print("Instale o Ollama e execute este configurador novamente.")
        try: webbrowser.open("https://ollama.com/download/windows")
        except Exception: pass
        input("\nENTER para sair...")
        return 2
    print("Ollama encontrado:", exe)
    print(f"\nBaixando/verificando {MODEL}...")
    rc = subprocess.run([exe, "pull", MODEL]).returncode
    if rc:
        print("Falha ao preparar o modelo.")
        input("ENTER para sair...")
        return rc
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            obj=json.loads(r.read().decode("utf-8") or "{}")
        names=[(m or {}).get("name","") for m in obj.get("models",[])]
        print("AI Brain ONLINE:", ", ".join(names) or MODEL)
    except Exception as exc:
        print("Modelo instalado, mas o servico ainda nao respondeu:", exc)
        print("Abra o Ollama e execute o V novamente.")
    input("\nConfiguracao concluida. ENTER para sair...")
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
