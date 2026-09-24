"""投资环境策略层迁移 3.1 单测(纯新增阶段;判据 = landing.md §3.1 ①-⑦)。

设计依据 = docs/develop/sr_od/application/currency_war/changes/
2026-09-23-invest-env-strategy-migration/design.md §2.2-§2.9(下称 design §)
与 landing.md §3.1 完成判据。3.1 期策略层新文件与 kernel 旧机并存;3.2 起
接线生效,本文件补 flow 消费侧锁面(见下)。

判据映射:
- ① 方向分序(line_value 三口径:注册表真实数据列车同行 S > 减益 A >
  仙舟 B;锁线不含该阵营 → 0;evicted 收窄 → 0);
- ② 赠卡分(gift_value:战技点契约 = core 白得高分;全员集外 → 0;
  advisor 减半;随机阵营 = 成员档位平均);
- ③ 时代族 6 条总分 = 0(design §2.6 表 3 零值裁定);
- ④ 现金分(增发货币 > 0 且 resolved;缺参 = 0 不炸;长线利好 50 /
  二手市场 30 拍值 = design §2.3/P97 §7);
- ⑤ 刷新三态(禁选必刷 / 低分帧+剩余 ≥1 刷 / 高分帧不刷,含次数闸);
- ⑥ 自拆台排除(板面 DoT/减益 ≥2 时克制者排除,机制归一调 kernel 表);
- ⑦ 构建校验(立场表缺行即炸 + 系数表键完备)。

追加锁面(3.1 验收 reviewer 派回):全排除退化帧两态(次数闸关 →
all-excluded-fallback 退化选卡 / 剩余 ≥1 → 建议刷);系数表缺键拒绝锁。
校验「import 即炸」的接线面按 reviewer 裁定归 3.2 消费侧行为覆盖,本文件
只锁校验逻辑本体(直接调校验入口 + 篡改表副本断言抛错,不用 reload /
源码扫描)。

追加锁面(3.2 验收 reviewer 必修单):flow 消费侧接线锁四条——env 帧路由
与动作包装 / memo 三态 / decide 与 decide_pick 零漂移 / 策略轴接线
(兑现上文「归 3.2 消费侧行为覆盖」的义务申报)。投资策略屏迁移批 3.2
接线落地:策略轴回归锁改指策略层新语义(reason 形态 ``pick total=``,
原「仍走 kernel」锁退役)+ 增补策略轴 memo 三态锁(落选卡取数口 =
invest_strategy.decide_pick)。

测试纪律:零真实副作用(不写项目目录、不发网络);断言锁设计语义而非
实现细节;断言依据 = 注册表真实数据(提交进仓)与本文件自造输入。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_ENVS,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    invest_env,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    env_economy_value,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
    named_gift_value,
    random_faction_gift_value,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.invest_env import (
    InvestEnvDecision,
    RefreshSuggestion,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.line_value import (
    line_value,
)

_SIG_LOGIC = ChannelSig(family='logic_action', actor='cw-invest-env-test',
                        mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='cw-invest-env-test',
                      mode='synthesized')

#: 零转向配置(禁测用户轴语义时使用;decide 不要求 config 具体类型)
_EMPTY_CONFIG = SimpleNamespace(env_priority=[], env_forbid=[])

#: 时代族 6 条(design §2.6 表 3 零值裁定行)
_ERA_ENVS = ('彩虹时代', '黄金时代', '白银时代', '头彩', '尾彩', '银·金·彩')


def _fresh_gs() -> GameState:
    """独立容器(桩 session 宿主;弱引用表按宿主隔离,零跨测残留)。"""
    return game_state_of(SimpleNamespace())


def _set_refresh_left(gs: GameState, left: int) -> None:
    """写环境刷新剩余次数(容器观察真值形态;次数闸 = ≥1,design §2.7)。"""
    gs.write_logic(gs.env_refresh_left, left, produced_by='cw-invest-env-test',
                   sig=_SIG_LOGIC)


# ==================== ① 方向分序(design §2.4)====================

def test_direction_score_ordering_over_registry():
    """注册表真实数据三口径序:列车同行(S 线阵营)> 减益(A)> 仙舟(B)。"""
    assert line_value('列车同行', '', False, frozenset()) == 100.0
    assert line_value('减益', '', False, frozenset()) == 60.0
    assert line_value('仙舟', '', False, frozenset()) == 30.0


def test_direction_locked_comp_without_faction_is_zero():
    """锁线不含该阵营 → 0(design §2.4 口径 2);锁线命中 → 锁线档分。"""
    # 锁线列车同行(无仙舟阵营)→ 仙舟方向分 0
    assert line_value('仙舟', '列车同行', False, frozenset()) == 0.0
    # 锁线命中该阵营 → 取锁线档(非先验 max)
    assert line_value('列车同行', '列车同行', False, frozenset()) == 100.0
    assert line_value('仙舟', '景元仙舟', False, frozenset()) == 30.0


def test_direction_demoted_frame_ignores_lock():
    """降格帧按未锁线口径(忽略锁线;design §2.4 口径 3)。"""
    assert line_value('仙舟', '列车同行', True, frozenset()) == 30.0


def test_direction_evicted_narrowing_kills_line():
    """evicted 收窄后线退场 → 0:唯一仙舟线(景元仙舟)被排除。"""
    assert line_value('仙舟', '', False, frozenset({'景元仙舟'})) == 0.0


def test_decide_picks_strongest_direction_over_frame():
    """决策面方向序:三概念股同帧,列车同行概念股(S)胜出。"""
    out = invest_env.decide(
        ['仙舟概念股', '列车同行概念股', '减益概念股'],
        _fresh_gs(), '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 1


# ==================== ② 赠卡分(design §2.5)====================

def test_named_gift_direct_core_scores_high():
    """战技点契约 = 丹恒·饮月+花火 双 core 白得 → core 档高分(50)。"""
    assert named_gift_value('战技点契约', frozenset()) == 50.0


def test_named_gift_all_evicted_is_zero_not_disqualified():
    """全员集外 → 赠卡分自然 0;整环境失格规则已删(design §2.5),
    环境其余成分照常计分——锁语义:总分公式仍成立而非整体清零。"""
    all_comps = frozenset(c.name for c in COMP_LIBRARY)
    assert named_gift_value('战技点契约', all_comps) == 0.0
    gs = _fresh_gs()
    _set_refresh_left(gs, 0)   # 关次数闸,强制返回选卡决策
    out = invest_env.decide(['战技点契约'], gs, '', False, all_comps,
                            _EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


def test_named_gift_advisor_halved():
    """advisor(付费顾问期权)按同档分 × 0.5:特邀专家:桑博 = core → 25。"""
    assert named_gift_value('特邀专家:桑博', frozenset()) == 25.0


def test_random_faction_gift_is_member_tier_average():
    """随机阵营赠卡 = 成员档位算术平均(design §2.5 无偏口径):
    量子同频注册成员中缇宝/花火/希儿/符玄 core + 银狼 shared →
    (4×50 + 20) / 5 = 44。"""
    assert random_faction_gift_value('量子同频', frozenset()) == 44.0


def test_random_faction_gift_no_member_in_rosters_is_zero():
    """无成员在册 → 0(全员 evicted 后三名单皆不在,除零防)。"""
    all_comps = frozenset(c.name for c in COMP_LIBRARY)
    assert random_faction_gift_value('量子同频', all_comps) == 0.0


# ==================== ③ 时代族 6 条总分 = 0(design §2.6 表 3)====================

def test_era_family_total_is_zero():
    """时代族 6 条总分 = 0:品质重排只是换随机方式,整体期望不变
    (用户裁定 2026-09-23);现金通道(品质改写层 E)fail-closed,
    无阵营无赠卡,立场登记 0。"""
    gs = _fresh_gs()
    for name in _ERA_ENVS:
        assert invest_env.option_total(name, gs) == 0.0, name


# ==================== ④ 现金分(design §2.3)====================

def test_cash_inflation_positive_and_resolved():
    """增发货币:A 类精确通道,开局全局期望 > 0 且 resolved。"""
    value, resolved = env_economy_value('增发货币', _fresh_gs())
    assert resolved is True
    assert value > 0.0


def test_cash_missing_estimate_failclosed_zero_without_raise():
    """缺参环境(C 类零有效估计)→ fail-closed (0.0, False),不炸。"""
    assert env_economy_value('经济过热', _fresh_gs()) == (0.0, False)


def test_cash_refresh_envs_fixed_registered_values():
    """长线利好 = 50 / 二手市场 = 30 拍值注册(design §2.3;锚 =
    proofs/p97-refresh-budget.md §7,无条件计,不读局内刷新计数)。"""
    assert env_economy_value('长线利好', _fresh_gs()) == (50.0, True)
    assert env_economy_value('二手市场', _fresh_gs()) == (30.0, True)


# ==================== ⑤ 刷新三态(design §2.7)====================

def test_refresh_forbidden_slot_suggests_refresh():
    """禁选必刷:帧内存在禁选槽 → RefreshSuggestion(剩余 ≥1)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 1)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['列车同行'])
    out = invest_env.decide(['列车同行概念股', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), cfg)
    assert isinstance(out, RefreshSuggestion)


