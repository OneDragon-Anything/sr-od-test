"""部署拖拽未落地·投影跳写回归锁(2026-09-18 reconcile 事故未投影族③
修法 = T-22;病理实证 = run 20260918 02:40:20,椒丘同路径生效、艾丝妲
静默未落场,证据 = .debug/temp/incidents/20260918-reconcile/report.md
§6 与 clean_match_gs_defect_rows.jsonl,语义对帧禁引 .debug 路径)。

病理:备战期 DeployMove 拖拽静默未生效(拖拽输入被游戏吞),投影契约
「发出即写」照写 bench 摘槽 + front_row 落位 + board 羁绊增量 → 逻辑态
失真;战斗窗内游戏侧对该单位零转移(下一备战帧 heavy 实读:单位仍在
备战席原槽、不在场)→ 三行失配连发 → 安灯当推算 bug 停机。拖拽静默丢
是执行环境噪声非推算 bug:修法 = 执行器拖后目标槽像素验证,零变化置
``exec_books.deploy_miss_pending`` 申报闩(置位端 = DeployMoveOp),
投影写端按动作匹配消费后跳写(容器零写 + 黑板保持事实,消费口 =
``consume_deploy_miss_mark`` 单一源),重试 = 决策循环自然重派。

锁依据 = ExecBooks.deploy_miss_pending 字段注释(单动作窗/清除点/
安灯零改动)+ consume_deploy_miss_mark docstring(命中/陈旧闩两形态)+
DeployMoveOp.execute 拖后验证置位端语义。改锁先重推语义:本锁钉的是
「闩窗跳写、无闩照写、陈旧闩不吞、闩不做失配吸收」四向,禁为保绿
机械跟绿。
"""
from __future__ import annotations

import numpy as np

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel import cw_mismatch_policy as _policy
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    DeployMissMark,
    bench_slots_of,
    bench_view_of_slots,
    consume_defect_sink,
    consume_deploy_miss_mark,
    deployed_slots_of,
    game_state_of,
    register_sig_actors,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_vocab import DeployMove
from sr_od.application.currency_war.operations.cw_op.cw_deploy_move_action import (
    DEPLOY_LAND_DIFF_THRESHOLD,
    DeployMoveOp,
    _region_changed_px,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)
from sr_od.application.currency_war.prep_actions import PrepExecEnv

register_sig_actors('TestDeployMissWriter')

_SIG = ChannelSig(family='logic_action', actor='TestDeployMissWriter')
_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep',
                      screen='货币战争-备战')

_ACTION = DeployMove(bench_idx=1, to_row='front', faction='')


def _mk_gs_with_bench_unit() -> tuple[object, object]:
    """run C 形态播种:备战席槽2 一个单位 + 空场(返回 session, gs)。

    播种走 write_logic(source=logic):失配锁依赖「逻辑来源被实读证伪」
    的比对前提(observe 来源不触发失配分流)。"""
    session = _FakeSession()
    gs = game_state_of(session)
    slots = [None] * 9
    slots[1] = BenchChar(slot=2, char_id='甲', star=1)
    gs.write_logic(gs.bench, bench_view_of_slots(slots),
                   produced_by='TestDeployMissWriter', sig=_SIG)
    return session, gs


class _FakeSession:
    """局身份桩(game_state_of 裸对象挂载形态;每实例独立容器)。"""


def _mk_stub(session: object) -> CwScreenPrep:
    """CwScreenPrep 绕道构造(无框架状态;投影纯计算面直接可调)。"""
    stub = CwScreenPrep.__new__(CwScreenPrep)
    stub._session = lambda: session
    return stub


def _mk_obs() -> PrepObservation:
    """黑板帧:槽2 单位(与容器播种同源)。"""
    return PrepObservation(
        bench_chars=[BenchChar(slot=2, char_id='甲', star=1)],
        deployed_chars=[], owned_equips=[], free_bench_slots=8,
        front_occupied=set(), back_occupied=set())


# ============================================================ 主锁:闩窗跳写


