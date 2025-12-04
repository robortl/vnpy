# OANDA 黄金交易系统集成指南 - 建议与思路

> 本文档从**量化交易员、产品经理、系统架构师、UI设计师、开发者**五个角色视角，提供集成建议和实施思路。

---

## 一、方案决策分析

### 1.1 为什么选择这套技术栈？

| 组件 | 选择理由 | 替代方案 |
|------|----------|----------|
| **OANDA v20** | 日本合规外汇经纪商，API稳定，黄金点差较低 | IG、Saxo、FXCM |
| **PostgreSQL** | 成熟稳定，支持时序数据优化，社区活跃 | TimescaleDB（PostgreSQL扩展）、ClickHouse |
| **Redis** | 超低延迟，Pub/Sub支持实时推送 | Memcached、本地内存 |
| **Docker** | 环境一致性，易于部署和扩展 | Kubernetes（更复杂场景） |

### 1.2 架构决策

```
┌─────────────────────────────────────────────────────────────────────┐
│                        决策点与选择                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Q1: 数据库选型？                                                    │
│  ├─ 选择: PostgreSQL                                                │
│  ├─ 理由: VeighNa原生支持，迁移成本低                                │
│  └─ 备选: TimescaleDB（如未来数据量>10GB/月）                         │
│                                                                     │
│  Q2: 是否需要Redis缓存？                                             │
│  ├─ 选择: 需要                                                      │
│  ├─ 理由: 黄金行情高频更新(~5次/秒)，减轻数据库压力                   │
│  └─ 场景: 最新Tick缓存、K线缓存、策略状态缓存                         │
│                                                                     │
│  Q3: 容器化方案？                                                    │
│  ├─ 选择: Docker Compose                                            │
│  ├─ 理由: 单机部署够用，学习成本低                                   │
│  └─ 备选: K8s（如需多节点高可用）                                     │
│                                                                     │
│  Q4: 代码侵入度？                                                    │
│  ├─ 选择: 最小侵入                                                  │
│  ├─ 理由: 便于后续升级VeighNa主版本                                  │
│  └─ 方法: 全部代码放custom目录，通过接口扩展                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、量化交易员视角

### 2.1 黄金交易特点

```
┌─────────────────────────────────────────────────────────────────────┐
│                     XAU/USD 交易特性分析                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  交易时间:                                                          │
│  ├─ 周一 07:00 ~ 周六 06:00 (东京时间)                              │
│  ├─ 24小时连续交易                                                  │
│  └─ 关键时段: 伦敦开盘(16:00)、纽约开盘(22:00)                       │
│                                                                     │
│  波动特性:                                                          │
│  ├─ 日均波动: 15-30美元                                             │
│  ├─ 重大事件(非农、利率决议): 可达50-100美元                         │
│  └─ 点差: OANDA JP约0.3-0.5美元/盎司                                │
│                                                                     │
│  策略建议:                                                          │
│  ├─ 趋势跟踪: 适合，黄金趋势性强                                     │
│  ├─ 均值回归: 谨慎，突发事件多                                       │
│  └─ 高频交易: 不适合，点差成本过高                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 风险控制建议

```python
# 建议的风控参数配置

RISK_CONFIG = {
    # 单笔风险
    "max_position_size": 1.0,       # 最大持仓手数
    "max_order_size": 0.5,          # 单笔最大下单量
    "max_daily_loss": 500,          # 日最大亏损(USD)

    # 止损设置
    "default_stop_loss": 10,        # 默认止损点数(美元)
    "trailing_stop": True,          # 启用移动止损
    "trailing_distance": 5,         # 移动止损距离

    # 时间控制
    "no_trade_before_news": 30,     # 重大新闻前30分钟不开仓
    "close_before_weekend": True,   # 周五收盘前平仓
    "weekend_close_hour": 28,       # 周五 04:00 (东京时间)

    # 异常处理
    "max_slippage": 1.0,            # 最大可接受滑点
    "order_timeout": 5,             # 订单超时秒数
}
```

