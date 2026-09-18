"""穿戴落地验证与 miss 刹车锁(T-55;点击≠成了穿戴侧补齐)。

病理(run_20260918_075416 停局链):备战期 WearEquip 拖拽静默未生效,
投影照写 ``owned[分身墨镜Max] -1(穿戴)``,下一帧实读该件仍在 owned 库
→ equips 失配安灯停局。根因 = WearEquipOp 发出即写零验证面。修法形态
逐位对齐 T-44 买牌落地先例:拖后对 owned 源件格做像素差判定(settle 重
采防动画时序误报),零变化 = 未生效 → 置申报闩(载体 cw4_counters)+
``env.emitted = False``——两投影腿跳写(容器 logic 腿经执行器 emitted
门,黑板腿经 ``_project_prep_obs`` 闩消费口);连续 miss 由闩消费口计数
(同键累加/异键归 1/无闩归零),触顶 WEAR_MISS_REDISPATCH_LIMIT →
round_fail 显式停交上层;缺证不可判与载体缺席 = 保守放行。

锁四件事:
1. 源件格像素差纯函数:零变化 = 未生效 / 可见变化 = 落地 / 缺证不可判
   保守放行(None);
2. WearEquipOp 落地门:miss 置闩 + emitted=False(投影跳写的置位端);
   落地/缺证照常发出;settle 重采收敛;定位落空(计划失效)不计 miss;
3. 闩消费口计数:无闩照写归零 / 命中计数 + 台账行 / 陈旧闩不吞 /
   异键归 1 / 载体缺席零动作;
4. 投影跳写与刹车:闩窗黑板保持事实;触顶 round_fail 交上层;
   单次假阳清零永不假满。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from one_dragon.base.geometry.point import Point
from one_dragon.base.geometry.rectangle import Rect
from one_dragon.base.operation.operation import (
    OperationRoundResultEnum,
)

import sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action \
    as wear_mod
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.kernel.cw_vocab import WearEquip
from sr_od.application.currency_war.operations.cw_op.cw_wear_equip_action import (
    CW4_KEY_WEAR_MISS_PENDING,
    CW4_KEY_WEAR_MISS_STREAK_KEY,
    CW4_KEY_WEAR_MISS_STREAK_N,
    WEAR_LAND_DIFF_THRESHOLD,
    WEAR_MISS_REDISPATCH_LIMIT,
    WearEquipOp,
    wear_miss_brake_status,
    wear_miss_consume,
    wear_miss_key_of,
    wear_miss_pending_set,
    wear_owned_cell_changed,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv
from sr_od.application.currency_war.telemetry import defects

_ACTION = WearEquip(item_name='分身墨镜Max', char_name='甲',
                    row='front', slot=1)
_KEY = wear_miss_key_of(_ACTION)

# 帧覆盖源件格 (1732,211)-(1804,283)(格心 (1768,247) ±36)。
_FRAME_H, _FRAME_W = 400, 2000


def _frame() -> np.ndarray:
    return np.zeros((_FRAME_H, _FRAME_W, 3), dtype=np.uint8)


def _cell_rect() -> Rect:
    return Rect(1768 - 36, 247 - 36, 1768 + 36, 247 + 36)


def _carrier_session() -> StrategySession:
    """带计数载体的局(session.strategy_state.cw4_counters = 空 dict)。"""
    session = StrategySession()
    session.strategy_state = SimpleNamespace(
        cw4_counters={}, cw4_segment_serial=0)
    return session


def _counters(session: StrategySession) -> dict:
    return session.strategy_state.cw4_counters


def _spy_defects(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """缺陷台账探针(替身缝 = defects.record_defect;行零真实落盘)。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


# ===== 锁1 源件格像素差纯函数 =====

class TestWearOwnedCellChanged:

    def test_zero_diff_means_miss(self):
        """两帧同区域零差 = 源件未离开 = 判未生效(False)。"""
        pre, post = _frame(), _frame()
        assert wear_owned_cell_changed(pre, post, _cell_rect()) is False

    def test_visible_diff_means_landed(self):
        """源件格出现可见变化(icon 消失/网格 reflow)= 判落地(True)。"""
        pre, post = _frame(), _frame()
        post[211:283, 1732:1804] = 120
        assert wear_owned_cell_changed(pre, post, _cell_rect()) is True

    def test_missing_evidence_is_unknown_not_failure(self):
        """缺帧/两帧形状不一致/矩形越界 = 不可判(None)→ 调用方按生效
        走既有行为;验证只在两帧齐备时发声,缺证不改变既有语义。"""
        pre, post = _frame(), _frame()
        assert wear_owned_cell_changed(None, post, _cell_rect()) is None
        assert wear_owned_cell_changed(pre, None, _cell_rect()) is None
        bad = np.zeros((_FRAME_H + 8, _FRAME_W, 3), dtype=np.uint8)
        assert wear_owned_cell_changed(pre, bad, _cell_rect()) is None
        assert wear_owned_cell_changed(pre, post,
                                       Rect(9999, 9999, 12000, 12000)) is None


