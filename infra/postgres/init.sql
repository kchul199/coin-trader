-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- JWT Blacklist table
CREATE TABLE jwt_blacklist (
    id SERIAL PRIMARY KEY,
    token VARCHAR(500) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jwt_blacklist_expires_at ON jwt_blacklist(expires_at);

-- Exchange Accounts table
CREATE TABLE exchange_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_id VARCHAR(50) NOT NULL,
    api_key VARCHAR(500) NOT NULL,
    api_secret VARCHAR(500) NOT NULL,
    is_testnet BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (exchange_id IN ('binance', 'kraken', 'coinbase', 'bybit'))
);

-- Balances table
CREATE TABLE balances (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange_account_id INTEGER NOT NULL REFERENCES exchange_accounts(id) ON DELETE CASCADE,
    asset VARCHAR(20) NOT NULL,
    free NUMERIC(20, 8) NOT NULL,
    locked NUMERIC(20, 8) NOT NULL,
    total NUMERIC(20, 8) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exchange_account_id, asset)
);

-- Strategies table
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    symbol VARCHAR(20) NOT NULL,
    base_currency VARCHAR(10) NOT NULL,
    quote_currency VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    ai_mode VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    max_position_size NUMERIC(20, 8),
    stop_loss_percent NUMERIC(5, 2),
    take_profit_percent NUMERIC(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (ai_mode IN ('disabled', 'suggestion', 'auto_execute')),
    CHECK (priority >= 1 AND priority <= 10)
);

CREATE INDEX idx_strategies_user_id ON strategies(user_id);
CREATE INDEX idx_strategies_is_active ON strategies(is_active);

-- Orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE SET NULL,
    exchange_order_id VARCHAR(255),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8),
    status VARCHAR(50) NOT NULL,
    filled_quantity NUMERIC(20, 8) DEFAULT 0,
    average_price NUMERIC(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (side IN ('buy', 'sell')),
    CHECK (status IN ('pending', 'open', 'partially_filled', 'filled', 'cancelled', 'rejected'))
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_strategy_id ON orders(strategy_id);
CREATE INDEX idx_orders_status ON orders(status);

-- AI Consultations table
CREATE TABLE ai_consultations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE SET NULL,
    symbol VARCHAR(20) NOT NULL,
    decision VARCHAR(50) NOT NULL,
    confidence NUMERIC(3, 2),
    reasoning TEXT,
    risk_level VARCHAR(20) NOT NULL,
    recommended_action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (decision IN ('buy', 'sell', 'hold')),
    CHECK (risk_level IN ('low', 'medium', 'high'))
);

CREATE INDEX idx_ai_consultations_user_id ON ai_consultations(user_id);
CREATE INDEX idx_ai_consultations_strategy_id ON ai_consultations(strategy_id);

-- Candles table (OHLCV data)
CREATE TABLE candles (
    exchange_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_time BIGINT NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (exchange_id, symbol, timeframe, open_time)
);

CREATE INDEX idx_candles_symbol_timeframe ON candles(symbol, timeframe);

-- Portfolio table
CREATE TABLE portfolio (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_value NUMERIC(20, 8) NOT NULL,
    total_cost NUMERIC(20, 8) NOT NULL,
    unrealized_pnl NUMERIC(20, 8),
    realized_pnl NUMERIC(20, 8),
    snapshot_date DATE NOT NULL,
    UNIQUE (user_id, snapshot_date)
);

-- Strategy Conflicts table
CREATE TABLE strategy_conflicts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id_1 INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    strategy_id_2 INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    conflict_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Emergency Stops table
CREATE TABLE emergency_stops (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(500) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- Backtest Results table
CREATE TABLE backtest_results (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital NUMERIC(20, 8) NOT NULL,
    final_capital NUMERIC(20, 8) NOT NULL,
    total_return NUMERIC(5, 2) NOT NULL,
    sharpe_ratio NUMERIC(5, 2),
    max_drawdown NUMERIC(5, 2),
    win_rate NUMERIC(5, 2),
    trades_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_backtest_results_strategy_id ON backtest_results(strategy_id);
