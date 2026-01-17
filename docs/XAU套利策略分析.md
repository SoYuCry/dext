# XAU 套利策略分析

> **创建时间**: 2026-01-17  
> **目的**: 分析当前策略逻辑，回答"什么时候平仓"的问题

---

## 🎯 策略目标

**捕捉 Aster 上的"大手指订单"（Fat Finger Orders）**

- Aster 流动性低，容易出现价格偏离
- 在 Aster 上挂多层限价单（做市）
- 等待大单吃掉你的挂单（获得有利价格）
- 立即在 Backpack 上对冲（锁定利润）

---

## 📊 当前策略流程

### 1. 启动阶段

```python
# run_xau_arbitrage.py
1. 加载配置（.env）
2. 启动价格订阅（Aster + Backpack WebSocket）
3. 启动做市模块（QuoteManager）
4. 启动用户事件监听（Aster UserStream）
5. 启动对冲模块（HedgeManager）
```

### 2. 做市阶段（持续运行）

```python
# strategies/xau_arbitrage/quotes.py
每 10 秒执行一次：
1. 获取 Aster 当前价格（mid price）
2. 取消所有旧订单
3. 挂 6 个新订单（3 层买 + 3 层卖）：
   - Tier 1: ±0.15% (10 USD)
   - Tier 2: ±0.25% (10 USD)
   - Tier 3: ±0.40% (15 USD)
```

**示例**（假设 XAU = $4,596）:
```
卖单:
  Tier 3: 0.0032 XAU @ $4,614.38 (+0.40%)
  Tier 2: 0.0021 XAU @ $4,607.49 (+0.25%)
  Tier 1: 0.0021 XAU @ $4,602.89 (+0.15%)
  
当前价: $4,596.00

买单:
  Tier 1: 0.0021 XAU @ $4,589.11 (-0.15%)
  Tier 2: 0.0021 XAU @ $4,584.51 (-0.25%)
  Tier 3: 0.0032 XAU @ $4,577.62 (-0.40%)
```

### 3. 成交检测（事件驱动）

```python
# strategies/xau_arbitrage/strategy.py:85-105
Aster UserStream 推送成交事件：
{
  "stream": "user",
  "type": "order",
  "status": "FILLED",
  "side": "BUY",  # 或 "SELL"
  "last_qty": 0.0021,
  "last_price": 4589.11,
  "order_id": "..."
}

触发对冲：
  hedge_mgr.handle_fill(fill)
```

### 4. 对冲阶段（立即执行）

```python
# strategies/xau_arbitrage/hedge.py:50-89
1. 确定对冲方向：
   - Aster 买入 → Backpack 卖出
   - Aster 卖出 → Backpack 买入

2. 计算对冲价格：
   - 获取 Backpack BBO
   - 使用 bid/ask 作为限价

3. 下对冲单（限价单）：
   - 数量: fill.qty（与 Aster 相同）
   - 价格: Backpack BBO

4. 监控对冲单（30 秒超时）：
   - 如果成交 → 完成
   - 如果超时 → 取消，改用市价单
```

### 5. 循环

回到步骤 2，继续做市...

---

## ❓ 关键问题：什么时候平仓？

### 当前答案：**没有平仓逻辑！**

**策略特点**:
1. ✅ 有开仓逻辑（做市 + 对冲）
2. ❌ **没有平仓逻辑**
3. ❌ **没有止盈/止损**
4. ❌ **没有仓位限制**

**这意味着**:
- 策略会持续累积仓位
- Aster 和 Backpack 上的仓位会越来越大
- 需要**手动平仓**或**添加平仓逻辑**

---

## 🔍 仓位累积示例

假设运行 1 小时，发生以下成交：

| 时间 | Aster 成交 | Backpack 对冲 | Aster 仓位 | Backpack 仓位 |
|------|-----------|--------------|-----------|--------------|
| 初始 | - | - | 0 | 0 |
| 10:00 | 卖 0.002 XAU | 买 0.002 PAXG | -0.002 | +0.002 |
| 10:15 | 买 0.003 XAU | 卖 0.003 PAXG | +0.001 | -0.001 |
| 10:30 | 卖 0.002 XAU | 买 0.002 PAXG | -0.001 | +0.001 |
| 10:45 | 卖 0.002 XAU | 买 0.002 PAXG | -0.003 | +0.003 |
| 11:00 | 买 0.003 XAU | 卖 0.003 PAXG | 0 | 0 |

**观察**:
- 仓位会随机波动
- 如果单边成交多，仓位会累积
- 最终仓位取决于市场方向

---

## 💡 策略类型分析

### 当前策略 = **Delta Neutral Market Making**

**特点**:
1. 在 Aster 上做市（提供流动性）
2. 在 Backpack 上对冲（保持 Delta 中性）
3. 赚取 Aster 的 spread（价差）

**盈利来源**:
- Aster 挂单价格 vs 成交价格的差异
- 例如：挂单 $4,602.89，被 $4,605 的市价单吃掉 → 赚 $2.11

**风险**:
1. **基差风险**（Basis Risk）
   - XAU 和 PAXG 价格不完全同步
   - 如果价差扩大，会有损失

