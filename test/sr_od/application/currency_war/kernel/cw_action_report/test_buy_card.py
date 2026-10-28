"""buy_card 上报测试(镜像 src = kernel/cw_action_report/buy_card.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-26-liangzi-tongpin-qiyue.md(定稿)§2.4 条 1 + §4.6:买牌上报内采集
升星事实(引擎 A),在升星分支整表写毕后收尾发火——**发火时序锁**:bench
终态 = 合并产物 + 发放角色并存(若发火先于升星分支整表写,发放写会被
覆盖,终态缺发放角色 = 本锁红)。

追加面 = T-42 设计(designs/T-42-teyao-zhuanjia-yinlang.md)§4 锁 3
(购买渠道,条件形态专家触发):购买回调分支段判据一次——买银狼LV.999
解锁 / 买其他 3 费角色不触发 / 拒买( applied=False 早退)不触发。
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


def test_buy_merge_fires_grant_after_starup_branch(seeded_provider) -> None:
    """买牌发火时序锁(T-26 设计 §4.6 主分支):2×1★花火在席,买第 3 张
    1★花火 → 合并 2★ 产物;升星分支整表写毕后发火 → bench 终态 = 产物 +
    发放角色并存(发放名 = 注入槽种子现算;gold 未读买分支跳写,场景
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
        f'合并产物 + 发放角色并存(升星分支不覆盖发放写): {_bench_units(gs)}'


# ============================================================ 条件形态专家触发(T-42 §4 锁 3)

_ENV_YINLANG = '特邀专家:银狼'


def test_buy_lv999_unlocks_expert_with_trigger_evidence() -> None:
    """购买渠道主分支(设计 §4 锁 3 条 1):本卡局买银狼LV.999 → 解锁
    银狼入商店;write 行 evidence = buy_card:expert_trigger#expert_unlock
    (购买/桥渠道效果串面以 write 行为准,evidence 可见,设计 §2.5)。"""
    gs = cw4_gs(bench=[], shop=[_card('银狼LV.999', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out.applied, '购买成功'
    assert gs.unlocked_experts.value == ('银狼',), '解锁写入'
    assert gs.unlocked_experts.evidence == \
        'buy_card:expert_trigger#expert_unlock', '触发分支 evidence 可见'


def test_buy_other_3cost_no_trigger() -> None:
    """非目标名不触发(设计 §4 锁 3 条 2):本卡局买其他 3 费角色
    (希儿)→ 判据条件①名不命中,零解锁写。"""
    gs = cw4_gs(bench=[], shop=[_card('希儿', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('希儿', cost=3, x=0)), _SIG)
    assert out.applied, '购买成功'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写'


def test_buy_rejected_bench_full_no_trigger() -> None:
    """拒买不触发(设计 §4 锁 3 条 3):满栏且合成不可达 = applied=False
    早退(reason='bench_full'),早退路径不经购买回调分支 → 零解锁写
    (触发点在回调分支的时序含义锁)。"""
    full_bench = [_bc(n) for n in ('希儿', '符玄', '花火', '停云', '刃',
                                   '杰帕德', '娜塔莎', '丹恒', '三月七')]
    gs = cw4_gs(bench=full_bench, shop=[_card('银狼LV.999', cost=3, x=0)],
                gold_unread=True, active_env=_ENV_YINLANG)
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionBuyCardParam,
    )
    out = report_action_buy_card_param(
        gs, CwActionBuyCardParam(card=_card('银狼LV.999', cost=3, x=0)),
        _SIG)
    assert out.applied is False and out.reason == 'bench_full', '拒买早退'
    assert gs.unlocked_experts.value in (None, ()), '零解锁写(早退不经触发分支)'
