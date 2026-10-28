"""Pesquisa web e notícias em tempo real para o V.

Sem chaves de API:
- Google News RSS para manchetes recentes.
- DuckDuckGo HTML para pesquisa/levantamento geral.
- Ollama local para sintetizar os resultados quando disponível.

O módulo nunca afirma que consultou a web se a requisição falhar e sempre
inclui as fontes/links disponíveis no resultado.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from legacy_config import OLLAMA_URL, MODEL

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7"}
TIMEOUT = (3, 8)

_LAST_NEWS: list[dict] = []
_LAST_RESEARCH: list[dict] = []


@dataclass
class WebItem:
    title: str
    url: str
    source: str = ""
    snippet: str = ""
    published: str = ""
    image_url: str = ""

    def as_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "snippet": self.snippet,
            "published": self.published,
            "image_url": self.image_url,
        }


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = BeautifulSoup(html.unescape(text), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
        return host or "fonte web"
    except Exception:
        return "fonte web"


def _google_news_url(topic: str | None = None) -> str:
    base = "https://news.google.com/rss"
    params = {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}
    if topic:
        # when:1d prioriza conteúdo das últimas 24h.
        query = f"{topic.strip()} when:1d"
        return base + "/search?" + urllib.parse.urlencode({"q": query, **params})
    return base + "?" + urllib.parse.urlencode(params)


def _write_web_error(kind: str, primary: Exception | str, fallback: Exception | str | None = None):
    """Registra o erro real sem deixar a interface presa em uma mensagem genérica."""
    try:
        logs = Path(__file__).resolve().parent / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": kind,
            "time": _dt.datetime.now().isoformat(timespec="seconds"),
            "primary": str(primary),
            "fallback": str(fallback or ""),
        }
        (logs / "web_last_error.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def fetch_news(topic: str | None = None, limit: int = 6) -> list[WebItem]:
    """Busca notícias com fallback leve.

    Google News RSS continua sendo a fonte principal. Se o RSS estiver
    temporariamente bloqueado/fora do ar, usa a busca HTML já existente em
    vez de declarar que toda a web está inacessível.
    """
    url = _google_news_url(topic)
    primary_error = None
    try:
        res = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        res.raise_for_status()
        root = ET.fromstring(res.content)
        items: list[WebItem] = []
        for node in root.findall("./channel/item"):
            title = _clean(node.findtext("title"))
            link = _clean(node.findtext("link"))
            pub_date = _clean(node.findtext("pubDate"))
            source_node = node.find("source")
            source = _clean(source_node.text if source_node is not None else "")
            # O Google News costuma anexar " - Fonte" à manchete embora a fonte
            # já venha em um campo separado. Remover isso melhora o slide, a fala
            # e também a busca da imagem do artigo.
            if source and title.lower().endswith((" - " + source).lower()):
                title = title[:-(len(source) + 3)].strip()
            raw_desc = node.findtext("description") or ""
            desc = _clean(raw_desc)

            # Alguns feeds já trazem thumbnail no description/media namespace.
            # Quando não houver, o HUD tenta descobrir og:image em background.
            image_url = ""
            try:
                desc_soup = BeautifulSoup(html.unescape(raw_desc), "html.parser")
                img = desc_soup.find("img")
                if img and img.get("src"):
                    image_url = str(img.get("src")).strip()
            except Exception:
                pass
            if not image_url:
                try:
                    for child in node.iter():
                        tag = str(child.tag).lower()
                        candidate = str(child.attrib.get("url", "") or "").strip()
                        media_type = str(child.attrib.get("type", "") or "").lower()
                        if candidate and (tag.endswith("thumbnail") or "image" in media_type):
                            image_url = candidate
                            break
                except Exception:
                    pass

            if title and link:
                items.append(WebItem(title=title, url=link, source=source, snippet=desc, published=pub_date, image_url=image_url))
            if len(items) >= limit:
                break
        if items:
            return items
    except Exception as exc:
        primary_error = exc

    # Fallback sem API/chave. Não promete publicação nas últimas 24h quando o
    # RSS não está disponível; retorna resultados de busca relacionados a hoje.
    try:
        query = f"{topic} notícias hoje Brasil" if topic else "principais notícias Brasil hoje"
        items = web_search(query, limit=limit)
        if items:
            return items
        raise RuntimeError("a busca alternativa não retornou resultados")
    except Exception as fallback_error:
        _write_web_error("news", primary_error or "RSS sem itens", fallback_error)
        if primary_error:
            raise RuntimeError(f"Google News: {primary_error}; busca alternativa: {fallback_error}") from fallback_error
        raise


def news_brief(topic: str | None = None, limit: int = 6) -> str:
    global _LAST_NEWS
    try:
        items = fetch_news(topic, limit)
    except Exception as exc:
        return f"Não consegui consultar as notícias agora. Erro de conexão: {exc}"
    if not items:
        return "Não encontrei notícias recentes para esse assunto."
    _LAST_NEWS = [x.as_dict() for x in items]

    today = _dt.datetime.now().strftime("%d/%m/%Y")
    header = f"Briefing de notícias de {today}"
    if topic:
        header += f" sobre {topic}"
    lines = [header + ":"]
    for i, item in enumerate(items, 1):
        src = item.source or _domain(item.url)
        lines.append(f"{i}. {item.title}. Fonte: {src}.")
    lines.append("As fontes e links ficaram registrados abaixo para consulta.")
    lines.append("FONTES:")
    for i, item in enumerate(items, 1):
        lines.append(f"[{i}] {item.source or _domain(item.url)} — {item.url}")
    return "\n".join(lines)


def _decode_ddg_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return urllib.parse.unquote(qs["uddg"][0])
    except Exception:
        pass
    return href


def web_search(query: str, limit: int = 7) -> list[WebItem]:
    endpoint = "https://html.duckduckgo.com/html/"
    res = requests.post(endpoint, data={"q": query}, headers=HEADERS, timeout=TIMEOUT)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    results: list[WebItem] = []
    seen = set()
    for result in soup.select(".result"):
        a = result.select_one("a.result__a")
        if not a:
            continue
        title = _clean(a.get_text(" ", strip=True))
        url = _decode_ddg_href(a.get("href", ""))
        snippet_node = result.select_one(".result__snippet")
        snippet = _clean(snippet_node.get_text(" ", strip=True) if snippet_node else "")
        if not title or not url or url in seen:
            continue
        seen.add(url)
        results.append(WebItem(title=title, url=url, source=_domain(url), snippet=snippet))
        if len(results) >= limit:
            break
    return results


def _ollama_summarize(query: str, items: Iterable[WebItem]) -> str | None:
    packed = []
    for i, item in enumerate(items, 1):
        packed.append(
            f"FONTE {i}\nTítulo: {item.title}\nSite: {item.source or _domain(item.url)}\n"
            f"Resumo/trecho: {item.snippet[:900]}\nURL: {item.url}"
        )
    evidence = "\n\n".join(packed)
    prompt = f"""Você é o módulo de pesquisa do V. Faça um levantamento objetivo em português do Brasil sobre: {query}

