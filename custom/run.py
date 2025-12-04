"""
VeighNa Trader - OANDA 版本

基于官方 examples/veighna_trader/run.py 修改
只需将 CtpGateway 替换为 OandaGateway
"""

import sys
from pathlib import Path

# [CUSTOM] 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# [/CUSTOM]

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

# [CUSTOM] 使用 OANDA Gateway 替代 CTP Gateway
from custom.gateways.oanda import OandaGateway
# [/CUSTOM]

from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctabacktester import CtaBacktesterApp
from vnpy_datamanager import DataManagerApp


def main():
    """"""
    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)

    # [CUSTOM] 添加 OANDA Gateway
    main_engine.add_gateway(OandaGateway)
    # [/CUSTOM]

    # 添加策略和数据管理模块
    main_engine.add_app(CtaStrategyApp)
    main_engine.add_app(CtaBacktesterApp)
    main_engine.add_app(DataManagerApp)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


if __name__ == "__main__":
    main()
