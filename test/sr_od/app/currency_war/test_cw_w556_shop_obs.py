"""商店开态对账纯函数真值表(cw_shop_obs:check_shop_pool / compare_merge_preview / refresh_expect)。

零接线批:三函数均为纯函数,测试只锁「输入→输出」映射,不触任何生产行为面。
规则出处单一源 = cw_shop_odds(REFRESH_PROB / POOL_COPIES_PER_CARD / SHOP_SLOTS)
与 docs/game/currency_war/research/merge_mechanics.md §2.7(合成预览对账信号)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.cw_shop_obs import (
    compare_merge_preview,
    check_shop_pool,
    refresh_expect,
)
from sr_od.application.currency_war.data.cw_shop_odds import REFRESH_PROB, SHOP_SLOTS

# ---------------------------------------------------------------------------
# 1. check_shop_pool
# ---------------------------------------------------------------------------


class TestCheckShopPool:
    def test_tier_boundary_pass(self) -> None:
        """门槛线内侧:4费在 Lv5(p=0.02)、5费在 Lv7(p=0.01)→ 通过。"""
        assert check_shop_pool([('甲', 4)], level=5) == []
        assert check_shop_pool([('乙', 5)], level=7) == []
        assert check_shop_pool([('丙', 1)], level=3) == []  # Lv1-3 纯 1 费

    def test_tier_boundary_locked(self) -> None:
        """门槛线外侧:4费在 Lv4、5费在 Lv6、2费在 Lv1-3 → tier_locked。"""
        kinds = {v.kind for v in check_shop_pool([('甲', 4)], level=4)}
        assert kinds == {'tier_locked'}
        kinds = {v.kind for v in check_shop_pool([('乙', 5)], level=6)}
        assert kinds == {'tier_locked'}
        kinds = {v.kind for v in check_shop_pool([('丙', 2)], level=3)}
        assert kinds == {'tier_locked'}

    def test_tier_table_exhaustive_with_registry(self) -> None:
        """与 REFRESH_PROB 全表互证:非零档通过、零档锁,无一例外。"""
        for level, tiers in REFRESH_PROB.items():
            for cost, p in tiers.items():
                violations = check_shop_pool([(f'牌{cost}', cost)], level=level)
                assert (violations == []) == (p > 0), \
                    f'Lv{level} {cost}费 p={p} 应{"过" if p > 0 else "锁"}'

    def test_invalid_cost(self) -> None:
        """费用不在 1-5(OCR 误读)→ invalid_cost,两查都免。"""
        vs = check_shop_pool([('怪', 0), ('怪2', 6)], level=10)
        assert {v.kind for v in vs} == {'invalid_cost'}

    def test_pool_overdraw_and_cap_boundary(self) -> None:
        """池守恒:可见+持有 > 上限 → 违例;恰等于上限 → 通过(1费 cap=27)。"""
        ok = check_shop_pool([('甲', 1), ('甲', 1)], level=10,
                             pool_state={'甲': 25})
        assert ok == []  # visible=2 + held=25 = 27 = cap
        bad = check_shop_pool([('甲', 1), ('甲', 1)], level=10,
                              pool_state={'甲': 26})
        assert [v.kind for v in bad] == ['pool_overdraw']  # 按牌名去重,同牌多张只一张票
        assert 'visible=2' in bad[0].detail and 'cap=27' in bad[0].detail

    def test_pool_state_none_skips_pool_check(self) -> None:
        """pool_state None = 池查跳过(现状无池追踪账,入参兜)。"""
        assert check_shop_pool([('甲', 1)] * 30, level=10) == []

    def test_two_checks_independent(self) -> None:
        """tier_locked 牌仍做池查(两票独立留证)。"""
        vs = check_shop_pool([('甲', 5)], level=6, pool_state={'甲': 9})
        assert {v.kind for v in vs} == {'tier_locked', 'pool_overdraw'}

    def test_level_out_of_range_reports_honestly(self) -> None:
        """level 越界按 p=0 兜 → 全档锁,如实报(不静默通过)。"""
        kinds = {v.kind for v in check_shop_pool([('甲', 1)], level=99)}
        assert kinds == {'tier_locked'}


# ---------------------------------------------------------------------------
# 2. compare_merge_preview(单向验证)
# ---------------------------------------------------------------------------


class TestCompareMergePreview:
    def test_detected_none_all_pending(self) -> None:
        """识别端未建(现状恒此形态)→ 全 pending,suspect 恒空(登记形态可跑)。"""
        r = compare_merge_preview({0: True, 2: False}, None)
        assert [row.verdict for row in r.rows] == ['pending', 'pending']
        assert r.suspect_slots == []
        assert [row.detected for row in r.rows] == [None, None]

    def test_our_true_detected_false_is_suspect(self) -> None:
        """单向罚则唯一对象:我方 True 而识别无星 → our_suspect。"""
        r = compare_merge_preview({3: True}, {3: False})
        assert r.rows[0].verdict == 'our_suspect'
        assert r.suspect_slots == [3]

    def test_game_extra_counted_not_penalized(self) -> None:
        """识别 True 而我方 False → game_extra(留证不判罚,不出 suspect)。"""
        r = compare_merge_preview({1: False}, {1: True})
        assert r.rows[0].verdict == 'game_extra'
        assert r.suspect_slots == []

    def test_match_and_key_union(self) -> None:
        """同键相等 = match;键集 = 两侧并集,缺键按 False 兜。"""
        r = compare_merge_preview({0: False, 2: True}, {0: False, 4: False})
        assert [row.slot for row in r.rows] == [0, 2, 4]
        assert [row.verdict for row in r.rows] == ['match', 'our_suspect', 'match']

    def test_empty_inputs(self) -> None:
        assert compare_merge_preview({}, {}).rows == []
        assert compare_merge_preview({}, None).rows == []


# ---------------------------------------------------------------------------
# 3. refresh_expect
# ---------------------------------------------------------------------------


class TestRefreshExpect:
    def test_basic_delta(self) -> None:
        """金 −刷新费;旧五张回池账按名计数(重复牌合并)。

        口径(用户裁决·倾向口径):新五格按当前等级概率独立抽取,同牌可
        重复——本函数是期望增量,对账只硬验金差/五格有牌/池守恒统计面,
        **不逐张断言全异**,故无「新五张互异」类断言(这是收窄后的规格)。
        """
        r = refresh_expect(10, [('甲', 1), ('甲', 1), ('乙', 2), ('丙', 3), ('丁', 4)],
                           refresh_cost=2)
        assert r.gold_after == 8 and r.refresh_cost == 2
        assert r.insufficient is False
        assert r.pool_returned == {'甲': 2, '乙': 1, '丙': 1, '丁': 1}
        assert r.new_slots == SHOP_SLOTS == 5

    def test_insufficient_gold(self) -> None:
        """金不足:insufficient True,算术差如实为负(执行判归调用方)。"""
        r = refresh_expect(1, [('甲', 1)], refresh_cost=2)
        assert r.insufficient is True and r.gold_after == -1

    def test_custom_refresh_cost(self) -> None:
        """费用不写死(W554:疑似 f(当前金币))→ 必填参数,任意现读值合法。"""
        assert refresh_expect(10, [], refresh_cost=0).gold_after == 10
        assert refresh_expect(10, [], refresh_cost=3).gold_after == 7

    def test_refresh_cost_is_required(self) -> None:
        """无默认值:漏传费用 = TypeError(防调用方写死 2 的旧习惯回流)。"""
        with pytest.raises(TypeError):
            refresh_expect(10, [])  # type: ignore[call-arg]

    def test_empty_old_cards(self) -> None:
        """空旧表合法(首刷无旧牌):回池账空、insufficient 按 gold 判。"""
        r = refresh_expect(5, [], refresh_cost=2)
        assert r.pool_returned == {} and r.insufficient is False
        assert r.gold_after == 3


# ---------------------------------------------------------------------------
# 4. 端到端(fixture 帧经 read_shop_cards → check_shop_pool)
# ---------------------------------------------------------------------------


def test_shop_fixture_end_to_end(test_context) -> None:
    """开商店帧离线复跑:read_shop_cards 全链 → check_shop_pool(Lv10 全档解锁)零违例。

    Lv10 五档概率全非零 → tier 查必过;池查不做(pool_state None,现状无账)。
    本测试锁「识别输出能过一致性票」的生产形态,不锁具体牌名(牌名归 SIFT 锁)。
    """
    from sr_od.application.currency_war.kernel.cw_obs_core import SHOP_SCREEN_NAME
    from sr_od.application.currency_war.cw_observation import read_shop_cards
    from sr_od.application.currency_war.kernel.cw_state import card_cost

    state = 'shop_open_preview_star'
    if not test_context.has_screen(SHOP_SCREEN_NAME, state):
        pytest.skip(f'存档截图缺失:screens/{SHOP_SCREEN_NAME}/{state}.webp')
    screen = test_context.load_screen(SHOP_SCREEN_NAME, state)
    cards = read_shop_cards(test_context, screen)
    assert len(cards) == 5, f'应读满 5 张牌,实际 {len(cards)}'
    card_tuples = [(c.name, card_cost(c)) for c in cards]
    assert check_shop_pool(card_tuples, level=10) == []
