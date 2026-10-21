from dataclasses import dataclass


@dataclass
class ConversationWindow:
    seconds: float = 8.0
    pending: bool = False
    opened_at: float = 0.0
    deadline: float = 0.0

    def cancel(self):
        self.pending = False
        self.opened_at = self.deadline = 0.0

    def wait_for_reply(self):
        self.cancel()
        self.pending = True

    def open(self, now):
        if self.pending:
            self.pending = False
            self.opened_at = now
            self.deadline = now + max(1.0, min(30.0, self.seconds))

    def accepts(self, speech_started_at):
        return self.deadline > 0 and self.opened_at <= speech_started_at <= self.deadline


def action_acknowledgement(progress):
    """Only describe an attempt; success belongs to the tool result."""
    if not str(progress).startswith("TOOL ") or "•" not in progress:
        return ""
    tool = progress.split("•", 1)[1].strip()
    return {
        "app.open": "Vou tentar abrir agora.",
        "app.close": "Vou tentar fechar agora.",
        "spotify.play_track": "Estou procurando a música no Spotify.",
        "youtube.search": "Estou buscando no YouTube.",
        "youtube.play": "Estou procurando o vídeo.",
        "news.today": "Estou consultando as notícias.",
        "news.topic": "Estou consultando as notícias sobre isso.",
        "web.research": "Estou pesquisando sobre isso.",
        "market.overview": "Estou consultando o mercado.",
        "market.quote": "Estou consultando a cotação.",
        "system.pc_status": "Estou verificando o computador.",
    }.get(tool, "")
