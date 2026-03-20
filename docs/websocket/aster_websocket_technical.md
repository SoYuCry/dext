# Aster WebSocket 技术规范

## 连接信息

- **Market Data Endpoint:** `wss://fstream.asterdex.com/stream`
- **User Data Endpoint:** `wss://fstream.asterdex.com/ws/<listenKey>`
- **协议:** URL 聚合流（streams 参数）
- **REST API Base:** `https://fapi.asterdex.com`

## 客户端类型

Aster 提供三种 WebSocket 客户端，适用于不同场景：

### 1. AsterWS（增量更新流）

**用途：** 高频交易，最低延迟

**特点：**
- 仅推送变化的订单簿档位
- 延迟 <10ms
- 需要客户端维护完整订单簿状态

**订阅格式：**
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth/btcusdt@depth
```

### 2. AsterDepthWS（快照流，推荐）

**用途：** 通用场景，无需维护状态

**特点：**
- 每 250ms 推送完整订单簿快照
- 支持 5/10/20 档深度
- 开箱即用，无需初始化

**订阅格式：**
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth20
```

### 3. AsterUserWS（用户数据流）

**用途：** 账户监控、订单/持仓更新

**特点：**
- 需要 API Key 认证
- listenKey 机制（30分钟有效期）
- 自动保活

**订阅格式：**
```
wss://fstream.asterdex.com/ws/<listenKey>
```

## 市场数据流

### 增量更新流（@depth）

**URL:** `wss://fstream.asterdex.com/stream?streams={symbol}@depth`

**消息格式：**
```json
{
  "stream": "xauusdt@depth",
  "data": {
    "e": "depthUpdate",
    "E": 1768490299726,    // Event time (milliseconds)
    "T": 1768490299720,    // Transaction time (milliseconds)
    "s": "XAUUSDT",
    "U": 167043001,        // First update ID
    "u": 167043010,        // Final update ID
    "pu": 167043000,       // Previous final update ID
    "b": [                 // Bids to update
      ["2875.50", "1.5000"],
      ["2875.40", "0"]     // qty=0 表示删除
    ],
    "a": [                 // Asks to update
      ["2875.60", "2.0000"]
    ]
  }
}
```

**字段说明：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `e` | string | 事件类型 "depthUpdate" |
| `E` | int | 事件时间（毫秒） |
| `T` | int | 交易时间（毫秒） |
| `U` | int | 本批次第一个 update ID |
| `u` | int | 本批次最后一个 update ID |
| `pu` | int | 上一批次最后一个 update ID |

**序列校验：**
```python
# 验证连续性
assert data['U'] == last_pu + 1, "Missing updates detected"
last_pu = data['u']
```

### 快照流（@depth{level}）

**URL:** `wss://fstream.asterdex.com/stream?streams={symbol}@depth{level}`

**支持的 level:** 5, 10, 20

**消息格式：**
```json
{
  "stream": "xauusdt@depth20",
  "data": {
    "e": "depthUpdate",
    "E": 1768490299726,
    "T": 1768490299720,
    "s": "XAUUSDT",
    "b": [                 // 完整的买盘（最多20档）
      ["2875.50", "1.5000"],
      ["2875.49", "2.0000"],
      ...
    ],
    "a": [                 // 完整的卖盘（最多20档）
      ["2875.60", "2.0000"],
      ["2875.61", "1.0000"],
      ...
    ]
  }
}
```

**推送频率：** 250ms（固定）

**优势：**
- 无需初始化订单簿
- 无需处理增量更新逻辑
- 自动去除零数量档位

**劣势：**
- 延迟稍高（250ms 间隔）
- 带宽消耗大于增量流

## 用户数据流

### 认证流程

1. **创建 listenKey**
```bash
POST https://fapi.asterdex.com/fapi/v1/listenKey
Headers:
  X-MBX-APIKEY: <your_api_key>

Response:
{
  "listenKey": "pqia91ma19a5s61cv6a81va65sdf19v8a65a1a5s61cv6a81va65sdf19v8a65a1"
}
```

2. **连接 WebSocket**
```
wss://fstream.asterdex.com/ws/pqia91ma19a5s61cv6a81va65sdf19v8a65a1a5s61cv6a81va65sdf19v8a65a1
```

3. **保活（每30分钟）**
```bash
PUT https://fapi.asterdex.com/fapi/v1/listenKey?listenKey=<listenKey>
Headers:
  X-MBX-APIKEY: <your_api_key>
```

### 用户事件类型

#### ORDER_TRADE_UPDATE（订单更新）

