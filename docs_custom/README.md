# VeighNa (vnpy) 项目快速理解指南

> 本文档帮助你快速理解 VeighNa 量化交易框架的功能、设计思路和架构。

## 一、项目概述

**VeighNa** 是一套基于 Python 的开源量化交易系统开发框架，版本 4.2.0。

### 核心定位
- **目标用户**：专业个人投资者、创业型私募、券商资管部门
- **核心价值**：提供从交易API对接到策略自动交易的一站式量化解决方案
- **技术栈**：Python 3.10+，支持 Windows/Linux/MacOS

### 主要特点
1. 开源免费，MIT 协议
2. 多市场覆盖（国内期货/股票/期权，海外市场）
3. 事件驱动架构，高可扩展性
4. 完整的策略开发到实盘交易流程
5. 4.0 版本新增 AI 量化模块 (vnpy.alpha)

---

## 二、架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        VeighNa Trader (UI)                       │
│                    vnpy.trader.ui.MainWindow                     │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                         MainEngine                               │
│                     vnpy.trader.engine                           │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐      │
│  │  OmsEngine  │  LogEngine  │ EmailEngine │  AppEngines │      │
│  │  (订单管理)  │   (日志)    │   (邮件)    │  (应用模块)  │      │
│  └─────────────┴─────────────┴─────────────┴─────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                                 │
┌─────────────────────────────────────────────────────────────────┐
│                        EventEngine                               │
│                      vnpy.event.engine                           │
│              (事件驱动核心 - 生产者/消费者模式)                    │
└─────────────────────────────────────────────────────────────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│   Gateway   │          │  Database   │          │  DataFeed   │
│  (交易接口)  │          │  (数据库)    │          │  (数据服务)  │
└─────────────┘          └─────────────┘          └─────────────┘
```

### 2.2 核心组件说明

#### EventEngine (事件引擎)
- **位置**：`vnpy/event/engine.py`
- **设计模式**：生产者-消费者 + 观察者模式
- **核心功能**：
  - 事件分发：根据事件类型分发给注册的处理函数
  - 定时器：每秒生成 Timer 事件
  - 通用处理：支持监听所有事件类型

```python
# 事件类型示例
EVENT_TICK      # 行情数据
EVENT_ORDER     # 委托回报
EVENT_TRADE     # 成交回报
EVENT_POSITION  # 持仓更新
EVENT_ACCOUNT   # 账户更新
EVENT_CONTRACT  # 合约信息
EVENT_LOG       # 日志事件
```

#### MainEngine (主引擎)
- **位置**：`vnpy/trader/engine.py`
- **职责**：交易平台核心，统一管理所有组件
- **核心功能**：
  - 管理 Gateway（交易接口）
  - 管理 Engine（功能引擎）
  - 管理 App（应用模块）
  - 统一的日志、下单、撤单接口

#### OmsEngine (订单管理引擎)
- **位置**：`vnpy/trader/engine.py`
- **职责**：订单管理系统
- **数据管理**：
  - Tick 行情缓存
  - Order 委托记录
  - Trade 成交记录
  - Position 持仓数据
  - Account 账户资金
  - Contract 合约信息

---

## 三、功能模块

### 3.1 交易接口 (Gateway)

支持 20+ 交易接口，覆盖：

| 市场 | 接口 |
|------|------|
| 国内期货 | CTP, CTP Mini, 飞马, 恒生UFT, 易盛 |
| ETF期权 | CTP期权, 顶点HTS, 华鑫奇点 |
| A股 | 中泰XTP, 华鑫奇点, 东方OST |
| 黄金TD | 金仕达黄金, 飞鼠 |
| 海外 | 盈透证券(IB), 易盛外盘, 直达期货 |

### 3.2 应用模块 (App)

| 模块 | 说明 |
|------|------|
| **CTA策略** | CTA策略引擎，支持回测与实盘 |
| **CTA回测** | 图形化策略回测分析 |
| **价差交易** | 多合约价差套利 |
| **期权交易** | 波动率交易，希腊值管理 |
| **组合策略** | 多合约组合策略 |
| **算法交易** | TWAP, Sniper, Iceberg 等 |
| **脚本交易** | REPL 风格交易 |
| **数据管理** | 历史数据导入导出 |
| **行情记录** | Tick/K线实时录制 |
| **风险管理** | 流控、委托限制 |
| **RPC服务** | 分布式架构支持 |

### 3.3 数据存储 (Database)

支持多种数据库：

| 类型 | 数据库 | 特点 |
|------|--------|------|
| SQL | SQLite | 默认，轻量级 |
| SQL | MySQL | 主流，文档丰富 |
| SQL | PostgreSQL | 特性丰富 |
| NoSQL | MongoDB | 文档存储，热缓存 |
| 时序 | TDengine | 高性能时序 |
| 时序 | DolphinDB | 极速查询 |
| 时序 | InfluxDB | 列式存储 |

### 3.4 数据服务 (DataFeed)

| 服务 | 覆盖品种 |
|------|----------|
| 迅投研 | 股票、期货、期权、基金、债券 |
| 米筐RQData | 全品种 |
| TuShare | 股票、期货、期权 |
| Wind/iFinD | 机构级数据 |
| 天勤TQSDK | 期货 |

---

## 四、AI 量化模块 (vnpy.alpha)

4.0 版本重磅新增，提供 ML 策略开发解决方案：

### 4.1 模块结构

```
vnpy/alpha/
├── dataset/          # 因子特征工程
│   ├── processor.py  # 数据处理器
│   ├── ta_function.py    # 技术指标函数
│   ├── ts_function.py    # 时序函数
│   └── datasets/alpha_158.py  # Alpha 158 因子集
├── model/            # 预测模型
│   └── models/
│       ├── lasso_model.py   # Lasso 回归
│       ├── lgb_model.py     # LightGBM
│       └── mlp_model.py     # 多层感知机
├── strategy/         # 策略模板
│   └── backtesting.py       # 回测引擎
└── lab.py            # 投研流程管理
```

### 4.2 工作流程

1. **数据准备** → Dataset 模块加载历史数据
2. **特征工程** → 使用 Alpha 158 等因子计算特征
3. **模型训练** → Lasso/LightGBM/MLP 模型训练
4. **信号生成** → 模型预测生成交易信号
5. **策略回测** → Lab 模块执行回测分析

---

## 五、策略开发

### 5.1 CTA 策略模板

```python
from vnpy_ctastrategy import CtaTemplate, BarGenerator, ArrayManager

