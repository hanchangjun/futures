import pytest
import time
from strategy.third_class_signal import ThirdClassSignal


class TestThirdClassSignalIntegration:

    def test_3b_success(self, signal_analyzer, valid_3b_context):
        """测试 3B 信号生成成功"""
        result = signal_analyzer.conditions_3B(valid_3b_context)
        assert result is True, "Expected 3B Signal"

    def test_3b_failure(self, signal_analyzer, valid_3b_context):
        """测试 3B 信号生成失败 (ZhongShu Overlap)"""
        valid_3b_context["retrace_bar"]["low"] = 100  # < ZG 110
        result = signal_analyzer.conditions_3B(valid_3b_context)
        assert result is False, "Expected 3B Failure due to overlap"

    def test_3s_success(self, signal_analyzer, valid_3s_context):
        """测试 3S 信号生成成功"""
        result = signal_analyzer.conditions_3S(valid_3s_context)
        assert result is True, "Expected 3S Signal"

    def test_3s_failure(self, signal_analyzer, valid_3s_context):
        """测试 3S 信号生成失败 (Volume)"""
        valid_3s_context["volume_leave"] = 100
        valid_3s_context["volume_retrace"] = 500
        result = signal_analyzer.conditions_3S(valid_3s_context)
        assert result is False, "Expected 3S Failure due to volume"

    def test_conflict_scenario(self, signal_analyzer, valid_3b_context):
        """测试 多空双信号冲突 (数据异常导致同时满足?)"""
        # Theoretically impossible with single context unless context is weird
        # But we can try to force check both on same context

        # Using 3B context for 3S check should fail immediately
        res_3b = signal_analyzer.conditions_3B(valid_3b_context)
        res_3s = signal_analyzer.conditions_3S(valid_3b_context)

        assert res_3b is True
        assert res_3s is False, "3B Context should not trigger 3S"

    def test_performance_benchmark(self, signal_analyzer, valid_3b_context):
        """性能测试: 10000 次执行 < 10ms (Req: 100k < 1ms per call? No, total?)"""
        # Req: "Single execution <= 1 ms".
        # We test 10000 executions and expect total < 10s (avg < 1ms).
        # Actually 10k is fast.

        start_time = time.time()
        for _ in range(10000):
            signal_analyzer.conditions_3B(valid_3b_context)
        end_time = time.time()

        duration = end_time - start_time
        avg_time = duration / 10000

        print(f"Average Execution Time: {avg_time*1000:.4f} ms")
        assert avg_time < 0.001, f"Performance too slow: {avg_time*1000:.4f} ms > 1ms"

    def test_robustness_nan(self, signal_analyzer, valid_3b_context):
        """鲁棒性测试: 处理 NaN 数据"""
        valid_3b_context["zg"] = float("nan")
        # Should catch exception and return False
        result = signal_analyzer.conditions_3B(valid_3b_context)
        assert result is False

    def test_robustness_missing_keys(self, signal_analyzer):
        """鲁棒性测试: 缺失键"""
        bad_context = {"zg": 100}
        result = signal_analyzer.conditions_3B(bad_context)
        assert result is False
