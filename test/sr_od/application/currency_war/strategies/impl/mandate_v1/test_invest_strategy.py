"""投资策略画面策略层单测(判据正本 = docs/develop/sr_od/application/
currency_war/strategy-docs/29_invest_strategy_screen.md;规格出处 =

下称 design §)。

判据映射:
- ① 现金分(strategy_economy 通道公式:面值/分期金 R−1 截断/XP 双通道/
  固定息/boss kind 计数/待建模塌 0/位置缺失退化);
- ② 方向分(触线集 comp 空间像:锁线并集/未锁线 max/线排除像/降格帧/
  角色绑定窄口径);
- ③ 赠卡分(STRATEGY_GRANTS + grant_gift_value:即时最高档/条件降档/
  全员集外/顾问折减/底册计数与构建校验);
- ④ 结构分区(禁选/自拆辖域护栏/血本位三态/定义型分区/空候选退化);
- ⑤ 平分裁决键(品质序→econ 有无→槽序;无 canonical 殿后;env 名防御);
- ⑥ 构建期校验(字段三分/卡级待建模断言集/立场表孤儿);
- ⑦ 刷新判据(帧级门与槽级顶级两谓词分立、E-豁免、F2 守卫、对齐保护);
- ⑨ decide_pick 纯选卡口(同评分基线、永不建议刷);
- ⑩ LCS 兜底命中即告警(观测锚);
- ⑪ 环境屏(env)平行测试面(投资环境策略层 invest_env:线价值三口径/
  赠卡分/时代族零值/环境现金分/刷新三态与阈值/自拆台排除/构建校验
  /flow 消费侧接线)——与策略屏同族评分概念的 env 支,两屏生产模块
  平行,各自直测;
- ⑫ 阵容冲突护栏·策略屏(护栏设计 §2.2/§2.3:基准锁定/持有切换/出域
  排除/全出域回退/刷新交互/reason 文法);
- ⑬ 阵容冲突护栏·环境屏(env 支,护栏设计 §2.4:出域槽并入 excluded
  槽位表通道——禁选通道先建议刷新/闸尽落选出域已排除/全出域回退/
  基准空帧与通用环境零变化)。

校验「import 即炸」的接线面:直接调校验入口 + monkeypatch 表断言抛错,
不用 reload/源码扫描。

测试纪律:零真实副作用;断言钉住设计语义,数值期望 = 注册表真实数据
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
    INVESTMENT_ENVS,
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_GRANTS,
    GiftGrant,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    P2_NODE_SEQUENCE,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    invest_env,
    invest_strategy,
    strategy_economy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    XP_GOLD_RATE,
    env_economy_value,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    grant_gift_value,
    named_gift_value,
    random_faction_gift_value,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.invest_env import (
    InvestEnvDecision,
    RefreshSuggestion,
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
           node_seqs: dict[int, tuple[str, ...]] | None = None) -> GameState:
    """写在帧节点位置(可选写节点序列场字段 = 视界长度真值;
    None = 未注册态,读侧回退默认表)。"""
    gs = _fresh_gs()
    if node_seqs is not None:
        gs.write_logic(gs.node_seq_by_plane, node_seqs,
                       produced_by='test', evidence='node_seq:env',
                       sig=ChannelSig(family='logic_action',
                                      actor='cw-invest-strategy-test',
                                      mode='compute'))
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

#: 开局帧剩余节点数(node 缺失 → (1,1) 退化 + 场字段 None 回退默认表
#: P1=9/P2=7/P3=7,视界封顶 modeled planes):R = 9 + 7 + 7 = 23
#: (strategy_economy 位置缺失退化断言的共用口径;P3 行 2026-10-15
#: 用户裁定入码后随真值联动)
_R_OPENING = 23


def test_cash_instant_gold_face_value():
    """instant_gold 面值直计:决议:娱乐星球 = 50(现役注册表最大一次性金)。
    藏一手 2026-11-04 用户裁定 R1 = 奖励(30 经验 + 80 金)随救援触发当场
    发放,注册行反向改判全默认 → 估值 (0.0, False)(救援价值不进经济分,
    归策略立场域后继批立项;载荷单一源 = STRATEGY_DEATH_SAVE_GRANTS)。"""
    assert strategy_economy_value('决议:娱乐星球', _fresh_gs()) == (50.0, True)
    assert strategy_economy_value('藏一手', _fresh_gs()) == (0.0, False)


def test_cash_gold_next_nodes_r_minus_1_truncation():
    """分期金 =「现在」分支 + count 分支按 R−1 截断(design §2.3;
    「接下来」不含当前节点)。开局帧 R=23:长期主义 = 7×(1+min(3,22))
    = 28(count 分支 3 封顶,R 变不越帽——勿读 instant_gold,长期主义该
    字段 = 0,误读即漏现在分支);表外位面帧(4,1)(位面 ∉ 序列表键集
    → R=0,horizon §3 契约):count 分支截断为 0 → 仅「现在」分支 7。"""
    assert strategy_economy_value('长期主义', _fresh_gs()) == (28.0, True)
    assert strategy_economy_value('长期主义+', _fresh_gs()) == (36.0, True)
    assert strategy_economy_value('长期主义', _gs_at(4, 1)) == (7.0, True)


def test_cash_per_node_interest_xp_channels():
    """per-node 流/固定息/XP 双通道(值 = 注册表【注】× R 查表):
    定期福利 = 4 + 2×23;狸财经狸息分支 = 2×23(活计分分支,取款/存款分支
    待建模不关门——design 申报 7);伟大征服 xp_instant = 12;气氛组+ =
    8(注册行形状一并锁,即时腿骑 apply_strategy_pick_xp 字段分派通道);
    买断制 = 15 + 4×23(xp_per_node 流);XP_GOLD_RATE = 1.0。
    (R 开局 16→23 = P3 行入真值表,2026-10-15 用户裁定联动。)"""
    assert strategy_economy_value('定期福利', _fresh_gs()) == (50.0, True)
    assert strategy_economy_value('狸财经狸', _fresh_gs()) == (46.0, True)
    assert strategy_economy_value('伟大征服', _fresh_gs()) == (12.0, True)
    assert strategy_economy_value('气氛组+', _fresh_gs()) == (8.0, True)
    assert STRATEGY_ECONOMY['气氛组+'] == cw_investments.EconomyEffect(xp_instant=8)
    assert strategy_economy_value('买断制', _fresh_gs()) == (107.0, True)


def test_streak_set_pending_classification_and_zero_value_drift():
    """胜利,还是胜利 置位腿策略侧锁(T-96 设计 §4 锁 7):
    ``streak_set`` ∈ ``_PENDING_MODELING_FIELDS``(置位金流变化轨迹依赖
    未建模,import 期字段分类校验的硬义务面——显式断言防后人误移);
    估值零漂移 = 现金分仍恰为 instant_gold=4 面值(置位腿不入任何通道
    公式,新字段不进现金分)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        strategy_economy,
    )
    assert 'streak_set' in strategy_economy._PENDING_MODELING_FIELDS
    assert strategy_economy_value('胜利,还是胜利', _fresh_gs()) == (4.0, True)


def test_cash_schedule_truth_lookup():
    """剩余口径按节点序列场字段真值(None 回退默认表;修饰表进字段
    自适应;单一源 = statefn/horizon 门面场字段自算):
    P2R4 修饰表(boss 前插补给,P1=10/P2=8/P3=8)→ R = 本位面剩余 5
    + P3 8 = 13,定期福利 = 4 + 2×13 = 30;未注册态回退默认表 →
    R = 4 + 7 = 11 → 26。"""
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        resolve_plane_node_seqs,
    )
    modified = resolve_plane_node_seqs('人身意外险')
    assert strategy_economy_value('定期福利', _gs_at(2, 4, modified)) \
        == (30.0, True)
    assert strategy_economy_value('定期福利', _gs_at(2, 4)) == (26.0, True)