# ===== 锁2 WearEquipOp 落地门 =====

def _make_env(monkeypatch: pytest.MonkeyPatch, screens: list[np.ndarray],
              session: object | None) -> tuple:
    """WearEquipOp 离线执行环境(零真实副作用):坐标注入绕 screen_info
    (拖点/源件格心固定),截图序列 scripted;返回 (op, env, 拖拽记录)。"""
    drags: list = []
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: drags.append(kw),
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': lambda self: screens.pop(0) if screens else None,
        'park_cursor': lambda self, **kw: None,
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    from sr_od.application.currency_war import prep_actions as pa
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    # 坐标边注入(替身缝 = 执行器实例方法;等价于 screen_info 命中形态)。
    ex._equip_slot_drag_point = lambda row, slot: Point(420, 421)
    ex._owned_grid_locate = lambda name: Point(1768, 247)
    ex._wait_stable_frame = lambda *a, **k: None
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    monkeypatch.setattr('time.sleep', lambda _s: None)
    return WearEquipOp(_ACTION), env, drags


def test_wear_miss_sets_latch_and_skips_emit(monkeypatch):
    """落地门 miss 臂:拖后源件格像素零变化(首采+settle 重采均零差)
    → 置申报闩 + emitted=False(两投影腿跳写的置位端)+ detail 申报
    未生效;判定发生在拖拽之后(先发射后验证,非前置拦截)。"""
    zeros = _frame()
    op, env, drags = _make_env(
        monkeypatch, [zeros.copy(), zeros.copy(), zeros.copy()],
        _carrier_session())

    ok = op.execute(env)

    assert ok is True, 'prep 域返回契约不变(miss 经旁路字段承载)'
    assert drags, '判定必须发生在拖拽之后'
    assert env.emitted is False, 'miss = emitted False(容器 logic 腿跳写门)'
    assert _counters(env.match.session).get(CW4_KEY_WEAR_MISS_PENDING) == _KEY
    assert '未生效' in env.detail


def test_wear_landed_emits_and_clears_stale_latch(monkeypatch):
    """落地门成功臂:源件格像素变化 → 照常发出(emitted=True)+ 不置闩;
    execute 入口清旧闩(任何路径的穿戴动作都不消费上一动作的申报)。"""
    pre, post = _frame(), _frame()
    post[211:283, 1732:1804] = 120
    session = _carrier_session()
    _counters(session)[CW4_KEY_WEAR_MISS_PENDING] = '旧件@back-2'   # 陈旧闩残留
    op, env, _drags = _make_env(monkeypatch, [pre, post], session)

    ok = op.execute(env)

    assert ok is True and env.emitted is True
    assert _counters(session).get(CW4_KEY_WEAR_MISS_PENDING) is None, \
        '入口清旧闩(单动作窗)'
    assert '已发' in env.detail


def test_wear_first_read_anim_then_settle_converges_landed(monkeypatch):
    """settle 重采臂:首采恰逢拖拽回弹动画零差 → 延迟重采一次收敛判
    落地(时序误报防线,T-44 buy 同款)。"""
    zeros, changed = _frame(), _frame()
    changed[211:283, 1732:1804] = 120
    op, env, _drags = _make_env(
        monkeypatch, [zeros.copy(), zeros.copy(), changed],
        _carrier_session())

    ok = op.execute(env)

    assert ok is True and env.emitted is True
    assert _counters(env.match.session).get(
        CW4_KEY_WEAR_MISS_PENDING) is None


def test_wear_locate_miss_is_not_counted_as_miss(monkeypatch):
    """定位落空(计划失效)= 未发射通道,不计 miss 不置闩(像素验证
    只覆盖「已发射未落地」;该路径既有语义 = 下帧重派重算)。"""
    op, env, _drags = _make_env(monkeypatch, [], _carrier_session())
    env.executor._owned_grid_locate = lambda name: None

    ok = op.execute(env)

    assert ok is True and env.emitted is False
    assert _counters(env.match.session).get(
        CW4_KEY_WEAR_MISS_PENDING) is None, '计划失效不计 miss'
    assert '未定位' in env.detail


