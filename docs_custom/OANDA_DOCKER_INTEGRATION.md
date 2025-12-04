# OANDA v20 + PostgreSQL + Redis + Docker 集成方案

> 本文档描述如何将 VeighNa 改造为使用 OANDA JP v20 API 进行黄金交易，配合 PostgreSQL 数据库和 Redis 缓存，全部服务 Docker 化部署。

---

## 〇、现状分析与方案选择

### 0.1 VeighNa 官方支持情况

**结论：VeighNa 官方没有提供 OANDA Gateway，需要自行开发。**

官方支持的 Gateway 列表（参考 [VeighNa 交易接口文档](https://www.vnpy.com/docs/cn/community/info/gateway.html)）：

| 接口 | 市场 | 是否支持黄金 |
|------|------|--------------|
| CTP | 国内期货 | 上海黄金(AU) |
| vnpy_ib (盈透) | 全球 | 支持 XAU |
| 富途/老虎 | 港美股 | 不支持 |

### 0.2 开发方案对比

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **A: 基于 oandapyV20 封装** | 库成熟稳定，文档完善 | 需要封装适配层 | ⭐⭐⭐⭐⭐ |
| B: 基于官方 v20-python | 官方维护 | 更新不活跃 | ⭐⭐⭐ |
| C: 纯 requests 实现 | 完全自主 | 工作量大 | ⭐⭐ |
| D: 改用 IB 盈透 | 有现成 vnpy_ib | 需要 IB 账户 | ⭐⭐⭐ |

### 0.3 推荐方案：基于 oandapyV20

选择 [oandapyV20](https://github.com/hootnot/oanda-api-v20) 的理由：
- GitHub 800+ stars，社区活跃
- 完整支持 v20 REST API 和 Streaming API
- 文档详尽：[oandapyV20 文档](https://oanda-api-v20.readthedocs.io/)
- pip 直接安装：`pip install oandapyV20`

```python
# oandapyV20 简单示例
from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream

api = API(access_token="your_token", environment="practice")

# 获取实时行情
params = {"instruments": "XAU_USD"}
r = PricingStream(accountID="your_account", params=params)
for tick in api.request(r):
    print(tick)
```

---

## 一、整体架构

### 1.1 目标架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Network                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │   Redis     │    │ PostgreSQL  │    │     VeighNa Trader      │ │
│  │  (缓存)     │◄───│   (数据库)   │◄───│      (交易系统)          │ │
│  │  Port:6379  │    │  Port:5432  │    │      Port:8888          │ │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │
│                                                     │               │
└─────────────────────────────────────────────────────┼───────────────┘
                                                      │
                                                      ▼
                                        ┌─────────────────────────┐
                                        │    OANDA JP v20 API     │
                                        │  (外汇/黄金交易服务)      │
                                        │  api-fxpractice.oanda.com │
                                        │  api-fxtrade.oanda.com   │
                                        └─────────────────────────┘
```

### 1.2 组件说明

| 组件 | 版本 | 用途 |
|------|------|------|
| VeighNa | 4.2.0 | 量化交易主系统 |
| OANDA v20 Gateway | 自定义 | 连接 OANDA 交易API |
| PostgreSQL | 15+ | 持久化存储（K线、Tick、交易记录） |
| Redis | 7+ | 实时行情缓存、会话管理 |
| Docker Compose | 2.x | 服务编排 |

---

## 二、需要开发的模块

### 2.1 模块清单

```
custom/
├── gateways/
│   └── oanda/                    # OANDA v20 Gateway
│       ├── __init__.py
│       ├── oanda_gateway.py      # 主Gateway实现
│       ├── oanda_api.py          # v20 REST API封装
│       └── oanda_stream.py       # 流式行情接口
├── database/
│   └── postgresql/               # PostgreSQL 数据库适配
│       ├── __init__.py
│       └── postgresql_database.py
├── cache/
│   └── redis/                    # Redis 缓存层
│       ├── __init__.py
│       └── redis_cache.py
├── config/
│   ├── oanda_config.json         # OANDA 连接配置
│   └── docker_config.json        # Docker 环境配置
└── docker/
    ├── Dockerfile                # VeighNa 镜像
    ├── docker-compose.yml        # 服务编排
    └── init-scripts/
        └── init-db.sql           # PostgreSQL 初始化脚本
```

---

## 三、OANDA v20 Gateway 开发

### 3.1 OANDA JP 账户信息

| 环境 | API 地址 | 用途 |
|------|----------|------|
| 模拟盘 | `api-fxpractice.oanda.com` | 测试开发 |
| 实盘 | `api-fxtrade.oanda.com` | 正式交易 |

### 3.2 黄金交易品种

| 品种代码 | 说明 | VeighNa 映射 |
|----------|------|--------------|
| XAU_USD | 黄金/美元 | symbol=XAU_USD, exchange=OTC |
| XAU_JPY | 黄金/日元 | symbol=XAU_JPY, exchange=OTC |

### 3.3 Gateway 接口实现（基于 oandapyV20）

> 使用成熟的 [oandapyV20](https://github.com/hootnot/oanda-api-v20) 库，大幅减少开发工作量。

```python
# custom/gateways/oanda/oanda_gateway.py

"""
OANDA v20 Gateway for VeighNa
基于 oandapyV20 库封装
安装依赖: pip install oandapyV20
"""

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData, OrderData, TradeData, PositionData, AccountData,
    ContractData, OrderRequest, CancelRequest, SubscribeRequest,
    HistoryRequest, BarData, Exchange, Product, Direction, OrderType, Status
)
from vnpy.trader.constant import Interval

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

    def __init__(self, event_engine, gateway_name: str = "OANDA"):
        super().__init__(event_engine, gateway_name)

        self.api: API | None = None
        self.account_id: str = ""
        self.stream_api: OandaStreamApi | None = None

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
                    pricetick=10 ** inst["pipLocation"],
                    min_volume=float(inst["minimumTradeSize"]),
                    history_data=True,
                    net_position=True,
                    gateway_name=self.gateway_name
                )
                self.on_contract(contract)

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
            elif "orderCreateTransaction" in response:
                order.status = Status.NOTTRADED
            else:
                order.status = Status.REJECTED

            self.on_order(order)
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
        """查询历史K线 - 使用 oandapyV20"""
        bars = []

        granularity_map = {
            Interval.MINUTE: "M1",
            Interval.HOUR: "H1",
            Interval.DAILY: "D",
        }
        granularity = granularity_map.get(req.interval, "M1")

        params = {
            "granularity": granularity,
            "from": req.start.isoformat() + "Z",
            "price": "M"
        }
        if req.end:
            params["to"] = req.end.isoformat() + "Z"

        try:
            r = instruments.InstrumentsCandles(instrument=req.symbol, params=params)
            response = self.api.request(r)

            for candle in response.get("candles", []):
                if not candle.get("complete"):
                    continue

                mid = candle["mid"]
                bar = BarData(
                    symbol=req.symbol,
                    exchange=Exchange.OTC,
                    datetime=datetime.fromisoformat(candle["time"].replace("Z", "+00:00")),
                    interval=req.interval,
                    open_price=float(mid["o"]),
                    high_price=float(mid["h"]),
                    low_price=float(mid["l"]),
                    close_price=float(mid["c"]),
                    volume=float(candle["volume"]),
                    gateway_name=self.gateway_name
                )
                bars.append(bar)

        except V20Error as e:
            self.write_log(f"查询历史数据失败: {e}")

        return bars

    def close(self) -> None:
        """关闭连接"""
        if self.stream_api:
            self.stream_api.stop()
        self.write_log("OANDA Gateway 已关闭")
```

### 3.4 流式行情接口（基于 oandapyV20）

> oandapyV20 已内置 Streaming API 支持，直接使用即可。

```python
# custom/gateways/oanda/oanda_stream.py

"""
OANDA Streaming API 封装
基于 oandapyV20.endpoints.pricing.PricingStream
"""

from threading import Thread
from datetime import datetime

from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream
from oandapyV20.exceptions import V20Error

from vnpy.trader.object import TickData, Exchange


class OandaStreamApi:
    """
    OANDA 流式行情 API

    使用 oandapyV20 的 PricingStream 端点
    """

    def __init__(self, gateway, token: str, account_id: str, environment: str):
        self.gateway = gateway
        self.token = token
        self.account_id = account_id
        self.environment = environment

        self.api = API(access_token=token, environment=environment)
        self.subscribed: set[str] = set()
        self.thread: Thread | None = None
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

    def _run_stream(self) -> None:
        """运行流式数据接收 - 使用 oandapyV20"""
        instruments = ",".join(self.subscribed)

        params = {"instruments": instruments}
        r = PricingStream(accountID=self.account_id, params=params)

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
```

### 3.5 模块入口文件

```python
# custom/gateways/oanda/__init__.py

"""
OANDA v20 Gateway for VeighNa

依赖: pip install oandapyV20

使用示例:
    from custom.gateways.oanda import OandaGateway
    main_engine.add_gateway(OandaGateway)
"""

from .oanda_gateway import OandaGateway

__all__ = ["OandaGateway"]
```

---

## 四、PostgreSQL 数据库适配

### 4.1 数据库实现

```python
# custom/database/postgresql/postgresql_database.py

from datetime import datetime
from typing import List
import psycopg2
from psycopg2.extras import execute_batch

from vnpy.trader.database import BaseDatabase, BarOverview, TickOverview
from vnpy.trader.object import BarData, TickData
from vnpy.trader.constant import Exchange, Interval

class PostgresqlDatabase(BaseDatabase):
    """PostgreSQL数据库实现"""

    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self) -> None:
        """连接数据库"""
        from vnpy.trader.setting import SETTINGS

        self.connection = psycopg2.connect(
            host=SETTINGS.get("database.host", "localhost"),
            port=SETTINGS.get("database.port", 5432),
            database=SETTINGS.get("database.database", "vnpy"),
            user=SETTINGS.get("database.user", "vnpy"),
            password=SETTINGS.get("database.password", "")
        )
        self.connection.autocommit = True
        self._init_tables()

    def _init_tables(self) -> None:
        """初始化数据表"""
        cursor = self.connection.cursor()

        # K线数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bar_data (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                exchange VARCHAR(20) NOT NULL,
                datetime TIMESTAMP NOT NULL,
                interval VARCHAR(10) NOT NULL,
                volume DOUBLE PRECISION,
                turnover DOUBLE PRECISION,
                open_interest DOUBLE PRECISION,
                open_price DOUBLE PRECISION NOT NULL,
                high_price DOUBLE PRECISION NOT NULL,
                low_price DOUBLE PRECISION NOT NULL,
                close_price DOUBLE PRECISION NOT NULL,
                UNIQUE(symbol, exchange, datetime, interval)
            );
            CREATE INDEX IF NOT EXISTS idx_bar_symbol_datetime
                ON bar_data(symbol, exchange, interval, datetime);
        """)

        # Tick数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tick_data (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                exchange VARCHAR(20) NOT NULL,
                datetime TIMESTAMP NOT NULL,
                name VARCHAR(100),
                volume DOUBLE PRECISION,
                last_price DOUBLE PRECISION,
                bid_price_1 DOUBLE PRECISION,
                ask_price_1 DOUBLE PRECISION,
                bid_volume_1 DOUBLE PRECISION,
                ask_volume_1 DOUBLE PRECISION,
                UNIQUE(symbol, exchange, datetime)
            );
            CREATE INDEX IF NOT EXISTS idx_tick_symbol_datetime
                ON tick_data(symbol, exchange, datetime);
        """)

        cursor.close()

    def save_bar_data(self, bars: List[BarData], stream: bool = False) -> bool:
        """保存K线数据"""
        if not bars:
            return True

        cursor = self.connection.cursor()

        data = [(
            bar.symbol, bar.exchange.value, bar.datetime,
            bar.interval.value if bar.interval else None,
            bar.volume, bar.turnover, bar.open_interest,
            bar.open_price, bar.high_price, bar.low_price, bar.close_price
        ) for bar in bars]

        sql = """
            INSERT INTO bar_data
            (symbol, exchange, datetime, interval, volume, turnover,
             open_interest, open_price, high_price, low_price, close_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, exchange, datetime, interval)
            DO UPDATE SET
                volume = EXCLUDED.volume,
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price
        """

        execute_batch(cursor, sql, data)
        cursor.close()
        return True

    def save_tick_data(self, ticks: List[TickData], stream: bool = False) -> bool:
        """保存Tick数据"""
        if not ticks:
            return True

        cursor = self.connection.cursor()

        data = [(
            tick.symbol, tick.exchange.value, tick.datetime, tick.name,
            tick.volume, tick.last_price,
            tick.bid_price_1, tick.ask_price_1,
            tick.bid_volume_1, tick.ask_volume_1
        ) for tick in ticks]

        sql = """
            INSERT INTO tick_data
            (symbol, exchange, datetime, name, volume, last_price,
             bid_price_1, ask_price_1, bid_volume_1, ask_volume_1)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, exchange, datetime) DO NOTHING
        """

        execute_batch(cursor, sql, data)
        cursor.close()
        return True

    def load_bar_data(
        self, symbol: str, exchange: Exchange, interval: Interval,
        start: datetime, end: datetime
    ) -> List[BarData]:
        """加载K线数据"""
        cursor = self.connection.cursor()

        sql = """
            SELECT datetime, volume, turnover, open_interest,
                   open_price, high_price, low_price, close_price
            FROM bar_data
            WHERE symbol = %s AND exchange = %s AND interval = %s
                  AND datetime >= %s AND datetime <= %s
            ORDER BY datetime
        """

        cursor.execute(sql, (symbol, exchange.value, interval.value, start, end))

        bars = []
        for row in cursor.fetchall():
            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=row[0],
                interval=interval,
                volume=row[1] or 0,
                turnover=row[2] or 0,
                open_interest=row[3] or 0,
                open_price=row[4],
                high_price=row[5],
                low_price=row[6],
                close_price=row[7],
                gateway_name="DB"
            )
            bars.append(bar)

        cursor.close()
        return bars

    def load_tick_data(
        self, symbol: str, exchange: Exchange,
        start: datetime, end: datetime
    ) -> List[TickData]:
        """加载Tick数据"""
        cursor = self.connection.cursor()

        sql = """
            SELECT datetime, name, volume, last_price,
                   bid_price_1, ask_price_1, bid_volume_1, ask_volume_1
            FROM tick_data
            WHERE symbol = %s AND exchange = %s
                  AND datetime >= %s AND datetime <= %s
            ORDER BY datetime
        """

        cursor.execute(sql, (symbol, exchange.value, start, end))

        ticks = []
        for row in cursor.fetchall():
            tick = TickData(
                symbol=symbol,
                exchange=exchange,
                datetime=row[0],
                name=row[1] or "",
                volume=row[2] or 0,
                last_price=row[3] or 0,
                bid_price_1=row[4] or 0,
                ask_price_1=row[5] or 0,
                bid_volume_1=row[6] or 0,
                ask_volume_1=row[7] or 0,
                gateway_name="DB"
            )
            ticks.append(tick)

        cursor.close()
        return ticks

    def delete_bar_data(self, symbol: str, exchange: Exchange, interval: Interval) -> int:
        """删除K线数据"""
        cursor = self.connection.cursor()
        sql = "DELETE FROM bar_data WHERE symbol = %s AND exchange = %s AND interval = %s"
        cursor.execute(sql, (symbol, exchange.value, interval.value))
        count = cursor.rowcount
        cursor.close()
        return count

    def delete_tick_data(self, symbol: str, exchange: Exchange) -> int:
        """删除Tick数据"""
        cursor = self.connection.cursor()
        sql = "DELETE FROM tick_data WHERE symbol = %s AND exchange = %s"
        cursor.execute(sql, (symbol, exchange.value))
        count = cursor.rowcount
        cursor.close()
        return count

    def get_bar_overview(self) -> List[BarOverview]:
        """获取K线数据概览"""
        cursor = self.connection.cursor()
        sql = """
            SELECT symbol, exchange, interval, COUNT(*), MIN(datetime), MAX(datetime)
            FROM bar_data
            GROUP BY symbol, exchange, interval
        """
        cursor.execute(sql)

        overviews = []
        for row in cursor.fetchall():
            overview = BarOverview(
                symbol=row[0],
                exchange=Exchange(row[1]),
                interval=Interval(row[2]),
                count=row[3],
                start=row[4],
                end=row[5]
            )
            overviews.append(overview)

        cursor.close()
        return overviews

    def get_tick_overview(self) -> List[TickOverview]:
        """获取Tick数据概览"""
        cursor = self.connection.cursor()
        sql = """
            SELECT symbol, exchange, COUNT(*), MIN(datetime), MAX(datetime)
            FROM tick_data
            GROUP BY symbol, exchange
        """
        cursor.execute(sql)

        overviews = []
        for row in cursor.fetchall():
            overview = TickOverview(
                symbol=row[0],
                exchange=Exchange(row[1]),
                count=row[2],
                start=row[3],
                end=row[4]
            )
            overviews.append(overview)

        cursor.close()
        return overviews


