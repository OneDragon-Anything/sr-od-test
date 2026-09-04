"""W443 阈值链共享面单帧锁:effective_hp_threshold 消费点 + 现值 + P1 零漂移。

(2026-09-03 拆分批:DP 两态/first_passage/损血标定面拆往
test_cw_w443_dp_first_passage.py(歼击战摘 legacy 错标复活);本文件只留
effective_hp_threshold 共享面——该链生产消费点单口 + 现值锁。)

口径定稿与边界声明见 ADR-0440(标定源=W375 双源重标定,
w375_dual_source_calib.json)。
"""
from __future__ import annotations

import dataclasses

import pytest

from sr_od.application.currency_war.kernel import cw_first_passage as fp
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    effective_hp_threshold,
)
from sr_od.application.currency_war.kernel import cw_registry as reg_mod
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

# ---- 阈值链:消费点静态源级锁 ---------------------------------------------
# 判据=全部消费点经 effective_hp_threshold(state) 单口消费,无旁路
# 裸算(裸算=绕过标定单口=双源)。路径清单即锁面:消费点增删须随批改锁。
# (default_strategy 两点危机/生存门已随本体退役删除)

_THRESHOLD_CONSUMERS: tuple[tuple[str, int], ...] = (
    ('kernel/cw_economy.py', 1),        # 止损门
    ('kernel/cw_comps.py', 1),          # 保命转型 0.75×
)


def test_threshold_chain_consumption_sites() -> None:
    """消费点静态锁:各文件对 effective_hp_threshold 的调用次数
    与声明清单一致(只增不减;减=消费点退役,须随批改本锁)。
    原名「five_consumption_sites」系拆分前旧账,现清单=2 文件各 1 处。"""
    from pathlib import Path
    base = Path(__file__).parents[5] / 'src' / 'sr_od' / 'application' \
        / 'currency_war'
    for rel, expect_calls in _THRESHOLD_CONSUMERS:
        code_lines = [ln.split('#', 1)[0]
                      for ln in (base / rel).read_text(encoding='utf-8')
                      .splitlines()]
        n = '\n'.join(code_lines).count('effective_hp_threshold(')
        assert n == expect_calls, f'{rel}: 期望 {expect_calls} 处消费,实得 {n}'


# ---- 阈值现值锁(现值=两态标定 v1 的 P2+ 值分布;P1 恒 base) ------------------


def test_threshold_current_values_two_state_calib() -> None:
    """P2+ 现值单帧锁(tier=board_tier_of(level);base=40 无职级):
    - tier0(lv4):P2 标定 μ0≈13.2 < P1 先验 μ0=14 → ratio 夹 1.0 → 40;
    - tier2(lv7,r1):ratio≈1.85 → 74;
    - tier3(lv10):顶 2.0 夹界 → 80;
    - A8(base=55)tier2:55×ratio 同比上浮(链式派生不破坏职级表)。"""
    assert effective_hp_threshold(
        GameState(plane=2, round_num=1, level=4)) == 40
    assert effective_hp_threshold(
        GameState(plane=2, round_num=1, level=7)) == 74
    assert effective_hp_threshold(
        GameState(plane=2, round_num=7, level=7)) == 73
    assert effective_hp_threshold(
        GameState(plane=2, round_num=1, level=10)) == 80
    a8 = GameState(plane=2, round_num=1, level=7, selected_difficulty='A8')
    assert effective_hp_threshold(a8) == 100   # 55×1.85≈101 → min(100,·) 夹上界


def test_threshold_p1_untouched_by_p2_calib(monkeypatch: pytest.MonkeyPatch) -> None:
    """P1 零漂移结构锚:monkeypatch 掉 P2 标定两表,P1/阈值 plane1 输出
    逐位不变(P1 不吃 P2 标定的行为声明)。"""
    reg = dataclasses.replace(
        reg_mod.DEFAULT_REGISTRY,
        p2_cond_loss_table={'normal': 99.0, 'encounter': 99.0,
                            'boss': 99.0, 'reward': 0.0},
        p_win_p2_by_rung={0: 0.9, 1: 0.9, 2: 0.9})
    monkeypatch.setattr(reg_mod, 'DEFAULT_REGISTRY', reg)
    # P1/P3 先验曲线随 DP 世界模型退役(BLUEPRINT §3;P1 零漂移锚
    # 由 first_passage P1 分布锁承担,见下)
    assert effective_hp_threshold(GameState(plane=1, level=7)) == 40
    # 对照:P2 帧吃注入(位移发生,证明 P1 恒等不是恒真断言)
    assert effective_hp_threshold(
        GameState(plane=2, round_num=1, level=7)) > 74




# ---- 三表对齐锁(p_win × 条件败面 × 无条件期望;ADR-0440 三表对齐节) ----
# 数学结论(检查点①复算的裁决):「同 rung 恒等式无条件=(1−p(rung))·
# 条件」在 p_win_p2_by_rung × p2_cond_loss_table × p2_node_loss_table
# 三表间**不成立也不应成立**——三表坐标与样本窗均不同:
# - p_win_p2_by_rung: rung 坐标(同战斗节点型内按板强成型度;W346 sim
#   Δ池 battle 样本,k0/k1/k2=0.016/0.413/0.657 单调升=H3 阶梯);
# - 两损血表: kind 坐标(节点型桶;W375 实机深层局样本)。两表比值
#   1−无条件/条件 隐含的是**各节点型桶上的板强混合平均存活率**
#   {normal 0.204/encounter 0.100/boss 0.000}——递减序=节点型难度序
#   (遭遇比普通战斗难、深层局 boss n=4 全败),与 ADR-0424 拟合伤害
#   斜率(遭遇 −23.48 vs 战斗 −12.06)同向;这是 kind 间难度差,不是
#   rung 阶梯反向,与 H3「同节点型内 p 随成型单调升」无矛盾。
# - 恒等式本身还要求 E[损|胜]=0 严格且桶内板强分布与 p̄ 一致,W375
#   口径(净负记 0/hp≤1 不删失/死亡行全额)不保证,只有近似意义。
# 消费面自洽:两态行为链(DP/rounds_alive/阈值 μ)只吃
# p2_cond_loss_table × p_win_p2_by_rung,无条件表不进任何行为公式。




