"""cw_difficulty_account(36 号难度账本)v0 测试:J1 恒等式对账 + 三态价值 + 溢出反转。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_difficulty_account import (  # noqa: E402
    DifficultyAccount,
    marginal_value,
)


def test_j1_account_identity() -> None:
    """J1:恒等式对账——total = base+Σaug+通胀+动态+曲线;OCR 修正残差进未知桶。"""
    acc = DifficultyAccount(base=108, augments={'简单模式': -3, '难度修改器': -4},
                            quality_inflation=12, streak=3, node_curve=5)
    assert acc.total() == 108 - 7 + 12 + 3 + 5
    acc.reconcile(acc.total() + 2.5)   # OCR 读到比账本多 2.5
    assert abs(acc.total() - (108 - 7 + 12 + 3 + 5 + 2.5)) < 1e-6
    acc2 = DifficultyAccount(base=100)
    acc2.reconcile(None)               # 读不到 → 外推不回退
    assert acc2.total() == 100.0


def test_marginal_three_states() -> None:
    """三态价值:同 −5 难度,大胜局≈0/边际局峰值/无解局→0(场合依赖,flat 惩罚算不出)。"""
    v_blow = marginal_value(100, -5, gap=-80)     # 大胜
    v_edge = marginal_value(100, -5, gap=0)        # 边际
    v_lost = marginal_value(100, -5, gap=80)       # 无解
    assert v_edge > v_blow and v_edge > 0
    assert abs(v_lost) < 0.01 and abs(v_blow) < 0.01


def test_p1_spike() -> None:
    """P1 尖峰:同幅度压低在 plane=1 价值放大(×1.5)。"""
    v_p1 = marginal_value(100, -5, gap=0, plane=1)
    v_p2 = marginal_value(100, -5, gap=0, plane=2)
    assert v_p1 > v_p2


def test_overflow_gambit_version_guard() -> None:
    """溢出反转:堆难度跨 200 → 大跳价值;证据态 refuted → gambit 退役(不跳)。"""
    v_overflow = marginal_value(195, +20, gap=0, overflow_evidence='verified')
    v_normal = marginal_value(95, +20, gap=0)
    assert v_overflow > v_normal + 5
    # refuted:同一跳跃位置不触发
    v_refuted = marginal_value(195, +20, gap=0, overflow_evidence='refuted')
    assert v_refuted < v_overflow


def test_floor_diminishing() -> None:
    """地板:压到 0 以下收益衰减。"""
    v_ok = marginal_value(30, -5, gap=0)
    v_over = marginal_value(3, -5, gap=0)    # 压到 -2
    assert v_over < v_ok
