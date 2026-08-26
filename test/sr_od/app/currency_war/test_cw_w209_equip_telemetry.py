# -*- coding: utf-8 -*-
"""W209g/ADR-0387 追加:装备遥测三断点修法锁(编排者定位,用户点名
「装备采集代码怎么会没采集到」)。

断点(run 26 实锤):
① ``cw_reconcile`` 整批替换清零 equips——decisions.jsonl 希儿装备闪烁
   (round6 三条快照仅一条有装备):布局错乱→纠漂狂刷→快照写入的装备反复被冲;
② ``equip_all`` 采集层过滤工具后才写 last_owned_equips——冶金炉/扳手从不
   进决策快照(owned 恒空);
③ 装备读槽硬编码(deploy_bench 已由 W209c 修;equip_all M7/C6 转移重读
   原硬编码 10,与布局档自相矛盾)。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.cw_reconcile import _merge_equips
from sr_od.application.currency_war.cw_state import BenchChar


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


def test_equip_collect_writes_unfiltered() -> None:
    """断点②:采集写端全量(工具不过滤)——过滤只留穿戴决策层。

    源码级锁:last_owned_equips 赋值来自 hits(全量),wearable 只辖 drag。
    """
    import inspect
    from sr_od.application.currency_war.operations.prep import equip_all
    src = inspect.getsource(equip_all)
    assert 'last_owned_equips = [n for n, _, _ in hits]' in src, \
        '采集写端必须全量 hits(工具进快照;过滤只辖 wearable 穿戴决策)'
    assert 'last_owned_equips = [n for n, _ in wearable]' not in src, \
        '旧版过滤后写快照(owned 恒空断点)不得回流'


def test_equip_row_reads_follow_layout() -> None:
    """断点③:equip_all 后排装备读槽随布局选档(select_back_layout 单一源),
    不再硬编码 10/6。"""
    import inspect
    from sr_od.application.currency_war.operations.prep import equip_all
    src = inspect.getsource(equip_all)
    assert 'select_back_layout' in src, \
        'equip_all 装备读槽必须接布局双通道单一源(ADR-0385)'
    assert '4 if row == \'front\' else 10' not in src, \
        '旧硬编码 10 读槽(deploy 拖 8 格/装备读固定槽自相矛盾)不得回流'
