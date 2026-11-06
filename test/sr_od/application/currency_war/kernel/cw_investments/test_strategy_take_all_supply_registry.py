"""全都要族注册面测试(cw_investments 分目录镜像;两条效果条目异键登记 + 配额
map 一致性 + 单取链登记缺位。族 = 银 id 131001 / 金 id 203501 /
彩 id 331701)。

- 登记锁:每卡两条 EffectSpec(canon 键 = 发放腿 / 申报键 = 列数修饰腿)
  过 ``_validate_strategy_effects``(import 即炸,本文件 import 即过);
- 配额 map-注册表一致性锁(表域测试,不入 import 校验——2026-10-28 治理
  口径「防登记笔误校验不加」,先例 = 先亏后盈 count/打捞族):map 键集 ⊆
  STRATEGY_EFFECTS name 集 + 配额值锁(int 卡 = 卡面「下 N 个」明写,银 1/
  金 2;彩 = None 值锁,recurring 无配额域防误写成 int 配额);
- 申报键永登记缺位锁:单取登记链 ``STRATEGY_EFFECTS.get(canon)`` 只自动
  登记 canon 键条目,申报键条目纯注册表声明(防误改键位引发双登记)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    _TAKE_ALL_SUPPLY_QUOTA,
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


_FAMILY_SPECS: dict[str, tuple[str, str]] = {
    # 卡名 → (plaza id, 发放腿持续期值):银配额 1 = ONCE 一次性形;
    # 金配额 2 = WHILE_HELD(「下2个」非一次性,计数一次性标志位承载耗尽即停);
    # 彩 recurring 无配额(None = 无界,恒放行无耗尽态)= WHILE_HELD。
    '全都要·银': ('131001', 'once'),
    '全都要·金': ('203501', 'while_held'),
    '全都要·彩': ('331701', 'while_held'),
}


def test_take_all_two_leg_specs_registered() -> None:
    """登记锁:每卡两条 EffectSpec(canon 键 = 发放腿 / 申报键 = 列数修饰
    腿)过 ``_validate_strategy_effects`` 四查(import 即炸,本文件 import
    即过);canon 条目 pending=True 带 notes 保守支、效果条目2 持续期按配额形
    分立;申报键条目声明面无 pending、spec.name 恒规范名。"""
    for name, (pid, leg2_dur) in _FAMILY_SPECS.items():
        leg2 = STRATEGY_EFFECTS[name]
        assert (leg2.id, leg2.name) == (pid, name), 'plaza 双对拍'
        assert leg2.trigger is TriggerKind.SUPPLY_PHASE, \
            '触发面 = 补给选定时点'
        assert leg2.duration.value == leg2_dur, f'发放腿持续期({name})'
        assert leg2.category is EffectKind.BATTLEFIELD, \
            '类别 = 战场改变(发放类世界写入)'
        assert leg2.payload.salvage_all_unchosen_supply is True, '效果条目2 载体字段'
        assert leg2.pending and leg2.notes, '二义条目 pending + 保守支必带'

        leg1 = STRATEGY_EFFECTS[f'{name}#supply_delta']
        assert (leg1.id, leg1.name) == (pid, name), \
            '申报键条目 spec.name 恒规范名(校验按 name 查)'
        assert leg1.trigger is TriggerKind.SUPPLY_PHASE
        assert leg1.duration.value == 'while_held', '效果条目1 持续期 = 持有期全程'
        assert leg1.payload.supply_option_delta == -2, '列数修饰 = -2(明写)'
        assert not leg1.pending, '声明面无未裁数值,不设 pending'


def test_take_all_name_set_subset_of_registry() -> None:
    """配额 map-注册表一致性锁(表域测试):map 键任一成员失联(注册表
    改名/移除)即红——同一卡名两抄本的漂移防线(判据维度 = name 集:申报
    键条目键不在 canon 键集,spec.name 才在);配额值锁 = 卡面明写值
    (int 卡「下 N 个」:银 1/金 2,配额写错 = 静默漏发/多发)+ 彩 None
    值锁(recurring 无配额域,误写成 int 配额 = 凭空耗尽早退 = 静默漏发)
    ——值面同一抄本防线,防写表人笔误。"""
    registry_names = {s.name for s in STRATEGY_EFFECTS.values()}
    assert set(_TAKE_ALL_SUPPLY_QUOTA) <= registry_names, \
        f'配额 map 键失联: {set(_TAKE_ALL_SUPPLY_QUOTA) - registry_names}'
    assert _TAKE_ALL_SUPPLY_QUOTA == {
        '全都要·银': 1, '全都要·金': 2, '全都要·彩': None,
    }, f'配额值锁(卡面明写): {_TAKE_ALL_SUPPLY_QUOTA}'
    assert _TAKE_ALL_SUPPLY_QUOTA['全都要·彩'] is None, \
        '彩 None 值锁(recurring 无配额域,恒放行零配额格)'


def test_take_all_declaration_key_never_enters_ledger() -> None:
    """申报键永登记缺位锁:选卡获得链单取 ``STRATEGY_EFFECTS.get(canon)``
    → 效果账本恰一条(发放腿,canon 键),申报键条目(列数修饰腿)永不入
    册——双登记 = 未来消费端按 payload 判别时的双发雷。两族卡同锁。"""
    for name in _FAMILY_SPECS:
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        gs.observe(gs.bench,
                   BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
                   sig=_SIG_OBS)
        gs.observe(gs.equips, [], sig=_SIG_OBS)
        gain_invest_strategy(gs, object(), name, rand=False, sig=_SIG)
        assert gs.active_strategies.value == [name], '注册入表'
        entries = gs.effects.by_source(SOURCE_STRATEGY)
        assert [e.spec.name for e in entries] == [name], \
            f'账本恰一条(canon 键单取): {[e.spec.name for e in entries]}'
        assert entries[0].spec.payload.salvage_all_unchosen_supply is True, \
            '入册条目 = 发放条目(非申报键效果条目1)'
        assert not any(
            int(getattr(e.spec.payload, 'supply_option_delta', 0) or 0) != 0
            for e in entries), '申报键条目(列数修饰腿)零入册'