def test_refresh_low_score_frame_with_budget_suggests():
    """低分帧(全 0 值 < 阈值)+ 剩余 ≥1 → RefreshSuggestion。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 1)
    out = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, RefreshSuggestion)


def test_refresh_high_score_frame_picks_instead():
    """高分帧(S 线方向分 > 阈值)→ 不刷,直接选卡。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 1)
    out = invest_env.decide(['列车同行概念股', '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


def test_refresh_count_gate_blocks_suggestion():
    """次数闸:剩余 = 0(与未观察 None 同理 fail-closed)→ 不建议刷,
    低分帧退化为常规选卡(建议刷最终由 handler 双闸裁定,design §2.7)。"""
    gs_zero = _fresh_gs()
    _set_refresh_left(gs_zero, 0)
    out_zero = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                                 gs_zero, '', False, frozenset(),
                                 _EMPTY_CONFIG)
    assert isinstance(out_zero, InvestEnvDecision)
    # 剩余次数未观察(Field None = 读缺跳写)→ 次数 ≥1 无法确证 → 不刷
    out_unobserved = invest_env.decide(['彩虹时代', '黄金时代', '白银时代'],
                                       _fresh_gs(), '', False, frozenset(),
                                       _EMPTY_CONFIG)
    assert isinstance(out_unobserved, InvestEnvDecision)


def test_refresh_threshold_is_full_registry_mean():
    """阈值 = 全 83 条环境无轴总分的均值(构建期派生,单一源 = 表;
    design §2.7)。派生口径与运行时评分同基线(不含转向轴)。"""
    gs = _fresh_gs()
    total = sum(invest_env.option_total(n, gs) for n in INVESTMENT_ENVS)
    assert pytest.approx(total / len(INVESTMENT_ENVS)) == \
        invest_env.REFRESH_THRESHOLD
    # 阈值非退化:正成分存在(现金/方向/赠卡/立场)→ 均值 > 0;低于 S 线
    # 方向分(均值 ≤ 最大总分 < 单线满档 + 赠卡,判据不会把最强帧判低分)
    assert 0.0 < invest_env.REFRESH_THRESHOLD < 100.0


# ==================== ⑥ 自拆台排除(design §2.8)====================

#: 自拆台测试帧:「净化身心」词缀(tag 净化)克制 DoT/减益 —— 机制归一
#: 走 kernel AFFIX_MECHANIC_MAP/MECHANIC_COUNTERS 表;注册表无含该词缀的
#: 环境名,用合成选项名承载排除语义(未注册名组件恒 0,排除是结构规则
#: 非定价)。
_SELF_DEFEAT_OPT = '净化身心试验'


def test_self_defeat_counters_dot_excluded_from_board():
    """板面 持续伤害+减益 ≥2:克制 DoT/减益的候选被排除,平分取先落到
    次席(剩余次数置 0 关刷新建议,隔离次数闸)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 0)
    gs.observe(gs.board, {'持续伤害': 2}, evidence='test', sig=_SIG_OBS)
    out = invest_env.decide([_SELF_DEFEAT_OPT, '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 1


def test_no_self_defeat_without_dot_board():
    """板面无 DoT/减益 ≥2:不触发排除,同分并列取先(落首席)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 0)
    out = invest_env.decide([_SELF_DEFEAT_OPT, '黄金时代', '白银时代'],
                            gs, '', False, frozenset(), _EMPTY_CONFIG)
    assert isinstance(out, InvestEnvDecision)
    assert out.idx == 0


