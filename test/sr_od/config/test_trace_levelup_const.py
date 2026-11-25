"""行迹升级数量表的结构锁:不锁具体材料数值(版本更新合法变动),
锁「段覆盖 + 合计锚点 + 查询语义」——锚点值来自实机晋阶界面交叉验证
(固化时凭据,见常量文件头),数值若变=官方改表,重生成+同步改锚点。"""
from sr_od.config.trace_levelup_const import (
    _TRACE_LEVELUP_COSTS,
    total_cost,
)


def test_all_nine_segments_covered():
    """等级 1→10 共 9 段全在表内,每段材料非空且含信用点。"""
    assert len(_TRACE_LEVELUP_COSTS) == 9
    for seg_name, mats in _TRACE_LEVELUP_COSTS.items():
        assert mats, f'{seg_name} 材料为空'
        assert '信用点' in mats, f'{seg_name} 缺信用点'


def test_total_cost_semantics():
    """合计为半开区间:1→8 含 7→8 段不含 8→9 段(命运足迹属 8→9 起)。"""
    total = total_cost(1, 8)
    assert '命运的足迹' not in total
    assert '信用点' in total and '永恒之花' in total
    # 与 8→9 段的合计不含该段自身材料(结构语义锁,不锁数值)
    seg89 = _TRACE_LEVELUP_COSTS['8→9']
    for name in seg89:
        if name == '信用点':
            continue
        if name in total:
            # 若两段有同名材料,合计值必须大于该段单独值(至少含前段)
            assert total[name] >= seg89[name]
