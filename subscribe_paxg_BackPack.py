"""订阅 Backpack PAXG_USDC_PERP WebSocket 并打印每条消息的简单脚本"""
import asyncio
import json
from datetime import datetime
from api.ws.backpack import BackpackWS

# ========== 配置选项 ==========
# 设置为 True 查看完整原始数据，False 查看简化版本
SHOW_RAW_DATA = False

# 是否包含深度数据（depth），False 则只订阅 bookTicker
INCLUDE_DEPTH = True

# 是否显示完整订单簿（True）还是只显示最佳买卖价（False）
SHOW_FULL_ORDERBOOK = True


async def on_event(event):
    """处理 WebSocket 事件 - 打印易读的市场信息"""

    if SHOW_RAW_DATA:
        # 显示完整原始数据
        print(json.dumps(event, indent=2, ensure_ascii=False))
        print("-" * 80)
        return

    # 简化版本 - 只显示关键信息
    exchange = event.get("exchange", "N/A")
    symbol = event.get("symbol", "N/A")
    stream = event.get("stream", "N/A")
    ts_exchange = event.get("ts_exchange", 0)
    ts_local = event.get("ts_local", 0)

    # 转换时间戳为可读格式
    # 自动检测时间戳单位（秒、毫秒或微秒）
    try:
        if ts_exchange > 1e15:  # 微秒时间戳
            time_str = datetime.fromtimestamp(ts_exchange / 1000000).strftime("%H:%M:%S.%f")[:-3]
        elif ts_exchange > 1e12:  # 毫秒时间戳
            time_str = datetime.fromtimestamp(ts_exchange / 1000).strftime("%H:%M:%S.%f")[:-3]
        else:  # 秒时间戳
            time_str = datetime.fromtimestamp(ts_exchange).strftime("%H:%M:%S.%f")[:-3]
    except (OSError, ValueError, OverflowError):
        time_str = "N/A"

    bids = event.get("bids", [])
    asks = event.get("asks", [])

    # 获取最佳买卖价
    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None

    print(f"⏰ {time_str} | {exchange.upper()} | {symbol} | 流: {stream}")

    if best_bid and best_ask:
        bid_price, bid_qty = best_bid
        ask_price, ask_qty = best_ask
        spread = ask_price - bid_price
        spread_bps = (spread / bid_price) * 10000  # 基点

        print(f"  💰 最佳买价: ${bid_price:,.2f} (数量: {bid_qty:.4f})")
        print(f"  💵 最佳卖价: ${ask_price:,.2f} (数量: {ask_qty:.4f})")
        print(f"  📊 价差: ${spread:.2f} ({spread_bps:.2f} bps)")

        # 显示完整订单簿
        if SHOW_FULL_ORDERBOOK and stream == "l2" and (len(bids) > 1 or len(asks) > 1):
            print(f"\n  📖 完整订单簿 (共 {len(bids)} 档买盘, {len(asks)} 档卖盘):")
            print(f"  {'':>4} {'买价':>12} {'数量':>10}  |  {'卖价':>12} {'数量':>10}")
            print(f"  {'-' * 52}")

            max_levels = max(len(bids), len(asks))
            for i in range(min(max_levels, 20)):  # 最多显示20档
                bid_str = ""
                ask_str = ""

                if i < len(bids):
                    bp, bq = bids[i]
                    bid_str = f"${bp:>11,.2f} {bq:>10.4f}"
                else:
                    bid_str = " " * 24

                if i < len(asks):
                    ap, aq = asks[i]
                    ask_str = f"${ap:>11,.2f} {aq:>10.4f}"
                else:
                    ask_str = " " * 24

                print(f"  {i+1:>2}. {bid_str}  |  {ask_str}")
        elif stream == "bbo":
            print(f"  📖 最佳买卖价 (bookTicker)")
    else:
        print(f"  ⚠️  数据不完整")

    print("-" * 80)


async def main():
    """主函数"""
    # 订阅 PAXG_USDC_PERP (黄金代币永续合约)
    symbols = ["PAXG_USDC_PERP"]

    print(f"开始订阅 Backpack {symbols} WebSocket...")
    print(f"订阅选项: bookTicker + {'depth (订单簿)' if INCLUDE_DEPTH else '仅最佳买卖价'}")
    print("=" * 80)

    # 创建 WebSocket 客户端
    ws_client = BackpackWS(
        symbols=symbols,
        on_event=on_event,
        include_depth=INCLUDE_DEPTH
    )

    # 运行 WebSocket 客户端（会自动重连）
    await ws_client.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
