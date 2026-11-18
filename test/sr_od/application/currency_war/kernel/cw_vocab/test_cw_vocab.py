"""动作词表参数面契约测试(穿装 + 工具原子七类坐标参数化形态)。

锁的设计约定:
- ``from_dict`` = MCP run_operation JSON 通道的唯一构造形态(只取已声明
  字段/未知键忽略/缺字段落 dataclass 默认值;单一源 = cw_replay_reader
  .from_dict 同构,工具七类经共享 ``action_param_from_dict`` 委托)
  ——坐标是跨进程契约,直调方按它传参;
- ``action_key`` 幂等粒度 = 行为参数含名称(不同名件 = 不同动作实例,
  屏蔽计数按行为参数含名称更准),``route_tag`` 不入键(词表全族统一
  契约,见 cw_vocab route_tag 字段契约块)。

被测单一源 = ``cw_vocab`` 各参数类 docstring(记账路径总契约首例 =
CwActionWearEquipParam、第二适用者 = 工具七类;契约正文 = action-op.md
「记账路径总契约」条款)。
"""

from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionWearEquipParam,
    action_key,
)


def test_from_dict_full_and_minimal() -> None:
    """全字段 dict 逐字段透传;最小 dict(必填 4 项)落全缺省。"""
    full = CwActionWearEquipParam.from_dict({
        'src_cx': 1740, 'src_cy': 210, 'row': 'front', 'slot': 2,
        'back_slot_count': 7, 'item_name': '量产型装甲',
        'char_name': '银狼', 'route_tag': 'm7'})
    assert (full.src_cx, full.src_cy) == (1740, 210)
    assert full.row == 'front'
    assert full.slot == 2
    assert full.back_slot_count == 7
    assert full.item_name == '量产型装甲'
    assert full.char_name == '银狼'
    assert full.route_tag == 'm7'

    minimal = CwActionWearEquipParam.from_dict(
        {'src_cx': 1, 'src_cy': 2, 'row': 'back', 'slot': 1})
    assert (minimal.src_cx, minimal.src_cy) == (1, 2)
    assert minimal.back_slot_count == 6
    assert minimal.item_name == ''
    assert minimal.char_name == ''
    assert minimal.route_tag == ''


def test_from_dict_ignores_unknown_keys() -> None:
    """未知键忽略(读端容忍:调用方多传历史/扩展键不炸构造)。"""
    p = CwActionWearEquipParam.from_dict({
        'src_cx': 3, 'src_cy': 4, 'row': 'front', 'slot': 1,
        'item_name': '量产型装甲', 'legacy_extra': 'x'})
    assert (p.src_cx, p.src_cy) == (3, 4)
    assert p.item_name == '量产型装甲'


def test_action_key_names_in_route_tag_out() -> None:
    """幂等键含名称(不同名件 = 不同动作实例);route_tag 不入键。"""
    base = {'src_cx': 10, 'src_cy': 20, 'row': 'front', 'slot': 2}
    k_a = action_key(CwActionWearEquipParam(item_name='甲', **base))
    k_b = action_key(CwActionWearEquipParam(item_name='乙', **base))
    assert k_a != k_b
    k_tag = action_key(
        CwActionWearEquipParam(item_name='甲', route_tag='m7', **base))
    assert k_tag == k_a


# ===== 工具原子七类(参数面迁移形态;from_dict 经共享 action_param_from_dict)=====

from sr_od.application.currency_war.kernel.cw_vocab import (  # noqa: E402
    CwActionFurnaceUseParam,
    CwActionLuckyTokenUseParam,
    CwActionPerfectProjectorUseParam,
    CwActionPrecisionWrenchUseParam,
    CwActionPrivilegeCardUseParam,
    CwActionStaffProjectorUseParam,
    CwActionWrenchUseParam,
    action_param_from_dict,
)

_DUAL_CLASSES = (CwActionFurnaceUseParam, CwActionPrivilegeCardUseParam)
_CHAR_CLASSES = (CwActionWrenchUseParam, CwActionPrecisionWrenchUseParam,
                 CwActionStaffProjectorUseParam, CwActionPerfectProjectorUseParam,
                 CwActionLuckyTokenUseParam)