def test_cash_boss_channel_kind_count():
    """boss 通道 = 场字段序列自当前节点(含)起 'boss' kind 直查
    (details §6 kind 化;封顶 modeled planes,P3 行入表后默认局跨位面
    boss 一并计入,2026-10-15 联动):
    P2R4 默认表 → 当前位面 r4 起 1 个 boss(r7)+ P3 r7 = 2 → 特战资金
    = 7×2 = 14、特战资金+ = 11×2 = 22(含当前位面口径,偏差申报见模块
    docstring)。"""
    assert strategy_economy_value('特战资金', _gs_at(2, 4)) == (14.0, True)
    assert strategy_economy_value('特战资金+', _gs_at(2, 4)) == (22.0, True)


def test_cash_boss_channel_kind_not_geometry():
    """kind 计数非几何的判别测试:boss 不在位面末槽的场字段序列下,几何
    末槽假设与 kind 直查分叉——自当前节点(含)起的真实 boss 计数 = 2
    (P1 r3 boss + P2 全程 1 个;P1 位面末槽假设会漏计 r3 的 boss)。"""
    displaced = {
        1: ('battle', 'battle', 'boss', 'reward', 'reward', 'reward',
            'reward', 'reward', 'reward'),
        2: P2_NODE_SEQUENCE,
    }
    assert strategy_economy_value('特战资金', _gs_at(1, 1, displaced)) \
        == (14.0, True)


def test_cash_missing_node_degrades_to_opening_frame():
    """位置缺失帧退化 (1,1)(沿 env 屏先例;landing ① 分支断言):
    node 未写的裸帧与显式 (1,1) 帧逐位同值。"""
    bare = strategy_economy_value('长期主义', _fresh_gs())
    explicit = strategy_economy_value('长期主义', _gs_at(1, 1))
    assert bare == explicit == (28.0, True)


def test_cash_pending_modeling_card_failclosed():
    """计分通道矩阵:固定理财系两卡 = xp_instant 现金计分在册分类字段,
    注册挂值即通道自动生效(固定理财 4×/固定理财+ 6×XP_GOLD_RATE;位面段
    两字段待建模塌 0,估值面不重复计——2026-11-01 建模批两卡同判);孪生
    素数全默认 = 纯无字段分支 fail-closed 0。"""
    assert strategy_economy_value('固定理财', _fresh_gs()) \
        == (4.0 * XP_GOLD_RATE, True)
    assert strategy_economy_value('固定理财+', _fresh_gs()) \
        == (6.0 * XP_GOLD_RATE, True)
    assert strategy_economy_value('孪生素数', _fresh_gs()) == (0.0, False)


def test_cash_unregistered_name_failclosed():
    """未入册卡名 → (0, False),不炸(消费端按无现金处理)。"""
    assert strategy_economy_value('不存在的卡名', _fresh_gs()) == (0.0, False)


# ==================== ③ 赠卡分(design §2.5)====================

def test_grant_immediate_highest_tier():
    """即时集取最高档:借力打力(黑塔 core + 缇宝 core)→ core 50。"""
    assert grant_gift_value(STRATEGY_GRANTS['借力打力'], frozenset()) == 50.0


def test_grant_conditional_downgraded():
    """条件集降一档:迷之旅人两条分支均条件(黄泉 core → shared 20)。"""
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


def test_char_grant_cards_gift_value_off_zero():
    """转正卡赠卡分 0(佩佩 = cost0 系统召唤单位,COMP_LIBRARY 无档 →
    off 档机器事实):注册进估值读端后策略估值零行为变化(off 恒 0.0;
    若未来 COMP_LIBRARY 收编佩佩本锁显影,归立场重拍批)。"""
    for n in ('溜佩佩', '溜佩佩+', '这么大的钻石'):
        assert grant_gift_value(STRATEGY_GRANTS[n], frozenset()) == 0.0


def test_grant_registry_counts_and_closed_set():
    """底册计数测试(对账记录 = 迭代目录 strategy-grants-reconciliation.md):
    106 条 = 11 顾问 + 77 角色直读(绑定母体白得/反扫补网/非直读人工
    转正[佩佩逛街句/佩佩携钻句/佩佩客串登场句]/非候选直读登记[狸职手续,
    按实机录名归一])+ 16 开箱分支(占席道具直读,箱腿卡随批扩员,含融合召唤)
    + 1 选择型具名装备(独家代言,人工登记——「从3件进阶装备中选择一件
    获取」占位选定建模,选择获取无「获得…roster 名」直读,反扫零命中)
    + 1 角色×道具混合(龙虎兄弟狸);顾问档名单在册。"""
    assert len(STRATEGY_GRANTS) == 106
    advisors = {n for n, g in STRATEGY_GRANTS.items() if g.advisor}
    assert len(advisors) == 11
    assert {'停云顾问', '加拉赫顾问', '摸个鱼吧I'} <= advisors
    for n in ('龙虎兄弟狸', '佩佩驾到', '艾丝妲的猛犬！', '招财狗'):
        assert n in STRATEGY_GRANTS
    # 非直读人工转正 4 条(溜佩佩/溜佩佩+/这么大的钻石/佩佩客串):
    # 注册存在 + 发放对象 = 佩佩
    for n in ('溜佩佩', '溜佩佩+', '这么大的钻石', '佩佩客串'):
        assert n in STRATEGY_GRANTS, '转正卡注册在册'
        assert STRATEGY_GRANTS[n].chars_immediate == ('佩佩',), \
            '转正登记发放对象 = 佩佩'
        assert STRATEGY_GRANTS[n].advisor is False, '转正卡非顾问型'


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


def test_grants_box_legs_items_only_pass_validation(monkeypatch):
    """开箱分支条目(占席道具直读)登记形状(chars 两通道空 + items_immediate
    非空 = 合法,登记面先例 = 三张棱彩箱分支卡 + 军火贸易/军火贸易+);箱条目
    经消费口恒 off → 0 分(design 取舍 3,占席道具不进打分零改动)。"""
    for name, item in (('战术义眼+', '简易武装箱'),
                       ('战术义眼++', '进阶武装箱'),
                       ('保守派', '进阶武装箱'),
                       ('快请专家·彩', '进阶武装箱'),
                       ('军火贸易', '简易武装箱'),
                       ('军火贸易+', '简易武装箱')):
        grant = STRATEGY_GRANTS[name]
        assert grant.items_immediate == (item,), '开箱分支直读登记'
        assert grant.chars_immediate == () and grant.chars_conditional == ()
        assert grant.advisor is False
    assert grant_gift_value(STRATEGY_GRANTS['保守派'], frozenset()) == 0.0
    assert grant_gift_value(STRATEGY_GRANTS['军火贸易'], frozenset()) == 0.0
    assert grant_gift_value(STRATEGY_GRANTS['军火贸易+'], frozenset()) == 0.0
    # 正面:items-only 条目经校验不炸(patch 值 = 融合召唤注册表真值形;
    # 该卡落注册后本例兼作「已注册卡重校验」形态,断言面 = 校验不炸)。
    patched = dict(STRATEGY_GRANTS)
    patched['融合召唤'] = GiftGrant(items_immediate=('简易武装箱',))
    _patch_grants(monkeypatch, patched)
    cw_investments._validate_strategy_grants()


def test_grants_validation_scan_closure_breach_raises(monkeypatch):
    """反扫候选闭集防线:摘除一张「获得…直读」登记卡(招财狗)→ 候选
    落白名单外即炸(④,新增发放卡漏登记的同形)。"""
    trimmed = {n: g for n, g in STRATEGY_GRANTS.items() if n != '招财狗'}
    _patch_grants(monkeypatch, trimmed)
    with pytest.raises(ValueError, match='反扫闭集破口'):
        cw_investments._validate_strategy_grants()


def test_char_grant_cards_retired_from_scan_exclusions():
    """非直读转正卡不在反扫排除白名单(注册后排除因「未登记」失真,两键
    随注册退役;候选闭集由注册表覆盖——防线负向回归由
    test_grants_validation_scan_closure_breach_raises 承担,本锁只钉退役
    事实防误加回)。"""
    assert '溜佩佩' not in cw_investments._STRATEGY_GRANTS_SCAN_EXCLUSIONS
    assert '溜佩佩+' not in cw_investments._STRATEGY_GRANTS_SCAN_EXCLUSIONS


# ==================== ④ 结构分区(design §2.7;统一阵容评分迭代重写)=====

