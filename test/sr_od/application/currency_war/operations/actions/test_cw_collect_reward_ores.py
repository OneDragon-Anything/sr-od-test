"""CwCollectRewardOres 入口画面锚与备战拾取回归(fixture harness 剧本)。

锁的设计约定(被测单一源 = cw_collect_reward_ores;设计出处 =
docs/develop/sr_od/application/currency_war/changes/2026-11-18-cw-fix1-smallfixes/design.md §2.2):

- 入口画面锚(防错屏守卫,非判效):错屏显式失败带实际画面名,点击零发生——
  替代此前「错屏识别空 → round_success('场上无晶矿')」假成功(实机验收期
  两次定谳事故同机制:错屏实况 = 主角选择画面,晶矿识别恒空报假成功);
- 守卫判别力依据(浮层改版后此依据即排查起点):框架画面判定对 id_mark 组合
  要求全中才算命中(screen_utils.is_target_screen);备战档 id_mark 四件 =
  备战标识-购买经验 / 按钮-出战 / 标识-前台区域 / 标识-后台区域,其中
  「标识-前台区域」(850,275,1070,340) 在开商店帧下完全落于商店牌区
  (300,228,1560,326)、在开拓商店帧下完全落于商品卡区 (430,145,1415,418)
  ——板面文本被浮层内容覆盖 → id_mark 不全中 → 备战不命中 → 守卫转 fail
  (浮层改版若致判别失效,本文件错屏用例先红);
- 备战屏空读成功语义保留:无晶矿帧仍 round_success('场上无晶矿'),只有错屏
  才转 fail;逐点点击 = min(球数, max_clicks),坐标 = 球心(球数 = fixture
  命名真值,与帧内容一致的事前核验记录见 reward_spheres_4 → 4 球)。
"""

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.currency_war.operations.actions.cw_collect_reward_ores import (
    CwCollectRewardOres,
)

#: 错屏帧:开商店浮层(备战档 id_mark 不全中的判别力实证帧)。
_SHOP_OPEN_FRAME: tuple[str, str] = ('货币战争-备战-开商店', 'shop_open')
#: 错屏帧:开拓商店浮层(同上,第二浮层形态)。
_PIONEER_FRAME: tuple[str, str] = ('货币战争-备战-开拓商店', '商店展开')
#: 备战帧:带晶矿(fixture 命名 = 球数真值)。
_SPHERES_4_FRAME: tuple[str, str] = ('货币战争-备战', 'reward_spheres_4')
_SPHERES_8_FRAME: tuple[str, str] = ('货币战争-备战', 'reward_spheres_8')
#: 备战帧:奖励区无晶矿。
_EMPTY_FRAME: tuple[str, str] = ('货币战争-备战', 'reward_panel_empty')

#: 备战画面档(守卫锚集合与区域-奖励 rect 所在档)。
_PREP_SCREEN: str = '货币战争-备战'


class _WatchedCollectOres(WatchdogOperationMixin, CwCollectRewardOres):
    """带看门狗的 op(流程测试防无限轮)。"""


def _run_op(test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch,
            phases: list[dict],
            max_clicks: int = 8) -> tuple[FixtureController, OperationResult]:
    """装假控制器 + 钉住共享 ctx 画面状态 + 跑完整 execute()。

    共享 ``test_context`` 的 screen_loader 画面名是跨测试残留高危面(守卫的
    二次识别从 current/last 出发 BFS),显式钉 None 走确定性全量扫描路径,
    monkeypatch 测试结束自动还原(i1 防单跑能过全量必挂)。
    """
    monkeypatch.setattr(test_context.screen_loader, 'current_screen_name', None)
    monkeypatch.setattr(test_context.screen_loader, 'last_screen_name', None)
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases(phases)
    op = _WatchedCollectOres(test_context, max_clicks=max_clicks)
    op._init_watchdog()  # type: ignore[attr-defined]
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)
    return ctrl, result


