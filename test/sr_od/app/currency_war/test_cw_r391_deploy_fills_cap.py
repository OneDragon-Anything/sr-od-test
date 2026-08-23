# -*- coding: utf-8 -*-
"""r391 检查项锁:deploy_fills_cap 语义(连续 2 轮≤cap-2 且 bench
有货;过渡态/贴 cap/无牌不报)。合成账本双向锁。"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_deploy_fills_cap,
)


def _row(rn: int, deployed: int, cap: int, bench_n: int) -> dict:
    """合成行:deployed 名单 x0..xN;bench 为**异名**货 y0..yN
    (r404-A2 起「可上货」= 非同名副本,异名构造保持旧语义)。"""
    return {
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': f'x{k}'}
                               for k in range(deployed)],
                  'cap': cap,
                  'bench': [{'char_id': f'y{k}'} for k in range(bench_n)]},
    }


def test_same_name_copies_not_reported() -> None:
    """r404-A2:bench 全是同名副本(3合1 素材)→ 不报(5.1.7 合法囤)。"""
    rows = [{
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': '爻光'}], 'cap': 6,
                  'bench': [{'char_id': '爻光'} for _ in range(5)]},
    } for rn in (2, 3)]
    assert not check_deploy_fills_cap(rows)


def test_persistent_gap_reported() -> None:
    """连续 2 轮 deployed≤cap-2 且 bench 有货 → 报(r387 指纹)。"""
    rows = [_row(2, 1, 3, 5), _row(3, 1, 3, 5)]
    assert check_deploy_fills_cap(rows), '连续短缺应报'


def test_transient_gap_not_reported() -> None:
    """单轮短缺(下一轮补满)→ 不报(代理时序过渡态,game14)。"""
    rows = [_row(2, 4, 6, 9), _row(3, 6, 6, 9)]
    assert not check_deploy_fills_cap(rows)


def test_near_cap_not_reported() -> None:
    """差 1(贴 cap)→ 不报(cap 竞争合法保守)。"""
    rows = [_row(2, 2, 3, 5), _row(3, 2, 3, 5)]
    assert not check_deploy_fills_cap(rows)


def test_no_bench_not_reported() -> None:
    """bench 无货(全上场了)→ 不报。"""
    rows = [_row(2, 1, 3, 2), _row(3, 1, 3, 2)]
    assert not check_deploy_fills_cap(rows)


def test_growing_deployed_not_reported() -> None:
    """ADR-0260 增长豁免:连续短缺但 deployed 在增长 → 不报
    (deploy 代理先于买入,每轮买新件时账本恒见滞后一拍的
    「上轮买未部署」形态;engine_seed 放行后 seed4 实证)。"""
    rows = [_row(2, 4, 6, 9), _row(3, 5, 7, 9)]
    assert not check_deploy_fills_cap(rows)
