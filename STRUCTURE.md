# 文件结构总览

重构前后目录分开描述，便于对照。

## 重构后（统一交易客户端）
```
api/
├── __init__.py
├── auth.py
├── bp_client.py          # Backpack 别名
├── proxy_utils.py
├── base/                 # 通用基类/类型/错误
└── exchanges/            # 各交易所适配器
    ├── __init__.py
    ├── aster.py
    ├── backpack.py
    ├── hyperliquid.py
    └── lighter.py

config.py
logger.py
README.md
requirements.txt
ARCHITECTURE.md
STRUCTURE.md
```

## 重构前（策略 + Web/CLI + DB）
```
api/                      # 多交易所 REST 客户端
ws_client/                # WebSocket 客户端
strategies/               # 做市/网格/对冲策略
cli/                      # 命令行入口
web/                      # Flask Web 控制台
database/                 # SQLite 持久化
docs/                     # 策略说明文档
utils/                    # 通用工具
run.py                    # 主入口
dashboard.png             # Web 截图
```

## 在策略项目中使用（推荐：可编辑安装）

在 `StrategyA` 的虚拟环境中执行：

```bash
pip install -e /Users/liuc/Documents/Projects/dext
```

然后在策略代码里直接：

```python
from dext import get_client

client = get_client("lighter", config={...})
```
