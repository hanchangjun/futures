# 迁移指南：从旧配置到新配置系统

本文档帮助你从旧的配置方式迁移到新的统一配置系统。

## 📋 迁移概览

### 变更内容

| 项目 | 旧方式 | 新方式 |
|------|--------|--------|
| 依赖管理 | 无requirements.txt | requirements.txt + 环境变量 |
| 配置文件 | config.yaml（部分） | config.yaml + .env |
| 配置加载 | yaml.safe_load | Pydantic Settings |
| 日志 | print / logging直接使用 | config/logging.py 统一管理 |
| TDX客户端 | 每次新建连接 | 连接池复用 |

### 迁移步骤

### 1. 安装依赖

```bash
# 安装新的依赖
pip install -r requirements.txt

# 或使用uv
uv pip install -r requirements.txt
```

### 2. 创建环境变量文件

```bash
# 复制示例文件
cp .env.example .env

# 根据需要编辑.env
vim .env
```

### 3. 更新代码中的配置引用

#### 旧代码
```python
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

weights = config['scorer']['weights']
```

#### 新代码
```python
from config import get_settings, get_scorer_config

# 获取完整配置
settings = get_settings()

# 获取特定配置
scorer_config = get_scorer_config()
weights = scorer_config.weights
```

### 4. 更新日志引用

#### 旧代码
```python
import logging

logger = logging.getLogger(__name__)
logger.info("message")
```

#### 新代码（推荐）
```python
from config import setup_logging, get_logger

# 初始化日志（在应用启动时调用一次）
setup_logging()

# 获取logger
logger = get_logger(__name__)
logger.info("message")
```

或使用装饰器：
```python
from config import log_execution, get_logger

logger = get_logger(__name__)

@log_execution(logger)
def my_function():
    # 自动记录函数执行时间
    pass
```

### 5. 更新TDX客户端引用

#### 旧代码（无需更改，兼容）
```python
from app.client.tdx.client import TdxClient

client = TdxClient()
```

#### 新代码（可选优化）
```python
from datafeed.tdx_pool_client import TdxClient

client = TdxClient()  # 自动使用连接池
```

### 6. 更新信号评分和过滤引用

#### 旧代码
```python
from strategy.signal_scorer import SignalScorer, ScorableSignal
from strategy.signal_filter import SignalFilter

scorer = SignalScorer("config.yaml")
filter_sys = SignalFilter("config.yaml")
```

#### 新代码（更简洁）
```python
from strategy.signal_scorer import SignalScorer, ScorableSignal
from strategy.signal_filter import SignalFilter

# 配置自动加载，无需传递路径
scorer = SignalScorer()
filter_sys = SignalFilter()
```

## 🔧 配置迁移对照表

### 评分配置

| 旧配置路径 | 新环境变量 | 新配置路径 |
|-----------|-----------|-----------|
| config.yaml → scorer.weights | SCORER_WEIGHTS (JSON) | ScorerConfig.weights |
| config.yaml → scorer.min_score | SCORER_MIN_SCORE | ScorerConfig.min_score |

### 过滤配置

| 旧配置路径 | 新环境变量 | 新配置路径 |
|-----------|-----------|-----------|
| config.yaml → filter.mandatory.* | FILTER_CHECK_* | FilterConfig.* |
| config.yaml → filter.exclusion.* | FILTER_* | FilterConfig.* |
| config.yaml → filter.acceptance.min_score | FILTER_MIN_SCORE | FilterConfig.min_score |

## 📝 迁移示例

### 示例1：main.py 迁移

#### 旧代码
```python
import yaml
import logging
from strategy.signal_scorer import SignalScorer
from strategy.signal_filter import SignalFilter

# 加载配置
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 初始化
scorer = SignalScorer("config.yaml")
filter_sys = SignalFilter("config.yaml")

logger = logging.getLogger(__name__)
```

#### 新代码
```python
from config import setup_logging, get_logger, get_scorer_config
from strategy.signal_scorer import SignalScorer
from strategy.signal_filter import SignalFilter

# 初始化日志
setup_logging()
logger = get_logger(__name__)

# 初始化（配置自动加载）
scorer = SignalScorer()
filter_sys = SignalFilter()

# 获取配置（如果需要）
config = get_scorer_config()
logger.info(f"最小评分: {config.min_score}")
```

### 示例2：Web服务迁移

#### 旧代码
```python
from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
```

#### 新代码
```python
from fastapi import FastAPI
from config import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="Futures Trading System")
```

## ✅ 验证迁移

迁移完成后，运行以下命令验证：

```bash
# 1. 测试配置加载
python -c "from config import get_settings; print(get_settings())"

# 2. 测试日志
python -c "from config import setup_logging, get_logger; setup_logging; logger = get_logger(__name__); logger.info('Test')"

# 3. 测试信号评分
python -c "from strategy.signal_scorer import SignalScorer; print(SignalScorer())"

# 4. 运行基准测试
python benchmark.py

# 5. 运行测试套件
pytest tests/
```

## 🐛 常见问题

### Q1: 配置文件找不到

**错误**: `FileNotFoundError: config.yaml`

**解决方案**:
```bash
# 确保config.yaml存在
ls config/config.yaml

# 或使用环境变量覆盖
export SCORER_MIN_SCORE=70.0
```

### Q2: 环境变量不生效

**错误**: 配置值未更新

**解决方案**:
```bash
# 确保环境变量已导出
export SCORER_MIN_SCORE=75.0

# 或创建.env文件
echo "SCORER_MIN_SCORE=75.0" >> .env
```

### Q3: 日志文件权限问题

**错误**: `PermissionError: [Errno 13] Permission denied: 'logs/app.log'`

**解决方案**:
```bash
# 创建日志目录
mkdir -p logs

# 确保目录可写
chmod 755 logs
```

### Q4: TDX连接失败

**错误**: `RuntimeError: 无法连接通达信服务器`

**解决方案**:
```bash
# 检查网络连接
ping 115.238.56.198

# 更换TDX服务器
export TDX_SERVERS='[{"ip": "119.147.212.81", "port": 7709}]'

# 增加超时时间
export TDX_TIMEOUT=30
```

## 📞 获取帮助

如果迁移过程中遇到问题：

1. 查看日志文件：`tail -f logs/app.log`
2. 运行测试：`pytest tests/ -v`
3. 查看文档：[docs/](docs/)
4. 提交Issue：https://github.com/hanchangjun/futures/issues

---

**迁移时间估计**: 小型项目 10-30 分钟，大型项目 1-2 小时

**回滚方案**: 旧代码文件已备份在 `.git` 历史中，可以随时回退
