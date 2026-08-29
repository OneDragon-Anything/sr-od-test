"""货币战争 DirectorV2 循环行为锁 + 生命周期六件套时机锁(W588 阶段2批②)。

- 循环行为锁:假快照序列 + 端口桩驱动 DirectorV2.run(纯引擎零 IO,可离线测),
  断言 正常步/defer/bail+ping-pong/非 confident 有界重试→留证停机/W209j 刹车
  双查点/步数预算/stall 门/连败→恢复→屏蔽链/fail-stop 批/跨域批拒绝/空批零进展。
- 六件套时机锁(权威表 = ADR-0458,「表=代码」一致性):环入口清零集与
  bail 局级计数不清;环内 progressed/恢复/屏蔽落定各清零点与 defer 跨步累积。

DirectorV2 未接线(纯新增未消费),本文件是其在批次内的唯一行为锚;
接线与旧环对拍归阶段2批③。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.decision.decision_v2.contracts import (
    AtomOp,
    Bail,
    Decision,
    Defer,
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.decision.decision_v2.director_v2 import (
    DirectorV2,
    LoopOutcomeKind,
    _DirectorPorts,
)

# ===== 桩与构造 ============================================================


def _snap(confident: bool = True, overlay: str | None = None,
          name: str = 'prep_shop') -> Snapshot:
    """构造快照:仅分类与 overlay 有意义,其余字段框架不读。"""
    return Snapshot(
        classification=SubstateClassification(name=name, confident=confident),
        event_overlay=overlay)


def _ops(*keys: str, domain: str = 'shop') -> Decision:
    """单域 op 批(op_key 即列表序执行)。"""
    return Decision(ops=tuple(AtomOp(k, domain) for k in keys))


class _Recorder:
    """端口桩调用记录(heavy 序/executed 序/恢复/强制/停机/缺陷台账)。"""

    def __init__(self) -> None:
        self.heavy_flags: list[bool] = []
        self.executed: list[str] = []
        self.recover_calls = 0
        self.forced_calls = 0
        self.stops: list[str] = []
        self.defects: list[tuple[str, str]] = []
        self.decide_count = 0


def _engine(snapshots: list[Snapshot] | Snapshot,
            decisions: list[Decision] | Decision,
            exec_results: dict[str, bool] | None = None,
            stopped_flags: list[bool] | bool = False,
            recover_closed_known: bool = False
            ) -> tuple[DirectorV2, _Recorder, SimpleNamespace]:
    """构造引擎 + 记录桩 + 假 session。

    - snapshots:观察序列,耗尽复用最后一个(恒不 confident 场景靠它);
    - decisions:决策序列,耗尽再取 = AssertionError(防测试自身死循环,
      decide 超发即测试脚本错);传单个 Decision = 恒同值(步数预算类用);
    - stopped_flags:is_stopped 现读序列(耗尽复用最后一个)。
    """
    rec = _Recorder()
    snaps = snapshots if isinstance(snapshots, list) else [snapshots]
    obs_state = {'i': 0}

    def observe(heavy: bool) -> Snapshot:
        rec.heavy_flags.append(heavy)
        i = min(obs_state['i'], len(snaps) - 1)
        obs_state['i'] += 1
        return snaps[i]

    if isinstance(decisions, Decision):
        def decide(_s, _sess):
            rec.decide_count += 1
            return decisions
    else:
        def decide(_s, _sess):
            rec.decide_count += 1
            if not decisions:
                raise AssertionError('decide 超发(测试脚本耗尽决策序列)')
            return decisions.pop(0)

    exec_map = exec_results or {}

    def execute(op):
        rec.executed.append(op.op_key)
        return exec_map.get(op.op_key, True), 'ok'

    flags = stopped_flags if isinstance(stopped_flags, list) else [stopped_flags]
    stop_state = {'i': 0}

    def is_stopped() -> bool:
        i = min(stop_state['i'], len(flags) - 1)
        stop_state['i'] += 1
        return flags[i]

    ports = _DirectorPorts(
        decide=decide, observe=observe, execute=execute,
        recover=lambda: (rec.__setattr__('recover_calls', rec.recover_calls + 1)
                         or recover_closed_known),
        force_battle=lambda _why='': rec.__setattr__('forced_calls', rec.forced_calls + 1)
        or True,
        is_stopped=is_stopped,
        stop_with_evidence=lambda reason: rec.stops.append(reason),
        record_defect=lambda kind, detail: rec.defects.append((kind, detail)))
    engine = DirectorV2(ports)
    session = SimpleNamespace(defer_count=0, prep_phase=0, bail_reason_counts={})
    return engine, rec, session


# ===== 循环行为锁 ==========================================================


def test_normal_step_progress_clears_stall_and_heavy_tail() -> None:
    """正常步:op progressed → stall/连败清零;批尾 heavy 观察恰一次;
    decide 收到该批尾后快照(环推进)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), Decision(control=Bail('done'))])
    engine._stall = 3          # 预置零进展计数:成功步必须断链清零
    engine._fail_counts = {'k1': 1}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == ['k1']
    assert engine._stall == 0
    assert 'k1' not in engine._fail_counts
    assert rec.heavy_flags == [True, True]   # 环入口 heavy + 批尾 heavy
    assert rec.forced_calls == 0


