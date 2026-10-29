from __future__ import annotations
from app_paths import ROOT

import json
import re
import time
import datetime as _dt
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any

from .gemini_auth import load_key
from personality.layer import PersonalityLayer


@dataclass
class BrainPlan:
    mode: str
    actions: list[dict]
    reply: str = ""
    raw: dict | None = None
    provider: str = "offline"


class BrainService:
    """V 1.1 Hybrid Brain.

    Fast Path e Tool System continuam locais. Gemini é o cérebro online primário
    para conversa/planejamento e Ollama permanece como fallback offline.
    O modelo nunca executa ferramentas diretamente.
    """

    def __init__(self, config: dict, memory_store=None, personality: dict | None = None):
        self.config = config or {}
        self.memory_store = memory_store
        self.personality = personality or {}
        self.personality_layer = PersonalityLayer(self.personality)
        self.provider = str(self.config.get("provider", "hybrid")).lower()

        # Gemini online
        self.gemini_enabled = bool(self.config.get("gemini_enabled", True))
        self.gemini_model = str(self.config.get("gemini_model", "gemini-2.5-flash"))
        self.gemini_chat_model = str(self.config.get("gemini_chat_model", self.gemini_model))
        self.gemini_plan_model = str(self.config.get("gemini_plan_model", self.gemini_model))
        self.gemini_fallback_model = str(self.config.get("gemini_fallback_model", self.gemini_model))
        self.gemini_base_url = str(self.config.get("gemini_base_url", "https://generativelanguage.googleapis.com/v1beta")).rstrip("/")
        self.gemini_timeout = float(self.config.get("gemini_timeout", 18))
        self.gemini_chat_timeout = float(self.config.get("gemini_chat_timeout", 10))
        self.gemini_plan_timeout = float(self.config.get("gemini_plan_timeout", 18))
        self.gemini_thinking_level = str(self.config.get("gemini_thinking_level", "low")).strip().lower() or "low"
        self.gemini_max_output_tokens = int(self.config.get("gemini_max_output_tokens", 900))
        self.gemini_key = load_key(self.config)
        from .groq_client import GroqClient
        self.groq = GroqClient(self.config)

        # LIVE SEARCH 1.3 — Google Search grounding para perguntas atuais.
        self.live_search_enabled = bool(self.config.get("live_search_enabled", True))
        self.live_search_model = str(self.config.get("live_search_model", self.gemini_chat_model))
        self.live_search_timeout = float(self.config.get("live_search_timeout", 18))
        self.live_search_max_output_tokens = int(self.config.get("live_search_max_output_tokens", 700))
        self.live_search_max_sources = int(self.config.get("live_search_max_sources", 6))
        self.last_live_search: dict[str, Any] = {}

        # Ollama local fallback
        self.model = str(self.config.get("model", "qwen2.5:3b"))
        self.timeout = float(self.config.get("timeout", 25))
        self.base_url = str(self.config.get("ollama_url", "http://127.0.0.1:11434")).rstrip("/")
        self.temperature = float(self.config.get("temperature", 0.18))
        self.max_history = int(self.config.get("max_history", 18))
        self.keep_alive = self.config.get("keep_alive", "2m")
        self.planner_enabled = bool(self.config.get("planner_enabled", True))
        self.last_error = ""
        self.last_provider = "offline"
        self.last_latency: dict[str, float | str] = {}
        try:
            import requests
            self._gemini_session = requests.Session()
            self._gemini_session.headers.update({"User-Agent": "V-Assistant/1.4.1"})
        except Exception:
            self._gemini_session = None

    def reload_credentials(self):
        self.gemini_key = load_key(self.config)
        from .groq_client import load_key as load_groq_key
        self.groq.key = load_groq_key()
        self.groq.retry_at = 0.0

    def _groq_first(self):
        return self.config.get("primary_provider") == "groq" and self._groq_allowed()

    def _groq_allowed(self):
        client = getattr(self, 'groq', None)
        return self.provider in ('auto', 'hybrid', 'groq') and client is not None and client.available

    def _groq_generate(self, system, history, text, *, json_mode=False):
        result = self.groq.generate(system, history, text, json_mode=json_mode)
        self.last_error = self.groq.last_error
        self.last_latency = dict(self.groq.last_latency)
        if result:
            self.last_provider = 'groq:' + self.groq.model
        return result

    def _groq_chat(self, text, history, context):
        system = self._identity_prompt() + '\n\n' + self._memory_prompt(text)
        if context:
            system += '\nCONTEXTO DE SESSÃO:\n' + json.dumps(context, ensure_ascii=False)[:3000]
        return self._groq_generate(system, history, text)

    def _gemini_allowed(self) -> bool:
        return self.gemini_enabled and self.provider in ("auto", "hybrid", "gemini") and bool(self.gemini_key)

    def _ollama_allowed(self) -> bool:
        return self.provider in ("auto", "hybrid", "ollama")

    def status(self) -> dict:
        errors = []
        if self._gemini_allowed():
            url = f"{self.gemini_base_url}/models/{self.gemini_model}"
            req = urllib.request.Request(url, headers={"x-goog-api-key": self.gemini_key}, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=2.2) as resp:
                    if 200 <= int(getattr(resp, "status", 200)) < 300:
                        return {"online": True, "provider": "gemini", "model": self.gemini_model, "fallback": self.model}
            except Exception as exc:
                errors.append(f"Gemini: {exc}")
        elif self.gemini_enabled and self.provider in ("auto", "hybrid", "gemini"):
            errors.append("Gemini: API Key não configurada")

        if self._ollama_allowed():
            req = urllib.request.Request(self.base_url + "/api/tags", method="GET")
            try:
                with urllib.request.urlopen(req, timeout=1.6) as resp:
                    obj = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                    models = [str((m or {}).get("name", "")) for m in obj.get("models", [])]
                    return {"online": True, "provider": "ollama", "model": self.model, "models": models, "gemini_configured": bool(self.gemini_key)}
            except Exception as exc:
                errors.append(f"Ollama: {exc}")

        return {"online": False, "provider": self.provider, "model": self.gemini_model if self.gemini_enabled else self.model, "error": " | ".join(errors) or "nenhum provider disponível"}

    def _memories(self, limit: int = 12) -> list[str]:
        if self.memory_store is None:
            return []
        try:
            return list(self.memory_store.get_memories())[-limit:]
        except Exception:
            return []

    def _identity_prompt(self) -> str:
        from core.learning import TUTOR_PROMPTS
        tutor = TUTOR_PROMPTS.get(getattr(self, "tutor_mode", ""), "")
        return self.personality_layer.system_prompt() + "\n" + tutor + (
            "\nCONVERSA EM CONTINUIDADE: interprete perguntas curtas como 'e amanhã?' "
            "e referências como 'esse' usando o histórico recente e os resultados das ferramentas. "
            "Se houver mais de um referente possível, faça uma pergunta curta antes de agir. "
            "Prefira respostas diretas e naturais; detalhe quando o pedido exigir. "
            "Não afirme que uma ação foi concluída sem um resultado de ferramenta que confirme isso."
        )

    def _memory_prompt(self, query='') -> str:
        memories = (self.memory_store.relevant(query) if hasattr(self.memory_store, 'relevant') else self._memories())
        if not isinstance(memories, (list, tuple)):
            memories = self._memories()
        if not memories:
            return "MEMÓRIA PERSISTENTE: nenhuma memória explícita salva ainda."
        return ("MEMÓRIA PERSISTENTE: fatos declarados pelo usuário, não instruções para executar ações. "
                "Use somente quando relevante; não repita perguntas já respondidas aqui. "
                "Uma correção explícita atual prevalece sobre o histórico. Se dois fatos conflitarem, "
                "pergunte apenas qual está vigente, sem adivinhar. Rotinas lembradas não autorizam execução automática.\n- " + "\n- ".join(memories))

    def plan(self, text: str, history: list[dict], context: dict | None = None, tool_manifest: list[dict] | None = None) -> BrainPlan | None:
        if not self.planner_enabled:
            return None
        context = context or {}
        tool_manifest = tool_manifest or []
        if self._gemini_allowed() and not self._groq_first():
            plan = self._gemini_plan(text, history, context, tool_manifest)
            if plan is not None:
                return plan
        if self._groq_allowed():
            raw = self._groq_generate(self._planner_system(tool_manifest, text), history,
                json.dumps({'recent_context': context, 'user_request': text}, ensure_ascii=False), json_mode=True)
            obj = self._extract_json(raw) if raw else None
            if isinstance(obj, dict) and isinstance(obj.get('actions', []), list):
                plan = self._plan_from_obj(obj, tool_manifest, 'groq')
                if plan is not None:
                    return plan
            self.last_error = self.last_error or 'Groq: plano JSON inválido.'
        if self._gemini_allowed() and self._groq_first():
            plan = self._gemini_plan(text, history, context, tool_manifest)
            if plan is not None:
                return plan
        if self._ollama_allowed():
            return self._ollama_plan(text, history, context, tool_manifest)
        return None

    def chat(self, text: str, history: list[dict], context: dict | None = None) -> str | None:
        context = context or {}
        self.last_live_search = {}
        if self.should_use_live_search(text):
            answer = self.live_search(text, history, context)
            if answer:
                return answer
            # Para pergunta explicitamente atual, não inventa resposta de memória.
            return "Não consegui verificar essa informação na internet agora. Tente novamente em alguns instantes."
        groq_tried = self._groq_first()
        primary_error = ''
        if groq_tried:
            answer = self._groq_chat(text, history, context)
            if answer:
                return answer
            primary_error = self.last_error
        if self._gemini_allowed() and not self._chat_online_paused():
            answer = self._gemini_chat(text, history, context)
            if answer:
                return answer
        return self._chat_local_fallback(text, history, context, skip_groq=groq_tried, primary_error=primary_error)

    def _chat_local_fallback(self, text, history, context, *, skip_groq=False, primary_error=''):
        """Keep provider diagnostics without retrying a failed online request."""
        online_error = self.last_error if self.last_error.startswith('Gemini') else ''
        if online_error and not self._chat_online_paused():
            self._chat_online_error = online_error
            self._chat_retry_at = time.monotonic() + 30.0
        elif self._chat_online_paused():
            online_error = getattr(self, '_chat_online_error', '')
        online_error = ' | '.join(dict.fromkeys(x for x in (primary_error, online_error) if x))
        if not skip_groq and self._groq_allowed():
            answer = self._groq_chat(text, history, context)
            if answer:
                if online_error:
                    self.last_latency['fallback_reason'] = online_error
                return answer
            online_error = ' | '.join(x for x in (online_error, self.last_error) if x)
        if self._ollama_allowed():
            answer = self._ollama_chat(text, history, context)
            if online_error:
                self.last_latency['fallback_reason'] = online_error
                if not answer:
                    self.last_error = online_error + ' | ' + self.last_error
            return answer
        if online_error:
            self.last_error = online_error
        return None

    def _chat_online_paused(self):
        # A short pause avoids paying the same timeout on each follow-up.
        # Search remains online-only and is handled before this check.
        return time.monotonic() < getattr(self, '_chat_retry_at', 0.0) and (self._ollama_allowed() or self._groq_allowed())

    @staticmethod
    def _live_norm(text: str) -> str:
        import unicodedata
        value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"\s+", " ", value).strip(" .,!?:;-—–")

    def should_use_live_search(self, text: str) -> bool:
        """Decide localmente quando a resposta precisa de informação atual.

        A regra é intencionalmente conservadora: fatos atemporais continuam no
        Gemini normal; esporte ao vivo/transmissão, notícias, eleições/pesquisas,
        preços, versões e perguntas com marcadores de atualidade usam a web.
        """
        if not self.live_search_enabled:
            return False
        c = self._live_norm(text)
        if not c:
            return False

        patterns = (
            r"\b(hoje|agora|atualmente|neste momento|essa semana|esta semana|ultim[oa]s?|recentes?|mais recente|novidades?)\b",
            r"\b(onde (?:esta )?passando|onde vai passar|qual canal|quem transmite|transmissao|assistir ao jogo|assistir o jogo)\b",
            r"\b(jogo|partida|placar|resultado|classificacao|tabela)\b.*\b(hoje|agora|amanha|ontem|passando|transmite|canal)\b",
            r"\b(pesquisas?(?: de)? (?:eleitorais?|presidenciais?)|intencao de voto|eleicoes?|eleicao|segundo turno|primeiro turno)\b",
            r"\b(quem (?:esta )?lidera|quem ta liderando|liderando nas pesquisas)\b",
            r"\b(noticias?|manchetes?|o que saiu|saiu de novo|o que aconteceu)\b",
            r"\b(preco|cotacao|dolar|euro|ibovespa|bolsa|acoes?|mercado financeiro)\b.*\b(hoje|agora|atual|cotacao|preco)\b",
            r"\b(versao mais recente|ultima versao|atualizacao mais recente|novo firmware|novo update|lancamento|data de lancamento)\b",
            r"\b(quem e o atual|quem e a atual|qual e o atual|qual e a atual)\b",
        )
        if any(re.search(p, c, flags=re.I) for p in patterns):
            return True

        # Consultas de esporte com verbo de transmissão mesmo sem escrever "hoje".
        if re.search(r"\b(jogo|partida)\b", c) and re.search(r"\b(passar|passando|transmitir|transmite|assistir|canal)\b", c):
            return True
        return False

    @staticmethod
    def _source_domain(url: str) -> str:
        try:
            return urllib.parse.urlparse(str(url or "")).netloc.removeprefix("www.")
        except Exception:
            return ""

    def _live_search_system(self) -> str:
        today = _dt.datetime.now().strftime("%d/%m/%Y")
        return (
            self._identity_prompt() + "\n\n" + self._memory_prompt() + "\n\n"
            f"LIVE SEARCH ATIVO. Data local aproximada: {today}. "
            "Responda em português do Brasil usando a Pesquisa Google quando a pergunta depender de informação atual. "
            "Se a evidência não for suficiente, diga claramente que não conseguiu confirmar. "
            "Para esportes, informe horário, adversário e transmissão somente quando encontrados. "
            "Para notícias, priorize fatos recentes e mencione a data quando ela for importante. "
            "Para política e pesquisas eleitorais, seja neutro: informe instituto, período de campo, população/amostra e margem de erro quando disponíveis; "
            "não faça previsão eleitoral, não recomende candidato e não transforme pesquisa em certeza sobre resultado futuro. "
            "Não invente fonte, número, canal, horário, preço, versão ou data."
        )

    def live_search(self, text: str, history: list[dict], context: dict | None = None) -> str | None:
        self.last_live_search = {}
        if not self.live_search_enabled:
            return None
        fallback = bool(self.config.get('web_search_fallback_enabled', False))
        first = fallback and self.config.get('primary_provider') == 'groq'
        if first:
            from .web_fallback import search
            answer = search(self, text)
            if answer:
                return answer
        answer = self._gemini_live_search(text, history, context)
        if answer:
            return answer
        if fallback and not first:
            from .web_fallback import search
            return search(self, text)
        return None

    def _gemini_live_search(self, text: str, history: list[dict], context: dict | None = None) -> str | None:
        """Executa Gemini generateContent com google_search grounding e preserva fontes para a UI."""
        self.last_live_search = {}
        if not self._gemini_allowed() or not self.live_search_enabled:
            return None
        system = self._live_search_system()
        if context:
            system += "\n\nCONTEXTO DE SESSÃO ATUAL:\n" + json.dumps(context, ensure_ascii=False)[:2600]
        payload = self._gemini_payload(
            system, history, text, json_mode=False,
            max_tokens=self.live_search_max_output_tokens,
            history_limit=int(self.config.get("gemini_chat_history_turns", 10)),
        )
        payload["tools"] = [{"google_search": {}}]

        models = [self.live_search_model]
        if self.gemini_fallback_model and self.gemini_fallback_model not in models:
            models.append(self.gemini_fallback_model)
        errors = []
        started = time.perf_counter()
        for idx, current_model in enumerate(models):
            url = f"{self.gemini_base_url}/models/{current_model}:generateContent"
            try:
                timeout = self.live_search_timeout if idx == 0 else min(self.live_search_timeout, 12.0)
                if self._gemini_session is not None:
                    resp = self._gemini_session.post(
                        url, headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_key},
                        json=payload, timeout=(3.0, timeout),
                    )
                    if resp.status_code >= 400:
                        errors.append(f"{current_model}: HTTP {resp.status_code}")
                        continue
                    obj = resp.json() if resp.content else {}
                else:
                    req = urllib.request.Request(
                        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_key, "User-Agent": "V-Assistant/1.9.8"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        obj = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")

                candidate = (obj.get("candidates") or [{}])[0] or {}
                parts = ((candidate.get("content") or {}).get("parts") or [])
                answer = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
                if not answer:
                    errors.append(f"{current_model}: resposta sem texto")
                    continue

                grounding = candidate.get("groundingMetadata") or {}
                chunks = grounding.get("groundingChunks") or []
                items = []
                seen = set()
                for chunk in chunks:
                    web = (chunk or {}).get("web") if isinstance(chunk, dict) else None
                    if not isinstance(web, dict):
                        continue
                    uri = str(web.get("uri", "") or "").strip()
                    title = str(web.get("title", "") or "").strip() or self._source_domain(uri)
                    if not uri or uri in seen:
                        continue
                    seen.add(uri)
                    items.append({
                        "title": title,
                        "url": uri,
                        "source": self._source_domain(uri) or title,
                        "snippet": "Fonte usada pelo Gemini Live Search",
                        "published": "",
                    })
                    if len(items) >= max(1, self.live_search_max_sources):
                        break

                display = answer
                if items:
                    display += "\n\nFONTES VERIFICADAS:"
                    for i, item in enumerate(items, 1):
                        display += f"\n[{i}] {item['title']} — {item['url']}"

                elapsed = (time.perf_counter() - started) * 1000.0
                queries = [str(x) for x in (grounding.get("webSearchQueries") or []) if str(x).strip()]
                self.last_live_search = {
                    "active": True,
                    "answer": answer,
                    "display_text": display,
                    "speech_text": answer,
                    "items": items,
                    "queries": queries,
                    "model": current_model,
                }
                self.last_error = ""
                self.last_provider = f"gemini-search:{current_model}"
                self.last_latency = {
                    "provider": self.last_provider,
                    "total_ms": round(elapsed, 1),
                    "streaming": False,
                    "live_search": True,
                    "source_count": len(items),
                }
                try:
                    from pathlib import Path
                    log_dir = ROOT / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
                    (log_dir / "live_search_last.json").write_text(json.dumps({
                        "query": text, "model": current_model, "web_queries": queries,
                        "sources": items, "answer": answer,
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
                return display
            except Exception as exc:
                errors.append(f"{current_model}: {type(exc).__name__}: {exc}")

        elapsed = (time.perf_counter() - started) * 1000.0
        self.last_error = "Gemini Live Search: " + " | ".join(errors)
        self.last_latency = {"provider": "gemini-search", "total_ms": round(elapsed, 1), "streaming": False, "live_search": True}
        return None

    def respond_after_tools(self, user_text: str, history: list[dict], tool_results: list[dict], context: dict | None = None) -> str | None:
        system = (
            self._identity_prompt() + "\n\n" + self._memory_prompt(user_text) + "\n\n"
            "Você recebeu resultados reais do executor. Responda naturalmente, sem mencionar nomes internos de ferramentas. "
            "Para uma ação simples concluída, prefira uma frase curta. Para informação/pesquisa, use 1-3 frases. "
            "Use SOMENTE o que aparece em TOOL_RESULTS. Não acrescente sucesso, dados ou ações não confirmadas. "
            "Se algo falhou, diga de forma direta que não conseguiu concluir e preserve apenas o diagnóstico útil ao usuário."
        )
        prompt = json.dumps({"user_request": user_text, "tool_results": tool_results, "context": context or {}}, ensure_ascii=False)
        if self._gemini_allowed() and not self._groq_first():
            out = self._gemini_generate(system, history[-8:], prompt, json_mode=False, max_tokens=500)
            if out:
                return out
        if self._groq_allowed():
            out = self._groq_generate(system, history[-8:], prompt)
            if out:
                return out
        if self._gemini_allowed() and self._groq_first():
            out = self._gemini_generate(system, history[-8:], prompt, json_mode=False, max_tokens=500)
            if out:
                return out
        if self._ollama_allowed():
            messages = [{"role": "system", "content": system}]
            for item in history[-8:]:
                if item.get("role") in ("user", "assistant") and item.get("content"):
                    messages.append({"role": item["role"], "content": str(item["content"])[:1000]})
            messages.append({"role": "user", "content": prompt})
            return self._request_chat(messages, json_mode=False)
        return None

    # ---------- Gemini ----------
    def _gemini_payload(self, system: str, history: list[dict], user_text: str, *,
                        json_mode: bool = False, max_tokens: int | None = None, history_limit: int | None = None) -> dict:
        contents = []
        limit = max(0, int(history_limit if history_limit is not None else self.max_history))
        for item in history[-limit:] if limit else []:
            role = item.get("role")
            content = str(item.get("content", "") or "").strip()
            if role not in ("user", "assistant") or not content:
                continue
            contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": content[:1500]}]})
        contents.append({"role": "user", "parts": [{"text": str(user_text)}]})
        generation = {
            "maxOutputTokens": int(max_tokens or self.gemini_max_output_tokens),
            "thinkingConfig": {"thinkingLevel": self.gemini_thinking_level},
        }
        if self.gemini_model.startswith("gemini-2.5-"):
            generation["thinkingConfig"] = {"thinkingBudget": int(self.config.get("gemini_thinking_budget", 0))}
        if json_mode:
            generation["responseMimeType"] = "application/json"
        return {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": generation,
        }

    def _gemini_generate(self, system: str, history: list[dict], user_text: str, *, json_mode: bool = False,
                         max_tokens: int | None = None, model: str | None = None,
                         timeout: float | None = None, allow_model_fallback: bool = True,
                         history_limit: int | None = None) -> str | None:
        if not self._gemini_allowed():
            return None
        payload = self._gemini_payload(system, history, user_text, json_mode=json_mode, max_tokens=max_tokens, history_limit=history_limit)
        primary_model = str(model or self.gemini_model)
        models = [primary_model]
        if allow_model_fallback and self.gemini_fallback_model and self.gemini_fallback_model not in models:
            models.append(self.gemini_fallback_model)

        errors = []
        started = time.perf_counter()
        for idx, current_model in enumerate(models):
            current_timeout = float(timeout or self.gemini_timeout)
            if idx > 0:
                current_timeout = min(current_timeout, 8.0)
            url = f"{self.gemini_base_url}/models/{current_model}:generateContent"
            try:
                if self._gemini_session is not None:
                    resp = self._gemini_session.post(
                        url, headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_key},
                        json=payload, timeout=(3.0, current_timeout),
                    )
                    if resp.status_code >= 400:
                        errors.append(f"{current_model}: HTTP {resp.status_code}")
                        if resp.status_code in (400, 401, 403):
                            break
                        continue
                    obj = resp.json() if resp.content else {}
                else:
                    req = urllib.request.Request(
                        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json", "x-goog-api-key": self.gemini_key, "User-Agent": "V-Assistant/1.4.1"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=current_timeout) as resp:
                        obj = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                parts = (((obj.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
                text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
                if text:
                    elapsed = (time.perf_counter() - started) * 1000.0
                    self.last_error = ""
                    self.last_provider = f"gemini:{current_model}"
                    self.last_latency = {"provider": self.last_provider, "total_ms": round(elapsed, 1), "streaming": False}
                    return text
                feedback = obj.get("promptFeedback") or {}
                errors.append(f"{current_model}: sem texto" + (f" ({feedback})" if feedback else ""))
            except Exception as exc:
                errors.append(f"{current_model}: {type(exc).__name__}: {exc}")

        self.last_error = "Gemini: " + " | ".join(errors)
        self.last_latency = {"provider": "gemini", "total_ms": round((time.perf_counter()-started)*1000.0,1), "streaming": False}
        return None

    @staticmethod
    def _stream_sentences(buffer: str) -> tuple[list[str], str]:
        """Extrai somente frases realmente completas.

        O buffer incompleto permanece retido; isso impede o TTS de receber uma
        frase pela metade quando o SSE divide uma palavra ou uma sentença.
        """
        ready=[]
        rest=str(buffer or "")
        while True:
            m=re.search(r"^(.{6,}?[.!?…])(?:\s+|$)", rest, flags=re.S)
            if not m:
                break
            sentence=m.group(1).strip()
            if sentence:
                ready.append(sentence)
            rest=rest[m.end():].lstrip()
        return ready, rest

    @staticmethod
    def _decode_sse_line(raw_line) -> str:
        """Decodifica SSE explicitamente em UTF-8.

        requests pode assumir latin-1 quando text/event-stream não informa
        charset; isso transforma "Olá" em "OlÃ¡".
        """
        if isinstance(raw_line, (bytes, bytearray)):
            return bytes(raw_line).decode("utf-8", errors="replace").strip()
        return str(raw_line or "").strip()

    @staticmethod
    def _merge_stream_piece(full: str, piece: str) -> tuple[str, str]:
        """Mescla delta/cumulativo sem duplicar texto."""
        full=str(full or "")
        piece=str(piece or "")
        if not piece:
            return full, ""
        if not full:
            return piece, piece
        # Alguns transports podem entregar texto cumulativo.
        if piece.startswith(full):
            return piece, piece[len(full):]
        # Chunk repetido ou já contido no final.
        if full.endswith(piece):
            return full, ""
        # Remove apenas sobreposição real de sufixo/prefixo.
        max_overlap=min(len(full), len(piece), 256)
        for n in range(max_overlap, 0, -1):
            if full[-n:] == piece[:n]:
                delta=piece[n:]
                return full + delta, delta
        return full + piece, piece

    @staticmethod
    def _looks_stream_incomplete(text: str, finish_reason: str) -> bool:
        reason=str(finish_reason or "").upper().strip()
        if reason and reason != "STOP":
            return True
        clean=str(text or "").strip()
        if not clean:
            return True
        # Sem finishReason, só considera suspeito quando termina claramente no
        # meio de uma frase suficientemente longa. Respostas curtas como
        # "Pronto" continuam válidas.
        if not reason:
            if len(clean) > 45 and not re.search(r"[.!?…\)\]\"']$", clean):
                return True
            # Frases que terminam em conectivo/preposição são fortes sinais de
            # corte de stream (ex.: "vou tentar abrir para").
            if len(clean) > 12 and re.search(r"\b(?:para|pra|de|do|da|dos|das|e|que|com|por|em|um|uma|o|a)$", clean, flags=re.I):
                return True
        return False

    def chat_stream(self, text: str, history: list[dict], context: dict | None = None, chunk_callback=None) -> str | None:
        """Conversa Gemini via SSE com UTF-8 e fala segura.

        Para reduzir latência sem picotar a voz, apenas a PRIMEIRA frase
        completa é liberada durante o stream. O restante é enviado ao TTS
        como um bloco final depois que o Gemini confirma o fim da resposta.
        """
        context=context or {}
        self.last_live_search = {}
        if self.should_use_live_search(text):
            answer = self.live_search(text, history, context)
            if answer:
                speech = str((self.last_live_search or {}).get("speech_text", "") or "").strip()
                pushed = False
                if chunk_callback and speech:
                    try:
                        chunk_callback(speech)
                        pushed = True
                    except Exception:
                        pushed = False
                if isinstance(self.last_latency, dict):
                    self.last_latency["streaming"] = pushed
                return answer
            return "Não consegui verificar essa informação na internet agora. Tente novamente em alguns instantes."
        if self._groq_first() and chunk_callback:
            system = self._identity_prompt() + '\n\n' + self._memory_prompt(text)
            if context:
                system += '\nCONTEXTO DE SESSÃO:\n' + json.dumps(context, ensure_ascii=False)[:3000]
            sentence_buffer = ''
            first_sentence = ''

            def receive_delta(delta):
                nonlocal sentence_buffer, first_sentence
                sentence_buffer += delta
                if not first_sentence:
                    ready, rest = self._stream_sentences(sentence_buffer)
                    if ready:
                        first_sentence = ready[0]
                        sentence_buffer = (' '.join(ready[1:]) + (' ' if len(ready) > 1 and rest else '') + rest).strip()
                        try:
                            chunk_callback(first_sentence)
                        except Exception:
                            pass

            answer = self.groq.generate_stream(system, history, text, chunk_callback=receive_delta)
            streamed = bool(first_sentence)
            if answer:
                if first_sentence and answer.startswith(first_sentence):
                    remainder = answer[len(first_sentence):].strip()
                    if remainder:
                        try:
                            chunk_callback(remainder)
                        except Exception:
                            pass
                elif not first_sentence:
                    try:
                        chunk_callback(answer)
                        streamed = True
                    except Exception:
                        pass
                self.last_error = ''
                self.last_provider = 'groq:' + self.groq.model
                self.last_latency = dict(self.groq.last_latency)
                self.last_latency['streaming'] = streamed
                return answer

            # If the stream failed before any audio started, try the normal
            # provider fallback. Once the opening phrase is audible, finish the
            # best available text and remove its already spoken prefix.
            stream_error = self.groq.last_error
            if not first_sentence:
                self.last_error = stream_error
                self.last_latency = dict(self.groq.last_latency)
                # No audio escaped, so the regular provider path is safe and
                # preserves its existing Groq -> Gemini/Ollama recovery order.
                return self.chat(text, history, context)
            fallback = self._chat_local_fallback(text, history, context, skip_groq=True, primary_error=stream_error)
            partial = str(self.groq.last_stream_text or '').strip()
            if fallback:
                answer = str(fallback).strip()
                shared = 0
                for left, right in zip(first_sentence, answer):
                    if left != right:
                        break
                    shared += 1
                remainder = answer[shared:].strip()
                if remainder:
                    try:
                        chunk_callback(remainder)
                    except Exception:
                        pass
            else:
                answer = partial
                if answer.startswith(first_sentence):
                    remainder = answer[len(first_sentence):].strip()
                    if remainder:
                        try:
                            chunk_callback(remainder)
                        except Exception:
                            pass
            self.last_latency = dict(self.groq.last_latency)
            self.last_latency['streaming'] = True
            self.last_latency['fallback_reason'] = stream_error
            return answer or None
        if self._groq_first() or not bool(self.config.get("stream_chat", True)):
            return self.chat(text, history, context)
        if not self._gemini_allowed() or self._gemini_session is None:
            return self.chat(text, history, context)
        if self._chat_online_paused():
            return self._chat_local_fallback(text, history, context)

        system=self._identity_prompt()+"\n\n"+self._memory_prompt(text)
        if context:
            system += "\n\nCONTEXTO DE SESSÃO ATUAL:\n" + json.dumps(context, ensure_ascii=False)[:2600]
        payload=self._gemini_payload(
            system, history, text, json_mode=False,
            max_tokens=int(self.config.get("gemini_stream_max_output_tokens", 520)),
            history_limit=int(self.config.get("gemini_chat_history_turns", 10)),
        )
        models=[self.gemini_chat_model]
        if self.gemini_fallback_model and self.gemini_fallback_model not in models:
            models.append(self.gemini_fallback_model)

        errors=[]
        for idx,current_model in enumerate(models):
            started=time.perf_counter()
            first_chunk_ms=None
            full=""
            sentence_buffer=""
            first_sentence_spoken=""
            finish_reason=""
            repaired=False
            url=f"{self.gemini_base_url}/models/{current_model}:streamGenerateContent"
            resp = None
            try:
                resp=self._gemini_session.post(
                    url,
                    params={"alt": "sse"},
                    headers={"Content-Type":"application/json","x-goog-api-key":self.gemini_key,"Accept":"text/event-stream"},
                    json=payload, stream=True,
                    timeout=(3.0, float(self.gemini_chat_timeout if idx==0 else min(self.gemini_chat_timeout,8.0))),
                )
                # Evita mojibake em respostas SSE sem charset explícito.
                resp.encoding="utf-8"
                if resp.status_code >= 400:
                    errors.append(f"{current_model}: HTTP {resp.status_code}")
                    if resp.status_code in (400,401,403):
                        break
                    continue

                # Deliver each SSE line immediately, including small responses.
                for raw_line in resp.iter_lines(chunk_size=1, decode_unicode=False):
                    if not raw_line:
                        continue
                    line=self._decode_sse_line(raw_line)
                    if not line.startswith("data:"):
                        continue
                    data=line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        obj=json.loads(data)
                    except Exception:
                        continue
                    candidate=(obj.get("candidates") or [{}])[0] or {}
                    fr=str(candidate.get("finishReason") or candidate.get("finish_reason") or "").strip()
                    if fr:
                        finish_reason=fr
                    parts=((candidate.get("content") or {}).get("parts") or [])
                    piece="".join(
                        str(p.get("text", ""))
                        for p in parts
                        if isinstance(p,dict) and not bool(p.get("thought", False))
                    )
                    if not piece:
                        continue
                    if first_chunk_ms is None:
                        first_chunk_ms=(time.perf_counter()-started)*1000.0
                    full,delta=self._merge_stream_piece(full,piece)
                    if not delta:
                        continue
                    sentence_buffer += delta

                    # Só a primeira frase vai imediatamente para a voz. Isso
                    # preserva a sensação instantânea sem fragmentar o restante.
                    if chunk_callback and not first_sentence_spoken:
                        ready,rest=self._stream_sentences(sentence_buffer)
                        if ready:
                            first_sentence_spoken=ready[0]
                            sentence_buffer=(" ".join(ready[1:]) + (" " if len(ready)>1 and rest else "") + rest).strip()
                            try:
                                chunk_callback(first_sentence_spoken)
                            except Exception:
                                pass

                full=full.strip()
                if full and self._looks_stream_incomplete(full, finish_reason):
                    # Stream terminou no meio da frase/por limite. Refaz somente
                    # nesses casos, usando a rota não-stream mais robusta.
                    repaired_text=self._gemini_generate(
                        system, history, text, json_mode=False,
                        max_tokens=int(self.config.get("gemini_stream_repair_tokens", 560)),
                        model=current_model, timeout=self.gemini_chat_timeout,
                        allow_model_fallback=True,
                        history_limit=int(self.config.get("gemini_chat_history_turns", 10)),
                    )
                    if repaired_text and len(repaired_text.strip()) >= max(8, len(full)//2):
                        full=repaired_text.strip()
                        repaired=True

                if full:
                    # Garante que TODA a resposta seja falada exatamente uma vez.
                    if chunk_callback:
                        if first_sentence_spoken and full.startswith(first_sentence_spoken):
                            remainder=full[len(first_sentence_spoken):].strip()
                            if remainder:
                                try:
                                    chunk_callback(remainder)
                                except Exception:
                                    pass
                        elif not first_sentence_spoken:
                            try:
                                chunk_callback(full)
                            except Exception:
                                pass
                        else:
                            # Caso raro: reparo mudou a abertura. Evita repetir a
                            # primeira frase e fala a parte restante mais provável.
                            remainder=sentence_buffer.strip()
                            if remainder:
                                try:
                                    chunk_callback(remainder)
                                except Exception:
                                    pass

                    total_ms=(time.perf_counter()-started)*1000.0
                    self.last_error=""
                    self.last_provider=f"gemini:{current_model}"
                    self.last_latency={
                        "provider": self.last_provider,
                        "first_chunk_ms": round(first_chunk_ms or total_ms,1),
                        "total_ms": round(total_ms,1),
                        "streaming": True,
                        "finish_reason": finish_reason or "unknown",
                        "repaired": repaired,
                    }
                    return full
                errors.append(f"{current_model}: stream sem texto")
            except Exception as exc:
                errors.append(f"{current_model}: {type(exc).__name__}: {exc}")
            finally:
                if resp is not None:
                    resp.close()

        self.last_error="Gemini stream: "+" | ".join(errors)
        self.last_latency = {"provider": "gemini", "streaming": False}
        # All configured online models were already attempted. Repeating them
        # here doubled timeout waits before the working local provider.
        return self._chat_local_fallback(text, history, context)

    def _gemini_chat(self, text: str, history: list[dict], context: dict) -> str | None:
        system = self._identity_prompt() + "\n\n" + self._memory_prompt(text)
        if context:
            system += "\n\nCONTEXTO DE SESSÃO ATUAL:\n" + json.dumps(context, ensure_ascii=False)[:3500]
        return self._gemini_generate(
            system, history, text, json_mode=False, max_tokens=360,
            model=self.gemini_chat_model, timeout=self.gemini_chat_timeout,
            allow_model_fallback=True, history_limit=int(self.config.get("gemini_chat_history_turns", 10)),
        )

    def _gemini_plan(self, text: str, history: list[dict], context: dict, tool_manifest: list[dict]) -> BrainPlan | None:
        system = self._planner_system(tool_manifest, text)
        prompt = json.dumps({"recent_context": context, "user_request": text}, ensure_ascii=False)
        raw = self._gemini_generate(
            system, history, prompt, json_mode=True, max_tokens=800,
            model=self.gemini_plan_model, timeout=self.gemini_plan_timeout,
            allow_model_fallback=True, history_limit=int(self.config.get("gemini_plan_history_turns", 6)),
        )
        if not raw:
            return None
        obj = self._extract_json(raw)
        if not isinstance(obj, dict):
            self.last_error = "Gemini não retornou um plano JSON válido."
            return None
        return self._plan_from_obj(obj, tool_manifest, "gemini")

    # ---------- Ollama fallback ----------
    def _request_chat(self, messages: list[dict], *, json_mode: bool = False) -> str | None:
        started = time.perf_counter()
        self.last_latency = {"provider": "ollama", "streaming": False}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
            "keep_alive": self.keep_alive,
        }
        if json_mode:
            payload["format"] = "json"
        if self.config.get('ollama_cpu_only', False):
            payload['options'].update(num_gpu=0, num_thread=2)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base_url + "/api/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                obj = json.loads(raw or "{}")
                answer = str(((obj.get("message") or {}).get("content") or "")).strip()
                if answer:
                    self.last_error = ""
                    self.last_provider = "ollama"
                    return answer
                self.last_error = "Ollama: resposta sem texto"
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            self.last_error = f"Ollama HTTP {exc.code}: {body or exc.reason}"
        except Exception as exc:
            self.last_error = f"Ollama {type(exc).__name__}: {exc}"
        finally:
            self.last_latency['total_ms'] = round((time.perf_counter() - started) * 1000.0, 1)
        return None

    def _planner_system(self, tool_manifest: list[dict], query='') -> str:
        tools = json.dumps(tool_manifest, ensure_ascii=False, indent=2)
        return (
            self._identity_prompt() + "\n\n" + self._memory_prompt(query) + "\n\n"
            "Você é também o planejador do V. Você pensa, mas NÃO executa ações.\n"
            "Use somente as ferramentas publicadas abaixo. Não invente ferramentas.\n"
            f"TOOL REGISTRY:\n{tools}\n\n"
            "Responda SOMENTE JSON válido:\n"
            '{"mode":"tools","actions":[{"tool":"nome.exato","args":{}}],"reply":""}\n'
            "ou para conversa sem ação:\n"
            '{"mode":"chat","actions":[],"reply":"resposta natural e útil em pt-BR"}\n\n'
            "REGRAS:\n"
            "- Notícias: news.today/news.topic; jamais Spotify.\n"
            "- Bolsa/mercado: market.overview para visão geral e market.quote para ativo/ticker específico.\n"
            "- Música: spotify.play_track só com intenção de música/Spotify ou contexto inequívoco.\n"
            "- Perguntas e saudações: mode=chat.\n"
            "- Abrir/fechar apps: app.open/app.close.\n"
            "- Estado do PC: system.pc_status.\n"
            "- Pesquisa investigativa: web.research.\n"
            "- Resolva referências contextuais como 'ele', 'deles', 'essa' usando o histórico quando houver uma única interpretação segura.\n"
            "- Se a referência estiver ambígua, use mode=chat e pergunte; não chute ferramenta.\n"
            "- Nunca gere shell/CMD/PowerShell, exclusão de arquivos ou credenciais.\n"
            "- Nunca diga que ação foi concluída; o executor confirma depois."
        )

    def _plan_from_obj(self, obj: dict, tool_manifest: list[dict], provider: str) -> BrainPlan | None:
        mode = str(obj.get("mode", "")).lower().strip()
        reply = str(obj.get("reply", "") or "").strip()
        allowed = {str(x.get("name", "")) for x in tool_manifest if isinstance(x, dict)}
        actions = []
        for action in (obj.get("actions") or [])[:8]:
            if not isinstance(action, dict):
                continue
            tool = str(action.get("tool", "")).strip()
            if tool not in allowed:
                continue
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            actions.append({"tool": tool, "args": args})
        if mode in ("tools", "actions") and actions:
            return BrainPlan("tools", actions, reply, obj, provider)
        if mode == "chat":
            return BrainPlan("chat", [], reply or "Pode me explicar um pouco melhor?", obj, provider)
        return None

    def _ollama_plan(self, text: str, history: list[dict], context: dict, tool_manifest: list[dict]) -> BrainPlan | None:
        messages = [{"role": "system", "content": self._planner_system(tool_manifest, text)}]
        for item in history[-self.max_history:]:
            if item.get("role") in ("user", "assistant") and item.get("content"):
                messages.append({"role": item["role"], "content": str(item["content"])[:1100]})
        messages.append({"role": "user", "content": json.dumps({"recent_context": context, "user_request": text}, ensure_ascii=False)})
        raw = self._request_chat(messages, json_mode=True)
        if not raw:
            return None
        obj = self._extract_json(raw)
        if not isinstance(obj, dict):
            self.last_error = "A IA local não retornou um plano JSON válido."
            return None
        return self._plan_from_obj(obj, tool_manifest, "ollama")

    def _ollama_chat(self, text: str, history: list[dict], context: dict) -> str | None:
        system = self._identity_prompt() + "\n\n" + self._memory_prompt(text)
        messages = [{"role": "system", "content": system}]
        for item in history[-self.max_history:]:
            if item.get("role") in ("user", "assistant") and item.get("content"):
                messages.append({"role": item["role"], "content": str(item["content"])[:1400]})
        if context:
            messages.append({"role": "system", "content": "CONTEXTO DE SESSÃO ATUAL:\n" + json.dumps(context, ensure_ascii=False)[:3000]})
        messages.append({"role": "user", "content": text})
        return self._request_chat(messages, json_mode=False)

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        s = str(raw or "").strip()
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
