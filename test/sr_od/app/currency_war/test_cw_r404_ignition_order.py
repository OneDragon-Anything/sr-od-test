"""r404-A1 锁:点火增量排序(ignition_gain 首键+桶序修正)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_deploy_logic import (
    ignition_gain,
    select_deployments,
)
from sr_od.application.currency_war.cw_state import BenchChar


def test_ignition_gain_semantics() -> None:
    """点火增量:恰好凑满体系 tier 的那张=1;冗余/无关=0。"""
    dep = {'仙舟': 2, '持续伤害': 2}
    # 第3仙舟 → 仙舟3 点火
    assert ignition_gain({'仙舟'}, dep) == 1
    # 第4仙舟(已 3) → 冗余
    assert ignition_gain({'仙舟'}, {'仙舟': 3}) == 0
    # 列车第2人 → 列车2 点火
    assert ignition_gain({'列车同行'}, {'列车同行': 1}) == 1
    # 无关节
    assert ignition_gain({'欢愉'}, dep) == 0


def test_ignition_beats_redundant_target() -> None:
    """r404-A1 探针④:vacancy=1,点火 rest 件 > 冗余 tgt 件。"""
    bench = [
        BenchChar(char_id='三月七', faction='列车同行', slot=1),  # 点火
        BenchChar(char_id='彦卿', faction='仙舟', slot=2),        # 冗余tgt
        BenchChar(char_id='赛飞儿', faction='夜之半神', slot=3),
    ]
    deployed_fac = {'仙舟': 3, '减益': 1, '星核猎手': 1,
                    '持续伤害': 2, '列车同行': 1, '夜之半神': 1}
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光', '椒丘', '卡芙卡'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'仙舟', '持续伤害'}))
    assert up and bench[up[0]].char_id == '三月七', \
        '点火件(列车第2人)应先于冗余第4仙舟'


def test_ignition_in_target_sorts_first() -> None:
    """tgt 内部:点火件排首(探针①:爻光第3仙舟最优先)。"""
    bench = [
        BenchChar(char_id='爻光', faction='仙舟', slot=1),
        BenchChar(char_id='彦卿', faction='仙舟', slot=2),  # 同tgt冗余
    ]
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月'},
        deployed_fac={'仙舟': 2, '持续伤害': 2},
        board={'仙舟': 2, '持续伤害': 2}, cap=6,
        target_factions=frozenset({'仙舟'}))
    assert up and bench[up[0]].char_id == '爻光'


def test_locked_line_core_beats_ignition_filler() -> None:
    """W65/ADR-0323:cap 竞争(1 空位)时锁定线核心(target_cores)优先于
    点火过渡件——旧序 ignite_rest 压 tgt,三月七(列车1→2 点火)先占坑,
    万敌(ig0)被挤留 bench(W64 seed 13 r5 形态);修后「同 cap 内先核心
    后填充」([21] 变阵窗口语义),不扩 cap。"""
    bench = [
        BenchChar(char_id='三月七', faction='列车同行', slot=1),  # 点火过渡件
        BenchChar(char_id='万敌', faction='夜之半神', slot=2),    # 锁定线核心(ig0)
    ]
    deployed_fac = {'列车同行': 1, '夜之半神': 1}
    up, _ = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光', '卡芙卡', '桑博'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'夜之半神', '燃血'}),
        target_cores=frozenset({'万敌', '千冶·刃'}))
    assert up and bench[up[0]].char_id == '万敌', \
        '锁定线核心(target_cores)应先于点火过渡件(同 cap 内先核心后填充)'
