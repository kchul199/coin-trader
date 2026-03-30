# Coin Trader

바이낸스 테스트넷 기반 비트코인 자동매매 솔루션입니다.
조건 트리 기반 전략 설정, AI 자문, 백테스트, 실시간 가격 모니터링을 지원합니다.

---

## 1. 개요

### 이 프로젝트는 무엇인가요?

Coin Trader는 비트코인을 자동으로 사고파는 웹 애플리케이션입니다.
사용자가 "RSI가 30 이하이면 매수해라" 같은 조건을 설정하면, 프로그램이 30초마다 시장을 확인하고 조건이 충족되면 자동으로 주문을 실행합니다.

현재는 바이낸스 테스트넷(가상 화폐로 연습하는 환경)에서 동작하며, 실제 돈이 들지 않으므로 안전하게 테스트할 수 있습니다.

### 주요 기능

- **전략 빌더** — 기술 지표(RSI, MACD, 볼린저밴드 등)를 조합한 조건 트리 방식의 매매 전략 생성
- **자동 매매 엔진** — 30초마다 전략 조건을 평가하고 자동으로 주문 실행
- **AI 자문** — Anthropic Claude AI가 매매 판단을 보조 (예: "지금 매수해도 될까요?")
- **백테스트** — 과거 데이터로 전략을 시뮬레이션하여 수익률, 최대낙폭 등 성과 확인
- **실시간 대시보드** — 비트코인 가격이 실시간으로 업데이트되는 차트 화면
- **리스크 관리** — 포지션 한도, 손실 방지, 위험 시 긴급 정지
- **2FA 인증** — 보안을 위한 2단계 인증 (Google Authenticator 등 사용)

### 기술 스택

| 구분 | 기술 | 역할 |
|------|------|------|
| Backend | Python 3.11, FastAPI | 서버 로직, API 제공 |
| Frontend | React 18, TypeScript | 사용자 화면 (웹 브라우저) |
| Database | PostgreSQL 16 | 전략, 주문, 사용자 데이터 저장 |
| Cache | Redis 7 | 실시간 가격 캐시, 백그라운드 작업 관리 |
| Exchange | CCXT | 바이낸스 거래소 연동 |
| AI | Anthropic Claude API | AI 매매 자문 |
| Infra | Docker Compose | 모든 서비스를 한 번에 실행 |

### 시스템 구성도

```
┌─────────────────────────────────────────────────────┐
│  사용자 (웹 브라우저)                                  │
│  http://localhost:3000                               │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  Frontend (React)                                    │
│  포트 3000 — 대시보드, 전략 설정, 백테스트 화면         │
└──────────────┬──────────────────────────────────────┘
               │ API 호출 (/api/v1/...)
┌──────────────▼──────────────────────────────────────┐
│  Backend (FastAPI)                                   │
│  포트 8000 — REST API + WebSocket 가격 피드           │
├──────────────┬─────────────────┬────────────────────┤
│  PostgreSQL  │  Redis          │  Celery Worker/Beat │
│  포트 5432   │  포트 6379      │  자동매매 스케줄러    │
│  데이터 저장  │  캐시/큐        │  30초 주기 전략 평가  │
└──────────────┴─────────────────┴────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│  바이낸스 거래소 (테스트넷)                             │
│  실시간 가격 수신 + 주문 실행                          │
└─────────────────────────────────────────────────────┘
```

### 프로젝트 폴더 구조

```
coin-trader/
├── backend/                 # 서버 프로그램 (Python)
│   ├── app/
│   │   ├── api/v1/          # API 엔드포인트 (회원가입, 전략, 주문 등)
│   │   ├── models/          # 데이터베이스 테이블 정의
│   │   ├── trading/         # 자동매매 핵심 로직
│   │   ├── exchange/        # 바이낸스 거래소 연동
│   │   ├── tasks/           # 백그라운드 작업 (30초 주기 매매 등)
│   │   ├── websocket/       # 실시간 가격 전송
│   │   ├── services/        # 백테스트 서비스
│   │   └── core/            # 보안, 인증, 암호화
│   ├── scripts/             # 데이터 초기화 스크립트
│   ├── requirements.txt     # Python 라이브러리 목록
│   └── Dockerfile           # Docker 빌드 설정
├── frontend/                # 웹 화면 (React)
│   ├── src/
│   │   ├── pages/           # 화면 9개 (대시보드, 전략, 백테스트 등)
│   │   ├── components/      # 재사용 가능한 UI 조각 (차트, 버튼 등)
│   │   ├── api/             # 서버와 통신하는 코드
│   │   ├── stores/          # 앱 상태 관리 (로그인 정보, 가격 등)
│   │   └── hooks/           # 실시간 데이터 연결
│   ├── package.json         # JavaScript 라이브러리 목록
│   └── Dockerfile           # Docker 빌드 설정
├── infra/                   # 인프라 설정
│   ├── docker-compose.yml   # 모든 서비스를 한 번에 실행하는 설정 파일
│   └── postgres/init.sql    # 데이터베이스 테이블 생성 SQL
├── scripts/
│   └── test_docker.sh       # 서비스 상태 자동 점검 스크립트
├── .env                     # 비밀 키 등 환경 변수 (Git에 올리지 않음)
└── .env.example             # .env 작성용 템플릿
```