# 导出数据库类
Database = PostgresqlDatabase
```

---

## 五、Redis 缓存层

### 5.1 缓存实现

```python
# custom/cache/redis/redis_cache.py

import json
import redis
from datetime import datetime
from typing import Optional

from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Exchange, Interval

class RedisCache:
    """Redis缓存管理器"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True
        )
        self.tick_expire = 60  # Tick数据60秒过期
        self.bar_expire = 300  # Bar数据5分钟过期

    def cache_tick(self, tick: TickData) -> None:
        """缓存Tick数据"""
        key = f"tick:{tick.vt_symbol}"
        data = {
            "symbol": tick.symbol,
            "exchange": tick.exchange.value,
            "datetime": tick.datetime.isoformat(),
            "last_price": tick.last_price,
            "bid_price_1": tick.bid_price_1,
            "ask_price_1": tick.ask_price_1,
            "bid_volume_1": tick.bid_volume_1,
            "ask_volume_1": tick.ask_volume_1,
            "volume": tick.volume,
        }
        self.client.setex(key, self.tick_expire, json.dumps(data))

        # 同时保存到有序集合（用于时间序列查询）
        ts_key = f"tick_ts:{tick.vt_symbol}"
        timestamp = tick.datetime.timestamp()
        self.client.zadd(ts_key, {json.dumps(data): timestamp})
        # 只保留最近1小时的数据
        self.client.zremrangebyscore(ts_key, 0, timestamp - 3600)

    def get_tick(self, vt_symbol: str) -> Optional[TickData]:
        """获取最新Tick"""
        key = f"tick:{vt_symbol}"
        data = self.client.get(key)

        if not data:
            return None

        d = json.loads(data)
        return TickData(
            symbol=d["symbol"],
            exchange=Exchange(d["exchange"]),
            datetime=datetime.fromisoformat(d["datetime"]),
            last_price=d["last_price"],
            bid_price_1=d["bid_price_1"],
            ask_price_1=d["ask_price_1"],
            bid_volume_1=d["bid_volume_1"],
            ask_volume_1=d["ask_volume_1"],
            volume=d["volume"],
            gateway_name="CACHE"
        )

    def cache_bar(self, bar: BarData) -> None:
        """缓存K线数据"""
        key = f"bar:{bar.vt_symbol}:{bar.interval.value if bar.interval else 'm1'}"
        data = {
            "symbol": bar.symbol,
            "exchange": bar.exchange.value,
            "datetime": bar.datetime.isoformat(),
            "interval": bar.interval.value if bar.interval else "1m",
            "open": bar.open_price,
            "high": bar.high_price,
            "low": bar.low_price,
            "close": bar.close_price,
            "volume": bar.volume,
        }

        # 保存到有序集合
        timestamp = bar.datetime.timestamp()
        self.client.zadd(key, {json.dumps(data): timestamp})

        # 限制缓存数量
        self.client.zremrangebyrank(key, 0, -1001)  # 只保留最近1000根

    def get_recent_bars(
        self, vt_symbol: str, interval: Interval, count: int = 100
    ) -> list[BarData]:
        """获取最近N根K线"""
        key = f"bar:{vt_symbol}:{interval.value}"
        items = self.client.zrevrange(key, 0, count - 1)

        bars = []
        for item in reversed(items):
            d = json.loads(item)
            bar = BarData(
                symbol=d["symbol"],
                exchange=Exchange(d["exchange"]),
                datetime=datetime.fromisoformat(d["datetime"]),
                interval=Interval(d["interval"]),
                open_price=d["open"],
                high_price=d["high"],
                low_price=d["low"],
                close_price=d["close"],
                volume=d["volume"],
                gateway_name="CACHE"
            )
            bars.append(bar)

        return bars

    def set_session(self, session_id: str, data: dict, expire: int = 3600) -> None:
        """保存会话数据"""
        key = f"session:{session_id}"
        self.client.setex(key, expire, json.dumps(data))

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话数据"""
        key = f"session:{session_id}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def publish_event(self, channel: str, data: dict) -> None:
        """发布事件"""
        self.client.publish(channel, json.dumps(data))

    def subscribe_events(self, channels: list) -> redis.client.PubSub:
        """订阅事件"""
        pubsub = self.client.pubsub()
        pubsub.subscribe(*channels)
        return pubsub
