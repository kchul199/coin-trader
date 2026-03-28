"""
AIConsultant — Claude API 비동기 자문 파이프라인
블라인드 모드: 신호 방향 미포함으로 확증 편향 방지
Adaptive Thinking + JSON 구조화 출력 사용
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

VALID_DECISIONS = {"execute", "hold", "avoid"}
VALID_RISK_LEVELS = {"low", "medium", "high"}
CACHE_TTL = 300  # 5분

PROMPT_VERSION = 2


class AIConsultant:
    """
    Claude API를 통해 시장 상황 분석 및 거래 자문 제공.

    ai_mode:
        - off: AI 자문 없음
        - observe: 자문 결과를 기록만 하고 거래에 영향 없음
        - semi_auto: 자문 결과가 execute여도 사용자 승인 필요
        - auto: 자문 결과에 따라 자동 실행
    """

    def __init__(self, redis_client, settings):
        self.redis = redis_client
        self.settings = settings
        self.timeout = getattr(settings, "AI_CONSULT_TIMEOUT_SECONDS", 10)
        self._client = None  # lazy init

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(
                    api_key=self.settings.ANTHROPIC_API_KEY
                )
            except ImportError:
                logger.error("anthropic 패키지가 설치되어 있지 않습니다.")
                raise
        return self._client

    # ------------------------------------------------------------------ #
    # 캐시 조회
    # ------------------------------------------------------------------ #

    async def get_cached_advice(self, strategy_id: str) -> Optional[dict]:
        """Redis 캐시에서 최신 자문 결과 조회"""
        raw = await self.redis.get(f"ai:advice:{strategy_id}")
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    # ------------------------------------------------------------------ #
    # 자문 요청
    # ------------------------------------------------------------------ #

    async def refresh_advice(
        self,
        strategy: dict,
        market_ctx: dict,
    ) -> Optional[dict]:
        """
        Claude API 호출 → 검증 → Redis 캐시 저장 → 결과 반환

        Args:
            strategy: {id, name, symbol, timeframe, ai_mode, ...}
            market_ctx: {price, change_24h, indicators, recent_trades, ...}

        Returns:
            {decision, confidence, reason, risk_level, key_concerns, latency_ms}
            or None (타임아웃/오류 시 이전 캐시 반환)
        """
        t_start = time.monotonic()
        prompt = self._build_prompt(strategy, market_ctx)

        try:
            client = self._get_client()
            async with asyncio.timeout(self.timeout):
                response = await client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )
        except asyncio.TimeoutError:
            logger.warning(
                "AI 자문 타임아웃 (%ss): strategy_id=%s",
                self.timeout,
                strategy.get("id"),
            )
            return await self.get_cached_advice(str(strategy.get("id")))
        except Exception as exc:
            logger.error("AI 자문 API 오류: %s", exc)
            return await self.get_cached_advice(str(strategy.get("id")))

        latency_ms = int((time.monotonic() - t_start) * 1000)

        # 응답 텍스트 추출
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break

        # JSON 파싱
        result = self._parse_response(text)
        if result is None:
            logger.warning("AI 응답 파싱 실패: strategy_id=%s text=%s", strategy.get("id"), text[:200])
            return await self.get_cached_advice(str(strategy.get("id")))

        # 화이트리스트 검증 (구조화 출력이더라도 추가 방어)
        if result.get("decision") not in VALID_DECISIONS:
            logger.error(
                "AI 응답 오염 (decision): strategy_id=%s value=%s",
                strategy.get("id"), result.get("decision"),
            )
            return await self.get_cached_advice(str(strategy.get("id")))

        if result.get("risk_level") not in VALID_RISK_LEVELS:
            logger.error(
                "AI 응답 오염 (risk_level): strategy_id=%s value=%s",
                strategy.get("id"), result.get("risk_level"),
            )
            return await self.get_cached_advice(str(strategy.get("id")))

        result["latency_ms"] = latency_ms
        result["prompt_version"] = PROMPT_VERSION

        # Redis 캐시 저장
        await self.redis.setex(
            f"ai:advice:{strategy['id']}",
            CACHE_TTL,
            json.dumps(result, ensure_ascii=False),
        )

        logger.info(
            "AI 자문 완료: strategy_id=%s decision=%s confidence=%s latency=%dms",
            strategy.get("id"), result.get("decision"), result.get("confidence"), latency_ms,
        )
        return result

    # ------------------------------------------------------------------ #
    # 내부 유틸리티
    # ------------------------------------------------------------------ #

    def _parse_response(self, text: str) -> Optional[dict]:
        """응답 텍스트에서 JSON 추출"""
        text = text.strip()

        # 직접 JSON 시도
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # ```json ... ``` 블록 추출
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 첫 번째 { } 블록 추출
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _build_prompt(self, strategy: dict, ctx: dict) -> str:
        """
        Claude 프롬프트 생성.
        블라인드 모드: 신호 방향(매수/매도) 미포함 → 확증 편향 방지
        """
        indicators_str = json.dumps(
            ctx.get("indicators", {}),
            ensure_ascii=False,
            indent=2,
        )
        recent_trades_str = json.dumps(
            ctx.get("recent_trades", [])[:5],
            ensure_ascii=False,
            indent=2,
        )

        return f"""당신은 암호화폐 리스크 분석 전문가입니다.
아래 시장 데이터를 분석하고, 반드시 JSON 형식으로만 응답하세요.
다른 텍스트는 포함하지 마세요.

## 분석 대상
- 심볼: {ctx.get('symbol', 'UNKNOWN')}
- 현재가: {ctx.get('price', 'N/A')} {ctx.get('quote_currency', 'USDT')}
- 24시간 변동률: {ctx.get('change_24h', 'N/A')}%
- 거래량 (24h): {ctx.get('volume_24h', 'N/A')}

## 기술 지표 (현재)
{indicators_str}

## 최근 체결 내역 (최대 5건)
{recent_trades_str}

## 시장 컨텍스트
- BTC 도미넌스: {ctx.get('btc_dominance', 'N/A')}%
- 전체 시장 방향: {ctx.get('market_trend', 'N/A')}

현재 시장 상황에서 거래 실행 여부에 대한 의견을 순수하게 평가하세요.
신호 방향(매수/매도)은 제공하지 않습니다.

응답 형식 (JSON만):
{{
  "decision": "execute" | "hold" | "avoid",
  "confidence": 0-100 (정수),
  "reason": "판단 근거 (한국어, 2-3문장)",
  "risk_level": "low" | "medium" | "high",
  "key_concerns": ["우려사항1", "우려사항2"]
}}"""
