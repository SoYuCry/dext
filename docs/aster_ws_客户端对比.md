# Aster WebSocket 客户端说明

> 本文档说明 `api/ws/aster.py` 文件中三个 Aster WebSocket 客户端类的区别和使用场景。

## 📋 快速对比

| 类名 | 用途 | 数据类型 | 是否需要认证 | 推送频率 |
|------|------|---------|-------------|---------|
| `AsterWS` | 市场行情（增量更新） | 公开市场数据 | ❌ 否 | 实时（有变化就推） |
| `AsterDepthWS` | 市场行情（完整快照） | 公开市场数据 | ❌ 否 | 每 250ms |
| `AsterUserWS` | 账户私有数据 | 订单/持仓/余额 | ✅ 是 | 实时（有变化就推） |

> **注意**: 这三个类都在同一个文件 [`api/ws/aster.py`](file:///Users/liuc/Documents/Projects/dext/api/ws/aster.py) 中。

---

## 1️⃣ `AsterWS` - 市场行情增量流

### 📝 用途
订阅**公开市场数据**的**增量更新**（Depth Update Stream）

### 🔌 连接方式
```python
from api.ws.aster import AsterWS

ws_client = AsterWS(
    symbols=['xauusdt', 'btcusdt'],  # 可订阅多个交易对
    on_event=on_event
)
await ws_client.run_forever()
```

### 🌐 WebSocket URL
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth/btcusdt@depth
```

### 📊 推送的数据
- **订单簿增量更新** - 只推送发生变化的价格档位
- **实时推送** - 有变化就立即推送（延迟 < 10ms）
- **需要维护状态** - 客户端需要自己维护完整订单簿

### 💡 使用场景
- 高频交易系统
- 做市商
- 需要捕捉每一个价格变化的场景

### ⚠️ 注意事项
- 需要先获取快照，再应用增量更新
- 需要处理更新 ID 的连续性
- 实现复杂度较高

---

## 2️⃣ `AsterDepthWS` - 市场行情完整快照流

### 📝 用途
订阅**公开市场数据**的**完整快照**（Depth Snapshot Stream）

### 🔌 连接方式
```python
from api.ws.aster import AsterDepthWS

ws_client = AsterDepthWS(
    symbols=['xauusdt'],
    on_event=on_event,
    depth_level=20  # 可选 5, 10, 20
)
await ws_client.run_forever()
```

### 🌐 WebSocket URL
```
wss://fstream.asterdex.com/stream?streams=xauusdt@depth20
```

### 📊 推送的数据
- **完整订单簿快照** - 每次推送完整的 N 档买卖盘
- **固定频率** - 每 250ms 推送一次
- **无需维护状态** - 每次都是独立的完整数据

### 💡 使用场景
- 交易界面显示
- 套利机器人
- 价格监控和告警
- **你的黄金监控脚本** ✅

### ✅ 优点
- 实现简单，直接使用
- 数据一致性好
- 适合大多数应用

---

## 3️⃣ `AsterUserWS` - 账户私有数据流

### 📝 用途
订阅**账户私有数据**（User Data Stream），包括订单更新、持仓变化、余额变化等

### 🔌 连接方式
```python
from api.ws.aster import AsterUserWS

ws_client = AsterUserWS(
    api_key='your_api_key',
    on_event=on_event
)
await ws_client.run_forever()
```

### 🌐 WebSocket URL
```
wss://fstream.asterdex.com/ws/<listenKey>
```

### 🔑 认证流程
1. 使用 API Key 创建 `listenKey`（有效期 60 分钟）
2. 使用 `listenKey` 连接 WebSocket
3. 每 30 分钟自动续期 `listenKey`

### 📊 推送的数据

#### 订单更新 (`ORDER_TRADE_UPDATE`)
```json
{
  "type": "order",
  "symbol": "XAUUSDT",
  "order_id": "123456",
  "side": "BUY",
  "status": "FILLED",
  "filled_qty": "1.5",
  "price": "4610.50",
  ...
}
```

#### 账户更新 (`ACCOUNT_UPDATE`)
```json
{
  "type": "account",
  "account": {
    "balances": [...],
    "positions": [...]
  }
}
```

#### 强平告警 (`MARGIN_CALL`)
```json
{
  "type": "margin_call",
  "positions": [...]
}
```

#### 配置更新 (`ACCOUNT_CONFIG_UPDATE`)
```json
{
  "type": "config_update",
  "config": {...}
}
```

### 💡 使用场景
- 监控自己的订单状态
- 实时跟踪持仓变化
- 接收强平告警
- 自动化交易系统

### ⚠️ 注意事项
- **需要 API Key** - 必须有账户和 API 权限
- **自动保活** - 客户端会自动续期 `listenKey`
- **私有数据** - 只能看到自己账户的数据

---

## 🎯 如何选择？

### 决策树

```
你需要什么数据？
  │
  ├─ 市场行情（公开数据）
  │   │
  │   ├─ 需要毫秒级延迟？
  │   │   └─ 是 → aster.py（增量流）
  │   │   └─ 否 → aster_depth.py（快照流）✅ 推荐
  │   │
  │   └─ 需要多少档深度？
  │       ├─ 1-5 档 → depth_level=5
  │       ├─ 6-10 档 → depth_level=10
  │       └─ 11-20 档 → depth_level=20
  │
  └─ 账户数据（私有数据）
      └─ aster_user.py（用户流）
```

---

## 📚 代码示例对比

### 示例 1: 监控黄金价格（公开数据）

```python
# 使用 AsterDepthWS - 最简单
from api.ws.aster import AsterDepthWS

async def on_price_update(event):
    best_bid = event['bids'][0][0]
    best_ask = event['asks'][0][0]
    print(f"买价: ${best_bid}, 卖价: ${best_ask}")

ws = AsterDepthWS(['xauusdt'], on_price_update, depth_level=5)
await ws.run_forever()
```

### 示例 2: 高频交易（需要最低延迟）

```python
# 使用 AsterWS - 增量流
from api.ws.aster import AsterWS

orderbook = OrderBookManager()  # 需要自己维护订单簿

async def on_depth_update(event):
    orderbook.apply_update(event)
    
    # 检查套利机会
    if orderbook.check_arbitrage():
        execute_trade()

ws = AsterWS(['xauusdt'], on_depth_update)
await ws.run_forever()
```

### 示例 3: 监控自己的订单（私有数据）

```python
# 使用 AsterUserWS - 用户流
from api.ws.aster import AsterUserWS

async def on_user_event(event):
    if event['type'] == 'order':
        print(f"订单更新: {event['symbol']} {event['status']}")
    elif event['type'] == 'margin_call':
        print("⚠️ 强平告警！")
        send_alert()

ws = AsterUserWS(api_key='your_key', on_event=on_user_event)
await ws.run_forever()
```

---

## 🔄 可以同时使用多个客户端

```python
import asyncio
from api.ws.aster import AsterDepthWS, AsterUserWS

async def main():
    # 同时订阅市场数据和账户数据
    market_ws = AsterDepthWS(['xauusdt'], on_market_event, depth_level=20)
    user_ws = AsterUserWS(api_key='your_key', on_event=on_user_event)
    
    # 并发运行
    await asyncio.gather(
        market_ws.run_forever(),
        user_ws.run_forever()
    )

asyncio.run(main())
```

---

## 📊 数据流对比图

```
┌─────────────────────────────────────────────────────────────┐
│                    Aster WebSocket 数据流                     │
└─────────────────────────────────────────────────────────────┘

公开数据（无需认证）:
┌──────────────┐
│ aster.py     │ → 增量更新 → 实时推送 → 高频交易
└──────────────┘

┌──────────────┐
│aster_depth.py│ → 完整快照 → 250ms → 普通交易/监控 ✅
└──────────────┘

私有数据（需要 API Key）:
┌──────────────┐
│aster_user.py │ → 订单/持仓 → 实时推送 → 账户监控
└──────────────┘
```

---

## 🛠️ 技术细节

### 共同点
- 都继承自 `WebsocketClient` 基类
- 都支持自动重连
- 都使用相同的事件回调机制

### 不同点

| 特性 | aster.py | aster_depth.py | aster_user.py |
|------|----------|----------------|---------------|
| **数据类型** | 公开市场数据 | 公开市场数据 | 私有账户数据 |
| **订阅方式** | URL 参数 | URL 参数 | listenKey |
| **认证** | 无 | 无 | API Key |
| **状态维护** | 需要 | 不需要 | 不需要 |
| **保活机制** | 无 | 无 | 30 分钟续期 |
| **推送频率** | 实时 | 250ms | 实时 |
| **实现复杂度** | 高 | 低 | 中 |

---

## 💡 最佳实践

### 1. 选择合适的客户端
- **大多数情况** → 使用 `aster_depth.py`
- **高频交易** → 使用 `aster.py`
- **监控订单** → 使用 `aster_user.py`

### 2. 错误处理
所有客户端都支持自动重连，但建议添加额外的错误处理：

```python
async def safe_run():
    while True:
        try:
            await ws.run_forever()
        except Exception as e:
            logger.error(f"WebSocket 错误: {e}")
            await asyncio.sleep(5)  # 等待后重试
```

### 3. 性能优化
- 只订阅需要的交易对
- 使用合适的深度档位（不要总是用 20）
- 及时处理事件，避免阻塞

---

## 📖 相关文档

- [WebSocket 订阅方式对比](file:///Users/liuc/Documents/Projects/dext/docs/websocket_订阅方式对比.md)
- [Binance Futures WebSocket API](https://binance-docs.github.io/apidocs/futures/en/)
- 项目代码：[`api/ws/aster.py`](file:///Users/liuc/Documents/Projects/dext/api/ws/aster.py) - 包含所有三个客户端类

---

**文档版本**: 2.0  
**最后更新**: 2026-01-15  
**变更**: 三个客户端类已合并到一个文件 `aster.py` 中
