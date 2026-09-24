"""投资策略画面策略层迁移 3.1 单测(纯新增阶段;判据 = landing.md §3.1 ①-⑩)。

设计依据 = docs/develop/sr_od/application/currency_war/changes/
2026-09-23-invest-strategy-screen-migration/design.md(下称 design §)
与 landing.md §3.1 完成判据。3.1 期策略层新文件与 kernel 旧机并存,
flow 仍走 kernel decide_event(零调用);3.2 接线后本文件锁面随切换验证。

判据映射:
- ① 现金分(strategy_economy 通道公式:面值/分期金 R−1 截断/XP 双通道/
  固定息/boss 位面末槽几何/待建模塌 0/位置缺失退化);
- ② 方向分(触线集 comp 空间像:锁线并集/未锁线 max/线排除像/降格帧/
  角色绑定窄口径);
- ③ 赠卡分(STRATEGY_GRANTS + grant_gift_value:即时最高档/条件降档/
  全员集外/顾问折减/底册计数与构建校验);
- ④ 结构分区(禁选/自拆辖域护栏/血本位三态/定义型分区/空候选退化);
- ⑤ 平分裁决键(品质序→econ 有无→槽序;无 canonical 殿后;env 名防御);
- ⑥ 构建期校验(字段三分/卡级待建模断言集/立场表孤儿);
- ⑦ 刷新判据(帧级门与槽级顶级两谓词分立、E-豁免、F2 守卫、对齐保护);
- ⑧ env 批件零漂移 = 既有 test_cw_invest_env_strategy.py 全绿(不重复);
- ⑨ decide_pick 纯选卡口(同评分基线、永不建议刷);
- ⑩ LCS 兜底命中即告警(观测锚)。

校验「import 即炸」的接线面:直接调校验入口 + monkeypatch 表断言抛错,
不用 reload/源码扫描(沿 test_cw_invest_env_strategy.py 同款口径)。

测试纪律:零真实副作用;断言锁设计语义,数值期望 = 注册表真实数据
(提交进仓)现算锚定,docstring 记出处。
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    _char_gift_tier,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_GRANTS,
    GiftGrant,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    invest_strategy,
    strategy_economy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    grant_gift_value,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.invest_strategy import (
    InvestStrategyDecision,
    StanceRow,
    StrategyRefreshSuggestion,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw-invest-strategy-test',
                      mode='synthesized')

#: 零转向配置(decide 不要求 config 具体类型)
_EMPTY_CONFIG = SimpleNamespace(strategy_priority=[], strategy_forbid=[])


def _fresh_gs() -> GameState:
    """独立容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


def _gs_at(plane: int, round_num: int,
           plane_lengths: list[int] | None = None) -> GameState:
    """写在帧节点位置(可选写已揭晓位面长度表 = schedule 真值)。"""
    gs = _fresh_gs()
    if plane_lengths is not None:
        gs.node_books.plane_lengths_seen = list(plane_lengths)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind=''),
               evidence='test', sig=_SIG_OBS)
    return gs


def _decide_pick(options: list[str], gs: GameState,
                 locked_comp: str = '', demoted_endgame: bool = False,
                 evicted: frozenset[str] = frozenset(),
                 config: SimpleNamespace | None = None,
                 ) -> InvestStrategyDecision:
    out = invest_strategy.decide_pick(
        options, gs, locked_comp, demoted_endgame, evicted,
        config or _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)
    return out


# ==================== ① 现金分(design §2.3)====================

#: 开局帧剩余节点数(node 缺失 → (1,1) 退化 + 未揭晓回退 (9,9,9)):
#: R = 9 + 9 + 9 = 27(strategy_economy 位置缺失退化断言的共用口径)
_R_OPENING = 27


def test_cash_instant_gold_face_value():
    """instant_gold 面值直计:藏一手 = 80(注册表全表最大一次性金;
    旧 PICK_VALUE 65 系拍值,新标尺按金等价)。"""
    assert strategy_economy_value('藏一手', _fresh_gs()) == (80.0, True)


