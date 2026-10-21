from __future__ import annotations

"""Dados leves de mercado para o V.

Usa o endpoint chart público do Yahoo Finance, sem chave de API. O objetivo é
mostrar cotações/variações informativas dentro do painel do V; não é um feed de
baixa latência nem ferramenta de negociação.
"""

import concurrent.futures
import datetime as dt
import re
import urllib.parse

import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}
_TIMEOUT = (2.5, 6.0)

_ALIASES = {
    "ibovespa": "^BVSP",
    "ibov": "^BVSP",
    "bovespa": "^BVSP",
    "petrobras": "PETR4.SA",
    "petr4": "PETR4.SA",
    "petr3": "PETR3.SA",
    "vale": "VALE3.SA",
    "vale3": "VALE3.SA",
    "itau": "ITUB4.SA",
    "itau unibanco": "ITUB4.SA",
    "itub4": "ITUB4.SA",
    "bradesco": "BBDC4.SA",
    "bbdc4": "BBDC4.SA",
    "banco do brasil": "BBAS3.SA",
    "bbas3": "BBAS3.SA",
    "weg": "WEGE3.SA",
    "wege3": "WEGE3.SA",
    "magalu": "MGLU3.SA",
    "magazine luiza": "MGLU3.SA",
    "mglu3": "MGLU3.SA",
}

_OVERVIEW = ["^BVSP", "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBAS3.SA"]


def _norm(text: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip(" .,!?:;-—–")


def resolve_symbol(text: str) -> str:
    raw = str(text or "").strip()
    upper = raw.upper()
    # Ticker B3 explícito, por exemplo PETR4, VALE3, BBAS3.
    m = re.search(r"\b([A-Z]{4}\d{1,2})\b", upper)
    if m:
        return m.group(1) + ".SA"
    n = _norm(raw)
    for alias, symbol in sorted(_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", n):
            return symbol
    return ""


def _fmt_number(value: float, decimals: int = 2) -> str:
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _display_name(symbol: str, meta: dict) -> str:
    if symbol == "^BVSP":
        return "Ibovespa"
    name = str(meta.get("shortName") or meta.get("longName") or symbol).strip()
    return name.replace(".SA", "")


def fetch_quote(symbol: str) -> dict:
    encoded = urllib.parse.quote(symbol, safe="")
    payload = None
    last_error = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = f"https://{host}/v8/finance/chart/{encoded}"
            r = requests.get(
                url,
                params={"range": "5d", "interval": "1d", "includePrePost": "false", "events": "div,splits"},
                headers=_HEADERS,
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            payload = r.json()
            result = ((payload.get("chart") or {}).get("result") or [None])[0]
            if result:
                break
            err = (payload.get("chart") or {}).get("error") or {}
            last_error = RuntimeError(err.get("description") or "cotação indisponível")
        except Exception as exc:
            last_error = exc
            result = None
    if not result:
        raise RuntimeError(str(last_error or "cotação indisponível"))

    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    previous = meta.get("previousClose") or meta.get("chartPreviousClose")

    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    valid_closes = [float(x) for x in closes if x is not None]
    if price is None and valid_closes:
        price = valid_closes[-1]
    if previous is None and len(valid_closes) >= 2:
        previous = valid_closes[-2]
    if price is None:
        raise RuntimeError("preço não retornado pela fonte")

    price = float(price)
    previous = float(previous) if previous not in (None, 0) else None
    change = price - previous if previous is not None else None
    pct = (change / previous * 100.0) if previous not in (None, 0) else None
    currency = str(meta.get("currency") or ("BRL" if symbol.endswith(".SA") else "")).upper()
    market_time = meta.get("regularMarketTime")
    if market_time:
        try:
            stamp = dt.datetime.fromtimestamp(int(market_time)).astimezone().strftime("%d/%m/%Y %H:%M")
        except Exception:
            stamp = ""
    else:
        stamp = ""

    return {
        "symbol": symbol,
        "name": _display_name(symbol, meta),
        "price": price,
        "previous": previous,
        "change": change,
        "change_percent": pct,
        "currency": currency,
        "published": stamp,
        "exchange": str(meta.get("exchangeName") or meta.get("fullExchangeName") or "Yahoo Finance"),
        "url": f"https://finance.yahoo.com/quote/{encoded}",
    }


def _quote_item(q: dict) -> dict:
    symbol = q["symbol"]
    is_index = symbol == "^BVSP"
    unit = " pts" if is_index else (f" {q['currency']}" if q.get("currency") else "")
    price = _fmt_number(q["price"], 2)
    pct = q.get("change_percent")
    change = q.get("change")
    if pct is None or change is None:
        movement = "variação indisponível"
    else:
        sign = "+" if change >= 0 else ""
        movement = f"{sign}{_fmt_number(change, 2)} • {sign}{_fmt_number(pct, 2)}%"
    label = "IBOV" if is_index else symbol.replace(".SA", "")
    return {
        "title": f"{q['name']} ({label})",
        "source": "Yahoo Finance",
        "snippet": f"{price}{unit} • {movement}. Cotação informativa; pode haver atraso na fonte.",
        "published": q.get("published", ""),
        "url": q.get("url", ""),
        "image_url": "",
        **q,
    }


def market_overview() -> tuple[str, list[dict]]:
    quotes: dict[str, dict] = {}
    errors: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(_OVERVIEW)) as pool:
        futures = {pool.submit(fetch_quote, symbol): symbol for symbol in _OVERVIEW}
        for future, symbol in [(f, s) for f, s in futures.items()]:
            try:
                quotes[symbol] = future.result()
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
    items = [_quote_item(quotes[s]) for s in _OVERVIEW if s in quotes]
    if not items:
        raise RuntimeError("; ".join(errors) or "nenhuma cotação retornada")

    ibov = quotes.get("^BVSP")
    if ibov:
        pct = ibov.get("change_percent")
        direction = "subindo" if pct is not None and pct > 0 else "caindo" if pct is not None and pct < 0 else "estável"
        pct_text = f" {_fmt_number(abs(pct), 2)}%" if pct is not None else ""
        intro = f"Ibovespa em {_fmt_number(ibov['price'], 2)} pontos, {direction}{pct_text}."
    else:
        intro = "Consegui consultar ações brasileiras, mas o índice Ibovespa não retornou agora."
    msg = intro + " O painel mostra também Petrobras, Vale, Itaú e Banco do Brasil. Dados informativos e sujeitos a atraso."
    return msg, items


def market_quote(query: str) -> tuple[str, list[dict]]:
    symbol = resolve_symbol(query)
    if not symbol:
        raise ValueError("Não reconheci o ativo. Tente, por exemplo, PETR4, VALE3, BBAS3 ou Ibovespa.")
    q = fetch_quote(symbol)
    item = _quote_item(q)
    pct = q.get("change_percent")
    if symbol == "^BVSP":
        value = f"{_fmt_number(q['price'], 2)} pontos"
    else:
        value = f"{_fmt_number(q['price'], 2)} {q.get('currency') or ''}".strip()
    if pct is None:
        movement = "sem variação calculável agora"
    else:
        movement = ("alta de " if pct >= 0 else "queda de ") + f"{_fmt_number(abs(pct), 2)}%"
    msg = f"{q['name']}: {value}, {movement}. Dados informativos e sujeitos a atraso."
    return msg, [item]