def _require_screens(test_context: SrTestContext,
                     frames: list[tuple[str, str]]) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in frames:
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _reward_rect(test_context: SrTestContext) -> tuple[int, int, int, int]:
    """备战档「区域-奖励」pc_rect(点击落区断言的建档单一源)。"""
    area = test_context.screen_loader.get_area(_PREP_SCREEN, '区域-奖励')
    assert area is not None and area.pc_rect is not None, '备战档缺 区域-奖励 area'
    r = area.pc_rect
    return r.x1, r.y1, r.x2, r.y2


@pytest.mark.parametrize('frame,expected_screen', [
    (_SHOP_OPEN_FRAME, '货币战争-备战-开商店'),
    (_PIONEER_FRAME, '货币战争-备战-开拓商店'),
])
def test_wrong_screen_fails_with_real_name(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        frame: tuple[str, str], expected_screen: str) -> None:
    """错屏显式失败:非备战浮层帧 → fail 且 status 带实际画面名,点击零发生
    (守卫拦在晶矿识别之前——错屏识别空报「场上无晶矿」的假成功形态退役锁)。"""
    _require_screens(test_context, [frame])
    ctrl, result = _run_op(test_context, monkeypatch, [{'frame': frame}])

    assert not result.success, f'错屏应 fail,实际 success:{result.status}'
    assert expected_screen in (result.status or ''), \
        f'fail status 应带实际画面名 {expected_screen}:{result.status}'
    assert ctrl.recorded_clicks == [], f'错屏不应有点击:{ctrl.recorded_clicks}'


def test_prep_spheres_click_each_ball_center(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """备战回归:带晶矿帧逐球点击(球数 = fixture 命名真值 4),落点全在
    「区域-奖励」rect 内且与 round data 一致(球心口径;不现算识别期望——
    与被测同源复刻为测试禁项)。"""
    _require_screens(test_context, [_SPHERES_4_FRAME])
    ctrl, result = _run_op(test_context, monkeypatch, [{'frame': _SPHERES_4_FRAME}])

    assert result.success, f'备战帧应 success:{result.status}'
    assert result.data['collected'] == 4
    assert len(ctrl.recorded_clicks) == 4
    rect = _reward_rect(test_context)
    for ore, click in zip(result.data['ores'], ctrl.recorded_clicks,
                          strict=True):
        assert (ore['x'], ore['y']) == (click.x, click.y)
        assert rect[0] <= click.x <= rect[2] and rect[1] <= click.y <= rect[3], \
            f'点击应落奖励区球心:({click.x},{click.y}) 不在 {rect}'


def test_prep_spheres_respect_max_clicks_cap(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """点击数 = min(球数, max_clicks):8 球帧 + 上限 3 → 恰 3 次点击
    (截断口径,防识别噪声连环误点的参数面契约)。"""
    _require_screens(test_context, [_SPHERES_8_FRAME])
    ctrl, result = _run_op(test_context, monkeypatch,
                           [{'frame': _SPHERES_8_FRAME}], max_clicks=3)

    assert result.success
    assert len(ctrl.recorded_clicks) == 3
    assert result.data['collected'] == 3


def test_prep_empty_still_reports_no_ore(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """备战屏空读成功语义保留:确认在备战 + 无晶矿帧 → 仍 success
    '场上无晶矿',零点击(只有错屏才转 fail)。"""
    _require_screens(test_context, [_EMPTY_FRAME])
    ctrl, result = _run_op(test_context, monkeypatch, [{'frame': _EMPTY_FRAME}])

    assert result.success, f'备战空读应保留 success:{result.status}'
    assert '场上无晶矿' in (result.status or '')
    assert result.data['collected'] == 0
    assert ctrl.recorded_clicks == []


def test_max_clicks_out_of_range_rejected(
        test_context: SrTestContext) -> None:
    """max_clicks 越界构造期 ValueError(op 契约完整面;1-12 之外拒绝)。"""
    for bad in (0, 13, -1):
        with pytest.raises(ValueError):
            CwCollectRewardOres(test_context, max_clicks=bad)
