# Tests

这个目录包含 dext 项目的所有测试。

## 测试结构

### 单元测试

#### REST API 客户端测试
- **test_backpack_integration.py** - Backpack 交易所集成测试
- **test_aster_integration.py** - Aster 交易所集成测试
- **test_lighter_integration.py** - Lighter 交易所集成测试
- **test_variational_integration.py** - Variational 交易所集成测试
- **test_variational_client.py** - Variational 客户端单元测试

#### WebSocket 测试
- **test_ws_clients.py** - WebSocket 客户端测试（Backpack, Lighter）
- **test_lighter_ws.py** - Lighter WebSocket 专项测试

#### 认证测试
- **test_lighter_signer.py** - Lighter zkSync 签名器测试

#### 策略测试
- **test_eth_spread_arbitrage.py** - ETH 价差套利策略测试

## 运行测试

### 运行所有测试
```bash
pytest
```

### 运行特定测试文件
```bash
pytest tests/test_backpack_integration.py
```

### 运行特定测试函数
```bash
pytest tests/test_ws_clients.py::test_backpack_bookticker_parsing
```

### 详细输出
```bash
pytest -v
```

### 查看打印输出
```bash
pytest -s
```

### 跳过需要凭证的测试
```bash
pytest -m "not skip"
```

## 测试覆盖范围

### REST API 层
- ✅ 统一 `_request()` 方法
- ✅ 两层错误处理 (`_handle_http_error()`, `parse_error()`)
- ✅ 端点配置 (Entry 对象)
- ✅ 交易所特定签名 (Ed25519, HMAC-SHA256, zkSync, Cookie)
- ✅ 标准化方法 (`fetch_ticker`, `create_order`, etc.)

### WebSocket 层
- ✅ 原始事件解析
- ✅ 事件标准化 (BBOUpdate, OrderUpdate)
- ✅ Dispatcher 队列分发
- ✅ 自动重连机制

### 错误处理
- ✅ HTTP 错误映射 (400, 401, 404, 429, 5xx)
- ✅ 交易所错误码映射
- ✅ 异常类型正确性

## 模拟模式

大多数测试使用模拟 WebSocket 和 HTTP 响应，无需真实 API 凭证。需要凭证的测试被标记为 `@pytest.mark.skip`。

### conftest.py

包含所有测试的共享配置和 fixture。

## 添加新测试

### 为新交易所添加测试

1. 创建 `test_{exchange}_integration.py`
2. 测试 REST API 方法
3. 测试错误处理
4. 测试端点配置
5. 添加 WebSocket 测试（如果适用）

### 示例结构

```python
"""Test {Exchange} integration with unified architecture."""
import pytest
from exchanges.{exchange} import {exchange}

class Test{Exchange}Client:
    @pytest.fixture
    def client(self):
        return {exchange}({})

    def test_parse_error_invalid_order(self, client):
        response = {"code": -1102, "msg": "Error"}
        with pytest.raises(InvalidOrder):
            client.parse_error(response)
```

## CI/CD

测试在每次提交时自动运行（如果配置了 CI）。确保所有测试在提交前通过。

## 相关文档

- `../CLAUDE.md` - 项目架构和开发指南
- `../docs/exchanges/common-pitfalls.md` - 常见问题和最佳实践
- `../examples/README.md` - 使用示例
