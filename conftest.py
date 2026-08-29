"""sr-od-test 慢桶隔离钩子(验证分层协议 §5;W650 实测方案,用户已批准)。

机制:slow_marks.txt 逐行一条 nodeid 后缀(形如 ``文件名::类::测试``),
命中者打 ``slow`` marker。命令分层:
- L1/L2 开发循环带 ``-m "not slow"`` → 慢桶跳过(慢桶多为 sim 行为锁/
  校准锁/OCR 重推理,单条 ≥2s,日常循环不陪跑);
- L3 全量不过滤(慢桶不可丢);
- ``-m slow`` 单独点名慢桶维护。
名单维护 = ``--durations`` 巡检回填,准入线:串行单条实测 ≥2s 且为
「无断言密度增益的重操作链」(sim 锁类按 README 纪律 7 已取最小 n,
保留在 quick 不入桶——是否入桶以逐条评审为准)。
"""
from pathlib import Path

import pytest

MARKS_FILE = Path(__file__).parent / "slow_marks.txt"


def _load_marks() -> list[str]:
    if not MARKS_FILE.exists():
        return []
    return [
        line.strip()
        for line in MARKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def pytest_collection_modifyitems(config, items):
    """按名单打 slow 标记;并自带 not slow/slow 选摘(不依赖核心 -m 求值顺序)。"""
    marks = _load_marks()
    if not marks:
        return
    slow, kept = [], []
    for item in items:
        if any(mark in item.nodeid for mark in marks):
            item.add_marker(pytest.mark.slow)
            slow.append(item)
        else:
            kept.append(item)
    markexpr = (getattr(config.option, "markexpr", "") or "").strip()
    if "not slow" in markexpr:
        items[:] = kept
    elif markexpr == "slow":
        items[:] = slow
