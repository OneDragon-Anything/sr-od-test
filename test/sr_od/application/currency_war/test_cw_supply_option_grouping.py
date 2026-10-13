"""补给选项归并纯函数锁(角色锚点定列骨架 + 装备簇归锚;T-9 过剩经费
design §2.2/§4.1/§4.2,设计正本 =
.debug/progress/2026-09-23-invest-effects-calc/designs/T-9-guoshengjingfei.md)。

选项单位语义 = **列 = 选项(角色 + 随选装备组,选中一并获得,非穿戴
语义)**,用户裁定 2026-10-13。归并规则(设计 §2.2,几何依据 = 归档帧
两帧实证:列距 ~352px、簇心 = 装备名 OCR 文本中心、簇心-自身锚点最差
~112(5 字件名 × 2 字角色名)、-邻锚点 ≥~240):

- 单排 5 列 → 与旧「每装备名 = 1 选项」读链逐值一致(idx/char/equip/
  点击点,回归锚);
- 双排 5 列 10 件 → 5 选项、equip = y 序首件、extra_equips 其余、char
  配对正确;
- 锚点失读降级(孤儿簇自成列 char='' 不并入邻列)/ char-only 列
  (equip='' 一等成立)/ 零锚点兜底(簇骨架);
- 带钻兜底遍历全列件名(「虫洞掘进钻头」类带钻字非钻名不误判)。

测试纪律:坐标全部为**测试自造常量**(按归档帧布局实证取值,断言依据
来自自造输入),不读归档帧文件、不跑 OCR;SIFT 通道以命中点列表直喂
纯函数(实机通道桩化到这一层已足——归簇语义在纯函数内)。
"""
from __future__ import annotations

from sr_od.application.currency_war.obs.cw_node_obs import (
    _group_supply_columns,
)

# ===== 自造坐标常量(依据 = 归档帧布局实证的设计记录,非运行时真值)=====
_COL_XS: tuple[int, ...] = (256, 608, 960, 1312, 1664)   # 5 列锚 x,列距 352
_CHAR_Y: int = 565            # 单排角色名 y(双排 ≈513,纯函数不消费 char y)
_EQUIP_Y: int = 700           # 单排装备名 y
_EQUIP_Y_A: int = 648         # 双排第一行 y
_EQUIP_Y_B: int = 748         # 双排第二行 y
_CLICK_Y = 550                # 卡身点击 y(常量语义断言用,纯函数不输出 y)


def _chars(names: tuple[str, ...],
           xs: tuple[int, ...] = _COL_XS) -> list[tuple[int, str]]:
    """列锚造料:第 i 列角色名文本中心 x = 列锚 x(截断 = 前列锚复用,
    失读降级造料靠少传名字;可传 xs 局部覆盖)。"""
    return list(zip(xs, names, strict=False))


def _single_row(names: tuple[str, ...],
                drift: tuple[int, ...] = (0, 0, 0, 0, 0),
                xs: tuple[int, ...] = _COL_XS) -> list[tuple[int, int, str]]:
    """单排装备造料:每列一件,装备文本中心 x = 列锚 x + 名长漂移量
    (截断语义同 _chars)。"""
    return [(x + d, _EQUIP_Y, n)
            for x, d, n in zip(xs, drift, names, strict=False)]


def test_single_row_five_columns_matches_legacy_per_equip_reading() -> None:
    """单排 5 列回归锚:角色锚点定列与旧「每装备名 = 1 选项」读链逐值
    一致(idx/char/equip 序、点击点 = 装备文本中心 x + 卡身 y)——
    默认布局零行为漂移(design §3 零改动声明)。"""
    chars = _chars(('镜流', '希儿', '花火', '停云', '杰帕德'))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池',
                          '垃圾袋', '生命之花'),
                         drift=(12, 40, 0, 25, 8))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5
    for i, ((opt, click_x), (ex, _ey, name)) in enumerate(zip(out, equips, strict=True)):
        assert opt.idx == i
        assert opt.char == chars[i][1], f'第 {i} 列角色配对'
        assert opt.equip == name
        assert opt.extra_equips == (), '单排每列恰一件'
        assert opt.has_diamond is False
        assert click_x == ex, '点击点 x = 装备文本中心 x(现役语义零漂移)'


