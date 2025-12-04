# VeighNa + OANDA Gateway Docker 镜像
# 适用于 Mac (ARM64/AMD64)

FROM python:3.11-slim

LABEL maintainer="vnpy-custom"
LABEL description="VeighNa Trading Platform with OANDA Gateway"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt /app/
COPY custom/requirements.txt /app/custom-requirements.txt

# 安装 Python 依赖
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -r custom-requirements.txt \
    && pip install psycopg2-binary redis

# 复制项目文件
COPY vnpy/ /app/vnpy/
COPY custom/ /app/custom/
COPY setup.py pyproject.toml /app/

# 安装 vnpy
RUN pip install -e .

# 创建配置目录
RUN mkdir -p /root/.vntrader

# 复制启动脚本
COPY custom/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 设置 Python 路径
ENV PYTHONPATH=/app

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "custom.run_oanda"]