```

---

## 六、Docker 部署配置

### 6.1 docker-compose.yml

```yaml
# custom/docker/docker-compose.yml

version: '3.8'

services:
  # PostgreSQL 数据库
  postgres:
    image: postgres:15-alpine
    container_name: vnpy-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: vnpy
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-vnpy123}
      POSTGRES_DB: vnpy
      TZ: Asia/Tokyo
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vnpy"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis 缓存
  redis:
    image: redis:7-alpine
    container_name: vnpy-redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # VeighNa 交易系统
  vnpy:
    build:
      context: ../..
      dockerfile: custom/docker/Dockerfile
    container_name: vnpy-trader
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # 数据库配置
      DATABASE_HOST: postgres
      DATABASE_PORT: 5432
      DATABASE_NAME: vnpy
      DATABASE_USER: vnpy
      DATABASE_PASSWORD: ${POSTGRES_PASSWORD:-vnpy123}
      # Redis配置
      REDIS_HOST: redis
      REDIS_PORT: 6379
      # OANDA配置
      OANDA_TOKEN: ${OANDA_TOKEN}
      OANDA_ACCOUNT_ID: ${OANDA_ACCOUNT_ID}
      OANDA_SERVER: ${OANDA_SERVER:-Practice}
      # 时区
      TZ: Asia/Tokyo
    volumes:
      - vnpy_data:/root/.vntrader
      - ./logs:/app/logs
    ports:
      - "8888:8888"  # Web UI (如果启用)
    # 如需GUI,取消以下注释
    # environment:
    #   - DISPLAY=${DISPLAY}
    # volumes:
    #   - /tmp/.X11-unix:/tmp/.X11-unix

