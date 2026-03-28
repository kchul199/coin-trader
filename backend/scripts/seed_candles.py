"""
캔들 데이터 시딩 스크립트
- Binance 공개 API에서 과거 OHLCV 데이터를 가져와 PostgreSQL에 저장
- Docker 환경 내에서 실행:
    docker compose exec backend python -m scripts.seed_candles
  또는 로컬에서:
    cd backend && python -m scripts.seed_candles

옵션:
  --symbols BTC/USDT,ETH/USDT   대상 심볼 (기본: BTC/USDT, ETH/USDT)
  --timeframes 1h,4h,1d          대상 타임프레임 (기본: 1h, 4h, 1d)
  --days 90                       조회할 과거 일수 (기본: 90)
"""
import asyncio
import argparse
import sys
import os
from datetime import datetime, timezone, timedelta

# 프로젝트 루트를 path에 추가 (scripts 디렉토리에서 실행될 수 있도록)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def seed_candles(symbols: list[str], timeframes: list[str], days: int):
    import ccxt.async_support as ccxt
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.config import settings
    from app.database import AsyncSessionLocal, init_db
    from app.models.candle import Candle

    # DB 테이블 생성 보장
    await init_db()

    exchange = ccxt.binance({"enableRateLimit": True})

    # Binance 공개 API는 테스트넷이 아니라 실제 마켓 데이터 사용
    # (가격 데이터는 공개이므로 API 키 불필요)

    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    total_saved = 0

    try:
        for symbol in symbols:
            for timeframe in timeframes:
                print(f"  Fetching {symbol} / {timeframe} (last {days} days)...", flush=True)

                all_ohlcv = []
                fetch_since = since

                # 페이지네이션: 한 번에 최대 1000개 캔들
                while True:
                    try:
                        batch = await exchange.fetch_ohlcv(
                            symbol, timeframe, since=fetch_since, limit=1000
                        )
                    except Exception as e:
                        print(f"    Warning: {e}", flush=True)
                        break

                    if not batch:
                        break

                    all_ohlcv.extend(batch)
                    last_ts = batch[-1][0]

                    # 마지막 캔들 타임스탬프가 현재와 같으면 종료
                    if len(batch) < 1000:
                        break
                    fetch_since = last_ts + 1

                    # Rate limit 존중
                    await asyncio.sleep(0.1)

                if not all_ohlcv:
                    print(f"    No data for {symbol}/{timeframe}", flush=True)
                    continue

                # DB에 upsert (중복 무시)
                rows = []
                for candle in all_ohlcv:
                    ts = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
                    rows.append({
                        "symbol": symbol,
                        "exchange": settings.EXCHANGE_ID,
                        "timeframe": timeframe,
                        "ts": ts,
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5],
                    })

                # 500개씩 배치 삽입
                async with AsyncSessionLocal() as db:
                    for i in range(0, len(rows), 500):
                        batch_rows = rows[i : i + 500]
                        stmt = pg_insert(Candle).values(batch_rows)
                        stmt = stmt.on_conflict_do_nothing(
                            index_elements=["symbol", "exchange", "timeframe", "ts"]
                        )
                        await db.execute(stmt)
                    await db.commit()

                total_saved += len(rows)
                print(f"    Saved {len(rows)} candles for {symbol}/{timeframe}", flush=True)

    finally:
        await exchange.close()

    print(f"\nDone! Total candles saved: {total_saved}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Seed candle data from Binance")
    parser.add_argument(
        "--symbols",
        type=str,
        default="BTC/USDT,ETH/USDT",
        help="Comma-separated trading pairs (default: BTC/USDT,ETH/USDT)",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default="1h,4h,1d",
        help="Comma-separated timeframes (default: 1h,4h,1d)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of past days to fetch (default: 90)",
    )
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    timeframes = [t.strip() for t in args.timeframes.split(",")]

    print(f"Seeding candles: symbols={symbols}, timeframes={timeframes}, days={args.days}")
    asyncio.run(seed_candles(symbols, timeframes, args.days))


if __name__ == "__main__":
    main()