def test_dual_mode_from_dict_full_and_minimal() -> None:
    """双模类 from_dict:全字段 dict 逐字段透传;最小 dict(必填 3 项)
    落全缺省(tgt 哨兵 0/back_slot_count 6/名称空);未知键忽略。"""
    full = CwActionFurnaceUseParam.from_dict({
        'target_kind': 'equip', 'tool_cx': 1660, 'tool_cy': 120,
        'tgt_cx': 1740, 'tgt_cy': 210, 'row': 'back', 'slot': 3,
        'back_slot_count': 8, 'item_name': '量产型装甲',
        'char_name': '罗刹', 'route_tag': 'm7_5'})
    assert full.target_kind == 'equip'
    assert (full.tool_cx, full.tool_cy) == (1660, 120)
    assert (full.tgt_cx, full.tgt_cy) == (1740, 210)
    assert full.row == 'back' and full.slot == 3
    assert full.back_slot_count == 8
    assert full.item_name == '量产型装甲'
    assert full.char_name == '罗刹'
    assert full.route_tag == 'm7_5'

    minimal = CwActionPrivilegeCardUseParam.from_dict(
        {'target_kind': 'equip', 'tool_cx': 1, 'tool_cy': 2})
    assert minimal.target_kind == 'equip'
    assert (minimal.tool_cx, minimal.tool_cy) == (1, 2)
    assert (minimal.tgt_cx, minimal.tgt_cy) == (0, 0)   # 未传哨兵
    assert minimal.row == '' and minimal.slot == 0
    assert minimal.back_slot_count == 6
    assert minimal.item_name == '' and minimal.char_name == ''
    assert minimal.route_tag == ''

    p = CwActionFurnaceUseParam.from_dict({
        'target_kind': 'char', 'tool_cx': 3, 'tool_cy': 4,
        'row': 'front', 'slot': 1, 'legacy_extra': 'x'})
    assert p.row == 'front' and p.slot == 1
    assert p.item_name == ''   # 未知键之上缺省正常;未知键不影响


def test_char_mode_from_dict_full_and_minimal() -> None:
    """char 单模类 from_dict:必填 4 项(tool_cx/tool_cy/row/slot);
    缺省全落;未知键忽略(五类逐一过)。"""
    for cls in _CHAR_CLASSES:
        full = cls.from_dict({'tool_cx': 1620, 'tool_cy': 120,
                              'row': 'back', 'slot': 7,
                              'back_slot_count': 7, 'char_name': '刃',
                              'route_tag': 'm7_5'})
        assert (full.tool_cx, full.tool_cy) == (1620, 120)
        assert full.row == 'back' and full.slot == 7
        assert full.back_slot_count == 7
        assert full.char_name == '刃'
        assert full.route_tag == 'm7_5'

        minimal = cls.from_dict({'tool_cx': 1, 'tool_cy': 2,
                                 'row': 'front', 'slot': 1})
        assert minimal.back_slot_count == 6
        assert minimal.char_name == ''
        assert minimal.route_tag == ''

    p = CwActionWrenchUseParam.from_dict({
        'tool_cx': 1, 'tool_cy': 2, 'row': 'front', 'slot': 1,
        'legacy_extra': 'x'})
    assert p.char_name == ''


def test_action_param_from_dict_shared_shape() -> None:
    """共享形态单一源:action_param_from_dict 与类 from_dict 委托等价
    (只取已声明字段/未知键忽略/缺字段落默认)。"""
    d = {'tool_cx': 5, 'tool_cy': 6, 'row': 'front', 'slot': 2,
         'unknown_key': 1}
    assert action_param_from_dict(CwActionStaffProjectorUseParam, d) == \
        CwActionStaffProjectorUseParam.from_dict(d)


def test_tool_action_key_rules() -> None:
    """工具类幂等键:同坐标不同 item_name 产不同键;坐标不同产不同键;
    route_tag 不入键(双模与 char 单模各验一类)。"""
    equip_a = CwActionFurnaceUseParam(target_kind='equip', tool_cx=10,
                                      tool_cy=20, tgt_cx=30, tgt_cy=40,
                                      item_name='甲')
    equip_b = CwActionFurnaceUseParam(target_kind='equip', tool_cx=10,
                                      tool_cy=20, tgt_cx=30, tgt_cy=40,
                                      item_name='乙')
    assert action_key(equip_a) != action_key(equip_b)
    equip_c = CwActionFurnaceUseParam(target_kind='equip', tool_cx=10,
                                      tool_cy=20, tgt_cx=31, tgt_cy=40,
                                      item_name='甲')
    assert action_key(equip_a) != action_key(equip_c)
    equip_tag = CwActionFurnaceUseParam(target_kind='equip', tool_cx=10,
                                        tool_cy=20, tgt_cx=30, tgt_cy=40,
                                        item_name='甲', route_tag='m7_5')
    assert action_key(equip_tag) == action_key(equip_a)

    char_a = CwActionWrenchUseParam(tool_cx=10, tool_cy=20, row='front',
                                    slot=2, char_name='甲')
    char_b = CwActionWrenchUseParam(tool_cx=10, tool_cy=20, row='front',
                                    slot=3, char_name='甲')
    assert action_key(char_a) != action_key(char_b)
    char_tag = CwActionWrenchUseParam(tool_cx=10, tool_cy=20, row='front',
                                      slot=2, char_name='甲',
                                      route_tag='m7_5')
    assert action_key(char_tag) == action_key(char_a)