volumes:
  postgres_data:
  redis_data:
  vnpy_data:

networks:
  default:
    name: vnpy-network
```

### 6.2 Dockerfile

```dockerfile
# custom/docker/Dockerfile

FROM python:3.11-slim

LABEL maintainer="vnpy-custom"
LABEL description="VeighNa Trading Platform with OANDA Gateway"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
COPY vnpy/ ./vnpy/
COPY custom/ ./custom/
COPY setup.py .
COPY pyproject.toml .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        psycopg2-binary \
        redis \
        requests

# 安装vnpy
RUN pip install -e .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 创建配置目录
RUN mkdir -p /root/.vntrader

# 复制启动脚本
COPY custom/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "custom.main"]
```

### 6.3 启动脚本

```bash
#!/bin/bash
# custom/docker/entrypoint.sh

set -e

# 等待数据库就绪
echo "Waiting for PostgreSQL..."
while ! pg_isready -h $DATABASE_HOST -p $DATABASE_PORT -U $DATABASE_USER; do
    sleep 1
done
echo "PostgreSQL is ready!"

# 等待Redis就绪
echo "Waiting for Redis..."
while ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping; do
    sleep 1
done
echo "Redis is ready!"

# 生成VeighNa配置文件
cat > /root/.vntrader/vt_setting.json << EOF
{
    "font.family": "Noto Sans CJK JP",
    "font.size": 12,
    "log.active": true,
    "log.level": 20,
    "log.console": true,
    "log.file": true,
    "database.timezone": "Asia/Tokyo",
    "database.name": "postgresql",
    "database.database": "${DATABASE_NAME}",
    "database.host": "${DATABASE_HOST}",
    "database.port": ${DATABASE_PORT},
    "database.user": "${DATABASE_USER}",
    "database.password": "${DATABASE_PASSWORD}"
}
EOF

