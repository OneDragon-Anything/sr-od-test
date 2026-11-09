"""sr_light_cones 光锥快照常量单测。

锁的内容（sr_light_cones 模块 docstring 契约；基准值与官方 wiki 快照一致，
不读本机易失快照件）：

- 快照完整性：LIGHT_CONES 恰 170 把、名称唯一、rarity ∈ {3,4,5}、
  skill 特效全文齐备；
- 基准：银河铁道之夜（5 星 智识）/ 于夜色中（5 星）；
- 查询助手：名查命中与 miss 返回 None；
- 图标寻址公式基准（名称键）。
"""

from sr_od.mys.sr_light_cones import (
    LIGHT_CONES,
    icon_webp_rel_path,
    resolve_light_cone,
)


def test_light_cones_snapshot_completeness() -> None:
    """快照完整性：恰 170 把；名称唯一；rarity ∈ {3,4,5}。"""
    assert len(LIGHT_CONES) == 170
    names = [c.name for c in LIGHT_CONES]
    assert len(set(names)) == 170
    assert all(c.rarity in (3, 4, 5) for c in LIGHT_CONES)
    assert all(c.skill for c in LIGHT_CONES)  # 特效全文固化齐备（用户裁定进 py）


def test_anchor_cones_and_helpers() -> None:
    """基准与查询助手：名查命中；miss None 不抛异常；path_id ∈ 九命途 id 集；
    图标路径公式基准（名称键）。"""
    by_name = resolve_light_cone('银河铁道之夜')
    assert by_name is not None
    assert by_name.rarity == 5
    assert by_name.path_id == 'erudition'
    assert '流星群' in by_name.skill  # 特效基准（skill 名 + 文本透传）

    assert resolve_light_cone('于夜色中') is not None
    assert resolve_light_cone('不存在的光锥') is None

    valid_paths = {'destruction', 'preservation', 'hunt', 'abundance', 'nihility',
                   'erudition', 'harmony', 'remembrance', 'elation'}
    assert all(c.path_id in valid_paths for c in LIGHT_CONES)
    assert icon_webp_rel_path('银河铁道之夜') == 'assets/game_data/light_cone_icons/银河铁道之夜.webp'
