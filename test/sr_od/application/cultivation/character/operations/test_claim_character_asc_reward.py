"""ClaimCharacterAscReward(领取角色晋阶奖励)流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_character.py
——晋阶预览窗口帧测试仓缺存档、识别类输入禁止合成),monkeypatch 识别层
构造 round 结果,驱动完整 ``execute()`` 节点图。

锁定的设计约定(出处 claim_character_asc_reward.py 模块 docstring 与
claim_loop 实现 + 负责人机制补充):
- 入口 NO_REWARD 分流:红点不命中 = 本无可领,零画面动作直接成功;
- 领取全链:打开预览 → 点领取 → 获得物品弹窗关闭 → 按钮消失 → 关窗收尾
  (负责人机制:游戏自动切下一级,op 不切阶段,循环只判按钮);
- 「领取」OCR 全词比对防线:「已领取」灰字不误点(末级领取后灰字残留帧
  误判 = 空转到预算耗尽)。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.cultivation.character.operations.claim_character_asc_reward import (
    ClaimCharacterAscReward,
)

_DETAIL: str = '角色-详情'
_PREVIEW: str = '角色-晋阶预览'
_LIST: str = '角色-列表'

# 领取循环每轮分类的第一个识别查询 = 获得物品浮层锚(优先级①),桩以它计轮
_LOOP_START: tuple[str, str] = (_PREVIEW, '文本-获得物品')


class _WatchedClaimAscReward(WatchdogOperationMixin, ClaimCharacterAscReward):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 30

    def __init__(self, ctx: SrTestContext) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。"""
        ClaimCharacterAscReward.__init__(self, ctx)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _install_script(
    monkeypatch: pytest.MonkeyPatch,
    ctx: SrTestContext,
    scenes: list[set[tuple[str, str]]],
    alert_by_round: dict[int, bool],
    claim_by_round: dict[int, Point | None],
) -> dict:
    """桩识别层并装记录器。

    :param scenes: 每轮 find_area 命中集合(轮由 _LOOP_START 锚计,入口轮 = 0)
    :param alert_by_round: 入口红点检测结果(桩 _has_asc_reward_alert)
    :param claim_by_round: 领取按钮定位结果(桩 _find_claim_btn)
    """
    state: dict = {'round': 0, 'find_events': [], 'find_clicks': []}

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        if (s_name, a_name) == _LOOP_START:
            state['round'] += 1
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is None:
            raise AssertionError(f'领取循环剧本耗尽:第 {state["round"]} 轮查询 {a_name}')
        if (s_name, a_name) in scene:
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
        state['find_clicks'].append((s_name, a_name))
        return self.round_success(status=a_name)

    def _fake_alert(self, screen) -> bool:
        return alert_by_round.get(state['round'], False)

    def _fake_claim(self, screen) -> Point | None:
        return claim_by_round.get(state['round'])

    monkeypatch.setattr(ClaimCharacterAscReward, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(ClaimCharacterAscReward, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(ClaimCharacterAscReward, '_has_asc_reward_alert', _fake_alert)
    monkeypatch.setattr(ClaimCharacterAscReward, '_find_claim_btn', _fake_claim)
    return state


def _record_controller_clicks(
    monkeypatch: pytest.MonkeyPatch, ctx: SrTestContext,
) -> list[tuple[int, int]]:
    """包装 controller.click 记录点击坐标(op 直点全部经 controller)。"""
    clicks: list[tuple[int, int]] = []
    real_click = ctx.controller.click

    def _recording_click(pos=None, press_time: float = 0, pc_alt: bool = False,
                         gamepad_key: str | None = None) -> bool:
        if pos is not None:
            clicks.append((int(pos.x), int(pos.y)))
        return real_click(pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctx.controller, 'click', _recording_click)
    return clicks


def _has_click_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> bool:
    """是否有点击落在建档区 pc_rect 内(坐标单一真相源 = screen_info)。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    rect = area.pc_rect
    return any(
        rect.x1 <= x <= rect.x2 and rect.y1 <= y <= rect.y2 for x, y in clicks
    )


def _run_op(op: ClaimCharacterAscReward) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


class TestClaimCharacterAscRewardFlow:

    def test_no_reward_exits_without_any_click(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口 NO_REWARD 分流:详情 TAB 在但红点不命中 = 本无可领。

        零画面动作直接成功——红点本无时不应打开晋阶预览窗口。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情')},  # 入口轮:列表不在、详情 TAB 在
        ]
        _install_script(monkeypatch, test_context, scenes,
                        alert_by_round={0: False}, claim_by_round={})
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedClaimAscReward(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'NO_REWARD', (
            f'红点不命中应直接 NO_REWARD 结束,status={result.status}'
        )
        assert clicks == [], f'无可领起点不应有任何画面点击:{clicks}'

    def test_claim_full_chain_returns_claimed(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """领取全链:打开预览 → 点领取 → 关获得弹窗 → 按钮消失 → 关窗收尾。

        剧本轮次:
        - 入口轮:红点命中 → HAS_REWARD;
        - 循环轮1:弹窗不在、标题锚在、按钮命中 → 点击领取;
        - 循环轮2:获得物品浮层在 → 点空白关闭;
        - 循环轮3:弹窗不在、标题锚在、按钮消失(游戏已自动切完各级) → 收尾。"""
        claim_point = Point(1795, 687)
        scenes = [
            {(_DETAIL, '按钮-属性详情')},                # 入口轮
            {(_PREVIEW, '标题-晋阶预览')},               # 轮1:按钮命中 → 点领取
            {(_PREVIEW, '文本-获得物品')},               # 轮2:关获得弹窗
            {(_PREVIEW, '标题-晋阶预览')},               # 轮3:按钮消失 → ALL_CLAIMED
        ]
        state = _install_script(monkeypatch, test_context, scenes,
                                alert_by_round={0: True},
                                claim_by_round={1: claim_point, 2: None, 3: None})
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedClaimAscReward(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'CLAIMED', (
            f'领取全链应以 CLAIMED 结束,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _PREVIEW, '按钮-领取'), (
            '按钮命中轮应对「领取」按钮执行点击'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-晋阶奖励红点'),
            (_PREVIEW, '点击区-关闭获得弹窗'),
            (_PREVIEW, '按钮-关闭'),
        ], f'find+click 序列(开预览/关获得弹窗/关预览)漂移:{state["find_clicks"]}'
        assert state['find_events'].count(_LOOP_START) == 3, (
            '领取循环应恰好分类 3 轮(领取/关弹窗/领完),轮数漂移 = 循环结构变化'
        )


class TestClaimBtnExactMatch:

    def test_claim_btn_full_word_match_only(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """「领取」按钮定位的全词比对防线。

        OCR 返回「已领取」灰字 → 不命中(返回 None);
        「已领取」与「领取」同框混排 → 只命中全词「领取」的框中心
        (lcs 子串会误命中灰字 = 空转到预算耗尽,此防线必须严格相等)。"""
        op = _WatchedClaimAscReward(test_context)

        claimed_only = [
            OcrMatchResult(c=0.95, x=1815, y=680, w=46, h=23, data='已领取'),
        ]
        monkeypatch.setattr(
            test_context.ocr_service, 'get_ocr_result_list',
            lambda *args, **kwargs: claimed_only)
        assert op._find_claim_btn(None) is None, (
            '「已领取」灰字不应命中领取按钮'
        )

        mixed = [
            OcrMatchResult(c=0.95, x=1815, y=680, w=46, h=23, data='已领取'),
            OcrMatchResult(c=0.97, x=1760, y=675, w=66, h=30, data='领取'),
        ]
        monkeypatch.setattr(
            test_context.ocr_service, 'get_ocr_result_list',
            lambda *args, **kwargs: mixed)
        point = op._find_claim_btn(None)
        assert point is not None, '全词「领取」应命中'
        assert (point.x, point.y) == (1760 + 66 / 2, 675 + 30 / 2), (
            f'命中点应为全词条目框中心,实际 {point}'
        )
