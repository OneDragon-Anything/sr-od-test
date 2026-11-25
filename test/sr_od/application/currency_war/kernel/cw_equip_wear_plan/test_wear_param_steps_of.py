"""wear_param_steps_of 发出面坐标伴随域消费单点测试。

锁的设计约定(发出面唯一坐标消费口;记账路径总契约的发出面预检半边):
- 游标序贯消费:同名多步逐件分帧消费候选(生产单动作收敛形态下恒取
  首候选,游标是 helper 完备性/MCP 对齐产物);
- None 守卫:伴随域未就绪(None)→ 全跳过(宁缺勿造,禁猜坐标);
- 候选缺席 = 该步不产(计数返回值承载,跳过自愈通道的输入);
- back_slot_count = int(gs.back_layout.value or 6)(与计划面
  ``_bk_n or 6`` 同口径,双弃权帧缺省沿用)。

被测单一源 = ``cw_equip_wear_plan.wear_param_steps_of``。
"""

from sr_od.application.currency_war.kernel.cw_equip_wear_plan import (
    EquipPlanBuild,
    EquipWearStep,
    wear_param_steps_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)

_OBS = ChannelSig(family='obs', actor='test')


def _seed_gs(xy: dict | None, back_layout: int | None) -> GameState:
    """测试种子(与观察链同写入口 gs.observe;None 参数 = 字段不写 =
    未观察 None)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if xy is not None:
        gs.observe(gs.owned_equip_xy, xy, sig=_OBS)
    if back_layout is not None:
        gs.observe(gs.back_layout, back_layout, sig=_OBS)
    return gs


def _build(*steps: EquipWearStep) -> EquipPlanBuild:
    return EquipPlanBuild(steps=list(steps), branch='m7')


def test_cursor_sequential_consumption() -> None:
    """同名两步 × 候选 1 条 → 首步产参、次步跳过;候选充足按序消费。"""
    steps = (EquipWearStep(item_name='量产型装甲', char_name='银狼',
                           row='front', slot=2),
             EquipWearStep(item_name='量产型装甲', char_name='刃',
                           row='front', slot=3))
    gs = _seed_gs({'量产型装甲': [(10, 20)]}, 6)
    params, skipped = wear_param_steps_of(_build(*steps), gs)
    assert len(params) == 1 and skipped == 1
    assert (params[0].src_cx, params[0].src_cy) == (10, 20)
    assert params[0].slot == 2

    gs2 = _seed_gs({'量产型装甲': [(10, 20), (30, 40)]}, 6)
    params2, skipped2 = wear_param_steps_of(_build(*steps), gs2)
    assert skipped2 == 0
    assert [(p.src_cx, p.src_cy) for p in params2] == [(10, 20), (30, 40)]


def test_unobserved_xy_all_skipped() -> None:
    """伴随域未就绪(None)→ 全部跳过(零产参,计数 = 步数)。"""
    steps = (EquipWearStep(item_name='量产型装甲', char_name='银狼',
                           row='front', slot=1),
             EquipWearStep(item_name='折叠小刀', char_name='银狼',
                           row='front', slot=2))
    params, skipped = wear_param_steps_of(_build(*steps), _seed_gs(None, 6))
    assert params == [] and skipped == 2


def test_missing_name_step_skipped() -> None:
    """候选缺名分支(环内新获得件形态)→ 该步跳过计数,余步照产。"""
    steps = (EquipWearStep(item_name='量产型装甲', char_name='银狼',
                           row='front', slot=1),
             EquipWearStep(item_name='折叠小刀', char_name='银狼',
                           row='front', slot=2))
    gs = _seed_gs({'量产型装甲': [(10, 20)]}, 6)
    params, skipped = wear_param_steps_of(_build(*steps), gs)
    assert skipped == 1
    assert len(params) == 1
    assert params[0].item_name == '量产型装甲'


def test_back_slot_count_default_and_value() -> None:
    """back_slot_count = int(back_layout or 6):None → 6 缺省;有值直传。"""
    step = EquipWearStep(item_name='量产型装甲', char_name='银狼',
                         row='back', slot=1)
    p_none, _ = wear_param_steps_of(_build(step), _seed_gs(
        {'量产型装甲': [(10, 20)]}, None))
    assert p_none[0].back_slot_count == 6
    p_eight, _ = wear_param_steps_of(_build(step), _seed_gs(
        {'量产型装甲': [(10, 20)]}, 8))
    assert p_eight[0].back_slot_count == 8