### 2.3 回测数据建议

| 数据类型 | 建议周期 | 存储位置 | 用途 |
|----------|----------|----------|------|
| Tick数据 | 最近1周 | Redis | 实时策略 |
| 1分钟K线 | 最近3个月 | PostgreSQL | 短周期策略回测 |
| 小时K线 | 最近2年 | PostgreSQL | 趋势策略回测 |
| 日线 | 最近10年 | PostgreSQL | 长期趋势分析 |

---

## 三、产品经理视角

### 3.1 核心功能需求

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MVP功能清单                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  P0 - 必须有 (第一阶段):                                             │
│  ├─ [x] OANDA账户连接                                               │
│  ├─ [x] XAU/USD实时行情                                             │
│  ├─ [x] 手动下单/撤单                                               │
│  ├─ [x] 持仓/资金查询                                               │
│  └─ [x] K线数据存储                                                 │
│                                                                     │
│  P1 - 应该有 (第二阶段):                                             │
│  ├─ [ ] CTA策略支持                                                 │
│  ├─ [ ] 策略回测                                                    │
│  ├─ [ ] 邮件/推送通知                                               │
│  └─ [ ] 交易日志分析                                                │
│                                                                     │
│  P2 - 可以有 (第三阶段):                                             │
│  ├─ [ ] 多账户管理                                                  │
│  ├─ [ ] Web监控界面                                                 │
│  ├─ [ ] 移动端推送                                                  │
│  └─ [ ] 风控仪表盘                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 用户体验优化

```
配置简化:
├─ 提供模板配置文件，用户只需填写API Token
├─ Docker一键启动，无需手动配置环境
└─ 默认连接模拟盘，降低误操作风险

操作便捷:
├─ 双击行情快速下单
├─ 一键平仓按钮
└─ 常用交易量预设(0.1, 0.5, 1.0手)

信息展示:
├─ 实时盈亏显示(日元和美元)
├─ 点差实时显示
└─ 资金使用率预警
```

---

## 四、系统架构师视角

### 4.1 分层架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                           应用层                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │   策略引擎   │  │   UI界面    │  │  监控告警   │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
├─────────┴────────────────┴────────────────┴─────────────────────────┤
│                           服务层                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │  订单服务   │  │  行情服务   │  │  数据服务   │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
├─────────┴────────────────┴────────────────┴─────────────────────────┤
│                           核心层                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │  事件引擎   │  │  风控引擎   │  │  日志引擎   │                  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │
├─────────┴────────────────┴────────────────┴─────────────────────────┤
│                           接口层                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │OANDA Gateway│  │  PostgreSQL │  │    Redis    │                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 数据流设计

```
行情数据流:
OANDA Stream API
    │
    ▼
┌─────────────────┐
│  OandaStreamApi │ (WebSocket长连接)
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│ Redis │ │ Event │
│ Cache │ │Engine │
└───┬───┘ └───┬───┘
    │         │
    │    ┌────┴────┐
    │    ▼         ▼
    │ ┌───────┐ ┌───────┐
    │ │  UI   │ │Strategy│
    │ └───────┘ └───────┘
    │
    ▼
┌───────────┐
│PostgreSQL │ (异步批量写入)
└───────────┘


订单数据流:
┌───────────┐
│  策略/UI  │
└─────┬─────┘
      │ OrderRequest
      ▼
┌───────────┐
│ MainEngine│
└─────┬─────┘
      │
      ▼
┌───────────┐
│OandaRestApi│
└─────┬─────┘
      │ HTTP POST
      ▼
┌───────────┐
│ OANDA API │
└─────┬─────┘
      │ OrderResponse
      ▼
┌───────────┐
│ on_order  │ ──► UI更新
└─────┬─────┘
      │
      ▼
┌───────────┐
│PostgreSQL │ (交易记录)
└───────────┘
```

