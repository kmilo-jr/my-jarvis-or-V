import re
from .conversation import action_acknowledgement


def progress_label(message):
    text = str(message or "")
    acknowledgement = action_acknowledgement(text)
    match = re.match(r"TOOL (\d+)/(\d+) • (.+)", text)
    if match:
        action = acknowledgement or "Executando a ação solicitada."
        return f"Etapa {match[1]} de {match[2]} · {action}"
    if text.startswith("Modo trabalho ·"):
        return text
    if text.startswith("LIVE SEARCH"):
        return "Consultando informações na internet."
    if text.startswith("AI BRAIN"):
        return "Preparando sua resposta." if "conversa" in text or "fallback" in text else "Organizando as etapas do seu pedido."
    if text.startswith("TOOL ROUTER"):
        return "Pedido entendido. Preparando a execução."
    if text.startswith(("LEGACY FALLBACK", "IA ")):
        return "Executando seu pedido."
    return text
