import pytest
from strategy.rules import ThirdClassRules


class TestThirdClassRules:

    # --- 3B Rules Tests ---

    def test_rule_3b_01_valid_center(self, rules_engine, valid_3b_context):
        """测试 3B-01: 中枢有效性 (ZG > ZD)"""
        assert rules_engine.rule_3b_01_valid_center(valid_3b_context) is True
        valid_3b_context["zg"] = 90  # Invalid ZG < ZD
        assert rules_engine.rule_3b_01_valid_center(valid_3b_context) is False

    def test_rule_3b_02_breakout_zg(self, rules_engine, valid_3b_context):
        """测试 3B-02: 离开段突破中枢上沿"""
        assert rules_engine.rule_3b_02_breakout_zg(valid_3b_context) is True
        valid_3b_context["leave_bar"]["high"] = 105  # Below ZG 110
        assert rules_engine.rule_3b_02_breakout_zg(valid_3b_context) is False

    def test_rule_3b_03_gap_condition(self, rules_engine, valid_3b_context):
        """测试 3B-03: 回调不破中枢上沿"""
        assert rules_engine.rule_3b_03_gap_condition(valid_3b_context) is True
        valid_3b_context["retrace_bar"]["low"] = 105  # Enter ZG 110
        assert rules_engine.rule_3b_03_gap_condition(valid_3b_context) is False

    def test_rule_3b_04_center_segments(self, rules_engine, valid_3b_context):
        """测试 3B-04: 中枢构件数量足够"""
        assert rules_engine.rule_3b_04_center_segments(valid_3b_context) is True
        valid_3b_context["center_bars"] = 1  # Less than min 3
        assert rules_engine.rule_3b_04_center_segments(valid_3b_context) is False

    def test_rule_3b_05_volume_check(self, rules_engine, valid_3b_context):
        """测试 3B-05: 离开段放量"""
        assert rules_engine.rule_3b_05_volume_check(valid_3b_context) is True
        valid_3b_context["volume_leave"] = 100
        valid_3b_context["volume_retrace"] = 200
        assert rules_engine.rule_3b_05_volume_check(valid_3b_context) is False

    def test_rule_3b_06_amplitude_check(self, rules_engine, valid_3b_context):
        """测试 3B-06: 离开段幅度足够"""
        assert rules_engine.rule_3b_06_amplitude_check(valid_3b_context) is True
        # ZG-ZD = 10. Threshold = 10 * 0.5 = 5.
        valid_3b_context["leave_bar"]["high"] = 111  # Amp = 1
        valid_3b_context["leave_bar"]["low"] = 110
        assert rules_engine.rule_3b_06_amplitude_check(valid_3b_context) is False

    def test_rule_3b_07_retrace_k_limit(self, rules_engine, valid_3b_context):
        """测试 3B-07: 回调时间限制"""
        assert rules_engine.rule_3b_07_retrace_k_limit(valid_3b_context) is True
        valid_3b_context["retrace_bar"]["count"] = 10  # > 3
        assert rules_engine.rule_3b_07_retrace_k_limit(valid_3b_context) is False

    def test_rule_3b_08_retrace_amplitude(self, rules_engine, valid_3b_context):
        """测试 3B-08: 回调幅度小于离开幅度"""
        assert rules_engine.rule_3b_08_retrace_amplitude(valid_3b_context) is True
        # Leave Amp = 20. Retrace Amp = 10.
        valid_3b_context["retrace_bar"]["high"] = 150
        valid_3b_context["retrace_bar"]["low"] = 115  # Amp 35 > 20
        assert rules_engine.rule_3b_08_retrace_amplitude(valid_3b_context) is False

    def test_rule_3b_09_safe_gap(self, rules_engine, valid_3b_context):
        """测试 3B-09: 安全缺口"""
        assert rules_engine.rule_3b_09_safe_gap(valid_3b_context) is True
        # ZG=110, H=10. Safe=3. Threshold=113.
        valid_3b_context["retrace_bar"]["low"] = 111  # > 110 but < 113
        assert rules_engine.rule_3b_09_safe_gap(valid_3b_context) is False

    def test_rule_3b_10_higher_tf(self, rules_engine, valid_3b_context):
        """测试 3B-10: 高级别买点共振"""
        assert rules_engine.rule_3b_10_higher_tf(valid_3b_context) is True
        valid_3b_context["higher_tf_buy"] = False
        assert rules_engine.rule_3b_10_higher_tf(valid_3b_context) is False

    def test_rule_3b_11_lower_tf(self, rules_engine, valid_3b_context):
        """测试 3B-11: 次级别买点共振"""
        assert rules_engine.rule_3b_11_lower_tf(valid_3b_context) is True
        valid_3b_context["lower_tf_buy"] = False
        assert rules_engine.rule_3b_11_lower_tf(valid_3b_context) is False

    def test_rule_3b_12_duration_ratio(self, rules_engine, valid_3b_context):
        """测试 3B-12: 时间比率"""
        assert rules_engine.rule_3b_12_duration_ratio(valid_3b_context) is True
        valid_3b_context["retrace_bar"]["count"] = 30  # 30/10 = 3 > 2.0
        assert rules_engine.rule_3b_12_duration_ratio(valid_3b_context) is False

    def test_rule_3b_13_leave_trend(self, rules_engine, valid_3b_context):
        """测试 3B-13: 离开段趋势向上"""
        assert rules_engine.rule_3b_13_leave_trend(valid_3b_context) is True
        valid_3b_context["leave_bar"]["high"] = 100
        valid_3b_context["leave_bar"]["low"] = 110  # Down
        assert rules_engine.rule_3b_13_leave_trend(valid_3b_context) is False

    def test_rule_3b_14_retrace_trend(self, rules_engine, valid_3b_context):
        """测试 3B-14: 回调段趋势向下"""
        assert rules_engine.rule_3b_14_retrace_trend(valid_3b_context) is True
        valid_3b_context["retrace_bar"]["low"] = 130
        valid_3b_context["retrace_bar"]["high"] = 120  # Up
        assert rules_engine.rule_3b_14_retrace_trend(valid_3b_context) is False

    def test_rule_3b_15_no_overlap_gg(self, rules_engine, valid_3b_context):
        """测试 3B-15: 离开段高点强力突破GG"""
        assert rules_engine.rule_3b_15_no_overlap_gg(valid_3b_context) is True
        valid_3b_context["leave_bar"]["high"] = 114  # < GG 115
        assert rules_engine.rule_3b_15_no_overlap_gg(valid_3b_context) is False

    def test_rule_3b_16_higher_tf_sell_filter(self, rules_engine, valid_3b_context):
        """测试 3B-16: 无高级别卖点"""
        assert rules_engine.rule_3b_16_higher_tf_sell_filter(valid_3b_context) is True
        valid_3b_context["higher_tf_sell"] = True
        assert rules_engine.rule_3b_16_higher_tf_sell_filter(valid_3b_context) is False

    # --- 3S Rules Tests (Sample, symmetric) ---

    def test_rule_3s_01_valid_center(self, rules_engine, valid_3s_context):
        """测试 3S-01: 中枢有效性"""
        assert rules_engine.rule_3s_01_valid_center(valid_3s_context) is True
        valid_3s_context["zg"] = 90
        assert rules_engine.rule_3s_01_valid_center(valid_3s_context) is False

    # ... (Implementing key 3S tests to satisfy coverage requirements efficiently)
    # Since prompt asks for "at least 1 pos/neg for EACH of 32 rules", I must write them all.

    def test_rule_3s_02_breakout_zd(self, rules_engine, valid_3s_context):
        """测试 3S-02: 离开段跌破中枢下沿"""
        assert rules_engine.rule_3s_02_breakout_zd(valid_3s_context) is True
        valid_3s_context["leave_bar"]["low"] = 105  # > ZD 100
        assert rules_engine.rule_3s_02_breakout_zd(valid_3s_context) is False

    def test_rule_3s_03_gap_condition(self, rules_engine, valid_3s_context):
        """测试 3S-03: 回调不上破中枢下沿"""
        assert rules_engine.rule_3s_03_gap_condition(valid_3s_context) is True
        valid_3s_context["retrace_bar"]["high"] = 105  # > ZD 100
        assert rules_engine.rule_3s_03_gap_condition(valid_3s_context) is False

    def test_rule_3s_04_center_segments(self, rules_engine, valid_3s_context):
        """测试 3S-04: 中枢构件数量"""
        assert rules_engine.rule_3s_04_center_segments(valid_3s_context) is True
        valid_3s_context["center_bars"] = 1
        assert rules_engine.rule_3s_04_center_segments(valid_3s_context) is False

    def test_rule_3s_05_volume_check(self, rules_engine, valid_3s_context):
        """测试 3S-05: 量能验证"""
        assert rules_engine.rule_3s_05_volume_check(valid_3s_context) is True
        valid_3s_context["volume_leave"] = 100
        valid_3s_context["volume_retrace"] = 200
        assert rules_engine.rule_3s_05_volume_check(valid_3s_context) is False

    def test_rule_3s_06_amplitude_check(self, rules_engine, valid_3s_context):
        """测试 3S-06: 离开幅度"""
        assert rules_engine.rule_3s_06_amplitude_check(valid_3s_context) is True
        valid_3s_context["leave_bar"]["low"] = 99  # Amp 1
        assert rules_engine.rule_3s_06_amplitude_check(valid_3s_context) is False

    def test_rule_3s_07_retrace_k_limit(self, rules_engine, valid_3s_context):
        """测试 3S-07: 回调K线限制"""
        assert rules_engine.rule_3s_07_retrace_k_limit(valid_3s_context) is True
        valid_3s_context["retrace_bar"]["count"] = 10
        assert rules_engine.rule_3s_07_retrace_k_limit(valid_3s_context) is False

    def test_rule_3s_08_retrace_amplitude(self, rules_engine, valid_3s_context):
        """测试 3S-08: 回调幅度"""
        assert rules_engine.rule_3s_08_retrace_amplitude(valid_3s_context) is True
        valid_3s_context["retrace_bar"]["low"] = 50  # Big retrace
        assert rules_engine.rule_3s_08_retrace_amplitude(valid_3s_context) is False

    def test_rule_3s_09_safe_gap(self, rules_engine, valid_3s_context):
        """测试 3S-09: 安全缺口"""
        assert rules_engine.rule_3s_09_safe_gap(valid_3s_context) is True
        # ZD=100. H=10. Safe=3. Threshold=97.
        valid_3s_context["retrace_bar"]["high"] = 98  # > 97
        assert rules_engine.rule_3s_09_safe_gap(valid_3s_context) is False

    def test_rule_3s_10_higher_tf(self, rules_engine, valid_3s_context):
        """测试 3S-10: 高级别卖点"""
        assert rules_engine.rule_3s_10_higher_tf(valid_3s_context) is True
        valid_3s_context["higher_tf_sell"] = False
        assert rules_engine.rule_3s_10_higher_tf(valid_3s_context) is False

    def test_rule_3s_11_lower_tf(self, rules_engine, valid_3s_context):
        """测试 3S-11: 次级别卖点"""
        assert rules_engine.rule_3s_11_lower_tf(valid_3s_context) is True
        valid_3s_context["lower_tf_sell"] = False
        assert rules_engine.rule_3s_11_lower_tf(valid_3s_context) is False

    def test_rule_3s_12_duration_ratio(self, rules_engine, valid_3s_context):
        """测试 3S-12: 时间比"""
        assert rules_engine.rule_3s_12_duration_ratio(valid_3s_context) is True
        valid_3s_context["retrace_bar"]["count"] = 30
        assert rules_engine.rule_3s_12_duration_ratio(valid_3s_context) is False

    def test_rule_3s_13_leave_trend(self, rules_engine, valid_3s_context):
        """测试 3S-13: 离开段向下"""
        assert rules_engine.rule_3s_13_leave_trend(valid_3s_context) is True
        valid_3s_context["leave_bar"]["low"] = 110  # Up
        assert rules_engine.rule_3s_13_leave_trend(valid_3s_context) is False

    def test_rule_3s_14_retrace_trend(self, rules_engine, valid_3s_context):
        """测试 3S-14: 回调段向上"""
        assert rules_engine.rule_3s_14_retrace_trend(valid_3s_context) is True
        valid_3s_context["retrace_bar"]["high"] = 80  # Down
        assert rules_engine.rule_3s_14_retrace_trend(valid_3s_context) is False

    def test_rule_3s_15_no_overlap_dd(self, rules_engine, valid_3s_context):
        """测试 3S-15: 离开段强力跌破DD"""
        assert rules_engine.rule_3s_15_no_overlap_dd(valid_3s_context) is True
        valid_3s_context["leave_bar"]["low"] = 96  # > DD 95
        assert rules_engine.rule_3s_15_no_overlap_dd(valid_3s_context) is False

    def test_rule_3s_16_higher_tf_buy_filter(self, rules_engine, valid_3s_context):
        """测试 3S-16: 无高级别买点"""
        assert rules_engine.rule_3s_16_higher_tf_buy_filter(valid_3s_context) is True
        valid_3s_context["higher_tf_buy"] = True
        assert rules_engine.rule_3s_16_higher_tf_buy_filter(valid_3s_context) is False
