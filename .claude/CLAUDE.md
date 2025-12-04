# VeighNa (vnpy) 开发指南

本项目是 vnpy 的 fork 版本，为了便于后续升级和维护，请遵循以下规则。

> 相关文档：
> - [ROLES.md](./ROLES.md) - 开发指导角色定义
> - [docs_custom/README.md](../docs_custom/README.md) - 项目快速理解指南

---

# 开发规则 - 最小侵入原则

## 核心原则

**最小侵入接入** - 尽量减少对原有代码的修改，便于后续与上游同步。

## 目录规范

1. **新增代码**：放置在 `custom/` 目录下
   - `custom/strategies/` - 自定义策略
   - `custom/apps/` - 自定义应用模块
   - `custom/utils/` - 自定义工具函数
   - `custom/gateways/` - 自定义网关接口

2. **新增文档**：放置在 `custom/docs/` 目录下

3. **配置文件**：放置在 `custom/config/` 目录下

## 修改原有代码的原则

如果必须修改原有代码：

1. **优先使用扩展机制**：如继承、装饰器、钩子等
2. **标记修改点**：使用注释标记 `# [CUSTOM]` 开头，便于后续升级时识别
3. **保持最小改动**：只修改必要的部分，不做额外重构
4. **记录变更**：在 `custom/docs/CHANGES.md` 中记录对原有代码的修改

## 示例

```python
# 推荐：在 custom 目录下扩展
# custom/strategies/my_strategy.py
from vnpy_ctastrategy import CtaTemplate

class MyStrategy(CtaTemplate):
    ...

# 如必须修改原代码，添加标记
# [CUSTOM] 添加自定义功能支持
some_custom_code()
# [/CUSTOM]
```

## 升级流程

1. 拉取上游更新
2. 搜索 `[CUSTOM]` 标记，确认冲突
3. 合并变更，保留 custom 目录内容
4. 测试验证
