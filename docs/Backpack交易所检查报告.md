# Backpack 交易所检查报告

> **检查时间**: 2026-01-17  
> **检查目的**: 对比 Aster 接入时遇到的问题，检查 Backpack 是否存在类似隐患

---

## 📋 检查结果总览

| 检查项 | Aster 状态 | Backpack 状态 | 风险等级 |
|--------|-----------|--------------|---------|
| URL 路径配置 | ❌ 有重复 | ✅ 正常 | 🟢 无风险 |
| timeInForce 参数 | ❌ 必填但未处理 | ⚠️ 非必填 | 🟡 低风险 |
| set_leverage 方法 | ❌ 未实现 | ⚠️ 不支持 | 🟡 需注意 |
| 精度处理 | ❌ amount_to_precision 有 bug | ✅ 正常工作 | 🟢 无风险 |
| USD 到合约转换 | ❌ 未转换 | ⚠️ **需要检查** | 🔴 **高风险** |
| 最小订单限制 | ✅ 符合 | ✅ 符合 | 🟢 无风险 |
| 价格差异对冲 | N/A | ⚠️ **需要处理** | 🟡 中风险 |

---

## 🔍 详细检查结果

### 1. ✅ URL 配置检查

**Backpack 配置**:
```python
'urls': {
    'api': {
        'public': 'https://api.backpack.exchange',
        'private': 'https://api.backpack.exchange',
    },
}
'api': {
    'public': {
        'get': {
            'api/v1/assets': 1,
            'api/v1/markets': 1,
            # ...
        }
    }
}
```

**结论**: ✅ **无问题**
- Base URL 不包含 `/api/v1`
- Endpoints 包含完整路径
- 不会出现 Aster 的路径重复问题

---

### 2. ⚠️ timeInForce 参数检查

**支持情况**:
```python
'timeInForce': {
    'GTC': True,   # Good Till Cancel
    'IOC': True,   # Immediate or Cancel
    'FOK': True,   # Fill or Kill
    'PO': True,    # Post Only
    'GTD': False,  # Good Till Date (不支持)
}
```

**当前代码**:
```python
# strategies/xau_arbitrage/exchanges.py:38
order = self.client.create_order(symbol, otype, side, amount, price)
```

**结论**: ⚠️ **低风险**
- Backpack 支持 timeInForce，但**不是必填参数**
- 如果不传，默认使用 GTC
- 建议：显式传递 `timeInForce='GTC'` 以提高代码可读性

**建议修改**:
```python
# 限价单显式指定 timeInForce
order = self.client.create_order(
    symbol, 'limit', side, amount, price,
    params={'timeInForce': 'GTC'}
)
```

---

### 3. ⚠️ set_leverage 方法检查

**Backpack 特性**:
```python
'has': {
    'setLeverage': False,  # 不支持
}
```

**原因**: Backpack 使用**账户级别杠杆**，不是交易对级别。

**当前影响**:
- 策略代码中没有调用 `set_leverage`
- Backpack 账户杠杆需要在网页端设置
- 无法通过 API 动态调整杠杆

**结论**: ⚠️ **需注意**
- 确保在 Backpack 网页端设置了合适的杠杆
- 建议杠杆：5x-10x（与 Aster 保持一致）
- 启动前检查账户杠杆设置

---

### 4. ✅ 精度处理检查

**市场规则**:
```python
{
    'precision': {
        'amount': 0.0001,  # stepSize
        'price': 0.01,     # tickSize
    },
    'limits': {
        'amount': {'min': 0.0001, 'max': None},
        'price': {'min': 0.01, 'max': 20000.0},
    }
}
```

**测试结果**:
```python
0.002172 -> '0.0021'  # ✅ 正确向下取整到 4 位小数
```

**结论**: ✅ **无问题**
- `amount_to_precision` 工作正常
- 不会出现 Aster 的 TICK_SIZE 模式 bug

---

### 5. 🔴 USD 到合约转换检查（重要！）

#### 问题描述

**Aster 端（做市）**:
- 交易对: XAU/USDT
- 价格: $4,596/XAU
- 订单配置: [10, 10, 15] USD
- 实际下单: 0.002 XAU（已修复转换）

**Backpack 端（对冲）**:
- 交易对: PAXG/USDC:USDC
- 价格: $4,604/PAXG
- 对冲数量: **直接使用 Aster 的合约数量**

#### 当前代码问题

```python
# strategies/xau_arbitrage/hedge.py:62
order = await self.exchange.create_limit_order(
    self.symbol, 
    hedge_side, 
    fill.qty,  # ← 直接使用 Aster 的数量！
    limit_price
)
```

**问题分析**:

场景：Aster 上成交了 0.002 XAU @ $4,596

| 方式 | Backpack 数量 | 名义价值 | 差异 |
|------|--------------|---------|------|
| ❌ 当前（直接用） | 0.002 PAXG @ $4,604 | $9.21 | +$0.02 |
| ✅ 正确（调整） | 0.001997 PAXG @ $4,604 | $9.19 | $0.00 |

