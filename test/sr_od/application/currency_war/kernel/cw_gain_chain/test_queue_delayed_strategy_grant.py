"""策略延时发放入队原语与登记腿测试(镜像 src = kernel/cw_gain_chain.py
的 queue_delayed_strategy_grant + kernel/cw_gain_effects.py 的
_make_delayed_grant_effect 派生条目)。

测试面依据 = 迭代设计 designs/T-106-rencai-jili.md §4 锁 2(登记腿
2+2 条)+ 锁 5(live 链登记;发放原语无 live 调用点由模块边界承担——
kernel 不 import sim,不设静态扫描锁)+ T-107 展开卡批(designs/
T-107-rencai-jili-plus.md §4 锁 2:人才激励+ 登记腿 @3 直断,原
monkeypatch 形态测随真注册转直测):
- 拿卡人才激励 → equips 尾部 +1 员工投影仪 ∧ 队列 (('人才激励', 4),)
  ∧ 双效果串(equip_grant:strategy_grant_scheduled);人才激励+ 同构
  @3(姊妹双卡逐名独立构造);
- 许诺特权 = 延时-only 单腿登记腿(卡文纯延时单句):效果串单枚
  strategy_grant_scheduled,零即时腿(反向锁错发形态);
- equips 未观察 → 即时腿拒落零写 placed=False、入队腿照写;
- 未登记策略卡(表外名 + 在册无腿卡)零写;
- live 落地形态(gain_invest_strategy 同函数,session=None 直构)队列
  照写,零世界发放动作。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _gs(equips: list[str] | None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if equips is not None:
        gs.write_logic(gs.equips, list(equips), produced_by='test-seed',
                       evidence='t:equips', sig=_lsig())
    gs.prep_anchored = True   # 置闩:登记 = 确定事件,锁确定面写通道
    return gs


def test_pick_rencai_jili_instant_equip_and_queue() -> None:
    """登记腿主条(handler 分派形态):拿卡人才激励 → equips 尾部 +1
    员工投影仪(write_logic 确定面,rand=False 具名发放)+ 队列恰
    (('人才激励', 4),)(元素 = (触发卡规范名, 登记节拍))+ 双效果串
    equip_grant(placed=True)/ strategy_grant_scheduled:员工投影仪@4。"""
    gs = _gs(equips=[])
    effects = on_strategy_gained(gs, '人才激励', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=True)',
                       'strategy_grant_scheduled:员工投影仪@4'), \
        f'效果串: {effects}'
    assert gs.equips.value == ['员工投影仪'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.equips.source == 'logic' \
        and gs.pending_strategy_grants.source == 'logic', '两腿走确定面'


def test_equips_unobserved_instant_rejected_queue_still_written() -> None:
    """equips 未观察(直构域):即时腿拒落零写(placed=False,入栏跳写
    gain_equipment 既有语义)、入队腿照写(登记 = 队列通道非装备通道,
    两腿互不拖)。"""
    gs = _gs(equips=None)
    effects = on_strategy_gained(gs, '人才激励', rand=False, sig=_lsig(),
                                 rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=False)',
                       'strategy_grant_scheduled:员工投影仪@4'), \
        f'效果串: {effects}'
    assert gs.equips.value is None, '拒落域出现写'
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'入队腿未写: {gs.pending_strategy_grants.value}'


def test_unregistered_cards_zero_write() -> None:
    """未登记卡零写(两形):表外名(查无效果安静不写)与在册无腿卡
    (躺平,注册表有卡但无登记行)均 → 零效果串 + 队列零写。"""
    for name in ('随便一张未收录卡', '躺平'):
        gs = _gs(equips=[])
        seq_before = gs.write_seq
        effects = on_strategy_gained(gs, name, rand=False, sig=_lsig(),
                                     rng=random.Random(0))
        assert effects == ()
        assert gs.pending_strategy_grants.value in (None, ()), \
            f'{name} 队列被写'
        assert gs.write_seq == seq_before, f'{name} 出现额外写行'


def test_live_gain_chain_queues_grant_zero_world_grant_action() -> None:
    """live 链登记(不对称申报的行为半边,锁 5):live 落地形态同函数
    (gain_invest_strategy,session=None 直构)→ 注册去重 + 即时装备腿
    与入队腿照写;kernel 零到点发放动作(发放腿仅存在于 sim 模块,模块
    边界承担,无静态扫描锁——AGENTS.md 测试规范源码扫描禁令)。"""
    gs = _gs(equips=[])
    outcome = gain_invest_strategy(gs, None, '人才激励', rand=False,
                                   sig=_lsig(), rng=random.Random(0),
                                   producer='CwActionReport')
    assert outcome.placed is True
    assert '人才激励' in (gs.active_strategies.value or []), '持卡注册'
    assert outcome.effects == ('equip_grant:员工投影仪(placed=True)',
                               'strategy_grant_scheduled:员工投影仪@4')
    assert gs.pending_strategy_grants.value == (('人才激励', 4),), \
        f'live 链队列: {gs.pending_strategy_grants.value}'
    assert gs.equips.value == ['员工投影仪'], '即时腿 live 照写'


def test_pick_rencai_jili_plus_direct_registry_chain() -> None:
    """人才激励+ 登记腿直断(原「注册表临时行 + 效果表同步派生」
    monkeypatch 形态测,随该卡真注册落地转直测——handler 按注册表
    驱动,零新增机制件):拿卡人才激励+ → equips 尾部 +1 员工投影仪
    ∧ 队列恰 (('人才激励+', 3),) ∧ 双效果串 equip_grant(placed=
    True)/ strategy_grant_scheduled:员工投影仪@3。@3 字面直断防姊妹
    卡键序错位(两卡唯一可见差异);逐名独立构造,姊妹卡登记腿主条
    (test_pick_rencai_jili_instant_equip_and_queue)不受影响。"""
    gs = _gs(equips=[])
    effects = on_strategy_gained(gs, '人才激励+', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('equip_grant:员工投影仪(placed=True)',
                       'strategy_grant_scheduled:员工投影仪@3'), \
        f'效果串: {effects}'
    assert gs.equips.value == ['员工投影仪'], f'装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('人才激励+', 3),), \
        f'队列值: {gs.pending_strategy_grants.value}'


def test_pick_xunuo_tequan_delayed_only_single_leg() -> None:
    """许诺特权 延时-only 登记腿直断(卡文「在进入7个节点后，获得
    1个【特权武装箱】。」纯延时单句,零即时腿):拿卡 → 队列恰
    (('许诺特权', 7),) ∧ 效果串单枚 strategy_grant_scheduled:
    特权武装箱@7 ∧ 零即时腿(equips 零写、无 equip_grant 字样;bench
    域零涉)。反向锁死「延时-only 卡直用两腿工厂派生」的错发形态
    (错发即时特权武装箱 = 行为级错误);@7 字面直断防族键序错位;
    逐名独立构造,姊妹双卡两腿锁不受影响。"""
    gs = _gs(equips=[])
    seq_before = gs.write_seq
    effects = on_strategy_gained(gs, '许诺特权', rand=False,
                                 sig=_lsig(), rng=random.Random(0))
    assert effects == ('strategy_grant_scheduled:特权武装箱@7',), \
        f'效果串(单枚,零即时腿): {effects}'
    assert gs.equips.value == [], f'即时腿误写装备栏: {gs.equips.value}'
    assert gs.pending_strategy_grants.value == (('许诺特权', 7),), \
        f'队列值: {gs.pending_strategy_grants.value}'
    assert gs.write_seq == seq_before + 1, \
        f'入队腿外出现额外写行(seq={gs.write_seq})'
