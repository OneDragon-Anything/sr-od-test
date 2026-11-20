"""prep_anchors_hit 备战两识别标志判定测试(第二识别标志三形态)。

锁的设计约定(kernel/cw_obs_core.py::prep_anchors_hit,判定单一源):
- 门序 = 第一识别标志「备战标识-购买经验」先判,不命中恒 False(防
  overlay 半开帧从底层透出的单标志误判,prep.md §时序);
- 第二识别标志三形态任一同帧命中即认领:出战(常规)/跳过(免战子态,
  「跳过(N/N)」按钮替换)/选择主角(位面末 BOSS 战前变体态)——扩形态
  回归锁:任一形态被删,对应用例红;
- 三形态用识别替身锁判定结构(真档 OCR 路径由真帧用例单锁一条,避免
  同一判定跑三遍全图 OCR——识别贵,聚合一次)。
"""

from __future__ import annotations

import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController

from sr_od.application.currency_war.kernel.cw_obs_core import prep_anchors_hit
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

#: 判定涉及的四个识别标志(画面名, 区域名)——与生产判定同源,
#: 替身按键名回命中,键名漂移 = 生产改了识别标志,本测试红 = 提醒同步。
_FIRST_ANCHOR: tuple[str, str] = ('货币战争-备战', '备战标识-购买经验')
_FORM_BATTLE: tuple[str, str] = ('货币战争-备战', '按钮-出战')
_FORM_SKIP: tuple[str, str] = ('货币战争-备战', '按钮-跳过')
_FORM_SELECT_HERO: tuple[str, str] = ('货币战争-备战-选择主角', '按钮-选择主角')

#: 备战帧存档(真档真帧路径锁;缺档 skip,先例 = test_prep_special_flow)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_p1r9')


class _AnchorStubOp:
    """round_by_find_area 替身:按预登记 (画面名, 区域名) 集合回命中。

    只替换识别原语,不碰判定逻辑——被锁的是 prep_anchors_hit 的门序与
    三形态组合,不是识别本体(识别本体有真帧用例与建档验证辖)。
    """

    def __init__(self, hits: set[tuple[str, str]]) -> None:
        self._hits = hits
        self.queries: list[tuple[str, str]] = []

    def round_by_find_area(self, screen, screen_name: str, area_name: str,
                           crop_first: bool = False):
        self.queries.append((screen_name, area_name))
        hit = (screen_name, area_name) in self._hits
        return types.SimpleNamespace(is_success=hit)


@pytest.mark.parametrize(
    'second_form',
    [_FORM_BATTLE, _FORM_SKIP, _FORM_SELECT_HERO],
    ids=['出战', '跳过', '选择主角'],
)
def test_second_anchor_each_form_claims_prep_frame(second_form) -> None:
    """第一识别标志在场 + 第二识别标志任一形态同帧命中 → 认领备战(True)。

    三形态各锁一条:任一形态从判定链删除,对应参数用例红。"""
    op = _AnchorStubOp({_FIRST_ANCHOR, second_form})
    assert prep_anchors_hit(op, screen=object()) is True, \
        f'第一识别标志 + {second_form[1]} 应认领备战帧'


def test_first_anchor_miss_never_claims_even_with_all_forms() -> None:
    """第一识别标志不在场 → 恒 False,即使三形态全命中。

    防线语义 = 单识别标志在 overlay 半开帧可从底层透出命中,缺第一
    标志的第二标志命中不得认领(prep.md §时序)。"""
    op = _AnchorStubOp({_FORM_BATTLE, _FORM_SKIP, _FORM_SELECT_HERO})
    assert prep_anchors_hit(op, screen=object()) is False, \
        '缺第一识别标志时三形态全在场也不得认领'


def test_first_anchor_hit_without_second_form_not_prep() -> None:
    """仅第一识别标志在场(第二识别标志三形态全缺)→ False。

    常规画面误含备战标识的形近帧不得认领(认领 = 进备战分支,
    非备战帧误入会跑错处置)。"""
    op = _AnchorStubOp({_FIRST_ANCHOR})
    assert prep_anchors_hit(op, screen=object()) is False, \
        '仅第一识别标志命中不得认领备战帧'


def test_real_prep_frame_claims_via_battle_form(
        test_context: SrTestContext) -> None:
    """真档真帧路径锁:真备战存档帧(出战形态双标志在案)经真实
    screen_loader + OCR 判定 → True。锁识别原语接线的真实路径
    (替身用例锁不到的半边:画面档/area 配置缺失时本用例红)。"""
    if not test_context.has_screen(*_PREP_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_PREP_FRAME[0]}/{_PREP_FRAME[1]}.webp')
    ctrl = FixtureController(ctx=test_context)
    ctrl.set_phases([{'frame': _PREP_FRAME}])
    op = CwScreenPrep(test_context)
    assert prep_anchors_hit(op, ctrl.current_frame) is True, \
        '真备战帧(出战形态)应经真实识别链认领'
