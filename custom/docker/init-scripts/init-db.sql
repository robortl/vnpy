-- VeighNa PostgreSQL 初始化脚本

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- K线数据表
CREATE TABLE IF NOT EXISTS bar_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    datetime TIMESTAMP NOT NULL,
    interval VARCHAR(10) NOT NULL,
    volume DOUBLE PRECISION DEFAULT 0,
    turnover DOUBLE PRECISION DEFAULT 0,
    open_interest DOUBLE PRECISION DEFAULT 0,
    open_price DOUBLE PRECISION NOT NULL,
    high_price DOUBLE PRECISION NOT NULL,
    low_price DOUBLE PRECISION NOT NULL,
    close_price DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, exchange, datetime, interval)
);

-- Tick数据表
CREATE TABLE IF NOT EXISTS tick_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    datetime TIMESTAMP NOT NULL,
    name VARCHAR(100),
    volume DOUBLE PRECISION DEFAULT 0,
    last_price DOUBLE PRECISION,
    bid_price_1 DOUBLE PRECISION,
    ask_price_1 DOUBLE PRECISION,
    bid_volume_1 DOUBLE PRECISION,
    ask_volume_1 DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, exchange, datetime)
);

-- 交易记录表
CREATE TABLE IF NOT EXISTS trade_data (
    id SERIAL PRIMARY KEY,
    tradeid VARCHAR(100) NOT NULL,
    orderid VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    offset_flag VARCHAR(20),
    price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    datetime TIMESTAMP NOT NULL,
    gateway_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tradeid, gateway_name)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_bar_symbol_datetime ON bar_data(symbol, exchange, interval, datetime);
CREATE INDEX IF NOT EXISTS idx_tick_symbol_datetime ON tick_data(symbol, exchange, datetime);
CREATE INDEX IF NOT EXISTS idx_trade_datetime ON trade_data(datetime);
CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trade_data(symbol, exchange);

-- 完成
SELECT 'Database initialized successfully' as status;
