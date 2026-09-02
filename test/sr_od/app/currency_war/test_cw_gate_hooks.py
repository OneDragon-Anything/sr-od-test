# -*- coding: utf-8 -*-
"""test_cw_gate_hooks 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- gate_fast_confirm: test_cw_gate_fast_confirm.py
- gate_flags: test_cw_gate_flags.py
- gate_post_collapse: test_cw_gate_post_collapse.py
- w379_gate_v2_wire: test_cw_w379_gate_v2_wire.py
- r330_hook_gates: test_cw_r330_hook_gates.py
- survey19_hooks: test_cw_survey19_hooks.py
- gate_fixtures: test_cw_gate_fixtures.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== gate_fast_confirm ====================

import numpy as np
import pytest

from sr_od.application.currency_war.obs.cw_observation_gate import  _PRESET_BASELINE, preset_stable_baseline, wait_stable_frame


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
    """终裁锁(加速器②):操作段预估等待 = 基线重置点——
    先等再取基线,随后快 poll 确认 min_stable 窗(非单校验)。
    等待值核减锁:1.2s(w781 自 1.5 核减:买牌特效实测 0.5-1s
    上限+0.2s 余量;低估由指纹重置机制兜底,见 gate._OP_SETTLE_S 注)。"""
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
    _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray(v=50)] * 4)
    out = wait_stable_frame(op, profile=_prof(), segment='op_settle',
                            clock=_TickingClock(0.3))
    assert out is not None
    assert gate._LAST_SETTLE_WAIT == gate._OP_SETTLE_S == 1.0, \
        '操作段必须先走 1.0s 预估等待(基线重置点;2026-09-02 用户口述口径 #15 收起动画 ~1s 自 1.2 核减)'
    assert op.shot_count >= 2, \
        f'须基线+至少一轮指纹确认(非单帧放行),实际 {op.shot_count}'


def test_op_settle_window_still_enforced(monkeypatch):
    """终裁锁(加速器②护栏):操作段不豁免稳定窗——画面持续变化
    (特效尾帧)→ 指纹逐轮重置基线,窗永不达成 → None。

    操作段稳定窗已分级到地板 0.6s(_OP_SETTLE_MIN_STABLE_S),
    但「窗须真实测量、不得单校验放行」的语义不变:指纹每轮变化
    时即使窗再短也必超时(None 语义:调用方走兜底)。"""
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
    _patch_anchor_hit(monkeypatch)
    op = _FakeOp([_gray(v=v) for v in
                  (10, 50, 90, 130, 170, 210, 30, 70, 110, 150,
                   190, 20, 60, 100, 140, 180, 40, 80, 120, 160)])
    out = wait_stable_frame(op, profile=_prof(min_stable_s=5.0),
                            segment='op_settle',
                            timeout_s=3.0,
                            clock=_TickingClock(0.3))
    assert out is None, '操作段稳定窗必须真实测量,不得单校验放行'
    assert gate._LAST_SETTLE_WAIT == 1.0


def test_op_settle_window_graded_to_floor(monkeypatch):
    """操作段稳定窗分级锁:profile 窗 0.8s 时,settle 段取地板
    0.6s——同场景下 settle 段确认轮数严格少于非 settle 段。"""
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
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


def test_profile_stable_window_uniform_floor():
    """三 profile 稳定窗统一下限锁:关态/开态与弹窗态/settle 段
    同取 0.6s——稳定的真守门是指纹变化重置机制,0.6s 首尾一致窗
    已拒绝动画中间帧;单局 gate stable 调用 30-84 次,0.8s 档每处
    白付 0.2s(耗时审计报告 .debug/temp/currency_war/
    w417_duration_audit/REPORT.md「需验证」表)。"""
    from sr_od.application.currency_war.obs.cw_observation_gate import  PROFILE_CLOSED, PROFILE_OPEN, PROFILE_POPUP
    for name, prof in (('closed', PROFILE_CLOSED), ('open', PROFILE_OPEN),
                       ('popup', PROFILE_POPUP)):
        assert prof['min_stable_s'] == 0.6, \
            f'{name} profile 稳定窗必须 = 0.6s 统一下限'


# ==================== gate_flags ====================

from sr_od.application.currency_war.currency_war_config import  CurrencyWarConfig


def test_gate_flags_removed() -> None:
    """r347:gate_* flag 不得回流——对拍已完成,gate 是唯一路径;
    flag 回流 = 死代码复活(双路径维护+组合爆炸)。"""
    src_attrs = [a for a in vars(CurrencyWarConfig) if a.startswith('gate_')]
    assert not src_attrs, f'gate flag 已删不得回流: {src_attrs}'
    import inspect
    init_src = inspect.getsource(CurrencyWarConfig.__init__)
    assert 'self.gate_' not in init_src, '__init__ 不得再读 gate flag'
    save_src = inspect.getsource(CurrencyWarConfig.save)
    assert "'gate_" not in save_src, 'save 白名单不得再写 gate flag 键'


# ==================== gate_post_collapse ====================

import inspect
from types import SimpleNamespace

import sr_od.application.currency_war.obs.cw_observation_gate as gate_mod
import sr_od.application.currency_war.prep_director as pd_mod
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_prep_actions import StartBattle


from sr_od.application.currency_war.prep_director import PrepDirector

_FRAME = object()   # gate 稳定帧哨兵(身份断言用)


def test_post_collapse_timeout_param_lock() -> None:
    """收紧超时常量存在且界内:≥1s(不低于单轮 poll + min_stable_s
    成本)、<12s(必须真省掉死等;实测收起后 ~2.0-2.2s stable,
    4.0s≈2 倍余量)。"""
    v = gate_mod.GATE_POST_COLLAPSE_TIMEOUT_S
    assert isinstance(v, float)
    assert 1.0 <= v < 12.0, f'收紧超时须在 [1, 12) 内,实得 {v}'
    src = inspect.getsource(gate_mod)
    assert 'REPORT.md' in src, '常量注释必须带持久出处(耗时深挖报告路径)'


def _make_director(monkeypatch, gate_calls: list, gate_returns: list,
                   collapse_open):
    """构造绕过 __init__ 的 PrepDirector,mock gate 与开店态探测。

    gate_calls 记录每次 wait_stable_frame 的 (timeout_s, expect_screen);
    gate_returns 按序弹出返回值。collapse_open 控制 _try_collapse_open_shop
    返回值(标量=恒值;列表=按序弹出,记录实际返回到返回的 list)。
    """
    d = PrepDirector.__new__(PrepDirector)
    d.ctx = SimpleNamespace(current_instance_idx=99)
    d._executor = SimpleNamespace(
        validate=lambda a: None,
        execute=lambda a: (True, 'ok'))
    d._steps = 0
    d._stall = 0
    d._fail_counts = {}
    d._blocked = set()
    d._recovered = set()
    d._recovery_closed_known = {}
    d._recovery_tried = False
    d._bench_pts = []
    d._cached_state = None
    d._cached_bench = []
    d._cached_deployed = []
    d._cached_vacancy = 0
    d._cached_gold_trusted = False

    def _fake_gate(op, *, profile, timeout_s=None, **kw):
        gate_calls.append((timeout_s, profile['expect_screen']))
        ret = gate_returns.pop(0) if gate_returns else None
        return ret

    monkeypatch.setattr(gate_mod, 'wait_stable_frame', _fake_gate)

    # 预收重试窗的 sleep 打桩(离线单测不付真实等待;记录间隔供断言)
    sleeps: list[float] = []
    monkeypatch.setattr(pd_mod.time, 'sleep', lambda s: sleeps.append(s))

    collapse_calls: list[bool] = []
    _collapse_seq = list(collapse_open) if isinstance(collapse_open, list) \
        else None

    def _fake_collapse():
        v = _collapse_seq.pop(0) if _collapse_seq is not None else collapse_open
        collapse_calls.append(v)
        return v

    monkeypatch.setattr(d, '_try_collapse_open_shop', _fake_collapse)

    def _observe(heavy, screen=None):
        from sr_od.application.currency_war.kernel.cw_prep_actions import PrepObservation
        obs = PrepObservation()
        obs.state = GameState(plane=1, round_num=1)
        return obs

    monkeypatch.setattr(d, '_observe', _observe)
    monkeypatch.setattr(d, '_record_step', lambda o, a: None)
    import sr_od.application.currency_war.currency_war_config as cfg_mod
    monkeypatch.setattr(cfg_mod, 'CurrencyWarConfig', lambda idx: SimpleNamespace())
    match = SimpleNamespace(
        strategy=SimpleNamespace(
            decide_prep_action=lambda obs, session, config: StartBattle(),
            update_target=lambda state, session, config: None),
        session=SimpleNamespace(defer_count=0, prep_phase=0,
                                prep_phase_retry=0, bail_reason_counts={}))
    return d, match, collapse_calls, sleeps


def test_open_shop_entrance_uses_tightened_gate(monkeypatch) -> None:
    """战后开店态入口:收起后 gate 用收紧超时(≠12s 默认)且一次
    达成 → 直接进本轮决策,不再打满 12s、不再 round_retry 重进。"""
    calls: list = []
    d, match, collapse_calls, _sleeps = _make_director(
        monkeypatch, calls, [_FRAME], collapse_open=True)
    result = d._run_loop(match)
    assert collapse_calls == [True]
    assert calls == [(gate_mod.GATE_POST_COLLAPSE_TIMEOUT_S, '货币战争-备战')], \
        f'开店态入口应只调一次收紧超时 gate,实得 {calls}'
    assert calls[0][0] < 12.0, '收紧超时必须小于默认 12s(否则死等未消除)'
    assert '出战' in (result.status or ''), \
        f'应直接进决策环并出战,实得 {result.status}'


def test_closed_shop_entrance_keeps_default_gate(monkeypatch) -> None:
    """关店态入口(新位面首环/无自动开商店):预收探针含重试窗全部
    miss → 走原 12s 完整门,行为不变——不改超时。"""
    calls: list = []
    d, match, collapse_calls, sleeps = _make_director(
        monkeypatch, calls, [_FRAME], collapse_open=False)
    result = d._run_loop(match)
    # 重试窗:首探 + PRECOLLAPSE_RETRIES 次重试,全 miss;每次重试前
    # sleep 一个间隔(有界,不无界等)
    assert collapse_calls == [False] * (1 + pd_mod.PRECOLLAPSE_RETRIES)
    # 重试窗 sleep 断言取前缀:sleep 桩记录的是全局 time.sleep,
    # 环后段(round_wait 等)另有无关等待,不属本锁
    assert sleeps[:pd_mod.PRECOLLAPSE_RETRIES] == \
        [pd_mod.PRECOLLAPSE_RETRY_S] * pd_mod.PRECOLLAPSE_RETRIES
    assert calls == [(None, '货币战争-备战')], \
        f'关店态入口应走默认超时 gate,实得 {calls}'
    assert '出战' in (result.status or '')


def test_tightened_timeout_falls_back_to_full_gate(monkeypatch) -> None:
    """收紧超时未达成 stable(收起动画偶发拖长)→ 落回原 12s 完整门
    兜底(有界,timeout=None=profile 默认);完整门也超时才进容忍
    探测分支(bail 语义保留)。"""
    calls: list = []
    d, match, collapse_calls, _sleeps = _make_director(
        monkeypatch, calls, [None, None], collapse_open=[True, False])
    result = d._run_loop(match)
    assert len(calls) == 2, f'收紧超时后应恰好落回一次完整门,实得 {calls}'
    assert calls[0][0] == gate_mod.GATE_POST_COLLAPSE_TIMEOUT_S
    assert calls[1][0] is None, '兜底门必须用 profile 默认超时(原 12s 语义)'
    # 容忍分支:收起已做过(店已关,第二次探测 False)→ bail 而非 round_retry
    assert '环入口帧不clean' in (result.status or ''), \
        f'完整门仍超时应走原 bail 路径,实得 {result.status}'
    assert collapse_calls == [True, False]


def test_precollapse_retry_hits_open_state_mid_window(monkeypatch) -> None:
    """时序竞争修复锁(单帧语义):首探 miss(商店尚未自动开)→
    重试窗内第 2 次探到开态 → 立即走「收起→收紧超时 gate」路径,
    不进 12s 完整门、不 round_retry 重进。"""
    calls: list = []
    d, match, collapse_calls, sleeps = _make_director(
        monkeypatch, calls, [_FRAME], collapse_open=[False, True])
    result = d._run_loop(match)
    assert collapse_calls == [False, True], \
        f'应首探 miss 后重试一次即命中,实得 {collapse_calls}'
    assert sleeps[:1] == [pd_mod.PRECOLLAPSE_RETRY_S], '重试前应等待一个间隔'
    assert calls == [(gate_mod.GATE_POST_COLLAPSE_TIMEOUT_S, '货币战争-备战')], \
        f'命中开态应只走一次收紧超时 gate,实得 {calls}'
    assert '出战' in (result.status or ''), '应直接进本轮决策,不重进'


def test_precollapse_retry_window_bounds(monkeypatch) -> None:
    """重试窗参数锁:次数 ≥1(窗必须存在)且有上限(≤5,防从不自动
    开店的轮次无界多付探针成本);间隔 ∈ (0, 2](实测开商店在入口后
    数秒内,窗过宽只对晚开店轮次有意义,白付成本)。"""
    assert isinstance(pd_mod.PRECOLLAPSE_RETRIES, int)
    assert 1 <= pd_mod.PRECOLLAPSE_RETRIES <= 5, \
        f'重试次数须在 [1,5] 内,实得 {pd_mod.PRECOLLAPSE_RETRIES}'
    assert 0.0 < pd_mod.PRECOLLAPSE_RETRY_S <= 2.0, \
        f'重试间隔须在 (0,2] 内,实得 {pd_mod.PRECOLLAPSE_RETRY_S}'


# ==================== (w379_gate_v2_wire 已随 C4 开关族删除) ====================
# (C4 换线存活门接线锁段(G1-G5)已随 line_switch_survival_gate_enabled
#  开关族删除——旧方案清退批,清查报告 OLD_MIX_AUDIT §1.3;
#  cw_intention._switch_gate_open 接线、cw_line_switch.survival_gate 族
#  与 v3_line_gate_* 决策位/闩同批删。)
# ==================== r330_hook_gates ====================

import inspect as _r330_hook_gates_inspect


def test_is_prep_like_frame_exists() -> None:
    """共享帧态判据在 cw_obs_core(id_mark 精准判定)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    assert hasattr(cw_obs_core, 'is_prep_like_frame')
    src = _r330_hook_gates_inspect.getsource(cw_obs_core.is_prep_like_frame)
    assert 'get_match_screen_name' in src   # 框架 id_mark 体系