### API 엔드포인트 목록

서버가 제공하는 주요 기능 목록입니다. 프론트엔드가 이 주소들을 호출하여 데이터를 주고받습니다.

| 경로 | 설명 |
|------|------|
| `POST /api/v1/auth/register` | 회원가입 |
| `POST /api/v1/auth/login` | 로그인 (JWT 토큰 발급) |
| `GET /api/v1/strategies` | 전략 목록 조회 |
| `POST /api/v1/strategies` | 새 전략 생성 |
| `GET /api/v1/portfolio` | 내 포트폴리오 조회 |
| `GET /api/v1/orders` | 주문 내역 조회 |
| `GET /api/v1/charts/candles` | 차트용 캔들 데이터 조회 |
| `POST /api/v1/backtest` | 백테스트 실행 |
| `POST /api/v1/ai-advisor/consult` | AI 자문 요청 |
| `POST /api/v1/emergency/stop` | 긴급 정지 |
| `GET /health` | 서버 상태 확인 |
| `WS /ws` | 실시간 가격 WebSocket |

서버 기동 후 http://localhost:8000/docs 에 접속하면 모든 API를 직접 테스트해볼 수 있는 Swagger UI 화면이 나옵니다.

---

## 2. 설치

### 2.1 사전 준비 — Docker Desktop 설치

이 프로젝트는 Docker를 사용합니다. Docker는 여러 프로그램(데이터베이스, 서버 등)을 한 번에 설치하고 실행할 수 있게 해주는 도구입니다. Python이나 Node.js를 직접 설치할 필요 없이, Docker만 있으면 됩니다.

**Windows 사용자:**

1. https://www.docker.com/products/docker-desktop/ 에 접속합니다.
2. "Download for Windows" 버튼을 클릭하여 설치 파일을 다운로드합니다.
3. 다운로드된 `Docker Desktop Installer.exe`를 더블클릭하여 설치합니다.
4. 설치 중 "Use WSL 2 instead of Hyper-V" 옵션이 나오면 체크한 채로 진행합니다.
5. 설치가 끝나면 컴퓨터를 재부팅합니다.
6. 재부팅 후 Docker Desktop이 자동으로 실행됩니다. 화면 하단 시스템 트레이에 고래 아이콘이 보이면 준비 완료입니다.

**Mac 사용자:**

1. https://www.docker.com/products/docker-desktop/ 에 접속합니다.
2. 본인의 Mac 칩에 맞는 버전을 다운로드합니다 (Apple Silicon / Intel).
3. 다운로드된 `.dmg` 파일을 열고, Docker 아이콘을 Applications 폴더로 드래그합니다.
4. Applications에서 Docker를 실행합니다.
5. 상단 메뉴바에 고래 아이콘이 나타나고 "Docker Desktop is running"이 표시되면 준비 완료입니다.

**설치 확인:**

터미널(Windows: PowerShell 또는 명령 프롬프트, Mac: 터미널)을 열고 아래 명령어를 입력합니다:

```bash
docker --version
```

`Docker version 27.x.x` 같은 버전 정보가 나오면 정상입니다.

```bash
docker compose version
```

`Docker Compose version v2.x.x` 같은 정보가 나오면 정상입니다.

### 2.2 사전 준비 — Git 설치

소스 코드를 다운로드하려면 Git이 필요합니다.

**Windows:** https://git-scm.com/download/win 에서 다운로드 후 설치합니다. 설치 옵션은 모두 기본값으로 진행하면 됩니다.

**Mac:** 터미널에서 `git --version`을 입력합니다. 설치되어 있지 않으면 자동으로 설치 안내가 나옵니다.

