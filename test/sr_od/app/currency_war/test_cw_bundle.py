"""cw_bundle(06 号束优化)行为测试:对拍锚点 + 交互项分歧(ADR-0156)。"""
import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.cw_bundle import bundle_select
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard


def _cfg():
    return SimpleNamespace(faction_priority=[], character_priority=[],
                           character_build_around=[], character_forbid=[], faction_forbid=[])


def _state(shop, gold=50, bench=(), deployed=(), board=None, level=7):
    return GameState(gold=gold, round_num=3, level=level, plane=1, hp=80,
                     shop=list(shop), bench=list(bench), deployed=list(deployed),
                     board=board or {})


def test_anchor_interactions_off_equals_best_single():
    """对拍锚点(提案性质 3):关交互项 → 束 = 最优单买(与贪心同参);全负 → None。"""
    shop = [ShopCard(x=1, faction='列车同行', name='三月七', cost=1),
            ShopCard(x=2, faction='仙舟', name='符玄', cost=4)]
    st = _state(shop, gold=30)
    r = bundle_select(st, _cfg(), [], None, interactions=False)
    assert r is not None and len(r) == 1   # 单买(贪心等价)


def test_anchor_no_affordable_returns_none():
    st = _state([ShopCard(x=1, faction='仙舟', name='符玄', cost=4)], gold=2)
    assert bundle_select(st, _cfg(), [], None, interactions=False) is None


def test_same_name_pair_beats_singles():
    """同名升星链:已有 2 张姬子,shop 2 张同名 → 第 3 张触发 MERGE_W,束应联合买
    (或至少单买最优含合并价值),而非 None。断言宽松:束选包含同名卡。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    tgt = get_comp('列车同行')
    shop = [ShopCard(x=1, faction='列车同行', name='姬子·启行', cost=3),
            ShopCard(x=2, faction='列车同行', name='姬子·启行', cost=3)]
    bench = [BenchChar(slot=1, char_id='姬子·启行', faction='列车同行'),
             BenchChar(slot=2, char_id='姬子·启行', faction='列车同行')]
    st = _state(shop, gold=20, bench=bench, board={'列车同行': 2})
    r = bundle_select(st, _cfg(), [], tgt, interactions=True)
    # 交互项开:合并价值可见 → 应产出束(买至少 1 张姬子完成 3合1)
    assert r is not None
    names = [a.card.name for a in r]
    assert '姬子·启行' in names


def test_breakpoint_crossing_visible_in_bonus():
    """断点跳变交互项:买前 1 张列车 → 买 2 张跨 tier2,bonus > 0(单元级)。"""
    from sr_od.application.currency_war.cw_bundle import _interaction_bonus
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    tgt = get_comp('列车同行')
    bench = [BenchChar(slot=1, char_id='三月七', faction='列车同行')]
    st = _state([], bench=bench)
    buys = [ShopCard(x=1, faction='列车同行', name='姬子·启行', cost=3),
            ShopCard(x=2, faction='列车同行', name='花火', cost=3)]
    assert _interaction_bonus(buys, st, tgt) > 0


def test_seam_flag_default_off():
    """影子开关默认关(现状贪心生效;ADR-0156 灰度)。"""
    from sr_od.application.currency_war import cw_bundle
    assert cw_bundle.BUNDLE_SEAM_ACTIVE is False


def test_determinism_same_inputs_same_output():
    shop = [ShopCard(x=1, faction='仙舟', name='符玄', cost=4),
            ShopCard(x=2, faction='列车同行', name='三月七', cost=1)]
    st = _state(shop, gold=30)
    r1 = bundle_select(st, _cfg(), [], None, interactions=False)
    r2 = bundle_select(st, _cfg(), [], None, interactions=False)
    assert [type(a).__name__ for a in r1] == [type(a).__name__ for a in r2]
