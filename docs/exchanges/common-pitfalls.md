# 交易所接入常见错误总结

> **文档目的**: 记录在接入 Aster 交易所时遇到的所有问题及解决方案，为后续接入其他交易所提供参考。
> 
> **创建时间**: 2026-01-17  
> **适用场景**: 交易所 API 集成、合约交易策略开发

---

## 📋 问题清单总览

| # | 问题类型 | 严重程度 | 修复难度 | Commit |
|---|---------|---------|---------|--------|
| 1 | URL 路径重复 | 🔴 高 | ⭐ 简单 | 238849b |
| 2 | timeInForce 参数缺失 | 🔴 高 | ⭐ 简单 | c39f92a |
| 3 | set_leverage 方法未实现 | 🟡 中 | ⭐⭐ 中等 | b0caac5 |
| 4 | 杠杆设置过高 | 🟡 中 | ⭐ 简单 | - |
| 5 | 保证金不足误判 | 🔴 高 | ⭐⭐⭐ 复杂 | b571962 |
| 6 | USD 金额未转换为合约数量 | 🔴 高 | ⭐⭐ 中等 | 485cb50 |
| 7 | amount_to_precision 精度 bug | 🔴 高 | ⭐⭐⭐ 复杂 | 4644be7 |

---

## 🔍 详细问题分析

### 问题 1: URL 路径重复

#### 错误现象
```
API request failed: 404 Not Found
Actual URL: https://fapi.asterdex.com/fapi/v1/fapi/v1/order
```

#### 根本原因
在 `api/aster.py` 的 API 配置中，`urls.api.public` 已经包含了 `/fapi/v1`，但在定义 endpoints 时又重复添加了 `fapi/v1`：

```python
# 错误配置
self.urls = {
    'api': {
        'public': 'https://fapi.asterdex.com/fapi/v1',  # ← 已有路径
        # ...
    }
}
self.api = {
    'public': {
        'get': [
            'fapi/v1/exchangeInfo',  # ← 重复！
            'fapi/v1/depth',
        ]
    }
}
```

#### 解决方案
移除 endpoints 定义中的重复路径前缀：

```python
self.api = {
    'public': {
        'get': [
            'exchangeInfo',  # ✅ 正确
            'depth',
        ]
    }
}
```

#### 预防措施
✅ **检查清单**:
- [ ] 确认 `urls.api.public/private` 的基础路径
- [ ] endpoints 定义只包含相对路径
- [ ] 测试时打印完整 URL 验证

---

### 问题 2: timeInForce 参数缺失

#### 错误现象
```json
{
  "code": -1102,
  "msg": "Mandatory parameter 'timeInForce' was not sent"
}
```

#### 根本原因
Aster 交易所要求所有限价单必须包含 `timeInForce` 参数，但基类的默认实现没有自动添加。

#### 解决方案
在 `create_order` 方法中强制添加默认值：

```python
def create_order(self, symbol, type, side, amount, price=None, params={}):
    # ...
    if type == "limit":
        # Aster requires timeInForce for limit orders
        time_in_force = self.safe_string(params, "timeInForce", "GTC")
        request["timeInForce"] = time_in_force
        params = self.omit(params, "timeInForce")
    # ...
```

#### 预防措施
✅ **检查清单**:
- [ ] 阅读交易所 API 文档的 "Mandatory Parameters" 部分
- [ ] 测试限价单、市价单、止损单等所有订单类型
- [ ] 检查是否需要其他必填参数（如 `newOrderRespType`）

---

### 问题 3: set_leverage 方法未实现

#### 错误现象
```python
AttributeError: 'aster' object has no attribute 'set_leverage'
```

#### 根本原因
基类没有提供 `set_leverage` 的通用实现，需要每个交易所自己实现。

#### 解决方案

**步骤 1**: 在 `self.api` 中添加 endpoint：

```python
self.api = {
    'private': {
        'post': [
            'fapi/v1/order',
            'fapi/v1/leverage',  # ← 添加
        ]
    }
}
```

**步骤 2**: 实现方法：

```python
def set_leverage(
    self, leverage: int, symbol: Optional[str] = None, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Set leverage for a symbol on Aster exchange.
    
    Args:
        leverage: Leverage multiplier (e.g., 5 for 5x)
        symbol: Trading pair symbol (e.g., 'XAU/USDT')
        params: Additional parameters
        
    Returns:
        Response from the exchange
    """
    if symbol is None:
        raise ArgumentsRequired(self.id + " set_leverage() requires a symbol argument")
    params = params or {}
    self.load_markets()
    market = self.market(symbol)
    request = {
        "symbol": market["id"],
        "leverage": int(leverage),
    }
    response = self.request("fapi/v1/leverage", "private", "POST", self.extend(request, params))
    return response
```

