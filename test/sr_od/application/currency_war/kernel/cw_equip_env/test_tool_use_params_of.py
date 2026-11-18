"""tool_use_params_of 发出面参数构造(坐标伴随域消费口)测试。

锁的设计约定(工具原子参数面迁移批;被测单一源 =
kernel/cw_equip_env.tool_use_params_of):
- 双坐标齐备才产原子:equip 模式四坐标(tool_cx/tool_cy 源 +
  tgt_cx/tgt_cy 目标)逐位透传,item_name 填日志语义;
- 坐标缺席 = 该原子本帧不产(计数返回值;自愈通道 = 帧稳定截断 →
  Obs outer_loop 重观察后自然重派,同穿装批);
- per-name 游标序贯消费(工具名/目标名各一游标,只在确定产原子时
  推进——缺席原子不白耗候选;单动作收敛生产形态下游标恒取首候选);
- 伴随域未就绪(None)= 全跳过零产出;
- action_kind 值域封闭(furnace_single/privilege_upgrade),词表外键 =
  AssertionError 响亮暴露;char 模式原子不经本 helper(无 back_slot_count
  写入位,gs.back_layout 不消费)。
"""

import pytest

from sr_od.application.currency_war.kernel.cw_equip_env import (
    tool_use_params_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionFurnaceUseParam,
    CwActionPrivilegeCardUseParam,
)

_OBS = ChannelSig(family='obs', actor='test')


def _gs(xy) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    return gs


def test_both_coords_present_builds_params_bitwise() -> None:
    """双坐标齐备产原子:字段逐位断言(两类各一)。"""
    xy = {'冶金炉': [(1660, 120)], '量产型装甲': [(1740, 210)],
          '特权赋予卡': [(1661, 121)], '武器大师': [(1741, 211)]}
    gs = _gs(xy)
    params, skipped = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '量产型装甲'),
        ('特权赋予卡', 'privilege_upgrade', '武器大师'),
    ])
    assert skipped == 0
    assert len(params) == 2
    p1 = params[0]
    assert isinstance(p1, CwActionFurnaceUseParam)
    assert p1.target_kind == 'equip'
    assert (p1.tool_cx, p1.tool_cy) == (1660, 120)
    assert (p1.tgt_cx, p1.tgt_cy) == (1740, 210)
    assert p1.item_name == '量产型装甲'
    p2 = params[1]
    assert isinstance(p2, CwActionPrivilegeCardUseParam)
    assert p2.target_kind == 'equip'
    assert (p2.tool_cx, p2.tool_cy) == (1661, 121)
    assert (p2.tgt_cx, p2.tgt_cy) == (1741, 211)
    assert p2.item_name == '武器大师'


def test_missing_tool_or_target_coord_skips_with_count() -> None:
    """工具名/目标名坐标缺席 → 该原子跳过 + 计数;缺席原子不白耗候选
    (后续原子仍消费首候选)。"""
    xy = {'冶金炉': [(1660, 120)], '量产型装甲': [(1740, 210)]}
    gs = _gs(xy)
    # 工具名缺席(拆装扳手不在伴随域)
    params, skipped = tool_use_params_of(gs, [
        ('拆装扳手', 'furnace_single', '量产型装甲'),
    ])
    assert params == [] and skipped == 1
    # 目标名缺席(折叠小刀不在伴随域)——且冶金炉候选未被上面缺席原子消耗
    params2, skipped2 = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '折叠小刀'),
    ])
    assert params2 == [] and skipped2 == 1
    # 双坐标齐备的原子正常产出(首候选未被消耗)
    params3, skipped3 = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '量产型装甲'),
    ])
    assert skipped3 == 0 and len(params3) == 1
    assert (params3[0].tool_cx, params3[0].tool_cy) == (1660, 120)
    assert (params3[0].tgt_cx, params3[0].tgt_cy) == (1740, 210)


def test_xy_none_skips_all() -> None:
    """伴随域未就绪(None)→ 全跳过零产出。"""
    gs = _gs(None)
    params, skipped = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '量产型装甲'),
    ])
    assert params == [] and skipped == 1


def test_cursor_sequential_consumption_per_name() -> None:
    """游标序贯消费(单次调用内;游标为每次调用新建,生产单动作收敛形态
    下每帧至多消费一次):同名两原子各消费一候选,候选耗尽后第三原子
    缺席计数(工具与目标游标独立推进)。"""
    xy = {'冶金炉': [(1, 1), (2, 2)], '量产型装甲': [(10, 10), (20, 20)]}
    gs = _gs(xy)
    params, skipped = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '量产型装甲'),
        ('冶金炉', 'furnace_single', '量产型装甲'),
        ('冶金炉', 'furnace_single', '量产型装甲'),
    ])
    assert len(params) == 2 and skipped == 1
    assert ((params[0].tool_cx, params[0].tool_cy),
            (params[0].tgt_cx, params[0].tgt_cy)) == ((1, 1), (10, 10))
    assert ((params[1].tool_cx, params[1].tool_cy),
            (params[1].tgt_cx, params[1].tgt_cy)) == ((2, 2), (20, 20))


def test_unknown_action_kind_raises() -> None:
    """action_kind 词表外键 = AssertionError 响亮暴露(禁静默跳过)。"""
    gs = _gs({'冶金炉': [(1, 1)], '量产型装甲': [(2, 2)]})
    with pytest.raises(AssertionError):
        tool_use_params_of(gs, [('冶金炉', 'projector_copy', '量产型装甲')])


def test_back_layout_not_consumed() -> None:
    """equip 分支无 back_slot_count 写入位:gs.back_layout 不入本 helper
    (值任意/未观察均不影响产出字段)。"""
    xy = {'冶金炉': [(1, 1)], '量产型装甲': [(2, 2)]}
    gs = _gs(xy)
    gs.observe(gs.back_layout, 8, sig=_OBS)
    params, _ = tool_use_params_of(gs, [
        ('冶金炉', 'furnace_single', '量产型装甲'),
    ])
    assert len(params) == 1
    assert params[0].back_slot_count == 6   # 词表缺省,不经 back_layout
