# 架构说明（统一交易客户端）

本仓库精简为「纯交易 API 客户端」，提供统一的下单/行情接口（`fetch_*`、`create_order`、`cancel_order` 等），不包含策略、CLI、Web 或数据库组件。

## 模块分层

- `api/base/`
  - `exchange.py`：通用交易所基类，内置精度与安全取值工具
  - `types.py`：统一数据结构
  - `errors.py`：统一错误层级
  - `precise.py`、`decimal_to_precision.py`：精度运算工具
- 单文件交易所实现
  - `api/backpack.py`：基于官方生成代码
  - `api/aster.py`：本地封装（HMAC 签名）
  - `api/hyperliquid.py`：基于官方生成代码
  - `api/lighter.py`：本地封装 + 原生签名库
- 其他：`api/auth.py`（Backpack 签名助手）、`api/proxy_utils.py`（代理配置）、`api/__init__.py`（工厂 `get_client`）、`config.py`（环境变量配置）、`logger.py`（日志封装）

## 依赖

- 已内置基类与精度工具，无需额外核心依赖
- 其他：`requests`、`PyNaCl`（Backpack 签名）、`cryptography`（ed25519）等，详见 `requirements.txt`
- Lighter 需本地 signer 动态库（见 `Signer/Lighter` 下的 `.dylib/.so/.dll`），并提供 `api_private_key` 与 `account_index`

## 使用方式

```python
from api import get_client

client = get_client("backpack", {"apiKey": "...", "secret": "..."})
ticker = client.fetch_ticker("SOL/USDC")
order = client.create_order("SOL/USDC", "limit", "buy", 1, 100)
client.cancel_order(order["id"], "SOL/USDC")

# Hyperliquid
hyper = get_client("hyperliquid", {"walletAddress": "...", "privateKey": "...", "password": "..."})
print(hyper.fetch_markets())

# Lighter（需本地 signer 动态库）
lighter = get_client(
    "lighter",
    {
        "base_url": "https://mainnet.zklighter.elliot.ai",
        "api_private_key": "<hex private key>",
        "account_index": 0,
        "api_key_index": 0,
        "signer_lib_dir": "Signer/Lighter",
    },
)
print(lighter.fetch_markets())
```

其他交易所：`get_client("aster"|"lighter"|"hyperliquid", config)`；配置键沿用现有命名（如 `apiKey`/`secret`、`api_private_key`、`passphrase` 等）。

## 设计取向

- Backpack / Hyperliquid：使用官方提供的生成代码，保持端点一致。
- Aster / Lighter：本地封装，签名逻辑与交易所 REST 兼容（Aster HMAC、Lighter signer）。
- 不包含策略/界面/数据库，仅保留 REST 客户端能力，便于脚本化下单或作为依赖集成。
