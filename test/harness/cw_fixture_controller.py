"""CW 画面 op 剧本控制器(fixture_controller 的 CW 扩展;SR 侧自有,
非 ZZZ 同步文件)。

基类 :class:`FixtureController` 缺 ``mouse_move``——CW 画面 op 的动态
坐标点击链统一先 ``mouse_move`` 防吞再 ``click``(先例 =
cw_pick_partner_action),缺它会 AttributeError 被框架吞成异常重试
(伪失败形态,test_prep_special_flow 同款教训)。本扩展补记录面:

- ``recorded_mouse_moves`` = mouse_move 坐标序(机械时序断言);
- ``recorded_drags`` = drag_to 双端序(拖拽源/终点断言,CwSelectProtagonist
  三步链与换抓点序列的断言载体)。
"""

from __future__ import annotations

from test.conftest import SrTestContext
from test.harness.fixture_controller import FixtureController


class CwFixtureController(FixtureController):
    """CW 剧本扩展控制器:mouse_move + drag_to 记录(基类缺位补全)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_drags: list[tuple[tuple[int, int] | None,
                                        tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        self.recorded_mouse_moves.append((int(pos.x), int(pos.y)))

    def drag_to(self, end, start=None, duration: float = 0.5,
                hold_time: float = 0.0) -> None:
        start_pt = ((int(start.x), int(start.y)) if start is not None
                    else None)
        self.recorded_drags.append((start_pt, (int(end.x), int(end.y))))
