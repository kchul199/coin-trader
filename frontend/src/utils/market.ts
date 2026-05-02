export const DEFAULT_EXCHANGE_ID = 'upbit'
export const DEFAULT_QUOTE_CURRENCY = 'KRW'
export const DEFAULT_STRATEGY_SYMBOL = 'BTC/KRW'
export const DEFAULT_DASHBOARD_SYMBOLS = ['BTCKRW', 'ETHKRW']
export const DEFAULT_CHART_SYMBOLS = ['BTCKRW', 'ETHKRW', 'XRPKRW']

const KNOWN_QUOTES = ['KRW', 'USDT', 'BTC', 'ETH'] as const

export function normalizeMarketSymbol(symbol: string, defaultQuote = DEFAULT_QUOTE_CURRENCY) {
  const raw = symbol.trim().toUpperCase()
  if (!raw) {
    return raw
  }

  if (raw.includes('/')) {
    return raw
  }

  if (raw.includes('-')) {
    const [quote, base] = raw.split('-', 2)
    return `${base}/${quote}`
  }

  const candidates = [defaultQuote, ...KNOWN_QUOTES.filter((quote) => quote !== defaultQuote)]
  for (const quote of candidates) {
    if (raw.endsWith(quote) && raw.length > quote.length) {
      return `${raw.slice(0, -quote.length)}/${quote}`
    }
  }

  return raw
}

export function toCompactSymbol(symbol: string, defaultQuote = DEFAULT_QUOTE_CURRENCY) {
  return normalizeMarketSymbol(symbol, defaultQuote).replace('/', '')
}

export function getTickerSymbolForAsset(asset: string, quoteCurrency = DEFAULT_QUOTE_CURRENCY) {
  const normalizedAsset = asset.trim().toUpperCase()
  if (!normalizedAsset || normalizedAsset === quoteCurrency) {
    return null
  }
  return `${normalizedAsset}${quoteCurrency}`
}

export function formatQuoteCurrency(value: number | null, quoteCurrency = DEFAULT_QUOTE_CURRENCY) {
  if (value === null) {
    return '-'
  }

  if (quoteCurrency === 'KRW') {
    const rounded = Math.round(value)
    const prefix = rounded < 0 ? '-' : ''
    return `${prefix}₩${Math.abs(rounded).toLocaleString('ko-KR')}`
  }

  const prefix = value < 0 ? '-' : ''
  return `${prefix}${quoteCurrency} ${Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function formatQuoteDelta(value: number | null, quoteCurrency = DEFAULT_QUOTE_CURRENCY) {
  if (value === null) {
    return '-'
  }

  const prefix = value >= 0 ? '+' : ''
  return `${prefix}${formatQuoteCurrency(value, quoteCurrency)}`
}
