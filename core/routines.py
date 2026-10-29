"""Editable local routines; only explicit routine commands trigger execution."""
from app_paths import ROOT
import json
import os
from pathlib import Path
import re
import unicodedata
import webbrowser

ROOT = ROOT
APPS = ("chrome", "edge", "firefox", "visual studio code", "discord", "spotify", "bloco de notas", "calculadora", "explorador")


def is_work_request(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"^\s*(?:ei\s+)?(?:v|vi|ve|jarvis)\b[\s,.;:!?-]*", "", text).strip(" .!?,")
    return bool(re.fullmatch(r"(?:(?:ative|ativar|ativa|inicie|iniciar|inicia|ligue)\s+(?:o\s+)?)?modo trabalho(?:\s+por favor)?", text))


class RoutineStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / "config" / "routines.json"

    def defaults(self):
        return {"browser_enabled": True, "browser": "padrão", "folder_enabled": True,
                "folder": str(ROOT), "volume_enabled": True, "volume": 25,
                "apps": [], "ask_priority": True}

    def validate(self, data):
        value = self.defaults()
        value.update({k: data[k] for k in value if k in data})
        for key in ("browser_enabled", "folder_enabled", "volume_enabled", "ask_priority"):
            if not isinstance(value[key], bool):
                raise ValueError("Opção inválida: " + key)
        if value["browser"] not in ("padrão", "chrome", "edge", "firefox"):
            raise ValueError("Selecione um navegador da lista.")
        if type(value["volume"]) is not int or not 0 <= value["volume"] <= 100:
            raise ValueError("O volume deve ficar entre 0 e 100.")
        if not isinstance(value["apps"], list) or any(app not in APPS for app in value["apps"]):
            raise ValueError("Selecione programas da lista de aplicativos.")
        value["apps"] = list(dict.fromkeys(value["apps"]))
        if not isinstance(value["folder"], str):
            raise ValueError("Pasta inválida.")
        if value["folder_enabled"] and (not Path(value["folder"]).is_absolute() or not Path(value["folder"]).is_dir()):
            raise ValueError("Escolha uma pasta existente para os projetos.")
        return value

    def load(self):
        if not self.path.exists():
            return self.defaults()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("work"), dict):
            raise ValueError("Configuração do modo trabalho inválida.")
        # Validate types here; folder existence is checked per step at runtime.
        work = dict(data["work"])
        enabled = work.get("folder_enabled", True)
        work["folder_enabled"] = False
        value = self.validate(work)
        if not isinstance(enabled, bool):
            raise ValueError("Opção de pasta inválida.")
        value["folder_enabled"] = enabled
        return value

    def save(self, data):
        work = self.validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"version": 1, "work": work}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


class RoutineRunner:
    def __init__(self, store=None, open_app=None, set_volume=None, open_folder=None, open_browser=None):
        self.store = store or RoutineStore()
        self.open_app = open_app or self._open_app
        self.set_volume = set_volume or self._set_volume
        self.open_folder = open_folder or os.startfile
        self.open_browser = open_browser or (lambda: webbrowser.open("about:blank"))

    @staticmethod
    def _open_app(name):
        from legacy_tools import open_target
        return open_target(name)

    @staticmethod
    def _set_volume(value):
        from legacy_tools import set_volume
        return set_volume(value)

    def run(self, progress=None):
        from .tool_system import _result
        cfg = self.store.load()
        steps = []
        if cfg["volume_enabled"]:
            steps.append(("Volume", lambda: self.set_volume(cfg["volume"])))
        if cfg["browser_enabled"]:
            def browser():
                if cfg["browser"] != "padrão":
                    return self.open_app(cfg["browser"])
                return "Abertura do navegador solicitada." if self.open_browser() else "Não consegui abrir o navegador."
            steps.append(("Navegador", browser))
        if cfg["folder_enabled"]:
            def folder():
                path = Path(cfg["folder"])
                if not path.is_absolute() or not path.is_dir():
                    return "Não consegui abrir a pasta de projetos: ela não existe. Edite em Rotinas."
                self.open_folder(str(path))
                return "Abertura da pasta de projetos solicitada."
            steps.append(("Pasta de projetos", folder))
        for app in cfg["apps"]:
            if cfg["browser_enabled"] and app == cfg["browser"]:
                continue
            steps.append((app, lambda app=app: self.open_app(app)))
        outcomes = []
        for label, action in steps:
            if progress:
                progress("Modo trabalho · " + label)
            try:
                result = _result("routine.work", str(action()))
                outcomes.append({"step": label, "ok": result.ok, "message": result.message})
            except Exception as exc:
                outcomes.append({"step": label, "ok": False, "message": f"Não consegui executar {label}: {type(exc).__name__}."})
        ok = all(item["ok"] for item in outcomes)
        summary = "Rotina de trabalho executada." if ok and steps else "Modo trabalho pronto." if ok else "Executei a rotina com algumas pendências."
        speech = summary
        if not ok:
            speech += " Falhou: " + ", ".join(item["step"] for item in outcomes if not item["ok"]) + ". Confira os detalhes na conversa."
        if cfg["ask_priority"]:
            speech += " Qual é a sua prioridade de hoje?"
        message = summary + "\n" + "\n".join(item["message"] for item in outcomes)
        if cfg["ask_priority"]:
            message += "\nQual é a sua prioridade de hoje?"
        return ok, message.strip(), {"speech_text": speech, "steps": outcomes}
