"""cw_observation_gate 单测(r324 框架复用版;flag off 零接线)。"""
from __future__ import annotations

import numpy as np

from sr_od.application.currency_war.cw_observation_gate import (
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
    """离线 op 桩:r324 后 gate 走 screen_utils.get_match_screen_name
    (框架 id_mark 体系),桩提供 ctx;画面判定用 monkeypatch
    screen_utils(见各测试)。"""

    def __init__(self, frames):
        self._frames = list(frames)
        self.park_calls = 0
        self.ctx = _FakeCtx()

    def park_cursor(self):
        self.park_calls += 1

    def screenshot(self):
        if not self._frames:
            raise RuntimeError('no more frames')
        return self._frames.pop(0)


class _FakeCtx:
    """最小 ctx 桩(gate 只透传给 screen_utils,由 monkeypatch 接管)。"""

    screen_loader = None


def _gray(w=1920, h=1080, v=128):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = v
    return img


def test_returns_stable_frame_when_fingerprint_constant(monkeypatch):
    """静止画面:首尾指纹一致且持续 min_stable_s → 返回帧。"""
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
    clk = _TickingClock(step=0.3)   # 每轮询推进 0.3s
    frames = [_gray(), _gray(), _gray(), _gray(), _gray(), _gray()]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (),
            'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=clk)
    assert out is not None
    assert op.park_calls == 1


def test_timeout_returns_none_when_never_stable(monkeypatch):
    """画面持续变化:超时 → None(None 语义:调用方走旧路径)。"""
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
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

    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (Rect(0, 0, 64, 64),),
            'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_Tick())
    assert out is None


def test_anchor_blip_recovery_returns_frame(monkeypatch):
    """r327 回归(终审 B):锚短暂 miss 后恢复(指纹未变)→
    稳定窗必须重新达成并返帧——旧 bug 只重置 stable_since
    不重置 first_fp,恢复后 same 成立跳过重设分支 → 永超时
    →(director 站)3-strike 停机。

    ADR-0264 注:fast_confirm 默认开时后续确认轮跳过 OCR,锚
    blip 序列不再被逐轮观测——本锁显式 fast_confirm=False 保持
    「每轮 OCR」旧口径,专锁 r327 锚 miss 重置语义(blip 场景
    下快路径回锚由 test_cw_gate_fast_confirm 覆盖)。"""
    from one_dragon.base.screen import screen_utils as su
    _seq = ['x', None, None, 'x', 'x', 'x', 'x', 'x']   # 1 miss 后恢复
    _i = {'n': 0}

    def _fake(ctx, screen, screen_name_list, crop_first=False):
        v = _seq[min(_i['n'], len(_seq) - 1)]
        _i['n'] += 1
        return v
    monkeypatch.setattr(su, 'get_match_screen_name', _fake)
    frames = [_gray() for _ in range(8)]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 6.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_TickingClock(0.3),
                            fast_confirm=False)
    assert out is not None, '锚 blip 恢复后必须能返帧(r327 回归锁)'


def test_screenshot_exception_raises_not_none():
    """终验 P1①:截图异常 → raise(非 None)——异常与超时分流;
    折叠进 None 会被 None 语义表接成 3-strike 停机。"""
    clk = _FakeClock()

    class _Boom(_FakeOp):
        def screenshot(self):
            raise RuntimeError('offline')

    op = _Boom([])
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (),
            'timeout_s': 1.0, 'min_stable_s': 0.3}
    try:
        wait_stable_frame(op, profile=prof, clock=clk)
        raised = False
    except RuntimeError:
        raised = True
    assert raised, '异常必须 raise,不得折叠进 None'