# 生成OANDA连接配置
cat > /root/.vntrader/connect_oanda.json << EOF
{
    "API Token": "${OANDA_TOKEN}",
    "Account ID": "${OANDA_ACCOUNT_ID}",
    "服务器": "${OANDA_SERVER}",
    "代理地址": "",
    "代理端口": 0
}
EOF

echo "Configuration generated."

# 执行传入的命令
exec "$@"
```

### 6.4 数据库初始化脚本

```sql
-- custom/docker/init-scripts/init-db.sql

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
    offset VARCHAR(20),
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

-- 插入黄金合约信息
INSERT INTO contract_info (symbol, exchange, name, product, size, pricetick)
VALUES
    ('XAU_USD', 'OTC', 'Gold/USD', 'FOREX', 1, 0.01),
    ('XAU_JPY', 'OTC', 'Gold/JPY', 'FOREX', 1, 1)
ON CONFLICT DO NOTHING;
```

---

## 七、环境配置

### 7.1 环境变量文件

```bash
# custom/docker/.env

# PostgreSQL
POSTGRES_PASSWORD=your_secure_password

# OANDA API
OANDA_TOKEN=your_oanda_api_token
OANDA_ACCOUNT_ID=your_account_id
OANDA_SERVER=Practice  # 或 Live