#: 自拆台合成选项名(「净化身心」词缀克制名单含 持续伤害/减益;未注册名
#: 组件恒 0,减分是结构规则非定价)
_SELF_DEFEAT_OPT = '净化身心试验'


def _gs_hold_backline(*names: str) -> GameState:
    """持有面种子(后排队;1★)——选卡锚点线(候选首名)由此点亮。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        Unit,
        deployed_view_sequential,
    )
    gs = _fresh_gs()
    gs.observe(gs.deployed,
               deployed_view_sequential(
                   [], [Unit(char_id=n, star=1, equips=[]) for n in names]),
               evidence='t', sig=_SIG_OBS)
    return gs


def test_forbid_excluded_from_competition():
    """禁选排除:最高分候选被 forbid 命中 → 出局,次高胜出(集合排除,
    分值化禁选退役)。决议:娱乐星球 50 被禁 → 嘴硬 6 胜。(原现金锚
    藏一手 R1 用户裁定 2026-11-04 反向改判后零分,禁选不再可辨——锚换
    现役面值例,见 test_cash_instant_gold_face_value。)"""
    cfg = SimpleNamespace(strategy_priority=[],
                          strategy_forbid=['决议:娱乐星球'])
    out = _decide_pick(['决议:娱乐星球', '嘴硬', '二极管'], _fresh_gs(),
                       config=cfg)
    assert out.idx == 1 and out.total == 6.0


def test_all_forbidden_frame_falls_back_to_all_argmax():
    """禁选致候选域全空 → 全体候选(含被禁)按组件总分 argmax 最不负分者
    (landing ④;reason 前缀 all-excluded-fallback)。"""
    cfg = SimpleNamespace(
        strategy_priority=[],
        strategy_forbid=['决议:娱乐星球', '嘴硬', '二极管'])
    out = _decide_pick(['决议:娱乐星球', '嘴硬', '二极管'], _fresh_gs(),
                       config=cfg)
    assert out.idx == 0
    assert out.reason.startswith('all-excluded-fallback')


def test_empty_frame_degrades_idx0():
    """空候选帧(观察层失约,op 层已拦、此态仅防御)退化 idx=0 不炸
    (design §2.8)。"""
    out = _decide_pick([], _fresh_gs())
    assert out.idx == 0 and out.reason.startswith('empty-frame')


def test_counter_penalty_applies_against_top1_line_main_faction():
    """克制减分(counters_dot 硬排除迁移,design §3.2;锚点线档 0 键
    命中克制名单即触发,P1 更早更广):
    持卡芙卡 → 候选首名 = DOT队(锚 8000)→ 档 0 键 持续伤害 ∈
    净化身心克制名单;净化身心试验 −750 落败,嘴硬 6 胜(纯加权,非排除)。"""
    out = _decide_pick([_SELF_DEFEAT_OPT, '嘴硬', '二极管'],
                       _gs_hold_backline('卡芙卡'))
    assert out.idx == 1 and out.total == 6.0
    assert out.components[5] == 0.0, '胜者无克制'


def test_counter_penalty_zero_when_anchor_missing():
    """锚缺失帧(零证据 → 无候选首名)克制减分不触发:同一自拆台卡在
    零证据帧不减分(0 分并列,品质/槽序裁决)——保守缺省申报。"""
    out = _decide_pick([_SELF_DEFEAT_OPT, '嘴硬'], _fresh_gs())
    assert out.idx == 1 and out.total == 6.0, '零锚帧不减分,嘴硬现金胜'


def test_counter_penalty_worse_than_cash_max():
    """克制档数量级:−750 压过现金满档——克制减分为线分数量级分量,
    与方向分同标尺(design §2 克制档)。"""
    gs = _gs_hold_backline('卡芙卡')
    out = _decide_pick([_SELF_DEFEAT_OPT + '藏一手', '嘴硬', '二极管'], gs)
    assert out.idx != 0, '−750 须压过任何现金组件'


def test_blood_forced_l2_domain():
    """血本位三态 L2:可入选非血集空(唯一非血卡被禁)→ 血卡间竞争
    (血强制帧,reason 前缀 blood-forced)。"""
    cfg = SimpleNamespace(strategy_priority=[], strategy_forbid=['藏一手'])
    out = _decide_pick(['奋斗协议', '不等价交换', '藏一手'], _fresh_gs(),
                       config=cfg)
    assert out.idx in (0, 1)
    assert out.reason.startswith('blood-forced')


def test_defining_partition_retired_direction_score_decides():
    """定义型分区退役(design §3.2 defining 布尔退役):支配由方向分
    数值实现——零证据帧(锚缺失 → 方向分 0)定义卡按组件分竞争,黑塔
    纪元/罗刹 赠卡 50 同分,平分裁决键取先(行为变更申报:P1 零证据
    开局帧定义卡不再无条件支配);锚点亮帧(持大黑塔+黑塔 → top1 =
    大黑塔银河学者)黑塔纪元方向分 500 + 赠卡 50 = 550 支配胜出。
    (原现金锚 藏一手 R1 用户裁定 2026-11-04 反向改判后估值 (0.0,False)
    零分出局,组件分竞争面换赠卡对内竞争。)"""
    bare = _decide_pick(['黑塔纪元', '本姑娘就是罗刹', '藏一手'],
                        _fresh_gs())
    assert bare.idx == 0 and bare.total == 50.0, \
        '零证据帧定义分区不再秒选(锚缺失方向分 0,赠卡分竞争)'
    lit = _decide_pick(['黑塔纪元', '本姑娘就是罗刹', '藏一手'],
                       _gs_hold_backline('大黑塔', '黑塔'))
    assert lit.idx == 0 and lit.total == 550.0
    assert lit.components[1] == 500.0, '方向分 = 定义卡通道加分'


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
    (被动收入/招财狗/气氛组/气氛组+,design §2.3 处置口径——气氛组系
    条件腿零建模是有意登记非漏登记);孪生素数 = 全默认 economy
    在册条目(③断言的真实对象)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        EconomyEffect,
    )
    for n in ('固定理财', '固定理财+', '孪生素数', '狸财经狸', '超发货币'):
        assert n in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING, n
    assert STRATEGY_ECONOMY['孪生素数'] == EconomyEffect()
    assert '被动收入' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING
    assert '招财狗' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING
    assert '气氛组' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING
    assert '气氛组+' in strategy_economy.STRATEGY_ECONOMY_PENDING_MODELING


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


def test_refresh_blocked_by_derived_defining_top():
    """帧级门 ③:顶级卡(派生:给 top1 线加分 ≥ 强档阈值)在场(非被禁)
    → 整帧不刷——锚点亮帧(持大黑塔+黑塔 → top1 = 大黑塔银河学者,
    黑塔纪元方向分 500 ≥ 500)整帧保护;对照零证据帧(锚缺失 → 方向分
    0 → 非顶级)同候选组照常建议刷(行为变更申报:现行查表不依赖锚,
    零证据开局帧定义卡受保护;新机制锚缺失不保护,入 sim 场景①)。"""
    out = invest_strategy.decide(['黑塔纪元', '嘴硬', '二极管'],
                                 _gs_hold_backline('大黑塔', '黑塔'),
                                 '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)
    zero = invest_strategy.decide(['黑塔纪元', '嘴硬', '二极管'],
                                  _fresh_gs(), '', False, frozenset(),
                                  _EMPTY_CONFIG)
    assert isinstance(zero, StrategyRefreshSuggestion), \
        '零锚帧定义卡不过阈,顶级保护不辖'


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
                                 _fresh_gs(), '列车同行·反震', False,
                                 frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestStrategyDecision)


def test_refresh_e_exempt_forbidden_not_counted_in_max_n():
    """E-豁免:被禁卡不计入 max_N——同帧被禁 N=1 卡后 max_N=0 → 门过
    (J6 承接)。"""
    cfg = SimpleNamespace(strategy_priority=[],
                          strategy_forbid=['列车同行星徽'])
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '列车同行·反震', False,
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



def test_refresh_demoted_frame_uses_unlocked_scale():
    """降格帧按未锁线口径:无 max_N 门(design §2.9-2),锁线参不生效
    ——同 max_N=1 帧在降格态(锁线已放弃)门通过。"""
    out = invest_strategy.decide(['列车同行星徽', '嘴硬', '二极管'],
                                 _fresh_gs(), '列车同行·反震', True,
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
    (idx/reason/total/components)。取引擎卡帧(开源节流 = 帧级顶级,
    整帧不刷)——统一阵容评分后零锚帧定义卡不再拦刷,黑塔纪元帧已变
    建议刷帧(test_refresh_blocked_by_derived_defining_top 对照面)。"""
    frame = ['开源节流', '嘴硬', '二极管']
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