def test_fingerprint_changes_with_pixels():
    """指纹随像素变化(基元在 cv2_utils;r324 下沉)。"""
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.utils import cv2_utils
    r = (Rect(0, 0, 64, 64),)
    a = cv2_utils.fingerprint_in_rects(_gray(v=10), r)
    b = cv2_utils.fingerprint_in_rects(_gray(v=10), r)
    c = cv2_utils.fingerprint_in_rects(_gray(v=200), r)
    assert cv2_utils.fingerprint_same(a, b)
    assert not cv2_utils.fingerprint_same(a, c)
    # 阈值容忍:小噪声(±2)视为同帧(局36 diag:字节恒等被
    # 截屏噪声否决)
    noisy = cv2_utils.fingerprint_in_rects(_gray(v=12), r)
    assert cv2_utils.fingerprint_same(a, noisy)


def test_poll_cost_exceeding_budget_returns_frame(monkeypatch):
    """r344 回归锁(局37 停机根因):单轮 poll 成本(截图+OCR)
    超过整个超时预算、画面稳定 → gate 仍必须返帧——旧实现
    `while _now() < deadline` 在首轮 poll 后直接退出,稳定窗
    结构性不可能达成(diag {'screen':0,'fp':1,'ok':0}),
    director 3-strike ping-pong 停机。grace poll 兜底。"""
    from one_dragon.base.screen import screen_utils as su
    monkeypatch.setattr(su, 'get_match_screen_name',
                        lambda ctx, screen, screen_name_list, crop_first=False:
                        screen_name_list[0])
    clk = _FakeClock()
    frames = [_gray(), _gray(), _gray()]
    op = _FakeOp(frames)
    _orig_shot = op.screenshot

    def _slow_shot():
        clk.advance(6.0)   # 单轮 poll 成本 6s > timeout 2s(实机全图 OCR ~5s)
        return _orig_shot()
    op.screenshot = _slow_shot
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 2.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=clk)
    assert out is not None, 'poll 成本超预算时稳定帧不得被饿死(r344 锁)'


def test_screen_match_uses_fullframe_ocr_for_cache_reuse(monkeypatch):
    """r344 传参锁(用户定调 2026-08-22):gate poll 的屏判定必须
    crop_first=False——全图 OCR 按 id(image) 缓存,同帧多消费者
    (gate 判 4 个 id_mark 区首区触发、后续全缓存命中;gate 末帧
    传 _observe 后 heavy 观察全部命中)共享一次全图 OCR。
    cropped 口径丢弃缓存复用且小 area 易漏字(项目统一 False)。"""
    from one_dragon.base.screen import screen_utils as su
    _seen: list[bool] = []

    def _rec(ctx, screen, screen_name_list, crop_first=False):
        _seen.append(crop_first)
        return screen_name_list[0]
    monkeypatch.setattr(su, 'get_match_screen_name', _rec)
    frames = [_gray(), _gray()]
    op = _FakeOp(frames)
    prof = {'screen_list': ['x'], 'expect_screen': 'x',
            'fingerprint_rects': (), 'timeout_s': 5.0,
            'min_stable_s': 0.5}
    out = wait_stable_frame(op, profile=prof, clock=_TickingClock(0.3))
    assert out is not None
    assert _seen and not any(_seen), \
        f'gate 屏判定必须全图 OCR(crop_first=False)复用缓存,实际 {_seen}'


def test_profile_timeouts_cover_fullframe_ocr_poll_cost():
    """r344 预算锁:profile timeout 必须 ≥2 轮全图 OCR poll
    (~5s/轮实机)+余量——旧 4.5s<单轮成本,稳定窗结构性饿死
    (局37 ping-pong 停机根因)。防未来调回小值忘了成本模型。"""
    from sr_od.application.currency_war.cw_observation_gate import (
        PROFILE_CLOSED,
        PROFILE_OPEN,
        PROFILE_POPUP,
    )
    for name, prof in (('closed', PROFILE_CLOSED), ('open', PROFILE_OPEN),
                       ('popup', PROFILE_POPUP)):
        assert prof['timeout_s'] >= 12.0, \
            f'{name} timeout={prof["timeout_s"]} 必须 ≥12s(2 轮全图 OCR poll+余量)'
