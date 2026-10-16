"""buy_card 上报合并升星触发发放腿测试(镜像 src =
kernel/cw_action_report/buy_card.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.4 条 1 + §4.6:买牌上报内采集
升星事实(引擎 A),在升星腿整表写毕后收尾发火——**发火时序锁**:bench
终态 = 合并产物 + 发放角色并存(若发火先于升星腿整表写,发放写会被
覆盖,终态缺发放角色 = 本锁红)。
"""
from __future__ import annotations

import random
from collections.abc import Iterator

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc as _bc,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_card as _card,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_buy_card_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
)

_POOL = ('符玄', '希儿')

_SIG = ChannelSig(family='logic_action', actor='CwScreenShop',
                  mode='compute')


@pytest.fixture
def seeded_provider() -> Iterator[None]:
    """注确定 rng 提供槽(固定种子,期望名可现算钉名),必达复位。"""
    set_action_rng_provider(lambda tool: random.Random(20261016))
    try:
        yield None
    finally:
        set_action_rng_provider(None)


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star) for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def test_buy_merge_fires_grant_after_starup_leg(seeded_provider) -> None:
    """买牌发火时序锁(T-26 设计 §4.6 主腿):2×1★花火在席,买第 3 张
    1★花火 → 合并 2★ 产物;升星腿整表写毕后发火 → bench 终态 = 产物 +
    发放角色并存(发放名 = 注入槽种子现算;gold 未读买腿跳写,场景
    最小化)。"""
    expected = random.Random(20261016).choice(list(_POOL))
    gs = cw4_gs(node_fill=False, shop_screen='off', gold_unread=True,
                bench=[_bc('花火'), _bc('花火')],
                active_env='量子同频契约')
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('花火', cost=2)), _SIG)
    assert out.applied and out.bought_count == 1, '买牌上报成功'
    assert _bench_units(gs) == [('花火', 2), (expected, 1)], \
        f'合并产物 + 发放角色并存(升星腿不覆盖发放写): {_bench_units(gs)}'
