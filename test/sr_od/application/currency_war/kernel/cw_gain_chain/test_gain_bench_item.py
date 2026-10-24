"""gain_bench_item 落位口测试(镜像 src = kernel/cw_gain_chain.py,被测 =
`_place_bench_item`/`gain_bench_item`/`_build_pool` 占位,按拆目录规范落位;
同 src 兄弟测试 = kernel/test_gain_chain.py〔在册超限文件,只读复用不追加;
三落位回归 = 其 test_gain_bench_item_three_landings〕)。

测试面依据 = 迭代 T-39 专家研讨会设计(.debug/progress/2026-09-23-invest-
effects-calc/designs/T-39-zhuanjia-yantaohui.md)§2.4 + §4 锁 3/锁 5 占位
半边:
- 落席 kind 直查:映射外道具名直调公开口 → KeyError 响亮(构造式 =
  ``BENCH_ITEM_KINDS[item]`` 直查非 .get,键缺 = 代码 bug,禁静默兜底);
- 溢出占位身份两分:溢出位道具串 → 惰性槽件带名查映射(kind/item 逐位 =
  映射表值),角色串 → unit 腿(回归),溢出空 → 零占位。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    _build_pool,
    gain_bench_item,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    seed_opening_state,
)

_SIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='CwGainChainTest')


def _make_gs_seeded() -> GameState:
    """种子底座直构(bench 未观察拒落,先种 9 空槽)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    seed_opening_state(gs)
    return gs


def test_place_bench_item_unknown_name_key_error() -> None:
    """落席 kind 直查(设计 §4 锁 3):映射外道具名直调公开口 → KeyError
    响亮——静默兜底 = 落错身份,治理劣于响亮(设计 §2.4 裁决)。"""
    gs = _make_gs_seeded()
    with pytest.raises(KeyError):
        gain_bench_item(gs, '神秘道具', rand=False, sig=_SIG, evidence='t')


def test_build_pool_overflow_item_named_slot_by_mapping() -> None:
    """溢出占位身份两分(设计 §2.4.2 + §4 锁 5 占位半边):溢出位道具串 →
    惰性槽件带名查映射(kind/item 逐位);角色串 → unit 腿(回归);
    溢出空 → 零占位。"""
    gs = _make_gs_seeded()
    gs.observe(gs.overflow_card, '专家邀请函', sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    pool = _build_pool(gs, None)
    assert pool is not None and len(pool.ovf) == 1
    assert (pool.ovf[0].kind, pool.ovf[0].item) == \
        ('bookcard', '专家邀请函'), '邀请函占位 = bookcard 带名'

    gs2 = _make_gs_seeded()
    gs2.observe(gs2.overflow_card, '简易武装箱', sig=_SIG_OBS)
    gs2.observe(gs2.overflow_warning, True, sig=_SIG_OBS)
    pool2 = _build_pool(gs2, None)
    assert pool2 is not None and len(pool2.ovf) == 1
    assert (pool2.ovf[0].kind, pool2.ovf[0].item) == \
        ('supply_box', '简易武装箱'), '箱占位 = supply_box 带名(回归)'

    gs3 = _make_gs_seeded()
    gs3.observe(gs3.overflow_card, '希儿', sig=_SIG_OBS)
    pool3 = _build_pool(gs3, None)
    assert pool3 is not None and len(pool3.ovf) == 1
    assert pool3.ovf[0].kind == 'unit' \
        and pool3.ovf[0].unit is not None \
        and pool3.ovf[0].unit.char_id == '希儿', '角色串 → unit 腿(回归)'

    gs4 = _make_gs_seeded()
    pool4 = _build_pool(gs4, None)
    assert pool4 is not None and pool4.ovf == [], '溢出空 → 零占位'