Use SOMENTE as evidências abaixo. Não invente números, fatos ou fontes. Se as fontes divergirem, diga isso. Diferencie fato encontrado de inferência. Faça uma síntese curta, em até 6 tópicos, adequada para ser lida em voz alta. Não repita URLs no corpo; as URLs serão exibidas depois.

EVIDÊNCIAS:\n{evidence}"""
    try:
        res = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "Resuma evidências web com rigor e sem inventar informações."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.25},
            },
            timeout=(3, 38),
        )
        res.raise_for_status()
        return res.json()["message"]["content"].strip()
    except Exception:
        return None


def save_report(query: str, text: str, items: Iterable[WebItem]) -> Path:
    out = Path.cwd() / "jarvis_reports"
    out.mkdir(exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", query.strip())[:60].strip("_") or "pesquisa"
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"{safe}_{stamp}.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"LEVANTAMENTO V\nAssunto: {query}\nData: {_dt.datetime.now():%d/%m/%Y %H:%M}\n\n")
        f.write(text.strip() + "\n\nFONTES\n")
        for i, item in enumerate(items, 1):
            f.write(f"[{i}] {item.title}\n{item.url}\n\n")
    return path


def research_brief(query: str, limit: int = 7, save: bool = True) -> str:
    global _LAST_RESEARCH
    query = query.strip()
    if not query:
        return "Diga qual assunto você quer que eu pesquise."
    try:
        items = web_search(query, limit)
    except Exception as exc:
        return f"Não consegui fazer o levantamento na web agora. Erro de conexão: {exc}"
    if not items:
        return "A pesquisa não retornou fontes suficientes para eu fazer um levantamento confiável."
    _LAST_RESEARCH = [x.as_dict() for x in items]

    summary = _ollama_summarize(query, items)
    if not summary:
        lines = [f"Encontrei {len(items)} fontes sobre {query}:"]
        for i, item in enumerate(items, 1):
            detail = item.snippet or item.title
            lines.append(f"{i}. {item.title}. {detail[:220]}")
        summary = "\n".join(lines)

    path = save_report(query, summary, items) if save else None
    lines = [summary, "", "FONTES:"]
    for i, item in enumerate(items, 1):
        lines.append(f"[{i}] {item.source or _domain(item.url)} — {item.url}")
    if path:
        lines.extend(["", f"Relatório salvo em: {path}"])
    return "\n".join(lines)


def last_sources(kind: str = "auto") -> str:
    data = _LAST_RESEARCH if kind == "research" else _LAST_NEWS if kind == "news" else (_LAST_RESEARCH or _LAST_NEWS)
    if not data:
        return "Ainda não tenho fontes de uma pesquisa recente nesta sessão."
    lines = ["Fontes da consulta mais recente:"]
    for i, item in enumerate(data, 1):
        lines.append(f"[{i}] {item.get('source') or _domain(item.get('url',''))} — {item.get('url','')}")
    return "\n".join(lines)


def latest_items(kind: str = "auto") -> list[dict]:
    """Retorna uma cópia dos itens da última consulta para a janela interna."""
    if kind == "news":
        data = _LAST_NEWS
    elif kind == "research":
        data = _LAST_RESEARCH
    else:
        data = _LAST_RESEARCH or _LAST_NEWS
    return [dict(x) for x in data]
