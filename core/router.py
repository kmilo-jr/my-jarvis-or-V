from __future__ import annotations
from .functional_engine import normalize, strip_wake_word, has_wake_word

# Mantido como shim de compatibilidade. O 0.4 não usa mais IntentRouter/Planner
# no caminho de execução principal.
class IntentRouter:
    def __init__(self, context=None): self.context = context
