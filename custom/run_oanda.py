#!/usr/bin/env python3
"""
OANDA Gateway 启动脚本

使用方法:
    python -m custom.run_oanda

或者直接运行:
    python custom/run_oanda.py
"""

import json
import sys
from pathlib import Path
from time import sleep

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.object import SubscribeRequest
from vnpy.trader.constant import Exchange

from custom.gateways.oanda import OandaGateway


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(__file__).parent / "config" / "oanda_config.json"

    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        print("请先创建配置文件，参考 custom/config/oanda_config.json.example")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """主函数"""
    print("=" * 50)
    print("OANDA Gateway for VeighNa")
    print("=" * 50)

    # 加载配置
    config = load_config()
    print(f"账户: {config['Account ID']}")
    print(f"服务器: {config['服务器']}")

    # 创建事件引擎和主引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 添加 OANDA Gateway
    main_engine.add_gateway(OandaGateway)
    print("Gateway 已添加")

    # 连接
    print("正在连接 OANDA...")
    main_engine.connect(config, "OANDA")

    # 等待连接完成
    sleep(2)

    # 订阅黄金行情
    print("订阅 XAU_USD 行情...")
    req = SubscribeRequest(symbol="XAU_USD", exchange=Exchange.OTC)
    main_engine.subscribe(req, "OANDA")

    print("\n连接成功! 按 Ctrl+C 退出")
    print("-" * 50)

    # 保持运行
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("\n正在关闭...")
        main_engine.close()
        print("已退出")


if __name__ == "__main__":
    main()
