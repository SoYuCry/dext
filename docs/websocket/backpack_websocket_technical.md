# Backpack WebSocket 技术规范

## 连接信息

- **Endpoint:** `wss://ws.backpack.exchange`
- **协议:** JSON-RPC style (SUBSCRIBE/UNSUBSCRIBE)
- **认证:** 私有流需要签名（公开流无需认证）

## 订阅协议

### 公开流订阅

```json
{
  "method": "SUBSCRIBE",
  "params": [
    "bookTicker.PAXG_USDC_PERP",
    "depth.PAXG_USDC_PERP"
  ]
}
```

### 私有流订阅（需签名）

```json
{
  "method": "SUBSCRIBE",
  "params": ["account.orderUpdate.BTC_USDC"],
  "signature": [
    "<api_key>",
    "<signature>",
    "<timestamp>",
    "<window>"
  ]
}
```

**签名生成：**
```python
sign_message = f"instruction=subscribe&timestamp={timestamp}&window={window}"
signature = hmac.new(secret_key.encode(), sign_message.encode(), hashlib.sha256).hexdigest()
```

## 数据流

### bookTicker（BBO）

**订阅：** `bookTicker.{SYMBOL}`

**消息格式：**
```json
{
  "stream": "bookTicker.PAXG_USDC_PERP",
  "data": {
    "e": "bookTicker",
    "s": "PAXG_USDC_PERP",
    "b": "4621.56",      // Best bid price
    "B": "0.0044",       // Best bid quantity
    "a": "4621.57",      // Best ask price
    "A": "4.6586",       // Best ask quantity
    "T": 1768490299726564,  // Transaction time (microseconds)
    "E": 1768490299730050,  // Event time (microseconds)
    "u": 167043030       // Update ID
  }
}
```

**字段说明：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `b` | string | 最佳买价 |
| `B` | string | 最佳买量 |
| `a` | string | 最佳卖价 |
| `A` | string | 最佳卖量 |
| `T` | int | 交易时间（微秒） |
| `E` | int | 事件时间（微秒） |
| `u` | int | 更新序号 |

**更新频率：** 每次最优价格变化时推送（通常 >100/s）

### depth（L2 增量更新）

**订阅：** `depth.{SYMBOL}`

**消息格式：**
```json
{
  "stream": "depth.PAXG_USDC_PERP",
  "data": {
    "e": "depth",
    "s": "PAXG_USDC_PERP",
    "T": 1768490299729799,
    "E": 1768490299734522,
    "U": 167043031,      // First update ID
    "u": 167043031,      // Final update ID
    "b": [               // Bids to update
      ["4621.56", "1.5000"],
      ["4621.50", "0"]   // qty=0 表示删除此档位
    ],
    "a": [               // Asks to update
      ["4621.57", "4.9082"]
    ]
  }
}
```

**增量更新规则：**
- `qty > 0`: 更新或新增该价位
- `qty = 0`: 删除该价位
- 需要客户端维护完整订单簿状态

**Update ID 序列：**
- 严格递增
- 用于检测丢包（`u != last_u + 1` 表示丢包）
- 丢包后需重新获取完整订单簿快照

### 订单簿状态维护

```python
orderbook = {"bids": {}, "asks": {}}  # price -> qty

def update_orderbook(data):
    for price_str, qty_str in data.get("b", []):
        price = float(price_str)
        qty = float(qty_str)
        if qty == 0:
            orderbook["bids"].pop(price, None)
        else:
            orderbook["bids"][price] = qty

    for price_str, qty_str in data.get("a", []):
        price = float(price_str)
        qty = float(qty_str)
        if qty == 0:
            orderbook["asks"].pop(price, None)
        else:
            orderbook["asks"][price] = qty
```

## 心跳机制

### Ping/Pong

**服务端发送：**
```json
{"ping": 1768490299726}
```

**客户端响应：**
```json
{"pong": 1768490299726}
```

**超时时间：** 30秒未收到 ping 视为连接断开

## 时间戳格式