def test_defer_counts_and_light_observe() -> None:
    """defer 路径:框架计 defer、轻观察、不进 execute(控制流不经验证链)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Defer()), Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 1
    assert rec.executed == []
    assert rec.heavy_flags == [True, False]   # 控制流走轻观察


def test_bail_counts_only_grows_and_pingpong_stops() -> None:
    """bail 局级计数只增不清;同因达阈值 → 留证停机;异因不清彼因计数。"""
    # 基础:bail 计数 +1 → BAIL 出口
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('ov'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.bail_reason_counts == {'ov': 1}
    assert rec.stops == []
    # 同因预置 2 次,再 bail 一次 → ≥3 → ping-pong 留证停机
    engine2, rec2, sess2 = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('ov'))])
    sess2.bail_reason_counts = {'ov': DirectorV2.BAIL_SAME_REASON_DIAG - 1}
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.PINGPONG_STOP
    assert len(rec2.stops) == 1
    # 异因不清彼因:ov 已 2 次,来因 'other' → 仍 BAIL 不停
    engine3, rec3, sess3 = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Bail('other'))])
    sess3.bail_reason_counts = {'ov': DirectorV2.BAIL_SAME_REASON_DIAG - 1}
    outcome3 = engine3.run(sess3)
    assert outcome3.kind is LoopOutcomeKind.BAIL
    assert sess3.bail_reason_counts['ov'] == DirectorV2.BAIL_SAME_REASON_DIAG - 1   # 不清
    assert rec3.stops == []


def test_unconfident_bounded_retry_then_evidence_stop() -> None:
    """非 confident 不进 decide:有界重试(重观察)内恢复 → 正常推进;
    恒不 confident → 耗尽 → 留证停机接口位恰调一次。"""
    # a) 前 2 帧不 confident(不 decide),第 3 帧恢复 → 正常走
    engine, rec, sess = _engine(
        snapshots=[_snap(confident=False), _snap(confident=False), _snap()],
        decisions=[_ops('k1'), Decision(control=Bail('done'))],
        exec_results={'k1': True})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.decide_count == 2   # 两帧不 confident 均未到 decide
    assert rec.executed == ['k1']
    # b) 恒不 confident → 重试耗尽 → EVIDENCE_STOP + stop_with_evidence 一次
    engine2, rec2, sess2 = _engine(
        snapshots=_snap(confident=False),
        decisions=[_ops('k1')])
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.EVIDENCE_STOP
    assert rec2.decide_count == 0
    assert len(rec2.stops) == 1
    assert rec2.heavy_flags == [True] * (DirectorV2.CONF_RETRY_LIMIT + 1)   # 入口 + 3 重试


def test_brake_top_before_any_decide() -> None:
    """W209j 刹车·环顶查:停机标志已设 → 收口,decide/execute 零调用。"""
    engine, rec, sess = _engine(snapshots=[_snap()],
                                decisions=[_ops('k1')], stopped_flags=True)
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BRAKE_STOPPED
    assert rec.decide_count == 0
    assert rec.executed == []


def test_brake_before_execute() -> None:
    """W209j 刹车·执行前双查:op 已出 decide、未落地 → 停机收口不发动作。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[_ops('k1')],
                                exec_results={'k1': True},
                                stopped_flags=[False, True])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BRAKE_STOPPED
    assert rec.decide_count == 1   # decide 已发生
    assert rec.executed == []      # execute 前被刹