# ==================== ⑪ 环境屏(env)平行测试面 ====================
# 投资环境策略层(与策略屏同族评分概念的 env 支;两屏生产模块平行,
# 各自直测)。判据 = ①-⑦ + flow 消费侧接线测试。

_ENV_SIG_LOGIC = ChannelSig(family='logic_action', actor='cw-invest-env-test',
                            mode='compute')
_ENV_SIG_OBS = ChannelSig(family='obs', actor='cw-invest-env-test',
                          mode='synthesized')

#: 零转向配置(禁测用户轴语义时使用;decide 不要求 config 具体类型)
_ENV_EMPTY_CONFIG = SimpleNamespace(env_priority=[], env_forbid=[])

#: 时代族 6 条(design 表零值裁定行)
_ERA_ENVS = ('彩虹时代', '黄金时代', '白银时代', '头彩', '尾彩', '银·金·彩')


def _env_set_refresh_left(gs: GameState, left: int) -> None:
    """写环境刷新剩余次数(容器观察真值形态;次数闸 = ≥1)。"""
    gs.write_logic(gs.env_refresh_left, left,
                   produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)


# ---- ② 赠卡分 ----


def test_env_named_gift_direct_core_scores_high():
    """战技点契约 = 丹恒·饮月+花火 双 core 白得 → core 档高分(50)。"""
    assert named_gift_value('战技点契约', frozenset()) == 50.0


def test_env_named_gift_all_evicted_is_zero_not_disqualified():
    """全员集外 → 赠卡分自然 0;整环境失格规则已删,环境其余成分照常
    计分——测试语义:总分公式仍成立而非整体清零。"""
    all_comps = frozenset(c.name for c in COMP_LIBRARY)
    assert named_gift_value('战技点契约', all_comps) == 0.0
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 0)   # 关次数闸,强制返回选卡决策
    out = invest_env.decide(['战技点契约'], gs, '', False, all_comps,
                            _ENV_EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


def test_env_named_gift_advisor_halved():
    """advisor(付费顾问期权)按同档分 × 0.5:特邀专家:桑博 = core → 25。"""
    assert named_gift_value('特邀专家:桑博', frozenset()) == 25.0


def test_env_sanxing_peipei_ruled_zero_total():
    """三星佩佩 = 用户裁定 0 分(T-16 §8-3,2026-10-15):赠卡 off 档 0
    (佩佩不在任何候选套的机器结果)+ 立场行 0(召唤填充位,星徽佩戴分支
    不建模)→ 环境总分 = 0。"""
    assert named_gift_value('三星佩佩', frozenset()) == 0.0
    assert invest_env.option_total('三星佩佩', _fresh_gs()) == 0.0


def test_env_cuxing_peipei_ruled_zero_total():
    """粗星佩佩 = 用户裁定 0 分(T-17 §8,2026-10-15):赠卡 off 档 0
    (佩佩不在任何候选套的机器结果)+ 立场行 0(效果无法估计,拍 0)
    → 环境总分 = 0。"""
    assert named_gift_value('粗星佩佩', frozenset()) == 0.0
    assert invest_env.option_total('粗星佩佩', _fresh_gs()) == 0.0


def test_env_random_faction_gift_is_member_tier_average():
    """随机阵营赠卡 = 成员档位算术平均(env 无偏口径):
    量子同频注册成员中缇宝/花火/希儿/符玄 core + 银狼 shared →
    (4×50 + 20) / 5 = 44。"""
    assert random_faction_gift_value('量子同频', frozenset()) == 44.0


def test_env_random_faction_gift_no_member_in_rosters_is_zero():
    """无成员在册 → 0(全员 evicted 后三名单皆不在,除零防)。"""
    all_comps = frozenset(c.name for c in COMP_LIBRARY)
    assert random_faction_gift_value('量子同频', all_comps) == 0.0


# ---- ③ 时代族 6 条总分 = 0 ----


def test_env_era_family_total_is_zero():
    """时代族 6 条总分 = 0:品质重排只是换随机方式,整体期望不变
    (用户裁定 2026-09-23);现金通道(品质改写层 E)fail-closed,
    无阵营无赠卡,立场登记 0。"""
    gs = _fresh_gs()
    for name in _ERA_ENVS:
        assert invest_env.option_total(name, gs) == 0.0, name


# ---- ④ 现金分 ----


def test_env_cash_inflation_positive_and_resolved():
    """增发货币:A 类精确通道,开局全局期望 > 0 且 resolved。"""
    value, resolved = env_economy_value('增发货币', _fresh_gs())
    assert resolved is True
    assert value > 0.0


def test_env_cash_missing_estimate_failclosed_zero_without_raise():
    """缺参环境(C 类零有效估计)→ fail-closed (0.0, False),不炸。"""
    assert env_economy_value('经济过热', _fresh_gs()) == (0.0, False)


def test_env_cash_refresh_envs_fixed_registered_values():
    """长线利好 = 50 / 二手市场 = 30 拍值注册(proofs/p97-refresh-budget
    §7,无条件计,不读局内刷新计数)。"""
    assert env_economy_value('长线利好', _fresh_gs()) == (50.0, True)
    assert env_economy_value('二手市场', _fresh_gs()) == (30.0, True)


# ---- ⑤ 刷新三态 ----


def test_env_refresh_forbidden_slot_suggests_refresh():
    """禁选必刷:帧内存在禁选槽 → RefreshSuggestion(剩余 ≥1)。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 1)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['列车同行'])
    out = invest_env.decide(['列车同行概念股', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), cfg)
    assert isinstance(out, RefreshSuggestion)


def test_env_refresh_low_score_frame_with_budget_suggests():
    """低分帧(全 0 值 < 阈值)+ 剩余 ≥1 → RefreshSuggestion。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 1)
    out = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, RefreshSuggestion)