# ===== 统一拖动(槽位键参数面迁移形态;from_dict 经共享 action_param_from_dict)=====

from sr_od.application.currency_war.kernel.cw_vocab import (  # noqa: E402
    CwActionMoveUnitParam,
)


def test_move_unit_from_dict_full_and_minimal() -> None:
    """统一拖动 from_dict:全字段 dict 逐字段透传;最小 dict(必填 4 项)
    落全缺省(back_slot_count 6/reason/expect/route_tag 空);未知键忽略。"""
    full = CwActionMoveUnitParam.from_dict({
        'src_domain': 'bench', 'src_slot': 2, 'dst_domain': 'back',
        'dst_slot': 7, 'back_slot_count': 8, 'reason': 'deploy_diff_place',
        'expect': '银狼', 'route_tag': 'yield_plan_deploy'})
    assert full.src_domain == 'bench' and full.src_slot == 2
    assert full.dst_domain == 'back' and full.dst_slot == 7
    assert full.back_slot_count == 8
    assert full.reason == 'deploy_diff_place'
    assert full.expect == '银狼'
    assert full.route_tag == 'yield_plan_deploy'

    minimal = CwActionMoveUnitParam.from_dict({
        'src_domain': 'front', 'src_slot': 1,
        'dst_domain': 'bench', 'dst_slot': 0})
    assert minimal.back_slot_count == 6
    assert minimal.reason == '' and minimal.expect == ''
    assert minimal.route_tag == ''

    p = CwActionMoveUnitParam.from_dict({
        'src_domain': 'bench', 'src_slot': 0, 'dst_domain': 'front',
        'dst_slot': 1, 'legacy_extra': 'x'})
    assert p.back_slot_count == 6   # 未知键不影响缺省


def test_move_unit_action_key_rules() -> None:
    """统一拖动幂等键:back_slot_count 不同产不同键(同槽位不同布局档 =
    不同拖拽落点,禁共享屏蔽粒度);reason/expect 入键、route_tag 不入键。"""
    base = {'src_domain': 'bench', 'src_slot': 1,
            'dst_domain': 'back', 'dst_slot': 7}
    k6 = action_key(CwActionMoveUnitParam(**base))
    k8 = action_key(CwActionMoveUnitParam(back_slot_count=8, **base))
    assert k6 != k8
    k_tag = action_key(CwActionMoveUnitParam(route_tag='x', **base))
    assert k_tag == k6


# ===== 卖上阵(槽位键参数面迁移形态;from_dict 经共享 action_param_from_dict)=====

from sr_od.application.currency_war.kernel.cw_vocab import (  # noqa: E402
    CwActionSellDeployedParam,
)


def test_sell_deployed_from_dict_full_and_minimal() -> None:
    """卖上阵 from_dict:全字段 dict 逐字段透传;最小 dict(必填 1 项)
    落全缺省(back_slot_count 6/income None/reason/expect/route_tag 空);
    未知键忽略。"""
    full = CwActionSellDeployedParam.from_dict({
        'deployed_idx': 10, 'back_slot_count': 8, 'income': 5,
        'reason': 'deploy_star_swap', 'expect': '银狼',
        'route_tag': 'yield_plan_sell'})
    assert full.deployed_idx == 10
    assert full.back_slot_count == 8
    assert full.income == 5
    assert full.reason == 'deploy_star_swap'
    assert full.expect == '银狼'
    assert full.route_tag == 'yield_plan_sell'

    minimal = CwActionSellDeployedParam.from_dict({'deployed_idx': 3})
    assert minimal.back_slot_count == 6
    assert minimal.income is None
    assert minimal.reason == '' and minimal.expect == ''
    assert minimal.route_tag == ''

    p = CwActionSellDeployedParam.from_dict({
        'deployed_idx': 0, 'legacy_extra': 'x'})
    assert p.back_slot_count == 6   # 未知键不影响缺省


def test_sell_deployed_action_key_rules() -> None:
    """卖上阵幂等键:back_slot_count 不同产不同键(同槽位不同布局档 =
    不同拖拽落点,禁共享屏蔽粒度);route_tag 不入键(reason 入键 =
    SellDeployed 现状非 action_key_exclude 字段,零变化不锁测)。"""
    base = {'deployed_idx': 7}
    k6 = action_key(CwActionSellDeployedParam(**base))
    k8 = action_key(CwActionSellDeployedParam(back_slot_count=8, **base))
    assert k6 != k8
    k_tag = action_key(CwActionSellDeployedParam(route_tag='x', **base))
    assert k_tag == k6