def test_step_budget_exhausted_forces_battle() -> None:
    """步数预算:DirectorV2.MAX_STEPS+1 步 → F5 强制出战端口恰调一次(恒空批驱动)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=_ops())   # 恒空批
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BATTLE_FORCED
    assert outcome.reason == '步数预算耗尽'
    assert rec.forced_calls == 1
    assert rec.decide_count == DirectorV2.MAX_STEPS   # 第 MAX_STEPS+1 步过门


def test_stall_gate_requires_recovery_tried() -> None:
    """stall 门:stall≥阈值但恢复未试 → 不强制;恢复已试 → 强制出战。"""
    # a) 连续零进展(空批)×DirectorV2.STALL_LIMIT,恢复未试 → 门不放行
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops(), _ops(), _ops(), _ops(), _ops(),
        Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL   # 门未触发,由 bail 收口
    assert engine._stall == DirectorV2.STALL_LIMIT
    assert rec.forced_calls == 0
    # b) 恢复已试(经真实失败链取得)+ 连续零进展补到阈值 → 门放行强制出战。
    # 注:引擎计数由 run() 环入口清零重建,不预设——这正是时机锁的语义。
    engine2, rec2, sess2 = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'),          # 连败×2 → 恢复一次(recovery_tried=True)
        _ops(), _ops(), _ops()],         # 零进展×3 → stall 5 → 过门
        exec_results={'k1': False})
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.BATTLE_FORCED
    assert outcome2.reason == 'stall+恢复试尽'
    assert rec2.forced_calls == 1
    assert rec2.recover_calls == 1


def test_fail_chain_recover_once_then_block() -> None:
    """连败→恢复→屏蔽链:连败 2 → 恢复原语恰一次 + 连败清零(重试窗);
    再连败 2 → 屏蔽落定 + 连败清零(防重复触发);屏蔽后同 key 重提案被拒。"""
    # a) 四次失败走完整链,恢复恰一次,不强制(stall 未到门)
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1'),
        Decision(control=Bail('done'))],
        exec_results={'k1': False})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.recover_calls == 1   # 恢复原语一次/实例,后续失败不再发
    assert engine._recovered == {'k1'}
    assert engine._blocked == {'k1'}
    assert engine._fail_counts.get('k1', 0) == 0   # 屏蔽落定清连败计数
    assert rec.forced_calls == 0
    # b) 恢复关过已知弹层仍败 → 弹层顽固 → bail 交外环(分型)。
    # 注:恢复发放清连败计数(重试窗),分型需恢复后再连败 2 次 → 共 4 决策。
    engine2, rec2, sess2 = _engine(
        snapshots=[_snap()],
        decisions=[_ops('k1'), _ops('k1'), _ops('k1'), _ops('k1')],
        exec_results={'k1': False}, recover_closed_known=True)
    outcome2 = engine2.run(sess2)
    assert outcome2.kind is LoopOutcomeKind.BAIL
    assert '恢复无效-弹层' in outcome2.reason
    assert engine2._blocked == set()   # 弹层顽固走 bail 不屏蔽
    # c) 屏蔽后同 key 重提案:拒绝执行 + 计 stall(确定性重提案防线);
    # 引擎计数同样不预设,屏蔽态由真实链走到(4 连败 + 第 5 次提案被拒过门)。
    engine3, rec3, sess3 = _engine(snapshots=[_snap()], decisions=[
        _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1'), _ops('k1')],
        exec_results={'k1': False})
    outcome3 = engine3.run(sess3)
    assert outcome3.kind is LoopOutcomeKind.BATTLE_FORCED   # 拒绝计 stall → 过门
    assert rec3.executed == ['k1', 'k1', 'k1', 'k1']        # 第 5 次未落地


def test_fail_stop_batch_drops_remaining() -> None:
    """fail-stop 批:三 op 批第 2 个失败 → 第 3 个不执行、批中止。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops('k1', 'k2', 'k3'), Decision(control=Bail('done'))],
        exec_results={'k1': True, 'k2': False, 'k3': True})
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == ['k1', 'k2']   # k3 丢弃
    assert engine._blocked == set()       # k2 仅失败一次,未到连败门


