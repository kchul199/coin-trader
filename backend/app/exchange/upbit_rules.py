from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

UPBIT_KRW_MIN_ORDER_AMOUNT = Decimal("5000")


def get_upbit_krw_tick_size(price: Decimal) -> Decimal:
    if price >= Decimal("1000000"):
        return Decimal("1000")
    if price >= Decimal("500000"):
        return Decimal("500")
    if price >= Decimal("100000"):
        return Decimal("100")
    if price >= Decimal("50000"):
        return Decimal("50")
    if price >= Decimal("10000"):
        return Decimal("10")
    if price >= Decimal("5000"):
        return Decimal("5")
    if price >= Decimal("100"):
        return Decimal("1")
    if price >= Decimal("10"):
        return Decimal("0.1")
    if price >= Decimal("1"):
        return Decimal("0.01")
    if price >= Decimal("0.1"):
        return Decimal("0.001")
    if price >= Decimal("0.01"):
        return Decimal("0.0001")
    if price >= Decimal("0.001"):
        return Decimal("0.00001")
    if price >= Decimal("0.0001"):
        return Decimal("0.000001")
    if price >= Decimal("0.00001"):
        return Decimal("0.0000001")
    return Decimal("0.00000001")


def floor_to_tick_size(value: Decimal, tick_size: Decimal) -> Decimal:
    if tick_size <= 0:
        return value
    steps = (value / tick_size).to_integral_value(rounding=ROUND_DOWN)
    return steps * tick_size


def normalize_upbit_limit_price(price: Decimal, quote_currency: str) -> Decimal:
    if quote_currency.upper() != "KRW":
        return price
    tick_size = get_upbit_krw_tick_size(price)
    return floor_to_tick_size(price, tick_size)


def normalize_upbit_market_buy_amount(amount: Decimal, quote_currency: str) -> Decimal:
    if quote_currency.upper() == "KRW":
        return amount.to_integral_value(rounding=ROUND_DOWN)
    return amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