2. **资金费率风险**
   - Aster 和 Backpack 的资金费率不同
   - 长期持仓会累积资金费用

3. **仓位累积风险**
   - 没有平仓逻辑，仓位会无限累积
   - 需要手动管理

---

## 🎯 对冲数量的正确性分析

### 你的观点：如果价差恒定，用数量对冲是对的 ✅

**分析**:

假设 XAU 和 PAXG 价格保持恒定比例（如 1:1.0017）

**场景 1: 开仓**
```
Aster:  卖 0.002 XAU @ $4,596 = -$9.19
Backpack: 买 0.002 PAXG @ $4,604 = +$9.21
净敞口: $0.02（可忽略）
```

**场景 2: 价格上涨 10%**
```
XAU:  $4,596 → $5,055.60
PAXG: $4,604 → $5,064.40

Aster 仓位:  -0.002 XAU × $5,055.60 = -$10.11
Backpack 仓位: +0.002 PAXG × $5,064.40 = +$10.13
净敞口: $0.02（仍然可忽略）
```

**结论**: ✅ **如果价差恒定，用数量对冲是正确的！**

### 我之前的错误

我误以为需要用 USD 价值对冲，但实际上：
- 这是一个 **basis trade**（基差交易）
- 目标是对冲 **价格变动风险**，不是 **绝对价值**
- 只要 XAU 和 PAXG 价格保持同步，数量对冲就是正确的

---

## 🔧 需要添加的功能

### 1. 平仓逻辑（重要！）

**选项 A: 定期平仓**
```python
# 每天 UTC 00:00 平仓所有仓位
if current_time.hour == 0 and current_time.minute == 0:
    await close_all_positions()
```

**选项 B: 仓位限制**
```python
# 如果仓位超过阈值，停止做市
max_position = 0.01  # XAU
if abs(current_position) > max_position:
    quote_mgr.pause()
```

**选项 C: 手动平仓**
```python
# 提供 API 或命令行工具手动平仓
python close_positions.py
```

### 2. 仓位监控

```python
# 定期检查仓位
async def monitor_positions():
    while True:
        aster_pos = await aster.fetch_positions('XAU/USDT')
        backpack_pos = await backpack.fetch_positions('PAXG/USDC:USDC')
        
        logger.info(f"Aster: {aster_pos['contracts']} XAU")
        logger.info(f"Backpack: {backpack_pos['contracts']} PAXG")
        
        # 检查是否平衡
        imbalance = abs(aster_pos['contracts'] + backpack_pos['contracts'])
        if imbalance > 0.001:
            logger.warning(f"Position imbalance: {imbalance}")
        
        await asyncio.sleep(300)  # 每 5 分钟
```

### 3. 止盈/止损

```python
# 如果累积 PnL 达到目标，停止策略
target_profit = 100  # USD
max_loss = -50  # USD

if total_pnl >= target_profit:
    logger.info("Target profit reached, stopping...")
    await strategy.stop()
elif total_pnl <= max_loss:
    logger.warning("Max loss reached, stopping...")
    await strategy.stop()
```

---

## 📋 建议的改进优先级

### 🔴 高优先级

1. **添加仓位监控**
   - 实时显示 Aster 和 Backpack 仓位
   - 检测仓位不平衡

2. **添加仓位限制**
   - 设置最大持仓量
   - 超过限制时暂停做市

### 🟡 中优先级

3. **添加手动平仓工具**
   - 提供命令行或 API 接口
   - 一键平掉所有仓位

4. **添加 PnL 计算**
   - 实时计算已实现和未实现盈亏
   - 记录每次成交的盈亏

### 🟢 低优先级

5. **添加自动平仓逻辑**
   - 定期平仓（如每天）
   - 或基于 PnL 的止盈/止损

6. **优化对冲逻辑**
   - 考虑滑点和手续费
   - 优化对冲时机

---

## 🎯 总结

### 当前策略

✅ **正确的部分**:
- 做市逻辑正确
- 对冲数量正确（用相同数量）
- WebSocket 事件驱动高效

❌ **缺失的部分**:
- **没有平仓逻辑**（最关键！）
- 没有仓位限制
- 没有 PnL 跟踪
- 没有风险管理

### 回答你的问题

**Q: 如果价差保持恒定，是否应该用数量一致做对冲？**  
**A**: ✅ **是的！你是对的。**

- 这是 basis trade，目标是对冲价格变动
- 只要 XAU 和 PAXG 价格同步，数量对冲就是正确的
- 我之前的分析是错误的

**Q: 什么时候 exit 对冲？现在有逻辑吗？**  
**A**: ❌ **目前没有平仓逻辑。**

- 策略会持续累积仓位
- 需要手动平仓或添加自动平仓逻辑
- 建议先添加仓位监控，然后再考虑平仓策略

---

## 🚀 下一步

1. **立即**: 添加仓位监控（实时查看持仓）
2. **启动前**: 设置仓位限制（避免过度累积）
3. **运行中**: 手动监控，准备平仓工具
4. **长期**: 添加自动平仓和风险管理

需要我帮你实现仓位监控功能吗？