**重要：** Backpack 使用**微秒时间戳**（10^-6秒）

```python
# 转换为秒
ts_sec = ts_exchange / 1_000_000

# 转换为 datetime
from datetime import datetime
dt = datetime.fromtimestamp(ts_exchange / 1_000_000)
```

**示例：**
- `ts_exchange = 1768490299726564`
- 对应时间：`2026-01-15 11:18:19.726564 UTC`

## 错误处理

### 订阅失败

服务端不会对订阅请求返回确认或错误，需通过以下方式验证：
1. 检查是否收到对应 stream 的消息
2. 超时未收到则认为订阅失败

### 连接断开

**常见原因：**
- 网络中断
- 心跳超时（30s）
- 服务端维护

**处理策略：**
- 自动重连（指数退避：3s, 6s, 12s, ...）
- 重连后重新订阅所有流
- 订阅 depth 流后重新获取订单簿快照

## 性能特征

### 延迟

| 项目 | 典型值 |
|------|--------|
| bookTicker 延迟 | 1-3ms |
| depth 延迟 | 2-5ms |
| 心跳间隔 | ~30s |

### 带宽消耗

**单交易对（PAXG_USDC_PERP）：**
- 仅 bookTicker: ~8 KB/s
- bookTicker + depth: ~30 KB/s

**多交易对（10个交易对）：**
- 仅 bookTicker: ~80 KB/s
- bookTicker + depth: ~300 KB/s

### 消息频率

| 流类型 | 典型频率 | 峰值频率 |
|--------|---------|---------|
| bookTicker | 50-100/s | 200/s |
| depth | 20-50/s | 100/s |

## 完整示例

### 订阅 BBO

```python
from exchanges.ws.backpack import BackpackWS

async def handle_bbo(event):
    if event['stream'] != 'bbo':
        return

    bid_price, bid_qty = event['bids'][0]
    ask_price, ask_qty = event['asks'][0]
    spread = ask_price - bid_price

    print(f"{event['symbol']}: {bid_price} / {ask_price}, spread={spread:.2f}")

ws = BackpackWS(
    symbols=["PAXG_USDC_PERP", "BTC_USDC"],
    on_event=handle_bbo,
    include_depth=False
)

await ws.run_forever()
```

### 订阅 BBO + L2

```python
from exchanges.ws.backpack import BackpackWS

async def handle_market_data(event):
    if event['stream'] == 'bbo':
        # 更新价格显示
        update_ticker(event)
    elif event['stream'] == 'l2':
        # 更新订单簿
        update_orderbook(event)

ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    on_event=handle_market_data,
    include_depth=True
)

await ws.run_forever()
```

### 延迟监控

```python
import time

async def monitor_latency(event):
    ts_exchange_sec = event['ts_exchange'] / 1_000_000
    ts_local_sec = event['ts_local'] / 1_000
    latency_ms = (ts_local_sec - ts_exchange_sec) * 1000

    if latency_ms > 50:
        print(f"High latency: {latency_ms:.1f}ms")
```

## 限制

- **无明确的订阅确认机制**：需要通过收到消息来验证订阅成功
- **无订单簿快照 API**：depth 流只推送增量，需要通过 REST API 获取初始快照
- **符号格式严格**：必须使用大写（如 `PAXG_USDC_PERP`），否则订阅失败

## 与 REST API 配合

### 获取订单簿快照

```python
import requests

response = requests.get(
    "https://api.backpack.exchange/api/v1/depth",
    params={"symbol": "PAXG_USDC_PERP"}
)
snapshot = response.json()

# 初始化订单簿
orderbook = {
    "bids": {float(p): float(q) for p, q in snapshot["bids"]},
    "asks": {float(p): float(q) for p, q in snapshot["asks"]}
}

# 然后应用 WebSocket 增量更新
```

## 参考

- [Backpack API 文档](https://docs.backpack.exchange/)
- [示例脚本](../subscribe_paxg.py)
- [客户端实现](../api/ws/backpack.py)
