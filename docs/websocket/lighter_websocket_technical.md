# Lighter WebSocket 技术规范

## 连接信息

- **WebSocket Endpoint:** `wss://mainnet.zklighter.elliot.ai/stream`
- **REST API Base:** `https://mainnet.zklighter.elliot.ai`
- **协议:** JSON-based subscription
- **官方文档:** [https://docs.lighter.xyz](https://docs.lighter.xyz)
- **Python SDK:** [https://github.com/elliottech/lighter-python](https://github.com/elliottech/lighter-python)

## 客户端类型

Lighter 提供单一 WebSocket 客户端，支持多种订阅类型：

### LighterWS（统一客户端）

**用途:** 市场数据和账户订单更新

**特点:**
- 支持订单簿快照和增量更新
- 支持账户订单订阅（需认证）
- 自动序列验证和完整性检查
- 自动重连机制

**WebSocket URL:**
```
wss://mainnet.zklighter.elliot.ai/stream
```

## 订阅流

### 1. 订单簿流（公开数据）

**订阅格式:**
```json
{
  "type": "subscribe",
  "channel": "order_book/{market_index}"
}
```

**示例:**
```json
{
  "type": "subscribe",
  "channel": "order_book/0"
}
```

### 2. 账户订单流（私有数据，需认证）

**订阅格式:**
```json
{
  "type": "subscribe",
  "channel": "account_orders/{market_index}/{account_index}",
  "auth": "<auth_token>"
}
```

**认证令牌生成:**
```python
from lighter import SignerClient

client = SignerClient(
    url="https://mainnet.zklighter.elliot.ai",
    account_index=0,
    api_private_keys={0: "your_private_key"}
)

auth_token, err = client.create_auth_token_with_expiry(api_key_index=0)
```

**令牌有效期:** 10 分钟

## 消息格式

### 订单簿快照（subscribed/order_book）

**初始订阅响应:**
```json
{
  "type": "subscribed/order_book",
  "order_book": {
    "code": "ETH_USDC",
    "offset": 12345,
    "bids": [
      {"price": "2500.50", "size": "1.5"},
      {"price": "2500.00", "size": "2.0"}
    ],
    "asks": [
      {"price": "2501.00", "size": "1.0"},
      {"price": "2501.50", "size": "3.0"}
    ]
  }
}
```

**字段说明:**
| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 消息类型 "subscribed/order_book" |
| `order_book.code` | string | 市场代码 |
| `order_book.offset` | int | 序列号，用于验证更新连续性 |
| `order_book.bids` | array | 买盘价格档位 |
| `order_book.asks` | array | 卖盘价格档位 |

### 订单簿增量更新（update/order_book）

**更新消息:**
```json
{
  "type": "update/order_book",
  "order_book": {
    "code": "ETH_USDC",
    "offset": 12346,
    "bids": [
      {"price": "2500.50", "size": "2.0"},
      {"price": "2499.00", "size": "0"}
    ],
    "asks": [
      {"price": "2501.00", "size": "0.5"}
    ]
  }
}
```

**更新规则:**
- `size > 0`: 更新或新增该价位
- `size = 0`: 删除该价位
- `offset` 必须连续递增（offset_new = offset_old + 1）

**序列验证:**
```python
if new_offset != last_offset + 1:
    # 检测到序列间隙，需要重新订阅获取快照
    logger.warning(f"Sequence gap: expected {last_offset + 1}, got {new_offset}")
```

### 账户订单更新（update/account_orders）

**消息格式:**
```json
{
  "type": "update/account_orders",
  "orders": {
    "0": [
      {
        "order_index": 123456,
        "client_order_index": 789,
        "market_index": 0,
        "is_ask": false,
        "price": "2500.00",
        "initial_base_amount": "1.0",
        "filled_base_amount": "0.5",
        "remaining_base_amount": "0.5",
        "status": "OPEN",
        "reduce_only": false
      }
    ]
  }
}
```

**订单状态:**
- `OPEN` - 订单已提交，等待成交
- `FILLED` - 订单完全成交
- `CANCELED` - 订单已取消
- `PARTIALLY_FILLED` - 订单部分成交（通过 filled_base_amount > 0 判断）

## 心跳机制

### Ping/Pong

**服务端发送:**
```json
{"type": "ping"}
```

**客户端响应:**
```json
{"type": "pong"}
```

**超时时间:** 建议 30 秒内响应

## 订单簿状态维护

### 初始化

1. 连接 WebSocket
2. 发送订阅消息
3. 接收 `subscribed/order_book` 快照
4. 记录初始 `offset`
5. 构建完整订单簿状态

### 增量更新

```python
orderbook = {"bids": {}, "asks": {}}
last_offset = None

def handle_snapshot(data):
    global last_offset
    orderbook["bids"].clear()
    orderbook["asks"].clear()
    
    order_book = data.get("order_book", {})
    last_offset = order_book.get("offset")
    
    for bid in order_book.get("bids", []):
        price = float(bid["price"])
        size = float(bid["size"])
        if size > 0:
            orderbook["bids"][price] = size

def handle_update(data):
    global last_offset
    order_book = data.get("order_book", {})
    new_offset = order_book.get("offset")
    
    # 验证序列
    if last_offset is not None and new_offset != last_offset + 1:
        # 序列间隙，需要重新订阅
        return False
    
    last_offset = new_offset
    
    # 应用更新
    for bid in order_book.get("bids", []):
        price = float(bid["price"])
        size = float(bid["size"])
        if size == 0:
            orderbook["bids"].pop(price, None)
        else:
            orderbook["bids"][price] = size
    
    return True
```

### 完整性验证

```python
def validate_orderbook():
    if not orderbook["bids"] or not orderbook["asks"]:
        return True
    
    best_bid = max(orderbook["bids"].keys())
    best_ask = min(orderbook["asks"].keys())
    
    if best_bid >= best_ask:
        logger.error(f"Invalid orderbook: bid={best_bid} >= ask={best_ask}")
        return False
    
    return True
```

## 错误处理

### 序列间隙

**检测:**
- `offset` 不连续（跳过某些更新）

**处理:**
1. 记录警告日志
2. 取消订阅当前流
3. 等待 1 秒
4. 重新订阅获取新快照

```python
async def request_fresh_snapshot(ws, market_index):
    # 取消订阅
    await ws.send(json.dumps({
        "type": "unsubscribe",
        "channel": f"order_book/{market_index}"
    }))
    
    await asyncio.sleep(1)
    
    # 重新订阅
    await ws.send(json.dumps({
        "type": "subscribe",
        "channel": f"order_book/{market_index}"
    }))
```

### 连接断开

**常见原因:**
- 网络中断
- 服务端维护
- 认证令牌过期（账户订单流）

**处理策略:**
- 自动重连（指数退避：1s, 2s, 4s, ..., 最大 30s）
- 重连后重新订阅所有流
- 账户订单流需重新生成认证令牌

## 性能特征

### 延迟

| 流类型 | 典型延迟 |
|--------|---------|
| 订单簿更新 | 10-50ms |
| 账户订单更新 | 20-100ms |

### 带宽消耗

**单市场（ETH_USDC）:**
- 订单簿流: ~10-20 KB/s
- 账户订单流: ~1-5 KB/s（低频事件）

### 消息频率

| 流类型 | 频率 |
|--------|------|
| 订单簿更新 | 不定（增量推送） |
| 账户订单更新 | 事件驱动 |

## 完整示例

### 订单簿订阅

```python
from exchanges.ws.lighter import LighterWS

async def handle_orderbook(event):
    if event['stream'] == 'orderbook':
        best_bid = event['best_bid']
        best_ask = event['best_ask']
        print(f"Market {event['market_index']}: {best_bid} / {best_ask}")

ws = LighterWS(
    market_index=0,  # ETH_USDC
    on_event=handle_orderbook
)

await ws.run_forever()
```

### 账户订单订阅

```python
from lighter import SignerClient
from exchanges.ws.lighter import LighterWS

# 初始化 Lighter 客户端
client = SignerClient(
    url="https://mainnet.zklighter.elliot.ai",
    account_index=0,
    api_private_keys={0: "your_private_key"}
)

async def handle_events(event):
    if event['stream'] == 'orderbook':
        print(f"Orderbook: {event['best_bid']} / {event['best_ask']}")
    elif event['stream'] == 'account_orders':
        print(f"Orders: {event['orders']}")

ws = LighterWS(
    market_index=0,
    account_index=0,
    lighter_client=client,
    api_key_index=0,
    on_event=handle_events
)

await ws.run_forever()
```

## 限制

- **认证令牌有效期:** 10 分钟（需定期重新生成）
- **最大订阅数:** 建议每个连接订阅不超过 10 个市场
- **序列验证:** 必须验证 offset 连续性，否则可能导致订单簿状态错误
- **内存管理:** 建议定期清理旧的价格档位（保留前 100 档）

## 与 Aster/Backpack 的差异

| 特性 | Lighter | Aster | Backpack |
|------|---------|-------|----------|
| 订阅方式 | JSON subscribe | URL 聚合 | JSON-RPC SUBSCRIBE |
| 快照流 | 内置 | 内置（@depth20） | 无 |
| 序列验证 | offset | update ID | update ID |
| 认证方式 | Auth token | listenKey | 签名 |
| 令牌有效期 | 10 分钟 | 60 分钟 | 无限制 |
| 心跳机制 | ping/pong | 无 | ping/pong |
| 市场标识 | market_index (int) | symbol (string) | symbol (string) |

## 参考

- [Lighter 官方文档](https://docs.lighter.xyz)
- [Lighter API 文档](https://apidocs.lighter.xyz)
- [Lighter Python SDK](https://github.com/elliottech/lighter-python)
- [示例实现](../docs/examples/ws_client/lighter_custom_websocket.py)
- [客户端实现](../api/ws/lighter.py)

## 账户订单回执（抓成交价）

HTTP 私有接口可能因权限/风控返回 403，此时可以通过 WebSocket `account_orders/{market_index}/{account_index}` 拿到成交信息。仓库内置的 `exchanges/ws/lighter.py` 已在账户订单事件里补充 `fill_price` 和 `filled_amount`（基于 fills 或 filled_quote_amount/filled_base_amount 推导）。

最小示例（无需官方 SDK，仅用仓库自带 signer）：

```bash
export LIGHTER_PRIVATE_KEY=your_hex_key_without_0x
export LIGHTER_ACCOUNT_INDEX=699299
export LIGHTER_API_KEY_INDEX=2
export LIGHTER_MARKET_INDEX=0  # perp 市场 ID，改成你的
python docs/examples/ws_client/lighter_custom_websocket.py
```

下单后，控制台会打印：
```
Order update: coid=... status=filled fill_price=3329.88 filled=0.0050 raw={...}
```

如果你用自定义 `LighterWS`（`exchanges/ws/lighter.py`），在 `on_event` 里处理：

```python
async def handle(evt):
    if evt["stream"] == "account_orders":
        for o in evt["orders"]:
            print("fill_price", o.get("fill_price"), "filled", o.get("filled_amount"))
```
