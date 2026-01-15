# Backpack WebSocket 数据流详解

> 深入理解 BBO 和 L2 两种市场数据流的区别与应用场景

---

## 📚 目录

- [数据结构总览](#数据结构总览)
- [两种数据流对比](#两种数据流对比)
- [应用场景](#应用场景)
- [实战案例](#实战案例)
- [性能考量](#性能考量)

---

## 数据结构总览

Backpack WebSocket 提供两种主要的市场数据流：

### 1️⃣ BBO (Best Bid/Offer) - 最佳买卖价

订阅 `bookTicker` 流，只推送最顶层的买1/卖1价格。

**数据格式：**

```json
{
  "exchange": "backpack",
  "symbol": "PAXG_USDC_PERP",
  "stream": "bbo",
  "ts_exchange": 1768490299726564,  // 交易所时间戳（微秒）
  "ts_local": 1768490299759,        // 本地接收时间戳（毫秒）

  "bids": [
    [4621.56, 0.0044]               // [价格, 数量]
  ],
  "asks": [
    [4621.57, 4.6586]               // [价格, 数量]
  ],

  "raw": {
    "e": "bookTicker",              // 事件类型
    "s": "PAXG_USDC_PERP",         // 交易对
    "b": "4621.56",                 // Best bid price
    "B": "0.0044",                  // Best bid quantity
    "a": "4621.57",                 // Best ask price
    "A": "4.6586",                  // Best ask quantity
    "T": 1768490299726602,          // Transaction time (微秒)
    "E": 1768490299730050,          // Event time (微秒)
    "u": 167043030                  // Update ID (序号)
  }
}
```

**字段说明：**

| 字段 | 说明 | 示例 |
|------|------|------|
| `bids` | 最佳买单 [价格, 数量] | `[4621.56, 0.0044]` |
| `asks` | 最佳卖单 [价格, 数量] | `[4621.57, 4.6586]` |
| `ts_exchange` | 交易所生成时间（微秒） | `1768490299726564` |
| `ts_local` | 本地接收时间（毫秒） | `1768490299759` |

**计算价差：**
```python
bid_price, bid_qty = event['bids'][0]
ask_price, ask_qty = event['asks'][0]

spread = ask_price - bid_price              # 绝对价差：$0.01
spread_bps = (spread / bid_price) * 10000   # 相对价差：0.22 基点
```

---

### 2️⃣ L2 (Level 2) - 订单簿深度

订阅 `depth` 流，推送完整订单簿的多档价格（增量更新）。

**数据格式：**

```json
{
  "exchange": "backpack",
  "symbol": "PAXG_USDC_PERP",
  "stream": "l2",
  "ts_exchange": 1768490299729799,
  "ts_local": 1768490299759,

  "bids": [],                       // 买单更新（空=无变化）
  "asks": [
    [4621.57, 4.9082]               // 卖单更新
  ],

  "raw": {
    "e": "depth",
    "s": "PAXG_USDC_PERP",
    "T": 1768490299729799,
    "E": 1768490299734522,
    "U": 167043031,                 // First update ID
    "u": 167043031,                 // Final update ID
    "b": [],                        // 买单列表
    "a": [["4621.57", "4.9082"]]   // 卖单列表
  }
}
```

**增量更新规则：**
- 数量 > 0：更新或添加该价位
- 数量 = 0：删除该价位
- `b/a` 为空：该侧无变化

**完整订单簿示例：**
```
买盘（Bids）              卖盘（Asks）
价格      数量            价格      数量
4621.56   0.0044   <-->  4621.57   4.9082
4621.55   1.2000         4621.58   10.000
4621.54   5.0000         4621.60   20.000
4621.50   10.000         4621.65   50.000
...                      ...
```

---

## 两种数据流对比

### 📊 核心区别

| 特性 | BBO (bookTicker) | L2 (depth) |
|------|------------------|------------|
| **数据内容** | 只有买1/卖1 | 完整订单簿（多档） |
| **消息大小** | ~100 bytes | 几百 bytes 到几 KB |
| **更新频率** | 极高（毫秒级） | 高（略低于BBO） |
| **延迟** | 最低 | 稍高（数据量大） |
| **带宽消耗** | 极小 | 中等到大 |
| **CPU消耗** | 极小 | 中等（需处理多档） |
| **适用场景** | 价格监控、高频交易 | 深度分析、大额交易 |

### 🔍 可见信息对比

#### BBO 视角（有限信息）
```
💰 买1: $4621.56 × 0.0044 = $20.33
💵 卖1: $4621.57 × 4.6586 = $21,532
📊 价差: $0.01 (0.22 bps)

❌ 看不到：
- 买2、买3... 在哪里？
- 卖2、卖3... 有多少？
- 是否有大单堆积（墙）？
- 大额交易的滑点？
```

#### L2 视角（完整信息）
```
💰 买盘深度（Bid Side）
  买1: $4621.56 × 0.0044   累计: 0.0044
  买2: $4621.55 × 1.2000   累计: 1.2044
  买3: $4621.50 × 5.0000   累计: 6.2044
  买4: $4621.45 × 10.000   累计: 16.2044
  ...

💵 卖盘深度（Ask Side）
  卖1: $4621.57 × 4.6586   累计: 4.6586
  卖2: $4621.60 × 10.000   累计: 14.6586
  卖3: $4621.65 × 20.000   累计: 34.6586  ← 大单"墙"
  卖4: $4621.70 × 50.000   累计: 84.6586
  ...

✅ 可以计算：
- 买入100 PAXG的平均价格
- 预估滑点
- 发现支撑位/压力位
- 检测市场深度是否充足
```

---

## 应用场景

### 场景1️⃣：高频交易 / 套利机器人

**需求：** 毫秒级价格监控，极低延迟

**推荐：** 仅订阅 BBO

```python
from api.ws.backpack import BackpackWS

# 只订阅最佳买卖价，最小延迟
ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=False,  # 不订阅深度
    on_event=handle_arbitrage
)

async def handle_arbitrage(event):
    if event['stream'] != 'bbo':
        return

    bid = event['bids'][0][0]
    ask = event['asks'][0][0]

    # 快速决策：套利机会？
    if should_arbitrage(bid, ask):
        execute_trade()  # 毫秒级执行
```

**优势：**
- 延迟最低（~1-2ms）
- 带宽占用小（~10 KB/s）
- CPU消耗低

---

### 场景2️⃣：大额交易评估

**需求：** 买入/卖出大额资产，需要评估滑点

**推荐：** 订阅 L2 深度数据

```python
from api.ws.backpack import BackpackWS

# 订阅完整深度
ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=True,
    on_event=analyze_depth
)

async def analyze_depth(event):
    if event['stream'] != 'l2':
        return

    asks = event['asks']  # 卖盘

    # 计算买入100 PAXG的成本
    target_qty = 100.0
    total_cost = 0
    filled_qty = 0

    for price, qty in asks:
        if filled_qty >= target_qty:
            break

        fill_amount = min(qty, target_qty - filled_qty)
        total_cost += price * fill_amount
        filled_qty += fill_amount

    avg_price = total_cost / filled_qty
    best_ask = asks[0][0]
    slippage = avg_price - best_ask

    print(f"买入 {target_qty} PAXG:")
    print(f"  最优价: ${best_ask:.2f}")
    print(f"  平均价: ${avg_price:.2f}")
    print(f"  滑点:   ${slippage:.2f} ({slippage/best_ask*100:.2f}%)")
```

**输出示例：**
```
买入 100 PAXG:
  最优价: $4621.57
  平均价: $4622.35
  滑点:   $0.78 (0.017%)
```

---

### 场景3️⃣：市场监控 / 交易界面

**需求：** 实时显示价格 + 按需查看深度

**推荐：** 同时订阅 BBO + L2

```python
from api.ws.backpack import BackpackWS

# 双流订阅
ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=True,  # 两者都订阅
    on_event=handle_ui_update
)

# 全局状态
current_price = None
orderbook = {"bids": [], "asks": []}

async def handle_ui_update(event):
    global current_price, orderbook

    if event['stream'] == 'bbo':
        # BBO: 更新顶部价格显示（高频）
        bid = event['bids'][0][0]
        ask = event['asks'][0][0]
        current_price = (bid + ask) / 2
        update_price_ticker(current_price)  # UI更新

    elif event['stream'] == 'l2':
        # L2: 更新订单簿（用户点击时显示）
        update_orderbook(event)
        if user_viewing_orderbook:
            render_orderbook_ui(orderbook)
```

**UI 设计：**
```
┌─────────────────────────────────────┐
│  PAXG_USDC_PERP                     │
│  $4621.57  ↑ 0.15%   [查看深度]    │ ← BBO实时更新
└─────────────────────────────────────┘

点击"查看深度"后：
┌─────────────────────────────────────┐
│  订单簿（Orderbook）                │
│  ────────────────────────────────   │
│  买盘              |  卖盘           │ ← L2数据
│  4621.56  0.0044  |  4621.57  4.96  │
│  4621.55  1.2000  |  4621.60 10.00  │
│  4621.50  5.0000  |  4621.65 20.00  │
└─────────────────────────────────────┘
```

---

### 场景4️⃣：量化回测

**需求：** 存储历史数据用于回测

**推荐：** 仅订阅 BBO（节省存储）

```python
import sqlite3
from api.ws.backpack import BackpackWS

# 数据库存储
conn = sqlite3.connect('market_data.db')
conn.execute('''
    CREATE TABLE IF NOT EXISTS ticks (
        ts INTEGER PRIMARY KEY,
        symbol TEXT,
        bid REAL,
        ask REAL
    )
''')

ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=False,  # 只存BBO，节省空间
    on_event=store_tick
)

async def store_tick(event):
    if event['stream'] != 'bbo':
        return

    conn.execute(
        "INSERT INTO ticks VALUES (?, ?, ?, ?)",
        (
            event['ts_exchange'],
            event['symbol'],
            event['bids'][0][0],
            event['asks'][0][0]
        )
    )
    conn.commit()
```

**存储对比：**
```
BBO 数据: ~40 bytes/tick × 100 ticks/s = 4 KB/s = 345 MB/天
L2 数据:  ~2 KB/tick  × 50 ticks/s  = 100 KB/s = 8.6 GB/天
```

---

## 实战案例

### 案例1：检测订单簿失衡

```python
async def detect_imbalance(event):
    """检测买卖盘失衡（需要L2数据）"""
    if event['stream'] != 'l2':
        return

    bids = event['bids'][:10]  # 前10档
    asks = event['asks'][:10]

    bid_volume = sum(qty for _, qty in bids)
    ask_volume = sum(qty for _, qty in asks)

    imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    if imbalance > 0.3:
        print("🟢 买盘强势！可能上涨")
    elif imbalance < -0.3:
        print("🔴 卖盘强势！可能下跌")
```

### 案例2：实时计算VWAP

```python
from collections import deque

vwap_window = deque(maxlen=100)  # 最近100笔

async def calculate_vwap(event):
    """计算成交量加权平均价（用BBO近似）"""
    if event['stream'] != 'bbo':
        return

    bid_price, bid_qty = event['bids'][0]
    ask_price, ask_qty = event['asks'][0]

    mid_price = (bid_price + ask_price) / 2
    volume = (bid_qty + ask_qty) / 2

    vwap_window.append((mid_price, volume))

    total_value = sum(p * v for p, v in vwap_window)
    total_volume = sum(v for _, v in vwap_window)

    vwap = total_value / total_volume if total_volume > 0 else 0
    print(f"VWAP: ${vwap:.2f}")
```

### 案例3：价格突破告警

```python
price_history = deque(maxlen=60)  # 60秒窗口

async def breakout_alert(event):
    """价格突破前高/低告警（只需BBO）"""
    if event['stream'] != 'bbo':
        return

    bid, ask = event['bids'][0][0], event['asks'][0][0]
    mid = (bid + ask) / 2

    price_history.append(mid)

    if len(price_history) < 60:
        return

    high = max(price_history)
    low = min(price_history)

    if mid > high * 1.001:  # 突破前高0.1%
        print(f"🚀 价格突破！${mid:.2f} > ${high:.2f}")
    elif mid < low * 0.999:  # 跌破前低0.1%
        print(f"📉 价格跌破！${mid:.2f} < ${low:.2f}")
```

---

## 性能考量

### ⚡ 延迟对比

```
交易所生成 → 网络传输 → 本地接收 → 应用处理
─────────────────────────────────────────────────
BBO:  1-2ms        1-3ms       0.1ms      总计: 2-5ms
L2:   2-3ms        2-5ms       0.5ms      总计: 4-8ms
```

**时间戳分析：**
```python
ts_exchange = 1768490299726564  # 交易所时间（微秒）
ts_local    = 1768490299759000  # 本地时间（微秒）

latency = (ts_local - ts_exchange) / 1000  # 毫秒
# 典型值: 3-5ms
```

### 💾 带宽消耗

**实测数据（PAXG_USDC_PERP）：**

| 配置 | 消息频率 | 消息大小 | 带宽 |
|------|---------|---------|------|
| 仅BBO | ~100/s | ~100 bytes | ~10 KB/s |
| 仅L2 | ~50/s | ~500 bytes | ~25 KB/s |
| BBO+L2 | ~150/s | 混合 | ~35 KB/s |

**每日流量：**
```
仅BBO:   10 KB/s × 86400s = 864 MB/天
BBO+L2:  35 KB/s × 86400s = 3.0 GB/天
```

### 🖥️ CPU使用

```python
# BBO处理：简单
bid, ask = event['bids'][0], event['asks'][0]
# ~0.01ms CPU时间

# L2处理：复杂
for price, qty in event['bids']:
    update_orderbook(price, qty)  # 需要排序、查找
# ~0.1-0.5ms CPU时间
```

---

## 最佳实践

### ✅ 推荐做法

1. **按需订阅**
   ```python
   # 高频策略：只订阅BBO
   ws = BackpackWS(symbols=["PAXG_USDC_PERP"], include_depth=False)

   # 大额交易：只订阅L2
   ws = BackpackWS(symbols=["PAXG_USDC_PERP"], include_depth=True)
   # 然后在代码里只处理 l2 事件
   ```

2. **过滤不需要的事件**
   ```python
   async def on_event(event):
       # 只处理BBO，忽略L2
       if event['stream'] != 'bbo':
           return

       # 你的逻辑...
   ```

3. **使用时间戳检测延迟**
   ```python
   import time

   async def monitor_latency(event):
       ts_exchange_sec = event['ts_exchange'] / 1_000_000  # 微秒→秒
       ts_now = time.time()

       latency_ms = (ts_now - ts_exchange_sec) * 1000

       if latency_ms > 100:
           print(f"⚠️ 延迟过高: {latency_ms:.1f}ms")
   ```

### ❌ 避免的错误

1. **不要盲目订阅所有流**
   ```python
   # ❌ 浪费带宽和CPU
   ws = BackpackWS(
       symbols=["BTC_USDC", "ETH_USDC", "SOL_USDC", ...],  # 10+交易对
       include_depth=True  # 全都要深度
   )
   # 带宽: 350+ KB/s, CPU: 高

   # ✅ 按需订阅
   ws_bbo = BackpackWS(
       symbols=["BTC_USDC", "ETH_USDC"],  # 只监控2个
       include_depth=False
   )
   ws_depth = BackpackWS(
       symbols=["PAXG_USDC_PERP"],  # 只对1个要深度
       include_depth=True
   )
   ```

2. **不要在回调函数里做重计算**
   ```python
   # ❌ 阻塞事件循环
   async def on_event(event):
       result = heavy_computation(event)  # 耗时100ms
       # 下一条消息要等100ms才能处理！

   # ✅ 异步处理
   async def on_event(event):
       asyncio.create_task(process_async(event))  # 不阻塞
   ```

3. **不要忽略update ID**
   ```python
   # L2数据有序号，用于检测丢包
   last_update_id = 0

   async def on_event(event):
       if event['stream'] != 'l2':
           return

       update_id = event['raw']['u']

       if update_id != last_update_id + 1:
           print(f"⚠️ 丢包检测: {last_update_id} → {update_id}")
           # 可能需要重新获取完整订单簿

       last_update_id = update_id
   ```

---

## 快速参考

### 选择决策树

```
开始
  │
  ├─ 只需要最新价格？
  │    └─ 是 → 仅订阅 BBO
  │
  ├─ 需要评估大单滑点？
  │    └─ 是 → 订阅 L2
  │
  ├─ 做市商/高频交易？
  │    └─ 是 → 仅订阅 BBO（最低延迟）
  │
  ├─ 需要分析市场深度？
  │    └─ 是 → 订阅 L2
  │
  └─ 交易界面（显示+深度）？
       └─ 是 → 订阅 BBO + L2
```

### 代码模板

```python
from api.ws.backpack import BackpackWS

# 场景1: 仅价格监控
ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=False,
    on_event=lambda e: print(f"价格: {e['bids'][0][0]}")
)

# 场景2: 完整深度分析
ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=True,
    on_event=analyze_orderbook
)

# 场景3: 双流处理
async def handle_both(event):
    if event['stream'] == 'bbo':
        update_price(event)
    elif event['stream'] == 'l2':
        update_depth(event)

ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    include_depth=True,
    on_event=handle_both
)

# 运行
import asyncio
asyncio.run(ws.run_forever())
```

---

## 总结

| 维度 | BBO | L2 |
|------|-----|-----|
| 🎯 核心用途 | 实时价格 | 市场深度 |
| ⚡ 延迟 | 最低 | 稍高 |
| 💾 数据量 | 极小 | 中等 |
| 🔍 信息量 | 有限 | 丰富 |
| 💡 适合场景 | 高频/监控 | 分析/大单 |

**记住：**
- 不确定用哪个？先用 BBO（够用且快）
- 需要深度分析时再加 L2
- 生产环境优先考虑带宽成本

---

**相关文档：**
- [Backpack WebSocket API 官方文档](https://docs.backpack.exchange/)
- [subscribe_paxg.py 示例脚本](../subscribe_paxg.py)
- [api/ws/backpack.py 实现代码](../api/ws/backpack.py)

**更新时间：** 2026-01-15