def test_layout_hook_gated() -> None:
    """back_layout 停机钩子过帧态门(过渡帧跳过)。件③(W209/ADR-0385)重构:
    触发判据从「level 对应档无档」改到双通道对账原始格数 n_raw 无档(=7,
    钻石+1 局);帧态门(is_prep_like_frame)语义不变。"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    src = _r330_hook_gates_inspect.getsource(cw_identity_obs.read_deployed_chars)
    assert 'is_prep_like_frame' in src
    assert "n_raw" in src, '触发判据应消费 resolve_back_slots 的 n_raw(双通道)'


def test_bookcard_stop_hook_removed() -> None:
    """bookcard 确认停机钩子退役(2026-08-30 开启语义确认,自动处理链接管):
    read_bench_chars 不再有停机逻辑;处理链接线在 battle_loop + handlers。
    (原锁 r133→r330「钩子过帧态门」钉的是停机语义,钩子删除后语义换新。)"""
    from sr_od.application.currency_war.obs import cw_identity_obs
    src = _r330_hook_gates_inspect.getsource(cw_identity_obs.read_bench_chars)
    assert 'bookcard_confirm' not in src   # 停机钩子段已删
    assert 'find_bookcards' in src   # 书册卡仍入 _obj_slots( summon 钩子不拦)
    assert src.count('is_prep_like_frame') >= 1   # summon 钩子帧态门仍在
    from sr_od.application.currency_war.operations import battle_loop
    loop_src = _r330_hook_gates_inspect.getsource(battle_loop)
    assert 'HandleBookcard' in loop_src   # 处理链接线(0k 分支 + 预清场)


def test_star_hook_gated() -> None:
    """star 回退留证钩子过帧态门(动画帧不留证)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    src = _r330_hook_gates_inspect.getsource(cw_reconcile._star_stop_hook)
    assert 'is_prep_like_frame' in src


