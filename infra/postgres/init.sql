-- ============================================================
-- Coin Trader — PostgreSQL 초기화 스크립트
-- ORM 모델(backend/app/models/) 기준으로 동기화됨
-- UUID 확장 활성화
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4()

-- ─── Users ───────────────────────────────────────────────────
CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             VARCHAR(255) NOT NULL UNIQUE,
    password_hash     VARCHAR(255) NOT NULL,
    totp_secret       VARCHAR(32),
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);

-- ─── JWT Blacklist ───────────────────────────────────────────
CREATE TABLE jwt_blacklist (
    jti               UUID PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason            VARCHAR(255),
    expires_at        TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jwt_blacklist_expires_at ON jwt_blacklist(expires_at);

-- ─── Exchange Accounts ───────────────────────────────────────
CREATE TABLE exchange_accounts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_id       VARCHAR(50) NOT NULL,
    api_key_encrypted BYTEA NOT NULL,
    api_secret_encrypted BYTEA NOT NULL,
    is_testnet        BOOLEAN NOT NULL DEFAULT TRUE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Balances ────────────────────────────────────────────────
CREATE TABLE balances (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_id       VARCHAR(50) NOT NULL,
    symbol            VARCHAR(20) NOT NULL,
    available         NUMERIC(20, 8) NOT NULL DEFAULT 0,
    locked            NUMERIC(20, 8) NOT NULL DEFAULT 0,
    synced_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_balance_user_exchange_symbol UNIQUE (user_id, exchange_id, symbol)
);

-- ─── Strategies ──────────────────────────────────────────────
CREATE TABLE strategies (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              VARCHAR(255) NOT NULL,
    symbol            VARCHAR(20) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    condition_tree    JSONB NOT NULL,
    order_config      JSONB NOT NULL,
    exit_condition    JSONB,
    ai_mode           VARCHAR(50) NOT NULL DEFAULT 'off',
    priority          SMALLINT NOT NULL DEFAULT 5,
    hold_retry_interval INTEGER NOT NULL DEFAULT 300,
    hold_max_retry    SMALLINT NOT NULL DEFAULT 3,
    is_active         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_strategies_user_id ON strategies(user_id);
CREATE INDEX idx_strategies_is_active ON strategies(is_active);

-- ─── Orders ──────────────────────────────────────────────────
CREATE TABLE orders (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    exchange_id       VARCHAR(50) NOT NULL,
    exchange_order_id VARCHAR(100) NOT NULL,
    symbol            VARCHAR(20) NOT NULL,
    side              VARCHAR(10) NOT NULL,
    order_type        VARCHAR(20) NOT NULL,
    price             NUMERIC(20, 8) NOT NULL,
    quantity          NUMERIC(20, 8) NOT NULL,
    filled_quantity   NUMERIC(20, 8) NOT NULL DEFAULT 0,
    avg_fill_price    NUMERIC(20, 8),
    fee               NUMERIC(20, 8),
    slippage_pct      NUMERIC(5, 2),
    status            VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    filled_at         TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_strategy_id ON orders(strategy_id);
CREATE INDEX idx_orders_status ON orders(status);

-- ─── AI Consultations ────────────────────────────────────────
CREATE TABLE ai_consultations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    order_id          UUID REFERENCES orders(id) ON DELETE SET NULL,
    model             VARCHAR(100) NOT NULL,
    prompt_version    VARCHAR(50) NOT NULL,
    decision          VARCHAR(100) NOT NULL,
    confidence        INTEGER NOT NULL,
    reason            VARCHAR(1000),
    risk_level        VARCHAR(50),
    key_concerns      JSONB,
    user_approved     BOOLEAN,
    latency_ms        INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_consultations_strategy_id ON ai_consultations(strategy_id);

-- ─── Candles (OHLCV) ────────────────────────────────────────
CREATE TABLE candles (
    symbol            VARCHAR(20) NOT NULL,
    exchange          VARCHAR(50) NOT NULL,
    timeframe         VARCHAR(10) NOT NULL,
    ts                TIMESTAMPTZ NOT NULL,
    open              NUMERIC(20, 8) NOT NULL,
    high              NUMERIC(20, 8) NOT NULL,
    low               NUMERIC(20, 8) NOT NULL,
    close             NUMERIC(20, 8) NOT NULL,
    volume            NUMERIC(20, 8) NOT NULL,
    PRIMARY KEY (symbol, exchange, timeframe, ts)
);

CREATE INDEX idx_candles_symbol_timeframe ON candles(symbol, timeframe);

-- ─── Portfolios ──────────────────────────────────────────────
CREATE TABLE portfolios (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol            VARCHAR(20) NOT NULL,
    exchange_id       VARCHAR(50) NOT NULL,
    quantity          NUMERIC(20, 8) NOT NULL,
    avg_buy_price     NUMERIC(20, 8) NOT NULL,
    initial_capital   NUMERIC(20, 8) NOT NULL,
    last_updated      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_portfolio_user_symbol_exchange UNIQUE (user_id, symbol, exchange_id)
);

-- ─── Strategy Conflicts ─────────────────────────────────────
CREATE TABLE strategy_conflicts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol            VARCHAR(20) NOT NULL,
    strategy_ids      JSONB NOT NULL,
    conflict_type     VARCHAR(100) NOT NULL,
    resolution        VARCHAR(100) NOT NULL,
    winner_strategy_id UUID,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Emergency Stops ─────────────────────────────────────────
CREATE TABLE emergency_stops (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID REFERENCES strategies(id) ON DELETE SET NULL,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason            VARCHAR(500) NOT NULL,
    cancelled_orders  JSONB NOT NULL DEFAULT '[]',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Backtest Results ────────────────────────────────────────
CREATE TABLE backtest_results (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    start_date        DATE NOT NULL,
    end_date          DATE NOT NULL,
    params_snapshot   JSONB NOT NULL,
    initial_capital   NUMERIC(20, 2) NOT NULL,
    final_capital     NUMERIC(20, 2) NOT NULL,
    total_return_pct  NUMERIC(10, 2) NOT NULL,
    max_drawdown_pct  NUMERIC(10, 2) NOT NULL,
    sharpe_ratio      NUMERIC(10, 4) NOT NULL,
    win_rate          NUMERIC(5, 2) NOT NULL,
    profit_factor     NUMERIC(10, 2) NOT NULL,
    total_trades      INTEGER NOT NULL,
    ai_on_return_pct  NUMERIC(10, 2),
    ai_off_return_pct NUMERIC(10, 2),
    commission_pct    NUMERIC(5, 2) NOT NULL,
    slippage_pct      NUMERIC(5, 2) NOT NULL,
    equity_curve      JSONB NOT NULL,
    trade_history     JSONB NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_backtest_results_strategy_id ON backtest_results(strategy_id);
