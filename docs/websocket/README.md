# WebSocket 使用指南

本目录包含 WebSocket 实时数据流的使用文档。

## 统一架构

WebSocket 层采用"原始事件 → 标准化事件 → 队列分发"的流程：

```
WS Client → raw event (dict) → Normalizer → BBOUpdate/OrderUpdate → WSDispatcher queues
```

### 快速示例

```python
import asyncio
from exchanges.ws import create_dispatcher
from exchanges.ws.backpack import BackpackWS

async def main():
    dispatcher = create_dispatcher()

    ws = BackpackWS(
        symbols=["PAXG_USDC_PERP"],
        on_event=dispatcher.on_raw_event,
        include_depth=False  # 仅订阅 BBO
    )

    asyncio.create_task(ws.run_forever())

    while True:
        bbo = await dispatcher.get_market_data()
        print(f"{bbo.symbol}: {bbo.data.bid} / {bbo.data.ask}")

asyncio.run(main())
```

## 数据流类型

### BBO (Best Bid/Offer)
- **用途**: 价格监控、高频交易、最低延迟
- **优点**: 数据量小（~100 bytes）、延迟低（1-5ms）
- **适用**: 套利、做市、价格监控

### L2 (Level 2 Depth)
- **用途**: 深度分析、滑点评估、大额交易
- **优点**: 完整市场深度信息
- **适用**: 交易界面、流动性分析

## 交易所特性

### Backpack
- ✅ 支持 BBO 与完整深度
- ✅ 用户数据流（订单更新、成交）
- 详见: [backpack_websocket_technical.md](./backpack_websocket_technical.md)

### Aster
- ✅ 增量流（@depth）- 实时推送
- ✅ 快照流（@depth5/10/20）- 每 250ms
- ✅ 用户数据流（订单、持仓）
- 详见: [aster_websocket_technical.md](./aster_websocket_technical.md)

### Lighter
- ✅ 公开订单簿流
- ⚠️ 用户数据流（需要 auth token）
- 使用 market_index 映射到 symbol
- 详见: [lighter_websocket_technical.md](./lighter_websocket_technical.md)

### Variational
- ⚠️ 无原生 WebSocket（使用轮询）
- 使用 `VariationalPricePoller` 轮询行情
- 使用 `VariationalFillPoller` 轮询订单
- 详见: `docs/exchanges/variational.md`

## 使用建议

| 场景 | 推荐方案 |
|------|---------|
| 价格监控 | BBO only |
| 高频/套利 | BBO only |
| 大额交易评估 | L2 Depth |
| 交易界面 | BBO + L2 |

## 错误处理

所有客户端内置自动重连机制（指数退避）：

```python
ws = BackpackWS(
    symbols=["BTC_USDC"],
    on_event=on_event
    # 自动重连: 3s, 6s, 12s, ...
)
await ws.run_forever()
```

## 技术文档

- [Backpack WebSocket 技术规范](./backpack_websocket_technical.md)
- [Aster WebSocket 技术规范](./aster_websocket_technical.md)
- [Lighter WebSocket 技术规范](./lighter_websocket_technical.md)

## 示例脚本

- `subscribe_paxg.py` - Backpack PAXG 订阅示例
- `subscribe_xau_Aster.py` - Aster XAU 订阅示例
- `docs/examples/ws_client/lighter_custom_websocket.py` - Lighter 订单簿示例

---

更多架构细节参考: `docs/plans/2026-01-24-ws-unified-architecture-design.md`
