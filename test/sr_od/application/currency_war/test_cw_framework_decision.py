"""过渡框架判定核心四符号锁:pick_framework / transition_score /
_framework_counts(kernel/cw_transition)+ decision_target(kernel/cw_recipe)。

背景(改动三审覆盖缺口申报,账本 T-16):P1 框架选线决策核心在双轨接线
(transition_framework 写端激活)前零覆盖——现域休门(零写端),锁必须
写在新数据语义上:TRANSITION_PACK/FRAMEWORK_FACTIONS 权威副本 =
knowledge/cw_line_facts(花火=('量子','carry') 修正已传播)。

期望源 = kernel 现行实现(判据数值出自 cw_transition.pick_framework/
transition_score docstring:plaza 784 篇 V4.4 数据实证 + MC 2000 局预囤
实证)与 knowledge/cw_line_facts 数据。玩法文档(docs/game/currency_war/
research/transitions.md、final_comps/*.md)载过渡双框架主流占比与 portal
信号存在性,不载滞回/偏置权/启动门数值判据——实现与玩法文档无分叉,
全部按现行实现如实锁。
"""
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_recipe import (
    decision_target,
    recipe_comp,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_transition import (
    _framework_counts,
    pick_framework,
    transition_score,
)
from sr_od.application.currency_war.kernel.cw_game_state import Unit
from sr_od.application.currency_war.kernel.cw_vocab import ShopCard


def _sig() -> ChannelSig:
    """渠道①签名(obs 族;观察写入口签名必填,ADR-0634)。"""
    return ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _gs(*, plane: int = 1) -> GameState:
    """容器:缺省未观察节点(plane_of 缺省 1);plane=2 写节点键。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if plane != 1:
        gs.observe(gs.node, NodeKey(plane=plane, round_num=1, kind='prep'),
                   sig=_sig())
    return gs


def _bc(name: str) -> Unit:
    """持有件(备战/上阵同型,char_id 载名;计数面鸭子读 = char_id)。"""
    return Unit(char_id=name, star=1)


def _card(name: str) -> ShopCard:
    """在售店卡(name 载名)。"""
    return ShopCard(x=0, name=name)


# ============================================================ _framework_counts


def test_framework_counts_owned_vs_merged_semantics() -> None:
    """计数语义:owned = deployed+bench 整权(bot 真持有,None 槽跳过);
    counts = owned + 商店在售 0.5/张(在售 = 即可得);三框架全键零值
    初始化。花火 = 量子线(knowledge/cw_line_facts 花火=('量子','carry'):
    注册表花火 = 盛会之星阵营+量子同频流派,无列车同行——计数归属量子,
    列车计数不受污染)。通用件(千冶·刃)不入任何框架键。

    场景:deployed=[藿藿,千冶·刃] + bench=[花火,None] + 店=[三月七×2]
    → owned={仙舟:1, 列车:0, 量子:1};counts={仙舟:1.0, 列车:1.0,
    量子:1.0}(两张在售三月七 = 列车 +1.0)。
    """
    owned, counts = _framework_counts(
        bench=[_bc('花火'), None],
        deployed=[_bc('藿藿'), _bc('千冶·刃')],
        shop=[_card('三月七'), _card('三月七')])
    assert owned == {'仙舟': 1, '列车': 0, '量子': 1}
    assert counts == {'仙舟': 1.0, '列车': 1.0, '量子': 1.0}


# ============================================================ pick_framework


def test_pick_framework_startup_gate_merged_weight() -> None:
    """启动门(合并权 ≥1.5):纯 shop 半权不够——2 张在售 = 1.0 < 1.5,
    防刷新噪声选定;持有 1 + 在售 1 = 1.5 即可选定(合并权启动判定,
    破「不买框架件 → 计数永不涨」死锁;pick_framework docstring 之
    MC 2000 局预囤实证:门 2→1.5 后 C 策略启动率 99.9%)。门下现任手里
    有真件仍保持(防闪烁回退 ''),真件卖空才回落未定 ''。
    """
    assert pick_framework([], [],
                          shop=[_card('三月七'), _card('姬子·启行')]) == ''
    assert pick_framework([], [_bc('三月七')],
                          shop=[_card('三月七')]) == '列车'
    assert pick_framework([], [_bc('藿藿')], current='仙舟') == '仙舟'
    assert pick_framework([], [_bc('三月七')], current='仙舟') == ''


def test_pick_framework_hysteresis_and_tie() -> None:
    """滞回:换线门 = 挑战者持有权(整权)领先现任 ≥1——shop 半权只参与
    「谁先过启动线」,翻不动现任(挑战者合并权 1.5 过线但持有 0 < 现任 1
    → 留任);真实持有领先才翻转(仙舟 3 整权 > 列车 1)。平局按
    FRAMEWORKS 序偏仙舟(knowledge FRAMEWORKS 首位;主流先验 32% vs 29%,
    docstring 注明有意为之)。
    """
    board = [_bc('三月七'), _bc('藿藿'), _bc('丹恒·饮月'), _bc('爻光')]
    assert pick_framework([], board, current='列车') == '仙舟'
    assert pick_framework([], [_bc('三月七')],
                          shop=[_card('藿藿'), _card('爻光'), _card('椒丘')],
                          current='列车') == '列车'
    tie = [_bc('藿藿'), _bc('爻光'), _bc('三月七'), _bc('姬子·启行')]
    assert pick_framework([], tie) == '仙舟'


def test_pick_framework_portal_bias() -> None:
    """portal 偏置:开局环境名含框架名 → 该框架计数 +3 等效权(数据级
    先验,普通来牌权压不过;portal 信号家族 = final_jizi_train.md
    「列车同行概念股」/transition_combos.md 量子契约 portal)——
    量子 1 持有无 portal 恒未定(''),有 portal 即选定。偏置非锁死:
    4 张对立框架真件(仙舟 4.0)压过列车偏置(3.0)。
    """
    assert pick_framework([], [_bc('花火')]) == ''
    assert pick_framework([], [_bc('花火')], portal='量子契约') == '量子'
    assert pick_framework(
        [], [_bc('藿藿'), _bc('丹恒·饮月'), _bc('爻光'), _bc('椒丘')],
        portal='列车概念股') == '仙舟'


# ============================================================ transition_score


def test_transition_score_tiers_and_prehoard() -> None:
    """打分表档位(docstring 档位表):carry 1.0 / partial 0.6 /
    drop 0.4;framework=''(预囤模式)= 见框架件就囤但 drop 恒 0
    (应急件囤了 P1 末就卖 = 浪费金),未在册散件 0(无框架无阵营兜底);
    通用插件按 carry 档 + 通用 0.15。

    ⚠️ 分叉待裁:通用件在预囤模式(framework='')仍得通用 +0.15
    (elif 链「fw == '通用'」臂不依赖 framework 是否为空),而函数体
    尾注写「预囤:base 保持档位分」——本锁按现行实现钉 1.15;若裁决
    预囤应保持纯档位分,改实现同时改本断言。
    """
    assert transition_score('藿藿', '仙舟', framework='') == pytest.approx(1.0)
    assert transition_score('爻光', '仙舟', framework='') == pytest.approx(0.6)
    assert transition_score('卡芙卡', '星核猎手', framework='') == 0.0
    assert transition_score('千冶·刃', '星核猎手',
                            framework='') == pytest.approx(1.15)
    assert transition_score('阿格莱雅', '昼之半神', framework='') == 0.0


def test_transition_score_framework_bonus_and_faction_fallback() -> None:
    """框架已定的加成与阵营兜底:同框架集中 +0.3(椒丘 0.4+0.3;
    faction 实参不入框架键面,不叠契合加成);通用 +0.15;carry 全栈 =
    同框架 0.3 + faction 契合 0.2(三月七 1.5);partial 同框架 = 0.9
    (缇宝,registry 流派含量子同频但 elif 链只走同框架臂)。
    阵营兜底:在册他框架件 registry 阵营命中当前框架 → +0.2(丹恒·饮月
    = 仙舟+列车双阵营,列车框架下 1.2——「列车×4 难凑齐」修正);
    非在册角色阵营命中 = partial 级 0.6(星期日,列车同行阵营)。
    """
    assert transition_score('椒丘', '狼狩',
                            framework='仙舟') == pytest.approx(0.7)
    assert transition_score('缇宝', '昼之半神',
                            framework='量子') == pytest.approx(0.9)
    assert transition_score('三月七', '列车同行',
                            framework='列车') == pytest.approx(1.5)
    assert transition_score('千冶·刃', '星核猎手',
                            framework='仙舟') == pytest.approx(1.15)
    assert transition_score('丹恒·饮月', '仙舟',
                            framework='列车') == pytest.approx(1.2)
    assert transition_score('星期日', '盛会之星',
                            framework='列车') == pytest.approx(0.6)


# ============================================================ decision_target


def _target_comp() -> Comp:
    """终局哨兵线(合成 Comp,身份断言用;值域无关)。"""
    return Comp(name='测试·终局哨兵', factions=['追击'], core_chars=['飞霄'],
                form_tiers={'追击': 3}, strength='S', form_difficulty='easy')


def _session(framework: str, target_comp: Comp,
             *, locked: bool = False) -> StrategySession:
    """策略状态桩:transition_framework/target_comp 黑盒引用
    (decision_target 两读口);locked = 附意向状态机锁线帧。"""
    st = SimpleNamespace(transition_framework=framework,
                         target_comp=target_comp)
    if locked:
        st.v3_intention = SimpleNamespace(phase='locked', p1_pair=())
    s = StrategySession()
    s.strategy_state = st
    return s


def test_decision_target_recipe_in_dual_track() -> None:
    """双轨期目标线 = 配方伪 comp(单一入口,消费方零改动):权威派生
    保守 False(plane<2 且无意向状态供给)→ transition_framework='仙舟'
    → recipe_comp('仙舟') 同一对象;配方形状即消费契约——仙舟键面含
    持续伤害(deploy 围栏视图键面补全,cw_recipe._RECIPES 注),
    爻光必后台(站位规则住 comp,漏了落 position_pref 兜底),
    form_tiers = 3 仙舟主羁绊档。framework='' → 终局 comp 散件口径;
    策略状态未装配(裸 session,None-safe)→ None。
    """
    rc = recipe_comp('仙舟')
    sentinel = _target_comp()
    got = decision_target(_session('仙舟', sentinel), _gs())
    assert got is rc
    assert got.name == '过渡·仙舟配方'
    assert got.factions == ['仙舟', '持续伤害']
    assert got.form_tiers == {'仙舟': 3}
    assert got.char_positions == {'爻光': 'back'}
    assert decision_target(_session('', sentinel), _gs()) is sentinel
    assert decision_target(StrategySession(), _gs()) is None


def test_decision_target_committed_returns_terminal_line() -> None:
    """定型权威(任一)压过配方路由 → 终局 comp:①plane≥2(P2 起恒定型);
    ②意向状态机 phase='locked'(plane 1 锁线)。两分支同返回 target_comp
    本体——休眠期零漂移面(cw_recipe.decision_target docstring:生产路径
    transition_framework 恒 '',双分支同返回)。"""
    sentinel = _target_comp()
    assert decision_target(_session('仙舟', sentinel),
                           _gs(plane=2)) is sentinel
    assert decision_target(_session('仙舟', sentinel, locked=True),
                           _gs()) is sentinel