def test_cash_gold_next_nodes_r_minus_1_truncation():
    """分期金 =「现在」腿 + count 腿按 R−1 截断(design §2.3;
    「接下来」不含当前节点)。开局帧 R=27:长期主义 = 7×(1+min(3,26)) = 28
    (勿读 instant_gold——长期主义该字段 = 0,误读即漏现在腿);
    终局帧 P3R9(R=1):count 腿截断为 0 → 仅「现在」腿 7。"""
    assert strategy_economy_value('长期主义', _fresh_gs()) == (28.0, True)
    assert strategy_economy_value('长期主义+', _fresh_gs()) == (36.0, True)
    assert strategy_economy_value('长期主义', _gs_at(3, 9)) == (7.0, True)


def test_cash_per_node_interest_xp_channels():
    """per-node 流/固定息/XP 双通道(值 = 注册表【注】× R 查表):
    定期福利 = 4 + 2×27;狸财经狸息腿 = 2×27(活计分腿,取款/存款腿
    待建模不关门——design 申报 7);伟大征服 xp_instant = 12;
    买断制 = 15 + 4×27(xp_per_node 流);XP_GOLD_RATE = 1.0。"""
    assert strategy_economy_value('定期福利', _fresh_gs()) == (58.0, True)
    assert strategy_economy_value('狸财经狸', _fresh_gs()) == (54.0, True)
    assert strategy_economy_value('伟大征服', _fresh_gs()) == (12.0, True)
    assert strategy_economy_value('买断制', _fresh_gs()) == (123.0, True)


def test_cash_schedule_truth_lookup():
    """剩余口径按 schedule_of 位面实际长度查表(P2=7 进表自适应;
    单一源 = cw_plane_table.r_global,经 statefn/horizon 门面):
    P2R4 长度表 (9,7,9) → R = 本位面剩余 4 + P3 9 = 13,
    定期福利 = 4 + 2×13 = 30。"""
    assert strategy_economy_value('定期福利', _gs_at(2, 4, [9, 7, 9])) \
        == (30.0, True)


def test_cash_boss_channel_plane_end_geometry():
    """boss 通道 = plane_end_slots 位面末槽几何(每位面恰一 boss):
    P2R4 长度表 (9,7,9) → 当前全局节点 13,末槽 {8,15,23} → 剩余 2 →
    特战资金 = 7×2 = 14(含当前位面口径,偏差申报见模块 docstring)。"""
    assert strategy_economy_value('特战资金', _gs_at(2, 4, [9, 7, 9])) \
        == (14.0, True)
    assert strategy_economy_value('特战资金+', _gs_at(2, 4, [9, 7, 9])) \
        == (22.0, True)


def test_cash_missing_node_degrades_to_opening_frame():
    """位置缺失帧退化 (1,1)(沿 env 屏先例;landing ① 分支断言):
    node 未写的裸帧与显式 (1,1) 帧逐位同值。"""
    bare = strategy_economy_value('长期主义', _fresh_gs())
    explicit = strategy_economy_value('长期主义', _gs_at(1, 1))
    assert bare == explicit == (28.0, True)


def test_cash_pending_modeling_card_failclosed():
    """纯待建模腿卡 fail-closed = 0:固定理财(唯一挂值字段
    free_refresh_burst 系刷新族待建模)、孪生素数(全默认)。"""
    assert strategy_economy_value('固定理财', _fresh_gs()) == (0.0, False)
    assert strategy_economy_value('孪生素数', _fresh_gs()) == (0.0, False)


def test_cash_unregistered_name_failclosed():
    """未入册卡名 → (0, False),不炸(消费端按无现金处理)。"""
    assert strategy_economy_value('不存在的卡名', _fresh_gs()) == (0.0, False)


# ==================== ② 方向分(design §2.4)====================
# 真值锚(注册表直调):列车同行星徽绑定 (列车同行阵营, 丹恒·饮月);
# 列车同行阵营线成员 = {列车同行(S), 龙丹战技点(A)};丹恒·饮月 core 仅在
# 龙丹战技点。