# ==================== survey19_hooks ====================

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_survey19_hooks import (  # noqa: E402
    encounter_tier_score,
    supply_reroll_decision,
    wear_discipline_alert,
)


def test_p9_encounter_tier_context_dependent() -> None:
    """遭遇档评分场合依赖:同 −4,边际局高分/大胜局≈0;P1 放大。"""
    edge = encounter_tier_score(100, -4, gap=0, plane=2)
    blow = encounter_tier_score(100, -4, gap=-80, plane=2)
    p1 = encounter_tier_score(100, -4, gap=0, plane=1)
    assert edge > blow
    assert p1 > edge   # P1 尖峰 ×1.5


def test_p1_wear_discipline() -> None:
    """狼狩穿戴纪律:可穿而未穿 = 报警;无空槽的真积压才算;非狼狩无 XP 项。"""
    # 3 件闲 + 2 空槽 → overflow 1 → 报警(狼狩:每战 −1 XP)
    r = wear_discipline_alert(['a', 'b', 'c'], total_slots=10, worn_count=8,
                              faction_hunt_active=True)
    assert r['alert'] and r['unwearable_overflow'] == 1
    assert r['hunt_xp_loss_per_battle'] == 1
    # 全穿满 → 无报警(装备可循环,合成交换不算积压)
    ok = wear_discipline_alert([], total_slots=10, worn_count=10,
                               faction_hunt_active=True)
    assert not ok['alert'] and ok['hunt_xp_loss_per_battle'] == 0
    # 非狼狩:仅战力视角
    no_hunt = wear_discipline_alert(['a', 'b', 'c'], 10, 8, faction_hunt_active=False)
    assert no_hunt['alert'] and no_hunt['hunt_xp_loss_per_battle'] == 0