### 4.3 高可用设计（未来扩展）

```
当前方案 (单机):
┌────────────────────────────────┐
│         Docker Host            │
│  ┌──────┐ ┌────┐ ┌───────┐    │
│  │VeighNa│ │Redis│ │Postgres│   │
│  └──────┘ └────┘ └───────┘    │
└────────────────────────────────┘

未来扩展 (高可用):
┌────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Node 1     │  │   Node 2     │  │   Node 3     │          │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │          │
│  │ │VeighNa-1 │ │  │ │VeighNa-2 │ │  │ │VeighNa-3 │ │          │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Redis Cluster (3 Master + 3 Slave)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │          PostgreSQL (Primary + Standby + PgBouncer)       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 4.4 性能优化建议

| 优化点 | 方案 | 预期效果 |
|--------|------|----------|
| Tick写入 | 批量写入 (每100条/1秒) | 减少90%数据库IO |
| K线计算 | Redis缓存最新K线 | 避免频繁查库 |
| 历史查询 | PostgreSQL分区表 | 查询提速10倍 |
| 行情推送 | Redis Pub/Sub | 毫秒级延迟 |

---

## 五、UI设计师视角

### 5.1 界面布局建议

```
┌─────────────────────────────────────────────────────────────────────┐
│  OANDA 黄金交易系统                                    [_][□][×]   │
├─────────────────────────────────────────────────────────────────────┤
│ 系统 | 策略 | 数据 | 帮助                                          │
├──────┬──────────────────────────────────────────────────────────────┤
│      │                                                              │
│ 交易 │  ┌─ XAU/USD 行情 ──────────────────────────────────────────┐│
│ 面板 │  │                                                         ││
│      │  │  当前价: 2024.35  ▲+12.50 (+0.62%)                      ││
│ ───  │  │                                                         ││
│[XAU] │  │  买一: 2024.30 (100)    卖一: 2024.40 (100)             ││
│      │  │  买二: 2024.25 (200)    卖二: 2024.45 (150)             ││
│      │  │                                                         ││
│      │  │  点差: 0.10  日高: 2030.00  日低: 2010.00               ││
│ 方向 │  └─────────────────────────────────────────────────────────┘│
│[多]  │                                                              │
│[空]  │  ┌─ 持仓 ─────────────────────────────────────────────────┐│
│      │  │ 品种      方向    数量    均价      浮盈                ││
│ 数量 │  │ XAU/USD   多     0.5    2015.00   +4.68 (+0.23%)       ││
│[0.1] │  └─────────────────────────────────────────────────────────┘│
│[0.5] │                                                              │
│[1.0] │  ┌─ 委托 ──────────┬─ 成交 ────────────────────────────────┐│
│[___] │  │ (活动委托列表)   │ (成交记录列表)                        ││
│      │  │                  │                                       ││
│[下单]│  └──────────────────┴───────────────────────────────────────┘│
│[平仓]│                                                              │
│      │  ┌─ 日志 ───────────────────────────────────────────────────┐│
│ 账户 │  │ 10:30:01 连接OANDA服务器成功                             ││
│余额: │  │ 10:30:02 订阅XAU/USD行情                                 ││
│$10000│  │ 10:31:15 买入XAU/USD 0.5手 @ 2015.00                     ││
│      │  └─────────────────────────────────────────────────────────┘│
└──────┴──────────────────────────────────────────────────────────────┘
```

### 5.2 颜色方案

```python
# 遵循VeighNa现有风格，适配黄金交易