def test_wear_miss_carrier_absent_keeps_existing_semantics(monkeypatch):
    """载体缺席(无局/第三方策略面)= 缺省口径:miss 只留痕,emitted
    保持 True(两投影腿要么同跳要么同写,半跳会造成容器/黑板分叉)。"""
    zeros = _frame()
    op, env, _drags = _make_env(
        monkeypatch, [zeros.copy(), zeros.copy(), zeros.copy()],
        StrategySession())   # strategy_state 缺省 None(无计数面)

    ok = op.execute(env)

    assert ok is True and env.emitted is True, '载体缺席 = 既有发出即写'
    assert '已发' in env.detail, '缺省口径 = 成功 detail(两投影腿同写)'


# ===== 锁3 闩消费口计数(wear_miss_consume)=====

def _miss_once(session: StrategySession, action: WearEquip) -> bool:
    """一次完整 miss 事件(置位端申报闩 + 消费口计数;成对出现)。"""
    wear_miss_pending_set(session, wear_miss_key_of(action))
    return wear_miss_consume(session, action)


def test_consume_no_mark_resets_and_projects(monkeypatch):
    """闩不在 = 消费口 False(投影照写)+ 计数归零(同键情节有了结,
    单次假阳永不假满;载体缺席同 False 零动作)。"""
    rows = _spy_defects(monkeypatch)
    session = _carrier_session()
    _miss_once(session, _ACTION)
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 1

    assert wear_miss_consume(session, _ACTION) is False   # 无闩 = 照写
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 0
    assert wear_miss_brake_status(session) is None

    bare = StrategySession()   # 载体缺席
    assert wear_miss_consume(bare, _ACTION) is False
    assert len(rows) == 1, '仅 miss 事件落台账行;无闩/缺席消费零新增'


def test_consume_hit_ticks_accumulates_and_ledgers(monkeypatch):
    """命中 = True(跳写)+ 同键累加 + wear_miss_skip 台账行逐次留证
    (防静默;豁免 ≠ 消失同纪律)。"""
    rows = _spy_defects(monkeypatch)
    session = _carrier_session()

    assert _miss_once(session, _ACTION) is True
    assert _miss_once(session, _ACTION) is True

    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 2, '同键累加'
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_KEY] == _KEY
    assert _counters(session).get(CW4_KEY_WEAR_MISS_PENDING) is None, \
        '闩读即清(单动作窗)'
    assert [(s, k) for s, k, _e, _o in rows
            if k == 'wear_miss_skip'] == [('equips', 'wear_miss_skip')] * 2


def test_consume_stale_or_new_key_restarts_at_one(monkeypatch):
    """陈旧闩不吞新动作投影(读即清 + 归零);异键 miss = 情节已换,
    新情节从 1 起算不继承旧计数。"""
    _spy_defects(monkeypatch)
    session = _carrier_session()
    _miss_once(session, _ACTION)
    _miss_once(session, _ACTION)
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 2

    # 陈旧闩:闩键与本次动作不匹配 → False + 归零(不吞投影)
    _counters(session)[CW4_KEY_WEAR_MISS_PENDING] = '旧件@back-2'
    assert wear_miss_consume(session, _ACTION) is False
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 0

    # 异键 miss:换目标件 → 从 1 起算
    act_b = WearEquip(item_name='冶金炉', char_name='乙',
                      row='back', slot=2)
    assert _miss_once(session, act_b) is True
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 1, '异键归 1'
    assert wear_miss_brake_status(session) is None


# ===== 锁4 投影跳写与刹车 =====

def _mk_stub(session: object) -> CwScreenPrep:
    """CwScreenPrep 绕道构造(无框架状态;投影纯计算面直接可调)。"""
    stub = CwScreenPrep.__new__(CwScreenPrep)
    stub._session = lambda: session
    return stub