def test_double_row_five_columns_groups_by_column() -> None:
    """双排 5 列 10 件(归档帧布局造料:跨列重复实证 = 光能电池第 3/5 列、
    折叠小刀第 1/5 列)→ 5 选项;每列 equip = y 序首件、extra_equips =
    其余;char 配对正确;点击点 = 簇首件(y 序)x。"""
    chars = _chars(('镜流', '希儿', '花火', '停云', '杰帕德'))
    equips: list[tuple[int, int, str]] = []
    # 逐列两件:(首件 y=648, 次件 y=748);x = 列锚 + 名长漂移(≤60)
    per_col = (
        ('折叠小刀', '垃圾袋'),
        ('量产型装甲', '生命之花'),
        ('光能电池', '折叠小刀'),
        ('生命之花', '光能电池'),
        ('光能电池', '折叠小刀'),
    )
    drifts = ((0, 18), (44, 6), (0, 30), (22, 50), (8, 0))
    for cx, (n1, n2), (d1, d2) in zip(_COL_XS, per_col, drifts,
                                    strict=True):
        equips.append((cx + d1, _EQUIP_Y_A, n1))
        equips.append((cx + d2, _EQUIP_Y_B, n2))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5, '双排 10 件归并为 5 列(非 10 幻影选项)'
    for i, ((opt, click_x), (n1, n2), (d1, _d2)) in enumerate(
            zip(out, per_col, drifts, strict=True)):
        assert opt.idx == i
        assert opt.char == chars[i][1]
        assert opt.equip == n1, 'equip = 列内 y 序首件'
        assert opt.extra_equips == (n2,), 'extra_equips = 其余件(y 序)'
        assert click_x == _COL_XS[i] + d1, '点击点 = 簇首件 x'


def test_missing_char_anchor_degrades_to_orphan_column() -> None:
    """锚点失读降级:某列角色名缺席 → 该列装备簇自成孤儿列(char='',
    不并入邻列);列序按 x 保持,其余列配对不受扰。"""
    # 第 3 列(花火,x=960)失读:其余四列锚显式传 xs
    chars = _chars(('镜流', '希儿', '停云', '杰帕德'),
                   xs=(_COL_XS[0], _COL_XS[1], _COL_XS[3], _COL_XS[4]))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池',
                          '垃圾袋', '生命之花'))
    out = _group_supply_columns(chars, equips)
    assert len(out) == 5, '孤儿簇不并邻列,5 列仍在'
    assert [opt.char for opt, _ in out] == \
        ['镜流', '希儿', '', '停云', '杰帕德'], '第 3 列孤儿列 char=空'
    assert out[2][0].equip == '光能电池'
    assert [opt.idx for opt, _ in out] == [0, 1, 2, 3, 4], '列序 = 画面列序'


