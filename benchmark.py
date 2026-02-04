"""
性能基准测试 - 使用统一配置和日志系统
"""
import time
import cProfile
import pstats
import random
from datetime import datetime

from strategy.signal_scorer import SignalScorer, ScorableSignal, SignalType
from strategy.signal_filter import SignalFilter
from config import setup_logging, get_logger

# 初始化日志
setup_logging()
logger = get_logger(__name__)


def generate_random_signal(i):
    """生成随机测试信号"""
    return ScorableSignal(
        signal_id=f"SIG_{i}",
        signal_type=random.choice(list(SignalType)),
        timestamp=datetime.now(),
        price=100.0 + random.uniform(-10, 10),
        is_structure_complete=random.choice([True, False]),
        structure_quality=random.uniform(0, 100),
        divergence_score=random.uniform(0, 100),
        volume=random.uniform(100, 500),
        avg_volume=200,
        trend_duration=random.uniform(20, 200),
        position_level=random.uniform(0, 100),
        has_sub_level_structure=random.choice([True, False]),
        momentum_val=random.uniform(0, 100),
        is_fractal_confirmed=random.choice([True, False]),
        meta={
            'minutes_to_news': random.choice([None, 100, 10]),
            'limit_proximity_percent': random.uniform(0, 5)
        }
    )


def run_benchmark():
    """运行性能基准测试"""
    filter_sys = SignalFilter()
    signals = [generate_random_signal(i) for i in range(1000)]

    logger.info(f"开始基准测试，信号数量: {len(signals)}")

    # 计时
    start_time = time.time()
    results = []
    for sig in signals:
        # 评分
        scorer = SignalScorer()
        score = scorer.calculate_score(sig)

        # 过滤
        res = filter_sys.filter_signal(sig)
        results.append(res)

    end_time = time.time()

    total_time = end_time - start_time
    avg_time_ms = (total_time / 1000) * 1000

    logger.info(f"总耗时: {total_time:.4f}s")
    logger.info(f"平均每信号耗时: {avg_time_ms:.4f}ms")

    pass_count = sum(1 for r in results if r)
    logger.info(f"通过率: {pass_count}/1000 ({pass_count/10.0}%)")

    if avg_time_ms <= 5.0:
        logger.info("✅ 性能测试通过 (<= 5ms)")
    else:
        logger.warning(f"⚠️  性能测试未通过 ({avg_time_ms:.4f}ms > 5ms)")

    return avg_time_ms


def run_profile():
    """运行性能分析"""
    logger.info("\n开始性能分析...")

    profiler = cProfile.Profile()
    profiler.enable()

    run_benchmark()

    profiler.disable()

    # 保存分析结果
    profiler.dump_stats('benchmark.prof')

    # 打印统计信息
    stats = pstats.Stats('benchmark.prof')
    stats.strip_dirs().sort_stats('cumtime').print_stats(20)

    logger.info("性能分析已保存到 benchmark.prof")


def run_memory_profile():
    """运行内存分析（如果memory-profiler可用）"""
    try:
        from memory_profiler import profile

        @profile
        def profile_function():
            filter_sys = SignalFilter()
            scorer = SignalScorer()
            signals = [generate_random_signal(i) for i in range(100)]

            for sig in signals:
                scorer.calculate_score(sig)
                filter_sys.filter_signal(sig)

        logger.info("\n开始内存分析...")
        profile_function()
        logger.info("内存分析完成")

    except ImportError:
        logger.warning("memory_profifier未安装，跳过内存分析")
        logger.info("安装命令: pip install memory-profiler")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="性能基准测试")
    parser.add_argument("--profile", action="store_true", help="运行性能分析")
    parser.add_argument("--memory", action="store_true", help="运行内存分析")
    parser.add_argument("--count", type=int, default=1000, help="测试信号数量")

    args = parser.parse_args()

    # 修改全局信号数量
    global generate_random_signal
    original_generate = generate_random_signal

    def generate_random_signal(i):
        return original_generate(i)

    if args.memory:
        run_memory_profile()

    if args.profile:
        run_profile()
    else:
        run_benchmark()