```json
{
  "e": "ORDER_TRADE_UPDATE",
  "E": 1768490299726,
  "T": 1768490299720,
  "o": {
    "s": "XAUUSDT",
    "c": "client_order_id_123",
    "S": "BUY",
    "o": "LIMIT",
    "f": "GTC",
    "q": "1.5",
    "p": "2875.50",
    "ap": "0",
    "sp": "0",
    "x": "NEW",
    "X": "NEW",
    "i": 8886774,
    "l": "0",
    "z": "0",
    "L": "0",
    "N": "USDT",
    "n": "0",
    "T": 1768490299720,
    "t": 0,
    "b": "0",
    "a": "9.91",
    "m": false,
    "R": false,
    "wt": "CONTRACT_PRICE",
    "ot": "LIMIT",
    "ps": "BOTH",
    "cp": false,
    "rp": "0",
    "pP": false,
    "si": 0,
    "ss": 0
  }
}
```

**关键字段：**
| 字段 | 说明 |
|------|------|
| `o.s` | 交易对 |
| `o.i` | 订单 ID |
| `o.c` | 客户端订单 ID |
| `o.S` | 方向（BUY/SELL） |
| `o.X` | 订单状态（NEW/PARTIALLY_FILLED/FILLED/CANCELED/EXPIRED） |
| `o.x` | 执行类型（NEW/TRADE/CANCELED） |
| `o.q` | 原始数量 |
| `o.z` | 已成交数量 |
| `o.p` | 委托价格 |
| `o.ap` | 平均成交价 |

#### ACCOUNT_UPDATE（账户更新）

```json
{
  "e": "ACCOUNT_UPDATE",
  "E": 1768490299726,
  "T": 1768490299720,
  "a": {
    "m": "ORDER",
    "B": [
      {
        "a": "USDT",
        "wb": "122624.12345678",
        "cw": "100.12345678",
        "bc": "50.12345678"
      }
    ],
    "P": [
      {
        "s": "XAUUSDT",
        "pa": "1.5",
        "ep": "2875.50",
        "cr": "200",
        "up": "100.12345678",
        "mt": "cross",
        "iw": "0.00000000",
        "ps": "BOTH"
      }
    ]
  }
}
```

**关键字段：**
| 字段 | 说明 |
|------|------|
| `a.B` | 余额变化 |
| `a.P` | 持仓变化 |
| `P.s` | 交易对 |
| `P.pa` | 持仓数量 |
| `P.ep` | 开仓均价 |
| `P.up` | 未实现盈亏 |

#### MARGIN_CALL（强平警告）

```json
{
  "e": "MARGIN_CALL",
  "E": 1768490299726,
  "cw": "3.16812045",
  "p": [
    {
      "s": "XAUUSDT",
      "ps": "LONG",
      "pa": "1.5",
      "mt": "CROSSED",
      "iw": "0",
      "mp": "2850.00",
      "up": "-50.12345678",
      "mm": "2.72556716"
    }
  ]
}
```

#### listenKeyExpired（密钥过期）

```json
{
  "e": "listenKeyExpired",
  "E": 1768490299726
}
```

收到此事件后需要：
1. 断开当前连接
2. 创建新的 listenKey
3. 重新连接

## 时间戳格式

**Aster 使用毫秒时间戳**（10^-3秒）

```python
# 转换为秒
ts_sec = ts_exchange / 1_000

# 转换为 datetime
from datetime import datetime
dt = datetime.fromtimestamp(ts_exchange / 1_000)
```

**示例：**
- `ts_exchange = 1768490299726`
- 对应时间：`2026-01-15 11:18:19.726 UTC`

## URL 聚合流机制

Aster 通过 URL 参数聚合多个流，无需发送订阅消息。

### 单个流
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth20
```

### 多个流（用 `/` 分隔）
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth20/btcusdt@depth20/ethusdt@depth
```

### 支持的流类型
- `{symbol}@depth` - 增量更新
- `{symbol}@depth5` - 5档快照
- `{symbol}@depth10` - 10档快照
- `{symbol}@depth20` - 20档快照

## 错误处理

### 连接失败

**常见原因：**
- 无效的 listenKey
- listenKey 过期
- 网络问题

**处理策略：**
```python
try:
    await ws.run_forever()
except Exception as e:
    if "listenKey" in str(e):
        # 重新创建 listenKey
        new_listen_key = create_listen_key()
        ws = AsterUserWS(api_key=api_key, ...)
        await ws.run_forever()
    else:
        # 其他错误，等待后重连
        await asyncio.sleep(3)
```

