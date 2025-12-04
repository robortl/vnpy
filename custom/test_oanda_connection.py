#!/usr/bin/env python3
"""
OANDA 连接测试脚本

测试 API Token 和账户是否配置正确
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_oandapyv20_installed():
    """测试 oandapyV20 是否安装"""
    print("检查 oandapyV20 库...")
    try:
        from oandapyV20 import API
        print("  [OK] oandapyV20 已安装")
        return True
    except ImportError:
        print("  [FAIL] oandapyV20 未安装")
        print("  请运行: pip install oandapyV20")
        return False


def test_config_exists():
    """测试配置文件是否存在"""
    print("检查配置文件...")
    config_path = Path(__file__).parent / "config" / "oanda_config.json"

    if config_path.exists():
        print(f"  [OK] 配置文件存在: {config_path}")
        return True
    else:
        print(f"  [FAIL] 配置文件不存在: {config_path}")
        return False


def test_api_connection():
    """测试 API 连接"""
    print("测试 API 连接...")

    config_path = Path(__file__).parent / "config" / "oanda_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    from oandapyV20 import API
    from oandapyV20.exceptions import V20Error
    import oandapyV20.endpoints.accounts as accounts

    token = config["API Token"]
    account_id = config["Account ID"]
    server = config["服务器"]

    environment = "practice" if server == "Practice" else "live"

    try:
        api = API(access_token=token, environment=environment)

        # 测试获取账户信息
        r = accounts.AccountSummary(accountID=account_id)
        response = api.request(r)

        account_info = response.get("account", {})
        balance = account_info.get("balance", "N/A")
        currency = account_info.get("currency", "N/A")

        print(f"  [OK] API 连接成功")
        print(f"  账户余额: {balance} {currency}")
        return True

    except V20Error as e:
        print(f"  [FAIL] API 连接失败: {e}")
        return False


def test_instruments():
    """测试获取交易品种"""
    print("获取可交易品种...")

    config_path = Path(__file__).parent / "config" / "oanda_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    from oandapyV20 import API
    from oandapyV20.exceptions import V20Error
    import oandapyV20.endpoints.accounts as accounts

    token = config["API Token"]
    account_id = config["Account ID"]
    server = config["服务器"]

    environment = "practice" if server == "Practice" else "live"

    try:
        api = API(access_token=token, environment=environment)

        r = accounts.AccountInstruments(accountID=account_id)
        response = api.request(r)

        gold_instruments = []
        for inst in response.get("instruments", []):
            if inst["name"].startswith("XAU"):
                gold_instruments.append(inst["name"])

        print(f"  [OK] 黄金品种: {', '.join(gold_instruments)}")
        return True

    except V20Error as e:
        print(f"  [FAIL] 获取品种失败: {e}")
        return False


def main():
    print("=" * 50)
    print("OANDA 连接测试")
    print("=" * 50)

    results = []

    # 测试库安装
    results.append(test_oandapyv20_installed())

    # 测试配置文件
    results.append(test_config_exists())

    # 如果基础检查通过，测试 API
    if all(results):
        results.append(test_api_connection())
        results.append(test_instruments())

    print("=" * 50)
    if all(results):
        print("所有测试通过!")
    else:
        print("部分测试失败，请检查配置")
        sys.exit(1)


if __name__ == "__main__":
    main()
