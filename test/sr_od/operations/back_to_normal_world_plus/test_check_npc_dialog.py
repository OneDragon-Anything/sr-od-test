"""BackToNormalWorldPlus.check_npc_dialog(对话态守卫)单元测试。"""

from __future__ import annotations

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import fast_sleep
from test.sr_od.operations.back_to_normal_world_plus.harness import _WatchedBackToNormal

from one_dragon.base.geometry.point import Point
from one_dragon.base.matcher.match_result import MatchResult
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus
from sr_od.operations.interact.talk_interact import TalkInteract


class _FakeMatchList:
    """够用的 MatchResultList 假件:只有 ``max``(守卫只消费 ``r.max.center``)。"""

    def __init__(self, x: int, y: int, w: int = 60, h: int = 30) -> None:
        self.max = MatchResult(1, x, y, w, h)


class TestNpcDialogGuard:
    """对话态守卫(check_npc_dialog)单元测试。

    背景(2026-08-26 实机事故):登录落点=活动摊位 NPC 对话态,对话 UI 遮蔽右上角
    图标,check_screen 所有既有分支不命中,兜底点「菜单-右上角返回」与对话的
    隐藏按钮重叠 → 一点把对话 UI 收掉 → 裸场景假象 + 键盘输入被吞。

    守卫语义(加严后,逐帧反应式):

    - 告别类选项命中 → 点选项退出对话(WAIT,同帧不落兜底);
    - 交互区无告别词(含只有未知文字)→ None,落回原兜底——「区域有字」是弱证据,
      不再单独构成对话态(2026-08-27 run 46:CW 大厅面板文字曾被误判成未知对话
      选项 → 点空白推进 → retry 永动;CW 大厅改由 check_screen 专属分支接管)。
    """

    BLANK = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def _make_op(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> tuple[_WatchedBackToNormal, list[Point], list[Point]]:
        """构造 op + 记录 mouse_move/click 序列;禁用守卫的采集截图钩子(不写 .debug)。"""
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'save_screenshot', lambda self, *a, **kw: None,
        )
        op = _WatchedBackToNormal(test_context)
        moves: list[Point] = []
        clicks: list = []

        def _record_move(pos, *args, **kwargs):
            moves.append(pos)
            return True

        def _record_click(pos=None, *args, **kwargs):
            clicks.append(pos)
            return True

        # MockController 无 mouse_move 属性(生产 controller 才有),raising=False 补桩
        monkeypatch.setattr(
            op.ctx.controller, 'mouse_move', _record_move, raising=False,
        )
        monkeypatch.setattr(
            op.ctx.controller, 'click', _record_click, raising=False,
        )
        return op, moves, clicks

    def test_farewell_clicked(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """告别选项命中:点选项中心(裁剪区坐标 + 交互区左上偏移),WAIT 不落兜底。"""
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        # 选项命中在交互区内相对坐标 (100, 80) → 绝对坐标 = +INTERACT_RECT.left_top
        monkeypatch.setattr(
            test_context.ocr, 'match_words',
            lambda image, words, **kw: {'告别': _FakeMatchList(100, 80)},
        )

        # 命中路径 round_wait(wait=1) 会真睡,包 fast_sleep 免空等
        with fast_sleep():
            result = op.check_npc_dialog(self.BLANK)

        assert result is not None
        assert result.is_success is False  # round_wait 非成功、也非兜底点击
        assert '对话态-告别' in (result.status or '')
        # 与 TalkInteract 同款:先 mouse_move 停留再 click(pc_alt 语义在真机,测试只锁坐标)
        # 期望坐标 = 命中框中心(MatchResult(100,80,60,30) → (130,95)) + 交互区左上偏移
        assert len(moves) == 1
        assert int(moves[0].x) == 130 + TalkInteract.INTERACT_RECT.left_top.x
        assert int(moves[0].y) == 95 + TalkInteract.INTERACT_RECT.left_top.y
        # click 不带坐标(选项位置已由 mouse_move 定位),且只点了一次
        assert len(clicks) == 1 and clicks[0] is None

    def test_unknown_options_no_blind_click(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """只有未知文字、无告别词:不构成对话态证据 → None 落回兜底,零动作。

        加严(2026-08-27 run 46 实证):旧版把交互区未知文字当「未知对话
        选项」点空白推进 + RETRY——选项态下空白推进无效,形成 retry 永动,且
        空白点击落在任意未知画面上有误触风险。
        """
        op, moves, clicks = self._make_op(test_context, monkeypatch)
        monkeypatch.setattr(
            test_context.ocr, 'match_words', lambda image, words, **kw: {},
        )
        monkeypatch.setattr(
            test_context.ocr, 'run_ocr',
            lambda image, *a, **kw: {'今天有什么好货': _FakeMatchList(50, 50)},
        )

        result = op.check_npc_dialog(self.BLANK)

        assert result is None, (
            f'未知文字不应构成对话态证据,status={getattr(result, "status", None)}'
        )
        assert clicks == [] and moves == [], '守卫不触发时不允许任何点击/移动'
