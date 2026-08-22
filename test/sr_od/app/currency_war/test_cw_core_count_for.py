# -*- coding: utf-8 -*-
"""③ 攒数据地基锁:core_count_for 按 target 语境路由单一口径。

三源收口(二轮#8):线库 core_cards / 桥池 fixed+core / 仙舟
三人组 _CORE_TRIO——非仙舟线局 core_count 不再恒 0。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_line_defs import core_count_for


def test_bridge_target_counts_pool_core() -> None:
    """桥 id → 桥池 fixed+core 在场数(hunt3:飞霄/椒丘/貊泽/灵砂)。"""
    names = {'飞霄', '椒丘'}
    assert core_count_for('hunt3', names) == 2
    assert core_count_for('xianzhou_dot', {'爻光', '藿藿'}) == 2   # fixed+core
    assert core_count_for('hunt3', {'飞霄', '姬子·启行'}) == 1    # 非核心不计


def test_p2_bridge_routed() -> None:
    """P2 桥(train4_shield3)也走路由(不在 P1 池;曾静默退三人组)。"""
    assert core_count_for('train4_shield3', {'三月七'}) >= 1


def test_known_line_without_core_returns_none() -> None:
    """dot_fallback(已知线,core_cards=[] 不锁信号)→ None
    (无核心概念;退三人组=③ dot 桶噪声,审查#1)。"""
    assert core_count_for('dot_fallback', {'卡芙卡', '藿藿'}) is None
    assert core_count_for('v2:dot_fallback', {'卡芙卡'}) is None


def test_bridge_field_name_is_real() -> None:
    """桥字段存在性(审查#3:getattr 链死防御掩盖改名;直接属性
    访问,改名即刻 AttributeError)。"""
    from sr_od.application.currency_war.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    for combo in (*BRIDGE_POOL, *BRIDGE_POOL_P2):
        assert combo.bridge_id   # 属性访问:字段改名此处即炸


def test_line_bridge_id_no_overlap() -> None:
    """线 id ∩ 桥 id = ∅(审查#7:桥先于线库匹配是隐式约定,
    未来撞名会静默先撞桥——断言钉住值域不相交)。"""
    from sr_od.application.currency_war.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    from sr_od.application.currency_war.cw_line_library_v1 import (
        LINE_LIBRARY_V1,
    )
    bridge_ids = {c.bridge_id
                  for c in (*BRIDGE_POOL, *BRIDGE_POOL_P2)}
    line_ids = {l.line_id for l in LINE_LIBRARY_V1}
    assert not (bridge_ids & line_ids), \
        f'线/桥 id 撞名:{bridge_ids & line_ids}(core_count_for 路由歧义)'


def test_line_target_counts_core_cards() -> None:
    """锁线 v2: 前缀 → 线库 core_cards(jizi=姬子·启行)。"""
    assert core_count_for('v2:jizi_train', {'姬子·启行', '三月七'}) == 1
    assert core_count_for('feiying_joy', {'绯英'}) == 1


def test_empty_and_unknown_fallback_trio() -> None:
    """空 target → 三人组缺省;未知 target 不 crash 退缺省。"""
    assert core_count_for('', {'爻光', '藿藿', '丹恒·饮月'}) == 3
    assert core_count_for('v2:nonexistent', {'藿藿'}) == 1


def test_sim_ledger_core_count_semantics() -> None:
    """sim 账本 core_count 语义标记(core_routed;含 None 序列化)。"""
    import json

    import contextlib
    import io
    from sr_od.application.currency_war.cw_sim import simulate_p1_batch
    with contextlib.redirect_stderr(io.StringIO()):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as td:
            rep = simulate_p1_batch(3, pool='snapshot',
                                    ledger=_P(td) / 'sem')
            mf = json.loads((_P(rep['ledger_dir'])
                             / 'manifest.json').read_text(encoding='utf-8'))
            assert mf['ledger_semantics'] == 'core_routed'
