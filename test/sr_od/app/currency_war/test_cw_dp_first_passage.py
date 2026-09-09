"""W443 DP/first_passage 面单帧锁(P2 损血标定家族,现役)。

锁对象为 P2 损血标定/首过分布面:`cw_first_passage._loss_dist`、
`p2_node_loss_table`/`p2_cond_loss_table`/`p_win_p2_by_rung`——现役消费方
=cw_state/cw_line_switch/cw_plane_table(2026-09-03 歼击战 grep 复核)。
本文件曾于 2026-09-03 拆分批被误挂旧核基线标记致被默认过滤,同批摘标(教训:打标前 grep 消费方)。

口径定稿与边界声明见 ADR-0440(标定源=W375 双源重标定,
w375_dual_source_calib.json)。effective_hp_threshold 共享面在
test_cw_two_state_unification.py。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_first_passage as fp
from sr_od.application.currency_war.kernel.cw_plane_table import HP_LOSS_MU
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)


def test_plane_loss_scale_retired() -> None:
    """位面乘数常量退役(双源合一的退役声明形态:not hasattr;
    对向声明=原 DP 侧旧挂账⑥随本批一并清账)。"""
    assert not hasattr(fp, 'PLANE_LOSS_SCALE')


def test_calibration_version_anchor() -> None:
    """P2 损血标定家族版本披露锚存在且为 int(独立于 COARSE/economy
    版本;任一标定值/消费口径变动必须递增并随批重锁)。"""
    assert isinstance(DEFAULT_REGISTRY.p2_loss_calib_version, int)
    assert DEFAULT_REGISTRY.p2_loss_calib_version == 1


def test_first_passage_p1_untouched_by_p2_calib() -> None:
    """first_passage P1 分布逐位=HP_LOSS_PRIOR 现档(P1 不走 P2 标定)。"""
    dist = fp._loss_dist(2, 1)
    assert dist[1][0] == HP_LOSS_MU[2]   # μ 档现算(σ=μ·CV);原手抄 2.5


def test_three_table_implied_kind_survival_anchor() -> None:
    """对齐锁:两损血表比值隐含的桶均存活率(1−无条件/条件)钉死——
    值漂移=重标定,须随批重锁并复核本文件头部的坐标声明。"""
    uncond = DEFAULT_REGISTRY.p2_node_loss_table
    cond = DEFAULT_REGISTRY.p2_cond_loss_table
    for kind, expect in (('normal', 0.204), ('encounter', 0.100),
                         ('boss', 0.0)):
        implied = 1.0 - uncond[kind] / cond[kind]
        assert implied == pytest.approx(expect, abs=5e-4), kind
    # kind 难度序:普通战斗 ≥ 遭遇 ≥ boss(桶均存活率;与 ADR-0424
    # 伤害斜率同向——这是节点型间难度差,非 rung 阶梯)
    def implied(k: str) -> float:
        return 1.0 - uncond[k] / cond[k]
    assert implied('normal') >= implied('encounter') >= implied('boss')
    # p_win 表的 rung 阶梯方向(单调升)独立成立,两坐标不互证
    t = DEFAULT_REGISTRY.p_win_p2_by_rung
    assert t[0] < t[1] < t[2]


def test_two_state_consumers_never_mix_tables() -> None:
    """混表禁令静态锁:两态消费文件(rounds_alive/DP 两态/阈值 μ)
    的**代码行**不得读 p2_node_loss_table(无条件表不进行为公式;注释
    里的对向声明不辖);无条件表进行为公式=把桶均存活率错当 rung 胜率
    用(坐标错位=非保守方向)。"""
    from pathlib import Path
    base = Path(__file__).parents[5] / 'src' / 'sr_od' / 'application' \
        / 'currency_war'
    # (批 3:DP 两态递推模块退役;胜率映射 cw_plane_table
    #  只读胜率表,不在条件败面表消费清单)
    for rel in ('kernel/cw_line_switch.py', 'kernel/cw_first_passage.py'):
        code = '\n'.join(ln.split('#', 1)[0]
                         for ln in (base / rel).read_text(encoding='utf-8')
                         .splitlines())
        assert 'p2_node_loss_table' not in code, (
            f'{rel} 代码行读无条件表(混表禁令)')
        assert 'p2_cond_loss_table' in code, f'{rel} 未读条件败面表'
