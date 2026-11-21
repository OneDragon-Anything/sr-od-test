"""角色行迹材料归属常量的结构锁:BWIKI 重生成后,查询接口的结构与锚点不变即应绿。

锚点材料名是跨源实证(2026-11-15:官方材料词条「来源」+BWIKI 材料页「相关角色」
+项目产出表三源交叉),重生成只应保持命中、不应漂移;不断言完整材料清单——
版本更新会合法新增条目。
"""
from sr_od.config.trace_material_const import (
    _CHARACTER_TRACE_MATERIALS,
    find_character_trace_materials,
)


def test_anchor_characters_hit_verified_materials():
    """三重锚点:样本角色必须命中已实证的行迹材料(生成器固化前也校验,此处锁查询语义)。"""
    assert '伪觉者的期许' in find_character_trace_materials('星神★阿哈')
    assert '蛀星孕灾的旧恶' in find_character_trace_materials('黄泉')
    assert '无穷假身的遗恨' in find_character_trace_materials('藿藿')


def test_bwiki_renamed_character_resolves():
    """BWIKI 页面改名角色(仙舟三月七→三月七•巡猎)经标题覆盖后表键正常命中。"""
    materials = find_character_trace_materials('仙舟三月七')
    assert materials is not None and len(materials) > 0


def test_trace_material_lists_are_nonempty_and_credit_included():
    """每名角色的材料列表非空,且都含通用项信用点(行迹升级固定消耗)。"""
    for cn, materials in _CHARACTER_TRACE_MATERIALS.items():
        assert materials, f'{cn} 材料列表为空'
        assert '信用点' in materials, f'{cn} 缺通用项信用点'


def test_find_supports_trailblazer_suffix_and_returns_none_for_unknown():
    """开拓者形态带性别后缀可前缀命中;表外角色返回 None。"""
    male = find_character_trace_materials('开拓者·毁灭·男')
    assert male is not None and len(male) > 0
    female = find_character_trace_materials('开拓者·毁灭·女')
    assert female == male  # 同形态材料与性别无关
    assert find_character_trace_materials('不存在角色') is None
    assert find_character_trace_materials('开拓者') is None  # 裸名多义,显式 None
