# 归档的交易所实现

本目录包含已归档的交易所实现，这些交易所在 v0.1.0 版本中已被移除，但保留作为参考。

## 归档文件

- `hyperliquid.py` - Hyperliquid 交易所 REST API 实现
- `lighter.py` - Lighter 交易所 REST API 实现
- `lighter_signer.py` - Lighter 签名工具
- `lighter_client.py` - Lighter 客户端

## 归档原因

v0.1.0 版本专注于 Aster 和 Backpack 交易所的套利功能验证。Hyperliquid 和 Lighter 的实现在当前阶段不需要，因此被归档。

## 未来计划

这些交易所的实现可能会在未来版本中重新引入：

- v0.2.0: 根据套利实战经验优化架构
- v0.3.0: 考虑重新引入 Hyperliquid（如果需要）
- v1.0.0: 稳定版本，支持多个交易所

## 使用归档代码

如果需要使用这些交易所的实现，可以：

1. 将文件复制回 `api/` 目录
2. 在 `api/__init__.py` 中添加相应的导入和工厂函数支持
3. 安装必要的依赖（如 Lighter 的 signer 动态库）

## 注意事项

这些代码可能已经过时，使用前请：

- 检查交易所 API 文档是否有变更
- 测试功能是否正常
- 更新依赖库版本