def test_direction_unlocked_takes_touched_max():
    """未锁线帧:触线集全体取 max 线价值 → 列车同行星徽 = 100(S 线)。"""
    out = _decide_pick(['列车同行星徽', '嘴硬', '二极管'], _fresh_gs())
    assert out.components[1] == 100.0


def test_direction_locked_frame_uses_locked_line_union():
    """锁线帧:触线 ∩ 锁线阵营线成员并集(comp 空间像,design §2.4)。
    锁线 = 龙丹战技点(A):其阵营线 = {列车同行, 龙丹战技点} → 方向仍
    100(锁线阵营族展开含 S 成员);锁线不含卡绑定阵营的对照见
    test_direction_char_binding_narrow_hit。"""
    out = _decide_pick(['列车同行星徽', '嘴硬', '二极管'], _fresh_gs(),
                       locked_comp='龙丹战技点')
    assert out.components[1] == 100.0


def test_direction_evicted_line_death_drops_to_zero():
    """线排除像 = 阵营线全体成员 comp ∈ evicted ⇔ 线排除(design §2.9-2):
    evicted = 全体列车同行线成员 → 阵营腿整线退场,角色腿唯一命中
    (龙丹战技点)同被逐 → 方向 0(evicted 收窄后线退场)。"""
    dead = frozenset(c.name for c in COMP_LIBRARY
                     if '列车同行' in c.factions)
    out = _decide_pick(['列车同行星徽', '嘴硬', '二极管'], _fresh_gs(),
                       evicted=dead)
    assert out.components[1] == 0.0


def test_direction_demoted_frame_uses_unlocked_scale():
    """降格帧按未锁线口径(design §2.4 口径 3):demoted=True 忽略锁线。"""
    out = _decide_pick(['列车同行星徽', '嘴硬', '二极管'], _fresh_gs(),
                       locked_comp='嘴硬非阵容', demoted_endgame=True)
    assert out.components[1] == 100.0


def test_direction_char_binding_narrow_hit():
    """角色绑定窄口径(core_chars 命中,design §2.4-1):本姑娘就是罗刹
    绑定 (∅,{三月七,罗刹}),三月七 core ∈ 列车同行(S) → 触线 100。"""
    out = _decide_pick(['本姑娘就是罗刹', '嘴硬', '二极管'], _fresh_gs())
    assert out.components[1] == 100.0


# ==================== ③ 赠卡分(design §2.5)====================

def test_grant_immediate_highest_tier():
    """即时集取最高档:借力打力(黑塔 core + 缇宝 core)→ core 50。"""
    assert grant_gift_value(STRATEGY_GRANTS['借力打力'], frozenset()) == 50.0


def test_grant_conditional_downgraded():
    """条件集降一档:迷之旅人双腿均条件(黄泉 core → shared 20)。"""
    assert grant_gift_value(STRATEGY_GRANTS['迷之旅人'], frozenset()) == 20.0


def test_grant_all_off_universe_zero():
    """发放角色全员集外(evicted 排除其在全部候选套的三名单身份)→ 0,
    不炸:借力打力的黑塔/缇宝宿主(core∪shared∪transition)全 evicted
    → 档落 off。"""
    hosts = frozenset(
        c.name for c in COMP_LIBRARY
        if {'黑塔', '缇宝'} & (set(c.core_chars) | set(c.shared_chars)
                               | set(c.transition_chars)))
    assert grant_gift_value(STRATEGY_GRANTS['借力打力'], hosts) == 0.0


def test_grant_advisor_halved():
    """顾问条目沿 ADVISOR_DISCOUNT ×0.5:锻冶专家:刃(刃 = shared 20)
    → 10(注册表真值直调:_char_gift_tier('刃') = shared)。"""
    assert _char_gift_tier('刃', frozenset()) == 'shared'
    assert grant_gift_value(STRATEGY_GRANTS['锻冶专家:刃'], frozenset()) == 10.0