**설치 확인:**

```bash
git --version
```

`git version 2.x.x` 같은 정보가 나오면 정상입니다.

### 2.3 소스 코드 다운로드

터미널을 열고 원하는 폴더로 이동한 뒤 아래 명령어를 실행합니다:

```bash
# 소스 코드 다운로드
git clone https://github.com/kchul199/coin-trader.git

# 다운로드된 폴더로 이동
cd coin-trader
```

> **참고:** `cd coin-trader`는 "coin-trader 폴더 안으로 들어가기"라는 뜻입니다. 이후 모든 명령어는 이 폴더 안에서 실행합니다.

### 2.4 환경 변수 설정

환경 변수란 프로그램에 전달하는 비밀 설정값입니다 (비밀번호, API 키 등). `.env`라는 파일에 저장합니다.

**템플릿 복사:**

```bash
# Mac/Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

**`.env` 파일 편집:**

텍스트 편집기(메모장, VS Code 등)로 `.env` 파일을 열어 아래 값을 수정합니다.

```
# 반드시 변경해야 하는 항목
JWT_SECRET_KEY=여기에_랜덤_문자열_입력
```

JWT_SECRET_KEY는 로그인 보안에 사용되는 비밀 키입니다. 아래 명령어로 안전한 랜덤 키를 생성할 수 있습니다:

```bash
# Mac/Linux
openssl rand -hex 32

# Windows (PowerShell)
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
```

출력된 긴 문자열(예: `a3f8b2c1d4e5...`)을 복사하여 `JWT_SECRET_KEY=` 뒤에 붙여넣습니다.

**선택 항목 (나중에 설정해도 됨):**

| 변수 | 언제 필요한가? | 발급처 |
|------|---------------|--------|
| `ANTHROPIC_API_KEY` | AI 자문 기능 사용 시 | https://console.anthropic.com/settings/keys |
| `API_KEY` | 바이낸스에서 실제 거래 시 | https://testnet.binancefuture.com |
| `API_SECRET` | 바이낸스에서 실제 거래 시 | 위와 동일 |

> **처음 시작하는 분:** 위 선택 항목은 비워두셔도 됩니다. 회원가입, 로그인, 전략 만들기, 백테스트, UI 둘러보기는 이 키 없이도 모두 동작합니다. 나중에 실제 매매를 시도할 때 추가하면 됩니다.

---

## 3. 프로그램 실행

### 3.1 Docker Compose로 전체 서비스 시작

**Docker Desktop이 실행 중인지 확인**한 뒤 (시스템 트레이에 고래 아이콘), 터미널에서 아래 명령어를 순서대로 실행합니다:

```bash
# infra 폴더로 이동 (docker-compose.yml이 있는 곳)
cd infra

# 모든 서비스 빌드 및 백그라운드 실행
docker compose up --build -d
```

> **명령어 설명:**
> - `docker compose up` : docker-compose.yml에 정의된 모든 서비스를 시작합니다.
> - `--build` : 소스 코드가 변경되었을 때 이미지를 다시 빌드합니다. 최초 실행 시 반드시 필요합니다.
> - `-d` : 백그라운드에서 실행합니다 (터미널을 닫아도 계속 실행됨).

최초 실행 시에는 Python, Node.js 등의 이미지를 다운로드하므로 **3~10분** 정도 소요될 수 있습니다. 이후 실행부터는 훨씬 빠릅니다.

6개의 서비스가 아래 순서로 자동 시작됩니다:

```
1. postgres  (5432) — 데이터베이스
2. redis     (6379) — 캐시/메시지 큐
3. backend   (8000) — API 서버
4. celery-worker    — 백그라운드 매매 엔진
5. celery-beat      — 30초 주기 스케줄러
6. frontend  (3000) — 웹 화면
```

### 3.2 서비스 상태 확인

```bash
docker compose ps
```

아래와 비슷한 결과가 나오면 정상입니다. 모든 서비스의 State가 `running`이어야 합니다:

```
NAME              STATUS         PORTS
postgres          running        0.0.0.0:5432->5432/tcp
redis             running        0.0.0.0:6379->6379/tcp
backend           running        0.0.0.0:8000->8000/tcp
celery-worker     running
celery-beat       running
frontend          running        0.0.0.0:3000->3000/tcp
```

만약 어떤 서비스가 `exited`나 `restarting` 상태라면 로그를 확인합니다:

```bash
# 문제가 있는 서비스의 로그 확인 (예: backend)
docker compose logs backend