# 时区
TZ=Asia/Tokyo
```

### 7.2 VeighNa 配置文件

```json
// ~/.vntrader/vt_setting.json

{
    "font.family": "微软雅黑",
    "font.size": 12,
    "log.active": true,
    "log.level": 20,
    "log.console": true,
    "log.file": true,
    "database.timezone": "Asia/Tokyo",
    "database.name": "postgresql",
    "database.database": "vnpy",
    "database.host": "localhost",
    "database.port": 5432,
    "database.user": "vnpy",
    "database.password": "your_password"
}
```

---

## 八、改动清单

### 8.1 需要修改的原有文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `vnpy/trader/constant.py` | 新增 | 添加 OANDA 交易所枚举（可选） |
| `vnpy/trader/setting.py` | 无需改动 | 配置文件格式已支持 |

### 8.2 需要新建的文件

| 文件 | 说明 |
|------|------|
| `custom/gateways/oanda/__init__.py` | Gateway 模块入口 |
| `custom/gateways/oanda/oanda_gateway.py` | Gateway 主实现 |
| `custom/gateways/oanda/oanda_api.py` | REST API 封装 |
| `custom/gateways/oanda/oanda_stream.py` | 流式API 封装 |
| `custom/database/postgresql/__init__.py` | 数据库模块入口 |
| `custom/database/postgresql/postgresql_database.py` | PostgreSQL 实现 |
| `custom/cache/redis/__init__.py` | 缓存模块入口 |
| `custom/cache/redis/redis_cache.py` | Redis 缓存实现 |
| `custom/docker/Dockerfile` | Docker 镜像定义 |
| `custom/docker/docker-compose.yml` | 服务编排 |
| `custom/docker/entrypoint.sh` | 容器启动脚本 |
| `custom/docker/init-scripts/init-db.sql` | 数据库初始化 |
| `custom/main.py` | 自定义启动入口 |

### 8.3 依赖包

```
# requirements-custom.txt