def test_grant_registry_counts_and_closed_set():
    """底册计数锁(对账记录 = 迭代目录 strategy-grants-reconciliation.md):
    83 条 = 11 顾问 + 68 绑定母体白得 + 4 反扫补网;顾问档名单在册。"""
    assert len(STRATEGY_GRANTS) == 83
    advisors = {n for n, g in STRATEGY_GRANTS.items() if g.advisor}
    assert len(advisors) == 11
    assert {'停云顾问', '加拉赫顾问', '摸个鱼吧I'} <= advisors
    for n in ('龙虎兄弟狸', '佩佩驾到', '艾丝妲的猛犬！', '招财狗'):
        assert n in STRATEGY_GRANTS


def _patch_grants(monkeypatch, table: dict[str, GiftGrant]) -> None:
    monkeypatch.setattr(cw_investments, 'STRATEGY_GRANTS', table)


def test_grants_validation_orphan_key_raises(monkeypatch):
    """孤儿键(注册表无此卡)即炸(_validate_strategy_grants ①)。"""
    _patch_grants(monkeypatch, dict(STRATEGY_GRANTS) | {'不存在的卡': GiftGrant(chars_immediate=('刃',))})
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_strategy_grants()


def test_grants_validation_char_drift_raises(monkeypatch):
    """角色名漂移(CHARACTER_ROSTER 外)即炸(②)。"""
    bad = dict(STRATEGY_GRANTS)
    bad['借力打力'] = GiftGrant(chars_immediate=('不存在角色',))
    _patch_grants(monkeypatch, bad)
    with pytest.raises(ValueError, match='角色名漂移'):
        cw_investments._validate_strategy_grants()


def test_grants_validation_empty_grant_raises(monkeypatch):
    """空发放集即炸(③)。"""
    bad = dict(STRATEGY_GRANTS)
    bad['借力打力'] = GiftGrant()
    _patch_grants(monkeypatch, bad)
    with pytest.raises(ValueError, match='空发放集'):
        cw_investments._validate_strategy_grants()


def test_grants_validation_scan_closure_breach_raises(monkeypatch):
    """反扫候选闭集防线:摘除一张「获得…直读」登记卡(招财狗)→ 候选
    落白名单外即炸(④,新增发放卡漏登记的同形)。"""
    trimmed = {n: g for n, g in STRATEGY_GRANTS.items() if n != '招财狗'}
    _patch_grants(monkeypatch, trimmed)
    with pytest.raises(ValueError, match='反扫闭集破口'):
        cw_investments._validate_strategy_grants()


# ==================== ④ 结构分区(design §2.7)====================

#: 自拆台合成选项名(「净化身心」词缀克 DoT/减益;未注册名组件恒 0,
#: 排除是结构规则非定价;沿 test_cw_invest_env_strategy.py 同款)
_SELF_DEFEAT_OPT = '净化身心试验'


def _gs_dot_board() -> GameState:
    gs = _fresh_gs()
    gs.observe(gs.board, {'持续伤害': 2}, evidence='test', sig=_SIG_OBS)
    return gs


def test_forbid_excluded_from_competition():
    """禁选排除:最高分候选被 forbid 命中 → 出局,次高胜出(集合排除,
    分值化禁选退役)。藏一手 80 被禁 → 嘴硬 6 胜。"""
    cfg = SimpleNamespace(strategy_priority=[], strategy_forbid=['藏一手'])
    out = _decide_pick(['藏一手', '嘴硬', '二极管'], _fresh_gs(), config=cfg)
    assert out.idx == 1 and out.total == 6.0


def test_all_forbidden_frame_falls_back_to_all_argmax():
    """禁选致候选域全空 → 全体候选(含被禁)按组件总分 argmax 最不负分者
    (landing ④;reason 前缀 all-excluded-fallback)。"""
    cfg = SimpleNamespace(
        strategy_priority=[],
        strategy_forbid=['藏一手', '嘴硬', '二极管'])
    out = _decide_pick(['藏一手', '嘴硬', '二极管'], _fresh_gs(), config=cfg)
    assert out.idx == 0
    assert out.reason.startswith('all-excluded-fallback')