#### 预防措施
✅ **检查清单**:
- [ ] 查看交易所是否支持杠杆交易
- [ ] 确认 API endpoint 和参数格式
- [ ] 测试不同杠杆倍数（1x, 5x, 10x, 20x）
- [ ] 检查是否有最大杠杆限制

---

### 问题 4: 杠杆设置过高

#### 错误现象
```json
{
  "code": -2027,
  "msg": "The current symbol's leverage exceeds the maximum supported leverage"
}
```

#### 根本原因
账户杠杆设置为 20x，但 XAUUSDT 交易对的最大允许杠杆可能是 10x 或更低。

#### 解决方案
设置为安全的杠杆倍数（建议 5x）：

```python
aster.set_leverage(5, 'XAU/USDT')
```

#### 预防措施
✅ **检查清单**:
- [ ] 查询交易对的最大杠杆限制
- [ ] 新策略启动时先用低杠杆测试（1x-5x）
- [ ] 在配置文件中明确记录杠杆设置

---

### 问题 5: 保证金不足误判

#### 错误现象
```json
{
  "code": -2019,
  "msg": "Margin is insufficient"
}
```

账户余额明明有 100 USDT，但仍然报保证金不足。

#### 根本原因（多层次）

**误判原因 1**: 资金分布问题
- USDF: 45.70（理财账户，**可以**作为保证金）
- USDT: 54.75（合约账户）
- 总计: 100 USDT ✅

**真正原因**: 订单大小配置错误！

配置文件中：
```python
order_sizes: List[float] = [30.0, 30.0, 40.0]  # USD 金额
```

但代码直接传给交易所：
```python
# 错误！直接传了 USD 金额作为合约数量
await exchange.create_limit_order(symbol, "buy", 30.0, price)
```

**实际效果**:
- XAU 价格: $4,596
- 传入 amount=30
- 交易所理解为: 30 个 XAU 合约
- 名义价值: 30 × $4,596 = **$137,880**
- 需要保证金 (5x): $137,880 ÷ 5 = **$27,576**
- 你只有: $100 → 保证金不足！

#### 解决方案

**方案 1**: 减小订单大小（临时方案）
```python
order_sizes: List[float] = [10.0, 10.0, 15.0]  # 减小到 10-15 USD
```

**方案 2**: 修复 USD 到合约数量的转换（根本方案，见问题 6）

#### 预防措施
✅ **检查清单**:
- [ ] 明确区分 "USD 金额" 和 "合约数量"
- [ ] 计算实际保证金需求: `(订单总价值 ÷ 杠杆) × 1.5`（留 50% 缓冲）
- [ ] 检查账户余额分布（现货、合约、理财）
- [ ] 测试时先用极小金额（如 5 USD）

---

### 问题 6: USD 金额未转换为合约数量

#### 错误现象
见问题 5，保证金不足的根本原因。

#### 根本原因
策略配置使用 USD 金额便于理解和控制风险：
```python
order_sizes: List[float] = [10.0, 10.0, 15.0]  # USD
```

但 `create_order` 的 `amount` 参数需要的是**合约数量**，不是金额！

#### 解决方案
在下单前进行转换：

```python
# 修改前
for i, (off, size) in enumerate(zip(self.price_offsets, self.order_sizes)):
    buy_price = price * (1 - off)
    sell_price = price * (1 + off)
    
    # ❌ 直接传 USD 金额
    await self.exchange.create_limit_order(self.symbol, "buy", size, buy_price)

# 修改后
for i, (off, size_usd) in enumerate(zip(self.price_offsets, self.order_sizes)):
    buy_price = price * (1 - off)
    sell_price = price * (1 + off)
    
    # ✅ 转换为合约数量
    buy_contracts = size_usd / buy_price
    sell_contracts = size_usd / sell_price
    
    await self.exchange.create_limit_order(self.symbol, "buy", buy_contracts, buy_price)
```

#### 验证计算
```python
# XAU 价格: $4,596
# 想下 10 USD 的单
contracts = 10 / 4596 = 0.002176 XAU
# 验证: 0.002176 × 4596 = $10 ✅
```

#### 预防措施
✅ **检查清单**:
- [ ] 明确 API 文档中 `amount` 参数的单位（合约数量 vs 金额）
- [ ] 配置文件中注释清楚单位
- [ ] 添加单元测试验证转换逻辑
- [ ] 下单后打印日志确认实际金额

---

### 问题 7: amount_to_precision 精度处理 bug

#### 错误现象
```
amount of XAU/USDT must be greater than minimum amount precision of 3
```

