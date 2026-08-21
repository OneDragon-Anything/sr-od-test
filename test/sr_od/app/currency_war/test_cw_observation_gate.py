"""cw_observation_gate 单测(批次1 首件;flag off 零接线)。"""
from __future__ import annotations

import numpy as np

from sr_od.application.currency_war.cw_observation_gate import (
    _fingerprint,
    wait_stable_frame,
)


class _FakeClock:
    """可推进假时钟;作为 clock 传入时 gate 的 _sleep 也是它驱动。"""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s: float):
        self.t += s


class _TickingClock(_FakeClock):
    """每次被调用推进 poll 间隔——gate 的 while 轮询天然推进。"""

    def __init__(self, step: float = 0.3):
        super().__init__()
        self._step = step

    def __call__(self):
        self.t += self._step
        return self.t


class _FakeOp:
    """离线 op 桩:park/screenshot/round_by_* 可脚本化。"""

    def __init__(self, frames):
        self._frames = list(frames)
        self.park_calls = 0

    def park_cursor(self):
        self.park_calls += 1

    def screenshot(self):
        if not self._frames:
            raise RuntimeError('no more frames')
        return self._frames.pop(0)

    def round_by_ocr(self, frame, kw, **kw2):
        class R:
            is_success = True
        return R()

    def round_by_find_area(self, frame, scr, area, **kw2):
        class R:
            is_success = True
        return R()


def _gray(w=1920, h=1080, v=128):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = v
    return img


def test_returns_stable_frame_when_fingerprint_constant():
    """静止画面:首尾指纹一致且持续 min_stable_s → 返回帧。"""
    clk = _TickingClock(step=0.3)   # 每轮询推进 0.3s
    frames = [_gray(), _gray(), _gray(), _gray(), _gray(), _gray()]
    op = _FakeOp(frames)
    prof = {'anchor_screen': 'x', 'anchor_area': 'a',
            'fingerprint_rects': (),
            'circle_gate': False, 'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=clk)
    assert out is not None
    assert op.park_calls == 1


def test_timeout_returns_none_when_never_stable():
    """画面持续变化:超时 → None(None 语义:调用方走旧路径)。"""
    from one_dragon.base.geometry.rectangle import Rect
    frames = [_gray(v=v) for v in (10, 20, 30, 40, 50, 60, 70, 80,
                                   90, 100, 110, 120, 130, 140, 150,
                                   160, 170, 180, 190, 200)]
    op = _FakeOp(frames)

    class _Tick:
        def __init__(self):
            self.n = 0

        def __call__(self):
            self.n += 1
            return self.n * 0.3   # 20 帧×0.3=6s > timeout 5s

    prof = {'anchor_screen': 'x', 'anchor_area': 'a',
            'fingerprint_rects': (Rect(0, 0, 64, 64),),
            'circle_gate': False, 'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_Tick())
    assert out is None


def test_screenshot_exception_raises_not_none():
    """终验 P1①:截图异常 → raise(非 None)——异常与超时分流;
    折叠进 None 会被 None 语义表接成 3-strike 停机。"""
    clk = _FakeClock()

    class _Boom(_FakeOp):
        def screenshot(self):
            raise RuntimeError('offline')

    op = _Boom([])
    prof = {'anchor_screen': 'x', 'anchor_area': 'a',
            'fingerprint_rects': (), 'circle_gate': False,
            'timeout_s': 1.0, 'min_stable_s': 0.3}
    try:
        wait_stable_frame(op, profile=prof, clock=clk)
        raised = False
    except RuntimeError:
        raised = True
    assert raised, '异常必须 raise,不得折叠进 None'


def test_fingerprint_changes_with_pixels():
    """指纹随像素变化(首尾一致性判据的基元)。"""
    from one_dragon.base.geometry.rectangle import Rect
    r = (Rect(0, 0, 64, 64),)
    a = _fingerprint(_gray(v=10), r)
    b = _fingerprint(_gray(v=10), r)
    c = _fingerprint(_gray(v=200), r)
    assert a == b
    assert a != c