# 모든 서비스의 최근 로그 50줄 확인
docker compose logs --tail=50
```

### 3.3 웹 브라우저에서 접속

모든 서비스가 `running` 상태가 되면 웹 브라우저를 열고 아래 주소에 접속합니다:

| 서비스 | 주소 | 설명 |
|--------|------|------|
| **웹 화면** | http://localhost:3000 | 메인 화면 (여기서 시작) |
| API 서버 | http://localhost:8000 | 백엔드 서버 (직접 접속할 필요 없음) |
| API 문서 | http://localhost:8000/docs | API를 직접 테스트해볼 수 있는 화면 |
| 상태 확인 | http://localhost:8000/health | `{"status":"ok"}` 이 나오면 정상 |

### 3.4 캔들 데이터 시딩 (백테스트를 사용하려면 필요)

백테스트는 과거 가격 데이터가 있어야 실행할 수 있습니다. 아래 명령어로 바이낸스에서 90일치 가격 데이터를 가져옵니다:

```bash
# infra 폴더에서 실행
docker compose exec backend python -m scripts.seed_candles
```

> **명령어 설명:** `docker compose exec backend`는 "backend 컨테이너 안에서 명령어를 실행해라"라는 뜻입니다. 즉 backend 컨테이너 안에 있는 Python으로 `seed_candles` 스크립트를 실행합니다.

더 많은 데이터가 필요하면 옵션을 추가할 수 있습니다:

```bash
docker compose exec backend python -m scripts.seed_candles \
  --symbols "BTC/USDT,ETH/USDT" \
  --timeframes "1h,4h,1d" \
  --days 180
```

### 3.5 서비스 종료 및 재시작

```bash
# 모든 서비스 종료 (데이터는 유지됨)
cd infra
docker compose down

# 다시 시작할 때 (이미 빌드된 상태이므로 --build 생략 가능)
docker compose up -d

# 소스 코드를 수정한 후 다시 시작할 때
docker compose up --build -d
```

**데이터를 완전히 초기화하고 싶을 때** (회원 정보, 전략, 주문 내역 등 모두 삭제):

```bash
cd infra
docker compose down -v          # -v 옵션이 데이터베이스 볼륨까지 삭제
docker compose up --build -d    # 처음부터 다시 시작
```

---

## 4. 테스트

### 4.1 자동 기동 테스트 (권장)

서비스가 실행 중인 상태에서, 프로젝트 루트 폴더로 이동하여 테스트 스크립트를 실행합니다:

```bash
# infra 폴더에 있다면 상위 폴더로 이동
cd ..

# 테스트 스크립트 실행
bash scripts/test_docker.sh
```

> **Windows 사용자:** Git Bash에서 실행하거나, WSL 터미널에서 실행하세요. PowerShell에서는 bash 스크립트가 직접 실행되지 않습니다.

이 스크립트는 아래 항목을 자동으로 점검하고 PASS/FAIL로 결과를 보여줍니다:

1. 6개 컨테이너가 모두 running 상태인지
2. PostgreSQL에 연결이 되는지, 테이블이 제대로 생성되었는지
3. Redis가 응답하는지
4. Backend API의 헬스 체크와 Swagger UI가 동작하는지
5. 회원가입 → 로그인 → JWT 토큰 발급이 정상인지
6. 토큰을 사용한 인증 API (전략 목록, 포트폴리오)가 동작하는지
7. Frontend 페이지가 접속 가능한지
8. Celery Worker와 Beat가 시작되었는지

모든 항목이 `[PASS]`로 나오면 시스템이 정상 동작하는 것입니다.

### 4.2 수동 테스트 — 웹 화면에서 따라하기

#### Step 1: 회원가입

1. 브라우저에서 http://localhost:3000 에 접속합니다.
2. 회원가입 페이지에서 이메일과 비밀번호를 입력합니다.
3. 가입 완료 후 로그인합니다.

#### Step 2: 전략 생성

1. 좌측 메뉴에서 **Strategies** 를 클릭합니다.
2. "새 전략" 버튼을 클릭합니다.
3. 전략 이름, 심볼(BTC/USDT), 타임프레임(1h), 조건(예: RSI < 30이면 매수)을 설정합니다.
4. 저장합니다.

#### Step 3: 백테스트 실행

1. 좌측 메뉴에서 **Backtest** 를 클릭합니다.
2. 방금 만든 전략을 선택합니다.
3. 기간과 초기 자본금을 설정합니다.
4. "실행" 버튼을 누르면 과거 데이터로 시뮬레이션 결과가 나옵니다.

> **주의:** 캔들 데이터 시딩(3.4단계)을 먼저 해야 백테스트가 동작합니다.

#### Step 4: 대시보드 확인

1. 좌측 메뉴에서 **Dashboard** 를 클릭합니다.
2. BTC/USDT, ETH/USDT 가격이 실시간으로 업데이트되는지 확인합니다.

#### Step 5: AI 자문 (선택)

1. 좌측 메뉴에서 **AI Advisor** 를 클릭합니다.
2. 자문을 요청하면 AI가 현재 시장 상황에 대한 분석을 제공합니다.

> **참고:** 이 기능은 `.env`에 `ANTHROPIC_API_KEY`가 설정되어 있어야 동작합니다.

### 4.3 API 직접 테스트 (터미널에서)

Swagger UI (http://localhost:8000/docs) 에서 클릭으로 테스트할 수도 있고, 아래처럼 터미널에서 직접 호출할 수도 있습니다:

```bash
# 1. 서버가 살아있는지 확인
curl http://localhost:8000/health
# 기대 결과: {"status":"ok","service":"coin-trader-api"}
```

```bash
# 2. 회원가입
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'
# 기대 결과: {"id":"...", "email":"test@example.com", ...}
```

```bash
# 3. 로그인 (토큰 발급)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'
# 기대 결과: {"access_token":"eyJhbG...", "token_type":"bearer"}
```

```bash
# 4. 전략 목록 조회 (위에서 받은 access_token 값으로 교체)
curl -H "Authorization: Bearer eyJhbG..." \
  http://localhost:8000/api/v1/strategies
