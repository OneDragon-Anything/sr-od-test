"""sim 重做 S2(M06 派生池 + M05 商店发牌)回归锁。

设计正本 = ``
`` §2.2 M05/M06;锁面 = 副本数真值
(27/27/9/9/9)/held 星级派生不变量/≥9 清空发牌过滤(U11)/专家入池
假设(U10)/5 槽发牌与概率表/免费刷先行(M05)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)

import pytest
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_bview,
)

from sr_od.application.currency_war.data.cw_chars import CHARACTERS, chars_by_cost
from sr_od.application.currency_war.data.cw_shop_odds import (
    POOL_COPIES_PER_CARD,
    REFRESH_PROB,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_pool import (
    EXPERT_COPIES_ASSUMED,
    drawable_names,
    fixed_pool,
    grant_bucket_names,
    held_copies,
    remaining_pool,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    ROTATION_ASSUMPTION_DISCLOSURE,
    deal_shop,
    effective_deal_probs,
)
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='TestSigWriter',
                      mode='compute')


def _fresh_gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


# ============================================================ M06 固定池与派生

def test_fixed_pool_copies_truth_and_expert_append() -> None:
    """副本数真值(1/2 费 27、3/4/5 费 9,V3.7 收案);专家入池 = U10
    首版假设(同费档追加 9 副本,标注待核);注册表外具名拒收。"""
    pool = fixed_pool()
    assert pool, '固定池非空'
    for name, copies in pool.items():
        assert copies == POOL_COPIES_PER_CARD[CHARACTERS[name].cost], \
            f'{name} 副本数偏离 POOL_COPIES_PER_CARD'
    any_cost1 = chars_by_cost(1)[0].name
    boosted = fixed_pool(extra_experts={any_cost1: EXPERT_COPIES_ASSUMED})
    assert boosted[any_cost1] == pool[any_cost1] + EXPERT_COPIES_ASSUMED
    with pytest.raises(ValueError, match='注册表'):
        fixed_pool(extra_experts={'不存在的角色': 9})


def test_held_derived_from_bench_and_deployed_stars() -> None:
    """held = Σ 3^(star−1)(容器 bench/deployed 派生;合成不销毁口径:
    2★ 计 3 张);剩余 = 固定 − held 不变量。"""
    gs = _fresh_gs()
    n1 = chars_by_cost(1)[0].name
    n2 = chars_by_cost(2)[0].name
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs.observe(gs.bench, cw4_bview([
        cw4_bc(n1, star=1),
        cw4_bc(n1, star=1),
    ]), sig=sig)
    gs.observe(gs.deployed, _dvs([Unit(char_id=n2, star=2)], []), sig=sig)
    held = held_copies(gs)
    assert held[n1] == 2, '两只 1★ = 2 副本'
    assert held[n2] == 3, '2★ = 3 副本(3^(2−1))'
    remaining = remaining_pool(gs)
    assert remaining[n1] == POOL_COPIES_PER_CARD[1] - 2
    assert remaining[n2] == POOL_COPIES_PER_CARD[2] - 3


def test_drawable_names_nine_copy_clearance() -> None:
    """≥9 清空 = 发牌过滤(U11):held ≥9 的牌不再进店,即便 1/2 费
    27 副本下剩余仍 >0(两条件不可互替)。"""
    gs = _fresh_gs()
    n1 = chars_by_cost(1)[0].name
    gs.observe(gs.bench, cw4_bview([
        cw4_bc(n1, star=3),   # 3★ = 9 副本
    ]), sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert held_copies(gs)[n1] == 9
    assert remaining_pool(gs)[n1] == POOL_COPIES_PER_CARD[1] - 9, \
        '27 副本卡 9 持有后剩余仍为正'
    assert n1 not in drawable_names(gs, 1), '≥9 清空:不再进店'
    other = [n for n in drawable_names(gs, 1) if n != n1]
    assert other, '同档其余牌照常可进店'


# ============================================================ 档感知与授予出口(池升格 kernel 批新增)

def test_drawable_names_tier_aware_bucket() -> None:
    """档感知:档 = 4(写点先例 = pick_planner 升费腿 write_logic 档行)
    → drawable_names(4) 含银狼LV.999、drawable_names(3) 不含;档未
    观察(None)→ 归约 3 费桶(起始档语义默认)。授予出口同享档过滤。"""
    gs = _fresh_gs()
    sw = '银狼LV.999'
    gs.write_logic(gs.lv999_cost_tier, 4, produced_by='TestWriter',
                   sig=_lsig())
    assert sw in drawable_names(gs, 4), '升费后归新费用档桶'
    assert sw not in drawable_names(gs, 3), '升费后旧档抽不出'
    assert sw in grant_bucket_names(gs, 4), '授予出口同享档过滤'
    gs_default = _fresh_gs()
    assert sw in drawable_names(gs_default, 3), '档未观察归约 3 费桶'
    assert sw not in drawable_names(gs_default, 4)
    assert sw in grant_bucket_names(gs_default, 3)


def test_dual_exit_divergence_on_nine_copies() -> None:
    """双出口分野:held ∈ [9,26] 的 1 费卡(3★ = 9 副本,27 副本下剩余
    18 >0)在 drawable_names(商店出口)被 ≥9 清空、在 grant_bucket_names
    (授予出口,不含 ≥9 过滤)仍在册——两出口集合不等锁。"""
    gs = _fresh_gs()
    n1 = chars_by_cost(1)[0].name
    gs.observe(gs.bench, cw4_bview([
        cw4_bc(n1, star=3),   # 3★ = 9 副本
    ]), sig=ChannelSig(family='obs', actor='TestSigWriter'))
    assert held_copies(gs)[n1] == 9
    assert remaining_pool(gs)[n1] == POOL_COPIES_PER_CARD[1] - 9, \
        '剩余 >0(共享条件在,分野纯由 ≥9 过滤产生)'
    assert n1 not in drawable_names(gs, 1), '商店出口:≥9 清空'
    assert n1 in grant_bucket_names(gs, 1), '授予出口:无 ≥9 过滤'


def test_conservation_safe_across_tier_transform() -> None:
    """守恒跨档安全:升费变换 2★→1★(升费腿形态,held 3 份→1 份)不炸
    守恒、旧档桶账面不出负值;副本数按名计与档无关(3/4/5 费同 9,
    升费只换桶归属)。"""
    sw = '银狼LV.999'
    sig = ChannelSig(family='obs', actor='TestSigWriter')
    gs = _fresh_gs()
    gs.observe(gs.bench, cw4_bview([cw4_bc(sw, star=2)]), sig=sig)
    assert held_copies(gs)[sw] == 3
    gs.write_logic(gs.lv999_cost_tier, 4, produced_by='TestWriter',
                   sig=_lsig())
    gs.observe(gs.bench, cw4_bview([cw4_bc(sw, star=1)]), sig=sig)
    assert held_copies(gs)[sw] == 1
    assert remaining_pool(gs)[sw] == POOL_COPIES_PER_CARD[3] - 1, \
        '守恒按名核对跨档不误炸,旧档账面不为负'
    assert sw in drawable_names(gs, 4)
    assert sw in grant_bucket_names(gs, 4)


# ============================================================ M05 发牌与刷价

def test_deal_shop_level1_pure_cost1_payload() -> None:
    """Lv1 概率表纯 1 费 → 5 槽全 1 费注册表名;概率条随载荷落容器
    (§3.3.2 契约);槽号 1 基连号。"""
    gs = _fresh_gs()
    deal_shop(gs, stream_rng(3, 'M05/deal/1/1'), level=1,
              tag='shop:deal:p1r1')
    payload = gs.shop.value
    assert payload is not None and len(payload.cards) == 5
    assert payload.refresh_probs == {1: 1.0}
    for i, slot in enumerate(payload.cards):
        assert slot.kind == 'content' and slot.card is not None
        assert slot.card.cost == 1 and slot.card.star == 1
        assert slot.card.name in CHARACTERS
        assert slot.card.slot == i + 1
    assert gs.shop.evidence is not None \
        and 'sim:engine:' in gs.shop.evidence


def test_deal_shop_level9_domain_and_registered_names() -> None:
    """Lv9 混档发牌:出场费用档 ⊆ 表内正概率档,名集全部注册表在册
    (M06 抽名约束;直出 2/3 星 = 0,U12)。"""
    gs = _fresh_gs()
    deal_shop(gs, stream_rng(4, 'M05/deal/1/9'), level=9)
    payload = gs.shop.value
    legal_costs = {c for c, p in REFRESH_PROB[9].items() if p > 0}
    for slot in payload.cards:
        if slot.card is not None:
            assert slot.card.cost in legal_costs
            assert slot.card.star == 1, 'U12:首版直出概率 0'
            assert slot.card.name in CHARACTERS


def test_effective_deal_probs_rotation_toggle() -> None:
    """基线 = REFRESH_PROB 原表;轮岗开 = 重掷翻倍档(1/5 均匀系假设档,
    假设随 ROTATION_ASSUMPTION_DISCLOSURE 申报)或不可行档退基线。"""
    base = effective_deal_probs(6, stream_rng(1, 'M05/rotation/1/6'),
                                rotation_on=False)
    assert base == dict(REFRESH_PROB[6])
    rotated = effective_deal_probs(6, stream_rng(2, 'M05/rotation/1/6'),
                                   rotation_on=True)
    assert abs(sum(rotated.values()) - 1.0) < 1e-6
    assert set(rotated) <= {1, 2, 3, 4, 5}
    assert ROTATION_ASSUMPTION_DISCLOSURE