def test_char_only_column_first_class_option() -> None:
    """char-only 列(锚点在、装备簇缺)→ equip=''、extra_equips=() 的
    一等选项成立(人才储备类变体天然承接);点击点 = 角色锚 x。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = [(x, _EQUIP_Y, n) for x, n in
              zip(_COL_XS[1:3], ('折叠小刀', '量产型装甲'),
                                strict=True)]   # 第 1 列无装备
    out = _group_supply_columns(chars, equips)
    assert len(out) == 3
    first = out[0][0]
    assert (first.char, first.equip, first.extra_equips) == ('镜流', '', ())
    assert out[0][1] == _COL_XS[0], 'char-only 列点击点 = 锚 x'
    assert out[1][0].equip == '折叠小刀' and out[2][0].equip == '量产型装甲'


def test_zero_anchor_fallback_cluster_skeleton() -> None:
    """零锚点兜底(角色名极端全失读)→ 装备 x 簇作骨架,各簇自成
    char='' 列,列序 = 簇 x 序。"""
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池'))
    out = _group_supply_columns([], equips)
    assert len(out) == 3
    assert all(opt.char == '' for opt, _ in out), '簇骨架列 char=空'
    assert [opt.equip for opt, _ in out] == ['折叠小刀', '量产型装甲',
                                             '光能电池']


def test_column_gap_keeps_clusters_split_and_name_drift_does_not() -> None:
    """聚簇双向余量:同列双件名长漂移(x 互距 ≤60)不裂簇;相邻列距
    352 > 阈值 200 不并簇(左列最右件与右列最左件间距仍 >> 阈值)。"""
    chars = _chars(('镜流', '希儿'))
    equips = [
        (_COL_XS[0], _EQUIP_Y_A, '折叠小刀'),
        (_COL_XS[0] + 60, _EQUIP_Y_B, '垃圾袋'),     # 同列漂移 60 ≤ 200
        (_COL_XS[1] - 60, _EQUIP_Y_A, '量产型装甲'),  # 距左列次件 352-120=232
        (_COL_XS[1], _EQUIP_Y_B, '生命之花'),
    ]
    out = _group_supply_columns(chars, equips)
    assert len(out) == 2, '两列四件,裂簇/并簇均不发生'
    assert out[0][0].equip == '折叠小刀'
    assert out[0][0].extra_equips == ('垃圾袋',)
    assert out[1][0].equip == '量产型装甲'
    assert out[1][0].extra_equips == ('生命之花',)


def test_worst_case_geometry_pairs_to_own_anchor() -> None:
    """最差几何造料(5 字件名 × 2 字角色名,簇心-自身锚点 ~112)不破
    配对:归入自身锚点(112 ≤ 容差 150),距邻锚 240 > 150 不误归。"""
    chars = [(_COL_XS[0], '镜流'), (_COL_XS[1], '希儿')]
    # 量产型装甲(5 字名)文本中心右移:距自身锚 112(单排帧实测最差列)
    equips = [(_COL_XS[0] + 112, _EQUIP_Y, '量产型装甲'),
              (_COL_XS[1] + 30, _EQUIP_Y, '折叠小刀')]
    out = _group_supply_columns(chars, equips)
    assert len(out) == 2
    assert out[0][0].char == '镜流' and out[0][0].equip == '量产型装甲', \
        '最差几何仍配对自身锚点'
    assert out[1][0].char == '希儿'


def test_diamond_text_fallback_scans_all_column_names() -> None:
    """带钻文本兜底遍历全列件名(design §2.2.8 迁移):extra_equips 命中
    三钻词表 → 该列 has_diamond=True;「虫洞掘进钻头」类带钻字非钻名
    不误判(精确匹配非子串)。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = [
        (_COL_XS[0], _EQUIP_Y_A, '折叠小刀'),
        (_COL_XS[0], _EQUIP_Y_B, '财富宝钻'),        # 附加件带钻 → 兜底命中
        (_COL_XS[1], _EQUIP_Y, '虫洞掘进钻头'),       # 带钻字非钻名
        (_COL_XS[2], _EQUIP_Y, '量产型装甲'),
    ]
    out = _group_supply_columns(chars, equips)
    assert out[0][0].has_diamond is True, '附加件名命中钻词表 → 列带钻'
    assert out[1][0].has_diamond is False, '带钻字非钻名不误判'
    assert out[2][0].has_diamond is False


def test_sift_hit_assigns_to_nearest_cluster() -> None:
    """SIFT 主通道:命中点归最近簇心(≤ 容差)→ 该列 has_diamond=True;
    文本名不含钻词表也成立(视觉通道独立于文本兜底)。"""
    chars = _chars(('镜流', '希儿', '花火'))
    equips = _single_row(('折叠小刀', '量产型装甲', '光能电池'))
    out = _group_supply_columns(chars, equips,
                                sift_hits=[(_COL_XS[1] + 10, 716)])
    assert [opt.has_diamond for opt, _ in out] == [False, True, False], \
        'SIFT 命中点归第 2 列簇'
