# -*- coding: utf-8 -*-
"""装备对账合并语义锁(ADR-0387 断点①):cw_reconcile 整批替换清零
equips 的修复——char_id 续接保留、画面真值优先、多副本逐个配对。
(断点②采集写端/③读槽布局的行为契约由 op 层测试与 w148 搬运链锁承载。)
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.kernel.cw_reconcile import _merge_equips
from sr_od.application.currency_war.kernel.cw_state import BenchChar


def _bc(cid: str, slot: int = 1, row: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=cid, position_pref=row)


def test_reconcile_preserves_equips_across_drift() -> None:
    """断点①:对账合并语义——char_id 续接保留 equips(整批替换不再清零)。

    run 26 希儿场景:旧 tracking [斩首行动,电磁弹射器],SIFT 新读对象
    equips=[] 默认 → 续接后保留(纠漂反复触发也不闪零)。
    """
    old = [_bc('希儿', 1, 'front')]
    old[0].equips = ['斩首行动', '电磁弹射器']
    new = [_bc('希儿', 1, 'front')]
    assert _merge_equips(old, new)[0].equips == ['斩首行动', '电磁弹射器']


def test_reconcile_picture_truth_wins_over_stale() -> None:
    """新读自带非空 equips(画面真值,如 deploy_bench 快照链)优先不覆盖。"""
    old = [_bc('卡芙卡')]
    old[0].equips = ['光能电池', '生命之花']
    new = [_bc('卡芙卡')]
    new[0].equips = ['绝对热量']   # 穿着合成后画面真值
    assert _merge_equips(old, new)[0].equips == ['绝对热量']


def test_reconcile_multi_copy_pairing_and_departure() -> None:
    """同名多副本逐个配对消耗(次序无关);离场角色的 equips 自然丢弃。"""
    old = [_bc('卡芙卡', 1), _bc('卡芙卡', 2)]
    old[0].equips = ['A']
    old[1].equips = ['B', 'C']
    new = [_bc('卡芙卡', 1), _bc('藿藿', 3)]
    out = _merge_equips(old, new)
    assert out[0].equips == ['A']
    assert out[1].equips == []          # 藿藿无旧账 → 空
    # 第二副本配对消耗(单副本新读只拿第一份,不多发)