**影响**:
- 价差 0.17% 时，每次对冲有 $0.02 误差
- 如果价差扩大到 1%，误差会达到 $0.09/单
- 长期累积会导致仓位不平衡

#### 解决方案

**方案 1: 根据价格比例调整数量（推荐）**

```python
# strategies/xau_arbitrage/hedge.py

async def _hedge_fill(self, fill: FillEvent) -> None:
    hedge_side = "sell" if fill.side.lower() == "buy" else "buy"
    
    # 获取当前价格
    aster_price = fill.price  # Aster 成交价
    backpack_bbo = self.feed.get_bbo("backpack")
    backpack_price = backpack_bbo.mid if backpack_bbo else aster_price
    
    # 🔧 根据价格比例调整对冲数量
    hedge_qty = fill.qty * (aster_price / backpack_price)
    
    # 精度处理
    # hedge_qty = self.exchange.client.amount_to_precision(self.symbol, hedge_qty)
    
    logger.info(
        f"hedge {hedge_side} {hedge_qty:.4f} @ {backpack_price:.2f} "
        f"(from Aster {fill.qty} @ {aster_price:.2f})"
    )
    
    # ... 后续下单逻辑
    order = await self.exchange.create_limit_order(
        self.symbol, hedge_side, hedge_qty, limit_price
    )
```

**方案 2: 使用 USD 名义价值对冲（更精确）**

```python
async def _hedge_fill(self, fill: FillEvent) -> None:
    hedge_side = "sell" if fill.side.lower() == "buy" else "buy"
    
    # 计算 USD 名义价值
    usd_notional = fill.qty * fill.price
    
    # 获取 Backpack 价格
    backpack_bbo = self.feed.get_bbo("backpack")
    limit_price = self._calc_hedge_price(hedge_side, backpack_bbo, slip=0.0, fallback=fill.price)
    
    # 根据 USD 计算对冲数量
    hedge_qty = usd_notional / limit_price
    
    logger.info(
        f"hedge {hedge_side} ${usd_notional:.2f} -> {hedge_qty:.4f} PAXG @ {limit_price:.2f}"
    )
    
    # ... 后续下单逻辑
```

**推荐**: 使用方案 2，因为：
- 更精确（基于实际 USD 价值）
- 自动处理价格差异
- 更容易理解和维护

---

### 6. ✅ 最小订单限制检查

**Backpack 限制**:
```python
Min amount: 0.0001 PAXG
Min USD value: $0.46 (at $4,604/PAXG)
```

**策略订单**:
```python
order_sizes = [10.0, 10.0, 15.0]  # USD

# 转换后
10 USD / 4604 = 0.0021 PAXG  ✅ > 0.0001
15 USD / 4604 = 0.0032 PAXG  ✅ > 0.0001
```

**结论**: ✅ **无问题**
- 所有订单都远超最小限制
- 即使价格上涨到 $10,000，10 USD 订单仍符合要求

---

### 7. 🟡 价格差异对冲风险

#### 当前状况

**XAU vs PAXG 价格差异**:
```
XAU (Aster):  $4,596
PAXG (Backpack): $4,604
差异: $8 (0.17%)
```

#### 潜在问题

1. **价格跟踪误差**
   - XAU 和 PAXG 价格不完全一致
   - 长期可能导致仓位偏移

2. **资金费率差异**
   - Aster 和 Backpack 的资金费率可能不同
   - 需要定期检查和调整

3. **流动性差异**
   - Aster 流动性较低（策略目标）
   - Backpack 流动性较高
   - 对冲时可能有滑点

#### 建议

1. **定期检查仓位**
   ```python
   # 每小时检查一次
   aster_position = aster.fetch_positions('XAU/USDT')
   backpack_position = backpack.fetch_positions('PAXG/USDC:USDC')
   
   # 计算 USD 名义价值
   aster_usd = aster_position['contracts'] * aster_price
   backpack_usd = backpack_position['contracts'] * paxg_price
   
   # 如果差异 > 5%，需要调整
   if abs(aster_usd + backpack_usd) / max(abs(aster_usd), abs(backpack_usd)) > 0.05:
       logger.warning("Position imbalance detected!")
   ```

2. **监控资金费率**
   ```python
   aster_funding = aster.fetch_funding_rate('XAU/USDT')
   backpack_funding = backpack.fetch_funding_rate('PAXG/USDC:USDC')
   
   # 如果资金费率差异 > 0.01%，需要注意
   ```

---

## 🎯 行动清单

### 立即修复（高优先级）

- [ ] **修复对冲数量计算**
  - 文件: `strategies/xau_arbitrage/hedge.py`
  - 修改: 使用 USD 名义价值计算对冲数量
  - 测试: 模拟不同价格差异下的对冲

### 建议改进（中优先级）

- [ ] **显式指定 timeInForce**
  - 文件: `strategies/xau_arbitrage/exchanges.py`
  - 修改: 限价单传递 `params={'timeInForce': 'GTC'}`

- [ ] **添加仓位监控**
  - 新建: `strategies/xau_arbitrage/position_monitor.py`
  - 功能: 定期检查 Aster 和 Backpack 仓位平衡

