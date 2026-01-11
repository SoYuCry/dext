# 统一客户端重构方案

## 1. 架构概览
- 目标：移除 `base_client.py`，集中公共逻辑到 `api/base`，每个交易所单文件实现。
- 目录：
  ```
  api/
    base/
      __init__.py
      exchange.py   # 通用基类（同步请求、精度/安全取值/签名钩子）
      errors.py     # 统一错误层级
      types.py      # 统一结构（Ticker/Order/Market 等）
      precise.py    # 精度运算工具
    __init__.py     # 工厂 + 兼容别名
    backpack.py     # 单文件交易所（官方生成代码）
    aster.py        # 单文件交易所（由 aster_client 重写）
    hyperliquid.py  # 单文件交易所（官方生成代码）
    lighter.py      # 单文件交易所（本地封装 + signer）
  ```
- 规则：一交易所一文件，不再拆分 client/wrapper。公共工具集中在 `api/base`。
- 兼容：保留 `get_client(name, config)` 工厂与旧别名。

## 2. 基础层（api/base）
- `exchange.Exchange`：同步基类，包含：
  - `describe()` 模板、`required_credentials`、`has`、`urls`、`timeframes`、`fees` 占位。
  - 市场工具：`load_markets()`、`market()`、`market_id()`、`safe_market()`、`safe_symbol()`、`safe_currency_code()`。
  - 解析工具：`safe_value/string/integer/number/datetime`、`sum`、`omit`、`group_by`、`index_by`、`parse_balance`、`account`、`balance()`。
  - 请求管线：`rateLimit` 限速、`request`/`fetch2`，`requests.Session` + 代理/超时，JSON 解析与错误映射。
  - 钩子：`sign`（签名/组装请求）、`handle_errors`（响应错误）、`nonce()`。
  - 精度：`currency_to_precision`、`price_to_precision`、`amount_to_precision`、`cost_to_precision`。
- `precise.py`：精度运算工具。
- `types.py`：统一结构体（Ticker/OrderBook/Trade/Balance/Position/Order/Market 等）。
- `errors.py`：统一错误层级与映射。
- 配置读取：`apiKey/secret/password/uid/proxies/timeout/rateLimit/verbose` 等，集成 `proxy_utils.get_proxy_config()`。

## 3. 交易所实现
- 形态：每个文件定义小写类并导出大写别名，方法名遵循统一接口（`fetch_markets`、`fetch_ticker`、`create_order`、`cancel_order`、`fetch_balance`、`fetch_positions` 等）。

### 3.1 Backpack
- 来源：官方生成代码（已内置）。
- 调整：切换到本地 base 导入，维持接口/限速/错误处理。

### 3.2 Aster
- 从 `api/aster_client.py` 重写为单文件类，继承基类。
- `describe`：`id='aster'`，REST `https://fapi.asterdex.com`，能力覆盖行情/下单/撤单/持仓等。
- 签名：HMAC-SHA256，参数含 `timestamp`、`recvWindow`（默认 5000），头部 `X-MBX-APIKEY`。
- 路由：`public` 与 `private` 分区（ping、ticker、depth、account、position、orders 等）。
- 解析：市场/行情/深度/成交/订单/余额/持仓；状态映射 NEW|PARTIALLY_FILLED|FILLED|CANCELED。
- 错误映射：如 `-1121`→`BadSymbol`、`-1021`→`InvalidNonce`、`-2015`→`AuthenticationError` 等。

### 3.3 Hyperliquid
- 来源：官方生成代码，保持端点与能力一致。

### 3.4 Lighter
- 本地封装，使用原生 signer。
- 市场：从 `/api/v1/orderBookDetails` 构建缓存，解析精度/步长/最小下单。
- 订单：签名下单/撤单需本地 signer 动态库与私钥；最小名义金额 10u；支持市价/限价、timeInForce、postOnly、reduceOnly。
- 查询：行情、深度、余额、持仓、未成交订单。

## 4. 兼容与配置
- 工厂 `get_client(name, config)` 返回对应实例；保留旧别名（如 `BPClient`）。
- `proxy_utils.py` 统一代理；`logger.py` 统一日志。
- 公共 API：方法名保持统一，返回结构为普通字典（附带 `info` 原始数据）。

## 5. 迁移步骤
1) 引入 `api/base/precise.py`，扩展 `api/base/exchange.py` 工具与钩子。
2) 迁移 Backpack 到 `api/backpack.py`，切换至本地基类。
3) 重写 `api/aster.py`，去除 `base_client` 依赖。
4) 新增 Lighter 封装与 signer 帮助。
5) 更新 `api/__init__.py` 懒加载导出，保留旧别名。
6) 如有新增遗留客户端，按同样模式迁移；移除无用的 `api/exchanges/` 文件。
7) 补充冒烟/单元测试（待后续）。

## 6. 未决/假设
- Aster K 线接口假设与 `/fapi/v1/klines` 对齐。
- 下单默认支持 `limit`/`market` 与 `reduceOnly`；停止单后续再加。
- WebSocket 暂不覆盖，仅 REST。
