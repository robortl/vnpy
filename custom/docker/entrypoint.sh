#!/bin/bash
set -e

echo "=========================================="
echo "VeighNa + OANDA Gateway"
echo "=========================================="

# 如果有数据库配置，等待数据库就绪
if [ -n "$DATABASE_HOST" ]; then
    echo "等待 PostgreSQL 就绪..."
    while ! pg_isready -h $DATABASE_HOST -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-vnpy} 2>/dev/null; do
        sleep 1
    done
    echo "PostgreSQL 已就绪"
fi

# 如果有 Redis 配置，等待 Redis 就绪
if [ -n "$REDIS_HOST" ]; then
    echo "等待 Redis 就绪..."
    while ! redis-cli -h $REDIS_HOST -p ${REDIS_PORT:-6379} ping 2>/dev/null; do
        sleep 1
    done
    echo "Redis 已就绪"
fi

# 生成 OANDA 连接配置
if [ -n "$OANDA_TOKEN" ]; then
    echo "生成 OANDA 配置..."
    mkdir -p /app/custom/config
    cat > /app/custom/config/oanda_config.json << EOF
{
    "API Token": "${OANDA_TOKEN}",
    "Account ID": "${OANDA_ACCOUNT_ID}",
    "服务器": "${OANDA_SERVER:-Practice}",
    "代理地址": "",
    "代理端口": 0
}
EOF
    echo "OANDA 配置已生成"
fi

# 生成 VeighNa 设置
cat > /root/.vntrader/vt_setting.json << EOF
{
    "font.family": "Arial",
    "font.size": 12,
    "log.active": true,
    "log.level": 20,
    "log.console": true,
    "log.file": true,
    "database.timezone": "Asia/Tokyo"
}
EOF

echo "配置完成，启动应用..."
echo "=========================================="

# 执行传入的命令
exec "$@"
