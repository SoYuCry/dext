# 架构说明（统一交易客户端）

本仓库精简为「纯交易 API 客户端」，提供统一的下单/行情接口（`fetch_*`、`create_order`、`cancel_order` 等），不包含策略、CLI、Web 或数据库组件。

**v0.1.0 支持的交易所：Aster, Backpack**

## 模块分层

- `api/base/`
  - `exchange.py`：通用交易所基类，内置精度与安全取值工具
  - `types.py`：统一数据结构
  - `errors.py`：统一错误层级
  - `precise.py`、`decimal_to_precision.py`：精度运算工具
- 单文件交易所实现
  - `api/backpack.py`：基于官方生成代码
  - `api/aster.py`：本地封装（HMAC 签名）
- WebSocket 行情和用户数据流
  - `api/ws/base.py`：基础 WebSocket 客户端
  - `api/ws/backpack.py`：Backpack 订单簿订阅和用户数据流（订单、成交）
  - `api/ws/aster.py`：Aster 订单簿订阅和用户数据流
- 其他：`api/auth.py`（Backpack 签名助手）、`api/proxy_utils.py`（代理配置）、`api/__init__.py`（工厂 `get_client`）、`config.py`（环境变量配置）、`logger.py`（日志封装）

## 归档的交易所

v0.1.0 版本将以下交易所实现归档到 `docs/archived/exchanges/`：

- Hyperliquid - 官方生成代码
- Lighter - 本地封装 + 原生签名库

这些交易所可能在未来版本中重新引入。

## 依赖

- 已内置基类与精度工具，无需额外核心依赖
- 其他：`requests`、`PyNaCl`（Backpack 签名）、`cryptography`（ed25519）、`websockets`（WebSocket 客户端）等，详见 `requirements.txt`

## 使用方式

### REST API

```python
from api import get_client

client = get_client("backpack", {"apiKey": "...", "secret": "..."})
ticker = client.fetch_ticker("SOL/USDC")
order = client.create_order("SOL/USDC", "limit", "buy", 1, 100)
client.cancel_order(order["id"], "SOL/USDC")

# Aster
aster = get_client("aster", {"apiKey": "...", "secret": "..."})
print(aster.fetch_markets())
```

### WebSocket 订单簿订阅

```python
import asyncio
from api.ws import get_ws_client

async def handle(event):
    print(event)

# Backpack
ws = get_ws_client("backpack", ["PAXG_USDC_PERP"], handle, include_depth=True)
asyncio.run(ws.run_forever())

# Aster
from api.ws import AsterDepthWS
ws = AsterDepthWS(["xauusdt"], handle, depth_level=20)
asyncio.run(ws.run_forever())
```

### WebSocket 用户数据流（订单成交）

```python
import asyncio
from api.ws import get_user_ws_client

async def handle(event):
    print(event)  # 订单更新、成交明细

# Backpack 用户数据流
ws = get_user_ws_client("backpack", handle, api_key="...", secret="...")
asyncio.run(ws.run_forever())

# Aster 用户数据流
ws = get_user_ws_client("aster", handle, api_key="...")
asyncio.run(ws.run_forever())
```

## 设计取向

- **Backpack**: 使用官方提供的生成代码，保持端点一致。支持 REST API、订单簿 WebSocket 和用户数据流（订单、成交）。
- **Aster**: 本地封装，签名逻辑与交易所 REST 兼容（HMAC）。支持 REST API、订单簿 WebSocket 和用户数据流。
- 不包含策略/界面/数据库，仅保留 REST 客户端和 WebSocket 能力，便于脚本化下单或作为依赖集成。

## v0.1.0 特性

- 专注于 Aster + Backpack 套利场景
- Backpack 用户数据流支持（实时订单成交）
- 清晰的代码结构，易于维护和扩展