def test_env_refresh_high_score_frame_picks_instead():
    """高分帧(S 线方向分 > 阈值)→ 不刷,直接选卡。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 1)
    out = invest_env.decide(['列车同行概念股', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


def test_env_refresh_count_gate_blocks_suggestion():
    """次数闸:剩余 = 0(与未观察 None 同理 fail-closed)→ 不建议刷,
    低分帧退化为常规选卡(建议刷最终由 handler 双闸裁定)。"""
    gs_zero = _fresh_gs()
    _env_set_refresh_left(gs_zero, 0)
    out_zero = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                                 gs_zero, '', False, frozenset(),
                                 _ENV_EMPTY_CONFIG)
    assert isinstance(out_zero, InvestEnvDecision)
    # 剩余次数未观察(Field None = 读缺跳写)→ 次数 ≥1 无法确证 → 不刷
    out_unobserved = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                                       _fresh_gs(), '', False, frozenset(),
                                       _ENV_EMPTY_CONFIG)
    assert isinstance(out_unobserved, InvestEnvDecision)


def test_env_refresh_threshold_is_full_registry_mean():
    """阈值 = 全 83 条环境无轴总分的均值(构建期派生,单一源 = 表)。
    派生口径与运行时评分同基线(不含转向轴)。"""
    gs = _fresh_gs()
    total = sum(invest_env.option_total(n, gs) for n in INVESTMENT_ENVS)
    assert pytest.approx(total / len(INVESTMENT_ENVS)) == \
        invest_env.REFRESH_THRESHOLD
    # 阈值非退化:正成分存在(现金/方向/赠卡/立场)→ 均值 > 0;低于 S 线
    # 方向分(均值 ≤ 最大总分 < 单线满档 + 赠卡,判据不会把最强帧判低分)
    assert 0.0 < invest_env.REFRESH_THRESHOLD < 100.0


# ---- ⑥ 选卡克制减分(counters_dot 硬排除迁移,design §3.2/§7)----

#: 全排除退化帧:三条概念股同被 env_forbid 子串命中(排除规则覆盖全体)。
_ALL_EXCLUDED_OPTS = ('仙舟概念股', '减益概念股', '击破概念股')


def test_env_counter_penalty_against_top1_line():
    """环境屏克制减分(机制与策略屏同源,design §3.2):持卡芙卡 →
    候选首名 = DOT队 → 净化身心试验 −750 落到次席(剩余次数置 0 关刷新
    建议,隔离次数闸;环境名不含词缀注册名族,生产帧该分量恒 0,
    合成名钉机制)。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 0)
    from sr_od.application.currency_war.kernel.cw_game_state import (
        Unit,
        deployed_view_sequential,
    )
    gs.observe(gs.deployed,
               deployed_view_sequential([], [Unit(char_id='卡芙卡', star=1)]),
               evidence='t', sig=_ENV_SIG_OBS)
    out = invest_env.decide([_SELF_DEFEAT_OPT, '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 1, '克制减分使自拆台卡落败(纯加权)'


def test_env_no_counter_penalty_when_anchor_missing():
    """锚缺失帧(零证据)不减分:同分并列取先(落首席)——旧「板面
    DoT/减益 ≥2 排除」随硬排除退役,触发面换锚点线主派。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 0)
    out = invest_env.decide([_SELF_DEFEAT_OPT, '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


def test_env_all_excluded_frame_falls_back_to_decision():
    """全排除退化帧 + 次数闸关:排除规则失去选择面,落地件对全体候选
    (含被禁)取 argmax 最不负分者返回选卡决策,
    归因串以 all-excluded-fallback 开头——该帧会真发选卡动作,
    reason 是判读面唯一标识(不断言 idx:位次随阵容库注册值漂移,校验类型 +
    归因前缀即设计语义)。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 0)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    out = invest_env.decide(list(_ALL_EXCLUDED_OPTS), gs, '', False,
                            frozenset(), cfg)
    assert isinstance(out, InvestEnvDecision)
    assert out.reason.startswith('all-excluded-fallback')


def test_env_all_excluded_frame_with_budget_suggests_refresh():
    """对照帧:同帧剩余 ≥1 → 禁选槽存在优先建议刷(排除规则有选择面,
    不做退化选卡;禁选槽 ∨ 低分即刷)。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 1)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    out = invest_env.decide(list(_ALL_EXCLUDED_OPTS), gs, '', False,
                            frozenset(), cfg)
    assert isinstance(out, RefreshSuggestion)


# ---- ⑦ 构建期校验 ----


def test_env_build_validation_missing_stance_row_raises(monkeypatch):
    """立场表缺行即炸:删「进化算法」(无机械成分环境)后校验抛 ValueError。
    (import 成功本身 = 真实全表已过校验的正面情形。)"""
    trimmed = dict(invest_env.STANCE_SCORE)
    trimmed.pop('进化算法')
    monkeypatch.setattr(invest_env, 'STANCE_SCORE', trimmed)
    with pytest.raises(ValueError, match='立场分表缺行'):
        invest_env._validate_stance_coverage()


def test_env_build_validation_orphan_stance_key_raises(monkeypatch):
    """立场表孤儿键(注册表无此环境)同样炸出。"""
    patched = dict(invest_env.STANCE_SCORE)
    patched['不存在的环境'] = invest_env.StanceRow(0.0, '孤儿键测试')
    monkeypatch.setattr(invest_env, 'STANCE_SCORE', patched)
    with pytest.raises(ValueError, match='孤儿键'):
        invest_env._validate_stance_coverage()



def test_env_build_validation_coefficient_tables_complete():
    """系数表键完备:赠卡档覆盖四档。(import 已过一遍;显式再验 = 钉住
    校验函数自身行为。线强度档校验已随 strength/方向分链下线移除。)"""
    invest_env._validate_coefficient_tables()   # 不抛 = 键完备
    from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
        GIFT_TIER_SCORE,
    )
    assert {'core', 'shared', 'transition', 'off'} <= set(GIFT_TIER_SCORE)


def test_env_build_validation_coefficient_missing_key_raises(monkeypatch):
    """系数表缺键即炸(校验逻辑本体拒绝测试):赠卡档缺 transition 拒绝。
    (线强度缺键分支已随 strength/方向分链下线移除。)"""
    with monkeypatch.context() as m:
        m.setattr(invest_env, 'GIFT_TIER_SCORE',
                  {k: v for k, v in invest_env.GIFT_TIER_SCORE.items()
                   if k != 'transition'})
        with pytest.raises(ValueError, match='赠卡档分缺键'):
            invest_env._validate_coefficient_tables()


# ---- flow 消费侧接线测试 ----


def _env_wired_strategy(gs: GameState):
    """活策略核(生产注册壳 mandate_v1.bridge 具现;决策入口 = CwFlowStrategy
    继承链。零真实副作用:容器桩 session 宿主隔离,config 桩缺省 =
    转向轴全空)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import bridge
    return bridge.MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))


def _env_write_frame(gs: GameState, options: list[str],
                     refresh_left: int) -> None:
    """写 env 帧 slots(候选 + 刷新余量;观察真值形态)。"""
    gs.write_logic(gs.invest_env_opts, options,
                   produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)
    gs.write_logic(gs.env_refresh_left, refresh_left,
                   produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)


def test_env_flow_frame_routes_and_wraps_actions():
    """env 帧路由+动作包装:高分帧(有余量)→ CwActionPickInvestEnvParam;
    低分帧(有余量)→ CwActionRefreshInvestCardsParam 且 slots = 全帧槽位
    (环境屏整组重掷单全局钮,slots = 真值哨兵)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionRefreshInvestCardsParam,
    )
    gs = _fresh_gs()
    _env_write_frame(gs, ['仙舟概念股', '列车同行概念股', '减益概念股'], 1)
    out = _env_wired_strategy(gs).decide_invest_env()
    assert isinstance(out, CwActionPickInvestEnvParam)
    assert out.idx == 0   # 仙舟概念股(方向分下线后按赠卡分胜出,gift 50)
    gs_low = _fresh_gs()
    _env_write_frame(gs_low, ['彩虹时代', '黄金时代', '白银时代'], 1)
    out_low = _env_wired_strategy(gs_low).decide_invest_env()
    assert isinstance(out_low, CwActionRefreshInvestCardsParam)
    assert out_low.slots == (0, 1, 2)


def test_env_flow_frame_memo_three_states():
    """memo 三态(同帧去重语义):首调发建议写 memo → 同候选重调落选卡
    (handler 刷新闸全败回退契约)→ 再调恢复首调建议(键清;
    行为面证明,不摸 scratch 内部)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionRefreshInvestCardsParam,
    )
    gs = _fresh_gs()
    _env_write_frame(gs, ['彩虹时代', '黄金时代', '白银时代'], 1)
    strategy = _env_wired_strategy(gs)
    first = strategy.decide_invest_env()
    assert isinstance(first, CwActionRefreshInvestCardsParam)
    again = strategy.decide_invest_env()
    assert isinstance(again, CwActionPickInvestEnvParam)
    third = strategy.decide_invest_env()
    assert isinstance(third, CwActionRefreshInvestCardsParam)


