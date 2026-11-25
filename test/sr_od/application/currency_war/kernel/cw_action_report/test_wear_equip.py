"""report_action_wear_equip_param 记账路径(坐标反查)测试。

锁的设计约定(记账路径总契约首例;契约正文 = action-op.md「记账路径
总契约」条款):
- 记账键 = 上报坐标(src_cx/src_cy),内容 = 坐标伴随域反查产物;
  反查不到 = wear_item_xy_unresolved 拒单零写(名称校验
  wear_item_not_owned 已退役);
- 名称零消费:同一坐标 × 任意 item_name/char_name → 记账结果逐位相同
  (宪法③对齐锁面);
- 反查命中但名单缺条目 = 禁消费窗口违反 → 零防御自然异常(list.remove
  ValueError),禁静默守卫把错账洗成静默;
- 目标定位 = 纯槽位反查(row/slot → 槽现任单位;char_name 身份核对已
  退役),越界/空槽 = wear_target_unit_missing 拒单;
- 穿着即合成链回归:合成输入改反查产物后行为不变。
"""

import pytest

from sr_od.application.currency_war.kernel.cw_action_report.wear_equip import (
    report_action_wear_equip_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionWearEquipParam,
)

_SIG = ChannelSig(family='logic_action', actor='test')


def _seed_gs(owned: list[str], xy: dict | None,
             front_units: list[Unit | None]) -> GameState:
    """测试种子(与观察链同写入口 gs.observe):deployed 前排补齐定长 4。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    sig = ChannelSig(family='obs', actor='test')
    gs.observe(gs.equips, list(owned), sig=sig)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=sig)
    slots = list(front_units) + [None] * (4 - len(front_units))
    gs.observe(gs.deployed,
               DeployedView(front_slots=slots, back_slots=[None] * 6),
               sig=sig)
    return gs


def _wear_param(item_name: str = '量产型装甲',
                char_name: str = '银狼') -> CwActionWearEquipParam:
    return CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                  slot=1, item_name=item_name,
                                  char_name=char_name)


def test_resolve_hit_and_accounting() -> None:
    """反查命中:记账消费反查产物(owned −1 + 槽位单位 equips +1)。"""
    unit = Unit(char_id='银狼', star=2, equips=[])
    gs = _seed_gs(owned=['量产型装甲', '折叠小刀'],
                  xy={'量产型装甲': [(1740, 210)]},
                  front_units=[unit])
    outcome = report_action_wear_equip_param(gs, _wear_param(), _SIG)
    assert outcome.applied is True
    assert gs.equips.value == ['折叠小刀']
    assert gs.deployed.value.front_slots[0].equips == ['量产型装甲']


def test_resolve_miss_rejects_zero_write() -> None:
    """反查不到(坐标不在表/伴随域未就绪)→ 拒单零写。"""
    unit = Unit(char_id='银狼', star=2, equips=[])
    # 坐标不在表
    gs = _seed_gs(owned=['量产型装甲'], xy={'量产型装甲': [(1, 1)]},
                  front_units=[unit])
    outcome = report_action_wear_equip_param(gs, _wear_param(), _SIG)
    assert outcome.applied is False
    assert outcome.reason == 'wear_item_xy_unresolved'
    assert gs.equips.value == ['量产型装甲']
    assert gs.deployed.value.front_slots[0].equips == []
    # 伴随域未就绪(None,字段不写)
    gs2 = _seed_gs(owned=['量产型装甲'], xy=None, front_units=[unit])
    outcome2 = report_action_wear_equip_param(gs2, _wear_param(), _SIG)
    assert outcome2.applied is False
    assert outcome2.reason == 'wear_item_xy_unresolved'
    assert gs2.equips.value == ['量产型装甲']


def test_name_fields_zero_consumption() -> None:
    """名称零消费锁测:同坐标 × 名称三变体 → 记账结果逐位相同。"""
    variants = [
        _wear_param(item_name='', char_name=''),
        _wear_param(item_name='折叠小刀', char_name='刃'),
        _wear_param(item_name='量产型装甲', char_name='银狼'),
    ]
    snapshots = []
    for param in variants:
        unit = Unit(char_id='银狼', star=2, equips=[])
        gs = _seed_gs(owned=['量产型装甲', '折叠小刀'],
                      xy={'量产型装甲': [(1740, 210)]},
                      front_units=[unit])
        outcome = report_action_wear_equip_param(gs, param, _SIG)
        assert outcome.applied is True
        snapshots.append((list(gs.equips.value),
                          list(gs.deployed.value.front_slots[0].equips)))
    assert snapshots == [(['折叠小刀'], ['量产型装甲'])] * 3


def test_stale_window_violation_raises() -> None:
    """禁消费窗口违反:反查命中但名单缺条目 → ValueError 响亮(零防御,
    防静默守卫把错账洗成静默)。"""
    unit = Unit(char_id='银狼', star=2, equips=[])
    gs = _seed_gs(owned=[], xy={'量产型装甲': [(1740, 210)]},
                  front_units=[unit])
    with pytest.raises(ValueError):
        report_action_wear_equip_param(gs, _wear_param(), _SIG)


def test_slot_target_missing_rejects() -> None:
    """槽位定位收窄:越界/空槽 → wear_target_unit_missing 拒单零写;
    char_name 任意值不再影响定位(身份核对删除回归)。"""
    unit = Unit(char_id='银狼', star=2, equips=[])
    gs = _seed_gs(owned=['量产型装甲'], xy={'量产型装甲': [(1740, 210)]},
                  front_units=[unit])
    # slot 越界(前排定长 4)
    bad_slot = CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                      slot=9, item_name='量产型装甲',
                                      char_name='银狼')
    outcome = report_action_wear_equip_param(gs, bad_slot, _SIG)
    assert outcome.applied is False
    assert outcome.reason == 'wear_target_unit_missing'
    # 空槽(slot=2,槽位无人)+ char_name 与现值不同(任意值不影响定位判定)
    empty_slot = CwActionWearEquipParam(src_cx=1740, src_cy=210, row='front',
                                        slot=2, item_name='量产型装甲',
                                        char_name='刃')
    outcome2 = report_action_wear_equip_param(gs, empty_slot, _SIG)
    assert outcome2.applied is False
    assert outcome2.reason == 'wear_target_unit_missing'
    assert gs.equips.value == ['量产型装甲']


def test_wear_synthesis_regression() -> None:
    """穿着即合成链回归:合成输入改反查产物后行为不变(两件合成进阶;
    期望产物从合成器单一源现算,不手抄常量)。"""
    from sr_od.application.currency_war.data.cw_synthesis import (
        synthesize_target,
    )
    unit = Unit(char_id='银狼', star=2, equips=['折叠小刀'])
    gs = _seed_gs(owned=['量产型装甲'],
                  xy={'量产型装甲': [(1740, 210)]},
                  front_units=[unit])
    outcome = report_action_wear_equip_param(gs, _wear_param(), _SIG)
    expected_merged = synthesize_target('折叠小刀', '量产型装甲')
    assert expected_merged is not None
    assert outcome.applied is True
    assert gs.equips.value == []
    assert gs.deployed.value.front_slots[0].equips == [expected_merged]
