"""战术义眼+(id 350402)登记锁(cw_investments 分目录镜像;策略源 UNIT_BUFF
族战力类零响应登记,族先例 = 同目录 test_strategy_unit_buff.py 星魂升华
同代形)。两条效果条目分治:能量恢复效果条目 = STRATEGY_EFFECTS 本条目零响应登记;
「获得1个【简易武装箱】」效果条目 = 获得时点效果(STRATEGY_GRANTS 开箱分支 +
cw_gain_effects._STRATEGY_BOX_GRANTS 镜像),其 pick/席满行为面由
test_gain_chain.py 箱分支参数化锁承载,本文件只锁只登记不写状态的实现分支零响应。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-386-zhanshu-
yiyan-plus.md(定稿,REVIEW 无需用户决定)§7 实现要点(卡面官方原文:「我方小队
消灭普通/精英及首领敌人时，恢复25%/75%能量。获得1个【简易武装箱】。」):

- 条目锁(锁 1):UNIT_BUFF 零响应登记形 / id 350402 / trigger
  PLANE_START 占位形(触发面 = 逐击杀,TriggerKind 无击杀成员)×
  WHILE_HELD × UnitBuffRef 且 effect_text 与卡面单一源对拍 / duties 三位
  全 False / pending False / 现金分支 fail-closed(估值恒 (0.0, False));
- 登记链锁 + 桥负锁(锁 2):获得链只登记不写状态的实现分支自动入册,UnitBuffRef 无任何
  写状态副本字段 → 全部桥鸭子类型读取(duck typing)缺省守卫 no-op(五桥登记期零 Field 行);
  获得时点效果串 = 恰箱条目单步(SE 条目零增量,非 advisor 零解锁写、
  零单位域写入);session=None 支登记跳过、注册照常;
- 聚合零承载锁(锁 3):aggregate_economy 输出与本卡缺席逐位一致
  (单持/并持两形,战力类不进经济模型);
- 绑定不绑锁(锁 4):「我方小队」系作用对象全域非阵营语义,不入显式
  绑定表,公开绑定读端 fail-closed 空元组;
- 商店停机钩子零成员锁(锁 5):零响应 buff 非停机采集对象,卡面无
  商店改写/计数采集需求。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
    DurationKind,
    EffectKind,
    TriggerKind,
    UnitBuffRef,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    apply_effect_burst_grant,
    apply_effect_plane_refire_grant,
    bench_units_of,
    grant_effect_node_refresh_balance,
    project_effect_capacity,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _STRATEGY_BINDINGS_EXPLICIT,
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_EFFECTS,
    aggregate_economy,
    strategy_bindings,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '战术义眼+'
_CID = '350402'
_BOX_ITEM = '简易武装箱'

_SIG_LOGIC = ChannelSig(family='logic_action', actor='CwGainChain',
                        mode='compute')


def _make_gs() -> GameState:
    """最小观测面(bench 空席,箱条目落席有位;equips 空栏)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    gs.observe(gs.equips, [],
               sig=ChannelSig(family='obs', actor='CwScreenPrep'))
    return gs


def test_zhanshu_yiyan_plus_entry_registered() -> None:
    """条目锁(锁 1):UNIT_BUFF 零响应登记形;五元组逐位 + id 对拍;
    duties 三位全 False;pending False(作用对象/数值 desc 明文,无二义
    冻结面);构建校验(孤儿键/id 双匹配)import 期已过。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == _CID, 'id 对拍'
    assert spec.name == _CARD
    assert spec.trigger is TriggerKind.PLANE_START, '占位形(逐击杀无触发成员)'
    assert spec.duration is DurationKind.WHILE_HELD, '持有期绑定'
    assert spec.category is EffectKind.UNIT_BUFF, 'category = UNIT_BUFF'
    assert isinstance(spec.payload, UnitBuffRef), '载荷 = UnitBuffRef'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器(余期播种双 None)'
    assert spec.duties is not None and not (spec.duties.track
                                            or spec.duties.predict
                                            or spec.duties.respond), \
        'duties 三位全 False(零响应)'
    assert spec.pending is False, 'pending False'


def test_zhanshu_yiyan_plus_effect_text_single_source() -> None:
    """锁 1 续:effect_text 与卡面单一源对拍(经 PLAZA_AUGMENTS 数据面
    表达式,版本更新改文自动跟随;id 漂移 = StopIteration import 即炸,
    本条目存活即证)。"""
    assert STRATEGY_EFFECTS[_CARD].payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'


def test_zhanshu_yiyan_plus_cash_fail_closed_and_aggregate_zero() -> None:
    """现金分支锁 + 聚合零承载锁(锁 3):无 STRATEGY_ECONOMY 条目 → 估值
    fail-closed (0.0, False);aggregate_economy 输出与本卡缺席逐位一致
    (单持 = 全默认 / 并持 = 零增量,战力类不进经济模型,防未来误加经济
    条目或通道误开)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert strategy_economy_value(_CARD, gs) == (0.0, False)
    assert aggregate_economy([_CARD]) == aggregate_economy([]), \
        '单持聚合 = 全默认 EconomyEffect'
    assert aggregate_economy([_CARD, '利息上调']) \
        == aggregate_economy(['利息上调']), '并持聚合零增量(逐位一致)'


