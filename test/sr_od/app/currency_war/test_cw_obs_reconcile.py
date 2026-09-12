"""obs 识别层·对账与仲裁纯函数(重建合同 ③)。

obs 独有的自检层:识别 vs 计算/池守恒的裁决语义,「对账不判哪边错、
记账留证」的代码化。本文件锁的是裁决行为本身:
- 仲裁注册表(cw_arbitration):规则声明/verdict 五态/未注册 key 当场炸;
- 商店三对账(cw_shop_obs):卡池一致性/合成预览单向验证/刷新期望;
- 羁绊面板解析与对账(cw_faction_obs):token 真值表 + 逐名三态。
全部纯函数直调,零桩零图片。组织蓝图 = obs 先删后重建规格 §2③。
"""
import pytest
from sr_od.application.currency_war.data.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.obs import cw_arbitration as arb
from sr_od.application.currency_war.obs import cw_faction_obs as facobs
from sr_od.application.currency_war.obs import cw_shop_obs as shops


# ===== 仲裁注册表(cw_arbitration;15 号稿 §2.4 批 A 迁移) =====

class TestArbitrationRegistry:
    """注册面:生产注册两量在册;schema 声明面;未知 key 拒绝。"""

    def test_production_rules_registered(self):
        keys = arb.registered_keys()
        assert 'deployed_count' in keys
        assert 'board_faction_count' in keys

    def test_deployed_rule_declaration(self):
        rule = arb.get_rule('deployed_count')
        assert rule is not None
        assert rule.dim_class == arb.DIM_COUNT
        assert rule.band == 1   # 分歧告警带 |Δ|>1
        assert set(rule.sources) == {'paddle_x', 'cv_occupied'}

    def test_unknown_key_get_rule_none(self):
        assert arb.get_rule('no_such_quantity') is None

    def test_register_same_key_overrides(self, monkeypatch):
        # 同 key 覆盖 = 显式改声明(声明式注册面的变更通道)
        monkeypatch.setattr(arb, '_RULES', dict(arb._RULES))   # 隔离全局表
        arb.register(arb.ArbitrationRule(
            key='deployed_count', dim_class=arb.DIM_COUNT,
            sources=['a'], combine=lambda **kw: (0, False)))
        assert arb.get_rule('deployed_count').sources == ['a']

    def test_arbitrate_unregistered_key_raises(self, monkeypatch):
        monkeypatch.setattr(arb, '_RULES', {})
        with pytest.raises(KeyError):
            arb.arbitrate('no_such_quantity', {})


class TestCombineDeployedCount:
    """deployed 计数内核:取低值 fail-closed + spread>1 告警带 + 缺席退化。"""

    def test_agree(self):
        assert arb.combine_deployed_count(5, 5) == (5, False)

    def test_take_min_fail_closed(self):
        # 高估→「板满」假判合法化 no-op 死锁(贵);低估→多试一次拖拽(廉价)
        assert arb.combine_deployed_count(5, 7) == (5, True)

    def test_spread_one_is_legal_noise(self):
        # CV 采样边沿/动画残影,单帧 ±1 不行动
        assert arb.combine_deployed_count(5, 6) == (5, False)

    def test_paddle_missing_degrades_to_cv(self):
        # 显式申报的退化:向「板满」侧 fail;调用方必须重读+留证(不得静默)
        assert arb.combine_deployed_count(None, 7) == (7, False)

    def test_cv_missing_degrades_to_paddle(self):
        assert arb.combine_deployed_count(5, None) == (5, False)

    def test_both_missing(self):
        assert arb.combine_deployed_count(None, None) == (None, False)


class TestCombineBoardFrameGated:
    """board 帧态门仲裁:备战帧徽标覆写(画面事实优先);坏帧双源弃权保底座。"""

    def test_prep_frame_badge_overrides(self):
        merged, decisions = arb.combine_board_frame_gated(
            {'昼之半神': 3}, {'昼之半神': 2}, prep_like=True, board_honest=True)
        assert merged['昼之半神'] == 3
        assert decisions == [('昼之半神', 'count_mismatch', True)]

    def test_bad_frame_keeps_computed_base(self):
        # 非备战帧/动画帧:双源皆不可信 → 不裁不覆(W285 overlay 干扰实证)
        merged, decisions = arb.combine_board_frame_gated(
            {'昼之半神': 3}, {'昼之半神': 2}, prep_like=False, board_honest=True)
        assert merged['昼之半神'] == 2
        assert decisions == [('昼之半神', 'count_mismatch', False)]

    def test_ocr_only_faction_merged_in(self):
        # badge 有 computed 无 = tracked 漏阵营(强信号),备战帧覆入
        merged, decisions = arb.combine_board_frame_gated(
            {'仙舟': 1}, {'昼之半神': 2}, prep_like=True, board_honest=True)
        assert merged == {'昼之半神': 2, '仙舟': 1}
        assert decisions == [('仙舟', 'ocr_only', True)]

    def test_agree_no_decisions(self):
        merged, decisions = arb.combine_board_frame_gated(
            {'昼之半神': 2}, {'昼之半神': 2}, prep_like=True, board_honest=True)
        assert merged == {'昼之半神': 2}
        assert decisions == []


