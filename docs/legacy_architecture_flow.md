# 期货波段系统：架构与全场景流程说明

## 1. 系统总览
```
[main.py] ──▶ ★ Runner 监控循环
                │
                ▼
        [datafeed] 获取行情
                │
                ▼
        [signal] 计算信号
                │
                ▼
        [control] 准入判断
                │
                ▼
        分级/冷却/确认（state + runner）
                │
                ├──▶ [notify] 通知路由
                └──▶ [state] 状态写回

        支线：回测
        ├── ConfirmBacktester（Signal→Confirm）
        └── EntryBacktester（Confirm→Entry）
```

## 2. 目录与关键模块
- 行情源适配：[datafeed](file:///e:/project/futures/futures/datafeed)
  - 统一接口：get_bars(source, symbol, period, ...)
- 策略计算：[signal](file:///e:/project/futures/futures/signal)
  - 指标：[indicators.py](file:///e:/project/futures/futures/signal/indicators.py)
  - 信号：[signal.py](file:///e:/project/futures/futures/signal/signal.py)
  - 类型：[types.py](file:///e:/project/futures/futures/signal/types.py)
- 控制与决策：[session/risk_gate/decision](file:///e:/project/futures/futures/signal)
- 通知分级与样式：[notify](file:///e:/project/futures/futures/notify)
  - 枚举：[types.py](file:///e:/project/futures/futures/notify/types.py)
  - 样式：[styles.py](file:///e:/project/futures/futures/notify/styles.py)
  - 出口：[__init__.py](file:///e:/project/futures/futures/notify/__init__.py)
- 状态管理：[state](file:///e:/project/futures/futures/state)
  - 信号冷却与去重：[signal_state.py](file:///e:/project/futures/futures/state/signal_state.py)
  - 确认状态：[confirm_state.py](file:///e:/project/futures/futures/state/confirm_state.py)
- 监控循环与确认判定：
  - 监控循环：[runner/monitor.py](file:///e:/project/futures/futures/runner/monitor.py)
  - 确认判定（0.5×ATR）：[runner/confirm.py](file:///e:/project/futures/futures/runner/confirm.py)
- 回测：
  - 确认回测：[runner/backtest_confirm.py](file:///e:/project/futures/futures/runner/backtest_confirm.py)

## 3. 主要流程（★ 为主线高亮）
### 3.1 监控主流程
```
★ 启动 main.py → 解析参数 → start_monitor(args, compute_dual_signal, signal_payload)
★ 拉取主/副周期 K 线 → datafeed.get_bars(...)
★ compute_dual_signal → 生成信号：
    - strong：双周期同向且 hands>0
    - normal：仅主周期 hands>0
    - weak：hands≤0 或双周期方向不一致/不可交易
★ 构造 payload（含 symbol/direction/entry/stop/take_profit/hands/risk/reason/date/strength + bar_index）
★ 分级与冷却：
    - weak：忽略（不冷却、不通知）
    - normal：SignalState.should_notify → 允许则 INFO 日志，不推送、不写状态
    - strong：SignalState.should_notify → 允许则推送 WeCom（SIGNAL），成功后写 last_notify_bar_index，并保存 Confirm pending
★ 确认检查（每根新 K 线）：
    - 价格向信号方向突破 entry ≥ 0.5×ATR → Confirm 成立
    - 成立后仅触发一次 SIGNAL 通知 → ConfirmState.mark_confirmed（落账并清空 pending）
★ Sleep（周期驱动：如日线 30 分钟） → 下一轮
```

### 3.2 冷却判断（SignalState.should_notify）
```
输入：current_signal(direction, bar_index), cooldown_bars
状态：last_notify_bar_index（signal_state.json）
规则：
1) 方向变化 → 立即允许（忽略冷却）
2) 同方向：
   gap = bar_index - last_notify_bar_index
   gap < cooldown_bars → 拦截（BLOCKED，仅日志）
   gap ≥ cooldown_bars → 允许
缺少 bar_index/last_notify_bar_index → 保守拦截（BLOCKED）
写回约束：仅在 allow=True 且实际推送成功后写入 last_notify_bar_index
```

### 3.3 通知路由（notify）
```
级别：DEBUG / INFO / BLOCKED / SIGNAL / ERROR
路由：
- SIGNAL/ERROR → Markdown → WeCom（失败回退 console）
- INFO/DEBUG/BLOCKED → console/file
样式：
- SIGNAL：方向、入场、止损、止盈、手数、风险、依据
- ERROR：突出严重性与细节
```

### 3.4 数据源分支
```
source = tq / tdx / file
- TQ：需账号与合约映射，支持增量拉取
- TDX：服务器/市场编号，可自动主力映射
- CSV：日线/60分等固定路径
接口统一：get_bars(...) → List[PriceBar], used_symbol
```

## 4. 确认与回测支线
### 4.1 ConfirmBacktester（Signal→Confirm）
```
目标：评估 strong 信号在 N 根 K 内被 Confirm 的命中率与等待分布
特性：严格时间推进（bars[:i+1]），无未来函数
事件：strong → pending；确认成功记录等待数；超时/被新 strong 覆盖记失败
输出：total_signals / hits / fails / hit_rate / avg_wait_bars / wait_distribution
```

### 4.2 EntryBacktester（Confirm→Entry）
```
目标：验证 Entry 可执行性与风险结构（非盈亏）
输入：ConfirmEvent 序列 + bars
EntryRule：可插拔（市价下一根、突破、回撤等）
指标：
- Fill Rate：Confirm 后 N 根内触达入场价
- Immediate Stop Rate：入场后 M 根内是否先触发止损
- R 倍数分布：入场后 T 根内的正向幅度 / 止损距离
输出：fills / fill_rate / immediate_stop_rate / avg_fill_wait_bars / r_distribution
```

## 5. 异常与容错
```
任何异常不退出：捕获并以 ERROR 级别通知（WeCom/console），延时重试
通知失败回退：WeCom 异常 → console 兜底
冷却信息缺失：保守拦截（BLOCKED），提示缺少 bar_index
网络限制（Git 推送）：支持 SSH/HTTPS、ssh.github.com:443 配置与代理/证书检查
```

## 6. 参数与状态
- 冷却参数：--cooldown-bars（默认 5）[main.py](file:///e:/project/futures/futures/main.py#L449-L456)
- 确认状态文件：--confirm-state-file（默认 confirm_state.json）
- Webhook：--webhook 或环境变量 WECOM_WEBHOOK_URL / WECOM_WEBHOOK
- 状态文件字段示例：
  - signal_state.json：
    - symbol/direction/entry/stop/take_profit/hands/risk/reason/date
    - last_notify_bar_index
  - confirm_state.json：
    - pending：symbol/direction/entry/bar_index/date
    - last_confirmed：symbol/direction/entry/confirm_bar_index/confirm_price/date

## 7. 维护与更新
- 本说明用于跟踪架构与流程变更；新增模块/支线时在此同步更新
- 更新建议：
  - 主流程变化（★）必须标注清晰
  - 新增分支/支线需描述输入/输出与边界
  - 重要参数与状态字段变更需同步示例

