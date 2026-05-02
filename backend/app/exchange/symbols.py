from __future__ import annotations

KNOWN_QUOTES = ("KRW", "USDT", "BTC", "ETH")


def normalize_symbol(symbol: str, default_quote: str | None = None) -> str:
    """입력 심볼을 CCXT 표준인 BASE/QUOTE 형식으로 정규화한다."""
    raw = (symbol or "").strip().upper()
    if not raw:
        return raw

    if "/" in raw:
        base, quote = raw.split("/", 1)
        return f"{base}/{quote}"

    if "-" in raw:
        quote, base = raw.split("-", 1)
        return f"{base}/{quote}"

    for quote in _quote_candidates(default_quote):
        if raw.endswith(quote) and len(raw) > len(quote):
            base = raw[: -len(quote)]
            return f"{base}/{quote}"

    return raw


def split_symbol(symbol: str, default_quote: str | None = None) -> tuple[str, str]:
    normalized = normalize_symbol(symbol, default_quote)
    if "/" not in normalized:
        raise ValueError(f"지원하지 않는 심볼 형식: {symbol}")
    base, quote = normalized.split("/", 1)
    return base, quote


def to_compact_symbol(symbol: str, default_quote: str | None = None) -> str:
    base, quote = split_symbol(symbol, default_quote)
    return f"{base}{quote}"


def to_upbit_market_code(symbol: str, default_quote: str | None = None) -> str:
    base, quote = split_symbol(symbol, default_quote)
    return f"{quote}-{base}"


def get_default_symbols(exchange_id: str, quote_currency: str) -> list[str]:
    quote = quote_currency.upper()
    if exchange_id == "upbit":
        return [f"BTC/{quote}", f"ETH/{quote}"]
    return ["BTC/USDT", "ETH/USDT"]


def _quote_candidates(default_quote: str | None) -> list[str]:
    candidates: list[str] = []
    if default_quote:
        candidates.append(default_quote.upper())
    for quote in KNOWN_QUOTES:
        if quote not in candidates:
            candidates.append(quote)
    return candidates
