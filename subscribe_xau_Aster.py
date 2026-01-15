"""订阅 Aster XAU WebSocket 并打印每条消息的简单脚本"""
import asyncio
import json
from datetime import datetime
from api.ws.aster import AsterDepthWS

# ========== 配置选项 ==========
# 设置为 True 查看完整原始数据，False 查看简化版本
SHOW_RAW_DATA = False

# 订单簿深度档位：5, 10, 20（推荐 20）
DEPTH_LEVEL = 20

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
    symbol = event.get("symbol", "N/A")
    stream = event.get("stream", "N/A")
    ts_exchange = event.get("ts_exchange", 0)
    ts_local = event.get("ts_local", 0)
    
    # 转换时间戳为可读格式
    time_str = datetime.fromtimestamp(ts_exchange / 1000).strftime("%H:%M:%S.%f")[:-3]
    
    bids = event.get("bids", [])
    asks = event.get("asks", [])
    
    # 获取最佳买卖价
    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None
    
    print(f"⏰ {time_str} | {symbol} | 流: {stream}")
    
    if best_bid and best_ask:
        bid_price, bid_qty = best_bid
        ask_price, ask_qty = best_ask
        spread = ask_price - bid_price
        spread_bps = (spread / bid_price) * 10000  # 基点
        
        print(f"  💰 最佳买价: ${bid_price:,.2f} (数量: {bid_qty})")
        print(f"  💵 最佳卖价: ${ask_price:,.2f} (数量: {ask_qty})")
        print(f"  📊 价差: ${spread:.2f} ({spread_bps:.2f} bps)")
        
        # 显示完整订单簿
        if SHOW_FULL_ORDERBOOK and (len(bids) > 1 or len(asks) > 1):
            print(f"\n  📖 完整订单簿 (共 {len(bids)} 档买盘, {len(asks)} 档卖盘):")
            print(f"  {'':>4} {'买价':>12} {'数量':>10}  |  {'卖价':>12} {'数量':>10}")
            print(f"  {'-' * 52}")
            
            max_levels = max(len(bids), len(asks))
            for i in range(max_levels):
                bid_str = ""
                ask_str = ""
                
                if i < len(bids):
                    bp, bq = bids[i]
                    bid_str = f"${bp:>11,.2f} {bq:>10.3f}"
                else:
                    bid_str = " " * 24
                
                if i < len(asks):
                    ap, aq = asks[i]
                    ask_str = f"${ap:>11,.2f} {aq:>10.3f}"
                else:
                    ask_str = " " * 24
                
                print(f"  {i+1:>2}. {bid_str}  |  {ask_str}")
        else:
            print(f"  📖 订单簿深度: 买盘 {len(bids)} 档 | 卖盘 {len(asks)} 档")
    else:
        print(f"  ⚠️  数据不完整")
    
    print("-" * 80)


async def main():
    """主函数"""
    # 订阅 XAUUSDT (黄金/USDT 永续合约)
    symbols = ["xauusdt"]
    
    print(f"开始订阅 Aster {symbols} WebSocket (深度: {DEPTH_LEVEL} 档)...")
    print("=" * 80)
    
    # 创建 WebSocket 客户端 - 使用完整订单簿深度订阅
    ws_client = AsterDepthWS(symbols=symbols, on_event=on_event, depth_level=DEPTH_LEVEL)
    
    # 运行 WebSocket 客户端（会自动重连）
    await ws_client.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