class MyStrategy(CtaTemplate):
    # 策略参数
    fast_window = 10
    slow_window = 20

    parameters = ["fast_window", "slow_window"]
    variables = ["fast_ma", "slow_ma"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()

    def on_init(self):
        self.load_bar(10)  # 加载历史数据初始化

    def on_bar(self, bar):
        self.bg.update_bar(bar)  # 合成更长周期K线

    def on_15min_bar(self, bar):
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 计算指标
        fast_ma = am.sma(self.fast_window)
        slow_ma = am.sma(self.slow_window)

        # 交易逻辑
        if fast_ma > slow_ma and self.pos == 0:
            self.buy(bar.close_price, 1)
        elif fast_ma < slow_ma and self.pos > 0:
            self.sell(bar.close_price, 1)
```

### 5.2 关键类说明

| 类 | 说明 |
|---|------|
| `CtaTemplate` | CTA 策略基类 |
| `BarGenerator` | K线合成器，Tick→1分钟→更长周期 |
| `ArrayManager` | K线时间序列管理，技术指标计算 |

### 5.3 交易函数

| 函数 | 说明 |
|------|------|
| `buy(price, volume)` | 买入开仓 |
| `sell(price, volume)` | 卖出平仓 |
| `short(price, volume)` | 卖出开仓 |
| `cover(price, volume)` | 买入平仓 |
| `cancel_all()` | 撤销所有委托 |

---

## 六、快速上手

### 6.1 启动流程

```python
from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

from vnpy_ctp import CtpGateway
from vnpy_ctastrategy import CtaStrategyApp

def main():
    qapp = create_qapp()

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 添加交易接口
    main_engine.add_gateway(CtpGateway)

    # 添加应用模块
    main_engine.add_app(CtaStrategyApp)

    # 启动 UI
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    qapp.exec()

if __name__ == "__main__":
    main()
```

### 6.2 配置文件位置

```
~/.vntrader/
├── vt_setting.json           # 全局配置
├── cta_strategy_setting.json # CTA 策略配置
├── cta_strategy_data.json    # 策略变量缓存
└── log/                      # 日志目录
```

---

## 七、扩展开发

### 7.1 自定义策略

放置位置：`~/.vntrader/strategies/`

### 7.2 自定义应用

继承 `BaseApp` 和 `BaseEngine`：

```python
from vnpy.trader.app import BaseApp
from vnpy.trader.engine import BaseEngine

class MyEngine(BaseEngine):
    def __init__(self, main_engine, event_engine):
        super().__init__(main_engine, event_engine, "my_engine")

class MyApp(BaseApp):
    app_name = "MyApp"
    engine_class = MyEngine
```

---

## 八、设计亮点

1. **事件驱动**：松耦合架构，易于扩展
2. **统一接口**：Gateway 抽象层屏蔽接口差异
3. **回测实盘一体**：同一策略代码，无缝切换
4. **插件化设计**：App 模块按需加载
5. **AI 集成**：vnpy.alpha 提供 ML 策略支持

---

*文档版本：基于 VeighNa 4.2.0*
