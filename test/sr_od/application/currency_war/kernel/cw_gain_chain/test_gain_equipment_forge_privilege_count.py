"""gain_equipment 尾段刃锻特权化获得计数锁(镜像 src = kernel
/cw_gain_chain.py 的 gain_equipment 尾段调用 + kernel/cw_effect_inventory
.record_forge_privilege_gain 机制单一源;按被测方法拆目录规范落位——
test_gain_chain.py 在册超限冻结禁追加,新锁落新镜像,先例 = 同目录
既有镜像文件)。

测试面依据 = 迭代设计 designs/T-418-duanye-zhuanjia-ren.md §4 锁 5
(计数钩子锁)+ 裁决点 3-A 计数口径(经 gain_equipment 原语的获得即
1 件,「获得」= 净新增字面直辖):
- 持卡 + 刃在场,gain_equipment ×10 → 次数 1→2 充能且计数器 =10;
- 刃不在场同调用 → 零计数(在场门控,离场期获得不计数不补计);
- 第 11 件 → 计数器 =11 零充能(整 10 倍数边界);
- 装备获得转换拦截的装备分支目标经原语净新增入栏照计(好运来行,
  进阶 → 好运令牌;占席道具分支不入装备栏不计 = 自由市场行,不在本
  文件重复锁——落位面归转换锁族)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    FORGE_PRIVILEGE_CARD,
    FORGE_PRIVILEGE_CHAR,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_equipment,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwGainChainTest')

_LSIG = ChannelSig(family='logic_action', actor='CwGainChainTest',
                   mode='compute')


def _make_gs(*, ren_present: bool,
             deployed_ren: bool = False) -> GameState:
    """观测面组装:equips 空观察(原语拒落早退的负基座);刃在场形态
    二选一 = 备战席首位(deployed_ren=False)/ 前排 1 号位
    (deployed_ren=True);ren_present=False = 全空席对照。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    slots: list[BenchSlot | None] = [BenchSlot(kind='empty')] * 9
    if ren_present and not deployed_ren:
        slots[0] = BenchSlot(kind='unit',
                             unit=Unit(char_id=FORGE_PRIVILEGE_CHAR,
                                       star=1))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    front: list[Unit | None] = [None] * 4
    if ren_present and deployed_ren:
        front[0] = Unit(char_id=FORGE_PRIVILEGE_CHAR, star=1)
    gs.observe(gs.deployed,
               DeployedView(front_slots=front, back_slots=[None] * 6),
               sig=_SIG_OBS)
    return gs


def _hold_card(gs: GameState, *cards: str) -> None:
    gs.write_logic(gs.active_strategies, list(cards), produced_by='test-seed',
                   evidence='t:card', sig=_LSIG)


def _gain(gs: GameState, item: str) -> None:
    out = gain_equipment(gs, item, rand=False, sig=_LSIG, evidence='t',
                         producer='Test')
    assert out.placed, '入栏前提(观察面已种)'


def test_ten_gains_recharge_once() -> None:
    """计数钩子主锁:持卡 + 刃在场(备战席),gain_equipment ×10 →
    次数账 1→2(充能恰 1 次)且计数器 =10;计数器随获得写通道累进。"""
    gs = _make_gs(ren_present=True)
    _hold_card(gs, FORGE_PRIVILEGE_CARD)
    assert gs.forge_privilege_charges_left.value == 1 \
        and gs.forge_privilege_gained_count.value == 0, \
        'Field 缺省承载开局态(零置位)'
    for _ in range(10):
        _gain(gs, '折叠小刀')
    assert gs.forge_privilege_gained_count.value == 10, '十件全计'
    assert gs.forge_privilege_charges_left.value == 2, '整 10 充能恰 1 次'
    assert len(gs.equips.value or []) == 10, '入栏与计数同事件'


def test_ten_gains_recharge_once_with_ren_deployed() -> None:
    """在场门控 deployed 侧:刃在后排/前排部署域同样计数(门控域 =
    deployed ∪ bench 现值)。"""
    gs = _make_gs(ren_present=True, deployed_ren=True)
    _hold_card(gs, FORGE_PRIVILEGE_CARD)
    for _ in range(10):
        _gain(gs, '折叠小刀')
    assert gs.forge_privilege_gained_count.value == 10
    assert gs.forge_privilege_charges_left.value == 2


def test_ren_absent_zero_count() -> None:
    """在场门控阴性:同持卡同调用,刃不在场 → 零计数零充能(计数时点
    现值判定,离场期获得不计数不补计)。"""
    gs = _make_gs(ren_present=False)
    _hold_card(gs, FORGE_PRIVILEGE_CARD)
    for _ in range(12):
        _gain(gs, '折叠小刀')
    assert gs.forge_privilege_gained_count.value == 0, '零计数'
    assert gs.forge_privilege_charges_left.value == 1, '零充能'


def test_eleventh_gain_no_recharge() -> None:
    """整 10 倍数边界:第 11 件 → 计数器 =11 零变化(充能只在整 10
    倍数刻,11 件零充能)。"""
    gs = _make_gs(ren_present=True)
    _hold_card(gs, FORGE_PRIVILEGE_CARD)
    for _ in range(11):
        _gain(gs, '折叠小刀')
    assert gs.forge_privilege_gained_count.value == 11
    assert gs.forge_privilege_charges_left.value == 2, '第 11 件零充能'


def test_converted_equipment_branch_counts() -> None:
    """转换装备分支计数锁(裁决点 3-A 口径对转换路径的落地):持好运来
    + 锻冶专家:刃,进阶件获得被转换为好运令牌(装备分支,名字替换落
    原插入路径)→ 令牌经原语净新增入栏 = 「获得」1 件,计数照进。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EQUIP_GAIN_CONVERSIONS,
    )
    assert STRATEGY_EQUIP_GAIN_CONVERSIONS['好运来'] == ('进阶', '好运令牌')
    gs = _make_gs(ren_present=True)
    _hold_card(gs, '好运来', FORGE_PRIVILEGE_CARD)
    _gain(gs, '步步生花')
    assert gs.equips.value == ['好运令牌'], '转换目标入栏(装备分支)'
    assert gs.forge_privilege_gained_count.value == 1, \
        '经原语净新增入栏 = 获得 1 件'


def test_no_card_zero_count() -> None:
    """门①阴性:不持卡同调用 → 零计数零充能(无卡局零行为差)。"""
    gs = _make_gs(ren_present=True)
    for _ in range(10):
        _gain(gs, '折叠小刀')
    assert gs.forge_privilege_gained_count.value == 0
    assert gs.forge_privilege_charges_left.value == 1
