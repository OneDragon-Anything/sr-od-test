"""cw_observation_gate 提速锁(ADR-0264:fast_confirm + overlay 预置基线)。

- 方案 A(fast_confirm):锚命中 1 次后,后续稳定确认轮跳过全图 OCR
  只比指纹;指纹变化即回锚定模式;fast_confirm=False 关回旧行为。
- 方案 B(overlay 预置基线):overlay 关闭后预置首帧指纹 → gate
  首次锚命中即一轮达标(仍须锚命中+指纹一致,不裸跳)。
"""
from __future__ import annotations

import numpy as np
import pytest

from sr_od.application.currency_war.cw_observation_gate import (
    _PRESET_BASELINE,
    preset_stable_baseline,
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
    """每次被调用推进 step——gate 的 while 轮询天然推进。"""

    def __init__(self, step: float = 0.3):
        super().__init__()
        self._step = step

    def __call__(self):
        self.t += self._step
        return self.t


class _FakeOp:
    """离线 op 桩(gate 只用 ctx 透传 + screenshot/park_cursor)。"""

    def __init__(self, frames):
        self._frames = list(frames)
        self.park_calls = 0
        self.shot_count = 0
        self.ctx = _FakeCtx()

    def park_cursor(self):
        self.park_calls += 1

    def screenshot(self):
        if not self._frames:
            raise RuntimeError('no more frames')
        self.shot_count += 1
        return self._frames.pop(0)


class _FakeCtx:
    screen_loader = None


def _gray(w=1920, h=1080, v=128):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = v
    return img


@pytest.fixture(autouse=True)
def _clear_preset():
    """模块级基线表隔离:每条测试前后清空,防跨测试泄漏。"""
    _PRESET_BASELINE.clear()
    yield
    _PRESET_BASELINE.clear()


def _prof(min_stable_s: float = 0.5) -> dict:
    from one_dragon.base.geometry.rectangle import Rect
    return {
        'screen_list': ['x'],
        'expect_screen': 'x',
        'fingerprint_rects': (Rect(0, 0, 64, 64),),
        'timeout_s': 6.0,
        'min_stable_s': min_stable_s,
    }


def _patch_anchor_hit(monkeypatch, seq=None):
    """接管 get_match_screen_name;seq=None 恒命中,否则按序返回(None=miss)。"""
    from one_dragon.base.screen import screen_utils as su
    calls = {'n': 0}
    if seq is None:
        def _fake(ctx, screen, screen_name_list, crop_first=False):
            calls['n'] += 1
            return screen_name_list[0]
    else:
        def _fake(ctx, screen, screen_name_list, crop_first=False):
            v = seq[min(calls['n'], len(seq) - 1)]
            calls['n'] += 1
            return v
    monkeypatch.setattr(su, 'get_match_screen_name', _fake)
    return calls


def test_fast_confirm_skips_ocr_after_first_anchor(monkeypatch):
    """方案 A:锚命中 1 次后,后续确认轮不再调全图 OCR(指纹-only)。"""
    calls = _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray()] * 5)
    out = wait_stable_frame(op, profile=_prof(), clock=_TickingClock(0.3))
    assert out is not None
    assert calls['n'] == 1, \
        f'fast_confirm 下 OCR 锚判定只应调 1 次,实际 {calls["n"]}'


def test_fast_confirm_fingerprint_change_re_anchors(monkeypatch):
    """方案 A 兜底:指纹变化(屏可能已切换)→ 回锚定模式(重做 OCR)。"""
    calls = _patch_anchor_hit(monkeypatch)
    frames = [_gray(v=10), _gray(v=200), _gray(v=200),
              _gray(v=200), _gray(v=200), _gray(v=200)]
    op = _FakeOp(frames)
    out = wait_stable_frame(op, profile=_prof(), clock=_TickingClock(0.3))
    assert out is not None
    assert calls['n'] >= 2, \
        f'指纹变化后必须回锚定模式(重做 OCR),实际 OCR 调用 {calls["n"]}'


def test_fast_confirm_false_keeps_ocr_every_poll(monkeypatch):
    """A/B 口:fast_confirm=False 关回旧行为——每轮 poll 都做 OCR 锚判定。"""
    calls = _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray()] * 5)
    out = wait_stable_frame(op, profile=_prof(), fast_confirm=False,
                            clock=_TickingClock(0.3))
    assert out is not None
    assert calls['n'] >= 2, '关 fast_confirm 时每轮 poll 必须做 OCR 锚判定'


