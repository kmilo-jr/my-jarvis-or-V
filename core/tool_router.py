from __future__ import annotations

from dataclasses import dataclass, field
import re
import unicodedata

from .tool_system import ToolCall


@dataclass
class RouteDecision:
    mode: str  # tools | chat | planner
    calls: list[ToolCall] = field(default_factory=list)
    reason: str = ""


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,!?:;-—–")


def _strip_wake(text: str) -> str:
    return re.sub(r"^\s*(?:ei\s+)?(?:v|vi|ve|vê|jarvis)\b[\s,.;:!?\-–—]*", "", str(text or ""), count=1, flags=re.I).strip()




def _strip_social_prefix(text: str) -> str:
    """Remove uma saudação inicial quando há um pedido real depois dela.

    Ex.: "olá V, toque uma música calma" -> "toque uma música calma".
    Uma saudação isolada continua sendo conversa.
    """
    raw = str(text or "").strip()
    m = re.match(
        r"^\s*(?:ol[áa]|oi|opa|e\s+a[ií]|bom\s+dia|boa\s+tarde|boa\s+noite)"
        r"(?:\s+(?:v|vi|ve|vê|jarvis))?"
        r"(?:\s*[,;:.!?\-–—]\s*|\s+)(.+)$",
        raw,
        flags=re.I,
    )
    if not m:
        return raw
    rest = str(m.group(1) or "").strip()
    return rest or raw

def _clean_target(s: str) -> str:
    s = re.sub(r"\s+(?:por favor|pra mim|para mim)\s*$", "", s, flags=re.I)
    return s.strip(" .,!?")


def _music_query(raw: str) -> str:
    s = _strip_wake(raw)
    s = re.sub(r"^\s*(?:toque|toca|tocar|reproduza|reproduzir|coloque|coloca|colocar|bote|bota|poe|põe|quero ouvir|quero escutar|ouvir|escutar)\b", "", s, flags=re.I).strip(" ,.;:-")
    s = re.sub(r"^(?:(?:a|uma)\s+)?(?:musica|música|faixa|cancao|canção)\s+", "", s, flags=re.I)
    s = re.sub(r"\s+(?:no|na|pelo|pela)\s+spotify\s*$", "", s, flags=re.I)
    s = re.sub(r"\s+spotify\s*$", "", s, flags=re.I)
    return s.strip(" ,.;:-")