def test_p8_supply_reroll() -> None:
    """补给重刷:出钻直选/未出可刷→刷/刷过仍无→按价值选。"""
    assert supply_reroll_decision(True, False) == 'pick_diamond'
    assert supply_reroll_decision(True, True) == 'pick_diamond'
    assert supply_reroll_decision(False, False) == 'reroll'
    assert supply_reroll_decision(False, True) == 'pick_best'


# ==================== gate_fixtures ====================

import pytest as _gate_fixtures_pytest

from sr_od.application.currency_war.obs.cw_observation_gate import  PROFILE_CLOSED, PROFILE_OPEN, wait_stable_frame as _gate_fixtures_wait_stable_frame


class _FixtureOp:
    """把 fixture 截图喂给 gate 的桩 op(r324 后 gate 走
    screen_utils.get_match_screen_name——真 ctx 建档判定,
    fixture 场景恰好完美匹配,无需 mock 锚)。"""

    def __init__(self, ctx, frame):
        self.ctx = ctx
        self._frame = frame
        self.park_calls = 0

    def park_cursor(self, **kw):
        self.park_calls += 1

    def screenshot(self):
        return self._frame


def _gate(op, profile, **kw):
    """跑 gate(短超时,离线单帧喂两次靠 stable 窗推进)。"""
    class _Clk:
        def __init__(self):
            self.t = 0.0

        def __call__(self):
            self.t += 0.5   # 每 poll 推进 0.5s(>profile 稳定窗 0.6s 两轮过)
            return self.t
    return _gate_fixtures_wait_stable_frame(op, profile=profile, clock=_Clk(), **kw)


