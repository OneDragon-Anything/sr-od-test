"""条件判定型免费刷新(本金充裕/+)行为锁(账本 T-11;设计依据 =
docs/develop/sr_od/application/currency_war/changes/2026-09-11-unified-state/
details/GameState-数据结构设计.md §3.3.5-§3.3.6(下称「设计」)+
docs/develop/sr_od/application/currency_war/game_state/effect-domain.md(效果域正本)。

锁面三族(任务口径):
- **条件触发**:节点边界一次,按 bs.gold 现值评估——金 > 50 每额外 10 金
  +1 次免费刷新(发放经 grant_effect_node_refresh_balance 既有桥,无旁路);
- **上限封顶**:单次触发至多 3 次;
- **非触发不授予**:金 ≤ 50、余量不足 10 金、金未读(None)三形态零授予
  (桥零写入,余额保持 None,不造 0 帧)。

附加锁:棱彩加强值口径(两卡条件腿逐字同文 → 三元组同值;加强值只在
instant_gold 26/45)+ 注册表条目形状(id 双匹配/同实例单一源/counter 不建)。
断言全部按设计语义写;桥静态形态既有锁 = test_cw_game_state.py(§8.7
批次三节),本文件不重复其断言面。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    BS_SCHEMA_VERSION,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig as _ChannelSig,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    register_sig_actors as _register_sig_actors,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    DutyFlags,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)

_register_sig_actors('TestSigWriter')


def _sig() -> _ChannelSig:
    """渠道①签名(obs 族;观察/沿用/先验/离屏/观察事件)。"""
    return _ChannelSig(family='obs', actor='TestSigWriter', mode='read')


def _grant(bs: GameState, frame: str = '') -> None:
    """桥调用(与生产挂点同式;闸门形态见 test_same_node_resample_*)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        grant_effect_node_refresh_balance,
    )
    grant_effect_node_refresh_balance(bs, frame=frame)


