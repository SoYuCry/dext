"""订阅 Backpack 用户订单和成交 WebSocket 并打印每条消息的脚本"""
import asyncio
import json
import os
from datetime import datetime
from api.ws.backpack import BackpackUserWS

# ========== 配置选项 ==========
# 设置为 True 查看完整原始数据，False 查看简化版本
SHOW_RAW_DATA = False

# 从环境变量获取 API 凭证
API_KEY = os.getenv("BACKPACK_API_KEY")
SECRET = os.getenv("BACKPACK_SECRET")

if not API_KEY or not SECRET:
    print("错误：请设置环境变量 BACKPACK_API_KEY 和 BACKPACK_SECRET")
    exit(1)


async def on_event(event):
    """处理 WebSocket 事件 - 打印易读的订单和成交信息"""

    if SHOW_RAW_DATA:
        # 显示完整原始数据
        print(json.dumps(event, indent=2, ensure_ascii=False))
        print("-" * 80)
        return

    # 简化版本 - 只显示关键信息
    exchange = event.get("exchange", "N/A")
    stream = event.get("stream", "N/A")
    event_type = event.get("event_type", "N/A")
    ts_exchange = event.get("ts_exchange", 0)

    # 转换时间戳为可读格式
    try:
        if ts_exchange > 1e12:  # 毫秒时间戳
            time_str = datetime.fromtimestamp(ts_exchange / 1000).strftime("%H:%M:%S.%f")[:-3]
        else:  # 秒时间戳
            time_str = datetime.fromtimestamp(ts_exchange).strftime("%H:%M:%S.%f")[:-3]
    except (OSError, ValueError, OverflowError):
        time_str = "N/A"

    print(f"⏰ {time_str} | {exchange.upper()} | 事件类型: {event_type}")

    # 订单更新
    if event.get("type") == "order":
        symbol = event.get("symbol", "N/A")
        order_id = event.get("order_id", "N/A")
        client_order_id = event.get("client_order_id", "N/A")
        side = event.get("side", "N/A")
        order_type = event.get("order_type", "N/A")
        status = event.get("status", "N/A")
        price = event.get("price", 0)
        orig_qty = event.get("orig_qty", 0)
        filled_qty = event.get("filled_qty", 0)

        print(f"  📋 订单更新")
        print(f"  交易对: {symbol}")
        print(f"  订单ID: {order_id} | 客户订单ID: {client_order_id}")
        print(f"  方向: {side} | 类型: {order_type} | 状态: {status}")
        print(f"  价格: ${price} | 数量: {orig_qty} | 已成交: {filled_qty}")

    # 成交更新
    elif event.get("type") == "trade":
        symbol = event.get("symbol", "N/A")
        trade_id = event.get("trade_id", "N/A")
        order_id = event.get("order_id", "N/A")
        side = event.get("side", "N/A")
        last_price = event.get("last_price", 0)
        last_qty = event.get("last_qty", 0)
        fee = event.get("fee", 0)
        fee_asset = event.get("fee_asset", "N/A")
        is_maker = event.get("is_maker", False)

        print(f"  💰 成交更新")
        print(f"  交易对: {symbol}")
        print(f"  成交ID: {trade_id} | 订单ID: {order_id}")
        print(f"  方向: {side} | {'Maker' if is_maker else 'Taker'}")
        print(f"  成交价: ${last_price} | 成交量: {last_qty}")
        print(f"  手续费: {fee} {fee_asset}")

    print("-" * 80)


async def main():
    """主函数"""
    print(f"开始订阅 Backpack 用户订单和成交 WebSocket...")
    print(f"API Key: {API_KEY[:8]}...")
    print("=" * 80)

    # 创建 WebSocket 客户端
    ws_client = BackpackUserWS(
        api_key=API_KEY,
        secret=SECRET,
        on_event=on_event,
    )

    # 运行 WebSocket 客户端（会自动重连）
    await ws_client.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
