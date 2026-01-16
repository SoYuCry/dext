# 文件结构总览

v0.1.0 版本专注于 Aster + Backpack 交易所支持。

## 当前结构（v0.1.0）

```
api/
├── __init__.py              # get_client(): aster, backpack
├── aster.py                 # Aster REST API
├── backpack.py              # Backpack REST API
├── auth.py                  # Backpack 签名工具
├── proxy_utils.py           # 代理配置
├── base/                    # 通用基类/类型/错误
│   ├── exchange.py
│   ├── types.py
│   ├── errors.py
│   ├── precise.py
│   └── decimal_to_precision.py
└── ws/                      # WebSocket 客户端
    ├── __init__.py          # get_ws_client(), get_user_ws_client()
    ├── base.py              # WebsocketClient 基类
    ├── aster.py             # AsterWS, AsterDepthWS, AsterUserWS
    └── backpack.py          # BackpackWS, BackpackUserWS

docs/
├── plans/                   # 设计文档
│   ├── 2026-01-16-v0.1.0-cleanup-and-backpack-userws-design.md
│   └── ...
└── archived/
    └── exchanges/           # 归档的交易所实现
        ├── README.md
        ├── hyperliquid.py
        ├── lighter.py
        ├── lighter_signer.py
        └── lighter_client.py

# 测试脚本
subscribe_paxg_BackPack.py   # Backpack 订单簿订阅测试
subscribe_xau_Aster.py       # Aster 订单簿订阅测试
subscribe_trades_backpack.py # Backpack 用户数据流测试

config.py                    # 环境变量配置
logger.py                    # 日志封装
README.md
ARCHITECTURE.md
STRUCTURE.md
CHANGELOG.md
requirements.txt
```

## 归档的交易所

以下交易所实现已归档到 `docs/archived/exchanges/`：

- **Hyperliquid** (`hyperliquid.py`) - 官方生成代码
- **Lighter** (`lighter.py`, `lighter_signer.py`, `lighter_client.py`) - 本地封装 + 原生 signer

这些交易所可能在未来版本中重新引入。

## 在策略项目中使用（推荐：可编辑安装）

在 `StrategyA` 的虚拟环境中执行：

```bash
pip install -e /Users/liuc/Documents/Projects/dext
```

然后在策略代码里直接：

```python
from dext import get_client

# REST API
client = get_client("aster", config={...})

# WebSocket 订单簿
from api.ws import get_ws_client
ws = get_ws_client("backpack", ["PAXG_USDC_PERP"], handler)

# WebSocket 用户数据流（订单成交）
from api.ws import get_user_ws_client
ws = get_user_ws_client("backpack", handler, api_key="...", secret="...")
```

## v0.1.0 新增功能

- **Backpack 用户数据流**: 实时订单成交监控
- **测试脚本**: `subscribe_trades_backpack.py`
- **代码清理**: 归档无关交易所，聚焦核心功能
