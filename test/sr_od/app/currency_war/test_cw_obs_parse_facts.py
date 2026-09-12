"""obs 识别层·解析真值对照(重建合同 ①)。

每个纯解析函数「输入样本 → 期望输出」的固定对照:输入用实机 OCR 实测样本
(各源函数 docstring 记录的真帧 token 形态),覆盖 OCR 误识别修复规则与带符号
语义。零桩、零图片、零框架对象——识别层「错了全场皆错」的唯一转换层。
组织蓝图 = obs 先删后重建规格 §2①(.debug/temp/cw_obs_rebuild/,易失产物;
语义以本文件各组 docstring 为准)。
"""
import types

from sr_od.application.currency_war.kernel.cw_board_state import (
    FINAL_ABNORMAL,
    FINAL_LOSS,
    FINAL_STOPPED,
    FINAL_WIN,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.obs import cw_briefing_obs
from sr_od.application.currency_war.obs import cw_observation as cobs
from sr_od.application.currency_war.obs import cw_settlement_obs as settle


def _ocr_item(data: str, x: int, y: int, w: int = 60, h: int = 20):
    """构造带坐标 OCR 条目(parse_settlement_damage / damage_breakdown 的 items 输入形态)。"""
    return types.SimpleNamespace(data=data, x=x, y=y, width=w, height=h)


# ===== 结算屏解析(cw_settlement_obs;样本出处 = 各函数 docstring 实跑 token 形态) =====

class TestSettlementNodeType:
    """结算屏头部节点类型:邻位窗口 + 精确/白名单前缀匹配(ADR-0239)。"""

    def test_reward_plain_tokens(self):
        assert settle.parse_settlement_node_type(
            ['挑战成功', '奖励', 'Lv.3', '数据统计']) == '奖励'

    def test_battle_glued_noise_token(self):
        # 实跑:battle 局 '1-N' 带 OCR 噪声,类型词在后续 token
        assert settle.parse_settlement_node_type(
            ['挑战成功', '1-3X点', '战斗', '火热连胜×1']) == '普通战斗'

    def test_glued_header_token(self):
        # OCR 把头部与类型词粘成单 token → hdr 自身入窗口
        assert settle.parse_settlement_node_type(['挑战成功战斗']) == '普通战斗'

    def test_decoration_prefix_allowed(self):
        # emoji/装饰字符前缀在白名单('👩首领')
        assert settle.parse_settlement_node_type(['挑战结束', '👩首领']) == 'boss'

    def test_modifier_prefix_rejected(self):
        # 修饰词前缀('基础奖励')不匹配 → 类型不可判,不是误中'奖励'
        assert settle.parse_settlement_node_type(
            ['挑战结束', '基础奖励', '数据统计']) is None

    def test_no_header(self):
        assert settle.parse_settlement_node_type(['数据统计', '战斗']) is None


class TestSettlementRound:
    """结算屏头部「X-Y」→ (plane, round):值域嵌入正则 + 数字粘连拒信(W28 缺陷①修)。"""

    def test_plain(self):
        assert settle.parse_settlement_round(
            ['挑战结束', '1-6', '战斗']) == (1, 6)

    def test_glued_leading_digit_rejected(self):
        # '11-6':'1-6' 子串有前导数字,lookbehind 拒 → 不误取
        assert settle.parse_settlement_round(['挑战结束', '11-6']) is None

    def test_trailing_digit_rejected(self):
        # '2-12':round 位两位数,lookahead 拒
        assert settle.parse_settlement_round(['挑战结束', '2-12']) is None

    def test_out_of_domain_rejected(self):
        # plane∈[1,3] hard-coded;4 = OCR 假阳
        assert settle.parse_settlement_round(['挑战结束', '4-6']) is None

    def test_beyond_window_not_matched(self):
        # 头部 5 token 窗口外不找(防误中远处数字对)
        assert settle.parse_settlement_round(
            ['挑战结束', '战斗', '火热连胜×1', '数据统计', '继续挑战', '3-9']) is None

    def test_no_header(self):
        assert settle.parse_settlement_round(['战斗', '1-6']) is None


class TestSettlementHp:
    """「小队生命值<N>」→ hp:紧邻取数 + garble 修复 + 值域拒信(P1.5)。"""

    def test_ocr_tail_noise_fixed(self):
        # 实跑形态:OCR 尾巴 'i'(71i)→ 紧邻数字 71
        assert settle.parse_settlement_hp(
            ['挑战结束', '战斗', '小队生命值71i', '数据统计']) == 71

    def test_garbled_keyword_fixed(self):
        # OCR 偶丢「生」:命值 形态同匹配(2026-08-07 hp=0 根因)
        assert settle.parse_settlement_hp(['队命值55']) == 55

    def test_investment_description_not_matched(self):
        # 投资策略描述偶同屏:「生命值」后无紧邻数字 → 不取 20/5
        assert settle.parse_settlement_hp(
            ['每损失20点小队生命值获得5']) is None

    def test_out_of_bounds_rejected(self):
        # HP_MAX=200(cw_obs_core):读成 500 = OCR 假阳,丢弃不冒认
        assert settle.parse_settlement_hp(['小队生命值500']) is None

    def test_no_anchor(self):
        assert settle.parse_settlement_hp(['挑战成功', '数据统计']) is None


class TestSettlementAssets:
    """结算页金币存量/等级/经验:存量=当前金币,经验需等级先命中(W971)。"""

    def test_full_read(self):
        out = settle.parse_settlement_assets(['存量:320', 'Lv.5', '4/20'])
        assert out == {'gold': 320, 'level': 5, 'xp_cur': 4, 'xp_next': 20}

    def test_xp_requires_level_first(self):
        # 失败结算页无等级 → 经验即使读到也不取(宁缺勿造)
        out = settle.parse_settlement_assets(['4/20'])
        assert out == {'gold': None, 'level': None, 'xp_cur': None, 'xp_next': None}

    def test_all_missing(self):
        out = settle.parse_settlement_assets(['挑战成功'])
        assert out == {'gold': None, 'level': None, 'xp_cur': None, 'xp_next': None}


class TestStreak:
    """「连胜×N/连败×N」带符号;失读 None ≠ 真 0(迁移批次二 §8.8)。"""

    def test_win_positive(self):
        assert settle.parse_streak(['连胜×3']) == 3

    def test_lose_negative(self):
        assert settle.parse_streak(['连败×2']) == -2

    def test_zero_is_real_reading(self):
        # '连胜×0' = 无连胜(方向真值),不是失读
        assert settle.parse_streak(['连胜×0']) == 0

    def test_x_sign_garble(self):
        # OCR 偶把 × 读成 x/X/*:前缀含「连胜」即可
        assert settle.parse_streak(['连胜x2']) == 2

    def test_miss_is_none(self):
        # 失读返 0 会把「未读到」冒充「真 0」并假复位连胜链 → None
        assert settle.parse_streak(['挑战结束', '战斗']) is None


class TestSettlementProgress:
    """「挑战进度 ±N」三形态:同 token 粘连/后随分离/前置分离;裸数字=累计值不取。"""

    def test_glued_positive(self):
        assert settle.parse_settlement_progress(['挑战进度+2']) == 2

    def test_glued_negative(self):
        assert settle.parse_settlement_progress(['挑战进度-22']) == -22

    def test_separate_following_token(self):
        assert settle.parse_settlement_progress(['挑战进度', '+2']) == 2

    def test_preceding_negative_token(self):
        # 战败屏数字前置形态(M41 实锤 '-22' '挑战进度')
        assert settle.parse_settlement_progress(['-22', '挑战进度']) == -22

    def test_bare_number_is_cumulative_not_delta(self):
        # 「挑战成功」屏的无符号累计值形态:不取,防 -22 被记成 +46
        assert settle.parse_settlement_progress(['挑战进度', '46']) is None

    def test_missing(self):
        assert settle.parse_settlement_progress(['挑战结束']) is None


class TestSettlementWon:
    """胜负真值:成功→True,失败→False,负进度→False,无法判定→None。"""

    def test_success_token(self):
        assert settle.parse_settlement_won(['挑战成功', '战斗']) is True

    def test_defeat_token(self):
        assert settle.parse_settlement_won(['挑战失败']) is False

    def test_negative_progress_means_loss(self):
        # 输轮形态 = 「挑战结束」+ 负进度(无「挑战成功」)
        assert settle.parse_settlement_won(
            ['挑战结束', '挑战进度-22']) is False

    def test_positive_progress_means_win(self):
        assert settle.parse_settlement_won(
            ['挑战结束', '挑战进度', '+2']) is True

    def test_undeterminable(self):
        assert settle.parse_settlement_won(['挑战结束', '战斗']) is None


class TestSettlementDamage:
    """「数据统计」右列「N万」求和;裸数字/列外 token 天然排除(W40)。"""

    def test_sum_of_right_column(self):
        items = [_ocr_item('396.3万', 1200, 600), _ocr_item('137.0万', 1210, 650)]
        assert settle.parse_settlement_damage(items) == 3963000 + 1370000

    def test_left_column_noise_excluded(self):
        # 同形 token 在左列(金币明细区)不进求和
        items = [_ocr_item('396.3万', 300, 600)]
        assert settle.parse_settlement_damage(items) is None

    def test_bare_number_without_wan_excluded(self):
        # 金币明细裸数字 10/5/4 无「万」后缀
        items = [_ocr_item('10', 1200, 600), _ocr_item('396.3万', 1200, 650)]
        assert settle.parse_settlement_damage(items) == 3963000

    def test_empty_is_none(self):
        assert settle.parse_settlement_damage([]) is None


class TestProgressSign:
    """页 1 进度符号三态('pos'/'neg'/None);boss 胜局页 1 判别消费(DD-006)。"""

    def test_pos(self):
        assert settle.settle_page1_progress_sign(['挑战进度', '+2']) == 'pos'

    def test_neg(self):
        assert settle.settle_page1_progress_sign(['挑战进度-22']) == 'neg'

    def test_miss_is_none(self):
        # None = OCR 漏读(两种形态页都可能),不是败局真值
        assert settle.settle_page1_progress_sign(['挑战结束']) is None

    def test_boss_win_page1(self):
        # boss 胜局页 1 与战败页同构,判别 = 进度正增量
        assert settle.is_boss_win_settle_page1(['挑战结束', '挑战进度', '+2']) is True

    def test_boss_lose_page1(self):
        assert settle.is_boss_win_settle_page1(['挑战结束', '挑战进度-22']) is False

    def test_boss_miss_falls_false(self):
        # OCR 漏 '+' → 判 False(回旧行为,不劣化)
        assert settle.is_boss_win_settle_page1(['挑战结束']) is False


class TestSettleDamageBreakdown:
    """掉血 tooltip 三行分量:标签定位 + 粘连/同行右侧取值 + 值域先验拒信。"""

    def test_glued_base_damage(self):
        out = settle.parse_settle_damage_breakdown(
            [_ocr_item('基础伤害-10', 1240, 500)])
        assert out['visible'] is True
        assert out['damage_base'] == -10

    def test_same_row_right_token(self):
        # 行判据 y 中心差 ≤20px、x 在标签右侧
        out = settle.parse_settle_damage_breakdown([
            _ocr_item('未完成进度伤害', 1240, 540, 100),
            _ocr_item('-5', 1380, 540, 30),
        ])
        assert out['damage_unfinished_progress'] == -5

    def test_broken_label_double_anchor(self):
        # 「未完成进度伤害」允许 OCR 断词:按「未完成」锚命中
        out = settle.parse_settle_damage_breakdown([
            _ocr_item('未完成', 1240, 540, 60),
            _ocr_item('-5', 1380, 540, 30),
        ])
        assert out['damage_unfinished_progress'] == -5

    def test_heal_row_allows_positive(self):
        out = settle.parse_settle_damage_breakdown([_ocr_item('长线作战+2', 1240, 560)])
        assert out['heal_longline'] == 2

    def test_unsigned_positive_rejected_for_damage_rows(self):
        # 伤害行恒 ≤0:无符号正值 = OCR 丢负号 → 拒信 None
        out = settle.parse_settle_damage_breakdown([
            _ocr_item('基础伤害', 1240, 500),
            _ocr_item('10', 1380, 500, 30),
        ])
        assert out['damage_base'] is None

    def test_bare_zero_is_legal(self):
        # 进度打满游戏可显 0
        out = settle.parse_settle_damage_breakdown([
            _ocr_item('基础伤害', 1240, 500),
            _ocr_item('0', 1380, 500, 30),
        ])
        assert out['damage_base'] == 0

    def test_unicode_minus_normalized(self):
        # OCR 符号形变 −(U+2212)/— 归一为 '-'
        out = settle.parse_settle_damage_breakdown([
            _ocr_item('基础伤害', 1240, 500),
            _ocr_item('−10', 1380, 500, 30),
        ])
        assert out['damage_base'] == -10

    def test_invisible_panel(self):
        out = settle.parse_settle_damage_breakdown([])
        assert out == {'visible': False, 'damage_base': None,
                       'damage_unfinished_progress': None, 'heal_longline': None}


class TestSettleHpAnchor:
    """结算页 HP 锚(常驻页判态门):HP 行 ∨ 继续挑战按钮。"""

    def test_hp_row(self):
        assert settle.parse_settle_hp_anchor(['小队生命值71']) is True

    def test_continue_button(self):
        assert settle.parse_settle_hp_anchor(['继续挑战']) is True

    def test_garbled_keyword(self):
        assert settle.parse_settle_hp_anchor(['队命值55']) is True

    def test_absent(self):
        assert settle.parse_settle_hp_anchor(['点击空白加速']) is False


# ===== 简报屏解析(cw_briefing_obs) =====

class TestEnemyDifficulty:
    """「敌人难度N」→ int;>300 越界拒信(state 回退 None)。"""

    def test_plain(self):
        assert cw_briefing_obs.parse_enemy_difficulty(['敌人难度108']) == 108

    def test_space_tolerant(self):
        assert cw_briefing_obs.parse_enemy_difficulty(['敌人难度 45']) == 45

    def test_out_of_bounds(self):
        assert cw_briefing_obs.parse_enemy_difficulty(['敌人难度500']) is None

    def test_no_match(self):
        assert cw_briefing_obs.parse_enemy_difficulty(['财富造物主']) is None


class TestBossNameLcsClean:
    """boss 读数 LCS 归一:规范名原样/简称形变归一/无关透传(防误配守卫)。"""

    def test_canonical_passthrough(self):
        assert cw_briefing_obs.clean_boss_names_by_lcs(['火线动力机甲']) == ['火线动力机甲']

    def test_short_name_normalized(self):
        # 简称 → 规范名(BOSS_MECHANICS 注册表;LCS 占规范名 ≥0.5)
        assert cw_briefing_obs.clean_boss_names_by_lcs(['银甲武装']) == ['银甲武装公司']

    def test_unrelated_passthrough(self):
        # 归一失败原名透传:错归一比不归一危害大(按序真值进 boss_fit)
        assert cw_briefing_obs.clean_boss_names_by_lcs(['阿巴阿巴']) == ['阿巴阿巴']


class TestBriefingReconcilePairs:
    """简报读数 vs 位面详情真值逐位面配对:True/False/None(不可判)三态。"""

    def test_match_true(self):
        pairs = cw_briefing_obs.briefing_reconcile_pairs(
            ['银甲武装'], ['银甲武装公司', None, None])
        assert pairs[0] == {'plane': 1, 'briefing': '银甲武装公司',
                            'truth': '银甲武装公司', 'match': True}

    def test_truth_none_is_undeterminable(self):
        pairs = cw_briefing_obs.briefing_reconcile_pairs(
            ['银甲武装公司'], [None, None, None])
        assert pairs[0]['match'] is None

    def test_briefing_none_all_undeterminable(self):
        pairs = cw_briefing_obs.briefing_reconcile_pairs(None, ['银甲武装公司'])
        assert all(p['match'] is None for p in pairs)


# ===== 备战屏纯函数(cw_observation) =====

class TestGateNodeType:
    """无锚定 node_type 语义门:boss 轮次门 + 标签位置门(r80 审计 P0)。"""

    def test_boss_before_min_round_rejected(self):
        # boss 标签也会出现在「即将到来」的 boss 节点下方(2-7 实证)→ 非当前
        assert cobs.gate_node_type('boss', 5) is None

    def test_boss_at_min_round_passes(self):
        # boss 轮次下限 = 9(实证值;调整此值时先重推 2-7 实证样本)
        assert cobs.gate_node_type('boss', 9) == 'boss'

    def test_non_boss_early_round_passes(self):
        assert cobs.gate_node_type('奖励', 3) == '奖励'

    def test_label_far_from_current_slot_rejected(self):
        # 标签 x 与当前槽 cx 错位(张冠李戴)→ None(2-7 实证 x1341 vs cx≈900)
        assert cobs.gate_node_type('奖励', 3, label_x=1341, current_cx=900) is None

    def test_label_near_current_slot_passes(self):
        assert cobs.gate_node_type('奖励', 3, label_x=950, current_cx=900) == '奖励'

    def test_none_input(self):
        assert cobs.gate_node_type(None, 5) is None


class TestNodeVoteVerdict:
    """三票裁决:无反对 ok / 单票异议 noise(不落账) / ≥2 独立票一致反对 defect。"""

    def test_all_agree(self):
        assert cobs.node_vote_verdict(
            '战斗', {'a': '战斗', 'b': '战斗', 'c': '战斗'}) == 'ok'

    def test_single_dissent_is_noise(self):
        # 单票反对(高亮 Hu 敏感/ROI 漏读)不落账,防逐帧刷屏
        assert cobs.node_vote_verdict(
            '战斗', {'a': None, 'b': '战斗', 'c': '奖励'}) == 'noise'

    def test_two_consistent_dissent_is_defect(self):
        assert cobs.node_vote_verdict(
            '战斗', {'a': '奖励', 'b': '奖励', 'c': '战斗'}) == 'defect'

    def test_abstentions_do_not_count(self):
        # 2 弃权 + 1 反对:非弃权票不足 2 → noise
        assert cobs.node_vote_verdict(
            '战斗', {'a': None, 'b': None, 'c': '奖励'}) == 'noise'


class TestParseSelectedDifficulty:
    """难度确认屏职级:全匹配 A\\d+(-\\d+)?;其余文字 → ''(回退默认阈值)。"""

    def test_plain(self):
        assert cobs.parse_selected_difficulty(['A8']) == 'A8'

    def test_with_stage(self):
        assert cobs.parse_selected_difficulty(['A5-3']) == 'A5-3'

    def test_noise_words_rejected(self):
        # 同屏文字「财富造物主/当前职级难度效果」非职级
        assert cobs.parse_selected_difficulty(['财富造物主', '当前职级难度效果']) == ''

    def test_bare_number_rejected(self):
        assert cobs.parse_selected_difficulty(['8']) == ''


class TestBoardFromTracked:
    """tracked 身份 → 阵营计数(以算为准):全集口径/未知身份 bail。"""

    def test_empty_tracked_is_none(self):
        assert cobs.board_from_tracked([]) is None

    def test_known_char_contributes_all_bonds(self):
        # 阿格莱雅(cw_chars 实测):L1 全集 = factions「昼之半神」+「能量」
        bc = BenchChar(slot=1, char_id='阿格莱雅')
        assert cobs.board_from_tracked([bc]) == {'昼之半神': 1, '能量': 1}

    def test_none_slots_filtered(self):
        # ADR-0392 槽位表滤 None(None 槽 = 未占用)
        bc = BenchChar(slot=2, char_id='阿格莱雅')
        assert cobs.board_from_tracked([None, bc]) == {'昼之半神': 1, '能量': 1}

    def test_unknown_identity_bails(self):
        # 未知身份('?')= 混合态:半算比漏算更毒 → 整体退 OCR 兜底
        bc = BenchChar(slot=1, char_id='?')
        assert cobs.board_from_tracked([bc]) is None


class TestResolveCostStar:
    """费用徽章 + roster 原费 → (实付价, 星级, 来源):倍数 ∈ {1,3,9}(merge_mechanics §2.6)。"""

    def test_missing_badge_falls_back(self):
        cost, star, src = cobs.resolve_cost_star(None, 2)
        assert (cost, star, src) == (2, 1, cobs.COST_SOURCE_ROSTER_FALLBACK)

    def test_invalid_roster_falls_back(self):
        cost, star, src = cobs.resolve_cost_star(6, 0)
        assert src == cobs.COST_SOURCE_ROSTER_FALLBACK

    def test_star1(self):
        assert cobs.resolve_cost_star(2, 2) == (2, 1, 'badge')

    def test_star2(self):
        assert cobs.resolve_cost_star(6, 2) == (6, 2, 'badge')

    def test_star3(self):
        assert cobs.resolve_cost_star(18, 2) == (18, 3, 'badge')

    def test_non_multiple_falls_back(self):
        # 非整数倍 = 疑误读 → roster 兜底(按原费 1★),调用方留证
        assert cobs.resolve_cost_star(5, 2) == (2, 1, cobs.COST_SOURCE_ROSTER_FALLBACK)

    def test_beyond_star_domain_falls_back(self):
        # ×27 = 4★ 超 CW 星级域 → 兜底
        assert cobs.resolve_cost_star(54, 2) == (2, 1, cobs.COST_SOURCE_ROSTER_FALLBACK)


class TestRunsResultMap:
    """runs result 词表 → 局终类型:同名直映,非完结值域(含空串)= abnormal。"""

    def test_win(self):
        assert cobs.runs_result_to_final_type('win') is FINAL_WIN

    def test_loss(self):
        assert cobs.runs_result_to_final_type('loss') is FINAL_LOSS

    def test_stopped(self):
        assert cobs.runs_result_to_final_type('stopped') is FINAL_STOPPED

    def test_abandoned_is_abnormal(self):
        assert cobs.runs_result_to_final_type('abandoned') is FINAL_ABNORMAL

    def test_empty_is_abnormal(self):
        assert cobs.runs_result_to_final_type('') is FINAL_ABNORMAL


class TestResolveFinalType:
    """在线局终判定:停止 > 失败 > 通关(精确 plane==3,禁 >=)> 未开局 None > abnormal。"""

    def test_stop_beats_all(self):
        assert cobs.resolve_final_type(
            stop_requested=True, saw_defeat=True, plane_reached=1) is FINAL_STOPPED

    def test_defeat_loses(self):
        assert cobs.resolve_final_type(
            stop_requested=False, saw_defeat=True, plane_reached=2) is FINAL_LOSS

    def test_plane3_is_win(self):
        assert cobs.resolve_final_type(
            stop_requested=False, saw_defeat=False, plane_reached=3) is FINAL_WIN

    def test_beyond_plane3_not_win(self):
        # OCR 难度泄漏曾读出 plane=8:通关只认精确值 3,禁 >=(ADR-0392 时代实证)
        assert cobs.resolve_final_type(
            stop_requested=False, saw_defeat=False, plane_reached=4) is FINAL_ABNORMAL

    def test_no_rounds_played_is_none(self):
        # 开局失败形态:非终局,禁拼假终局行(调用方跳过收口)
        assert cobs.resolve_final_type(
            stop_requested=False, saw_defeat=False,
            plane_reached=1, rounds_played=False) is None

    def test_default_abnormal(self):
        assert cobs.resolve_final_type(
            stop_requested=False, saw_defeat=False, plane_reached=1) is FINAL_ABNORMAL