def test_projection_keeps_blackboard_on_latch(monkeypatch):
    """闩窗跳写主锁:置位端申报闩在 → 投影写端消费后黑板保持事实
    (owned_equips 不摘件,原对象返回),闩清,台账行留证;复放一次
    闩已清后的投影 = 摘件照常(单动作窗无残留)。"""
    rows = _spy_defects(monkeypatch)
    session = _carrier_session()
    wear_miss_pending_set(session, _KEY)
    obs = PrepObservation(owned_equips=['分身墨镜Max', '拆装扳手'])

    out = CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)

    assert out is obs, '黑板保持事实(不摘件)'
    assert out.owned_equips == ['分身墨镜Max', '拆装扳手']
    assert _counters(session).get(CW4_KEY_WEAR_MISS_PENDING) is None, '闩清'
    assert any(k == 'wear_miss_skip' for _s, k, _e, _o in rows)

    out2 = CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)
    assert out2 is not obs and '分身墨镜Max' not in (out2.owned_equips or []), \
        '闩清后摘件照常(无残留影响)'


def test_projection_unchanged_without_latch(monkeypatch):
    """无变化回归锁:闩不在(正常穿戴)→ owned_equips 摘件逐位不变;
    陈旧闩(键不匹配)不吞投影(照常摘件 + 闩读即清)。"""
    _spy_defects(monkeypatch)
    session = _carrier_session()
    obs = PrepObservation(owned_equips=['分身墨镜Max', '拆装扳手'])

    out = CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)

    assert out is not obs, '黑板推进照旧(摘件)'
    assert out.owned_equips == ['拆装扳手']

    session2 = _carrier_session()
    _counters(session2)[CW4_KEY_WEAR_MISS_PENDING] = '旧件@back-2'
    obs2 = PrepObservation(owned_equips=['分身墨镜Max'])
    out2 = CwScreenPrep._project_prep_obs(_mk_stub(session2), _ACTION, obs2)
    assert '分身墨镜Max' not in out2.owned_equips, \
        '陈旧闩不吞新动作投影(摘件照常)'
    assert _counters(session2).get(CW4_KEY_WEAR_MISS_PENDING) is None, \
        '陈旧闩读即清'


def test_brake_status_pure_read_semantics():
    """触顶判定纯读形态:同键累加触顶出文案;无闩消费归零后 None
    (文案单一源,对齐 deploy/buy 刹车形态)。"""
    session = _carrier_session()
    assert wear_miss_brake_status(session) is None
    for i in range(1, WEAR_MISS_REDISPATCH_LIMIT):
        _miss_once(session, _ACTION)
        assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == i
        assert wear_miss_brake_status(session) is None, \
            f'第 {i} 次 miss 未达限不触顶'
    _miss_once(session, _ACTION)
    status = wear_miss_brake_status(session)
    assert status is not None and '超上限' in status, '触顶给出可判读状态'

    # 落地成功(闩不在消费)归零 → 永不假满
    assert wear_miss_consume(session, _ACTION) is False
    assert _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] == 0
    assert wear_miss_brake_status(session) is None


def test_brake_round_fails_at_limit():
    """决策循环刹车接线锁:触顶 → ``_wear_miss_brake_round`` 返回 FAIL
    轮(status 携「超上限」交上层);未触顶 / 非 WearEquip = None 零
    动作(零行为回归面)。"""
    session = _carrier_session()
    stub = _mk_stub(session)
    _counters(session)[CW4_KEY_WEAR_MISS_STREAK_KEY] = _KEY
    _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] = WEAR_MISS_REDISPATCH_LIMIT

    res = CwScreenPrep._wear_miss_brake_round(stub, session, _ACTION)

    assert res is not None and res.result == OperationRoundResultEnum.FAIL, \
        '触顶 = round_fail 交上层'
    assert '超上限' in (res.status or '')

    _counters(session)[CW4_KEY_WEAR_MISS_STREAK_N] = \
        WEAR_MISS_REDISPATCH_LIMIT - 1
    assert CwScreenPrep._wear_miss_brake_round(
        stub, session, _ACTION) is None, '限内零动作'
    from sr_od.application.currency_war.kernel.cw_vocab import SellBench
    assert CwScreenPrep._wear_miss_brake_round(
        stub, session, SellBench(bench_idx=0)) is None, '非 WearEquip 零动作'


def test_counter_carrier_absent_is_noop():
    """载体缺席(第三方策略面)= 无计数面零动作(缺省口径;帧帽/访问
    上限仍兜底,不会无界)。"""
    session = StrategySession()   # strategy_state 缺省 None
    assert wear_miss_brake_status(session) is None
    wear_miss_pending_set(session, _KEY)   # 零动作不炸
    assert wear_miss_consume(session, _ACTION) is False