def test_empty_frame_degrades_idx0():
    """空候选帧(观察层失约,op 层已拦、此态仅防御)退化 idx=0 不炸
    (design §2.8)。"""
    out = _decide_pick([], _fresh_gs())
    assert out.idx == 0 and out.reason.startswith('empty-frame')


def test_self_defeat_excluded_in_normal_frame():
    """板面 DoT/减益 ≥2:克制者从非血非禁域排除(多候选帧仍排除,
    design §2.7-2)。"""
    out = _decide_pick([_SELF_DEFEAT_OPT, '嘴硬', '二极管'], _gs_dot_board())
    assert out.idx != 0


def test_self_defeat_guard_regains_one_selfdefeat_two_blood():
    """辖域护栏·1 自拆 + 2 血帧:自拆排除掏空非血域 → 自拆卡回归,
    血卡不得上位(design §2.7-2;与旧机器 L1 行为对齐)。"""
    out = _decide_pick(
        [_SELF_DEFEAT_OPT, '奋斗协议', '不等价交换'], _gs_dot_board())
    assert out.idx == 0


def test_self_defeat_guard_regains_two_forbid_one_selfdefeat():
    """辖域护栏·2 禁 + 1 自拆帧:禁选后非血域仅剩自拆卡,排除致空 →
    回归 → 选自拆卡。"""
    cfg = SimpleNamespace(strategy_priority=[],
                          strategy_forbid=['嘴硬', '二极管'])
    out = _decide_pick([_SELF_DEFEAT_OPT, '嘴硬', '二极管'], _gs_dot_board(),
                       config=cfg)
    assert out.idx == 0


def test_blood_forced_l2_domain():
    """血本位三态 L2:可入选非血集空(唯一非血卡被禁)→ 血卡间竞争
    (血强制帧,reason 前缀 blood-forced)。"""
    cfg = SimpleNamespace(strategy_priority=[], strategy_forbid=['藏一手'])
    out = _decide_pick(['奋斗协议', '不等价交换', '藏一手'], _fresh_gs(),
                       config=cfg)
    assert out.idx in (0, 1)
    assert out.reason.startswith('blood-forced')


def test_defining_zone_shrinks_and_component_argmax():
    """定义型分区:竞争域收缩为定义型子集(支配无条件化,design §2.7-4);
    并列定义型按组件总分裁决:黑塔纪元 110 < 本姑娘就是罗刹 150
    (组件直调:dir 100 + gift 50)→ 后者胜,尽管藏一手现金 80 在场。"""
    out = _decide_pick(['黑塔纪元', '本姑娘就是罗刹', '藏一手'], _fresh_gs())
    assert out.idx == 1 and out.total == 150.0


# ==================== ⑤ 平分裁决(design §2.8)====================

def test_tiebreak_quality_rank_over_slot_order():
    """平分裁决键 1:品质序(棱彩>金>银,游戏定义)压过槽序——三张零总分
    无机械成分卡(晋升名额 棱彩/枪在手 金/二费援银 银,注册表直调),
    任意槽序下棱彩胜。"""
    a = _decide_pick(['晋升名额', '枪在手', '二费援军'], _fresh_gs())
    b = _decide_pick(['二费援军', '枪在手', '晋升名额'], _fresh_gs())
    assert a.idx == 0 and b.idx == 2
    assert INVESTMENT_STRATEGIES['晋升名额'].rarity == '棱彩'


def test_tiebreak_econ_flag_within_quality():
    """平分裁决键 2:同品质同总分下 economy 效果有无合取式
    (economy is not None ∧ ≠ EconomyEffect())定先:高效决策(棱彩,
    free_refresh_burst 挂值→待建模塌 0 = 总分 0 但 econ=1)压过
    晋升名额(棱彩,无 economy);槽序翻转不改 winner。"""
    a = _decide_pick(['高效决策', '晋升名额'], _fresh_gs())
    b = _decide_pick(['晋升名额', '高效决策'], _fresh_gs())
    assert a.idx == 0 and b.idx == 1