#: 全排除退化帧:三条概念股同被 env_forbid 子串命中(排除规则覆盖全体)。
_ALL_EXCLUDED_OPTS = ('仙舟概念股', '减益概念股', '击破概念股')


def test_all_excluded_frame_falls_back_to_decision():
    """全排除退化帧 + 次数闸关:排除规则失去选择面,落地件对全体候选
    (含被禁)取 argmax 最不负分者返回选卡决策,
    归因串以 all-excluded-fallback 开头——该帧会真发选卡动作,
    reason 是判读面唯一标识(不锁 idx:位次随阵容库注册值漂移,锁类型 +
    归因前缀即设计语义)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 0)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    out = invest_env.decide(list(_ALL_EXCLUDED_OPTS), gs, '', False,
                            frozenset(), cfg)
    assert isinstance(out, InvestEnvDecision)
    assert out.reason.startswith('all-excluded-fallback')


def test_all_excluded_frame_with_budget_suggests_refresh():
    """对照帧:同帧剩余 ≥1 → 禁选槽存在优先建议刷(排除规则有选择面,
    不做退化选卡;design §2.7 禁选槽 ∨ 低分即刷)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 1)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    out = invest_env.decide(list(_ALL_EXCLUDED_OPTS), gs, '', False,
                            frozenset(), cfg)
    assert isinstance(out, RefreshSuggestion)