def test_gate_closed_passes_on_reward_panel_frame(test_context) -> None:
    """局35 形态:1-1 奖励面板帧(备战+奖励展开)关态 gate 放行。

    fixture「货币战争-备战/补给节点.webp」=备战屏带节点面板
    展开形态(节点行被遮)——圆数门误杀的现场形态。
    """
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        _gate_fixtures_pytest.skip('fixture 缺:货币战争-备战/补给节点.webp')
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=8)
    assert out is not None, '奖励面板帧应放行(局35 误杀形态回归锁)'


def test_gate_fingerprint_same_source_stable(test_context) -> None:
    """同源图连续指纹必稳(阈值比较,截屏噪声容差;r324 基元
    在 cv2_utils)。"""
    if not test_context.has_screen('货币战争-备战', '补给节点'):
        _gate_fixtures_pytest.skip('fixture 缺')
    from one_dragon.base.geometry.rectangle import Rect
    from one_dragon.utils import cv2_utils
    frame = test_context.load_screen('货币战争-备战', '补给节点')
    r = (Rect(1408, 23, 1498, 103), Rect(60, 895, 320, 975))
    a = cv2_utils.fingerprint_in_rects(frame, r)
    b = cv2_utils.fingerprint_in_rects(frame, r)   # 同一图再读=完全一致
    assert cv2_utils.fingerprint_same(a, b), '同源图指纹必须一致(阈值语义)'


