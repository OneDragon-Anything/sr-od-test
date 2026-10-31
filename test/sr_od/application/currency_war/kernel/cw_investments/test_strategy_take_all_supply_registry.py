"""全都要·银注册面测试(cw_investments 分目录镜像;双腿异键登记 + 名单集
一致性 + 单取链登记缺位)。

- 登记锁:两条 EffectSpec(canon 键 = 一次性全捞腿 / 申报键 = 列数修饰腿)
  过 ``_validate_strategy_effects``(import 即炸,本文件 import 即过);
- 名单集-注册表一致性锁(表域测试,不入 import 校验——2026-10-28 治理口径
  「防登记笔误校验不加」,先例 = 先亏后盈 count/打捞族):持卡名单集 ⊆
  STRATEGY_EFFECTS name 集;
- 申报键永登记缺位锁:单取登记链 ``STRATEGY_EFFECTS.get(canon)`` 只自动
  登记 canon 键条目,申报键条目纯注册表声明(防误改键位引发双登记)。

卡面官方原文:「本局游戏中，补给阶段的可选项减少2个。下1个补给阶段选择
后，额外获得所有未选择的角色及装备。」
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    _TAKE_ALL_SUPPLY_STRATEGY_NAMES,
    SOURCE_STRATEGY,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)

_SIG = ChannelSig(family='logic_action', actor='test', mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='test', mode='read')


def test_take_all_two_leg_specs_registered() -> None:
    """登记锁:canon 键 = 腿2 一次性全捞(SUPPLY_PHASE/ONCE/BATTLEFIELD,
    payload salvage_all_unchosen_supply,pending=True 带 notes 保守支);
    申报键 = 腿1 列数修饰(SUPPLY_PHASE/WHILE_HELD,payload
    supply_option_delta=-2,声明面无 pending);两 spec.name 恒规范名。"""
    leg2 = STRATEGY_EFFECTS['全都要·银']
    assert (leg2.id, leg2.name) == ('131001', '全都要·银'), 'plaza 双对拍'
    assert leg2.trigger is TriggerKind.SUPPLY_PHASE, '触发面 = 补给选定时点'
    assert leg2.duration.value == 'once', '腿2 持续期 = 一次性(配额 1)'
    assert leg2.category is EffectKind.BATTLEFIELD, \
        '类别 = 战场改变(发放类世界写入)'
    assert leg2.payload.salvage_all_unchosen_supply is True, '腿2 载体字段'
    assert leg2.pending and leg2.notes, '二义条目 pending + 保守支必带'

    leg1 = STRATEGY_EFFECTS['全都要·银#supply_delta']
    assert (leg1.id, leg1.name) == ('131001', '全都要·银'), \
        '申报键条目 spec.name 恒规范名(校验按 name 查)'
    assert leg1.trigger is TriggerKind.SUPPLY_PHASE
    assert leg1.duration.value == 'while_held', '腿1 持续期 = 持有期全程'
    assert leg1.payload.supply_option_delta == -2, '列数修饰 = -2(明写)'
    assert not leg1.pending, '声明面无未裁数值,不设 pending'


def test_take_all_name_set_subset_of_registry() -> None:
    """名单集-注册表一致性锁(表域测试):持卡名单集任一成员失联(注册表
    改名/移除)即红——同一卡名两抄本的漂移防线,全都要·金/彩后继批扩集时
    防静默失联(判据维度 = name 集:申报键条目键不在 canon 键集,spec.name
    才在)。"""
    registry_names = {s.name for s in STRATEGY_EFFECTS.values()}
    assert set(_TAKE_ALL_SUPPLY_STRATEGY_NAMES) <= registry_names, \
        f'名单集失联: {_TAKE_ALL_SUPPLY_STRATEGY_NAMES} - {registry_names}'


def test_take_all_declaration_key_never_enters_ledger() -> None:
    """申报键永登记缺位锁:选卡获得链单取 ``STRATEGY_EFFECTS.get(canon)``
    → 效果账本恰一条(腿2,canon 键),申报键条目(腿1)永不入册——
    双登记 = 未来消费端按 payload 判别时的双发雷。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    gain_invest_strategy(gs, object(), '全都要·银', rand=False, sig=_SIG)
    assert gs.active_strategies.value == ['全都要·银'], '注册入表'
    entries = gs.effects.by_source(SOURCE_STRATEGY)
    assert [e.spec.name for e in entries] == ['全都要·银'], \
        f'账本恰一条(canon 键单取): {[e.spec.name for e in entries]}'
    assert entries[0].spec.payload.salvage_all_unchosen_supply is True, \
        '入册条目 = 腿2(非申报键腿1)'
    assert not any(
        int(getattr(e.spec.payload, 'supply_option_delta', 0) or 0) != 0
        for e in entries), '申报键条目(列数修饰腿)零入册'