def test_preset_baseline_reaches_stable_in_one_poll(monkeypatch):
    """方案 B:overlay 预置基线后,gate 首次锚命中(1 轮 poll)即返帧。

    语义:仍须「锚命中 + 指纹一致」确认(不裸跳);预置时刻距今
    ≥ min_stable_s → 稳定窗一轮达标,跳过「从零等 2 轮」。
    """
    calls = _patch_anchor_hit(monkeypatch)
    frame = _gray()
    clk = _FakeClock()
    preset_stable_baseline(frame, profile=_prof(), clock=clk)
    assert 'x' in _PRESET_BASELINE, '预置必须落基线表'
    clk.advance(1.0)   # 预置时刻距今 1.0s ≥ min_stable 0.5
    op = _FakeOp([frame])
    out = wait_stable_frame(op, profile=_prof(), clock=clk)
    assert out is not None, '预置基线一致 + 锚命中 → 1 轮即稳定'
    assert op.shot_count == 1, f'应只消费 1 帧,实际 {op.shot_count}'
    assert calls['n'] == 1
    # 单次消费:基线已 pop,下一次 gate 不再吃到(仍须 2 轮起)
    op2 = _FakeOp([frame, frame, frame])
    out2 = wait_stable_frame(op2, profile=_prof(), clock=_TickingClock(0.3))
    assert out2 is not None
    assert op2.shot_count >= 2, '无预置时不得一轮裸跳(仍须 2 轮起)'


def test_preset_baseline_mismatch_falls_back(monkeypatch):
    """方案 B 边界:预置基线过期(指纹已变)→ 走正常从零稳定路径。"""
    _patch_anchor_hit(monkeypatch)
    clk = _FakeClock()
    preset_stable_baseline(_gray(v=10), profile=_prof(), clock=clk)
    clk.advance(1.0)
    # 当前画面指纹 ≠ 预置 → 正常路径:set fp → 下一轮比对 → 稳定
    op = _FakeOp([_gray(v=200)] * 5)
    out = wait_stable_frame(op, profile=_prof(), clock=_TickingClock(0.3))
    assert out is not None
    assert op.shot_count >= 2, '指纹不匹配的预置不得触发一轮返帧'


# ===== ADR-0264 终裁:融合(指纹快 poll 骨架 + 用户流程知识加速器) =====

def test_node_end_accelerator_is_fast_poll_not_trust(monkeypatch):
    """终裁锁(加速器① + 不做纯信任放行):节点结束段 = 锚命中后立即
    进指纹快 poll——锚命中帧设基线,后续轮纯 CV;**不是**锚命中即返。

    序列 [miss, hit, same, same]:锚在第 2 帧命中,必须再经指纹双轮
    窗(min_stable 0.5,轮进 0.3:命中帧设基线→1 轮比对→窗达成)
    才返帧;OCR 恰 1 次(快 poll 骨架)。
    """
    calls = _patch_anchor_hit(monkeypatch, seq=[None, 'x', 'x', 'x'])
    op = _FakeOp([_gray(v=10)] * 4)
    out = wait_stable_frame(op, profile=_prof(), clock=_TickingClock(0.3))
    assert out is not None
    # OCR 恰 2 次 = 1 次前置锚 miss(battle 后画面未到)+ 1 次锚命中;
    # 命中后的确认轮零 OCR(快 poll 骨架)。
    assert calls['n'] == 2, \
        f'锚命中后确认轮不得再调 OCR,实际 OCR {calls["n"]} 次'
    assert op.shot_count >= 3, \
        f'不得锚命中即返(纯信任),须指纹窗确认,实际 {op.shot_count} 帧'


def test_op_settle_waits_then_baseline_then_fast_poll(monkeypatch):
    """终裁锁(加速器②):操作段 2s 预估等待 = 基线重置点——
    先等 2s 再取基线,随后快 poll 确认 min_stable 窗(非单校验)。"""
    from sr_od.application.currency_war import cw_observation_gate as gate
    _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray(v=50)] * 4)
    out = wait_stable_frame(op, profile=_prof(), segment='op_settle',
                            clock=_TickingClock(0.3))
    assert out is not None
    assert gate._LAST_SETTLE_WAIT == gate._OP_SETTLE_S == 2.0, \
        '操作段必须先走 2s 预估等待(基线重置点)'
    assert op.shot_count >= 2, \
        f'须基线+至少一轮指纹确认(非单帧放行),实际 {op.shot_count}'