即使 `amount = 0.002` 符合 `stepSize = 0.001`，仍然报错。

#### 根本原因

**市场规则**:
```python
{
    'precision': {'amount': 3.0, 'price': 2.0},
    'limits': {
        'amount': {'min': 0.001, 'max': 1000},
    },
    'info': {
        'filters': [
            {'filterType': 'LOT_SIZE', 'stepSize': '0.001', 'minQty': '0.001'},
            {'filterType': 'MIN_NOTIONAL', 'notional': '5'}
        ]
    }
}
```

**精度处理 bug**:
- Aster 使用 `TICK_SIZE` 精度模式（mode=4）
- `precision['amount'] = 3` 在此模式下被错误解释为 "最小变动单位是 3"
- 而不是 "3 位小数"
- 导致 `amount_to_precision(0.002)` 返回 `'0'` 并报错

#### 解决方案
绕过 `amount_to_precision` 方法，手动处理精度：

```python
# 修改前
if amount is not None:
    request["quantity"] = self.amount_to_precision(symbol, amount)  # ❌ 有 bug

# 修改后
if amount is not None:
    # Manual precision handling for amount
    # Aster XAUUSDT has stepSize=0.001 (3 decimal places)
    # amount_to_precision has a bug in TICK_SIZE mode
    amount_str = f"{float(amount):.3f}"  # ✅ 强制 3 位小数
    request["quantity"] = amount_str
```

#### 深层原因分析

`amount_to_precision` 在 `TICK_SIZE` 模式下的实现：

```python
# exchanges/base/exchange.py (简化版)
def amount_to_precision(self, symbol, amount):
    market = self.market(symbol)
    precision = market['precision']['amount']
    
    if self.precisionMode == TICK_SIZE:
        # Bug: 直接用 precision 作为 tick size
        # 但 Aster 的 precision=3 实际是小数位数，不是 tick size
        return self.decimal_to_precision(amount, TICK_SIZE, precision)
```

#### 预防措施
✅ **检查清单**:
- [ ] 测试极小金额订单（如 0.001 合约）
- [ ] 检查交易所的精度模式（DECIMAL_PLACES vs TICK_SIZE）
- [ ] 查看 `market['info']['filters']` 中的实际规则
- [ ] 必要时绕过基类的精度方法，手动处理
- [ ] 添加日志打印最终发送的 `quantity` 值

---

## 🎯 通用接入流程（防错清单）

### 阶段 1: API 配置（Day 1）

```python
# ✅ 检查清单
□ 1. 确认 base URL 不包含重复路径
□ 2. 测试 public endpoints（exchangeInfo, ticker）
□ 3. 测试 private endpoints（balance, positions）
□ 4. 验证签名算法（打印请求头和签名）
```

### 阶段 2: 订单测试（Day 2）

```python
# ✅ 检查清单
□ 1. 测试市价单（最简单）
□ 2. 测试限价单（检查必填参数）
□ 3. 测试订单查询和取消
□ 4. 验证订单状态映射
```

### 阶段 3: 精度和限制（Day 3）

```python
# ✅ 检查清单
□ 1. 获取市场规则（filters, precision）
□ 2. 测试最小订单金额
□ 3. 测试精度处理（amount, price）
□ 4. 验证 stepSize 和 tickSize
```

### 阶段 4: 杠杆和保证金（Day 4）

```python
# ✅ 检查清单
□ 1. 实现 set_leverage 方法
□ 2. 测试不同杠杆倍数
□ 3. 计算保证金需求
□ 4. 测试保证金不足场景
```

### 阶段 5: 策略集成（Day 5）

```python
# ✅ 检查清单
□ 1. 配置文件单位明确（USD vs 合约数量）
□ 2. 实现金额转换逻辑
□ 3. 添加日志验证实际下单参数
□ 4. 小金额测试（5-10 USD）
```

---

## 💡 设计模式最佳实践

> 本节总结在重构过程中学习到的设计模式和最佳实践

### 1. 统一请求处理架构

**模式**：所有 API 调用通过统一的 `_request()` 方法

**优势**：
- 集中化的错误处理
- 一致的签名流程
- 便于调试和日志记录
- 简化测试和 mock

**实现示例**：
```python
def _request(self, endpoint: Entry, params=None, config=None):
    """统一的请求-响应生命周期"""
    # 1. 构建请求
    # 2. 签名（如果私有端点）
    # 3. 发送请求
    # 4. HTTP 错误处理
    # 5. 业务错误处理
    # 6. 响应解析
    return response
```

### 2. 两层错误处理

**Layer 1 - HTTP 错误** (`_handle_http_error`)：
- 400 → BadRequest
- 401/403 → AuthenticationError
- 404 → BadSymbol
- 429 → RateLimitExceeded
- 5xx → ExchangeNotAvailable

