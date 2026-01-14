# WebSocket 统一架构计划（轻量可扩展）

## 目标与约束
- 目标：用一套轻量的 asyncio WebSocket 基类覆盖公开行情与用户流，Backpack/Aster 共享；事件格式统一，便于策略消费。
- 约束：先从基础功能开始，保持小而清晰；不引入过度封装（例如线程 + 复杂备援）；保留未来扩展点（私有流 keepalive、重连退避、标准化事件）。
- 现状：`api/ws/base.py` 已有简化公共流基类（Aster/Backpack 行情在用）；`docs/examples/ws_client/` 存放朋友的重型线程版，仅作参考，不直接继承。

## 设计要点
- **基础类（asyncio）**：负责连接、重连、订阅、消息循环、JSON decode。可选钩子：`on_connect`、`on_reconnect`、`on_error`、`on_close`。
- **事件格式**：统一输出字典，字段包含：
  - 公共流：`exchange`、`stream` (`bbo`/`l2`)、`symbol`、`ts_exchange`、`ts_local`、`bids`、`asks`、`raw`
  - 用户流：`exchange`、`stream: "user"`、`event_type`（如 `ORDER_TRADE_UPDATE`）、`type` (`order`/`account`/`margin_call`/`config_update`/`expired`)、订单字段（side/status/filled/price/...）、`raw`
- **最小功能集**（先做）：连接+订阅、公平重连（固定延时）、日志、事件回调。
- **可拓展点**（后续再加）：指数退避重连、REST 备援、通用心跳/延迟指标、批量订阅管理、标准化 dataclass 封装。
- **私有流特例**：Binance 风格 listenKey（Aster）需要 REST 创建/续期；保活单独协程。

## 分阶段计划
1) **基类巩固**
   - 在 `api/ws/base.py` 补充：可插拔 reconnect 参数（延时/重试次数）、`on_connect`/`on_error` 钩子、基础日志；保留 asyncio 栈。
   - 约定事件格式（见上）并添加简短注释。
2) **Aster 用户流迁移到基类**
   - 让 `AsterUserWS` 继承基类（仍包含 listenKey 创建/keepalive）；按统一事件格式输出。
3) **Aster 行情迁移到基类**
   - 调整 `api/ws/aster.py` 继承基类，使用相同事件字段命名（`stream="l2"`）。
4) **Backpack 行情迁移**
   - 将 `api/ws/backpack.py` 迁移到基类，统一事件字段，并保留 `include_depth` 功能。
5) **工厂与命名**
   - `api/ws/__init__.py` 提供 `get_ws_client`（公共）、`get_user_ws_client`（用户流）；文档化必需参数（如 Aster 用户流 `api_key`）。
6) **兼容与清理**
   - 保留 `docs/examples/ws_client/` 作为 legacy 参考（短期不删除）；在 README/ARCHITECTURE 添加“新接口推荐使用 asyncio ws”说明。
7) **后续可选**
   - 添加指数退避、metrics、REST 备援开关；补充 Backpack 私有流（若需要）与 Hyperliquid/Lighter 对齐。

## 开发顺序（落地细节）
1. 基类增强（不破坏当前 Aster/Backpack 调用），增加可配置重连参数与事件注释。
2. 改造 `AsterUserWS` → 继承基类；保持 listenKey 逻辑，统一事件字典。
3. 改造 `AsterWS`（公开行情）→ 继承基类，校正字段。
4. 改造 `BackpackWS` → 继承基类，统一字段；验证 `include_depth`。
5. 更新工厂函数与示例，文档说明参数/事件形态。
6. （可选）为策略层写一个简单消费示例，验证用户流对冲逻辑的输入格式。

## 风险与TODO
- 依赖 `websockets`（asyncio），策略若用线程需封装桥接。
- Aster listenKey 的保活失败时需要重新创建并重连（后续实现指数退避）。
- Backpack 是否有私有流需确认，若有可沿用同基类模式。
- 在完成迁移前，旧 `docs/examples/ws_client/` 与新实现并存，需在说明文件标注推荐路径。
