# 最近优化的功能汇总 (Optimization Summary)

本文档汇总了近期对缠论量化系统的核心优化，包括量化逻辑模块、信号优先级系统以及螺纹钢策略与风控模块。

## 1. 核心量化模块 (Core Quant Modules)
位于 `strategy/quant_logic.py`，实现了三个基于协议的高性能计算函数：

*   **`is_downtrend`**: 下跌趋势验证
    *   逻辑：检查至少两个中枢的 DD (Drawdown) 是否依次降低。
    *   要求：趋势持续时间 > 20 根 K 线。
    *   性能：< 1ms。
*   **`quantify_divergence`**: 背驰量化评分 (0-100)
    *   维度：面积 (Area)、高度 (Height)、斜率 (Slope) 等 5 个维度。
    *   阈值：默认 60 分以上视为背驰。
*   **`is_adjacent_bi`**: 相邻笔检查
    *   逻辑：验证两笔之间的时间间隔是否在允许范围内 (默认 max_gap=3)。
    *   用途：确保笔结构的连续性。

所有输入均基于 `quant_types.py` 定义的 `IQuantBi` 和 `IQuantCenter` 协议，实现了与具体数据结构的解耦。

## 2. 信号优先级与过滤系统 (Signal Priority & Filtering)
位于 `strategy/signal_scorer.py` 和 `strategy/signal_filter.py`。

### 2.1 信号评分 (Signal Scorer)
*   **多维度评分**: 支持结构 (Structure)、背驰 (Divergence)、成交量 (Volume)、时间 (Time) 等 8 个维度。
*   **配置化**: 权重和阈值在 `config.yaml` 中配置。
*   **输出**: 0-100 的综合得分。

### 2.2 信号过滤 (Signal Filter)
*   **强制检查 (Mandatory)**: 必须满足的基础条件 (如结构完整性)。
*   **排除条件 (Exclusions)**: 新闻事件、流动性不足、涨跌停限制等。
*   **得分过滤**: 默认仅通过得分 > 70 的信号。

## 3. 螺纹钢策略与风控 (Rebar Strategy & Risk)
位于 `strategy/rebar/main_strategy.py`，针对螺纹钢品种特性的深度定制。

### 3.1 策略逻辑 (RebarStrategy)
*   **时间过滤**: 严格定义的交易时段，支持早盘/午盘/夜盘，以及开收盘前的强制平仓/禁止开仓窗口。
*   **价格过滤**:
    *   **整数关口**: 接近整数关口 (如 3600, 3700) 时检查波动率，防止窄幅震荡磨损。
    *   **涨跌停限制**: 接近涨跌停板 (7%) 禁止开仓，超过 5% 减仓。
*   **合约切换**: 基于基差 (Basis) 的权重调整。
    *   深贴水 (Deep Discount): 做多权重增加。
    *   高升水 (High Premium): 做空权重增加。

### 3.2 风控管理 (RiskManager)
*   **差异化风控**: 针对 1B/2B/3B 信号采用不同的参数。
    *   **1B**: 止损 = 低点 - 1.2*ATR。
    *   **2B**: 止损 = min(1B低点, 2B低点)。
    *   **3B**: 禁止加仓，止损紧跟中枢。
*   **资金管理**:
    *   基于 ATR 的仓位计算。
    *   全局最大回撤 (5%) 和单笔亏损 (2%) 强平保护。

### 3.3 参数配置
所有策略参数均在 `strategy/rebar/params.json` 中配置，支持热更新。
详细字段说明请参考: [螺纹钢策略配置详解](rebar_config_reference.md)

