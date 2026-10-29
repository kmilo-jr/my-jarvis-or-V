from __future__ import annotations
from app_paths import ROOT

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import os
import re


@dataclass
class ToolContext:
    user_text: str
    history: list[dict]
    memory: Any = None


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass
class ToolExecution:
    name: str
    ok: bool
    message: str
    data: dict = field(default_factory=dict)
    allowed: bool = True
    reason: str = ""


Guard = Callable[[dict, ToolContext], tuple[bool, str]]
Handler = Callable[[dict, ToolContext], ToolExecution | tuple[bool, str] | str]


@dataclass
class ToolSpec:
    name: str
    description: str
    args: dict[str, str]
    handler: Handler
    guard: Guard | None = None
    category: str = "general"
    risk: str = "low"

    def manifest(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "args": self.args,
            "category": self.category,
            "risk": self.risk,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(str(name or "").strip())

    def manifest(self) -> list[dict]:
        return [self._tools[k].manifest() for k in sorted(self._tools)]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def validate(self, call: ToolCall, ctx: ToolContext) -> tuple[bool, str]:
        spec = self.get(call.name)
        if not spec:
            return False, f"ferramenta desconhecida: {call.name}"
        if spec.guard:
            try:
                return spec.guard(call.args or {}, ctx)
            except Exception as exc:
                return False, f"guard falhou: {type(exc).__name__}: {exc}"
        return True, ""

    def execute(self, call: ToolCall, ctx: ToolContext) -> ToolExecution:
        spec = self.get(call.name)
        if not spec:
            return ToolExecution(call.name, False, f"Ferramenta desconhecida: {call.name}", allowed=False, reason="unknown_tool")
        allowed, reason = self.validate(call, ctx)
        if not allowed:
            return ToolExecution(call.name, False, f"Ação bloqueada pelo Tool Firewall: {reason}", allowed=False, reason=reason)
        try:
            result = spec.handler(call.args or {}, ctx)
            if isinstance(result, ToolExecution):
                return result
            if isinstance(result, tuple) and len(result) >= 2:
                return ToolExecution(spec.name, bool(result[0]), str(result[1]))
            return ToolExecution(spec.name, True, str(result))
        except Exception as exc:
            return ToolExecution(spec.name, False, f"{spec.name} falhou: {type(exc).__name__}: {exc}")


def _norm(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip(" .,!?:;-—–")


def _recent_media(ctx: ToolContext) -> bool:
    joined = " ".join(_norm(x.get("content", "")) for x in (ctx.history or [])[-8:])
    return any(k in joined for k in ("spotify", "musica", "faixa", "tocando", "playlist", "youtube"))


def _guard_spotify(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    q = str(args.get("query", "")).strip()
    if not q:
        return False, "spotify.play_track exige query"
    music = bool(re.search(r"\b(toque|toca|tocar|reproduza|reproduzir|ouvir|escutar|musica|faixa|cancao|playlist)\b", c))
    contextual = _recent_media(ctx) and bool(re.search(r"\b(outra|proxima|troca|essa|essa nao|de novo)\b", c))
    if "spotify" in c or music or contextual:
        return True, ""
    return False, "pedido sem intenção explícita de música/Spotify"


def _guard_news(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    return (True, "") if "noticia" in c else (False, "pedido não menciona notícias")


def _guard_volume(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    keys = ("volume", "som", "audio", "mute", "mudo", "silencio")
    return (True, "") if any(k in c for k in keys) else (False, "pedido sem intenção de volume")


def _guard_set_volume(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    value = args.get('value')
    if type(value) not in (int, float) or not 0 <= value <= 100 or int(value) != value:
        return False, 'Informe um volume inteiro entre 0 e 100.'
    return _guard_volume(args, ctx)


def _guard_pc(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    keys = ("pc", "computador", "cpu", "ram", "disco", "sistema")
    return (True, "") if any(k in c for k in keys) else (False, "pedido sem referência ao computador")


def _guard_open(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    target = str(args.get("target", "")).strip()
    if not target:
        return False, "app.open exige target"
    return (True, "") if re.search(r"\b(abra|abre|abrir|inicie|iniciar|acesse|acessar)\b", c) else (False, "pedido sem verbo de abertura")


def _guard_close(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    target = str(args.get("target", "")).strip()
    if not target:
        return False, "app.close exige target"
    return (True, "") if re.search(r"\b(feche|fecha|fechar|encerre|encerrar)\b", c) else (False, "pedido sem verbo de fechamento")


def _guard_youtube(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    return (True, "") if ("youtube" in c or any(x in c for x in ("video", "live", "canal"))) else (False, "pedido sem intenção de YouTube/vídeo")


def _guard_media(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    words = ("musica", "faixa", "midia", "spotify", "youtube", "pause", "pausar", "proxima", "anterior", "continue")
    if any(x in c for x in words) or _recent_media(ctx):
        return True, ""
    return False, "pedido sem contexto de mídia"


def _guard_window(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    return (True, "") if any(x in c for x in ("janela", "desktop", "area de trabalho", "tela")) else (False, "pedido sem intenção de janela/desktop")


def _guard_diag(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    return (True, "") if any(x in c for x in ("diagnostico", "diagnosticos", "log", "logs")) else (False, "pedido não menciona diagnóstico/logs")


def _guard_research(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    q = str(args.get("query", "")).strip()
    return (True, "") if q else (False, "web.research exige query")


def _guard_mobile_alarm(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    return (True, "") if "alarme" in c and re.search(r'\b(?:iphone|celular|v mobile)\b', c) else (False, "pedido sem alarme explícito no celular")


def _guard_mobile_reminder(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    keys = ("lembrete", "me lembre", "lembre-me")
    return (True, "") if any(k in c for k in keys) and re.search(r'\b(?:iphone|celular|v mobile)\b', c) else (False, "pedido sem lembrete explícito no celular")


def _guard_market(args: dict, ctx: ToolContext) -> tuple[bool, str]:
    c = _norm(ctx.user_text)
    keys = ("bolsa", "ibovespa", "ibov", "bovespa", "mercado financeiro", "mercado de acoes",
            "acao", "acoes", "cotacao", "ticker", "petr4", "petr3", "vale3", "itub4",
            "bbdc4", "bbas3", "wege3", "mglu3", "petrobras", "vale", "itau", "bradesco")
    return (True, "") if any(k in c for k in keys) else (False, "pedido sem intenção de mercado/bolsa")


def _result(name: str, msg: str, fail_prefixes: tuple[str, ...] = ("nao consegui", "não consegui", "falha", "erro")) -> ToolExecution:
    nm = _norm(msg)
    ok = not any(nm.startswith(_norm(p)) for p in fail_prefixes)
    return ToolExecution(name, ok, str(msg))


def build_default_registry(initiative_store=None, list_store=None) -> ToolRegistry:
    # Imports de automação são lazy. Isso deixa o cérebro/roteador testáveis sem
    # exigir sessão gráfica e reduz custo de startup.
    reg = ToolRegistry()

    def lt():
        import legacy_tools
        return legacy_tools

    def wr():
        import web_research
        return web_research

    def news_execution(name: str, topic: str | None = None):
        module = wr()
        msg = module.news_brief(topic)
        nm = _norm(msg)
        ok = not any(nm.startswith(_norm(p)) for p in ("nao consegui", "não consegui", "falha", "erro"))
        items = module.latest_items("news") if ok and hasattr(module, "latest_items") else []
        if items:
            from voice.news_speech import news_text
            titles = [news_text(x.get("title", "")) for x in items if str(x.get("title", "")).strip()]
            prefix = "Encontrei estas notícias" if not topic else f"Encontrei estas notícias sobre {topic}"
            speech = prefix + ": " + ". ".join(titles[:5])
        else:
            speech = msg
        return ToolExecution(name, ok, msg, {
            "kind": "news",
            "topic": topic or "",
            "items": items,
            "speech_text": speech,
        })

    def research_execution(query: str):
        module = wr()
        msg = module.research_brief(query)
        nm = _norm(msg)
        ok = not any(nm.startswith(_norm(p)) for p in ("nao consegui", "não consegui", "falha", "erro"))
        items = module.latest_items("research") if ok and hasattr(module, "latest_items") else []
        speech = msg.split("FONTES:", 1)[0].strip()
        if len(speech) > 1100:
            speech = speech[:1097].rstrip() + "..."
        return ToolExecution("web.research", ok, msg, {
            "kind": "research",
            "query": query,
            "items": items,
            "speech_text": speech,
        })

    def market_execution(name: str, query: str = ""):
        try:
            import market_data
            if name == "market.quote":
                msg, items = market_data.market_quote(query)
            else:
                msg, items = market_data.market_overview()
            return ToolExecution(name, True, msg, {
                "kind": "market",
                "query": query,
                "items": items,
                "speech_text": msg,
            })
        except Exception as exc:
            msg = f"Não consegui consultar a bolsa agora. Erro da fonte de mercado: {exc}"
            return ToolExecution(name, False, msg, {"kind":"market", "query":query, "items":[], "speech_text":msg})

    def mobile_alarm_execution(request: str):
        import mobile_bridge
        try:
            item = mobile_bridge.queue_alarm(request=request)
            return ToolExecution("mobile.alarm", True,
                f"Alarme para {item['time']} preparado no iPhone. Abra o V Remote e toque em EXECUTAR NO IPHONE.",
                {"kind": "mobile", "mobile_action": item, "speech_text": f"Alarme para {item['time']} preparado no seu iPhone."})
        except ValueError as exc:
            return ToolExecution("mobile.alarm", False, str(exc), {"kind":"mobile"})

    def mobile_reminder_execution(request: str):
        import mobile_bridge
        try:
            item = mobile_bridge.queue_reminder(request=request)
            due = str(item.get("due", "")).replace("T", " às ")
            return ToolExecution("mobile.reminder", True,
                f"Lembrete '{item['title']}' preparado para {due}. Abra o V Remote e toque em EXECUTAR NO IPHONE.",
                {"kind": "mobile", "mobile_action": item, "speech_text": f"Lembrete preparado no seu iPhone."})
        except ValueError as exc:
            return ToolExecution("mobile.reminder", False, str(exc), {"kind":"mobile"})

    reg.register(ToolSpec(
        "mobile.alarm", "Prepara um alarme para o iPhone via V Mobile/Atalhos.", {"request":"pedido completo com horário"},
        lambda a, c: mobile_alarm_execution(str(a.get("request", c.user_text))), _guard_mobile_alarm, "mobile"
    ))
    reg.register(ToolSpec(
        "mobile.reminder", "Prepara um lembrete para o iPhone via V Mobile/Atalhos.", {"request":"pedido completo com data/hora e texto"},
        lambda a, c: mobile_reminder_execution(str(a.get("request", c.user_text))), _guard_mobile_reminder, "mobile"
    ))

    reg.register(ToolSpec(
        "system.pc_status", "Lê CPU, RAM, disco e bateria do PC.", {},
        lambda a, c: _result("system.pc_status", lt().system_info()), _guard_pc, "system"
    ))
    reg.register(ToolSpec(
        "app.open", "Abre um aplicativo, site ou pasta conhecida.", {"target": "nome do aplicativo/site/pasta"},
        lambda a, c: _result("app.open", lt().open_target(str(a.get("target", "")).strip())), _guard_open, "apps"
    ))
    reg.register(ToolSpec(
        "app.close", "Fecha um aplicativo pelo nome.", {"target": "nome do aplicativo"},
        lambda a, c: _result("app.close", lt().close_application(str(a.get("target", "")).strip())), _guard_close, "apps"
    ))

    reg.register(ToolSpec("audio.volume_up", "Aumenta o volume do Windows.", {}, lambda a, c: _result("audio.volume_up", lt().change_volume("up")), _guard_volume, "audio"))
    reg.register(ToolSpec("audio.volume_down", "Diminui o volume do Windows.", {}, lambda a, c: _result("audio.volume_down", lt().change_volume("down")), _guard_volume, "audio"))
    reg.register(ToolSpec("audio.mute", "Ativa/desativa mudo.", {}, lambda a, c: _result("audio.mute", lt().media_control("mute")), _guard_volume, "audio"))
    reg.register(ToolSpec(
        "audio.set_volume", "Define volume de 0 a 100.", {"value": "número entre 0 e 100"},
        lambda a, c: _result("audio.set_volume", lt().set_volume(int(a['value']))), _guard_set_volume, "audio"
    ))

    reg.register(ToolSpec("media.play_pause", "Pausa ou continua a mídia atual.", {}, lambda a, c: _result("media.play_pause", lt().media_control("play_pause")), _guard_media, "media"))
    reg.register(ToolSpec("media.next", "Vai para a próxima faixa; Spotify usa o Bridge direto e outros players usam fallback do Windows.", {}, lambda a, c: _result("media.next", lt().media_control("next")), _guard_media, "media"))
    reg.register(ToolSpec("media.previous", "Volta para a faixa anterior.", {}, lambda a, c: _result("media.previous", lt().media_control("previous")), _guard_media, "media"))

    reg.register(ToolSpec(
        "spotify.play_track", "Pesquisa uma música pela Spotify Web API e reproduz no Spotify Desktop via Spicetify Bridge.", {"query": "título e artista quando conhecido"},
        lambda a, c: _result("spotify.play_track", lt().play_music_on_spotify(str(a.get("query", "")).strip())), _guard_spotify, "spotify"
    ))

    reg.register(ToolSpec(
        "youtube.search", "Abre uma busca no YouTube.", {"query": "termos da busca"},
        lambda a, c: _result("youtube.search", lt().youtube_search(str(a.get("query", "")).strip())), _guard_youtube, "youtube"
    ))
    reg.register(ToolSpec(
        "youtube.play", "Tenta abrir/reproduzir um vídeo ou live no YouTube.", {"query": "vídeo/live/canal"},
        lambda a, c: _result("youtube.play", lt().youtube_play(str(a.get("query", "")).strip())), _guard_youtube, "youtube"
    ))

    reg.register(ToolSpec(
        "news.today", "Busca as principais notícias do dia no Brasil.", {},
        lambda a, c: news_execution("news.today"), _guard_news, "news"
    ))
    reg.register(ToolSpec(
        "news.topic", "Busca notícias recentes sobre um assunto.", {"topic": "assunto"},
        lambda a, c: news_execution("news.topic", str(a.get("topic", "")).strip() or None), _guard_news, "news"
    ))
    reg.register(ToolSpec(
        "web.research", "Pesquisa a web em múltiplas fontes e resume.", {"query": "assunto a pesquisar"},
        lambda a, c: research_execution(str(a.get("query", "")).strip()), _guard_research, "web"
    ))
    reg.register(ToolSpec(
        "market.overview", "Mostra Ibovespa e um resumo das principais ações brasileiras.", {},
        lambda a, c: market_execution("market.overview"), _guard_market, "market"
    ))
    reg.register(ToolSpec(
        "market.quote", "Consulta a cotação de um ativo da B3 ou do Ibovespa.", {"query": "ticker ou nome do ativo"},
        lambda a, c: market_execution("market.quote", str(a.get("query", "")).strip() or c.user_text), _guard_market, "market"
    ))

    reg.register(ToolSpec("window.minimize", "Minimiza a janela ativa.", {}, lambda a, c: _result("window.minimize", lt().window_control("minimize")), _guard_window, "windows"))
    reg.register(ToolSpec("window.maximize", "Maximiza a janela ativa.", {}, lambda a, c: _result("window.maximize", lt().window_control("maximize")), _guard_window, "windows"))
    reg.register(ToolSpec("window.show_desktop", "Mostra a área de trabalho.", {}, lambda a, c: _result("window.show_desktop", lt().window_control("show_desktop")), _guard_window, "windows"))
    reg.register(ToolSpec('window.switch', 'Alterna a janela ativa.', {}, lambda a, c: _result('window.switch', lt().window_control('switch')), _guard_window, 'windows'))
    reg.register(ToolSpec('window.close', 'Fecha a janela ativa.', {}, lambda a, c: _result('window.close', lt().window_control('close')),
                          lambda a, c: (bool(re.search(r'\b(?:feche|fechar|encerre) (?:a )?janela', _norm(c.user_text))), 'Peça explicitamente para fechar a janela.'), 'windows'))
    from .desktop_controls import describe_monitors, move_active_window
    reg.register(ToolSpec('monitor.list', 'Lista os monitores; o principal vem primeiro.', {},
                          lambda a, c: describe_monitors(), lambda a, c: ('monitor' in _norm(c.user_text), 'pedido deve mencionar monitores'), 'windows'))
    def move_guard(a, c):
        match = re.search(r'\b(?:mova|mover|mande|envie) (?:a )?janela(?: ativa)? para (?:o )?monitor (\d+)\b', _norm(c.user_text))
        return (True, '') if match and type(a.get('number')) is int and int(match.group(1)) == a['number'] else (False, 'Informe explicitamente a janela e o número do monitor.')
    reg.register(ToolSpec('window.move_monitor', 'Move a janela ativa para um monitor numerado.', {'number': 'número mostrado por monitor.list'},
                          lambda a, c: move_active_window(a.get('number')), move_guard, 'windows'))

    def open_diag(a, c):
        root = ROOT
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(logs))
        else:
            import subprocess
            subprocess.Popen(["explorer", str(logs)])
        return ToolExecution("diagnostics.open", True, f"Abrindo a pasta de diagnóstico: {logs}")

    reg.register(ToolSpec("diagnostics.open", "Abre a pasta de logs/diagnóstico do V.", {}, open_diag, _guard_diag, "diagnostics"))
    from .initiative import InitiativeStore
    from .personal_assistant import PersonalAssistant, is_local_request
    assistant = PersonalAssistant(initiative_store or InitiativeStore(), list_store)

    def personal_guard(a, c):
        request = str(a.get('request', c.user_text))
        return (True, '') if is_local_request(request) and _norm(request) in _norm(c.user_text) else (False, 'Pedido local ausente ou diferente do pedido do usuário.')

    def personal_execute(a, c):
        try:
            message = assistant.execute(str(a.get('request', c.user_text)))
            return ToolExecution('assistant.local', True, message, {'speech_text': re.sub(r'\s*\[[a-f0-9]{8}\]| Código [a-f0-9]{8}\.', '', message)})
        except ValueError as exc:
            time_errors = ('Qual horário?', 'Use um horário', 'Esse horário', 'Essa data', 'Para esse dia', 'Você indicou uma data', 'Com manhã', 'Use um intervalo')
            return ToolExecution('assistant.local', False, str(exc), {'needs_time': str(exc).startswith(time_errors), 'request': str(a.get('request', c.user_text))})

    reg.register(ToolSpec('assistant.local', 'Listas, agenda, alarmes e lembretes locais no PC. Use as palavras exatas do usuário; não invente horário.',
                          {'request': 'pedido local completo do usuário'}, personal_execute, personal_guard, 'personal'))
    reg.register(ToolSpec('request.limit', 'Informa limite de oito ações.', {}, lambda a, c: ToolExecution('request.limit', False, 'Posso executar até oito ações por pedido. Divida essa sequência; nenhuma ação foi executada.')))
    reg.register(ToolSpec('request.clarify', 'Pede esclarecimento de uma sequência ambígua.', {}, lambda a, c: ToolExecution('request.clarify', False, 'Não identifiquei todas as etapas desse pedido. Nenhuma ação foi executada. Separe as ações com “e depois” e informe o que fazer em cada uma.')))
    return reg

def save_tool_trace(root: Path, payload: dict):
    try:
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "tool_trace_last.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