def test_gate_closed_rejects_shop_open_frame(test_context) -> None:
    """开商店帧:关态 profile 拒绝(absence 锚「按钮-收起」可见)。"""
    if not test_context.has_screen('货币战争-备战-开商店', 'shop_open'):
        _gate_fixtures_pytest.skip('fixture 缺:货币战争-备战-开商店/shop_open.webp')
    frame = test_context.load_screen('货币战争-备战-开商店', 'shop_open')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=4)
    assert out is None, '开商店帧关态 gate 必须拒绝(absence 锚)'


def test_gate_open_profile_passes_shop_open(test_context) -> None:
    """开态 profile 在商店开帧放行(锚=按钮-收起 presence)。"""
    if not test_context.has_screen('货币战争-备战-开商店', 'shop_open'):
        _gate_fixtures_pytest.skip('fixture 缺')
    frame = test_context.load_screen('货币战争-备战-开商店', 'shop_open')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_OPEN, timeout_s=8)
    assert out is not None, '商店开帧开态 gate 应放行'


def test_gate_closed_passes_on_r1_stop_frame(test_context) -> None:
    """r344 实机回归锁(局37 停机现场帧):gate 超时预算按全图
    OCR poll 成本(~5s/轮)调 12s 后,真机 r1 备战帧上关态 gate
    必须放行(屏判定 crop_first=False 全图 OCR,局37 diag
    screen:0 实证 4 个 id_mark 区全中,缺的只是预算)。防
    预算/口径回退让 ping-pong 停机复发。
    fixture=局37 bail_pingpong 停机保全帧(hp=80/r1/gold=3)。"""
    if not test_context.has_screen('货币战争-备战', 'r1_idle_stop'):
        _gate_fixtures_pytest.skip('fixture 缺:货币战争-备战/r1_idle_stop.webp')
    frame = test_context.load_screen('货币战争-备战', 'r1_idle_stop')
    op = _FixtureOp(test_context, frame)
    out = _gate(op, PROFILE_CLOSED, timeout_s=8)
    assert out is not None, '局37 停机现场帧关态 gate 必须放行(r344 锁)'
