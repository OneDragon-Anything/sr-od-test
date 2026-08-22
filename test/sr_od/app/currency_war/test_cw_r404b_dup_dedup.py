# -*- coding: utf-8 -*-
"""r404-A2 锁:同名去重扩到本轮已上名单(重复件占位根修)。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_deploy_logic import (
    select_deployments,
)
from sr_od.application.currency_war.cw_state import BenchChar


def test_same_name_second_copy_not_deployed() -> None:
    """bench 两张爻光 → 只上第一张(第二张留 bench 当 3合1 素材)。"""
    bench = [
        BenchChar(char_id='爻光', faction='仙舟', slot=1),
        BenchChar(char_id='爻光', faction='仙舟', slot=2),
        BenchChar(char_id='三月七', faction='列车同行', slot=3),
    ]
    up, held = select_deployments(
        bench, deployed_cids=set(), deployed_fac={},
        board={}, cap=6)
    names_up = [bench[i].char_id for i in up]
    assert names_up.count('爻光') == 1, \
        f'同名只一张上场(5.1.7):{names_up}'
    assert 1 in held, '第二张爻光应留 bench'


def test_dup_no_longer_blocks_ignition() -> None:
    """r404 诊断主场景:deployed_cids 空(代理口径),bench
    爻光×3+三月七,cap=3 → 三月七(点火列车)不被重复件挤掉。"""
    bench = [
        BenchChar(char_id='爻光', faction='仙舟', slot=1),
        BenchChar(char_id='爻光', faction='仙舟', slot=2),
        BenchChar(char_id='爻光', faction='仙舟', slot=3),
        BenchChar(char_id='三月七', faction='列车同行', slot=4),
    ]
    # 已有 2 仙舟在场语境(deployed_cids 空=代理重建口径,用
    # deployed_fac 携带既有计数)
    up, held = select_deployments(
        bench, deployed_cids=set(),
        deployed_fac={'仙舟': 2, '列车同行': 1},
        board={'仙舟': 2, '列车同行': 1}, cap=3)
    names_up = [bench[i].char_id for i in up]
    assert '三月七' in names_up, f'点火件(列车第2人)必须上场:{names_up}'
    assert names_up.count('爻光') <= 1