# ==================== ⑦ 构建期校验(design §2.9)====================

def test_build_validation_missing_stance_row_raises(monkeypatch):
    """立场表缺行即炸:删「进化算法」(无机械成分环境)后校验抛 ValueError。
    (import 成功本身 = 真实全表已过校验的正面情形。)"""
    trimmed = dict(invest_env.STANCE_SCORE)
    trimmed.pop('进化算法')
    monkeypatch.setattr(invest_env, 'STANCE_SCORE', trimmed)
    with pytest.raises(ValueError, match='立场分表缺行'):
        invest_env._validate_stance_coverage()


def test_build_validation_orphan_stance_key_raises(monkeypatch):
    """立场表孤儿键(注册表无此环境)同样炸出。"""
    patched = dict(invest_env.STANCE_SCORE)
    patched['不存在的环境'] = invest_env.StanceRow(0.0, '孤儿键测试')
    monkeypatch.setattr(invest_env, 'STANCE_SCORE', patched)
    with pytest.raises(ValueError, match='孤儿键'):
        invest_env._validate_stance_coverage()


def test_build_validation_coefficient_tables_complete():
    """系数表键完备:线强度档覆盖 COMP_LIBRARY 全部档;赠卡档覆盖四档。
    (import 已过一遍;显式再验 = 锁校验函数自身行为。)"""
    invest_env._validate_coefficient_tables()   # 不抛 = 键完备
    from sr_od.application.currency_war.strategies.impl.mandate_v1.gift_value import (
        GIFT_TIER_SCORE,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.line_value import (
        LINE_STRENGTH_SCORE,
    )
    assert {'core', 'shared', 'transition', 'off'} <= set(GIFT_TIER_SCORE)
    assert {'S', 'A', 'B'} <= set(LINE_STRENGTH_SCORE)


def test_build_validation_coefficient_missing_key_raises(monkeypatch):
    """系数表缺键即炸(校验逻辑本体拒绝锁;import 接线面 = 3.2 消费侧行为
    覆盖,reviewer 裁定不在本批用 reload/源码扫描锁):线强度档缺 B 与
    赠卡档缺 transition 两分支各自拒绝。两段用独立 context 隔离——
    monkeypatch 默认测试级还原,同测试内前段篡改会泄漏进后段。"""
    with monkeypatch.context() as m:
        m.setattr(invest_env, 'LINE_STRENGTH_SCORE',
                  {k: v for k, v in invest_env.LINE_STRENGTH_SCORE.items()
                   if k != 'B'})
        with pytest.raises(ValueError, match='线强度档分缺键'):
            invest_env._validate_coefficient_tables()
    with monkeypatch.context() as m:
        m.setattr(invest_env, 'GIFT_TIER_SCORE',
                  {k: v for k, v in invest_env.GIFT_TIER_SCORE.items()
                   if k != 'transition'})
        with pytest.raises(ValueError, match='赠卡档分缺键'):
            invest_env._validate_coefficient_tables()


# ==================== flow 消费侧接线锁(3.2 接线;模块头申报义务)====================

def _wired_strategy(gs: GameState):
    """活策略核(生产注册壳 mandate_v1.bridge 具现;决策入口 = CwFlowStrategy
    继承链。零真实副作用:容器桩 session 宿主隔离,config 桩缺省 =
    转向轴全空)。"""
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import bridge
    return bridge.MandateV1Strategy(gs, SimpleNamespace(strategy_seed=None))


def _write_env_frame(gs: GameState, options: list[str], refresh_left: int) -> None:
    """写 env 帧 slots(候选 + 刷新余量;观察真值形态)。"""
    gs.write_logic(gs.invest_env_opts, options,
                   produced_by='cw-invest-env-test', sig=_SIG_LOGIC)
    gs.write_logic(gs.env_refresh_left, refresh_left,
                   produced_by='cw-invest-env-test', sig=_SIG_LOGIC)


def test_flow_env_frame_routes_and_wraps_actions():
    """a. env 帧路由+动作包装:高分帧(有余量)→ CwActionPickInvestEnvParam;
    低分帧(有余量)→ CwActionRefreshInvestCardsParam 且 slots = 全帧槽位
    (环境屏整组重掷单全局钮,slots = 真值哨兵)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionRefreshInvestCardsParam,
    )
    gs = _fresh_gs()
    _write_env_frame(gs, ['仙舟概念股', '列车同行概念股', '减益概念股'], 1)
    out = _wired_strategy(gs).decide_invest_env()
    assert isinstance(out, CwActionPickInvestEnvParam)
    assert out.idx == 1   # 列车同行概念股(S 线方向分胜出)
    gs_low = _fresh_gs()
    _write_env_frame(gs_low, ['彩虹时代', '黄金时代', '白银时代'], 1)
    out_low = _wired_strategy(gs_low).decide_invest_env()
    assert isinstance(out_low, CwActionRefreshInvestCardsParam)
    assert out_low.slots == (0, 1, 2)


def test_flow_env_frame_memo_three_states():
    """b. memo 三态(design §2.9 同帧去重语义):首调发建议写 memo → 同候选
    重调落选卡(handler 刷新闸全败回退契约)→ 再调恢复首调建议(键清;
    行为面证明,不摸 scratch 内部)。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestEnvParam,
        CwActionRefreshInvestCardsParam,
    )
    gs = _fresh_gs()
    _write_env_frame(gs, ['彩虹时代', '黄金时代', '白银时代'], 1)
    strategy = _wired_strategy(gs)
    first = strategy.decide_invest_env()
    assert isinstance(first, CwActionRefreshInvestCardsParam)
    again = strategy.decide_invest_env()
    assert isinstance(again, CwActionPickInvestEnvParam)
    third = strategy.decide_invest_env()
    assert isinstance(third, CwActionRefreshInvestCardsParam)