def test_deploy_miss_mark_skips_projection_and_keeps_blackboard(monkeypatch):
    """run C 迷你重放:拖拽静默未生效(置位端申报闩在)→ 投影写端按动作
    匹配消费后跳写——容器 bench/front_row/board 全零写(逻辑态保持事实),
    黑板原样返回(不摘槽不落位),闩清,deploy_miss_skip 台账行留证,
    安灯零触发。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    session, gs = _mk_gs_with_bench_unit()
    gs.exec_books.deploy_miss_pending = DeployMissMark(
        bench_idx=1, to_row='front', char_id='甲')
    obs = _mk_obs()

    out = CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)

    assert out is obs, '黑板保持事实(原对象返回,不摘槽不落位)'
    assert bench_slots_of(gs)[1] is not None \
        and bench_slots_of(gs)[1].char_id == '甲', '容器 bench 零写(单位仍在槽2)'
    assert deployed_slots_of(gs)[0] is None, '容器 front_row 零写(未落位)'
    assert gs.board.value is None or gs.board.value == {}, '容器 board 零写'
    assert gs.exec_books.deploy_miss_pending is None, '闩读即清(单动作窗)'
    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        # 复放一次闩已清后的投影 = 无残留影响(闩窗语义单动作)
        CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)
    finally:
        set_defect_sink(None)
        consume_defect_sink()
    assert fired == [], '跳写路径安灯零触发(执行噪声不进安灯辖域)'


def test_deploy_miss_skip_leaves_ledger_row(monkeypatch):
    """跳写可审计:闩命中落 deploy_miss_skip 台账行(无告警无停机,
    豁免 ≠ 消失同纪律),行携动作坐标与单位身份。"""
    monkeypatch.setattr(_policy, '_ANDON_HOOK', lambda r: None)
    session, gs = _mk_gs_with_bench_unit()
    gs.exec_books.deploy_miss_pending = DeployMissMark(
        bench_idx=1, to_row='front', char_id='甲')

    captured: list[dict] = []
    set_defect_sink(captured.append)
    try:
        hit = consume_deploy_miss_mark(
            gs, _ACTION,
            sig=ChannelSig(family='logic_action',
                           actor='TestDeployMissWriter'))
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert hit is True, '动作匹配 = 消费命中'
    assert len(captured) == 1 and captured[0]['kind'] == 'deploy_miss_skip'
    assert captured[0]['field'] == 'deploy'
    assert 'bench_idx=1' in captured[0]['expected']


# ============================================================ 回归锁:无闩照写


def test_no_mark_projection_unchanged(monkeypatch):
    """无变化回归锁:闩不在(正常部署)→ 投影照写逐位不变(bench 摘槽 +
    front_row 落位;甲无羁绊标签 → board 零增量合法跳写),闩窗不存在时
    行为零变化。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    session, gs = _mk_gs_with_bench_unit()
    assert gs.exec_books.deploy_miss_pending is None
    obs = _mk_obs()

    out = CwScreenPrep._project_prep_obs(_mk_stub(session), _ACTION, obs)

    assert out is not obs, '黑板推进照旧(摘槽 + 落位)'
    assert bench_slots_of(gs)[1] is None, '容器 bench 摘槽照写'
    dep = deployed_slots_of(gs)
    assert dep[0] is not None and dep[0].char_id == '甲', 'front_row 落位照写'
    assert gs.bench.evidence == 'proj_deploy_src_clear', \
        'bench 写端 = 部署摘槽投影(证据位)'
    assert gs.exec_books.deploy_miss_pending is None
    assert fired == []


# ============================================================ 陈旧闩不吞


def test_stale_mark_does_not_swallow_new_action():
    """陈旧闩防吞:闩坐标与本次动作不匹配 → 投影照写(不跳),闩读即清
    (任何路径的部署动作都不消费上一动作的申报)。"""
    session, gs = _mk_gs_with_bench_unit()
    gs.exec_books.deploy_miss_pending = DeployMissMark(
        bench_idx=5, to_row='back', char_id='乙')

    hit = consume_deploy_miss_mark(gs, _ACTION, sig=_SIG)

    assert hit is False, '动作不匹配 = 不跳写'
    assert gs.exec_books.deploy_miss_pending is None, '读即清(不残留)'
    assert bench_slots_of(gs)[1] is not None, '容器未被陈旧闩污染'


def test_latch_absent_consume_returns_false():
    """闩不在 = 消费口返回 False(投影照写),容器零扰动。"""
    session, gs = _mk_gs_with_bench_unit()
    assert consume_deploy_miss_mark(gs, _ACTION, sig=_SIG) is False


# ============================================================ 安灯语义零改动


def test_mark_is_not_a_mismatch_absorption(monkeypatch):
    """申报闩只阻投影写入、不做 observe 失配吸收:闩在时 units 失配照真
    失配(observe_vs_logic_mismatch + 安灯触发)——未被申报覆盖的变更
    不被吞,安灯停机语义零改动。"""
    fired: list[dict] = []
    monkeypatch.setattr(_policy, '_ANDON_HOOK', fired.append)
    session, gs = _mk_gs_with_bench_unit()
    gs.exec_books.deploy_miss_pending = DeployMissMark(
        bench_idx=1, to_row='front', char_id='甲')
    # 实读 = 少了该单位(与逻辑不符的任意形状)
    slots = [None] * 9
    slots[2] = BenchChar(slot=3, char_id='乙', star=1)

    rows: list[dict] = []
    set_defect_sink(rows.append)
    try:
        gs.observe(gs.bench, bench_view_of_slots(slots), sig=_SIG_OBS)
    finally:
        set_defect_sink(None)
        consume_defect_sink()

    assert [r['kind'] for r in rows] == ['observe_vs_logic_mismatch'], \
        '闩在不是失配吸收依据,units 失配照落真失配行'
    assert len(fired) == 1, '安灯照触发(停机语义零改动)'


# ============================================================ 执行器置位端


