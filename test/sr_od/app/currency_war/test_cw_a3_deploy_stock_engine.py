# -*- coding: utf-8 -*-
"""A3 修复2 探针场景锁:「存量引擎件躺 bench」在 select_deployments
(纯函数)侧不成立的形态锚(局64 实锤数据形态)。

诊断结论(2026-08-24 探针,cw_dev/probe 用完即删):ammo 局64
「姬子·启行×2 全程躺 bench,deployed 上着非引擎件」的机制**不在**
cw_deploy_logic.select_deployments 的排序/围栏——局64 精确形态
(deployed=饮月+三月七+3 非引擎,bench=姬子×2)下纯函数让姬子上场;
生产路径的拦截在 DeployBench op 侧(deploy_bench.py r288 配方底线门:
列车≥2 且仙舟<3 时列车件留 bench;ADR-0261 报告裁决)。

本测试锁两点:
1. 纯函数在该形态下引擎存量件上场(防排序回归 + 记录 op/sim 分歧
   的 sim 侧行为);
2. 第二张同名按 r404-A2 去重留 bench(5.1.7 不变量)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
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
    """局64 精确形态:deployed 饮月+三月七+3 非引擎(列车2 已达),
    bench 姬子·启行×2,cap=7 → 纯函数仍让 1 张姬子上场。"""
    dep = ['丹恒·饮月', '三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [BenchChar(slot=i, char_id='姬子·启行',
                       faction=_fac('姬子·启行'), star=1)
             for i in range(2)]
    up, held = select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=7)
    up_names = [bench[i].char_id for i in up]
    assert '姬子·启行' in up_names, (
        '引擎存量件在 cap 未满+有空位时被排序/围栏压住(回归)')
    # 第二张同名:r404-A2 去重留 bench
    assert up_names.count('姬子·启行') == 1
    assert len(held) == 1 and bench[held[0]].char_id == '姬子·启行'


def test_engine_piece_ignition_priority_with_vacancy() -> None:
    """点火形态:deployed 三月七(列车1)+3 非引擎,cap 宽 →
    姬子(列车 1→2 恰点火)上场。"""
    dep = ['三月七', '阿格莱雅', '乱破', '大丽花']
    bench = [BenchChar(slot=0, char_id='姬子·启行',
                       faction=_fac('姬子·启行'), star=1)]
    up, held = select_deployments(
        bench, set(dep), _deployed_fac(dep), _deployed_fac(dep),
        cap=8)
    assert [bench[i].char_id for i in up] == ['姬子·启行']
    assert not held