def test_decide_and_decide_pick_agree():
    """c. decide 与 decide_pick 零漂移:同帧同 idx 同 reason(同一评分基线,
    memo 落选卡的语义承载);至少含全排除退化帧一例(memo 命中恰落的形态)。"""
    gs = _fresh_gs()
    _set_refresh_left(gs, 0)
    cfg = SimpleNamespace(env_priority=[], env_forbid=['概念股'])
    opts = list(_ALL_EXCLUDED_OPTS)
    d1 = invest_env.decide(opts, gs, '', False, frozenset(), cfg)
    d2 = invest_env.decide_pick(opts, gs, '', False, frozenset(), cfg)
    assert isinstance(d1, InvestEnvDecision)
    assert d1.reason.startswith('all-excluded-fallback')
    assert (d2.idx, d2.reason) == (d1.idx, d1.reason)
    # 正常高分帧同基线(非退化形态)
    gs_hi = _fresh_gs()
    _set_refresh_left(gs_hi, 1)
    hi = ['仙舟概念股', '列车同行概念股', '减益概念股']
    h1 = invest_env.decide(hi, gs_hi, '', False, frozenset(), _EMPTY_CONFIG)
    h2 = invest_env.decide_pick(hi, gs_hi, '', False, frozenset(), _EMPTY_CONFIG)
    assert (h2.idx, h2.reason) == (h1.idx, h1.reason)


