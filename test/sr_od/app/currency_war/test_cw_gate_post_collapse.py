"""战后环入口开店态预收锁(实机单局耗时深挖报告
.debug/temp/currency_war/w358_time_depth/REPORT.md 可压缩清单 #1 落地;
时序竞争修复见 .debug/temp/currency_war/w417_duration_audit/REPORT.md)。

背景:战斗胜利后新回合游戏常自动开商店,环入口原直接等关店态锚
(PROFILE_CLOSED)永不命中 → 每轮打满 12s 超时才走「收起重进」
(实机每局 ~16 轮 × ~12s 纯等)。修复语义:入口先探开商店态,
开 → 收起 → 以收紧超时(GATE_POST_COLLAPSE_TIMEOUT_S)等关店态
stable 直接进本轮;未开走原 12s 完整门;收紧超时未达成 → 落回
原 12s 完整门兜底(有界)。时序竞争修复:自动开商店可能晚于首探,
首探 miss 后在有限窗内按 PRECOLLAPSE_RETRY_S 间隔重试同一探针,
任一次探到开 → 走收紧超时路径(免 12s 死等+重进往返)。
"""
from __future__ import annotations

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