COLORS = {
    # 涨跌颜色 (国内习惯)
    "price_up": "#FF0000",      # 红色 - 上涨
    "price_down": "#00FF00",    # 绿色 - 下跌

    # 盘口颜色
    "bid": "#FFAEC9",           # 粉红 - 买盘
    "ask": "#A0FFA0",           # 浅绿 - 卖盘

    # 状态颜色
    "connected": "#00FF00",     # 绿色 - 已连接
    "disconnected": "#FF0000",  # 红色 - 断开

    # 盈亏颜色
    "profit": "#FF0000",        # 红色 - 盈利
    "loss": "#00FF00",          # 绿色 - 亏损

    # 黄金主题色
    "gold_primary": "#FFD700",  # 金色 - 可用于图标/强调
    "gold_secondary": "#FFA500", # 橙金色
}
```

### 5.3 新增UI组件

```python
# 黄金专用行情显示组件

class GoldQuoteWidget(QtWidgets.QWidget):
    """黄金行情显示组件"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 当前价格 (大字体)
        self.price_label = QtWidgets.QLabel("-----.--")
        self.price_label.setStyleSheet("font-size: 32px; font-weight: bold;")

        # 涨跌幅
        self.change_label = QtWidgets.QLabel("+0.00 (0.00%)")

        # 点差显示
        self.spread_label = QtWidgets.QLabel(_("点差: 0.00"))

        # 日内高低
        self.high_low_label = QtWidgets.QLabel(_("高: ----  低: ----"))

        # 布局
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.spread_label)
        layout.addWidget(self.high_low_label)
        self.setLayout(layout)

    def update_quote(self, tick: TickData):
        """更新行情显示"""
        # 更新价格
        self.price_label.setText(f"{tick.last_price:.2f}")

        # 更新点差
        spread = tick.ask_price_1 - tick.bid_price_1
        self.spread_label.setText(_("点差: {:.2f}").format(spread))

        # 涨跌颜色
        if tick.last_price > tick.pre_close:
            color = "#FF0000"
            change = f"+{tick.last_price - tick.pre_close:.2f}"
        else:
            color = "#00FF00"
            change = f"{tick.last_price - tick.pre_close:.2f}"

        pct = (tick.last_price / tick.pre_close - 1) * 100 if tick.pre_close else 0
        self.change_label.setText(f"{change} ({pct:+.2f}%)")
        self.change_label.setStyleSheet(f"color: {color};")
```

---

## 六、开发者视角

### 6.1 开发路线图

```
第一阶段: 基础框架 (预计1-2周)
├─ Day 1-2: OANDA REST API封装
├─ Day 3-4: OANDA Stream API封装
├─ Day 5-6: Gateway集成测试
└─ Day 7: PostgreSQL适配

第二阶段: Docker化 (预计3-5天)
├─ Day 1: Dockerfile编写
├─ Day 2: docker-compose配置
├─ Day 3: 启动脚本和初始化
└─ Day 4-5: 测试和文档

第三阶段: 优化完善 (预计1周)
├─ Redis缓存集成
├─ 性能优化
├─ 错误处理完善
└─ 监控告警
```

### 6.2 关键代码结构

```
custom/
├── __init__.py
├── main.py                      # 启动入口
│
├── gateways/
│   ├── __init__.py
│   └── oanda/
│       ├── __init__.py
│       ├── oanda_gateway.py     # Gateway主类
│       ├── oanda_api.py         # REST API
│       ├── oanda_stream.py      # Streaming API
│       └── oanda_constant.py    # 常量定义
│
├── database/
│   ├── __init__.py
│   └── postgresql/
│       ├── __init__.py
│       └── postgresql_database.py
│
├── cache/
│   ├── __init__.py
│   └── redis/
│       ├── __init__.py
│       └── redis_cache.py
│
├── strategies/                   # 自定义策略
│   ├── __init__.py
│   └── gold_trend_strategy.py
│
├── utils/
│   ├── __init__.py
│   └── helpers.py
│
├── config/
│   ├── oanda_config.json
│   └── settings.py
│
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── entrypoint.sh
    ├── .env.example
    └── init-scripts/
        └── init-db.sql
```

### 6.3 测试策略

```python
# tests/test_oanda_gateway.py

import pytest
from custom.gateways.oanda import OandaGateway

class TestOandaGateway:
    """OANDA Gateway 测试"""

    @pytest.fixture
    def gateway(self):
        """创建测试用Gateway"""
        from vnpy.event import EventEngine
        event_engine = EventEngine()
        return OandaGateway(event_engine)

    def test_connect(self, gateway):
        """测试连接"""
        # 使用模拟盘测试
        setting = {
            "API Token": "test_token",
            "Account ID": "test_account",
            "服务器": "Practice",
        }
        gateway.connect(setting)
        assert gateway.rest_api.host == "https://api-fxpractice.oanda.com"

    def test_subscribe(self, gateway):
        """测试订阅"""
        from vnpy.trader.object import SubscribeRequest
        from vnpy.trader.constant import Exchange

        req = SubscribeRequest(symbol="XAU_USD", exchange=Exchange.OTC)
        gateway.subscribe(req)
        assert "XAU_USD" in gateway.stream_api.subscribed
```

### 6.4 常见问题处理

```python
# 异常处理示例

class OandaRestApi:

    def _request(self, method: str, path: str, **kwargs) -> dict | None:
        """发送HTTP请求（带重试）"""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                url = f"{self.host}{path}"
                response = self.session.request(method, url, timeout=10, **kwargs)

                # 处理HTTP错误
                if response.status_code == 401:
                    self.gateway.write_log("API Token无效，请检查配置")
                    return None
                elif response.status_code == 429:
                    # 频率限制，等待后重试
                    wait_time = int(response.headers.get("Retry-After", 1))
                    self.gateway.write_log(f"请求频率过高，等待{wait_time}秒")
                    time.sleep(wait_time)
                    continue
                elif response.status_code >= 500:
                    self.gateway.write_log(f"服务器错误: {response.status_code}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                self.gateway.write_log(f"请求超时，重试 {attempt + 1}/{max_retries}")
                time.sleep(retry_delay)

            except requests.exceptions.ConnectionError:
                self.gateway.write_log("网络连接错误，检查网络或代理设置")
                time.sleep(retry_delay * 2)

            except Exception as e:
                self.gateway.write_log(f"请求异常: {e}")
                return None

        self.gateway.write_log("请求失败，已达最大重试次数")
        return None
```

---

## 七、实施建议

### 7.1 阶段性目标

| 阶段 | 目标 | 验收标准 |
|------|------|----------|
| **Week 1** | OANDA Gateway可用 | 能连接、订阅行情、手动下单 |
| **Week 2** | 数据持久化完成 | Tick/K线存入PostgreSQL |
| **Week 3** | Docker化部署 | 一键启动所有服务 |
| **Week 4** | CTA策略运行 | 策略能在实时行情下运行 |

### 7.2 风险提示

```
⚠️ 技术风险:
├─ OANDA API可能有访问频率限制
├─ 流式API断线需要自动重连
└─ 时区处理需特别注意（UTC vs 东京时间）

⚠️ 交易风险:
├─ 黄金波动大，注意仓位控制
├─ 周末/节假日流动性差
└─ 模拟盘与实盘可能有差异

⚠️ 合规风险:
├─ OANDA JP需日本居民账户
├─ 遵守日本金融厅相关规定
└─ 注意API使用条款
```

### 7.3 后续优化方向

1. **性能优化**: TimescaleDB替代PostgreSQL，提升时序数据查询性能
2. **高可用**: 引入Kubernetes，实现服务自动恢复
3. **监控**: 接入Prometheus + Grafana，实现全链路监控
4. **通知**: 接入LINE/Slack，重要事件实时推送
5. **回测**: 开发专用回测模块，支持历史数据回放

---

*文档版本: 1.0 | 作者: Claude (量化交易员/产品经理/架构师/UI设计师/开发者) | 最后更新: 2024*
