# 缠论量化交易系统设计方案 (ChanQuant Architecture)

## 1. 系统概述
本方案旨在构建一套基于**缠中说禅理论 (Chan Theory)** 的全栈量化交易系统。系统强调“形态学”与“动力学”的数学化表达，实现从数据采集、形态识别、信号生成到实盘交易的完整闭环。

## 2. 核心架构设计

系统采用**模块化分层架构**，分为四层：
1.  **数据层 (Data Layer)**: 数据清洗、持久化存储。
2.  **核心算法层 (Core Layer)**: 缠论几何形态的严格数学定义与计算。
3.  **策略层 (Strategy Layer)**: 基于形态的交易逻辑（买卖点）。
4.  **交互层 (UI/Service Layer)**: 可视化界面与API服务。

### 2.1 模块详细设计

#### A. 数据层 (Data Layer)
*   **DataFeed**: 支持多源数据（TQSDK, TDX, CSV）。
*   **Persistence**: 使用 **SQLite** 或 **DuckDB** 进行本地化存储（支持高频读写）。
    *   `bars_1m`, `bars_30m`, `bars_1d`: 存储各周期K线。
    *   `trade_log`: 交易流水。

#### B. 核心算法层 (Chan Core) - *数学化的心脏*
这是系统的核心，负责实时维护缠论结构：
1.  **K线预处理 (K-Merge)**: 严格执行“包含关系”处理（上升/下降序列的不同合并规则）。
2.  **分型识别 (Fractals)**: 顶分型 (Top-FX) 与 底分型 (Bottom-FX) 识别。
3.  **笔生成 (Bi)**: 
    *   连接顶底分型。
    *   **严格笔定义**: 结合律验证（中间独立K线 >= 1根，顶底高低点比较）。
4.  **线段生成 (Duan)**: 特征序列法处理笔的破坏与重构。
5.  **中枢构建 (ZhongShu)**: 
    *   线段重叠部分定义中枢。
    *   中枢扩展与扩张逻辑。
6.  **背驰检测 (Divergence)**:
    *   MACD 辅助判断力度。
    *   盘整背驰 vs 趋势背驰。

#### C. 策略层 (Strategy Layer)
*   **SignalGenerator**: 
    *   **1类买卖点 (1B/1S)**: 趋势背驰 + 区间套。
    *   **2类买卖点 (2B/2S)**: 第一次回调不创新低/高。
    *   **3类买卖点 (3B/3S)**: 离开中枢后的不回拉。
*   **Filter**: 结合多级别联立（区间套），如 30m 向上一笔 + 5m 1买。

#### D. 交互与回测层 (UI & Backtest)
*   **Web Dashboard**: 
    *   使用 **FastAPI** 提供后端 API。
    *   使用 **ECharts** 进行K线、笔、中枢的精确绘制。
*   **Backtester**: 
    *   事件驱动回测引擎。
    *   支持“信号重放”和“逐K线回放”。

## 3. 技术栈选型
*   **语言**: Python 3.10+
*   **数据源**: TQSDK (实盘/历史), PyTDX (备用)
*   **数据库**: SQLite (轻量级，无需配置)
*   **Web框架**: FastAPI (高性能异步)
*   **可视化**: Apache ECharts (最适合金融绘图)
*   **UI框架**: 纯 HTML/JS (轻量) 或 Streamlit (快速原型)

## 4. 实施路线图 (Roadmap)

### 第一阶段：核心算法实现 (Completed)
*   [x] 搭建项目结构。
*   [x] 实现K线包含处理 (K-Merge)。
*   [x] 实现顶底分型 (Fractals) 与 笔 (Bi) 的识别。
*   [x] 可视化验证 (ECharts)。
*   [x] 基础买卖点逻辑 (1B/1S, 2B/2S, 3B/3S)。

### 第二阶段：量化交易基础设施 (Current Focus)
当前系统仅为“信号监测器”，缺失交易核心：
1.  **交易执行层 (Execution Layer)**:
    *   [ ] `execution/`: 封装 TqSdk/CTP 交易接口 (Order, Trade, Position)。
    *   [ ] 订单管理系统 (OMS): 状态维护、撤单重发。
2.  **账户管理层 (Portfolio Layer)**:
    *   [x] `portfolio/`: 本地维护资金、持仓状态 (用于回测与实盘核对)。
    *   [x] 权益曲线计算 (逐日盯市)。
3.  **事件驱动回测 (Event-Driven Backtest)**:
    *   [x] 升级 `runner/`: 新增 `event_backtest.py`，支持真实撮合模拟 (BacktestBroker)。
    *   [x] 核心引擎: `backtest/engine.py` 实现事件循环。
4.  **风控模块 (Risk Control)**:
    *   [x] 交易前风控 (Pre-trade Check): `risk/manager.py` 实现最大持仓限制。
    *   [ ] 更多风控规则 (单日亏损限额等)。

### 第三阶段：系统化与UI增强
*   [x] 接入 PostgreSQL 数据库 (已替代 SQLite)。
*   [x] Web 看板 (Flask + ECharts)。
*   [ ] 实盘自动跟单/半自动确认机制。

## 5. 目录结构规划 (Updated)
```text
futures/
├── chan/               # 缠论核心算法 (已完成)
├── database/           # 数据库层 (PostgreSQL Models)
├── datafeed/           # 数据获取 (TqSdk, TDX)
├── strategy/           # 策略逻辑 (ChanStrategy)
├── execution/          # [NEW] 交易执行 (Broker, OMS)
├── portfolio/          # [NEW] 账户与持仓 (Position, Account)
├── backtest/           # [NEW] 回测引擎 (Engine, Matcher)
├── risk/               # [NEW] 风控模块
├── web/                # Web界面
└── main.py             # 启动入口
```
