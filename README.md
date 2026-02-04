# Futures Trading System

一个基于缠论（Chan Theory）的期货交易量化系统，支持信号生成、多维度评分、过滤、回测和实时监控。

## ✨ 核心特性

### 🎯 信号系统
- **多维度评分**：结构、背驰、成交量、时间、位置等8个维度
- **智能过滤**：强制检查、排除条件、评分阈值
- **信号确认**：1B/2B/3B买卖点的确认机制
- **配置化权重**：所有评分权重在 `config/config.yaml` 中可调

### 📊 策略支持
- **缠论策略**：完整的缠论买卖点识别
- **EMA策略**：双均线交叉策略
- **螺纹钢定制**：针对RB品种的深度优化

### 🔧 技术架构
- **模块化设计**：策略、风控、数据源、回测分离
- **高性能**：纯函数计算，信号处理 < 0.1ms
- **连接池**：TDX连接池优化，提升30-50%数据获取速度
- **数据库索引**：复合索引优化查询性能

### 🌐 Web界面
- **实时监控**：信号实时展示
- **回测系统**：支持历史数据回测
- **图表可视化**：交互式K线图表
- **配置管理**：在线修改策略参数

## 📦 安装

### 环境要求
- Python 3.9+
- pip 或 uv

### 快速开始

```bash
# 克隆项目
git clone https://github.com/hanchangjun/futures.git
cd futures

# 安装依赖
pip install -r requirements.txt

# 或使用uv（推荐）
pip install uv
uv pip install -r requirements.txt

# 初始化日志系统
mkdir -p logs data
```

## ⚙️ 配置

### 配置文件结构

```
config/
├── config.yaml       # 主配置文件
└── settings.py       # 配置加载逻辑（自动生成）
```

### 主配置示例 (config/config.yaml)

```yaml
scorer:
  weights:
    structure: 20
    divergence: 20
    volume_price: 10
    time: 10
    position: 10
    sub_level: 10
    strength: 10
    confirmation: 10
  thresholds:
    min_score: 60.0

filter:
  mandatory:
    check_structure_complete: true
    check_position_clear: true
    check_fractal_confirmation: true

  exclusion:
    major_news_window_minutes: 30
    low_liquidity_window_minutes: 30
    limit_move_percent: 2.0
    contract_switch_week: true

  acceptance:
    min_score: 70.0

# 数据库配置
database:
  url: "sqlite:///./data/futures.db"
  echo: false
  pool_size: 5

# 日志配置
logging:
  level: "INFO"
  file: true
  file_path: "logs/app.log"
```

### 环境变量

支持通过环境变量覆盖配置：

```bash
# 评分配置
export SCORER_MIN_SCORE=65.0

# 过滤配置
export FILTER_MIN_SCORE=75.0
export FILTER_LIMIT_MOVE_PERCENT=3.0

# 数据库配置
export DB_URL="postgresql://user:pass@localhost/futures"

# 日志配置
export LOG_LEVEL="DEBUG"
```

## 🚀 使用

### 命令行模式

```bash
# 运行一次信号分析
python main.py --once --symbol RB --period 1d

# 持续监控模式
python main.py --symbol RB --period 1d --interval 30

# 使用天勤数据源
python main.py --source tq --tq_user YOUR_USER --tq_pass YOUR_PASS

# 使用增强策略
python main.py --enhanced --max-entries 2

# 回测模式
python main.py --backtest --symbol RB --period 1d --days 30
```

### Web界面

```bash
# 启动Web服务
python -m uvicorn web.main:app --reload --host 0.0.0.0 --port 8000

# 访问
# 主页: http://localhost:8000
# API文档: http://localhost:8000/docs
```

### API示例

```python
from strategy.signal_scorer import SignalScorer, ScorableSignal, SignalType
from strategy.signal_filter import SignalFilter
from datetime import datetime

# 创建信号
signal = ScorableSignal(
    signal_id="SIG001",
    signal_type=SignalType.B1,
    timestamp=datetime.now(),
    price=100.0,
    is_structure_complete=True,
    structure_quality=85.0,
    divergence_score=90.0,
    volume=200,
    avg_volume=100,
    # ... 其他字段
)

# 评分
scorer = SignalScorer()
score = scorer.calculate_score(signal)
print(f"信号评分: {score}")

# 过滤
filter_sys = SignalFilter()
passed = filter_sys.filter_signal(signal)
print(f"是否通过: {passed}")
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=. --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html
```

### 性能基准测试

```bash
# 运行性能基准
python benchmark.py

# 运行性能分析（生成profile文件）
python benchmark.py --profile

# 运行内存分析
python benchmark.py --memory
```

性能目标：
- 信号评分: < 0.05ms
- 信号过滤: < 0.05ms
- 总处理时间: < 0.1ms/信号

## 📈 性能优化

### 已实现的优化

1. **TDX连接池**
   - 预创建连接，避免重复建立
   - 连接复用，提升30-50%速度
   - 自动重连和故障转移

2. **数据库索引**
   - 复合索引优化常用查询
   - 支持symbol+period+dt联合查询
   - 加速时间范围查询

3. **缓存机制**
   - K线数据本地缓存
   - 减少重复数据请求
   - 增量更新支持

### 性能监控

```bash
# 查看日志
tail -f logs/app.log

# 性能分析
python -m pstats benchmark.prof
```

## 📚 文档

详细文档请查看 [docs/](docs/) 目录：

- [系统架构](docs/system_architecture_and_strategy.md)
- [缠论策略说明](docs/缠论策略说明.md)
- [优化总结](docs/optimization_summary.md)
- [配置参考](docs/rebar_config_reference.md)

## 🛠️ 开发

### 项目结构

```
futures/
├── config/              # 配置管理
│   ├── settings.py       # 配置定义
│   └── logging.py        # 日志配置
├── datafeed/            # 数据源
│   ├── base.py          # 数据基类
│   ├── tdx_feed.py      # 通达信数据
│   ├── tdx_pool_client.py # TDX连接池
│   └── tq_feed.py       # 天勤数据
├── strategy/            # 策略模块
│   ├── signal_scorer.py # 信号评分
│   ├── signal_filter.py # 信号过滤
│   ├── chan_strategy.py # 缠论策略
│   └── rebar_strategy.py # 螺纹钢策略
├── database/            # 数据库
│   ├── connection.py    # 数据库连接
│   └── models.py       # 数据模型
├── portfolio/           # 投资组合
├── risk/               # 风控模块
├── backtest/           # 回测引擎
├── notify/             # 通知模块
├── web/                # Web界面
├── tests/              # 测试
├── main.py             # 主程序入口
├── benchmark.py        # 性能基准测试
└── requirements.txt    # 依赖列表
```

### 代码规范

```bash
# 格式化代码
black .

# 检查代码风格
flake8 .

# 类型检查
mypy .
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

## 📄 许可证

MIT License

## 📞 联系方式

- 作者: hanchangjun
- GitHub: https://github.com/hanchangjun/futures

---

**⚠️ 免责声明**: 本系统仅供学习和研究使用，不构成投资建议。期货交易有风险，投资需谨慎。
