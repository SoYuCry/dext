# WebSocket 市场数据流概述

本项目实现了 Backpack 和 Aster 交易所的 WebSocket 客户端，提供统一的事件接口。

## 数据流类型

### BBO (Best Bid/Offer)
仅推送最优买卖价，适合价格监控和高频交易。

**特点：**
- 消息体积小（~100 bytes）
- 更新频率高
- 延迟最低（1-5ms）
- 信息有限（仅买1/卖1）

### L2 (Level 2 Depth)
推送多档订单簿数据，适合深度分析和大额交易评估。

**特点：**
- 消息体积大（数百 bytes 至数 KB）
- 完整的市场深度信息
- 可计算滑点、支撑/压力位
- 增量更新或完整快照（取决于交易所）

## 统一事件格式

两个交易所的客户端都输出相同的事件结构：

```python
{
    "exchange": str,         # "backpack" | "aster"
    "symbol": str,           # 交易对，如 "PAXG_USDC_PERP"
    "stream": str,           # "bbo" | "l2" | "depth20" | "user"
    "ts_exchange": int,      # 交易所时间戳（微秒或毫秒）
    "ts_local": int,         # 本地接收时间戳（毫秒）
    "bids": [[float, float]],  # [[price, qty], ...]
    "asks": [[float, float]],  # [[price, qty], ...]
    "raw": dict             # 原始消息
}
```

## 快速开始

### Backpack

```python
from api.ws.backpack import BackpackWS

async def on_event(event):
    if event['stream'] == 'bbo':
        bid, ask = event['bids'][0][0], event['asks'][0][0]
        print(f"{event['symbol']}: bid={bid}, ask={ask}")

ws = BackpackWS(
    symbols=["PAXG_USDC_PERP"],
    on_event=on_event,
    include_depth=False  # 仅订阅 BBO
)

await ws.run_forever()
```

### Aster

```python
from api.ws.aster import AsterDepthWS

async def on_event(event):
    print(f"{event['symbol']}: {len(event['bids'])} bids, {len(event['asks'])} asks")

ws = AsterDepthWS(
    symbols=["xauusdt"],
    on_event=on_event,
    depth_level=20  # 20档深度
)

await ws.run_forever()
```

## 使用场景

| 场景 | 推荐配置 | 理由 |
|------|---------|------|
| 价格监控 | BBO only | 延迟低，带宽小 |
| 高频交易/套利 | BBO only | 最低延迟 |
| 大额交易评估 | L2/Depth | 需要计算滑点 |
| 市场深度分析 | L2/Depth | 完整订单簿信息 |
| 交易界面 | BBO + L2 | 实时价格 + 按需深度 |
| 历史数据采集 | BBO only | 存储成本低 |

## 性能对比

|  | BBO | L2 |
|---|-----|-----|
| 消息大小 | ~100 bytes | ~500 bytes - 5 KB |
| 更新频率 | 极高 | 高 |
| 典型延迟 | 1-5ms | 3-8ms |
| 带宽消耗 | ~10 KB/s | ~25-100 KB/s |
| CPU 开销 | 极低 | 低-中 |

## 技术文档

- [Backpack WebSocket 技术规范](./backpack_websocket_technical.md)
- [Aster WebSocket 技术规范](./aster_websocket_technical.md)

## 延迟计算

```python
ts_exchange_sec = event['ts_exchange'] / 1_000_000  # 微秒 -> 秒
ts_local_sec = event['ts_local'] / 1_000

latency_ms = (ts_local_sec - ts_exchange_sec) * 1000
```

典型延迟：3-10ms（取决于网络和地理位置）

## 错误处理

所有客户端都内置自动重连机制：

```python
ws = BackpackWS(
    symbols=["BTC_USDC"],
    on_event=on_event,
    # 基类默认配置：
    # - 自动重连
    # - 指数退避（3s, 6s, 12s, ...）
)
```

## 示例脚本

- `subscribe_paxg.py` - Backpack PAXG 订阅示例
- `subscribe_xau_Aster.py` - Aster XAU 订阅示例
