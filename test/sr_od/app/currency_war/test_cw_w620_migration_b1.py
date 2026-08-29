"""W620 批 1(重构迁移·框架一次集成接线)锁面。

依据 = 蓝图 v-final.1 §7 批 1 行 + §1/§2/§3.4/§4.3:
1. TurnState 装配:幂等(frozen 值语义,重入等值)+ 方向/预算投影字段齐;
2. R1:committed 唯一合法读端(prep_brain.committed_from),session
   ``dual_track_phase`` 直读点归零(源码 grep 守卫);
3. R2:tracking 优先读口(tracking 非空优先,空退 fresh read);
4. R4 接缝:schedule_upgrade / refresh_ev_budget 公开纯函数落地;
5. 单帧等价锁:prep_brain 管线 decide 输出与旧通道(直调现役决策核)
   逐位一致(批 1 行为语义 = 与旧环等价);
6. DirectorV2 出战域 op 落地 = BATTLE 正常出口(批 1 接线补)。
"""
from __future__ import annotations

from pathlib import Path

from sr_od.application.currency_war.cw_state import BenchChar
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.adapter import (
    DecideAdapter,
    snapshot_to_obs,
)
from sr_od.application.currency_war.decision_v2.contracts import (
    AtomOp,
    Decision,
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.decision_v2.director_v2 import (
    DirectorV2,
    LoopOutcomeKind,
    _DirectorPorts,
)
from sr_od.application.currency_war.decision_v2.prep_brain import (
    assemble,
    committed_from,
)
from sr_od.application.currency_war.decision_v2.turn_state import (
    BudgetView,
    DirectionView,
    TurnState,
)
from sr_od.application.currency_war.prep_actions import SellBench

_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')


def _snapshot() -> Snapshot:
    return Snapshot(
        classification=SubstateClassification(
            name='prep_shop', evidence=('test',), confident=True),
        plane=1, round_num=2, level=3, gold=40, gold_trusted=True,
        free_bench_slots=3, deploy_vacancy=1, shop_open=False,
    )


class _Strat:
    """可编程假策略(记录 obs 输入,返回固件动作——单帧等价对照用)。"""

    def __init__(self):
        self.last_obs = None

    def decide_prep_action(self, obs, session, config):
        self.last_obs = obs
        return SellBench(3)


class _Executor:
    """F3 校验桩(恒合法;不执行)。"""

    def validate(self, action):
        return None

    def execute(self, action):
        return True, 'stub'


# ----------------------------------------------------- 1. TurnState 装配

def test_assemble_is_idempotent_and_frozen():
    import dataclasses

    import pytest

    sess = StrategySession()
    snap = _snapshot()
    t1 = assemble(snap, sess)
    t2 = assemble(snap, sess)
    assert t1 == t2 and isinstance(t1, TurnState)
    with pytest.raises(dataclasses.FrozenInstanceError):
        t1.budget = BudgetView()   # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        t1.direction = DirectionView()   # type: ignore[misc]


def test_assemble_projects_direction_and_budget_fields():
    sess = StrategySession()
    turn = assemble(_snapshot(), sess)
    d, b = turn.direction, turn.budget
    # 方向投影:字段齐(蓝图 §2 清单)+ R2 读口非空
    # 批 2 语义换源:缺供给帧(ist 无 + plane<2)= 保守侧 False(D2)
    assert isinstance(d.committed, bool) and d.committed is False
    assert d.hoard_readable is True   # D1:正常帧可信位为真
    assert d.fallback_comp != ''
    assert isinstance(d.hoard, frozenset)
    # 批 3 F5 清偿:三门模块级旗标退役,gates 恒空(字段保留=契约形状)
    assert set(d.gates) == set()
    assert isinstance(d.bench_view, tuple)
    assert isinstance(d.deployed_view, tuple)
    # 预算投影:R* = 息线 + 排程(息线帧 → R* == floor,零漂移 I-1 前提)
    assert b.interest_floor > 0
    assert b.reserve_cap >= b.interest_floor
    assert b.obligation == 0   # g=40 ≤ R* → 无义务帧
    assert b.ev_auth >= 0 and isinstance(b.schedule, bool)


# ----------------------------------------------------- 2. R1 committed 读端

def test_committed_from_semantics():
    """批 2 语义换源(方向层接管):权威 = cw_intention 派生谓词。

    - 缺供给帧(ist 无 + plane<2)→ False 保守侧(D2,禁缺省 True);
    - ist.phase=='locked' / p1_pair 非空 / plane≥2 → True(权威序);
    - 旧 session 双轨字段写入不再影响读端(字段读点已归零)。
    """
    sess = StrategySession()
    assert committed_from(sess) is False         # 缺供给 = 保守双轨
    from sr_od.application.currency_war.cw_intention import IntentionState
    sess.v3_intention = IntentionState()
    assert committed_from(sess) is False         # ist 未锁,仍双轨
    sess.v3_intention.phase = 'locked'
    assert committed_from(sess) is True          # 锁线 → 已定型
    sess2 = StrategySession()
    sess2.v3_intention = IntentionState(p1_pair=('仙舟', '列车'))
    assert committed_from(sess2) is True         # 配方锁立 → 已定型
    st = _mk_state()
    st.plane = 2
    assert committed_from(StrategySession(), st) is True   # P2 恒定型
    sess3 = StrategySession()
    sess3.dual_track_phase = True                # 旧字段写端:不再被读
    assert committed_from(sess3) is False


def test_grep_guard_session_dual_track_read_points_isolated():
    """session 双轨态直读点归零:唯一读端 prep_brain.committed_from。

    守卫形状(W624 F3 修补:模式须跨点号,锁得住 ``getattr(_match.session,…)``
    与 ``_match.session.dual_track_phase`` 形态;全文扫描不锚行,防多行
    getattr 漏检):
    - getattr(session 系变量, 'dual_track_phase') — 除读端文件外全禁;
    - ``<…session…>.dual_track_phase`` 属性**读**(非赋值)全禁
      (default_strategy 写端 / cw_replay 离线恢复写端不受扰;
      state 字段读如 last_state.dual_track_phase 不属 session 读,不禁)。
    """
    pat_getattr, pat_read, pat_last_state = _guard_patterns()
    offenders: dict[str, int] = {}
    for path in _SRC.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        hits = (len(pat_getattr.findall(text)) + len(pat_read.findall(text))
                + len(pat_last_state.findall(text)))
        if hits:
            offenders[path.name] = hits
    # 批 2(R1 终局):committed_from 换源 cw_intention 权威派生后,session
    # 侧双轨字段读点 = **全仓归零**(连唯一读端也不再读旧字段);变异
    # 自检(test_grep_guard_mutation_self_check)钉住守卫仍抓得住历史原形。
    assert not offenders, offenders


def _guard_patterns():
    """守卫模式单一源(守卫测试与变异自检共用,防两处漂移)。

    W629-R1 扩口:守卫辖域从 session 直读扩至 **state/last_state 通道**
    (equip_all L406 裸直读 last_state.dual_track_phase 曾在旧措辞之外,
    W623 D3 活证据)——``last_state.dual_track_phase`` 读(非赋值)全禁。
    一般 ``state.dual_track_phase`` 读仍是老栈消费面(装配边界权威回填,
    批 4 随老栈退役归零),不在本守卫辖。
    """
    import re
    pat_getattr = re.compile(
        r"getattr\(\s*[\w.]*sess\w*\s*,\s*'dual_track_phase'")
    pat_read = re.compile(r"\b[\w.]*sess\w*\.dual_track_phase\b(?!\s*=)")
    pat_last_state = re.compile(
        r"\blast_state\.dual_track_phase\b(?!\s*=)")
    return pat_getattr, pat_read, pat_last_state


def test_grep_guard_mutation_self_check():
    """守卫变异自检(W624 F3):用改造前原形验证守卫确实锁得住。

    原形取自 deploy_bench.py:269 / shop.py:492(W620 批 1 前)与
    equip_all.py:406(W629-R1 扩口,改造前)。
    反例 = 一般 state 字段读与写端(守卫不得误报)。
    """
    pat_getattr, pat_read, pat_last_state = _guard_patterns()
    historical_forms = [
        "_st_dual = getattr(_match.session, 'dual_track_phase', False)",
        "state.dual_track_phase = getattr("
        "match.session, 'dual_track_phase', False)",
        "getattr(session, 'dual_track_phase', False)",
        # W629-R1:last_state 通道原形(equip_all L406 改造前)
        "and _match.session.last_state.dual_track_phase) "
        "if _match is not None else False",
        "if sess.last_state.dual_track_phase:",
    ]
    for form in historical_forms:
        assert (pat_getattr.search(form) or pat_read.search(form)
                or pat_last_state.search(form)), \
            f'守卫漏检历史原形(变异自检失败): {form}'
    # 反例:一般 state 字段读不误报;赋值写端放行
    state_field_reads = [
        "_dual = bool(_match.session.last_state is not None)",
        "if getattr(state, 'dual_track_phase', False):",
        "session.dual_track_phase = state.dual_track_phase",
        "_os.dual_track_phase = not committed_from(session, _os)",
    ]
    for form in state_field_reads:
        assert not (pat_getattr.search(form) or pat_read.search(form)
                    or pat_last_state.search(form)), \
            f'守卫误报非 session 读(变异自检失败): {form}'


# ----------------------------------------------------- 3. R2 tracking 读口

def test_tracking_view_prefers_tracked_over_fresh():
    sess = StrategySession()
    tracked = BenchChar(slot=1, char_id='huohuo', star=2)
    sess.tracked_bench_chars = [tracked]
    snap = _snapshot()
    turn = assemble(snap, sess)
    assert turn.direction.bench_view == (tracked,)   # tracking 优先
    # tracking 空 → fresh read 补缺(snapshot.bench 通道)
    sess2 = StrategySession()
    turn2 = assemble(snap, sess2)
    assert turn2.direction.bench_view == tuple(snap.bench)


# ----------------------------------------------------- 4. R4 接缝

def test_r4_seam_functions_public_and_pure():
    from sr_od.application.currency_war.decision_v2.economy_cycle import (
        refresh_ev_budget,
        schedule_upgrade,
    )
    sess = StrategySession()
    assert schedule_upgrade(_mk_state(), sess) in (True, False)
    assert refresh_ev_budget(_mk_state(), sess) >= 0


def _mk_state():
    from sr_od.application.currency_war.cw_state import GameState
    st = GameState()
    st.plane, st.round_num, st.level, st.gold = 1, 2, 3, 40
    return st


# ----------------------------------------------------- 5. 单帧等价锁

def test_single_frame_equivalence_new_pipeline_vs_old_channel():
    """批 1 等价判据:新管线 decide 输出与旧通道(直调决策核)逐位一致。"""
    sess = StrategySession()
    snap = _snapshot()
    strat_new, strat_old = _Strat(), _Strat()
    adapter = DecideAdapter(strat_new, config=None, executor=_Executor())
    decision = adapter.decide(snap, sess)
    # 旧通道:同一 snapshot 经同一 obs 通道直调决策核
    action_old = strat_old.decide_prep_action(
        snapshot_to_obs(snap, sess), sess, None)
    from sr_od.application.currency_war.decision_v2.adapter import action_to_atomop
    new_sig = ('op', decision.ops[0].op_key, decision.ops[0].domain)
    old_op = action_to_atomop(action_old)
    old_sig = ('op', old_op.op_key, old_op.domain)
    assert new_sig == old_sig
    # obs 通道一致:两路决策核看到的 obs 逐字段相同(frozen 快照深拷贝语义)
    assert strat_new.last_obs.state.gold == strat_old.last_obs.state.gold
    assert (strat_new.last_obs.free_bench_slots
            == strat_old.last_obs.free_bench_slots)


# ----------------------------------------------------- 6. 出战域出口

def _ports(decide, execute):
    return _DirectorPorts(
        decide=decide,
        observe=lambda heavy: _snapshot(),
        execute=execute,
        recover=lambda: False,
        force_battle=lambda _w='': True,
        is_stopped=lambda: False,
        stop_with_evidence=lambda _r: None,
        record_defect=lambda k, d: None,
    )


def test_battle_domain_op_success_exits_as_battle():
    sess = StrategySession()
    calls = {'n': 0}

    def decide(snapshot, session):
        calls['n'] += 1
        return Decision(ops=(AtomOp(op_key='start_battle', domain='battle'),))

    def execute(op):
        return True, 'ok'

    outcome = DirectorV2(_ports(decide, execute)).run(sess)
    assert outcome.kind is LoopOutcomeKind.BATTLE
    assert calls['n'] == 1   # 出战落地即退环,不再重观察重决策


def test_battle_op_failure_does_not_exit():
    sess = StrategySession()

    def decide(snapshot, session):
        return Decision(ops=(AtomOp(op_key='start_battle', domain='battle'),))

    def execute(op):
        return False, '未落地'

    outcome = DirectorV2(_ports(decide, execute)).run(sess)
    assert outcome.kind is not LoopOutcomeKind.BATTLE