def test_cross_domain_batch_rejected() -> None:
    """跨域批:域校验拒绝,零 execute 调用,计 stall(MED-3 拒绝路径过门)。"""
    cross = Decision(ops=(AtomOp('k1', 'shop'), AtomOp('k2', 'bench')))
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        cross, Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == []
    assert engine._stall == 1


def test_empty_ops_zero_progress_stall() -> None:
    """空批 = 合法零进展:计 stall、无 execute(空返回防线,W561 攻击1)。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        _ops(), Decision(control=Bail('done'))])
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert rec.executed == []
    assert engine._stall == 1


# ===== 六件套时机锁(权威表 = ADR-0458;「表=代码」一致性)==================


def test_entry_reset_table() -> None:
    """环入口清零表:defer/prep_phase/步数/stall/连败链全清,
    **bail 局级计数不清**(唯一清零点 = 外环 handler 成功消化)。"""
    engine, rec, sess = _engine(snapshots=[_snap()],
                                decisions=[Decision(control=Bail('probe'))])
    sess.defer_count = 5
    sess.prep_phase = 7
    sess.bail_reason_counts = {'x': 2}          # 局级陈计数
    engine._steps = 9
    engine._stall = 4
    engine._fail_counts = {'a': 1}
    engine._blocked = {'b'}
    engine._recovered = {'c'}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 0                # 件 4:环入口清
    assert sess.prep_phase == 0
    assert engine._steps == 1                   # 件 1:入口清零后本步已 +1
    assert engine._stall == 0                   # 件 2:入口清(bail 路径不计 stall)
    assert engine._fail_counts == {}            # 件 3:重建
    assert engine._blocked == set()             # 件 3:屏蔽集生命周期 = 本环
    assert engine._recovered == set()
    assert sess.bail_reason_counts == {'x': 2, 'probe': 1}   # 件 5:只增不清


def test_intra_loop_clear_points_table() -> None:
    """环内清零表:progressed 清 stall+连败;恢复发放清连败留 recovered;
    屏蔽落定清连败留 blocked;defer 跨步累积不被步间清零。"""
    engine, rec, sess = _engine(snapshots=[_snap()], decisions=[
        Decision(control=Defer()),
        Decision(control=Defer()),
        _ops('k1'),
        Decision(control=Bail('done')),
    ], exec_results={'k1': True})
    engine._stall = 2
    engine._fail_counts = {'k1': 1}
    outcome = engine.run(sess)
    assert outcome.kind is LoopOutcomeKind.BAIL
    assert sess.defer_count == 2                # 件 4:步间不清,跨步累积
    assert engine._stall == 0                   # 件 2:progressed 即清
    assert 'k1' not in engine._fail_counts      # 件 3:progressed 清连败
