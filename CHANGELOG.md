# Changelog

## [0.1.0] - 2026-01-16

### Added
- Backpack 用户数据流支持 (`BackpackUserWS`)
- 实时订单成交事件订阅（订单更新和成交明细）
- 测试脚本 `subscribe_trades_backpack.py` 用于验证 Backpack 用户数据流
- ED25519 签名认证支持用户 WebSocket 流

### Changed
- 归档 Hyperliquid 和 Lighter 交易所实现到 `docs/archived/exchanges/`
- v0.1.0 版本专注于 Aster + Backpack 支持
- 更新 `get_client()` 工厂函数，仅支持 Aster 和 Backpack
- 更新 `get_user_ws_client()` 添加 Backpack 用户数据流支持

### Removed
- 从主代码库移除 Hyperliquid 和 Lighter（已归档，保留作为参考）

## [0.0.1] - 2026-01-11

### 新增
- 初始提交：统一交易客户端框架，集中公共基类、精度与错误处理。
- 内置交易所：Backpack、Aster、Hyperliquid（官方生成代码）以及 Lighter（本地封装 + 原生 signer）。
- 工厂函数 `get_client` 懒加载实例，保留 Backpack 别名兼容。

### 配置
- 代理由 `proxy_utils` 统一读取；支持 `LIGHTER_BASE_URL` 环境变量（默认 `https://mainnet.zklighter.elliot.ai`）。
- Lighter 需本地 signer 动态库与 `api_private_key`/`account_index`。
