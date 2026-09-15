"""选择伙伴 op 选选流序回归锁(2026-09-15 实机卡死事故的行为锁)。

事故机制(细节单一源 = docs/game/screens/currency_war_choose_partner.md):
旧「选中态 gate」= 全屏 OCR 找「已选择」,LCS 阈值按关键词归一(3 字词与
本屏常驻指令句/「请选择强化角色」共享子序列「选择」即达 0.5)→ 本屏恒
误命中 → op 恒跳过点选候选、每轮只点置灰确认钮 → 游戏拒绝,节点预算耗尽
fail,外环重派无限循环(实机 P1-r1 十八连 fail,~12 分钟零推进)。

本文件锁两个行为面(真帧 fixture 驱动,真 OCR 识别链,FixtureController
记录点击;SIFT 立绘识别桩化为 label 名回落——决策质量不在本锁范围):

1. **选选流序锁**:未选中态帧(提示在场)上,首个 click 必须落在候选卡区
   且先于确认钮 click(先选后确认);确认 click 后 overlay 关(剧本推进
   备战帧)→ op success(完成门 = 标识消失)。
2. **确认被拒有界重试锁**:overlay 恒在帧(确认被拒形态)→ 「点选→确认」
   脉冲恰跑满 ``CONFIRM_REJECT_MAX`` 次 → 显式 fail(状态含「确认被拒」),
   点击总数有界,先于节点预算(10)耗尽,看门狗零触发 —— 禁无限原样重试。
   同锁兼钉:重入轮决策一次(全部点选落同一点位,防跨轮决策抖动换候选)。

fixture = ``screens/货币战争-列车同行/伙伴遮罩-未选中.webp``(2026-09-15
事故帧 1-1 归档)与 ``screens/货币战争-备战/deployed_2star.webp``(overlay
关闭后的备战帧)。
"""
from __future__ import annotations

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_partner as partner_mod,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_partner import (
    CwScreenPartner,
)

_PARTNER_SCREEN = '货币战争-列车同行'
_OVERLAY_FIXTURE = '伙伴遮罩-未选中'
_BOARD_FRAME = ('货币战争-备战', 'deployed_2star')


class _NoSleep:
    """partner 模块内 ``time`` 替身:点击后等待记录不真睡(fast_sleep 只盖
    op 框架的轮间等待,盖不到本模块自己的 ``time.sleep``)。"""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


def _make_watched_op(test_context, monkeypatch) -> CwScreenPartner:
    """真类 + 桩面装配:cw_match=None(idx0 兜底,决策质量不在锁范围)、
    SIFT 立绘识别回落 label 名(跳过模板库加载)、模块内 time 不真睡。"""

    class _WatchedPartner(WatchdogOperationMixin, CwScreenPartner):
        pass

    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    op = _WatchedPartner(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        op, '_identify_portraits',
        lambda screen, cands: [n for n, _cx, _cy in cands])
    monkeypatch.setattr(partner_mod, 'time', _NoSleep())
    return op


