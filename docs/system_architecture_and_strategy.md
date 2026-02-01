# 系统架构与策略算法详解 (System Architecture & Strategy Algorithms)

本文档对最新的量化系统功能进行了全面整合与深度解析，涵盖核心算法、信号评级系统以及针对螺纹钢的定制化策略逻辑。

## 1. 核心量化模块 (Core Quant Modules)
路径: `strategy/quant_logic.py`

本模块提供了基于协议 (`protocol`) 的纯函数计算，确保逻辑与数据结构解耦，性能极高 (<1ms)。

### 1.1 下跌趋势验证 (`is_downtrend`)
用于确认当前是否处于标准的下跌趋势中，作为背驰判断的前提。
*   **算法逻辑**:
    1.  输入一组中枢对象 (`centers`)。
    2.  检查数量是否 >= 2。
    3.  验证 $DD_{i} < DD_{i-1}$ (后一个中枢的 $DD$ 点必须低于前一个中枢的 $DD$ 点)。
    4.  **时间过滤**: 趋势总持续时间 (最新K线时间 - 第一个中枢开始时间) 必须 > 20 根 K 线，排除短期噪音。
*   **输入**: `List[IQuantCenter]`, `current_price`
*   **输出**: `bool`

### 1.2 背驰量化评分 (`quantify_divergence`)
多维度量化趋势力度的衰竭程度，输出 0-100 的评分。
*   **算法逻辑**: 计算 5 个维度的背驰指标，每个维度权重不同 (总分 100):
    1.  **MACD 面积 (Area)**: 比较两段趋势的 MACD 红/绿柱面积。若 $Area_{current} < Area_{prev}$，得分 += 30 * Ratio。
    2.  **MACD 高度 (Height)**: 比较 DIF/DEA 的极值高度。若 $|Height_{current}| < |Height_{prev}|$，得分 += 20 * Ratio。
    3.  **K线 斜率 (Slope)**: 比较趋势段的涨跌速率。斜率变缓，得分 += 20。
    4.  **成交量 (Volume)**: 量价背离 (价新低量缩)，得分 += 15。
    5.  **内部结构 (Internal Structure)**: 次级别是否出现区间套，得分 += 15。
*   **阈值**: 默认总分 > 60 判定为背驰。

### 1.3 相邻笔检查 (`is_adjacent_bi`)
验证两笔在时间上的连续性，确保结构完整。
*   **算法逻辑**:
    1.  检查 $Bi_{next}.start\_time \ge Bi_{prev}.end\_time$ (时间不倒流)。
    2.  检查间隔 $Gap = Bi_{next}.index - Bi_{prev}.index$。
    3.  若 $Gap > max\_gap$ (默认 3)，视为不连续（可能存在缺口或数据丢失）。

---

## 2. 信号优先级与过滤系统 (Signal Priority & Filtering)
路径: `strategy/signal_scorer.py`, `strategy/signal_filter.py`

### 2.1 评分系统 (Signal Scorer)
对生成的信号进行多维度打分，用于筛选高质量机会。
*   **评分维度 (8类)**:
    1.  `structure`: 结构完整性 (如是否有完整中枢)。
    2.  `divergence`: 背驰评分 (调用 `quantify_divergence`)。
    3.  `trend`: 大级别趋势方向一致性。
    4.  `volume`: 成交量配合度。
    5.  `time`: 发生时间的有效性。
    6.  `fractal`: 分型强度。
    7.  `bias`: 乖离率 (是否过大/过小)。
    8.  `custom`: 自定义因子。
*   **配置**: 权重在 `config.yaml` 中定义。

### 2.2 过滤系统 (Signal Filter)
*   **Mandatory (强制条件)**: 必须满足，否则直接丢弃 (如结构未完成)。
*   **Exclusions (排除条件)**: 触发特定风控规则 (如重大新闻发布前、流动性枯竭)。
*   **Score Threshold**: 最终得分 < 70 (可配置) 的信号被过滤。

---

## 3. 螺纹钢定制策略 (Rebar Strategy)
路径: `strategy/rebar/main_strategy.py`
配置文件: `strategy/rebar/params.json`

本策略针对螺纹钢品种特性进行了深度定制，集成了时间、价格、合约及精细化风控。

### 3.1 过滤器 (Filters)
1.  **时间过滤 (Time Filter)**:
    *   仅在定义的 `trading_sessions` (如 09:00-11:30, 13:30-15:00, 21:00-23:00) 内交易。
    *   在 `force_close_windows` (如 14:45-15:00) 强制平仓或禁止开仓，规避隔夜风险。
2.  **价格过滤 (Price Filter)**:
    *   **整数关口**: 在 3600, 3700 等关口 ±10 点范围内，若波动率 (Range) < 5 点，视为窄幅震荡，过滤信号。
    *   **涨跌停风控**:
        *   涨跌幅 > 7%: 禁止开新仓 (`stop_opening_threshold`)。
        *   涨跌幅 > 5%: 强制减仓目标至 1% (`reduce_position_target`)。

### 3.2 合约增强 (Contract Enhancement)
利用期现基差 (Basis) 调整信号权重。
*   **基差计算**: $Basis\% = (Price_{futures} - Price_{spot}) / Price_{spot}$
*   **深贴水 (Deep Discount)**: 若 $Basis\% < -1.5\%$ (期货严重低于现货)，做多信号权重 +0.3 (增加仓位/优先级)。
*   **高升水 (High Premium)**: 若 $Basis\% > +1.5\%$ (期货严重高于现货)，做空信号权重 +0.3。

### 3.3 风险管理 (Risk Manager)
针对不同类型的缠论买卖点实施差异化风控。

#### **1B (第一类买卖点 - 趋势反转)**
*   **止损**: $Low - 1.2 \times ATR$ (留有缓冲)。
*   **仓位**: 初始 3%，允许加仓至 5%。
*   **加仓逻辑**: 价格创出新高 (Long) 或新低 (Short) 后加仓。
*   **止盈**: 触及前中枢下沿 或 出现反向 2B 信号。

#### **2B (第二类买卖点 - 确认回调)**
*   **止损**: $min(1B_{Low}, 2B_{Low})$ (共用防守点)。
*   **仓位**: 初始 2%，最大允许 8% (信心较强时)。
*   **止盈**: 回归中枢中轴 或 出现顶分型。

#### **3B (第三类买卖点 - 趋势中继)**
*   **止损**: $max(ZG_{bottom}, Pullback_{low})$ (紧贴中枢，防守严格)。
*   **仓位**: 初始 2%，**禁止加仓** (防止趋势末端被套)。
*   **止盈**: 突破前高 或 出现顶背驰 (一旦背驰立即离场)。

#### **全局风控 (Global Risk)**
*   **单笔亏损限额**: 任意单笔交易预计亏损额 > 初始权益的 2% -> 拒绝开仓或强平。
*   **最大回撤熔断**: 动态权益回撤 > 5% -> 触发熔断，停止交易。

---

## 4. Web 系统整合
*   **配置管理**: 新增 "Config" 标签页，支持在线修改 `params.json` 并热更新策略参数。
*   **文档系统**: 支持 Markdown 文档动态加载与 SPA 风格导航。
*   **交互图表**: 信号开关 (`1B`/`2B`...) 现已与图表深度联动，点击即可实时过滤显示特定类型的信号。
