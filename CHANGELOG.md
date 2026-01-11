# Changelog

## [0.1.0] - 2026-01-11

### 新增
- 初始提交：统一交易客户端框架，集中公共基类、精度与错误处理。
- 内置交易所：Backpack、Aster、Hyperliquid（官方生成代码）以及 Lighter（本地封装 + 原生 signer）。
- 工厂函数 `get_client` 懒加载实例，保留 Backpack 别名兼容。

### 配置
- 代理由 `proxy_utils` 统一读取；支持 `LIGHTER_BASE_URL` 环境变量（默认 `https://mainnet.zklighter.elliot.ai`）。
- Lighter 需本地 signer 动态库与 `api_private_key`/`account_index`。