def test_env_decide_and_decide_pick_agree():
    """decide 与 decide_pick 零漂移:同帧同 idx 同 reason(同一评分基线,
    memo 落选卡的语义承载);至少含全排除退化帧一例(memo 命中恰落的形态)。"""
    gs = _fresh_gs()
    _env_set_refresh_left(gs, 0)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    opts = list(_ALL_EXCLUDED_OPTS)
    d1 = invest_env.decide(opts, gs, '', False, frozenset(), cfg)
    d2 = invest_env.decide_pick(opts, gs, '', False, frozenset(), cfg)
    assert isinstance(d1, InvestEnvDecision)
    assert d1.reason.startswith('all-excluded-fallback')
    assert (d2.idx, d2.reason) == (d1.idx, d1.reason)
    # 正常高分帧同基线(非退化形态)
    gs_hi = _fresh_gs()
    _env_set_refresh_left(gs_hi, 1)
    hi = ['仙舟概念股', '列车同行概念股', '减益概念股']
    h1 = invest_env.decide(hi, gs_hi, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    h2 = invest_env.decide_pick(hi, gs_hi, '', False, frozenset(),
                                _ENV_EMPTY_CONFIG)
    assert (h2.idx, h2.reason) == (h1.idx, h1.reason)


#: 策略轴建议帧(三张精确低分卡:帧级门过、全槽可刷——同帧取自本文件
#: 刷新判据测试,注册表真实数据)。
_STRATEGY_REFRESH_FRAME = ['嘴硬', '二极管', '免费升舱']


def _write_strategy_frame(gs: GameState, options: list[str]) -> None:
    """写策略帧 slots(候选;观察真值形态)。"""
    gs.write_logic(gs.invest_strategy_opts, options,
                   produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)


def test_env_flow_strategy_axis_strategy_layer_reason_shape():
    """策略轴接线回归:kind='strategy' 走策略层 ``invest_strategy.decide``——
    产物 = CwActionPickInvestStrategyParam 且 reason 为策略层新机签名
    形态 ``pick total=...`` 前缀(归因来源可辨);idx 落在候选域。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestStrategyParam,
    )
    gs = _fresh_gs()
    gs.write_logic(gs.invest_strategy_opts, ['远见', '利息上调'],
                   produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)
    out = _env_wired_strategy(gs).decide_invest_strategy()
    assert isinstance(out, CwActionPickInvestStrategyParam)
    assert out.idx in (0, 1)
    assert out.reason.startswith('pick total=')
    assert 'score=' not in out.reason


def test_env_flow_strategy_frame_memo_three_states():
    """策略轴 memo 三态(同帧去重语义;缺 decide_pick 落选卡口则建议帧
    三闸全败时 op round_fail 的行为缺口测试):建议帧首调发
    CwActionRefreshInvestCardsParam(slots = 策略层动作集)→ 同候选重调落
    选卡 CwActionPickInvestStrategyParam(reason = pick total= 前缀,取数口
    = invest_strategy.decide_pick 同一评分基线)→ 再调恢复首调建议(键清;
    行为面证明,不摸 scratch 内部)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestStrategyParam,
        CwActionRefreshInvestCardsParam,
    )
    gs = _fresh_gs()
    _write_strategy_frame(gs, _STRATEGY_REFRESH_FRAME)
    strategy = _env_wired_strategy(gs)
    first = strategy.decide_invest_strategy()
    assert isinstance(first, CwActionRefreshInvestCardsParam)
    assert first.slots == (0, 1, 2)
    again = strategy.decide_invest_strategy()
    assert isinstance(again, CwActionPickInvestStrategyParam)
    assert again.reason.startswith('pick total=')
    third = strategy.decide_invest_strategy()
    assert isinstance(third, CwActionRefreshInvestCardsParam)


# ==================== ⑫ 阵容冲突护栏(护栏设计 §2.2/§2.3)====================
# 判据 = changes/2026-10-17-invest-direction-guard/design.md §2.2/§2.3。
# 指向集派生与查询归一在 kernel 单元(test_cw_investments.py 指向集节)
# 锁定,本节锁选卡/刷新行为面,期望值全部注册表现算。§4 清单的「兼容卡」
# 用命运圣杯星徽承载——命运圣杯契约是环境名非策略卡(PlazaPortal 1202),
# 策略屏候选域无此卡(env 名防御路径),不可作本面候选。

def _gs_holding(env: str = '',
                strategies: tuple[str, ...] | None = None) -> GameState:
    """写持有投资(观察真值形态;与生产写入同通道,§3.4.4/active_env
    选择事实)。"""
    gs = _fresh_gs()
    if env:
        gs.observe(gs.active_env, env, evidence='test', sig=_SIG_OBS)
    if strategies:
        gs.observe(gs.active_strategies, list(strategies),
                   evidence='test', sig=_SIG_OBS)
    return gs


def test_guard_held_frame_excludes_conflicting_defining():
    """持有指向帧 + 冲突定义型排除:持命运圣杯邀请(基准 = {命运圣杯,
    能量}),黑塔纪元({银河学者, 群攻})与全部持有指向零交 → 出域,
    通用卡胜出(护栏设计 §2.3 规则表行 3)。"""
    out = _decide_pick(['黑塔纪元', '嘴硬', '二极管'],
                       _gs_holding(env='命运圣杯邀请'))
    assert out.idx != 0
    assert out.reason.startswith('off-direction')


def test_guard_held_frame_excludes_conflicting_component():
    """持有指向帧 + 冲突组件型排除(§4 清单):琼玉专家:青雀({仙舟})
    对圣杯基零交 → 出域。"""
    out = _decide_pick(['琼玉专家:青雀', '嘴硬', '二极管'],
                       _gs_holding(env='命运圣杯邀请'))
    assert out.idx != 0
    assert out.reason.startswith('off-direction')


def test_guard_compatible_card_scores_normal():
    """兼容卡正常(§4 清单):命运圣杯星徽(指向 ⊇ 命运圣杯)对圣杯基
    有交 → 不出域,高分胜出且无护栏前缀。"""
    out = _decide_pick(['命运圣杯星徽', '嘴硬', '二极管'],
                       _gs_holding(env='命运圣杯邀请'))
    assert out.idx == 0
    assert out.reason.startswith('pick total=')


def test_guard_generic_frame_unchanged_with_basis():
    """通用卡正常 + 护栏未生效帧逐位不变(§4 清单):基准非空但全帧无
    出域候选 → 与无持有帧 idx/reason/total 逐位一致(tag 不加前缀)。"""
    frame = ['嘴硬', '二极管', '免费升舱']
    held = _decide_pick(frame, _gs_holding(env='命运圣杯邀请'))
    bare = _decide_pick(frame, _fresh_gs())
    assert (held.idx, held.reason, held.total) == \
        (bare.idx, bare.reason, bare.total)


def test_guard_scopeless_holdings_zero_anchor_frame():
    """无指向持有帧(§4 清单):只持打捞人才库(指向集空)→ 基准空 →
    护栏不辖;零证据锚缺失帧定义卡按组件分竞争(黑塔纪元赠卡 50 胜——
    定义型分区退役后的数值语义,锚点亮支配由方向分承载;原现金锚藏一手
    R1 改判后零分出局)。"""
    out = _decide_pick(['黑塔纪元', '本姑娘就是罗刹', '藏一手'],
                       _gs_holding(strategies=('打捞人才库',)))
    assert out.idx == 0 and out.total == 50.0
    assert out.reason.startswith('pick total='), '护栏不辖帧无前缀'


def test_guard_all_off_direction_falls_back_full_argmax():
    """全出域回退(§4 清单):圣杯基下三候选全出域 → 回退全候选 argmax
    (不制造空选),回退域内按组件总分裁决(定义型分区已退役,黑塔纪元
    赠卡 50 胜),标签按管线序拼接。"""
    out = _decide_pick(['黑塔纪元', '琼玉专家:青雀', '列车同行星徽'],
                       _gs_holding(env='命运圣杯邀请'))
    assert out.idx == 0   # 黑塔纪元:回退域内赠卡分最高
    assert out.reason.startswith('off-direction fallback pick total=')