def test_tiebreak_no_canonical_sorts_after_canonical():
    """无 canonical 候选(垃圾名)恒排任何 canonical 候选之后——并列
    0 分帧垃圾名不凭槽序压真卡(design §2.8);垃圾名之间按槽序。"""
    out = _decide_pick(['垃圾名甲', '垃圾名乙', '晋升名额'], _fresh_gs())
    assert out.idx == 2
    two = _decide_pick(['垃圾名甲', '垃圾名乙'], _fresh_gs())
    assert two.idx == 0


def test_env_name_defense_skips_resolution_zero_bottom():
    """env 名防御(design §2.8):env 注册名候选跳过解析、0 分垫底
    (防注册表交叉演化下 LCS 误中)——列车同行概念股(LCS 会误中
    列车同行星徽拿赠卡+方向)实际 0 分,嘴硬 6 金胜出。"""
    out = _decide_pick(['列车同行概念股', '嘴硬', '二极管'], _fresh_gs())
    assert out.idx == 1 and out.total == 6.0


# ==================== ⑥ 构建期校验(design §2.3/§2.6)====================

def test_field_classification_unclassified_raises(monkeypatch):
    """字段分类校验:未分类字段(从计分类摘除 instant_gold,藏一手
    挂值即触雷)即炸——建模缺口不静默。"""
    trimmed = strategy_economy._CASH_SCORED_FIELDS - {'instant_gold'}
    monkeypatch.setattr(strategy_economy, '_CASH_SCORED_FIELDS', trimmed)
    with pytest.raises(ValueError, match='未分类'):
        strategy_economy._validate_field_classification()


def test_field_classification_closure_missing_raises(monkeypatch):
    """字段分类闭集缺位:EconomyEffect 字段从三分并集消失即炸(注册表
    新字段未分类同形)——摘除 hp_max_loss_cap_pct 的不计行(该字段现版
    无挂值条目,'未分类' 扫描不触雷,唯闭集断言可辖)。"""
    trimmed = strategy_economy._NOT_SCORED_FIELDS - {'hp_max_loss_cap_pct'}
    monkeypatch.setattr(strategy_economy, '_NOT_SCORED_FIELDS', trimmed)
    with pytest.raises(ValueError, match='闭集缺位'):
        strategy_economy._validate_field_classification()


def test_field_classification_double_membership_raises(monkeypatch):
    """字段双归属(分类互斥破)即炸。"""
    doubled = strategy_economy._CASH_SCORED_FIELDS | {'hp_gold_swap'}
    monkeypatch.setattr(strategy_economy, '_CASH_SCORED_FIELDS', doubled)
    with pytest.raises(ValueError, match='双归属'):
        strategy_economy._validate_field_classification()