**Layer 2 - 业务错误** (`parse_error`)：
- 每个交易所实现自己的错误码映射
- 使用 `throw_exactly_matched_exception()` 精确匹配
- 使用 `throw_broadly_matched_exception()` 模糊匹配

**为什么需要两层**：
- HTTP 层由基类统一处理，避免重复代码
- 业务层处理交易所特定的错误码（如 Binance 的 -1000 系列）

### 3. 端点配置分离

**模式**：API 端点定义与业务逻辑分离

**优势**：
- 端点定义集中管理（`endpoints/{exchange}.py`）
- 业务逻辑专注于数据转换和错误处理
- 便于 API 版本升级
- 自动生成 API 文档

**Entry 对象结构**：
```python
Entry(
    path='api/v1/order',         # API 路径
    visibility='private',         # public/private
    method='POST',                # HTTP 方法
    config={'cost': 1}            # 速率成本等配置
)
```

### 4. 精度处理的陷阱

**问题**：`amount_to_precision()` 在某些精度模式下有 bug

**症状**：
- `stepSize=0.001` 的市场，`amount=0.002` 被格式化为 `'0'`
- TICK_SIZE 模式下，precision 被错误解释

**解决方案**：
```python
# 绕过基类的精度方法，手动处理
amount_str = f"{float(amount):.3f}"  # 根据 stepSize 确定小数位数
request["quantity"] = amount_str
```

**预防措施**：
- 测试极小金额订单
- 查看 `market['info']['filters']` 获取真实规则
- 必要时绕过基类的精度方法

### 5. 声明式 API 定义

**ImplicitAPI 模式**：
```python
self.endpoints = BackpackEndpoints()

# 自动生成方法：
# self.public_get_api_v1_ticker() → GET /api/v1/ticker
# self.private_post_api_v1_order() → POST /api/v1/order (signed)
```

**优势**：
- 减少样板代码
- 类型安全（Entry 对象）
- 自文档化

### 6. 综合错误码覆盖

**对比**：
- **Aster（重构后）**：40+ 错误码精确映射
- **之前实现**：仅 8 个通用错误

**最佳实践**：
- 阅读交易所 API 文档的完整错误码列表
- 为每个错误码选择合适的 dext 异常类型
- 使用 `exact` 和 `broad` 两种匹配策略

**示例**：
```python
self.exceptions = {
    'exact': {
        '-1000': ExchangeError,      # 未知错误
        '-1021': InvalidNonce,        # 时间戳错误
        '-2010': InsufficientFunds,   # 余额不足
        '-2011': OrderNotFound,       # 订单不存在
    },
    'broad': {
        'insufficient': InsufficientFunds,
        'invalid order': InvalidOrder,
    }
}
```

---

## 📚 参考资源

### 必读文档
1. **交易所 API 文档**: 
   - Aster: https://docs.asterdex.com/api
   - 重点章节: Authentication, Order Placement, Error Codes

2. **本项目 API 文档**:
   - 交易所使用指南: `exchanges/README.md`
   - 各交易所文档: `docs/exchanges/` 目录

3. **本项目文档**:
   - `ARCHITECTURE.md`: 系统架构
   - `LIVE_TRADING_CHECKLIST.md`: 实盘前检查清单

### 调试工具

```python
# 1. 打印完整请求 URL
import logging
logging.basicConfig(level=logging.DEBUG)

# 2. 查看市场规则
market = exchange.market('XAU/USDT')
print(json.dumps(market, indent=2))

# 3. 测试精度转换
amount = 0.002176
formatted = f"{amount:.3f}"  # '0.002'
print(f"Original: {amount}, Formatted: {formatted}")

# 4. 计算保证金需求
price = 4596
contracts = 0.002
notional = price * contracts  # 9.192 USD
margin_required = notional / leverage  # 1.84 USD (5x)
```

---

## 🔄 版本历史

| 日期 | 版本 | 修改内容 |
|------|------|---------|
| 2026-01-17 | v1.0 | 初始版本，记录 Aster 接入的 7 个问题 |

---

## 📝 后续改进建议

1. **自动化测试**:
   - 为每个问题创建单元测试
   - 添加 CI/CD 检查

2. **配置验证**:
   - 启动时自动检查配置合理性
   - 验证保证金充足性

3. **错误处理**:
   - 统一错误码映射
   - 自动重试机制

4. **文档完善**:
   - 为每个交易所创建接入指南
   - 记录特殊配置和注意事项

---

**最后更新**: 2026-01-17 23:38  
**维护者**: Liuc  
**反馈**: 如有问题或补充，请更新此文档
