"""sr_light_cones 光锥快照常量单测。

锁的内容（sr_light_cones 模块 docstring 契约；锚点值与 mys 实证/归档图标 SIFT
双源锚定结果一致，不读本机易失快照件）：

- 快照完整性：LIGHT_CONES 恰 170 把、tid 唯一、名称唯一；
- tid 分段契约：2000x=3星 / 210xx+2200x=4星 / 2300x+2400x=5星（与
  rarity 字段逐把一致——图标寻址与 mys 反查的地址契约）；
- 锚点：实证套（银河铁道之夜 23000 / 于夜色中 23001 / 记忆的质料 24002）；
- 查询助手：名查 / tid 查命中与 miss 返回 None；
- 图标寻址公式锚点。
"""

from sr_od.mys.sr_light_cones import (
    LIGHT_CONES,
    icon_webp_rel_path,
    resolve_cone_by_tid,
    resolve_light_cone,
)


def test_light_cones_snapshot_completeness() -> None:
    """快照完整性：恰 170 把；tid 与名称各自唯一；rarity ∈ {3,4,5}。"""
    assert len(LIGHT_CONES) == 170
    tids = [c.tid for c in LIGHT_CONES]
    names = [c.name for c in LIGHT_CONES]
    assert len(set(tids)) == 170
    assert len(set(names)) == 170
    assert all(c.rarity in (3, 4, 5) for c in LIGHT_CONES)
    assert all(c.skill for c in LIGHT_CONES)  # 特效全文固化齐备（用户裁定进 py）


def test_tid_segment_matches_rarity() -> None:
    """tid 分段契约：2000x 段恒 3 星、210xx/2200x 段恒 4 星、2300x/2400x 段
    恒 5 星——段即「星级×渠道」的地址语义，逐把校验。"""
    for cone in LIGHT_CONES:
        if cone.tid < 21000:
            assert cone.rarity == 3, cone
        elif cone.tid < 23000:
            assert cone.rarity == 4, cone
        else:
            assert cone.rarity == 5, cone


def test_anchor_cones_and_helpers() -> None:
    """锚点与查询助手：tid 实证套命中；名查/tid 查一致；miss None 不抛异常；
    path_id ∈ 九命途 id 集；图标路径公式锚点。"""
    by_name = resolve_light_cone('银河铁道之夜')
    assert by_name is not None
    assert by_name.tid == 23000
    assert by_name.rarity == 5
    assert by_name.path_id == 'erudition'
    assert '流星群' in by_name.skill  # 特效锚点（skill 名 + 文本透传）

    assert resolve_light_cone('于夜色中').tid == 23001
    assert resolve_cone_by_tid(24002).name == '记忆的质料'
    assert resolve_light_cone('不存在的光锥') is None
    assert resolve_cone_by_tid(-1) is None

    valid_paths = {'destruction', 'preservation', 'hunt', 'abundance', 'nihility',
                   'erudition', 'harmony', 'remembrance', 'elation'}
    assert all(c.path_id in valid_paths for c in LIGHT_CONES)
    assert icon_webp_rel_path(23000) == 'assets/game_data/light_cone_icons/lightcone_23000.webp'
