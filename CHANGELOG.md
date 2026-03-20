# Changelog

## [0.2.0] - 2026-01-25

### Major Refactoring - REST API Unified Architecture

重构 REST API 层为统一架构，提升代码质量和可维护性。

#### Changed
- **统一请求处理**: 所有交易所使用 `_request()` 方法处理 REST API 请求
- **两层错误处理**:
  - Layer 1: `_handle_http_error()` 处理 HTTP 状态码 (400, 401, 404, 429, 5xx)
  - Layer 2: `parse_error()` 处理交易所特定业务错误
- **端点配置分离**: API 端点定义从 `abstract/` 迁移到 `exchanges/endpoints/`
  - Backpack: 112 个端点
  - Aster: 41 个端点
  - Lighter: 30 个端点
  - Variational: 18 个端点

#### Improved
- **错误处理覆盖率提升**:
  - Aster: 从 8 个通用错误 → 40+ 精确错误码映射
  - Backpack: 完善的 Ed25519 签名文档
  - 统一的异常类型 (InvalidOrder, InsufficientFunds, OrderNotFound 等)
- **代码质量**:
  - 减少重复代码（错误处理集中到基类）
  - 改进 API 方法文档和注释
  - 精度处理 bug 修复（手动处理 TICK_SIZE 模式）

#### Added
- `exchanges/base/exchange.py`: 新增 `_request()` 和 `_handle_http_error()` 方法
- `exchanges/endpoints/`: 新增端点配置层
- 每个交易所新增 `parse_error()` 方法

#### Documentation
- 更新 CLAUDE.md 添加 REST API 架构说明
- 更新 ARCHITECTURE.md, STRUCTURE.md 反映新结构
- 更新所有交易所文档 (backpack.md, aster.md, lighter.md, variational.md)
- 文档重构为两层结构 (根目录核心文档 + 专题子目录)

#### Technical Details
**Before (旧实现)**:
- 每个交易所独立实现 `request()` 方法
- 错误处理分散、不一致
- API 路径定义混乱（如 Aster 路径重复）
- 缺少必填参数检查（如 timeInForce）

**After (新架构)**:
- 统一的 `_request()` 生命周期
- 两层错误处理保证全覆盖
- 声明式端点配置（Entry 对象）
- 完善的参数验证和默认值

参考: `docs/exchanges/common-pitfalls.md` - 设计模式最佳实践

---

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
