# -*- coding: utf-8 -*-
"""ADR-0261 裁决「1+3 组合」落地锁(op 侧排序 + op/纯函数对齐)。

① op `_deployment_order`(DeployBench 排序单一源,import
cw_deploy_logic.ignition_gain)点火首键:探针形态 bench 姬子·启行
(列车 1→2 恰点火)+ 非引擎 tgt 件 → 姬子先上(旧序 tgt 全体压 rest,
非引擎 tgt 先占坑——局64「deployed 非引擎+引擎件躺 bench」的排序侧
机制);
② tgt 内部点火首键(冗余 tgt 让位点火 tgt);
③ 对齐锁:同输入下 op `_deployment_order` 与纯函数
`select_deployments` 的上场序一致(对齐后 op/纯函数行为差异只剩
「读屏 vs 内存态」;r288 门侧由 bfd1c21 更新锁覆盖)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_deploy_logic import select_deployments
from sr_od.application.currency_war.cw_state import BenchChar
from sr_od.application.currency_war.operations.prep.deploy_bench import (
    _deployment_order,
)


def _bonds(cid: str) -> set[str]:
    ch = CHARACTERS[cid]
    return set(ch.factions) | set(ch.flows)


def _fac(cid: str) -> str:
    return CHARACTERS[cid].factions[0]


def test_op_order_ignition_first_key_probe_form() -> None:
    """裁决选项1 探针形态:bench 姬子(点火)+ 非引擎 tgt 件,deployed
    含三月七(列车1)+非引擎 → 姬子优先上(点火首键+桶序修正)。"""
    bench_id = {0: _bonds('姬子·启行'), 1: _bonds('大丽花')}
    bench_fac = {0: _fac('姬子·启行'), 1: _fac('大丽花')}
    deployed_fac = {'列车同行': 1, '盛会之星': 1}
    order = _deployment_order(
        tgt_idx=[1], rest=[0], bench_id=bench_id,
        bench_fac=bench_fac, deployed_fac=deployed_fac)
    assert order[0] == 0, (
        '点火引擎件(姬子,列车1→2)应先于 ignition=0 的非引擎 tgt 件'
        '(旧序 tgt 全体压 rest = 局64 引擎件躺 bench 的排序侧机制)')


def test_op_order_tgt_internal_ignition_first() -> None:
    """tgt 内部:点火 tgt 件(三月七,列车1→2)先于冗余 tgt 件
    (彦卿,仙舟已3 的第4人)。"""
    bench_id = {0: _bonds('彦卿'), 1: _bonds('三月七')}
    bench_fac = {0: _fac('彦卿'), 1: _fac('三月七')}
    deployed_fac = {'仙舟': 3, '列车同行': 1}
    order = _deployment_order(
        tgt_idx=[0, 1], rest=[], bench_id=bench_id,
        bench_fac=bench_fac, deployed_fac=deployed_fac)
    assert order[0] == 1, 'tgt 序点火首键:点火件(三月七)应排首'


def test_op_and_pure_function_order_aligned() -> None:
    """对齐锁(裁决③):同输入下 op 排序与纯函数上场序一致——
    bench=[冗余 tgt 彦卿, 点火 rest 三月七],deployed 仙舟3+列车1,
    target={仙舟}。两侧都应把三月七排第一。"""
    bench = [BenchChar(slot=1, char_id='彦卿', faction=_fac('彦卿')),
             BenchChar(slot=2, char_id='三月七', faction=_fac('三月七'))]
    deployed_fac = {'仙舟': 3, '列车同行': 1, '减益': 1}
    up, held = select_deployments(
        bench, deployed_cids={'藿藿', '丹恒·饮月', '爻光'},
        deployed_fac=deployed_fac, board=dict(deployed_fac), cap=6,
        target_factions=frozenset({'仙舟'}))
    assert up and bench[up[0]].char_id == '三月七', '纯函数:点火件先上'
    op_order = _deployment_order(
        tgt_idx=[0], rest=[1],
        bench_id={0: _bonds('彦卿'), 1: _bonds('三月七')},
        bench_fac={0: _fac('彦卿'), 1: _fac('三月七')},
        deployed_fac=deployed_fac)
    assert op_order[0] == up[0] == 1, (
        'op 排序与纯函数上场序对齐(ADR-0261 裁决:差异只剩读屏 vs 内存态)')
