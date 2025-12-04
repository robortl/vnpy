#!/usr/bin/env python3
"""
OANDA Gateway GUI 启动脚本

启动带图形界面的 VeighNa Trader
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

from custom.gateways.oanda import OandaGateway


def load_config() -> dict:
    """加载配置文件"""
    config_path = Path(__file__).parent / "config" / "oanda_config.json"

    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """主函数"""
    # 创建 Qt 应用
    qapp = create_qapp()

    # 创建事件引擎和主引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 添加 OANDA Gateway
    main_engine.add_gateway(OandaGateway)

    # 创建主窗口
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    # 自动连接 OANDA（可选）
    config = load_config()
    main_engine.connect(config, "OANDA")

    # 运行 Qt 事件循环
    qapp.exec()


if __name__ == "__main__":
    main()
