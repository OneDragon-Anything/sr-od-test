"""relic_tpl_store 遗器模板库单测。

锁的内容（命名约定即注册表；读仓内真实模板资产）：
- 模板库与常量表一致：目录名集合 == 非空 id 套装 × 部位组合的全集
  （空 id 套装国际服未同步不入库，白名单随 test_sr_relic_sets 同步收紧）；
- 遍历条目自洽：template_id == 套装 id + 部位英文段，raw 可加载。

自建 store 实例（零 ctx）——store 构造只注入 TemplateLoader，契约可独立验证。
"""

from one_dragon.base.screen.template_loader import TemplateLoader
from sr_od.application.cultivation.relic.relic_tpl_store import (
    RELIC_TEMPLATE_SUB_DIR,
    RelicTplStore,
    relic_template_id,
)
from sr_od.mys.sr_relic_sets import RELIC_POS_EN, RELIC_SETS


def test_card_faces_matches_constants() -> None:
    entries = RelicTplStore(TemplateLoader()).card_faces
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
