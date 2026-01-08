# Bug修复报告

## 总结
所有5个bug已成功修复并通过测试验证。测试结果: **11/11 通过**

---

## Bug 1: RSI计算在价格不变时返回错误值 ✅

**位置**: `exchange.py:121-124`

**问题描述**:
当价格完全不变时(avg_gain = 0, avg_loss = 0)，原代码会返回100.0(极度超买)，导致错误的卖出信号。正确行为应该返回50.0(中性)。

**修复前**:
```python
if avg_loss == 0:
    return 100.0  # 错误: 应该区分是否有涨幅
```

**修复后**:
```python
if avg_loss == 0:
    if avg_gain == 0:
        return 50.0  # 价格不变 - 中性
    return 100.0  # 全部上涨 - 极度超买
```

**测试结果**:
- ✅ 价格完全不变时返回50.0
- ✅ 价格全部上涨时返回100.0
- ✅ 正常波动时计算正确

---

## Bug 2: run_once中同一持仓可能被卖出两次 ✅

**位置**: `strategy.py:257-292`

**问题描述**:
在步骤2中因止损/止盈卖出的持仓，可能在步骤3中因RSI > 70再次被卖出，导致API错误。

**修复**:
添加 `sold_symbols` set来跟踪已卖出的持仓，在步骤3中跳过这些持仓。

```python
sold_symbols = set()  # 记录已卖出的symbol

# 步骤2: 止损/止盈时添加到集合
if order:
    sold_symbols.add(pos['symbol'])

# 步骤3: 检查RSI信号前先过滤
for pos in positions:
    if pos['symbol'] in sold_symbols:
        continue  # 跳过已卖出的持仓
```

**测试结果**:
- ✅ 触发止损后不会因RSI信号再次卖出
- ✅ 持仓只被卖出一次

---

## Bug 3: should_buy未检查是否已持有该币种 ✅

**位置**: `strategy.py:150-177`

**问题描述**:
`should_buy`只检查持仓总数，不检查是否已持有该币种，可能导致重复买入同一币种，违反"最多持有2个不同币种"的设计目标。

**修复**:
添加检查是否已持有该币种的逻辑。

```python
# 检查是否已经持有该币种
currency = signal['symbol'].split('/')[0]
for pos in positions:
    if pos['currency'] == currency:
        print(f"⚠️ 已持有 {currency}，跳过重复买入")
        return False
```

**测试结果**:
- ✅ 已持有的币种被正确拒绝
- ✅ 不同的币种允许买入

---

## Bug 4: create_market_buy_usdt可能除零 ✅

**位置**: `exchange.py:174-189`

**问题描述**:
在计算买入数量时，如果ticker['ask']为None或0，会导致除零错误或TypeError。

**修复**:
添加价格验证，在除法前检查价格有效性。

```python
price = ticker.get('ask')  # 使用卖一价

# 验证价格有效
if price is None or price <= 0:
    raise ValueError(f"Invalid price for {symbol}: {price}")

amount = usdt_amount / price  # 现在安全了
```

**测试结果**:
- ✅ price = None时抛出ValueError
- ✅ price = 0时抛出ValueError
- ✅ price < 0时抛出ValueError

---

## Bug 5: Dashboard允许卖出0数量 ✅

**位置**: `dashboard.py:443`

**问题描述**:
Dashboard只检查余额中是否有该币种，不检查free余额是否大于0。当free余额为0(全部锁定)时，点击卖出会导致API错误。

**修复前**:
```python
if currency in balance:
    sell_amount = balance[currency]['free']  # 可能为0
```

**修复后**:
```python
if currency in balance and balance[currency]['free'] > 0:
    sell_amount = balance[currency]['free']  # 确保 > 0
```

**测试结果**:
- ✅ free余额为0时不显示卖出按钮
- ✅ free余额大于0时显示卖出按钮

---

## 测试运行结果

```
======================================================================
测试总结
======================================================================
总测试数: 11
✅ 通过: 11
❌ 失败: 0
⚠️  错误: 0
======================================================================
```

### 测试覆盖:

1. **Bug 1 - RSI计算**: 3个测试用例
   - 价格不变时返回50.0
   - 价格全部上涨时返回100.0
   - 正常波动时计算正确

2. **Bug 2 - 防止双重卖出**: 1个测试用例
   - 止损后不会因RSI信号再次卖出

3. **Bug 3 - 防止重复买入**: 2个测试用例
   - 拒绝买入已持有的币种
   - 允许买入不同的币种

4. **Bug 4 - 防止除零**: 3个测试用例
   - price = None时抛出错误
   - price = 0时抛出错误
   - price < 0时抛出错误

5. **Bug 5 - Dashboard零余额**: 2个测试用例
   - free余额为0时正确隐藏按钮
   - free余额大于0时正确显示按钮

---

## 修改的文件

1. ✅ `exchange.py` (Bug 1, 4已在代码中修复)
2. ✅ `strategy.py` (Bug 2已在代码中修复, Bug 3新增修复)
3. ✅ `dashboard.py` (Bug 5新增修复)
4. ✅ `test_bug_fixes.py` (新增测试文件)

---

## 结论

所有报告的bug已成功修复并通过全面测试验证。代码现在更加健壮，能够正确处理:
- 边缘情况(价格不变、价格无效)
- 并发问题(防止双重卖出)
- 业务逻辑(防止重复买入、零余额卖出)

系统现在可以安全运行。