def _run_execute(test_context, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _in_rect(point, rect) -> bool:
    return rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2


def _rect_of(test_context, area_name: str):
    area = test_context.screen_loader.get_area(_PARTNER_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, (
        f'建档缺失:{_PARTNER_SCREEN}/{area_name}(测试依赖 screen_info area)')
    return area.pc_rect


@pytest.fixture()
def fixture_controller(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """注入 FixtureController(monkeypatch 自动还原,防污染 session 级 ctx)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # partner op 点击链 = mouse_move + click(harness 未备 mouse_move 桩,
    # 本地补 no-op;点击记录只看 click)。
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def test_partner_selects_candidate_before_confirm(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """选选流序锁:未选中帧上先点候选卡后点确认;确认后 overlay 关 → success。

    事故反形:旧 gate 误命中时首个(且唯一)click 落在置灰确认钮上、候选
    零点击 —— 本锁红 = 流序回退(未选先确认)或完成门失效。
    """
    if not test_context.has_screen(_PARTNER_SCREEN, _OVERLAY_FIXTURE):
        pytest.skip(f'存档截图缺失:screens/{_PARTNER_SCREEN}/{_OVERLAY_FIXTURE}.webp')
    if not test_context.has_screen(*_BOARD_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_BOARD_FRAME[0]}/{_BOARD_FRAME[1]}.webp')

    fixture_controller.set_phases([
        {
            # 确认 click 落在确认钮内 → 游戏接受,overlay 关(推进备战帧)。
            'frame': (_PARTNER_SCREEN, _OVERLAY_FIXTURE),
            'exit': ('on_click_in', _PARTNER_SCREEN, '按钮-确认选择'),
        },
        {'frame': _BOARD_FRAME},   # terminal:overlay 已关,完成门应判 success。
    ])
    op = _make_watched_op(test_context, monkeypatch)

    result = _run_execute(test_context, op)

    assert result.success, (
        f'选择伙伴未成功完成:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')

    strip = _rect_of(test_context, '候选-卡区')
    confirm = _rect_of(test_context, '按钮-确认选择')
    clicks = fixture_controller.recorded_clicks
    assert clicks, f'零点击记录:{clicks}'
    first = clicks[0]
    assert _in_rect(first, strip) and not _in_rect(first, confirm), (
        f'首个 click 必须是候选卡点选(非确认钮):{first} '
        f'clicks={clicks}')
    assert any(_in_rect(p, confirm) for p in clicks[1:]), (
        f'确认钮 click 缺失(先选后确认流序断裂):{clicks}')
    assert fixture_controller.phase_idx == 1, (
        f'确认后应推进到备战帧:phase_idx={fixture_controller.phase_idx}')
    assert op._watchdog_round_count <= 4, (
        f'成功路径轮次应 ≤4(点选→确认→完成门):{op._watchdog_round_count}')


def test_partner_confirm_rejected_bounded_retry(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """确认被拒有界重试锁:overlay 恒在(置灰确认被游戏拒)→ 脉冲恰
    CONFIRM_REJECT_MAX 次 → 显式 fail,点击有界、先于节点预算、看门狗零触发。

    事故反形:旧实现每执行烧满 10 轮(20 click)且 fail 原因无形态区分,
    外环无限重派 —— 本锁红 = 有界防线回退或失败语义丢失。
    """
    if not test_context.has_screen(_PARTNER_SCREEN, _OVERLAY_FIXTURE):
        pytest.skip(f'存档截图缺失:screens/{_PARTNER_SCREEN}/{_OVERLAY_FIXTURE}.webp')

    # 无 exit 的单 phase = 帧恒不变(确认被拒、overlay 不关的实机形态)。
    fixture_controller.set_phases([
        {'frame': (_PARTNER_SCREEN, _OVERLAY_FIXTURE)},
    ])
    op = _make_watched_op(test_context, monkeypatch)

    result = _run_execute(test_context, op)

    assert not result.success, (
        f'确认被拒形态不得假成功:{result!r}')
    assert '确认被拒' in (result.status or ''), (
        f'失败状态须含「确认被拒」(形态可判读):{result.status!r}')

    strip = _rect_of(test_context, '候选-卡区')
    confirm = _rect_of(test_context, '按钮-确认选择')
    clicks = fixture_controller.recorded_clicks
    card_clicks = [p for p in clicks if _in_rect(p, strip) and not _in_rect(p, confirm)]
    confirm_clicks = [p for p in clicks if _in_rect(p, confirm)]
    assert len(confirm_clicks) == CwScreenPartner.CONFIRM_REJECT_MAX, (
        f'确认脉冲应恰跑满上限 {CwScreenPartner.CONFIRM_REJECT_MAX} 次:'
        f'{len(confirm_clicks)} clicks={clicks}')
    assert len(card_clicks) == CwScreenPartner.CONFIRM_REJECT_MAX, (
        f'未选中实证下每脉冲都应重点选候选:{len(card_clicks)} clicks={clicks}')
    assert len(set(map(str, card_clicks))) == 1, (
        f'重入轮点位应稳定(决策一次,防跨轮换候选):{card_clicks}')
    assert op._watchdog_round_count <= CwScreenPartner.CONFIRM_REJECT_MAX + 2, (
        f'应在节点预算(10)耗尽前显式退出:{op._watchdog_round_count}')
