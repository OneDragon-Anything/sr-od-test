"""CwActionWearEquipParam 参数面契约测试(穿装坐标参数化形态)。

锁的设计约定:
- ``from_dict`` = MCP run_operation JSON 通道的唯一构造形态(只取已声明
  字段/未知键忽略/缺字段落 dataclass 默认值;单一源 = cw_replay_reader
  .from_dict 同构)——坐标是跨进程契约,直调方按它传参;
- ``action_key`` 幂等粒度 = 行为参数含名称(不同名件 = 不同动作实例,
  屏蔽计数按行为参数含名称更准),``route_tag`` 不入键(词表全族统一
  契约,见 cw_vocab route_tag 字段契约块)。

被测单一源 = ``cw_vocab.CwActionWearEquipParam`` 类 docstring(记账路径
总契约首例;契约正文 = action-op.md「记账路径总契约」条款)。
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
