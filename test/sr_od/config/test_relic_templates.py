"""relic_templates 遗器模板库单测。

锁的内容（命名约定即注册表；读仓内真实模板资产）：
- 模板库与常量表一致：目录名集合 == 非空 id 套装 × 部位组合的全集
  （空 id 套装国际服未同步不入库，白名单随 test_sr_relic_sets 同步收紧）；
- 遍历条目自洽：template_id == 套装 id + 部位英文段，raw 可加载。
"""

from sr_od.config.relic_templates import (
    RELIC_TEMPLATE_SUB_DIR,
    iter_relic_templates,
    relic_template_id,
)
from sr_od.mys.sr_relic_sets import RELIC_POS_EN, RELIC_SETS


def test_iter_relic_templates_matches_constants(test_context, monkeypatch) -> None:
    monkeypatch.setattr(test_context, 'relic_templates', None, raising=False)
    entries = iter_relic_templates(test_context)
    expected = {
        relic_template_id(relic_set, piece.pos): (relic_set, piece)
        for relic_set in RELIC_SETS if relic_set.id
        for piece in relic_set.pieces
    }
    assert {e.template_id for e in entries} == set(expected)
    for e in entries:
        relic_set, piece = expected[e.template_id]
        assert e.relic_set is relic_set
        assert e.piece is piece
        assert e.template_id == f'{relic_set.id}_{RELIC_POS_EN[piece.pos]}'
        assert e.info.raw is not None


def test_sub_dir_and_id_formula() -> None:
    """分类目录名与公式基准锚点（防目录改名/公式漂移无声破裂）。"""
    assert RELIC_TEMPLATE_SUB_DIR == 'relic_icon'
    wakka = next(s for s in RELIC_SETS if s.set_name == '生命的翁瓦克')
    assert relic_template_id(wakka, 5) == 'sprightlyvonwacq_planarsphere'