def _make_env(screens: list, session: object | None):
    """executor + env 构造(坐标注入绕 screen_info;截图序列 scripted)。"""
    from sr_od.application.currency_war import prep_actions as pa
    controller = type('_Ctl', (), {
        'mouse_move': lambda self, p: None,
        'drag_to': lambda self, **kw: None,
    })()
    sl = type('_SL', (), {'get_screen': lambda self, n: None})()
    op = type('_Op', (), {
        'screenshot': staticmethod(lambda: screens.pop(0)),
        'park_cursor': staticmethod(lambda **kw: None),
        'round_by_find_area': staticmethod(
            lambda *a, **k: type('_R', (), {'is_success': False})()),
        'ctx': type('_Ctx', (), {
            'controller': controller,
            'cw_match': (None if session is None
                         else type('_M', (), {'session': session})()),
            'run_context': None,
            'screen_loader': sl,
        })(),
    })()
    ctx = op.ctx
    ex = pa.PrepActionExecutor(op, ctx)
    ex._bench_pts = [Point(300, 800)] * 9
    ex._front_pts = [Point(300 + i * 140, 400) for i in range(4)]
    ex._back_pts = [Point(300 + i * 140, 620) for i in range(6)]
    env = PrepExecEnv(op=op, match=ctx.cw_match, executor=ex)
    return ex, env


def test_executor_marks_miss_and_keeps_tracked(monkeypatch):
    """置位端主锁:拖后目标槽像素零变化(同帧)→ 判未生效 → 置申报闩 +
    tracked 保持事实(单位仍在备战席,不记上阵);detail 申报未生效。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    frame = np.zeros((1080, 1920, 3), dtype='uint8')
    screens = [frame, frame.copy()]
    session, gs = _mk_gs_with_bench_unit()
    gs.tracked_books.bench = [None, BenchChar(slot=2, char_id='甲', star=1)]

    ex, env = _make_env(screens, session)
    ok = DeployMoveOp(_ACTION).execute(env)

    assert ok is True, '机械发出即职责完成(返回契约不变)'
    assert gs.exec_books.deploy_miss_pending == DeployMissMark(
        bench_idx=1, to_row='front', char_id='甲'), '像素零变化 → 置申报闩'
    assert gs.tracked_books.bench[1] is not None \
        and gs.tracked_books.bench[1].char_id == '甲', \
        'tracked 保持事实(单位仍在备战席槽2,不记上阵)'
    assert '未生效' in env.detail, 'detail 申报拖拽未生效'


def test_executor_landed_tracks_and_clears_stale_mark(monkeypatch):
    """生效腿回归:拖后目标槽出现像素变化 → tracked 记上阵 + 不置闩;
    execute 入口清旧闩(任何路径的部署动作都不消费上一动作的申报)。"""
    monkeypatch.setattr('time.sleep', lambda _s: None)
    frame = np.zeros((1080, 1920, 3), dtype='uint8')
    landed = frame.copy()
    landed[335:465, 240:360] = 255   # 目标槽(300,400)区域出现单位立绘
    screens = [frame, landed]
    session, gs = _mk_gs_with_bench_unit()
    gs.tracked_books.bench = [None, BenchChar(slot=2, char_id='甲', star=1)]
    gs.exec_books.deploy_miss_pending = DeployMissMark(
        bench_idx=7, to_row='back', char_id='乙')   # 陈旧闩残留

    ex, env = _make_env(screens, session)
    ok = DeployMoveOp(_ACTION).execute(env)

    assert ok is True
    assert gs.exec_books.deploy_miss_pending is None, \
        '生效路径不置闩 + 入口清旧闩'
    moved = [d for d in gs.tracked_books.deployed
             if d is not None and d.char_id == '甲']
    assert moved, 'tracked 记上阵(生效路径现行为不变)'
    assert all(b is None or b.char_id != '甲'
               for b in (gs.tracked_books.bench or [])), 'bench 侧摘除照旧'


# ============================================================ 像素验证纯函数


def test_region_changed_px_threshold_and_failsafe():
    """判据边界:零变化 → False(未生效);区域出现变化且达阈值 → True;
    形状不一致/退化 → True 保守放行(验证只在两帧齐备时发声,缺证不改变
    既有语义)。"""
    frame = np.zeros((1080, 1920, 3), dtype='uint8')
    assert _region_changed_px(frame, frame.copy(), Point(300, 400)) is False
    moved = frame.copy()
    moved[350:450, 260:340] = 255
    assert _region_changed_px(frame, moved, Point(300, 400)) is True
    assert _region_changed_px(moved, frame, Point(300, 400)) is True, \
        '反向差同样计入(判定对称)'
    below = frame.copy()
    below[399:401, 299:301] = 1   # 远低于阈值的微变化(噪声量级)
    assert float(np.abs(
        frame[335:465, 240:360].astype('int16')
        - below[335:465, 240:360].astype('int16')).mean()) \
        < DEPLOY_LAND_DIFF_THRESHOLD
    assert _region_changed_px(frame, below, Point(300, 400)) is False
    assert _region_changed_px(frame[:, :, :2], frame, Point(300, 400)) is True, \
        '形状不一致保守放行'