def test_zhanshu_yiyan_plus_gain_chain_register_and_bridges_noop() -> None:
    """登记链锁 + 桥负锁(锁 2):session 在场选卡 → 注册入表 + 账本登记
    (by_source 含本条);UnitBuffRef 无写状态副本字段 → 五桥鸭子类型读取缺省守卫
    no-op,登记期零 Field 行;获得时点效果串 = 恰箱条目单步(SE 条目零增量;
    箱条目 pick/席满行为面 = test_gain_chain.py 箱分支参数化锁辖域)、非
    advisor 条目只登记不写状态的实现分支零解锁写、道具非角色零单位域写入;session=None 支
    登记跳过、注册照常。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=_SIG_LOGIC)
    assert gs.active_strategies.value == [_CARD], '注册入表'
    entries = gs.effects.by_source(SOURCE_STRATEGY)
    assert [e.spec.name for e in entries] == [_CARD], \
        'register_strategy 入册(获得链只登记不写状态的实现分支既有链,零新代码)'
    assert entries[0].spec.id == _CID
    assert gs.free_refresh_left.value is None, \
        'burst/位面段补发桥 no-op(零 Field 行)'
    seq_after_gain = gs.write_seq   # 入册本身占账本写;五桥零写以此为基
    spec = entries[0].spec
    apply_effect_burst_grant(gs, spec)
    apply_effect_plane_refire_grant(gs, spec)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, 'burst/位面段补发桥显式调用零写'
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.write_seq == seq_after_gain
    grant_effect_node_refresh_balance(gs)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, '节点边界桥 no-op'
    project_effect_capacity(gs)
    assert gs.write_seq == seq_after_gain, '容量直写桥 no-op'
    assert gs.bench.value.capacity == 9, '容量默认值未被改写'
    gs2 = _make_gs()
    effects = on_strategy_gained(gs2, _CARD, rand=False, sig=_SIG_LOGIC)
    assert effects == (f'box_grant:{_BOX_ITEM}(placed=True)',), \
        '获得时点效果串 = 恰箱条目单步(SE 条目零增量)'
    assert gs2.unlocked_experts.value in (None, ()), '非 advisor 零解锁写'
    assert bench_units_of(gs2) == [], '道具非角色,单位域不变'
    # session=None 支:登记跳过、注册照常(登记分支同型断言)
    gs3 = _make_gs()
    gain_invest_strategy(gs3, None, _CARD, rand=False, sig=_SIG_LOGIC)
    assert gs3.active_strategies.value == [_CARD], '注册照常'
    assert gs3.effects.by_source(SOURCE_STRATEGY) == [], 'session=None 跳过'


def test_zhanshu_yiyan_plus_no_faction_binding() -> None:
    """绑定不绑锁(锁 4):「我方小队」系作用对象全域非阵营语义,不入显式
    绑定表;公开绑定读端对表外卡返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in _STRATEGY_BINDINGS_EXPLICIT, '显式绑定表零触碰'
    assert _CARD not in STRATEGY_BINDINGS, '派生绑定表零触碰'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_zhanshu_yiyan_plus_not_in_shop_watch_names() -> None:
    """商店停机钩子零成员锁(锁 5):零响应 buff 非停机采集对象,卡面无
    商店改写/计数采集需求(名单访问形 = 类限定 ClassVar)。"""
    assert _CARD not in CwScreenPrep._SPEC_INVEST_WATCH_NAMES, \
        '本卡不入停机钩子名单'