class TestArbitrateEntrypoint:
    """统一裁决入口 verdict 五态(ok/noise/arbitrated/rejected/unknown)。"""

    def test_ok(self):
        v, verdict, div = arb.arbitrate(
            'deployed_count', {'paddle_x': 5, 'cv_occupied': 5})
        assert (v, verdict, div) == (5, arb.VERDICT_OK, False)

    def test_in_band_noise(self):
        v, verdict, div = arb.arbitrate(
            'deployed_count', {'paddle_x': 5, 'cv_occupied': 6})
        assert v == 5
        assert verdict == arb.VERDICT_NOISE
        assert div is False

    def test_out_of_band_arbitrated(self):
        v, verdict, div = arb.arbitrate(
            'deployed_count', {'paddle_x': 5, 'cv_occupied': 7})
        assert v == 5
        assert verdict == arb.VERDICT_ARBITRATED
        assert div is True

    def test_missing_source_rejected(self):
        v, verdict, div = arb.arbitrate(
            'deployed_count', {'paddle_x': None, 'cv_occupied': 7})
        assert v == 7
        assert verdict == arb.VERDICT_REJECTED

    def test_all_sources_missing_unknown(self):
        v, verdict, div = arb.arbitrate(
            'deployed_count', {'paddle_x': None, 'cv_occupied': None})
        assert v is None
        assert verdict == arb.VERDICT_UNKNOWN

    def test_board_rule_arbitrated_on_prep_frame(self):
        v, verdict, div = arb.arbitrate('board_faction_count', {
            'badge_ocr': {'昼之半神': 3}, 'computed': {'昼之半神': 2},
            'prep_like': True, 'board_honest': True})
        assert v == {'昼之半神': 3}
        assert verdict == arb.VERDICT_ARBITRATED


# ===== 商店三对账(cw_shop_obs;W556) =====

class TestCheckShopPool:
    """卡池一致性两查:费用档解锁 + 池副本守恒;违例清单不判哪边错。"""

    def test_all_pass(self):
        assert shops.check_shop_pool([('阿格莱雅', 3), ('银狼', 1)], level=6) == []

    def test_invalid_cost_skips_both_checks(self):
        vs = shops.check_shop_pool([('阿格莱雅', 7)], level=6)
        assert [v.kind for v in vs] == ['invalid_cost']

    def test_tier_locked_at_low_level(self):
        # level 1 刷不出 5 费档(p=0)→ 商店不可能刷出 = 识别错或等级读错
        vs = shops.check_shop_pool([('阿格莱雅', 5)], level=1)
        assert [v.kind for v in vs] == ['tier_locked']

    def test_pool_overdraw_per_name_deduped(self):
        # 同名牌 2 张可见 + 持有顶满 → 池守恒破;按牌名去重只开一张
        cap = POOL_COPIES_PER_CARD[1]
        vs = shops.check_shop_pool(
            [('阿格莱雅', 1), ('阿格莱雅', 1)], level=6,
            pool_state={'阿格莱雅': cap})
        assert [v.kind for v in vs] == ['pool_overdraw']

    def test_pool_check_skipped_without_state(self):
        # pool_state 未提供 → 池守恒查整体跳过(现状无池追踪账)
        assert shops.check_shop_pool([('阿格莱雅', 1)], level=6, pool_state=None) == []


class TestCompareMergePreview:
    """合成预览单向验证:我方计算主源;our_suspect 唯一罚则对象。"""

    def test_none_detection_all_pending(self):
        # preview_detected=None 仍合法(登记/测试形态)= 全行 pending
        res = shops.compare_merge_preview({0: True, 1: False}, None)
        assert [r.verdict for r in res.rows] == ['pending', 'pending']
        assert res.suspect_slots == []

    def test_our_true_detected_false_is_suspect(self):
        # 我方算可合成而游戏无星 = 我方合成计算嫌疑(单向罚则唯一对象)
        res = shops.compare_merge_preview({2: True}, {2: False})
        assert res.suspect_slots == [2]

    def test_detected_true_our_false_is_game_extra(self):
        # 反向 = 我方漏算:单向框架内不判罚,计数留证
        res = shops.compare_merge_preview({3: False}, {3: True})
        assert res.rows[0].verdict == 'game_extra'
        assert res.suspect_slots == []

    def test_match(self):
        res = shops.compare_merge_preview({4: True}, {4: True})
        assert res.rows[0].verdict == 'match'