# 기대 결과: [] (아직 전략을 안 만들었으므로 빈 배열)
```

> **Windows PowerShell 사용자:** `curl` 대신 `Invoke-RestMethod`를 사용하거나, Swagger UI(http://localhost:8000/docs)에서 직접 테스트하는 것을 권장합니다.

---

## 5. 트러블슈팅

### "docker compose" 명령어가 안 될 때

Docker Desktop이 실행 중인지 확인하세요 (시스템 트레이에 고래 아이콘). Docker Desktop을 시작한 후 잠시 기다렸다가 다시 시도합니다.

### backend가 시작 직후 종료될 때

```bash
cd infra
docker compose logs backend
```

로그에서 에러 메시지를 확인합니다. 주요 원인과 해결 방법은 아래와 같습니다.

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| `Connection refused...5432` | PostgreSQL이 아직 준비 안 됨 | `docker compose restart backend` |
| `Connection refused...6379` | Redis가 아직 준비 안 됨 | `docker compose restart backend` |
| `ModuleNotFoundError` | 새 라이브러리 미설치 | `docker compose up --build -d` |

### frontend가 빈 화면일 때

```bash
cd infra
docker compose logs frontend
```

`npm install` 관련 에러가 있다면:

```bash
docker compose down
docker compose up --build -d
```

### 캔들 시딩이 실패할 때

바이낸스 공개 API 접근이 차단된 네트워크(일부 기업망, 중국 등)에서는 VPN이 필요합니다.

### DB 스키마를 변경한 후 반영이 안 될 때

`init.sql`은 PostgreSQL 볼륨이 처음 생성될 때만 실행됩니다. 스키마를 변경했다면 볼륨을 삭제 후 재생성해야 합니다:

```bash
cd infra
docker compose down -v          # 볼륨(데이터) 삭제
docker compose up --build -d    # 처음부터 다시 시작
```

### 포트 충돌 (Address already in use)

다른 프로그램이 같은 포트를 사용 중일 수 있습니다:

```bash
# 어떤 프로그램이 포트를 사용 중인지 확인 (예: 8000번)
# Mac/Linux
lsof -i :8000

# Windows (PowerShell)
netstat -ano | findstr :8000
```

해당 프로그램을 종료하거나, `docker-compose.yml`에서 포트 번호를 변경합니다.

---

## 6. 로드맵

- [x] Phase 1 — 기반 스캐폴딩 (FastAPI + React + Docker)
- [x] Phase 2 — 차트 & 전략 CRUD
- [x] Phase 3 — 매매 엔진 + AI 자문
- [x] Phase 4 — 백테스트 엔진
- [ ] Phase 5 — 실거래 전환 (테스트넷 → 라이브)
- [ ] Phase 6 — 업비트 KRW 마켓 지원
