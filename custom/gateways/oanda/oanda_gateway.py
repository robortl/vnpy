"""
OANDA v20 Gateway for VeighNa
基于 oandapyV20 库封装
安装依赖: pip install oandapyV20
"""

from datetime import datetime
from threading import Thread
from typing import Optional

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData, OrderData, TradeData, PositionData, AccountData,
    ContractData, OrderRequest, CancelRequest, SubscribeRequest,
    HistoryRequest, BarData
)
from vnpy.trader.constant import (
    Exchange, Product, Direction, OrderType, Status, Interval
)
from vnpy.event import EventEngine

# 使用成熟的第三方库
from oandapyV20 import API
from oandapyV20.exceptions import V20Error
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.pricing as pricing


class OandaGateway(BaseGateway):
    """
    OANDA v20 API Gateway

    基于 oandapyV20 库实现，该库已经封装了：
    - REST API 完整支持
    - Streaming API 支持
    - 错误处理和重试机制
    """

    default_name: str = "OANDA"

    default_setting: dict = {
        "API Token": "",
        "Account ID": "",
        "服务器": ["Practice", "Live"],
        "代理地址": "",
        "代理端口": 0,
    }

    exchanges: list = [Exchange.OTC]

    def __init__(self, event_engine: EventEngine, gateway_name: str = "OANDA"):
        super().__init__(event_engine, gateway_name)

        self.api: Optional[API] = None
        self.account_id: str = ""
        self.stream_api: Optional["OandaStreamApi"] = None

        self.orders: dict[str, OrderData] = {}
        self.order_count: int = 0

    def connect(self, setting: dict) -> None:
        """连接OANDA服务器"""
        token = setting["API Token"]
        self.account_id = setting["Account ID"]
        server = setting["服务器"]

        # oandapyV20 自动处理服务器地址
        environment = "practice" if server == "Practice" else "live"

        # 创建 API 客户端（oandapyV20 核心类）
        self.api = API(access_token=token, environment=environment)

        # 创建流式 API
        self.stream_api = OandaStreamApi(self, token, self.account_id, environment)

        # 初始化查询
        self.query_contracts()
        self.query_account()
        self.query_position()

        self.write_log(f"OANDA Gateway 连接成功 [{environment}]")

    def query_contracts(self) -> None:
        """查询合约信息 - 使用 oandapyV20"""
        try:
            r = accounts.AccountInstruments(accountID=self.account_id)
            response = self.api.request(r)

            for inst in response.get("instruments", []):
                # 只处理黄金相关品种
                if not inst["name"].startswith("XAU"):
                    continue

                contract = ContractData(
                    symbol=inst["name"],
                    exchange=Exchange.OTC,
                    name=inst["displayName"],
                    product=Product.FOREX,
                    size=1,
                    pricetick=10 ** int(inst["pipLocation"]),
                    min_volume=float(inst["minimumTradeSize"]),
                    history_data=True,
                    net_position=True,
                    gateway_name=self.gateway_name
                )
                self.on_contract(contract)

            self.write_log("合约查询成功")

        except V20Error as e:
            self.write_log(f"查询合约失败: {e}")

    def query_account(self) -> None:
        """查询账户 - 使用 oandapyV20"""
        try:
            r = accounts.AccountSummary(accountID=self.account_id)
            response = self.api.request(r)
            account_info = response.get("account", {})

            account = AccountData(
                accountid=self.account_id,
                balance=float(account_info.get("balance", 0)),
                frozen=float(account_info.get("marginUsed", 0)),
                gateway_name=self.gateway_name
            )
            self.on_account(account)

            self.write_log("账户查询成功")

        except V20Error as e:
            self.write_log(f"查询账户失败: {e}")

    def query_position(self) -> None:
        """查询持仓 - 使用 oandapyV20"""
        try:
            r = positions.OpenPositions(accountID=self.account_id)
            response = self.api.request(r)

            for pos in response.get("positions", []):
                instrument = pos["instrument"]

                # 多头
                long_units = float(pos["long"]["units"])
                if long_units != 0:
                    position = PositionData(
                        symbol=instrument,
                        exchange=Exchange.OTC,
                        direction=Direction.LONG,
                        volume=abs(long_units),
                        price=float(pos["long"].get("averagePrice", 0)),
                        pnl=float(pos["long"].get("unrealizedPL", 0)),
                        gateway_name=self.gateway_name
                    )
                    self.on_position(position)

                # 空头
                short_units = float(pos["short"]["units"])
                if short_units != 0:
                    position = PositionData(
                        symbol=instrument,
                        exchange=Exchange.OTC,
                        direction=Direction.SHORT,
                        volume=abs(short_units),
                        price=float(pos["short"].get("averagePrice", 0)),
                        pnl=float(pos["short"].get("unrealizedPL", 0)),
                        gateway_name=self.gateway_name
                    )
                    self.on_position(position)

            self.write_log("持仓查询成功")

        except V20Error as e:
            self.write_log(f"查询持仓失败: {e}")

    def send_order(self, req: OrderRequest) -> str:
        """发送委托 - 使用 oandapyV20"""
        self.order_count += 1
        orderid = f"OANDA_{self.order_count}"

        units = int(req.volume) if req.direction == Direction.LONG else -int(req.volume)

        # 构建订单数据
        order_data = {
            "order": {
                "instrument": req.symbol,
                "units": str(units),
                "type": "MARKET" if req.type == OrderType.MARKET else "LIMIT",
                "timeInForce": "FOK" if req.type == OrderType.MARKET else "GTC",
            }
        }

        if req.type == OrderType.LIMIT:
            order_data["order"]["price"] = str(req.price)

        try:
            r = orders.OrderCreate(accountID=self.account_id, data=order_data)
            response = self.api.request(r)

            order = req.create_order_data(orderid, self.gateway_name)

            if "orderFillTransaction" in response:
                order.status = Status.ALLTRADED
                order.traded = req.volume

                # 生成成交记录
                fill = response["orderFillTransaction"]
                trade = TradeData(
                    symbol=req.symbol,
                    exchange=Exchange.OTC,
                    orderid=orderid,
                    tradeid=fill.get("id", orderid),
                    direction=req.direction,
                    price=float(fill.get("price", req.price)),
                    volume=req.volume,
                    datetime=datetime.now(),
                    gateway_name=self.gateway_name
                )
                self.on_trade(trade)

            elif "orderCreateTransaction" in response:
                order.status = Status.NOTTRADED
            else:
                order.status = Status.REJECTED

            self.on_order(order)
            self.orders[orderid] = order

            return order.vt_orderid

        except V20Error as e:
            self.write_log(f"下单失败: {e}")
            order = req.create_order_data(orderid, self.gateway_name)
            order.status = Status.REJECTED
            self.on_order(order)
            return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销委托"""
        try:
            r = orders.OrderCancel(accountID=self.account_id, orderID=req.orderid)
            self.api.request(r)
            self.write_log(f"撤单成功: {req.orderid}")
        except V20Error as e:
            self.write_log(f"撤单失败: {e}")

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        if self.stream_api:
            self.stream_api.subscribe(req.symbol)

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """查询历史K线 - 使用 oandapyV20，支持分批下载"""
        from datetime import timedelta

        bars = []

        # VeighNa 原生支持的周期
        granularity_map = {
            Interval.MINUTE: "M1",
            Interval.HOUR: "H1",
            Interval.DAILY: "D",
            Interval.WEEKLY: "W",
        }
        granularity = granularity_map.get(req.interval, "M1")

        # 每个周期对应的时间增量（用于分批）
        interval_delta = {
            Interval.MINUTE: timedelta(minutes=1),
            Interval.HOUR: timedelta(hours=1),
            Interval.DAILY: timedelta(days=1),
            Interval.WEEKLY: timedelta(weeks=1),
        }
        delta = interval_delta.get(req.interval, timedelta(minutes=1))

        # 处理时区
        start_time = req.start.replace(tzinfo=None) if req.start.tzinfo else req.start
        end_time = req.end.replace(tzinfo=None) if (req.end and req.end.tzinfo) else (req.end or datetime.now())

        self.write_log(f"下载历史数据: {req.symbol} {granularity}")

        # OANDA 每次最多返回 5000 条，使用 count 参数分批获取
        batch_size = 5000
        current_start = start_time

        while current_start < end_time:
            start_str = current_start.strftime("%Y-%m-%dT%H:%M:%SZ")

            params = {
                "granularity": granularity,
                "from": start_str,
                "price": "M",
                "count": batch_size,
            }

            try:
                r = instruments.InstrumentsCandles(instrument=req.symbol, params=params)
                response = self.api.request(r)

                candles = response.get("candles", [])
                if not candles:
                    break

                last_bar_time = None
                for candle in candles:
                    if not candle.get("complete"):
                        continue

                    mid = candle["mid"]
                    bar_time = datetime.fromisoformat(candle["time"].replace("Z", "+00:00"))

                    # 检查是否超过结束时间
                    bar_time_naive = bar_time.replace(tzinfo=None)
                    if bar_time_naive > end_time:
                        break

                    bar = BarData(
                        symbol=req.symbol,
                        exchange=Exchange.OTC,
                        datetime=bar_time,
                        interval=req.interval,
                        open_price=float(mid["o"]),
                        high_price=float(mid["h"]),
                        low_price=float(mid["l"]),
                        close_price=float(mid["c"]),
                        volume=float(candle["volume"]),
                        gateway_name=self.gateway_name
                    )
                    bars.append(bar)
                    last_bar_time = bar_time_naive

                # 更新下一批起始时间
                if last_bar_time:
                    current_start = last_bar_time + delta
                else:
                    break

                # 如果返回数据少于请求数量，说明已到末尾
                if len(candles) < batch_size:
                    break

                self.write_log(f"已下载 {len(bars)} 条...")

            except V20Error as e:
                error_msg = str(e).replace('{', '{{').replace('}', '}}')
                self.write_log(f"查询历史数据失败: {error_msg}")
                break

            except Exception as e:
                self.write_log(f"下载历史数据异常: {str(e)[:200]}")
                break

        self.write_log(f"历史数据下载完成，共 {len(bars)} 条")
        return bars

    def close(self) -> None:
        """关闭连接"""
        if self.stream_api:
            self.stream_api.stop()
        self.write_log("OANDA Gateway 已关闭")


class OandaStreamApi:
    """
    OANDA 流式行情 API

    使用 oandapyV20 的 PricingStream 端点
    """

    def __init__(self, gateway: OandaGateway, token: str, account_id: str, environment: str):
        self.gateway = gateway
        self.token = token
        self.account_id = account_id
        self.environment = environment

        self.api = API(access_token=token, environment=environment)
        self.subscribed: set[str] = set()
        self.thread: Optional[Thread] = None
        self.active: bool = False

    def subscribe(self, symbol: str) -> None:
        """订阅行情"""
        self.subscribed.add(symbol)

        # 重新启动流（oandapyV20 需要重启来更新订阅列表）
        if self.active:
            self.stop()

        self.active = True
        self.thread = Thread(target=self._run_stream, daemon=True)
        self.thread.start()
        self.gateway.write_log(f"订阅行情: {symbol}")

    def _run_stream(self) -> None:
        """运行流式数据接收 - 使用 oandapyV20"""
        if not self.subscribed:
            return

        instruments_str = ",".join(self.subscribed)

        params = {"instruments": instruments_str}
        r = pricing.PricingStream(accountID=self.account_id, params=params)

        try:
            # oandapyV20 的流式请求是一个生成器
            for response in self.api.request(r):
                if not self.active:
                    break

                if response.get("type") == "PRICE":
                    self._process_tick(response)
                elif response.get("type") == "HEARTBEAT":
                    # 心跳包，忽略
                    pass

        except V20Error as e:
            self.gateway.write_log(f"行情流错误: {e}")
        except Exception as e:
            self.gateway.write_log(f"行情流断开: {e}")

        # 自动重连
        if self.active:
            self.gateway.write_log("行情流断开，尝试重连...")
            self._run_stream()

    def _process_tick(self, data: dict) -> None:
        """处理Tick数据"""
        bids = data.get("bids", [])
        asks = data.get("asks", [])

        tick = TickData(
            symbol=data["instrument"],
            exchange=Exchange.OTC,
            datetime=datetime.fromisoformat(data["time"].replace("Z", "+00:00")),
            bid_price_1=float(bids[0]["price"]) if bids else 0,
            ask_price_1=float(asks[0]["price"]) if asks else 0,
            bid_volume_1=float(bids[0].get("liquidity", 0)) if bids else 0,
            ask_volume_1=float(asks[0].get("liquidity", 0)) if asks else 0,
            gateway_name=self.gateway.gateway_name
        )

        # 计算中间价作为最新价
        if tick.bid_price_1 and tick.ask_price_1:
            tick.last_price = (tick.bid_price_1 + tick.ask_price_1) / 2

        self.gateway.on_tick(tick)

    def stop(self) -> None:
        """停止"""
        self.active = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