class TestRefreshExpect:
    """刷新期望增量:金 −现读费 + 旧五张回池账;费用不写死(W554)。"""

    def test_normal_expect(self):
        exp = shops.refresh_expect(10, [('阿格莱雅', 1), ('阿格莱雅', 1), ('银狼', 2)], 2)
        assert exp.gold_after == 8
        assert exp.insufficient is False
        assert exp.pool_returned == {'阿格莱雅': 2, '银狼': 1}
        assert exp.new_slots == 5

    def test_insufficient_still_full_expect(self):
        # 金不足:期望增量仍完整给出(可为负),是否执行由调用方判
        exp = shops.refresh_expect(1, [], 2)
        assert exp.gold_after == -1
        assert exp.insufficient is True

    def test_empty_old_cards(self):
        exp = shops.refresh_expect(10, [], 2)
        assert exp.pool_returned == {}


# ===== 羁绊面板解析与对账(cw_faction_obs;计算侧主源裁决口径) =====

def _tok(text, x1, y1, x2, y2):
    return (text, x1, y1, x2, y2)


class TestParsePanelTokens:
    """面板 token 真值表:名称锚 + 徽章配对;灰梯滤除/越域拒信/截断形态。"""

    def test_normal_entry_paired(self):
        reading = facobs.parse_panel_tokens(
            [_tok('昼之半神', 100, 100, 180, 120)],
            [_tok('3', 80, 135, 100, 155)])   # bcy=145, dy=35 ∈ 配对窗
        assert reading.entries == [('昼之半神', 3)]
        assert reading.truncated is False

    def test_ladder_token_filtered(self):
        # 灰梯('3/5/7/10')含斜杠被滤:不占名称锚,也不进任何计数
        reading = facobs.parse_panel_tokens(
            [_tok('3/5/7/10', 100, 100, 180, 120)], [])
        assert reading.entries == []
        assert reading.unmatched == []
        assert reading.unreadable == []
        assert reading.truncated is False

    def test_badge_out_of_domain_becomes_unreadable(self):
        # 徽章数字 >12 = OCR 误读(前后台总部署上界 13 内)→ 条目进 unreadable
        reading = facobs.parse_panel_tokens(
            [_tok('昼之半神', 100, 100, 180, 120)],
            [_tok('30', 80, 135, 100, 155)])
        assert reading.entries == []
        assert reading.unreadable == ['昼之半神']

    def test_unmatched_name_counted(self):
        # 对不上注册表的残名/艺术字形变:存原文不评口径
        reading = facobs.parse_panel_tokens(
            [_tok('某某残名', 100, 100, 180, 120)],
            [_tok('3', 80, 135, 100, 155)])
        assert reading.unmatched == ['某某残名']

    def test_last_anchor_without_badge_is_truncation(self):
        # 最后一条无徽章 = 视口截断形态(底部还有条目被面板裁掉)
        reading = facobs.parse_panel_tokens(
            [_tok('昼之半神', 100, 100, 180, 120)], [])
        assert reading.truncated is True
        assert reading.unreadable == ['昼之半神']


class TestCompareFactions:
    """逐名三态对账:match/mismatch/display_unreadable/computed_missing + 截断嫌疑。"""

    def test_match(self):
        res = facobs.compare_factions({'昼之半神': 2}, [('昼之半神', 2)])
        assert res.rows[0].verdict == 'match'
        assert res.mismatch_count == 0

    def test_mismatch_counted(self):
        res = facobs.compare_factions({'昼之半神': 2}, [('昼之半神', 3)])
        assert res.rows[0].verdict == 'mismatch'
        assert res.mismatch_count == 1

    def test_computed_missing_is_explicit_fourth_state(self):
        # displayed 有 computed 无 = 计算侧漏贡献/名称配错:独立判词命名
        # (mismatch_count 只数 mismatch,computed_missing 单独归因不混计)
        res = facobs.compare_factions({}, [('仙舟', 1)])
        assert res.rows[0].verdict == 'computed_missing'
        assert res.mismatch_count == 0

    def test_truncation_suspects_counted_not_judged(self):
        # computed 有而显示没有:列表滚动截断是常态,单独计数不判错
        res = facobs.compare_factions({'昼之半神': 2, '仙舟': 1}, [('昼之半神', 2)])
        assert res.truncation_suspects == ['仙舟']

    def test_unreadable_skipped(self):
        res = facobs.compare_factions({'昼之半神': 2}, [], unreadable=['昼之半神'])
        assert res.ocr_skipped == ['昼之半神']
        assert res.rows == []


class TestReportFactionReconcile:
    """mismatch 行落缺陷台账(纯转发);match/missing 行不落。"""

    def test_only_mismatch_rows_reported(self, monkeypatch):
        reported = []
        monkeypatch.setattr(
            'sr_od.application.currency_war.kernel.cw_telemetry_exit.record_defect',
            lambda **kw: reported.append(kw['note']))
        res = facobs.compare_factions(
            {'昼之半神': 2, '仙舟': 3}, [('昼之半神', 2), ('仙舟', 1)])
        n = facobs.report_faction_reconcile(res)
        assert n == 1
        assert reported == ['faction=仙舟']
