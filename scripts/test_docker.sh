#!/bin/bash
# ============================================================
# Coin Trader — Docker 기동 테스트 스크립트
# 사용법: cd infra && docker compose up -d && cd .. && bash scripts/test_docker.sh
# ============================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

passed=0
failed=0
warnings=0

check() {
    local label="$1"
    local result="$2"
    if [ "$result" = "0" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $label"
        ((passed++))
    else
        echo -e "  ${RED}[FAIL]${NC} $label"
        ((failed++))
    fi
}

warn() {
    local label="$1"
    echo -e "  ${YELLOW}[WARN]${NC} $label"
    ((warnings++))
}

echo ""
echo "========================================"
echo "  Coin Trader Docker 기동 테스트"
echo "========================================"
echo ""

# ── 1. 컨테이너 상태 확인 ──────────────────────────────────
echo "1) 컨테이너 상태"
for svc in postgres redis backend celery-worker celery-beat frontend; do
    status=$(cd infra && docker compose ps --format '{{.State}}' $svc 2>/dev/null || echo "missing")
    if [ "$status" = "running" ]; then
        check "$svc 컨테이너 running" 0
    else
        check "$svc 컨테이너 running (현재: $status)" 1
    fi
done
echo ""

# ── 2. PostgreSQL 연결 ─────────────────────────────────────
echo "2) PostgreSQL"
pg_result=$(docker exec $(cd infra && docker compose ps -q postgres) pg_isready -U cointrader 2>/dev/null && echo "ok" || echo "fail")
if [ "$pg_result" = "ok" ]; then
    check "PostgreSQL 연결" 0
else
    check "PostgreSQL 연결" 1
fi

table_count=$(docker exec $(cd infra && docker compose ps -q postgres) psql -U cointrader -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
if [ -n "$table_count" ] && [ "$table_count" -ge 10 ]; then
    check "테이블 생성 완료 (${table_count}개)" 0
else
    check "테이블 생성 (현재: ${table_count:-0}개, 최소 10개 필요)" 1
fi
echo ""

# ── 3. Redis 연결 ──────────────────────────────────────────
echo "3) Redis"
redis_ping=$(docker exec $(cd infra && docker compose ps -q redis) redis-cli ping 2>/dev/null || echo "fail")
if [ "$redis_ping" = "PONG" ]; then
    check "Redis PING/PONG" 0
else
    check "Redis PING/PONG" 1
fi
echo ""

# ── 4. Backend API ─────────────────────────────────────────
echo "4) Backend API"
health=$(curl -s -o /dev/null -w "%{http_code}" ${BACKEND_URL}/health 2>/dev/null || echo "000")
if [ "$health" = "200" ]; then
    check "GET /health → 200" 0
else
    check "GET /health → 200 (현재: $health)" 1
fi

docs=$(curl -s -o /dev/null -w "%{http_code}" ${BACKEND_URL}/docs 2>/dev/null || echo "000")
if [ "$docs" = "200" ]; then
    check "Swagger UI /docs → 200" 0
else
    check "Swagger UI /docs → 200 (현재: $docs)" 1
fi

# 회원가입 테스트
register_result=$(curl -s -X POST ${BACKEND_URL}/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPass123!"}' 2>/dev/null)
if echo "$register_result" | grep -q '"id"'; then
    check "POST /api/v1/auth/register → 성공" 0
elif echo "$register_result" | grep -q "already"; then
    check "POST /api/v1/auth/register → 이미 존재 (OK)" 0
else
    check "POST /api/v1/auth/register → 실패: $register_result" 1
fi

# 로그인 테스트
login_result=$(curl -s -X POST ${BACKEND_URL}/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPass123!"}' 2>/dev/null)
token=$(echo "$login_result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
if [ -n "$token" ] && [ "$token" != "" ]; then
    check "POST /api/v1/auth/login → JWT 토큰 발급" 0
else
    check "POST /api/v1/auth/login → 실패" 1
fi

# 인증 필요 API 테스트
if [ -n "$token" ]; then
    strategies=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $token" \
        ${BACKEND_URL}/api/v1/strategies 2>/dev/null || echo "000")
    if [ "$strategies" = "200" ]; then
        check "GET /api/v1/strategies (인증) → 200" 0
    else
        check "GET /api/v1/strategies (인증) → $strategies" 1
    fi

    portfolio=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $token" \
        ${BACKEND_URL}/api/v1/portfolio 2>/dev/null || echo "000")
    if [ "$portfolio" = "200" ]; then
        check "GET /api/v1/portfolio (인증) → 200" 0
    else
        check "GET /api/v1/portfolio (인증) → $portfolio" 1
    fi
fi
echo ""

# ── 5. Frontend ────────────────────────────────────────────
echo "5) Frontend"
fe_status=$(curl -s -o /dev/null -w "%{http_code}" ${FRONTEND_URL} 2>/dev/null || echo "000")
if [ "$fe_status" = "200" ]; then
    check "Frontend 접속 → 200" 0
else
    check "Frontend 접속 (현재: $fe_status)" 1
fi
echo ""

# ── 6. Celery Worker ──────────────────────────────────────
echo "6) Celery"
worker_log=$(cd infra && docker compose logs --tail=20 celery-worker 2>/dev/null || echo "")
if echo "$worker_log" | grep -q "ready"; then
    check "Celery Worker ready" 0
elif echo "$worker_log" | grep -q "connected"; then
    check "Celery Worker connected (ready 대기)" 0
else
    warn "Celery Worker 로그에서 ready 확인 안됨"
fi

beat_log=$(cd infra && docker compose logs --tail=20 celery-beat 2>/dev/null || echo "")
if echo "$beat_log" | grep -q "beat"; then
    check "Celery Beat 시작됨" 0
else
    warn "Celery Beat 로그 확인 필요"
fi
echo ""

# ── 7. WebSocket ───────────────────────────────────────────
echo "7) WebSocket (선택)"
ws_check=$(curl -s -o /dev/null -w "%{http_code}" --include \
    --no-buffer \
    -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Sec-WebSocket-Version: 13" \
    -H "Sec-WebSocket-Key: dGVzdA==" \
    ${BACKEND_URL}/ws 2>/dev/null || echo "000")
if [ "$ws_check" = "101" ]; then
    check "WebSocket Upgrade → 101" 0
else
    warn "WebSocket Upgrade → $ws_check (브라우저에서 테스트 권장)"
fi
echo ""

# ── 결과 요약 ──────────────────────────────────────────────
echo "========================================"
echo "  테스트 결과"
echo "========================================"
echo -e "  ${GREEN}PASS: ${passed}${NC}  ${RED}FAIL: ${failed}${NC}  ${YELLOW}WARN: ${warnings}${NC}"
echo ""

if [ "$failed" -eq 0 ]; then
    echo -e "  ${GREEN}모든 핵심 테스트 통과!${NC}"
    echo ""
    echo "  다음 단계:"
    echo "    - 브라우저에서 http://localhost:3000 접속"
    echo "    - 회원가입 후 로그인"
    echo "    - 전략 생성 및 백테스트 실행"
    echo ""
else
    echo -e "  ${RED}실패한 테스트가 있습니다.${NC}"
    echo ""
    echo "  디버깅 명령어:"
    echo "    cd infra && docker compose logs backend  # 백엔드 로그"
    echo "    cd infra && docker compose logs frontend  # 프론트엔드 로그"
    echo "    cd infra && docker compose logs postgres  # DB 로그"
    echo ""
fi

exit $failed
