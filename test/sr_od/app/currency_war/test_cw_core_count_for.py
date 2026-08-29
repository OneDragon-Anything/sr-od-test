# -*- coding: utf-8 -*-
"""③ 攒数据地基锁:core_count_for 按 target 语境路由单一口径。

桥池 fixed+core / 仙舟三人组 _CORE_TRIO(旧 v1 线库 core_cards 分支
随 ADR-0336 删除——decision_v2 target 是 COMP 套名,不查线库)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_line_defs import core_count_for


def test_bridge_target_counts_pool_core() -> None:
    """桥 id → 桥池 fixed+core 在场数(W126/ADR-0350:hunt3/dot_belog
    已封存删除——hunt3 路由退缺省;存活桥照常计数)。"""
    names = {'飞霄', '椒丘'}
    # hunt3 已删:未知桥 id 走缺省路由(飞霄/椒丘 ∉ 三人组 → 0)
    assert core_count_for('hunt3', names) == 0
    assert core_count_for('xianzhou_dot', {'爻光', '藿藿'}) == 2   # fixed+core
    assert core_count_for('xianzhou_dot', {'爻光', '姬子·启行'}) == 1  # 非核心不计


def test_p2_bridge_routed() -> None:
    """P2 桥(train4_shield3)也走路由(不在 P1 池;曾静默退三人组)。"""
    assert core_count_for('train4_shield3', {'三月七'}) >= 1


def test_bridge_field_name_is_real() -> None:
    """桥字段存在性(审查#3:getattr 链死防御掩盖改名;直接属性
    访问,改名即刻 AttributeError)。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    for combo in (*BRIDGE_POOL, *BRIDGE_POOL_P2):
        assert combo.bridge_id   # 属性访问:字段改名此处即炸


def test_line_bridge_id_no_overlap() -> None:
    """桥 id 唯一性(旧线库已删;桥 id 与 COMP/角色名不撞即可)。"""
    from sr_od.application.currency_war.kernel.cw_bridge_pool import (
        BRIDGE_POOL,
        BRIDGE_POOL_P2,
    )
    bridge_ids = {c.bridge_id
                  for c in (*BRIDGE_POOL, *BRIDGE_POOL_P2)}
    assert len(bridge_ids) == len((*BRIDGE_POOL, *BRIDGE_POOL_P2)), \
        '桥 id 重复(core_count_for 路由歧义)'


def test_empty_and_unknown_fallback_trio() -> None:
    """空 target → 三人组缺省;未知 target 不 crash 退缺省。"""
    assert core_count_for('', {'爻光', '藿藿', '丹恒·饮月'}) == 3
    assert core_count_for('nonexistent', {'藿藿'}) == 1


def test_sim_ledger_core_count_semantics() -> None:
    """sim 账本 core_count 语义标记(core_routed;含 None 序列化)。"""
    import json

    import contextlib
    import io

    from sr_od.application.currency_war.sim.runner import simulate_p1_batch
    with contextlib.redirect_stderr(io.StringIO()):
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as td:
            rep = simulate_p1_batch(3, pool='snapshot',
                                    ledger=_P(td) / 'sem')
            mf = json.loads((_P(rep['ledger_dir'])
                             / 'manifest.json').read_text(encoding='utf-8'))
            assert mf['ledger_semantics'] == 'core_routed'
