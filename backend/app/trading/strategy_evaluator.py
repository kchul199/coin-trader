from dataclasses import dataclass, field
from typing import Any
import pandas as pd

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


@dataclass
class ConditionResult:
    matched: bool
    triggered: list[str] = field(default_factory=list)


class StrategyEvaluator:
    SUPPORTED_INDICATORS = {"RSI", "MACD", "BB", "MA", "EMA", "STOCH", "CCI", "VOLUME"}

    def evaluate(self, condition_tree: dict, ohlcv: pd.DataFrame) -> ConditionResult:
        """condition_tree를 ohlcv 데이터로 평가"""
        if ohlcv is None or ohlcv.empty:
            return ConditionResult(matched=False)
        indicators = self._compute_indicators(condition_tree, ohlcv)
        return self._eval_tree(condition_tree, indicators)

    def _eval_tree(self, node: dict, indicators: dict) -> ConditionResult:
        if not node:
            return ConditionResult(matched=False)

        op = node.get("operator", "")

        if op in ("AND", "OR"):
            # 논리 연산자 노드
            children = node.get("conditions", [])
            results = [self._eval_tree(c, indicators) for c in children]

            if op == "AND":
                matched = all(r.matched for r in results)
            else:
                matched = any(r.matched for r in results)

            triggered = [t for r in results for t in r.triggered if r.matched]
            return ConditionResult(matched=matched, triggered=triggered)
        else:
            # 리프 조건 노드
            return self._eval_leaf(node, indicators)

    def _eval_leaf(self, cond: dict, indicators: dict) -> ConditionResult:
        indicator = cond.get("indicator", "")
        params = cond.get("params", {})
        tf = params.get("timeframe", "1h")
        op = cond.get("operator", "")
        threshold = cond.get("value")
        compare_to = cond.get("compare_to")

        key = f"{indicator}_{tf}"
        value = indicators.get(key)

        if value is None:
            return ConditionResult(matched=False)

        close = indicators.get("CLOSE", 0)

        try:
            ops = {
                "lt": lambda v, t: float(v) < float(t),
                "gt": lambda v, t: float(v) > float(t),
                "lte": lambda v, t: float(v) <= float(t),
                "gte": lambda v, t: float(v) >= float(t),
                "eq": lambda v, t: abs(float(v) - float(t)) < 0.0001,
                "gt_multiple": lambda v, t: float(v) > float(indicators.get(compare_to, 0)) * float(t),
                "price_below_lower": lambda v, t: float(close) < float(v.get("lower", 0)) if isinstance(v, dict) else False,
                "price_above_upper": lambda v, t: float(close) > float(v.get("upper", 0)) if isinstance(v, dict) else False,
                "price_above_mid": lambda v, t: float(close) > float(v.get("mid", 0)) if isinstance(v, dict) else False,
                "price_below_mid": lambda v, t: float(close) < float(v.get("mid", 0)) if isinstance(v, dict) else False,
                "golden_cross": lambda v, t: v.get("cross") == "golden" if isinstance(v, dict) else False,
                "dead_cross": lambda v, t: v.get("cross") == "dead" if isinstance(v, dict) else False,
            }

            fn = ops.get(op)
            if fn is None:
                return ConditionResult(matched=False)

            matched = fn(value, threshold)
        except (TypeError, ValueError):
            return ConditionResult(matched=False)

        label = f"{indicator}({tf}) {op} {threshold}"
        return ConditionResult(matched=matched, triggered=[label] if matched else [])

    def _compute_indicators(self, tree: dict, ohlcv: pd.DataFrame) -> dict:
        """조건 트리에서 필요한 지표만 계산"""
        needed = self._extract_needed_indicators(tree)
        close = ohlcv["close"]
        volume = ohlcv["volume"]

        result = {
            "CLOSE": float(close.iloc[-1]),
            "OPEN": float(ohlcv["open"].iloc[-1]),
            "HIGH": float(ohlcv["high"].iloc[-1]),
            "LOW": float(ohlcv["low"].iloc[-1]),
            "VOLUME_raw": float(volume.iloc[-1]),
        }

        if not TA_AVAILABLE:
            return result

        for ind, params in needed.items():
            tf = params.get("timeframe", "1h")
            try:
                if ind == "RSI":
                    period = params.get("period", 14)
                    rsi = ta.momentum.RSIIndicator(close, window=period)
                    result[f"RSI_{tf}"] = float(rsi.rsi().iloc[-1])

                elif ind == "MACD":
                    macd_ind = ta.trend.MACD(close)
                    diff_series = macd_ind.macd_diff()
                    prev_diff = float(diff_series.iloc[-2])
                    curr_diff = float(diff_series.iloc[-1])

                    if prev_diff < 0 and curr_diff >= 0:
                        cross = "golden"
                    elif prev_diff > 0 and curr_diff <= 0:
                        cross = "dead"
                    else:
                        cross = "none"

                    result[f"MACD_{tf}"] = {
                        "diff": curr_diff,
                        "macd": float(macd_ind.macd().iloc[-1]),
                        "signal": float(macd_ind.macd_signal().iloc[-1]),
                        "cross": cross,
                    }

                elif ind == "BB":
                    period = params.get("period", 20)
                    std = params.get("std", 2)
                    bb = ta.volatility.BollingerBands(close, window=period, window_dev=std)
                    result[f"BB_{tf}"] = {
                        "upper": float(bb.bollinger_hband().iloc[-1]),
                        "lower": float(bb.bollinger_lband().iloc[-1]),
                        "mid": float(bb.bollinger_mavg().iloc[-1]),
                    }

                elif ind == "MA":
                    period = params.get("period", 20)
                    result[f"MA_{tf}"] = float(close.rolling(window=period).mean().iloc[-1])

                elif ind == "EMA":
                    period = params.get("period", 20)
                    result[f"EMA_{tf}"] = float(close.ewm(span=period).mean().iloc[-1])

                elif ind == "STOCH":
                    stoch = ta.momentum.StochasticOscillator(
                        ohlcv["high"], ohlcv["low"], close,
                        window=params.get("k_period", 14),
                        smooth_window=params.get("d_period", 3),
                    )
                    result[f"STOCH_{tf}"] = float(stoch.stoch().iloc[-1])

                elif ind == "CCI":
                    period = params.get("period", 20)
                    cci = ta.trend.CCIIndicator(ohlcv["high"], ohlcv["low"], close, window=period)
                    result[f"CCI_{tf}"] = float(cci.cci().iloc[-1])

                elif ind == "VOLUME":
                    result[f"VOLUME_{tf}"] = float(volume.iloc[-1])
                    result["volume_ma_20"] = float(volume.rolling(20).mean().iloc[-1])

            except Exception:
                pass  # 지표 계산 실패 시 스킵

        return result

    def _extract_needed_indicators(self, node: dict, acc: dict = None) -> dict:
        if acc is None:
            acc = {}
        if not node:
            return acc
        if "conditions" in node:
            for c in node["conditions"]:
                self._extract_needed_indicators(c, acc)
        elif "indicator" in node:
            key = node["indicator"]
            if key not in acc:
                acc[key] = node.get("params", {})
        return acc