def test_flow_strategy_axis_strategy_layer_reason_shape():
    """d. 策略轴接线回归:kind='strategy' 走策略层 ``invest_strategy.decide``——
    产物 = CwActionPickInvestStrategyParam 且 reason 为策略层新机签名
    形态 ``pick total=...`` 前缀(归因来源可辨);idx 落在候选域。"""
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestStrategyParam,
    )
    gs = _fresh_gs()
    gs.write_logic(gs.invest_strategy_opts, ['远见', '利息上调'],
                   produced_by='cw-invest-env-test', sig=_SIG_LOGIC)
    out = _wired_strategy(gs).decide_invest_strategy()
    assert isinstance(out, CwActionPickInvestStrategyParam)
    assert out.idx in (0, 1)
    assert out.reason.startswith('pick total=')
    assert 'score=' not in out.reason


#: 策略轴建议帧(三张精确低分卡:帧级门过、全槽可刷——同帧取自
#: test_cw_invest_strategy.py 刷新判据锁,注册表真实数据)。
_STRATEGY_REFRESH_FRAME = ['嘴硬', '二极管', '免费升舱']


def _write_strategy_frame(gs: GameState, options: list[str]) -> None:
    """写策略帧 slots(候选;观察真值形态)。"""
    gs.write_logic(gs.invest_strategy_opts, options,
                   produced_by='cw-invest-env-test', sig=_SIG_LOGIC)


def test_flow_strategy_frame_memo_three_states():
    """e. 策略轴 memo 三态(迁移批 design §2.10 同帧去重语义;缺 decide_pick
    落选卡口则建议帧三闸全败时 op round_fail 的行为缺口锁):建议帧首调发
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
    strategy = _wired_strategy(gs)
    first = strategy.decide_invest_strategy()
    assert isinstance(first, CwActionRefreshInvestCardsParam)
    assert first.slots == (0, 1, 2)
    again = strategy.decide_invest_strategy()
    assert isinstance(again, CwActionPickInvestStrategyParam)
    assert again.reason.startswith('pick total=')
    third = strategy.decide_invest_strategy()
    assert isinstance(third, CwActionRefreshInvestCardsParam)