class ToolRouter:
    """Roteador determinístico antes da IA.

    Ele só captura intenções óbvias. O que for ambíguo vai para o Planner,
    e o ToolRegistry ainda valida a ferramenta antes da execução.
    """

    def route(self, text: str, history: list[dict] | None = None) -> RouteDecision:
        raw = _strip_social_prefix(_strip_wake(text))
        # Se a saudação veio antes do wake word ("olá V, ..."), remove o V restante.
        raw = _strip_wake(raw)
        c = _norm(raw)
        if not c:
            return RouteDecision("chat", reason="mensagem vazia/apenas wake word")

        # Cadeias explícitas: só combina se TODAS as partes forem ferramentas determinísticas.
        parts = [p.strip() for p in re.split(r"\s*(?:;|\be depois\b|\bdepois\b|\be ent[aã]o\b|\bent[aã]o\b|\be\s+(?=(?:abra|inicie|feche|coloque|ajuste|defina|toque|mostre|minimize|maximize|me lembre|crie|adicione)\b))\s*", raw, flags=re.I) if p.strip()]
        if len(parts) > 1:
            calls: list[ToolCall] = []
            for part in parts:
                d = self.route(part, history)
                if d.mode != "tools" or not d.calls:
                    calls = []
                    break
                calls.extend(d.calls)
            if calls:
                if len(calls) > 8:
                    return RouteDecision('tools', [ToolCall('request.limit')], 'pedido excede oito ações')
                return RouteDecision("tools", calls, "cadeia determinística")
            return RouteDecision('tools', [ToolCall('request.clarify')], 'sequência com etapa não reconhecida')

        from .personal_assistant import is_local_request
        if is_local_request(raw):
            return RouteDecision('tools', [ToolCall('assistant.local', {'request': raw})], 'assistente pessoal local')

        # Conversa clara.
        if re.fullmatch(r"(?:ola|oi|opa|e ai|bom dia|boa tarde|boa noite)(?:\s+v)?", c):
            return RouteDecision("chat", reason="saudação")
        if re.match(r"^(?:tudo bem|como voce esta|como vai|ta tudo bem)(?:\s+v)?$", c):
            return RouteDecision("chat", reason="conversa social")

        # V Mobile: alarmes e lembretes do iPhone.
        # Mantemos isso determinístico para não depender do Planner/LLM.
        if "alarme" in c and re.search(r"\b(?:coloque|coloca|crie|criar|programe|programar|agende|agendar|bote|bota|alarme)\b", c):
            return RouteDecision("tools", [ToolCall("mobile.alarm", {"request": raw})], "alarme no iPhone")

        reminder_temporal = bool(re.search(r"\b(?:hoje|amanha|amanhã|\d{1,2}[:h.]\d{0,2}|\d{1,2}[/-]\d{1,2})\b", raw, flags=re.I))
        reminder_explicit = bool(re.search(r"\b(?:lembrete|me\s+lembre|lembre-me|crie\s+um\s+lembrete|agende\s+um\s+lembrete)\b", raw, flags=re.I))
        if reminder_explicit and (reminder_temporal or "lembrete" in c):
            return RouteDecision("tools", [ToolCall("mobile.reminder", {"request": raw})], "lembrete no iPhone")

        # Notícias têm prioridade máxima para nunca virarem conversa/Spotify.
        # Aceita fala natural, incluindo perguntas como
        # "quais são as notícias do dia?" e "me diga as notícias de hoje".
        general_news_patterns = (
            r"^(?:as )?(?:ultimas )?noticias(?: do dia| de hoje)?$",
            r"^(?:quais )(?:sao )?(?:as )?(?:ultimas )?noticias(?: do dia| de hoje)?$",
            r"^(?:me diga|me fale|me mostre|mostre|leia|ler|quero saber)(?: quais sao)?(?: as)?(?: ultimas)? noticias(?: do dia| de hoje)?$",
            r"^briefing de noticias$",
            r"^(?:o que aconteceu|o que esta acontecendo)(?: no brasil)? hoje$",
        )
        if any(re.fullmatch(pattern, c) for pattern in general_news_patterns):
            return RouteDecision("tools", [ToolCall("news.today")], "notícias gerais")

        # Assunto específico. Evita capturar a expressão reservada "do dia"/"de hoje".
        m = re.match(r"^(?:quais (?:sao )?(?:as )?)?(?:ultimas )?noticias (?:de|sobre|do|da) (.+)$", c)
        if m:
            topic = m.group(1).strip()
            if topic not in {"dia", "hoje"}:
                return RouteDecision("tools", [ToolCall("news.topic", {"topic": topic})], "notícias por assunto")

        # Bolsa / mercado financeiro. Mantém a intenção determinística para que
        # cotações não virem uma resposta genérica do cérebro.
        market_ticker = re.search(r"\b[a-z]{4}\d{1,2}\b", c)
        market_names = ("petrobras", "vale", "itau", "bradesco", "banco do brasil", "weg", "magalu", "magazine luiza")
        quote_words = ("cotacao", "preco", "quanto esta", "quanto vale", "valor da acao", "valor de", "acao da", "acao do")
        if market_ticker or (any(name in c for name in market_names) and any(w in c for w in quote_words)):
            return RouteDecision("tools", [ToolCall("market.quote", {"query": raw})], "cotação de ativo")
        if re.search(r"\b(?:ibovespa|ibov|bovespa)\b", c):
            # Pedido específico de valor do índice continua sendo quote; perguntas
            # amplas mostram o painel com o mercado brasileiro.
            if any(w in c for w in quote_words) or re.fullmatch(r"(?:ibovespa|ibov|bovespa)", c):
                return RouteDecision("tools", [ToolCall("market.quote", {"query": raw})], "cotação do Ibovespa")
            return RouteDecision("tools", [ToolCall("market.overview")], "resumo do Ibovespa")
        if any(x in c for x in ("bolsa de valores", "como esta a bolsa", "como esta o mercado financeiro", "mercado financeiro hoje", "mercado de acoes", "acoes da bolsa", "bolsa hoje")):
            return RouteDecision("tools", [ToolCall("market.overview")], "mercado financeiro")

        if re.search(r"\b(?:diagnostico|diagnosticos|log|logs)\b", c) and re.search(r"\b(?:abra|abrir|abre|mostre|mostrar)\b", c):
            return RouteDecision("tools", [ToolCall("diagnostics.open")], "diagnóstico")

        if re.search(r"\b(?:como esta|estado|status|uso)\b", c) and any(x in c for x in ("pc", "computador", "cpu", "ram", "disco", "sistema")):
            return RouteDecision("tools", [ToolCall("system.pc_status")], "status do PC")

        # Volume.
        if any(x in c for x in ("volume", "som", "audio")):
            m = re.search(r"\b(\d{1,3})\b", c)
            if m and any(x in c for x in ("coloque", "deixe", "ajuste", "defina", "volume em", "volume para")):
                return RouteDecision("tools", [ToolCall("audio.set_volume", {"value": int(m.group(1))})], "volume absoluto")
            if re.search(r"\b(aumente|aumentar|aumenta|suba|subir|mais alto|mais volume)\b", c):
                return RouteDecision("tools", [ToolCall("audio.volume_up")], "volume +")
            if re.search(r"\b(diminua|diminuir|diminui|abaixe|abaixar|baixe|baixar|mais baixo|menos volume)\b", c):
                return RouteDecision("tools", [ToolCall("audio.volume_down")], "volume -")
        if re.search(r"\b(mute|mutar|silenciar|mudo)\b", c):
            return RouteDecision("tools", [ToolCall("audio.mute")], "mute")

        # Spotify/música. Verbo forte de música é evidência suficiente mesmo sem dizer Spotify.
        if re.match(r"^(?:toque|toca|tocar|reproduza|reproduzir|coloque|coloca|colocar|bote|bota|poe|quero ouvir|quero escutar|ouvir|escutar)\b", c):
            if "youtube" not in c:
                q = _music_query(raw)
                if q:
                    return RouteDecision("tools", [ToolCall("spotify.play_track", {"query": q})], "pedido explícito de música")

        # YouTube explícito.
        if "youtube" in c:
            m = re.match(r"^(?:pesquise|pesquisar|procure|buscar|busque)\s+(?:no\s+youtube\s+)?(.+?)(?:\s+no\s+youtube)?$", c)
            if m:
                q = re.sub(r"^no youtube\s+", "", m.group(1)).strip()
                return RouteDecision("tools", [ToolCall("youtube.search", {"query": q})], "busca YouTube")
            m = re.match(r"^(?:toque|tocar|reproduza|reproduzir|abra|abrir)\s+(.+?)\s+(?:no|na)\s+youtube$", c)
            if m:
                return RouteDecision("tools", [ToolCall("youtube.play", {"query": m.group(1).strip()})], "play YouTube")

        # Mídia local.
        if re.fullmatch(r"(?:proxima|proxima musica|proxima faixa|pule|pular|avance a musica)", c):
            return RouteDecision("tools", [ToolCall("media.next")], "próxima mídia")
        if re.fullmatch(r"(?:anterior|musica anterior|faixa anterior|volte a musica)", c):
            return RouteDecision("tools", [ToolCall("media.previous")], "mídia anterior")
        if re.fullmatch(r"(?:pause|pausa|pausar|continue|continuar|play pause)(?: a musica)?", c):
            return RouteDecision("tools", [ToolCall("media.play_pause")], "play/pause")

        # Apps.
        if re.fullmatch(r'(?:(?:mostre|liste|quais sao) (?:os |meus )?)?monitores', c):
            return RouteDecision('tools', [ToolCall('monitor.list')], 'monitores do PC')
        m = re.fullmatch(r'(?:mova|mover|mande|envie) (?:a )?janela(?: ativa)? para (?:o )?monitor (\d+)', c)
        if m:
            return RouteDecision('tools', [ToolCall('window.move_monitor', {'number': int(m.group(1))})], 'mover janela')
        if re.fullmatch(r'(?:alterne|troque|alternar) (?:a |de )?janela', c):
            return RouteDecision('tools', [ToolCall('window.switch')], 'alternar janela')
        if re.fullmatch(r'(?:feche|fechar|encerre) (?:a )?janela(?: ativa)?', c):
            return RouteDecision('tools', [ToolCall('window.close')], 'fechar janela ativa')
        m = re.match(r"^(?:abra|abre|abrir|inicie|iniciar|acesse|acessar)\s+(?:o|a)?\s*(.+)$", raw, flags=re.I)
        if m:
            target = _clean_target(m.group(1))
            if target:
                return RouteDecision("tools", [ToolCall("app.open", {"target": target})], "abrir app")
        m = re.match(r"^(?:feche|fecha|fechar|encerre|encerrar)\s+(?:o|a)?\s*(.+)$", raw, flags=re.I)
        if m:
            target = _clean_target(m.group(1))
            if target:
                return RouteDecision("tools", [ToolCall("app.close", {"target": target})], "fechar app")

        # Janelas.
        if re.search(r"\b(minimize|minimizar|minimiza)\b", c) and "janela" in c:
            return RouteDecision("tools", [ToolCall("window.minimize")], "minimizar")
        if re.search(r"\b(maximize|maximizar|maximiza)\b", c) and "janela" in c:
            return RouteDecision("tools", [ToolCall("window.maximize")], "maximizar")
        if any(x in c for x in ("mostre a area de trabalho", "mostrar desktop", "ir para o desktop")):
            return RouteDecision("tools", [ToolCall("window.show_desktop")], "desktop")

        # Pesquisa explícita/levantamento na web.
        for prefix in ("pesquise na web ", "investigue ", "faca um levantamento sobre ", "faça um levantamento sobre ", "pesquise e resuma "):
            if c.startswith(_norm(prefix)):
                q = raw[len(prefix):].strip() if raw.lower().startswith(prefix.lower()) else re.sub(r"^(?:pesquise na web|investigue|faca um levantamento sobre|faça um levantamento sobre|pesquise e resuma)\s+", "", raw, flags=re.I).strip()
                if q:
                    return RouteDecision("tools", [ToolCall("web.research", {"query": q})], "pesquisa web")

        # Perguntas gerais são conversa, sem Planner de ferramenta.
        if re.search(r"\b(o que|oque|quem|por que|porque|como|qual|quais|quando|onde|me explica|explique|o que acha|pensa sobre)\b", c):
            return RouteDecision("chat", reason="pergunta geral")

        return RouteDecision("planner", reason="intenção ambígua; IA pode planejar com ferramentas")
