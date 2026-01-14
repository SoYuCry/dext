# XAU 套利策略实现计划

## 背景与目标
- 本仓库定位为统一交易 API（不含策略），但为降低跨仓库导入成本，临时在此落地 XAU 套利（Aster ↔ Backpack）策略。
- 需求：Aster 挂 0.1%/0.2%/0.3% 报价（10s 轮换），成交后立刻在 Backpack 对冲同量，30s 未对冲完则市价对冲。
- 更重要目标：检视当前架构对策略开发的友好度，不足处同步补齐/抽象，保证后续可迁移。

## 当前架构评估
- **优点**：`api.get_client` 统一工厂；Aster/Backpack 深度与 BBO WebSocket 已有；ccxt-style API 能直接下单/撤单/查余额。
- **痛点**：
  - 无策略层：缺少事件循环、订单状态机、风险/配置管理，直接在主仓库写策略会造成耦合与可读性下降。
  - 成交通知缺口：现有 WS 只含行情，无用户流，需自行轮询 `fetch_open_orders`/`fetch_my_trades` 才能捕获成交。
  - 接口过重：ccxt 生成文件冗长且同步调用，缺少轻量包装与类型约束，不利于快速编排策略。
- **调整方向**：保持 API 层不动，新增 `strategies/xau_arbitrage/` 独立包（可整体迁出），提供轻量包装 + 有限状态机，避免污染核心客户端。

建议目录：
```
strategies/
  xau_arbitrage/
    __init__.py
    config.py        # 参数、API key 读取，价格偏移、轮询周期、滑点等
    symbols.py       # Aster/Backpack 符号/合约单位映射（确认 XAU 合约代码与合约乘数）
    exchanges.py     # 封装 get_client，提供 create_order/cancel_order/fetch_open_orders 的薄包装
    feeds.py         # Aster/Backpack WS 行情聚合，输出最新 mid/BBO
    quotes.py        # 报价管理：10s 循环挂/撤单，跟踪订单 ID
    hedge.py         # 成交检测 + 对冲状态机（30s 超时转市价）
    strategy.py      # 主控协程/事件循环，整合 quotes + hedge
    runner.py        # 启动入口，加载配置并启动 asyncio 任务
```

## 设计方案（行为）
1. **报价循环（Aster）**
   - 数据源：取 Aster mid（深度一档均价）或 ticker last 作为锚价。
   - 计算 0.1%/0.2%/0.3% 的买卖价，按当前剩余仓位/风险参数决定下单数量。
   - 每 10s：撤掉上一轮所有活跃报价（批量 `cancel_order`），根据最新锚价重挂。
2. **成交捕获**
   - 轮询 `fetch_open_orders` + `fetch_my_trades`（按时间游标）检测新成交；对 partial fill 记录剩余量。
   - 记录成交事件：side/filled_qty/avg_price/order_id/timestamp。
3. **对冲（Backpack）**
   - 收到 Aster 成交事件：查询 Backpack BBO，按反向方向在买1/卖1 位置限价对冲同量（含可配置溢价）。
   - 启动 30s 超时计时；期间轮询 `fetch_open_orders`/`fetch_order` 获取对冲订单进度。
   - 超时未完全成交：撤销剩余限价，按剩余量市价对冲；若市价不可用则在 BBO 上加滑点重挂并重启计时。
4. **状态与风控**
   - 维护内存状态：当前行情（mid/BBO）、报价订单簿、未对冲成交队列、对冲任务表。
   - 配置项：最小下单量、单笔/总持仓上限、最大未对冲敞口、重试次数/间隔、价格精度校准。
5. **观测与日志**
   - 统一用 `logger.py` 输出：下单/撤单结果、成交事件、对冲耗时、异常重试。
   - 关键指标（后续可埋点）：报价命中率、对冲滑点、对冲超时次数。

## 落地步骤
1. 新增 `strategies/xau_arbitrage/` 目录与基础文件骨架（config/symbols/exchanges/feeds/strategy）。
2. `exchanges.py`：封装 Aster/Backpack 客户端创建，提供简化下单/撤单/订单查询方法并适配精度（tick size/amount step）。
3. `feeds.py`：复用现有 WS 客户端，维持最新 mid 与 BBO 缓存；提供同步读取接口（带超时 fallback 到 REST ticker）。
4. `quotes.py`：实现 10s 报价循环（挂 → 记录 ID → 到期撤），考虑部分成交后的剩余量处理。
5. `hedge.py`：实现成交轮询 + 对冲状态机（限价下单、进度跟踪、超时转市价）。
6. `strategy.py`/`runner.py`：组装 asyncio 任务、共享状态、信号处理（优雅停机时撤销挂单）。
7. 验证：本地 dry-run（关闭真实下单）日志演练；小仓位实盘冒烟，记录指标并调整参数。

## 风险与待确认
- 确认 Aster/Backpack 的 XAU 合约代码、合约乘数、下单精度与是否支持市价单。
- 用户层 WebSocket 若缺失，只能轮询，需评估 10s/30s 频率对 API 额度的影响。
- 对冲时的仓位方向/净敞口策略（是否需要 net 结算与持仓上限）。
- 市价单风险控制：需要价格保护（滑点上限）或在 BBO 基础上限价代替。
- 部署位置：后续若迁回独立策略仓库，可整体搬运 `strategies/xau_arbitrage/` 包并复用 `api` 客户端。
