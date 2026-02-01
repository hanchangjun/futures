# 期货波段信号自动监控系统说明

## 🎯 目标
基于 TQSDK 或 通达信 接口自动获取行情，计算交易信号，实现**7x24小时自动监控**。系统具备**信号去重**、**自动风控**、**多渠道通知**（企业微信/弹窗）等功能，仅在出现有效新信号时提醒，辅助人工决策。

## 🚀 快速开始

### 策略逻辑文档
详细的算法逻辑（多空判断、入场止损止盈计算、风控手数）请参考：
👉 [策略算法逻辑说明.md](策略算法逻辑说明.md)

### 1. 默认启动（自动监控模式）
使用默认参数（天勤数据源、螺纹钢 RB、日线周期）启动自动监控：
```bash
python main.py
```
*   **行为**：自动拉取数据 -> 计算信号 -> 状态去重 -> 推送新信号 -> 自动休眠 -> 循环。

### 2. 指定品种与周期
监控玻璃（FG）的 1小时周期信号：
```bash
python main.py --symbol FG --period 1h
```

### 3. 配置企业微信通知
**推荐**：设置环境变量（一次设置，永久有效）：
```powershell
$env:WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
python main.py
```
**临时**：通过命令行参数：
```bash
python main.py --webhook "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

---

## 🛠 运行模式详解

### A. 自动监控模式（Monitor Runner）
默认模式。系统会根据周期自动决定休眠时间（如日线休眠 30 分钟，分钟周期休眠 1~5 分钟）。
*   **信号去重**：利用 `state/signal_state.py` 记录上次信号方向，仅当方向变化（如 `观望` -> `多`）时才触发通知。
*   **自动风控**：内置 `risk_gate` 和 `session` 模块，非交易时间或超额亏损会自动拦截信号。
*   **容错机制**：遇到网络异常或接口错误会自动重试，不会导致程序退出。

### B. 单次运行模式（Once）
仅运行一次并退出，适合测试或通过外部调度器（如 Windows 任务计划程序）调用。
```bash
python main.py --once
```

### C. 调试模式（Debug）
输出详细的运行日志，用于排查问题。
```bash
python main.py --debug
```

---

## 📊 常用参数速查

| 参数 | 说明 | 默认值 | 示例 |
| :--- | :--- | :--- | :--- |
| `--symbol` | 交易品种 | `RB` | `--symbol FG` |
| `--period` | K线周期 | `1d` | `--period 30m` |
| `--source` | 数据源 | `tq` | `--source tdx` (通达信) |
| `--once` | 单次运行 | `False` | `--once` |
| `--webhook` | 企业微信 Webhook | `None` | `--webhook https://...` |
| `--debug` | 调试日志 | `False` | `--debug` |

---

## 🔔 通知分级与样式

系统实现了通知分级系统 (`notify` 模块)：
*   **SIGNAL (信号)**：Markdown 格式，包含方向、入场、止损、风险等详细数据，**推送至企业微信**。
*   **ERROR (错误)**：Markdown 格式，高亮显示错误详情，**推送至企业微信**。
*   **INFO/DEBUG**：普通日志，仅输出到控制台。

---

## 📁 目录结构说明

*   `main.py`: 程序入口
*   `datafeed/`: 行情源适配器 (TQSDK / TDX / CSV)
*   `signal/`: 策略核心逻辑 (EMA/ATR 计算、风控规则)
*   `notify/`: 通知模块 (微信/控制台)
*   `runner/`: 运行控制模块 (自动监控循环)
*   `state/`: 状态管理模块 (信号去重)

## 📝 信号去重机制

系统会在本地生成 `signal_state.json` 文件，记录上一次的信号状态。
*   **规则**：
    *   当前信号方向 ≠ 上次信号方向 → **允许通知** (New Signal)
    *   当前信号方向 = 上次信号方向 → **拦截通知** (Duplicate)