- [ ] **检查 Backpack 账户杠杆**
  - 登录 Backpack 网页端
  - 确认账户杠杆设置为 5x-10x

### 长期优化（低优先级）

- [ ] **资金费率监控**
  - 添加资金费率差异告警
  - 自动记录资金费率历史

- [ ] **价格跟踪分析**
  - 记录 XAU 和 PAXG 价格差异
  - 分析长期趋势

---

## 📊 风险评估

### 高风险 🔴

1. **对冲数量计算错误**
   - 影响: 每次对冲都有误差，长期累积
   - 概率: 100%（当前代码确实有问题）
   - 解决: 立即修复

### 中风险 🟡

2. **价格差异导致仓位偏移**
   - 影响: 长期运行后仓位不平衡
   - 概率: 中等（取决于价格差异波动）
   - 解决: 添加仓位监控

3. **Backpack 杠杆设置未确认**
   - 影响: 可能保证金不足或风险过高
   - 概率: 低（如果已在网页端设置）
   - 解决: 启动前确认

### 低风险 🟢

4. **timeInForce 未显式指定**
   - 影响: 代码可读性差，但功能正常
   - 概率: 无影响
   - 解决: 代码优化

---

## 🔧 修复代码示例

### 修复 1: 对冲数量计算

```python
# strategies/xau_arbitrage/hedge.py

async def _hedge_fill(self, fill: FillEvent) -> None:
    """对冲 Aster 上的成交。
    
    Args:
        fill: Aster 上的成交事件
            - fill.qty: XAU 合约数量
            - fill.price: XAU 成交价格
    """
    hedge_side = "sell" if fill.side.lower() == "buy" else "buy"
    initial_order_id: Optional[str] = None

    # 🔧 计算 USD 名义价值
    usd_notional = fill.qty * fill.price
    logger.info(f"Hedging ${usd_notional:.2f} from Aster fill {fill.order_id}")

    # 获取 Backpack BBO
    bbo = self.feed.get_bbo("backpack")
    limit_price = self._calc_hedge_price(hedge_side, bbo, slip=0.0, fallback=fill.price)
    
    # 🔧 根据 USD 计算 PAXG 数量
    hedge_qty = usd_notional / limit_price
    
    if self.dry_run:
        logger.info(
            f"[dry-run] hedge {hedge_side} ${usd_notional:.2f} "
            f"-> {hedge_qty:.4f} PAXG @ {limit_price:.2f}"
        )
        return

    # 下单
    order = await self.exchange.create_limit_order(
        self.symbol, hedge_side, hedge_qty, limit_price
    )
    if order:
        initial_order_id = order.order_id
        logger.info(
            f"hedge order placed {order.order_id} {hedge_side} "
            f"{hedge_qty:.4f} PAXG (${usd_notional:.2f}) @ {limit_price:.2f}"
        )

    # ... 后续监控逻辑保持不变
```

### 修复 2: 显式 timeInForce

```python
# strategies/xau_arbitrage/exchanges.py

def _create_order_sync(self, symbol: str, side: str, amount: float, price: Optional[float], otype: str) -> Optional[OrderRef]:
    try:
        # 🔧 限价单显式指定 timeInForce
        params = {}
        if otype == 'limit':
            params['timeInForce'] = 'GTC'
        
        order = (
            self.client.create_order(symbol, otype, side, amount, price, params)
            if price is not None
            else self.client.create_order(symbol, otype, side, amount, params)
        )
        return OrderRef(
            order_id=str(order.get("id")),
            symbol=symbol,
            side=side,
            price=float(order.get("price") or price or 0),
            amount=float(order.get("amount") or amount),
            info=order,
        )
    except Exception as exc:
        logger.error(f"[{self.name}] create_order failed: {exc}")
        return None
```

---

## 📝 总结

### Backpack vs Aster 对比

| 问题类型 | Aster | Backpack | 结论 |
|---------|-------|----------|------|
| URL 配置 | ❌ 有问题 | ✅ 正常 | Backpack 更好 |
| timeInForce | ❌ 必填未处理 | ⚠️ 非必填 | Backpack 更宽松 |
| set_leverage | ❌ 未实现 | ⚠️ 不支持 | 都需要注意 |
| 精度处理 | ❌ 有 bug | ✅ 正常 | Backpack 更好 |
| 对冲数量 | N/A | ❌ **需修复** | **新发现的问题** |

### 关键发现

1. ✅ Backpack 的 CCXT 实现质量比 Aster 好
2. ⚠️ 但策略层面有对冲数量计算问题
3. 🔴 **必须修复对冲数量计算**，否则长期会有仓位偏移

### 下一步

1. **立即修复**: 对冲数量计算（hedge.py）
2. **启动前检查**: Backpack 账户杠杆设置
3. **运行后监控**: 仓位平衡、资金费率

---

**最后更新**: 2026-01-17 23:41  
**检查者**: Claude  
**状态**: 🔴 发现高优先级问题，需要立即修复