def test_op_settle_window_still_enforced(monkeypatch):
    """终裁锁(加速器②护栏):操作段不豁免稳定窗——画面持续变化
    (特效尾帧)→ 指纹逐轮重置基线,窗永不达成 → None。

    操作段稳定窗已分级到地板 0.6s(_OP_SETTLE_MIN_STABLE_S),
    但「窗须真实测量、不得单校验放行」的语义不变:指纹每轮变化
    时即使窗再短也必超时(None 语义:调用方走兜底)。"""
    from sr_od.application.currency_war import cw_observation_gate as gate
    _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray(v=v) for v in
                  (10, 50, 90, 130, 170, 210, 30, 70, 110, 150,
                   190, 20, 60, 100, 140, 180, 40, 80, 120, 160)])
    out = wait_stable_frame(op, profile=_prof(min_stable_s=5.0),
                            segment='op_settle',
                            timeout_s=3.0,
                            clock=_TickingClock(0.3))
    assert out is None, '操作段稳定窗必须真实测量,不得单校验放行'
    assert gate._LAST_SETTLE_WAIT == 2.0


def test_op_settle_window_graded_to_floor(monkeypatch):
    """操作段稳定窗分级锁:profile 窗 0.8s 时,settle 段取地板
    0.6s——同场景下 settle 段确认轮数严格少于非 settle 段。"""
    from sr_od.application.currency_war import cw_observation_gate as gate
    assert gate._OP_SETTLE_MIN_STABLE_S == 0.6, \
        'settle 稳定窗地板必须 = 0.6s(特效帧误读红线,实机耗时报告风险声明)'
    _patch_anchor_hit(monkeypatch)
    op_s = _FakeOp([_gray(v=50)] * 8)
    out_s = wait_stable_frame(op_s, profile=_prof(min_stable_s=0.8),
                              segment='op_settle',
                              timeout_s=6.0,
                              clock=_TickingClock(0.3))
    assert out_s is not None
    op_n = _FakeOp([_gray(v=50)] * 8)
    out_n = wait_stable_frame(op_n, profile=_prof(min_stable_s=0.8),
                              timeout_s=6.0,
                              clock=_TickingClock(0.3))
    assert out_n is not None
    assert op_s.shot_count < op_n.shot_count, \
        (f'settle 段须按 0.6s 地板更早返帧(确认轮更少),'
         f'实际 settle={op_s.shot_count} 帧 vs 非 settle={op_n.shot_count} 帧')


def test_non_settle_keeps_profile_window(monkeypatch):
    """分级边界:非 settle 段(环入口/兜底门)不吃 0.6 地板——
    profile 窗抬高时确认轮随之变多(窗仍由 profile 驱动)。"""
    _patch_anchor_hit(monkeypatch)
    op_lo = _FakeOp([_gray(v=50)] * 8)
    out_lo = wait_stable_frame(op_lo, profile=_prof(min_stable_s=0.8),
                               timeout_s=6.0,
                               clock=_TickingClock(0.3))
    assert out_lo is not None
    op_hi = _FakeOp([_gray(v=50)] * 12)
    out_hi = wait_stable_frame(op_hi, profile=_prof(min_stable_s=1.7),
                               timeout_s=6.0,
                               clock=_TickingClock(0.3))
    assert out_hi is not None
    assert op_hi.shot_count > op_lo.shot_count, \
        (f'非 settle 段窗必须随 profile 变化(不吃 0.6 地板),'
         f'实际 0.8s={op_lo.shot_count} 帧 vs 1.7s={op_hi.shot_count} 帧')


def test_fast_confirm_false_restores_full_gate(monkeypatch):
    """终裁锁(回退开关④):fast_confirm=False → 每轮 poll 都做
    全图 OCR 锚判定的旧完整门(A/B 回退)。"""
    calls = _patch_anchor_hit(monkeypatch)
    prof = _prof()
    prof['fast_confirm'] = False   # profile 键同样有效
    op = _FakeOp([_gray()] * 5)
    out = wait_stable_frame(op, profile=prof, clock=_TickingClock(0.3))
    assert out is not None
    assert calls['n'] >= 2, \
        f'关 fast_confirm 时每轮 poll 必须做 OCR 锚判定,实际 {calls["n"]}'
