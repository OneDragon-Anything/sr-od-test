# -*- coding: utf-8 -*-
"""A3 修复2 场景锁(局64 实锤数据形态;原 bfd1c21 诊断锁,ADR-0261
裁决落地后按新语义更新)。

演变:2026-08-24 探针诊断时纯函数无 r288 门,局64 形态「让姬子上场」
锚定 op/sim 分歧;ADR-0261 裁决「1+3 组合」落地后——op 补 ignition
首键排序 + 纯函数补 r288 配方底线门(列车≥2 且仙舟<3 → 列车件让位,
与 deploy_bench op r288 同语义)——两侧行为对齐,本文件锁对齐后语义:
1. 局64 形态(列车2 已达+仙舟<3):纯函数**同样**拦姬子(留 bench)
   ——「引擎件被配方底线拦」不再是 sim 盲区;
2. 点火形态(列车 1,差 1 人点火):门不触发,姬子上场(点火首键)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_deploy_logic import (
    select_deployments,
)
from sr_od.application.currency_war.cw_state import BenchChar


def _bonds(cid: str) -> set[str]:
    ch = CHARACTERS[cid]
    return set(ch.factions) | set(ch.flows)


def _fac(cid: str) -> str:
    return CHARACTERS[cid].factions[0]


def _deployed_fac(names: list[str]) -> dict[str, int]:
    fac: dict[str, int] = {}
    for c in names:
        for f in _bonds(c):
            fac[f] = fac.get(f, 0) + 1
    return fac


def test_stock_engine_piece_deploys_game64_form() -> None:
    """局64 精确形态:deployed 饮月+三月七+3 非引擎(列车2 已达,仙舟 1<3),
    bench 姬子·启行×2,cap=7 → r288 配方底线门拦(ADR-0261 裁决选项3;
    原诊断锁断言「纯函数让姬子上场」,对齐后按新语义更新——op/sim
    在该形态一致拦截,sim 盲区消除)。"""
    dep = ['丹恒·饮月', '三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [BenchChar(slot=i, char_id='姬子·启行',
                       faction=_fac('姬子·启行'), star=1)
             for i in range(2)]
    up, held = select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=7)
    up_names = [bench[i].char_id for i in up]
    assert '姬子·启行' not in up_names, (
        '列车≥2 且仙舟<3 时列车件应被 r288 配方底线门拦下(与 op 对齐)')
    # 两张全部让位留 bench(仙舟基础线优先)
    assert len(held) == 2
    assert all(bench[h].char_id == '姬子·启行' for h in held)


def test_engine_piece_ignition_priority_with_vacancy() -> None:
    """点火形态:deployed 三月七(列车1)+3 非引擎,cap 宽 →
    r288 门不触发(列车<2),姬子(列车 1→2 恰点火)上场。"""
    dep = ['三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [BenchChar(slot=0, char_id='姬子·启行',
                       faction=_fac('姬子·启行'), star=1)]
    up, held = select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=8)
    assert [bench[i].char_id for i in up] == ['姬子·启行']
    assert not held


def test_r288_gate_releases_when_xianzhou_base_met() -> None:
    """门放行对照:仙舟≥3(基础线已满)时列车件不再让位——r288 只在
    「仙舟基础线未满」时拦,基础线满足后列车第 3 人照常上(门语义,
    非永久封顶)。"""
    dep = ['丹恒·饮月', '三月七', '藿藿', '爻光', '大丽花']
    bench = [BenchChar(slot=0, char_id='姬子·启行',
                       faction=_fac('姬子·启行'), star=1)]
    up, held = select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=7)
    assert [bench[i].char_id for i in up] == ['姬子·启行']
    assert not held
