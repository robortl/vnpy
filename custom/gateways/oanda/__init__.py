"""
OANDA v20 Gateway for VeighNa

依赖: pip install oandapyV20

使用示例:
    from custom.gateways.oanda import OandaGateway
    main_engine.add_gateway(OandaGateway)
"""

from .oanda_gateway import OandaGateway

__all__ = ["OandaGateway"]
