# 自定义修改记录

记录对原有 vnpy 代码的修改，便于后续升级合并。

## 修改记录

### 2024-12-04

#### .gitignore
- 添加 `custom/config/*.json` 和 `custom/config/.env` 到忽略列表
- 原因：保护敏感配置信息不被提交

---

## 新增文件

所有新增文件均位于 `custom/` 目录，不影响原有代码：

```
custom/
├── __init__.py
├── run_oanda.py              # OANDA 启动脚本
├── test_oanda_connection.py  # 连接测试脚本
├── config/
│   ├── oanda_config.json     # OANDA 配置（git忽略）
│   └── .env                  # 环境变量（git忽略）
├── gateways/
│   ├── __init__.py
│   └── oanda/
│       ├── __init__.py
│       └── oanda_gateway.py  # OANDA Gateway 实现
├── docs/
│   └── CHANGES.md            # 本文件
├── strategies/               # 自定义策略（待开发）
├── apps/                     # 自定义应用（待开发）
└── utils/                    # 工具函数（待开发）
```