def _bs_with_cond(gold: int | None) -> GameState:
    """本金充裕在册 + 金观察(或未读)的 GameState 桩。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.effects.register_strategy(STRATEGY_EFFECTS['本金充裕'], acquired_t=5)
    if gold is not None:
        bs.observe(bs.gold, gold, sig=_sig())
    return bs


# ============================================================ 注册表形状锁


def test_registry_conditional_spec_entries() -> None:
    """条目形状:id 双匹配(base plaza id)/NODE_ENTER×WHILE_HELD×ECONOMY/
    payload 引 STRATEGY_ECONOMY 同一实例(单一源)/counter 不建(duties 全空)。"""
    for name, spec_id in (('本金充裕', '301001'), ('本金充裕+', '301002')):
        spec = STRATEGY_EFFECTS[name]
        assert spec.id == spec_id
        assert INVESTMENT_STRATEGIES[name].source == f'plaza:{spec_id}', \
            '构建层 id 双匹配前置(base.source = plaza:<id>)'
        assert spec.trigger is TriggerKind.NODE_ENTER
        assert spec.duration is DurationKind.WHILE_HELD
        assert spec.category is EffectKind.ECONOMY
        assert spec.payload is STRATEGY_ECONOMY[name], 'payload 同实例(单一源)'
        assert spec.duties == DutyFlags(), '无累计量 → counter 不建,义务全空'


def test_prismatic_enhanced_value_scope() -> None:
    """棱彩态=加强值口径:加强值只在 instant_gold(26 vs 45);条件腿两卡
    官方卡文逐字同文 → 三元组同值(50/10/3)。"""
    base = STRATEGY_ECONOMY['本金充裕']
    plus = STRATEGY_ECONOMY['本金充裕+']
    assert (base.instant_gold, plus.instant_gold) == (26, 45)
    for eff in (base, plus):
        assert eff.free_refresh_cond_gold_above == 50
        assert eff.free_refresh_cond_gold_step == 10
        assert eff.free_refresh_cond_cap == 3
    cond_base = INVESTMENT_STRATEGIES['本金充裕'].effect
    cond_plus = INVESTMENT_STRATEGIES['本金充裕+'].effect
    _head, _, tail_base = cond_base.partition('。')
    _head_p, _, tail_plus = cond_plus.partition('。')
    assert tail_base == tail_plus != '', '首句(即时金)外条件腿逐字同文'
    assert '超过50金币' in tail_base and '每额外10金币' in tail_base \
        and '最多3次' in tail_base, '条件腿与三元组数值同源'


# ============================================================ 行为锁·条件触发


def test_conditional_grant_scales_with_gold() -> None:
    """条件触发+梯度:节点边界按当拍金现值评估,每额外 10 金 +1 次
    (70 金→+2;60 金→+1;59 金→余量不足 10 金→+0)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        grant_effect_node_refresh_balance,
    )
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.effects.register_strategy(STRATEGY_EFFECTS['本金充裕'], acquired_t=5)
    bs.observe(bs.gold, 70, sig=_sig())
    adv, _ = bs.effects.advance_node(6)
    assert adv
    grant_effect_node_refresh_balance(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 2, '金 70:(70-50)//10=2'
    bs.observe(bs.gold, 60, sig=_sig())
    bs.effects.advance_node(7)
    grant_effect_node_refresh_balance(bs, frame='p1-r7')
    assert bs.free_refresh_balance.value == 3, '金 60:+1,累计 3'
    bs.observe(bs.gold, 59, sig=_sig())
    bs.effects.advance_node(8)
    grant_effect_node_refresh_balance(bs, frame='p1-r8')
    assert bs.free_refresh_balance.value == 3, '金 59:余量 9 <10 → +0'


def test_same_node_resample_no_double_grant() -> None:
    """每节点恰一次:同节点重复采样(挂点每备战环一次)经 advanced=False
    闸门关闭累加——条件形态与静态形态同闸门(设计 §3.3.6 桥契约)。"""
    bs = _bs_with_cond(gold=80)
    adv, _ = bs.effects.advance_node(6)
    assert adv
    _grant(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 3, '金 80:(80-50)//10=3'
    adv2, _ = bs.effects.advance_node(6)
    assert adv2 is False, '同节点去重位 = 余额累加闸门'
    if adv2:   # 生产挂点同式(cw_loop:仅 advanced=True 调桥)
        _grant(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 3, '同节点禁双计'


# ============================================================ 行为锁·上限封顶


def test_conditional_cap_three() -> None:
    """上限封顶:金余量远超 30 金时单次触发仍至多 3 次(150/999 两拍)。"""
    bs = _bs_with_cond(gold=150)
    bs.effects.advance_node(6)
    _grant(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 3, '金 150:余 100 → min(10,3)=3'
    bs.observe(bs.gold, 999, sig=_sig())
    bs.effects.advance_node(7)
    _grant(bs, frame='p1-r7')
    assert bs.free_refresh_balance.value == 6, '金 999:封顶仍 +3,累计 6'


# ============================================================ 行为锁·非触发不授予


def test_no_grant_when_condition_not_met() -> None:
    """非触发不授予:金 ≤ 阈值(55 不足一步/50 恰等)→ 桥零写入,余额保持
    None(不造 0 帧;零授予 = 无该来源逻辑帧,观察通道不受扰)。"""
    for gold in (55, 50, 30):
        bs = _bs_with_cond(gold=gold)
        bs.effects.advance_node(6)
        _grant(bs, frame='p1-r6')
        assert bs.free_refresh_balance.value is None, gold


def test_no_grant_when_gold_unread() -> None:
    """金未读(None)= 条件不可评估 → 保守零授予(禁猜);下一节点金可读
    时恢复评估(不补发历史拍,授予量随当拍现值)。"""
    bs = _bs_with_cond(gold=None)
    bs.effects.advance_node(6)
    _grant(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value is None, '金未读 → 本拍零授予'
    bs.observe(bs.gold, 80, sig=_sig())
    bs.effects.advance_node(7)
    _grant(bs, frame='p1-r7')
    assert bs.free_refresh_balance.value == 3, '下一节点金可读 → 恢复评估'


# ============================================================ 与静态形态并存


def test_static_and_conditional_stack_single_write() -> None:
    """并存叠加:双手狸(静态 2/节点,BattlefieldEffect 无条件字段)+ 本金
    充裕(条件 3)同局 → 一拍一笔写入合计 5(鸭子求和,缺省 0 不串账)。"""
    bs = GameState(schema_version=BS_SCHEMA_VERSION)
    bs.effects.register_strategy(STRATEGY_EFFECTS['双手狸开键盘！'],
                                 acquired_t=5)
    bs.effects.register_strategy(STRATEGY_EFFECTS['本金充裕'], acquired_t=5)
    bs.observe(bs.gold, 80, sig=_sig())
    bs.effects.advance_node(6)
    _grant(bs, frame='p1-r6')
    assert bs.free_refresh_balance.value == 5, '静态 2 + 条件 3 单笔合计'
    assert bs.free_refresh_balance.evidence == 'effect_per_node@p1-r6'
    assert bs.free_refresh_balance.source == 'logic', '§3.3.6 写入=仅逻辑'
