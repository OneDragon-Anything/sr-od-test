"""备战帧判定测试:prep_anchors_hit 备战两识别标志判定(第二识别标志三形态)
+ is_prep_like_frame 停机钩子门的合成确认浮层段。

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
from collections import OrderedDict

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController

from sr_od.application.currency_war.kernel import cw_obs_core
from sr_od.application.currency_war.kernel.cw_obs_core import (
    is_prep_like_frame,
    prep_anchors_hit,
)
from sr_od.application.currency_war.obs import cw_synthesis_overlay_obs as overlay_mod
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


# ===== is_prep_like_frame 停机钩子门:合成确认浮层段 =====

#: 实机浮层帧(浮层的最高档):✓ 按钮的位置高出旧画面档固定搜索框的上沿,两段式判定
#: 得到的屏名是「货币战争-备战」——本用例判否只能来自浮层这一段。
_OVERLAY_FRAME: tuple[str, str] = ('货币战争-备战', 'rail_badge_absent_r2')
#: 商店面板展开帧(两段式判定的屏名 = 「货币战争-备战-开商店」)。
_SHOP_OPEN_FRAME: tuple[str, str] = ('货币战争-备战-开商店', 'shop_open')


def test_overlay_frame_is_not_prep_like(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """浮层帧判非备战帧:屏名认成备战、合成确认浮层在场 → False。

    浮层在场的帧装备栏读数已知失真,采集与停机钩子不该在这一帧上跑。同一帧再判
    一次(一帧内多个钩子各调一次)结果相同,识别只算一次——按帧缓存。"""
    if not test_context.has_screen(*_OVERLAY_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_OVERLAY_FRAME[0]}/{_OVERLAY_FRAME[1]}.webp')
    frame = test_context.load_screen(*_OVERLAY_FRAME)
    # 「识别只算一次」要数识别次数,前提是这一帧此前没被别的用例放进过按帧缓存
    # (缓存是模块级的)。换成本用例自己的空缓存:用例之间互不依赖,也不把这一帧
    # 留给后面的用例。
    monkeypatch.setattr(cw_obs_core, '_SYNTHESIS_OVERLAY_CACHE', OrderedDict())
    real_read = overlay_mod.read_synthesis_overlay_of
    reads: list[int] = []

    def _counting_read(ctx, screen):
        reads.append(1)
        return real_read(ctx, screen)

    monkeypatch.setattr(overlay_mod, 'read_synthesis_overlay_of', _counting_read)

    assert is_prep_like_frame(test_context, frame) is False, \
        '合成确认浮层在场的帧应判非备战帧'
    assert is_prep_like_frame(test_context, frame) is False, \
        '同一帧再判一次结果应相同'
    assert len(reads) == 1, f'同一帧的浮层识别应只算一次,实际算了 {len(reads)} 次'


def test_shop_open_frame_skips_overlay_check_and_stays_prep_like(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """屏名是开商店的帧不识别浮层、仍判备战帧。

    商店开着的画面不读右侧装备(用户口径):识别函数换成触碰即炸的桩,被调用就红;
    判定结果仍是备战帧——钩子在这种帧上照常可跑。"""
    if not test_context.has_screen(*_SHOP_OPEN_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_SHOP_OPEN_FRAME[0]}/{_SHOP_OPEN_FRAME[1]}.webp')
    frame = test_context.load_screen(*_SHOP_OPEN_FRAME)

    def _must_not_read(ctx, screen):
        raise AssertionError('商店开着的帧不应识别合成确认浮层(不读右侧装备)')

    monkeypatch.setattr(overlay_mod, 'read_synthesis_overlay_of', _must_not_read)

    assert is_prep_like_frame(test_context, frame) is True, \
        '开商店帧不识别浮层,应照现有两段式判定为备战帧'