# OANDA API
requests>=2.28.0

# PostgreSQL
psycopg2-binary>=2.9.0

# Redis
redis>=4.5.0

# 其他
python-dotenv>=1.0.0
```

---

## 九、使用指南

### 9.1 快速启动

```bash
# 1. 进入Docker目录
cd custom/docker

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OANDA API Token 等

# 3. 启动所有服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f vnpy

# 5. 停止服务
docker-compose down
```

### 9.2 开发模式启动

```bash
# 只启动数据库和Redis
docker-compose up -d postgres redis

# 本地运行VeighNa
python -m custom.main
```

### 9.3 连接OANDA并订阅黄金行情

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from custom.gateways.oanda import OandaGateway

# 创建引擎
event_engine = EventEngine()
main_engine = MainEngine(event_engine)

# 添加OANDA网关
main_engine.add_gateway(OandaGateway)

# 连接
setting = {
    "API Token": "your_token",
    "Account ID": "your_account_id",
    "服务器": "Practice",
    "代理地址": "",
    "代理端口": 0,
}
main_engine.connect(setting, "OANDA")

# 订阅黄金行情
from vnpy.trader.object import SubscribeRequest
from vnpy.trader.constant import Exchange

req = SubscribeRequest(symbol="XAU_USD", exchange=Exchange.OTC)
main_engine.subscribe(req, "OANDA")
```

---

## 十、注意事项

1. **OANDA JP 特殊性**
   - OANDA Japan 使用 v20 API
   - 需要日本居民账户
   - API Token 需在 OANDA 后台生成

2. **时区处理**
   - 所有时间统一使用 UTC 存储
   - 显示时转换为 Asia/Tokyo

3. **网络代理**
   - 如在中国大陆使用，可能需要配置代理
   - Docker 内需配置代理环境变量

4. **数据持久化**
   - PostgreSQL 数据存储在 Docker Volume
   - 定期备份 `postgres_data` Volume

5. **安全建议**
   - 不要将 API Token 提交到代码仓库
   - 使用环境变量或 secrets 管理敏感信息
   - 生产环境使用强密码

---

*文档版本: 1.0 | 最后更新: 2024*
