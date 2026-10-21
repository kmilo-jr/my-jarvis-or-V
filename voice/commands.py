"""Local speech controls, independent of the planner and media commands."""
import re
import unicodedata


def is_stop_request(text: str) -> bool:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())
    text = re.sub(r"^(?:v|ve|vei)\s+", "", text)
    return text in {"para", "pare", "pare de falar", "para de falar", "interromper fala", "silencio"}
