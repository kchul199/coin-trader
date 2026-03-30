# Coin Trader — 로컬 구동 가이드

## 사전 준비

- Docker Desktop 및 Docker Compose v2
- Anthropic API 키 ([console.anthropic.com](https://console.anthropic.com/settings/keys))

## 1단계: 환경 변수 설정

```bash
# 프로젝트 루트에서
cp .env.example .env
```

`.env`를 열어 아래 값을 채워 주세요:

| 변수 | 설명 |
|------|------|
| `JWT_SECRET_KEY` | 32자 이상 랜덤 문자열 (`openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | Anthropic API 키 (`sk-ant-...`) |

나머지는 Docker Compose 내부 기본값이 적용됩니다.

## 2단계: Docker Compose 실행

```bash
cd infra
docker compose up --build -d
```

서비스 6개가 순서대로 구동됩니다:
- postgres (5432) → redis (6379) → backend (8000) → celery-worker → celery-beat → frontend (3000)

```bash
# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f backend
```

## 3단계: 캔들 데이터 시딩 (백테스트용)

최초 1회 실행하면 BTC/USDT, ETH/USDT의 90일치 OHLCV 데이터가 DB에 저장됩니다.

```bash
docker compose exec backend python -m scripts.seed_candles
```

옵션:
```bash
# 특정 심볼/타임프레임/기간
docker compose exec backend python -m scripts.seed_candles \
  --symbols "BTC/USDT,ETH/USDT" \
  --timeframes "1h,4h,1d" \
  --days 180
```

## 4단계: 접속

| 서비스 | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| PostgreSQL | localhost:5432 (cointrader/secret) |
| Redis | localhost:6379 |

## 4.5단계: 자동 기동 테스트 (선택)

모든 서비스가 정상인지 자동 확인:

```bash
# 프로젝트 루트에서
bash scripts/test_docker.sh
```

PostgreSQL 연결, 테이블 생성, Redis, Backend API (회원가입/로그인), Frontend 접속, Celery 상태를 한번에 점검합니다.

## 5단계: 최초 테스트 흐름

1. http://localhost:3000 접속 → 회원가입
2. Settings → Binance testnet API 키 등록
3. Strategies → 전략 생성 (RSI < 30 매수 등)
4. Dashboard → 실시간 가격 확인
5. Backtest → 전략 선택 → 기간 설정 → 실행
6. AI Advisor → 자문 조회

> **참고:** Binance API 키/Anthropic API 키 없이도 회원가입, 로그인, 전략 CRUD, UI 탐색은 정상 동작합니다. 거래 실행과 AI 어드바이저만 해당 키가 필요합니다.

## DB 초기화 (스키마 변경 시)

```bash
cd infra
docker compose down -v    # 볼륨 삭제 포함
docker compose up --build -d
```

`-v` 플래그가 pg_data 볼륨을 삭제하여 init.sql이 다시 실행됩니다.

## 트러블슈팅

**backend가 시작 직후 죽는 경우:**
```bash
docker compose logs backend
# → DATABASE_URL 또는 REDIS_URL 연결 에러 확인
```

**캔들 시딩이 실패하는 경우:**
```bash
# Binance 공개 API에 직접 접근이 차단된 환경에서는
# VPN이나 프록시 필요 (중국/일부 기업 네트워크)
```