def test_guard_refresh_off_slot_in_action_not_frame_top():
    """刷新交互(§4 清单):出域定义型卡不入帧级顶级判定(对照:无持有
    帧 test_refresh_blocked_by_defining_top 同帧整帧不刷)且出域槽恒入
    动作集(占槽应刷掉换本线卡机会)。"""
    out = invest_strategy.decide(['黑塔纪元', '嘴硬', '二极管'],
                                 _gs_holding(env='命运圣杯邀请'),
                                 '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert out.slots == (0, 1, 2)


def test_guard_refresh_unique_l1_excludes_off_slot():
    """刷新交互·L1 剔除(§4 清单):唯一非血槽恰为出域槽 → 与被禁同款
    不算 L1,F2 守卫不保护它(否则动作集被摘空,出域槽刷不掉)。"""
    out = invest_strategy.decide(
        ['琼玉专家:青雀', '奋斗协议', '不等价交换'],
        _gs_holding(env='命运圣杯邀请'),
        '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, StrategyRefreshSuggestion)
    assert out.slots == (0, 1, 2)


def test_guard_reason_grammar_off_direction_then_blood_forced():
    """reason 文法锁(护栏设计 §2.3):标签按管线序拼接、空格分隔——
    出域过滤后非血域掏空 → off-direction → blood-forced → pick total=。"""
    out = _decide_pick(['黑塔纪元', '奋斗协议', '不等价交换'],
                       _gs_holding(env='命运圣杯邀请'))
    assert out.reason.startswith('off-direction blood-forced pick total=')


def test_guard_reason_grammar_off_direction_then_direction_score():
    """reason 文法锁·方向分支(统一阵容评分迭代):锁定景元仙舟帧
    (基准 = {仙舟}),黑塔纪元出域、飞光·映月(仙舟)兼容 → off-direction
    → 飞光方向分 500(+赠卡)胜出(定义型分区退役,支配数值化)。"""
    out = _decide_pick(['黑塔纪元', '飞光·映月', '嘴硬'], _fresh_gs(),
                       locked_comp='景元仙舟')
    assert out.idx == 1
    assert out.reason.startswith('off-direction pick total=')


def test_guard_lock_switch_held_mistake_not_in_basis():
    """锁定换基·历史误持不入基(§4 清单):误持黑塔纪元后锁双王圣杯,
    基准 = 锁线 factions(不并持有)→ 银河学者星徽照排出域,圣杯兼容卡
    胜出。"""
    gs = _gs_holding(strategies=('黑塔纪元',))
    out = _decide_pick(['银河学者星徽', '命运圣杯星徽', '嘴硬'], gs,
                       locked_comp='双王圣杯')
    assert out.idx == 1
    assert out.reason.startswith('off-direction')


def test_guard_lock_switch_tighten_energy_becomes_off():
    """锁定换基·收紧(护栏设计 §2.3 基准演化申报):持命运圣杯邀请(旧基
    含能量)后锁命运圣杯红A(新基 = {命运圣杯})→ 能量星徽由兼容变出域。"""
    gs = _gs_holding(env='命运圣杯邀请')
    out = _decide_pick(['能量星徽', '嘴硬', '二极管'], gs,
                       locked_comp='命运圣杯红A')
    assert out.idx != 0
    assert out.reason.startswith('off-direction')


def test_guard_lock_switch_relax_pursuit_compatible_after_lock():
    """锁定换基·放松(护栏设计 §2.3 基准演化申报):持减益概念股(旧基
    {减益})后兜底锁追击飞霄(新基 = {追击})→ 追击星徽由出域变兼容,
    胜出且无护栏前缀。"""
    gs = _gs_holding(env='减益概念股')
    out = _decide_pick(['追击星徽', '嘴硬', '二极管'], gs,
                       locked_comp='追击飞霄')
    assert out.idx == 0
    assert out.reason.startswith('pick total=')


def test_guard_demoted_frame_falls_back_to_holdings_basis():
    """锁定换基·降格帧(demoted_endgame,前瞻语义,护栏设计 §2.2/§2.6):
    锁线不入基,基准回持有指向并集——误持黑塔纪元({银河学者})+ 降格,
    银河学者星徽按持有兼容合法胜出(降格帧锚点回候选首名 = 大黑塔
    银河学者〔+500 通道〕→ 星徽方向分 150 加成);命运圣杯星徽对持有基
    冲突出域(帧级 off-direction 标记;降格 = 终局方向暂席,锁线阵营
    不再保护)。"""
    gs = _gs_holding(strategies=('黑塔纪元',))
    out = _decide_pick(['银河学者星徽', '命运圣杯星徽', '嘴硬'], gs,
                       locked_comp='双王圣杯', demoted_endgame=True)
    assert out.idx == 0, '持有兼容卡 + 方向分胜出(降格回持有基)'
    assert out.reason.startswith('off-direction')


# ==================== ⑬ 阵容冲突护栏·环境屏(env 支)====================
# 判据 = changes/2026-10-17-invest-direction-guard/design.md §2.2/§2.4。
# 出域槽并入 env 屏既有 excluded 槽位表通道(禁选/自拆台同路):闸过先
# 建议刷新、闸尽落选出域已排除、全出域走既有 all-excluded 回退。期望值
# 全部注册表现算,持有写入沿 ⑫ 节 _gs_holding helper(观察真值形态)。
# 候选环境指向集(kernel test_cw_investments 同源事实):仙舟概念股→
# {仙舟};列车同行概念股→{列车同行};减益概念股→{减益};命运圣杯邀请/
# 契约→{命运圣杯, 能量};时代族/经济类→∅(通用)。

def test_env_guard_conflict_env_suggests_refresh_via_forbidden_channel():
    """持有指向帧+冲突环境排除(§4 env 清单):持命运圣杯邀请(基准 =
    {命运圣杯, 能量}),仙舟概念股({仙舟})与基准零交 = 出域槽 →
    走既有禁选通道先建议刷新。reason 断言钉死「禁选分支专属归因串」
    (阈值分支的归因串形态不同)——护栏触发与用户禁选同路同形,
    零新出口形态(护栏设计 §2.4)。"""
    gs = _gs_holding(env='命运圣杯邀请')
    _env_set_refresh_left(gs, 1)
    out = invest_env.decide(['仙舟概念股', '命运圣杯契约', '黄金时代'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, RefreshSuggestion)
    assert out.reason == 'refresh: 禁选槽存在'


def test_env_guard_gate_exhausted_picks_compatible_excluding_off():
    """次数闸尽落 pick 时出域已排除(护栏设计 §2.4 闸尽半边):同帧闸 0
    → 常规选卡,兼容环境(命运圣杯契约,指向集与基准有交)胜出,出域槽
    (仙舟概念股)不入竞争;decide_pick 同基线零漂移(memo 落选卡口)。"""
    frame = ['仙舟概念股', '命运圣杯契约', '黄金时代']
    gs = _gs_holding(env='命运圣杯邀请')
    _env_set_refresh_left(gs, 0)
    d1 = invest_env.decide(frame, gs, '', False, frozenset(),
                           _ENV_EMPTY_CONFIG)
    d2 = invest_env.decide_pick(frame, gs, '', False, frozenset(),
                                _ENV_EMPTY_CONFIG)
    assert isinstance(d1, InvestEnvDecision)
    assert d1.idx == 1 and d1.reason.startswith('pick total=')
    assert (d2.idx, d2.reason) == (d1.idx, d1.reason)


def test_env_guard_all_off_frame_gate_exhausted_falls_back():
    """全出域+闸尽回退(§4 env 清单):圣杯基下三概念股全出域(指向集
    两两异阵营且与基准零交)→ 次数闸尽走既有 all-excluded 回退(对全体
    候选取 argmax 最不负分者,不制造空选)。"""
    gs = _gs_holding(env='命运圣杯邀请')
    _env_set_refresh_left(gs, 0)
    out = invest_env.decide(['仙舟概念股', '列车同行概念股', '减益概念股'],
                            gs, '', False, frozenset(), _ENV_EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx in (0, 1, 2)
    assert out.reason.startswith('all-excluded-fallback')


def test_env_guard_scopeless_holdings_frame_identical():
    """无指向持有帧零变化(§4 env 清单):只持打捞人才库(策略指向集空)
    → 基准空 → 护栏不辖,出域风险候选帧与无持有帧逐位一致(§2.3 规则表
    行 1)。"""
    frame = ['仙舟概念股', '列车同行概念股', '减益概念股']
    gs_held = _gs_holding(strategies=('打捞人才库',))
    _env_set_refresh_left(gs_held, 0)
    held = invest_env.decide(frame, gs_held, '', False, frozenset(),
                             _ENV_EMPTY_CONFIG)
    gs_bare = _fresh_gs()
    _env_set_refresh_left(gs_bare, 0)
    bare = invest_env.decide(frame, gs_bare, '', False, frozenset(),
                             _ENV_EMPTY_CONFIG)
    assert isinstance(held, InvestEnvDecision)
    assert (held.idx, held.reason) == (bare.idx, bare.reason)


def test_env_guard_universal_envs_normal_with_basis():
    """通用环境正常(§4 env 清单):基准非空(持命运圣杯邀请)但候选全
    为通用环境(时代族/经济类,指向集空)→ 无出域,与无持有帧逐位一致
    (通用卡全帧零变化,§2.3 规则表行 2)。"""
    frame = ['彩虹时代', '增发货币', '黄金时代']
    gs_held = _gs_holding(env='命运圣杯邀请')
    _env_set_refresh_left(gs_held, 0)
    held = invest_env.decide(frame, gs_held, '', False, frozenset(),
                             _ENV_EMPTY_CONFIG)
    gs_bare = _fresh_gs()
    _env_set_refresh_left(gs_bare, 0)
    bare = invest_env.decide(frame, gs_bare, '', False, frozenset(),
                             _ENV_EMPTY_CONFIG)
    assert isinstance(held, InvestEnvDecision)
    assert (held.idx, held.reason) == (bare.idx, bare.reason)


# ==================== ⑩ 次名分量遥测 margin(pick-margin-telemetry
# ====================  design §2.2-1/§2.2-2;纯观测,决策面零消费)====================

def test_env_margin_value_order_and_excluded_not_in_domain():
    """env 值序与排除域(design §2.2-1):margin 键形 =
    {runner_up, runner_up_total, margin},次名 = 竞争域内除胜者外首个
    最高分(平分取先,与 argmax 同款语义);被禁槽不入竞争域——即使
    分高也不入次名。"""
    # 火药味(立场 10)胜;彩虹时代/头彩同 0 分 → 次名取先 = 彩虹时代。
    gs = _fresh_gs()
    out = invest_env.decide_pick(['火药味', '彩虹时代', '头彩'], gs, '',
                                 False, frozenset(), _ENV_EMPTY_CONFIG)
    assert out.idx == 0
    assert out.margin == {'runner_up': '彩虹时代', 'runner_up_total': 0.0,
                          'margin': 10.0}
    # 被禁槽不入域:禁火药味(最高分)→ 竞争域 = 彩虹/头彩,胜者彩虹
    #(平分取先),次名头彩;火药味 10 分不进 margin。
    cfg = SimpleNamespace(env_priority=[], env_forbid=['火药味'])
    out2 = invest_env.decide_pick(['火药味', '彩虹时代', '头彩'], gs, '',
                                  False, frozenset(), cfg)
    assert out2.idx == 1
    assert out2.margin == {'runner_up': '头彩', 'runner_up_total': 0.0,
                           'margin': 0.0}


def test_env_margin_boundary_three_forms():
    """env 边界值表三形态(design §2.2-1):竞争域仅 1 候选 → 三键
    null;全排除退化帧 → 按全体域取次名(reason tag 已携退化标记供
    判读);空候选帧 → 不落值 None。"""
    gs = _fresh_gs()
    # 形态一:竞争域仅 1 候选(两禁一活)→ 无次名。
    cfg1 = SimpleNamespace(env_priority=[],
                           env_forbid=['彩虹时代', '头彩'])
    out1 = invest_env.decide_pick(['火药味', '彩虹时代', '头彩'], gs, '',
                                  False, frozenset(), cfg1)
    assert out1.margin == {'runner_up': None, 'runner_up_total': None,
                           'margin': None}
    # 形态二:全排除退化帧 → 全体域次名(与胜者同域,含被禁候选)。
    cfg2 = SimpleNamespace(env_priority=[],
                           env_forbid=['火药味', '彩虹时代', '头彩'])
    out2 = invest_env.decide_pick(['火药味', '彩虹时代', '头彩'], gs, '',
                                  False, frozenset(), cfg2)
    assert out2.reason.startswith('all-excluded-fallback')
    assert out2.margin == {'runner_up': '彩虹时代', 'runner_up_total': 0.0,
                           'margin': 10.0}
    # 形态三:空候选帧(入口防御退化)→ 不落值。
    out3 = invest_env.decide_pick([], gs, '', False, frozenset(),
                                  _ENV_EMPTY_CONFIG)
    assert out3.margin is None


def test_strategy_margin_value_and_domain():
    """策略面值序与竞争域(design §2.2-2):次名 = 结构分区竞争域内
    除胜者外按同一平分裁决键的最高者(决议:娱乐星球 50 金胜,嘴硬 6
    分次);被禁槽不入域(50 分的决议:娱乐星球被禁后不进 margin)。
    (面值锚原 = 藏一手 80,R1 用户裁定 2026-11-04 反向改判零分后换锚,
    面值例现役归属见 test_cash_instant_gold_face_value。)"""
    gs = _fresh_gs()
    out = _decide_pick(['决议:娱乐星球', '嘴硬', '二极管'], gs)
    assert out.margin == {'runner_up': '嘴硬', 'runner_up_total': 6.0,
                          'margin': 44.0}
    cfg = SimpleNamespace(strategy_priority=[],
                          strategy_forbid=['决议:娱乐星球'])
    out2 = invest_strategy.decide_pick(['决议:娱乐星球', '嘴硬', '二极管'],
                                       gs, '', False, frozenset(), cfg)
    # 嘴硬/二极管同为 6 分(现金分真值):胜者嘴硬(平分裁决键取先),
    # 次名二极管 margin = 0;决议:娱乐星球 50 分被禁不入域。
    assert out2.margin == {'runner_up': '二极管', 'runner_up_total': 6.0,
                           'margin': 0.0}


def test_strategy_margin_single_domain_null_and_empty_frame():
    """策略面边界(design §2.2-2 同款边界值表):竞争域仅 1 候选 →
    三键 null;空候选帧不进评分帧(入口防御)→ margin None。"""
    gs = _fresh_gs()
    cfg = SimpleNamespace(strategy_priority=[], strategy_forbid=['二极管'])
    out = invest_strategy.decide_pick(['嘴硬', '二极管'], gs, '', False,
                                      frozenset(), cfg)
    assert out.margin == {'runner_up': None, 'runner_up_total': None,
                          'margin': None}
    empty = invest_strategy.decide_pick([], gs, '', False, frozenset(),
                                        _EMPTY_CONFIG)
    assert empty.margin is None


def test_flow_pick_actions_carry_margin():
    """词表通道拷入(design §2.1):flow 选卡动作实例携带决策产物
    margin(经词表动作字段 margin 到达 payload 组装面,不入动作实例键);
    建议帧动作无该载荷(getattr → None,不误落)。值序恒等式:
    runner_up_total + margin == 胜者总分(reason 的 pick total)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionPickInvestStrategyParam,
    )
    # env 选卡帧(高分帧不触发刷新建议)。
    gs = _fresh_gs()
    _env_write_frame(gs, ['仙舟概念股', '列车同行概念股', '减益概念股'], 1)
    out = _env_wired_strategy(gs).decide_invest_env()
    assert isinstance(out, CwActionPickInvestEnvParam)
    assert out.margin is not None
    assert out.margin['runner_up'] == '列车同行概念股'
    assert out.margin['runner_up_total'] + out.margin['margin'] == 50.0, \
        '次名总分 + 差值 = 胜者总分(值序恒等式,胜者 gift 50)'
    # 策略轴选卡帧(候选 2 张,帧级门失败不刷)。
    gs2 = _fresh_gs()
    gs2.write_logic(gs2.invest_strategy_opts, ['远见', '利息上调'],
                    produced_by='cw-invest-env-test', sig=_ENV_SIG_LOGIC)
    out2 = _env_wired_strategy(gs2).decide_invest_strategy()
    assert isinstance(out2, CwActionPickInvestStrategyParam)
    assert out2.margin == {'runner_up': '远见', 'runner_up_total': 15.0,
                           'margin': 10.0}
    # 建议帧(低分发刷新):动作不带 margin 载荷。
    gs_low = _fresh_gs()
    _env_write_frame(gs_low, ['彩虹时代', '黄金时代', '白银时代'], 1)
    out_low = _env_wired_strategy(gs_low).decide_invest_env()
    assert not isinstance(out_low, CwActionPickInvestEnvParam)
    assert getattr(out_low, 'margin', None) is None