def test_pending_modeling_registry_shape():
    """卡级待建模在册正面形状:5 张辖域派生闭集卡必在册(固定理财/+
    孪生素数/狸财经狸/超发货币,landing ⑥)+ 注册表外经济语义代表例
    (被动收入/招财狗,design §2.3 处置口径);孪生素数 = 全默认 economy
    在册条目(③断言的真实对象)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        EconomyEffect,
    )
    for n in ('固定理财', '固定理财+', '孪生素数', '狸财经狸', '超发货币'):
        assert n in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING, n
    assert STRATEGY_ECONOMY['孪生素数'] == EconomyEffect()
    assert '被动收入' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING
    assert '招财狗' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING


def test_pending_modeling_orphan_and_empty_raises(monkeypatch):
    """卡级登记 ①孤儿键/②空描述即炸。"""
    bad = dict(strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING)
    bad['不存在的卡'] = 'x'
    monkeypatch.setattr(strategy_economy, 'STRATEGY_ECONOMY_PENDING_MODELING',
                        bad)
    with pytest.raises(ValueError, match='孤儿键'):
        strategy_economy._validate_pending_modeling_registry()
    bad2 = dict(strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING)
    bad2['孪生素数'] = ''
    monkeypatch.setattr(strategy_economy, 'STRATEGY_ECONOMY_PENDING_MODELING',
                        bad2)
    with pytest.raises(ValueError, match='空描述'):
        strategy_economy._validate_pending_modeling_registry()


def test_pending_modeling_all_default_entry_required(monkeypatch):
    """卡级登记 ③:全默认 economy 条目必须卡级在册(摘除孪生素数即炸
    ——全默认卡不入字段分类视野,唯卡级登记辖得住)。"""
    bad = {n: v for n, v in
           strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING.items()
           if n != '孪生素数'}
    monkeypatch.setattr(strategy_economy, 'STRATEGY_ECONOMY_PENDING_MODELING',
                        bad)
    with pytest.raises(ValueError, match='缺卡级待建模登记'):
        strategy_economy._validate_pending_modeling_registry()


def test_pending_modeling_closed_set_required(monkeypatch):
    """卡级登记 ④:辖域派生 5 张闭集卡缺位即炸。"""
    bad = {n: v for n, v in
           strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING.items()
           if n != '固定理财'}
    monkeypatch.setattr(strategy_economy, 'STRATEGY_ECONOMY_PENDING_MODELING',
                        bad)
    with pytest.raises(ValueError, match='闭集缺位'):
        strategy_economy._validate_pending_modeling_registry()


def test_stance_orphan_key_raises(monkeypatch):
    """立场表孤儿校验:v1 空表恒真,注入孤儿键(首行登记形态)即炸。"""
    monkeypatch.setattr(invest_strategy, 'STANCE_SCORE',
                        {'不存在的卡': StanceRow(1.0, '测试')})
    with pytest.raises(ValueError, match='孤儿键'):
        invest_strategy._validate_stance_registry()


# ==================== ⑦ 刷新判据(design §2.9)====================

def test_refresh_frame_gate_passes_low_frame():
    """帧级门全过(恰3 ∧ 全精确 ∧ 无帧级顶级 ∧ 锁线帧不适用):
    三张精确低分卡 → 全槽可刷建议。"""
    out = invest_strategy.decide(['嘴硬', '二极管', '免费升舱'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert out.slots == (0, 1, 2)


def test_refresh_blocked_by_defining_top():
    """帧级门 ③:定义型卡在场(非被禁)→ 整帧不刷(帧级顶级类 =
    定义型 ∨ 引擎,黑塔纪元 = 定义型)。"""
    out = invest_strategy.decide(['黑塔纪元', '嘴硬', '二极管'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)


def test_refresh_blocked_by_engine_top():
    """帧级门 ③:持续通道引擎卡在场 → 整帧不刷(开源节流 =
    interest_cap_override 入族)。"""
    out = invest_strategy.decide(['开源节流', '嘴硬', '二极管'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)


def test_refresh_e_exempt_forbidden_engine_does_not_block():
    """E-豁免:被禁引擎卡不入帧级顶级判定 → 门照常触发,被禁槽恒入
    动作集(P81 前提 E;开源节流被禁)。"""
    cfg = SimpleNamespace(strategy_priority=[], strategy_forbid=['开源节流'])
    out = invest_strategy.decide(['开源节流', '嘴硬', '二极管'],
                                 _fresh_gs(), '', False, frozenset(), cfg)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert 0 in out.slots


def test_refresh_locked_max_n1_blocks():
    """帧级门 ④:锁线帧 max_N = 1 → 整帧不刷(保守缺省;依据重建 =
    P81 单篇 §7 必答③,3.2 候裁)。
    列车同行星徽对锁线『列车同行』N=1(阵营命中,丹恒·饮月不在其 core)。"""
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '列车同行', False,
                                 frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)


def test_refresh_e_exempt_forbidden_not_counted_in_max_n():
    """E-豁免:被禁卡不计入 max_N——同帧被禁 N=1 卡后 max_N=0 → 门过
    (J6 承接)。"""
    cfg = SimpleNamespace(strategy_priority=[],
                          strategy_forbid=['列车同行星徽'])
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '列车同行', False,
                                 frozenset(), cfg)
    assert isinstance(out, StrategyRefreshSuggestion)


def test_refresh_f2_unique_l1_guard():
    """F2 唯一 L1 槽守卫:L1 = 非血∧非禁恰一时该槽不可刷(刷掉唯一 L1
    且新卡为血/禁 → 强制血选,确定损失分支)。血血非帧动作集 =
    {0,1}(唯二非血槽被守卫摘除)。"""
    out = invest_strategy.decide(['奋斗协议', '不等价交换', '嘴硬'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert out.slots == (0, 1)


def test_refresh_unlocked_sa_slot_protection():
    """未锁线帧槽级对齐保护 = 非血 ∧ 触 S/A 档线(方向分 ≥ A 档,无新
    常数):列车同行星徽触 S 线(100)受保护不入动作集,余槽可刷。"""
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert out.slots == (1, 2)


def test_refresh_demoted_frame_uses_unlocked_scale():
    """降格帧按未锁线口径:无 max_N 门(design §2.9-2),锁线参不生效
    ——同 max_N=1 帧在降格态(锁线已放弃)门通过。"""
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '列车同行', True,
                                 frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)


def test_refresh_gate_requires_all_exact():
    """帧级门 ②:全精确分类(LCS 兜底不入刷新分类,fail-closed)——
    形变名『嘴硬+』(LCS → 嘴硬)在场 → 门不过,不刷。"""
    out = invest_strategy.decide(['嘴硬+', '二极管', '免费升舱'],
                                 _fresh_gs(), '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)


# ==================== ⑨ decide_pick 纯选卡口(design §2.10)====================

def test_decide_pick_never_suggests_on_refresh_frame():
    """纯选卡口永不建议刷:同一建议帧,decide 返刷新建议、decide_pick
    返选卡决策(flow 同帧去重 memo 落选卡入口,对抗 H1)。"""
    frame = ['嘴硬', '二极管', '免费升舱']
    gs = _fresh_gs()
    out_decide = invest_strategy.decide(frame, gs, '', False, frozenset(),
                                        _EMPTY_CONFIG)
    assert isinstance(out_decide, StrategyRefreshSuggestion)
    out_pick = invest_strategy.decide_pick(frame, gs, '', False,
                                           frozenset(), _EMPTY_CONFIG)
    assert isinstance(out_pick, InvestStrategyDecision)
    assert out_pick.idx == 0 and out_pick.total == 6.0


def test_decide_pick_same_baseline_as_decide():
    """同评分基线:门失败帧(不刷)上 decide 与 decide_pick 逐位一致
    (idx/reason/total/components)。"""
    frame = ['黑塔纪元', '嘴硬', '二极管']
    gs = _fresh_gs()
    out_decide = invest_strategy.decide(frame, gs, '', False, frozenset(),
                                        _EMPTY_CONFIG)
    out_pick = invest_strategy.decide_pick(frame, gs, '', False,
                                           frozenset(), _EMPTY_CONFIG)
    assert isinstance(out_decide, InvestStrategyDecision)
    assert (out_decide.idx, out_decide.reason, out_decide.total) == \
        (out_pick.idx, out_pick.reason, out_pick.total)


# ==================== ⑩ 观测锚(landing ⑩,申报 5)====================

def test_lcs_fallback_hit_warns(caplog):
    """LCS 兜底命中即告警(观测锚;形变名会拿错卡全组件分,须可见):
    『嘴硬+』(LCS → 嘴硬)帧产 [cw!][invest_strategy] warning。"""
    with caplog.at_level(logging.WARNING):
        _decide_pick(['嘴硬+', '二极管'], _fresh_gs())
    assert any('[cw!][invest_strategy]' in r.message and 'LCS' in r.message
               for r in caplog.records)


def test_exact_hit_does_not_warn(caplog):
    """对照:精确命中不告警(锚只辖 LCS 兜底形态)。"""
    with caplog.at_level(logging.WARNING):
        _decide_pick(['嘴硬', '二极管'], _fresh_gs())
    assert not any('[cw!][invest_strategy]' in r.message
                   for r in caplog.records)
