# XAU 套利策略运行指南

## 环境与配置
1) 安装依赖（仓库根目录）：
```bash
pip install -e .
```
2) 设置环境变量（示例）：
```bash
# Aster
export ASTER_API_KEY=your_aster_key
export ASTER_SECRET_KEY=your_aster_secret

# Backpack
export BACKPACK_KEY=your_backpack_key
export BACKPACK_SECRET=your_backpack_secret

# 其他可选
export DRY_RUN=true          # 默认 true；设为 false 才会真实下单
export ASTER_SYMBOL=XAUUSDT  # 如需换合约在此覆盖
export BACKPACK_SYMBOL=PAXG_USDC_PERP  # 请填 Backpack 实际可交易的标的
```
3) 默认符号：
- Aster: `XAUUSDT`
- Backpack: 请确认实际有此品种；默认示例为 `PAXG_USDC_PERP`，如无对应标的则无法对冲
（如需修改，创建自定义 `StrategyConfig`，或扩展 `runner.py` 读取配置）

## 运行
```bash
python -m strategies.xau_arbitrage.runner
```
行为：
- 启动 Aster/Backpack 行情 WS，缓存 BBO；
- Aster 每 10 秒撤旧挂新 0.1%/0.2%/0.3% 买卖限价单（量为 `order_size`，默认 0.1）；
- 收到 Aster 成交（用户流）后，在 Backpack 反向对冲同量；30 秒未成交则取消并市价（或激进限价）对冲；
- `DRY_RUN=true` 时只打印日志，不下单。

## 关键参数（`StrategyConfig`）
- `order_size`: 单笔报价数量（默认 0.1）
- `price_offsets`: [0.001, 0.002, 0.003] 对应 ±0.1/0.2/0.3%
- `quote_interval_sec`: 报价循环间隔（默认 10s）
- `hedge_timeout_sec`: 对冲限价等待超时（默认 30s）
- `poll_interval_sec`: 对冲订单轮询间隔（默认 1s）
- `aggressive_slippage`: 超时后的滑点比例（默认 0.0005，5bp）
- `dry_run`: True/False 控制是否真实下单
- `use_user_stream`: 是否使用 Aster 用户流捕捉成交

## Demo 日志（dry-run，截取）
```
2024-05-01 12:00:00,100 - INFO - [aster-user] connected with listenKey: abcd1234...
2024-05-01 12:00:00,200 - INFO - XAU arbitrage strategy started.
2024-05-01 12:00:10,005 - INFO - [dry-run] buy 0.1 @ 2320.1234
2024-05-01 12:00:10,006 - INFO - [dry-run] sell 0.1 @ 2324.7870
2024-05-01 12:00:10,007 - INFO - [dry-run] buy 0.1 @ 2317.8034
2024-05-01 12:00:10,008 - INFO - [dry-run] sell 0.1 @ 2327.1070
2024-05-01 12:00:15,300 - INFO - Aster fill detected 123456 BUY 0.05 @ 2322.1000
2024-05-01 12:00:15,301 - INFO - [dry-run] hedge sell 0.05 @ 2321.9000 (from 123456)
```

## 注意事项
- 真实交易前将 `DRY_RUN=false`，并确认 API Key 权限与资金量充足。
- Aster 用户流 listenKey 自动保活；断线自动重连，但极端情况下需重启。
- Backpack 是否支持市价单取决于交易所配置；若失败会退回激进限价。
- 若修改符号/精度，请确保与交易所实际合约一致。