### listenKey 保活失败

保活请求失败不会立即断开连接，但 60 分钟后 listenKey 会过期。

**最佳实践：**
- 保活间隔设为 30 分钟（默认）
- 保活失败时记录日志
- 连续失败 3 次后主动重连

## 性能特征

### 延迟

| 客户端类型 | 典型延迟 |
|-----------|---------|
| AsterWS (增量) | 5-10ms |
| AsterDepthWS (快照) | 250ms (固定间隔) |
| AsterUserWS | 10-20ms |

### 带宽消耗

**单交易对（XAUUSDT）：**
- AsterWS: ~15 KB/s
- AsterDepthWS (depth20): ~8 KB/s（固定频率更低）
- AsterUserWS: ~2 KB/s（低频事件）

### 消息频率

| 流类型 | 频率 |
|--------|------|
| @depth | 不定（增量推送） |
| @depth5/10/20 | 固定 250ms（4次/秒） |
| 用户流 | 事件驱动 |

## 完整示例

### 快照流（推荐用法）

```python
from exchanges.ws.aster import AsterDepthWS

async def handle_depth(event):
    symbol = event['symbol']
    bids = event['bids']  # 已排序，最优价格在前
    asks = event['asks']

    if bids and asks:
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        print(f"{symbol}: {best_bid} / {best_ask}")

ws = AsterDepthWS(
    symbols=["xauusdt", "btcusdt"],
    on_event=handle_depth,
    depth_level=20
)

await ws.run_forever()
```

### 增量流（高频交易）

```python
from exchanges.ws.aster import AsterWS

# 维护订单簿状态
orderbook = {"bids": {}, "asks": {}}

async def handle_incremental(event):
    # 应用增量更新
    for price, qty in event['bids']:
        if qty == 0:
            orderbook['bids'].pop(price, None)
        else:
            orderbook['bids'][price] = qty

    for price, qty in event['asks']:
        if qty == 0:
            orderbook['asks'].pop(price, None)
        else:
            orderbook['asks'][price] = qty

    # 获取最优价
    best_bid = max(orderbook['bids'].keys()) if orderbook['bids'] else None
    best_ask = min(orderbook['asks'].keys()) if orderbook['asks'] else None

ws = AsterWS(
    symbols=["xauusdt"],
    on_event=handle_incremental
)

await ws.run_forever()
```

### 用户数据流

```python
from exchanges.ws.aster import AsterUserWS

async def handle_user_event(event):
    event_type = event['event_type']

    if event_type == 'ORDER_TRADE_UPDATE':
        order_id = event['order_id']
        status = event['status']
        print(f"Order {order_id}: {status}")

    elif event_type == 'ACCOUNT_UPDATE':
        print(f"Account updated: {event['account']}")

    elif event_type == 'MARGIN_CALL':
        print("MARGIN CALL WARNING!")

ws = AsterUserWS(
    api_key="your_api_key",
    on_event=handle_user_event
)

await ws.run_forever()
```

### 多流组合

```python
import asyncio
from exchanges.ws.aster import AsterDepthWS, AsterUserWS

async def main():
    # 市场数据
    market_ws = AsterDepthWS(
        symbols=["xauusdt"],
        on_event=handle_market,
        depth_level=20
    )

    # 用户数据
    user_ws = AsterUserWS(
        api_key="your_api_key",
        on_event=handle_user
    )

    # 并发运行
    await asyncio.gather(
        market_ws.run_forever(),
        user_ws.run_forever()
    )

asyncio.run(main())
```

## 限制

- **listenKey 有效期：** 60 分钟（需每 30 分钟保活）
- **最大订阅数：** 单连接最多 200 个流
- **符号格式：** 小写（如 `xauusdt`），与 Backpack 不同
- **快照流固定频率：** 250ms，无法调整

## 与 Backpack 的差异

| 特性 | Aster | Backpack |
|------|-------|----------|
| 订阅方式 | URL 聚合 | JSON-RPC SUBSCRIBE |
| 快照流 | 内置（@depth20） | 无，需 REST API |
| 时间戳单位 | 毫秒 | 微秒 |
| 符号大小写 | 小写 | 大写 |
| 心跳机制 | 无（listenKey 保活） | ping/pong |
| 用户流认证 | listenKey | 签名 |

## 参考

- [Aster API 文档](https://docs.asterdex.com/)
- [示例脚本](../subscribe_xau_Aster.py)
- [客户端实现](../api/ws/aster.py)
