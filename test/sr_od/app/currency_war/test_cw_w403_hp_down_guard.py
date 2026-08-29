"""W403/ADR-0430:hp 下行守卫——「幅度 × 战斗事实」联合判据 + 复现确认通道。

守卫语义(对账层,reconcile_hp 下行分支):
- win/零损节点帧:胜战不损血机制事实 → 任何下行一律拒信;
- loss 帧:Δ ≤ L_cap(node型)(p100 标定:普通 23/遭遇 42/boss 39)采新;
- 无战斗事实/节点型未标定:拒信 + 复现确认通道(连续 2 真值帧低位一致
  → 真掉血采新出窗;读回旧值 → 误读确认丢弃;毒化窗 ≤2 节点);
- node_t=None(离线/旧调用)守卫不介入,ADR-0282 行为零漂移。
"""
from __future__ import annotations


def _mk_session():
    from sr_od.application.currency_war.cw_strategy import StrategySession
    return StrategySession()


def _outcome(plane: int, round_num: int, node_type: str, killed) -> object:
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    return RoundOutcome(round_num=round_num, plane=plane, node_type=node_type,
                        comp_tag='test', hp_after=0, killed=killed)


def _seed_real(s, hp: int, node_t: int) -> None:
    """模拟上一真值帧(last_hp_real + 帧龄门节点锚)。"""
    s.last_hp_real = hp
    s.last_hp_real_node = node_t


# ===== 锁1:win 帧下行拒信(胜战不损血机制事实)=====

def test_win_frame_down_rejected(monkeypatch) -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '普通战斗', killed=True))
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    hp, readable = cw_reconcile.reconcile_hp(s, 20, node_t=6)
    assert (hp, readable) == (60, False)      # 拒信:沿用旧值
    assert s.last_hp_real == 60               # 不写 last_hp_real
    assert s.hp_suspect['value'] == 20        # 拒信值进复现通道
    assert len(calls) == 1
    assert calls[0][1].get('direction') == 'down'   # 方向字段区分


def test_zero_loss_node_down_rejected() -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '奖励', killed=None))   # 零损节点
    hp, readable = cw_reconcile.reconcile_hp(s, 55, node_t=6)
    assert (hp, readable) == (60, False)      # 小幅下行也无豁免


# ===== 锁2:loss 帧分档采信(p100 标定)=====

def test_loss_frame_within_cap_accepted() -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    # 遭遇 Δ=40 ≤ 42 → 真掉血,毒化窗不误开
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '遭遇', killed=False))
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (20, True)
    assert s.last_hp_real == 20 and s.hp_suspect is None
    # 普通战斗 Δ=20 ≤ 23 → 采新
    s2 = _mk_session()
    _seed_real(s2, 60, 5)
    s2.performance.record(_outcome(1, 6, '普通战斗', killed=False))
    assert cw_reconcile.reconcile_hp(s2, 40, node_t=6) == (40, True)


def test_loss_frame_over_cap_rejected() -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    # 普通战斗 Δ=40 > 23 → 拒信(毒化窗起点)
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '普通战斗', killed=False))
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)


def test_loss_cap_boundary_exact() -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '遭遇', killed=False))
    assert cw_reconcile.reconcile_hp(s, 18, node_t=6) == (18, True)   # Δ=42 恰在上界
    s2 = _mk_session()
    _seed_real(s2, 60, 5)
    s2.performance.record(_outcome(1, 6, '遭遇', killed=False))
    assert cw_reconcile.reconcile_hp(s2, 17, node_t=6) == (60, False)  # Δ=43 超界


def test_loss_unknown_node_type_rejected_then_self_heal() -> None:
    """节点型未标定(精英)不拍值:拒信 + 复现通道 ≤2 帧自愈。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '精英', killed=False))
    assert cw_reconcile.reconcile_hp(s, 40, node_t=6) == (60, False)
    assert cw_reconcile.reconcile_hp(s, 40, node_t=6) == (60, False)   # 首帧复现,仍沿用
    assert cw_reconcile.reconcile_hp(s, 40, node_t=6) == (40, True)    # 第 2 帧确认真掉血
    assert s.last_hp_real == 40 and s.hp_suspect is None


# ===== 锁3:无战斗事实拒信 + 双帧复现自愈 =====

def test_no_fact_down_rejected_then_confirmed() -> None:
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    assert s.performance.history == []
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)   # 无幅度豁免
    assert cw_reconcile.reconcile_hp(s, 20, node_t=7) == (60, False)   # 复现 1/2
    assert cw_reconcile.reconcile_hp(s, 20, node_t=7) == (20, True)    # 复现 2/2 → 采新
    assert s.last_hp_real == 20 and s.hp_suspect is None


def test_no_fact_down_regression_confirms_misread() -> None:
    """1 帧低位 + 1 帧回归旧值 → 误读确认,丢弃 suspect,一切如旧。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)
    assert cw_reconcile.reconcile_hp(s, 60, node_t=6) == (60, True)    # 回归 → 误读确认
    assert s.hp_suspect is None
    assert s.last_hp_real == 60


def test_suspect_window_expiry() -> None:
    """超窗(>2 节点)未复现 → suspect 过期,下次下行重新走首拒帧。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)
    assert s.hp_suspect['count'] == 0
    assert cw_reconcile.reconcile_hp(s, 20, node_t=9) == (60, False)
    assert s.hp_suspect['count'] == 0   # 重置,不延续旧计数


# ===== 锁4:守卫介入条件(零漂移边界)=====

def test_guard_inactive_without_node_t() -> None:
    """node_t=None(离线/旧调用方)守卫不介入,ADR-0282 行为逐位不变。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 50, None)
    assert cw_reconcile.reconcile_hp(s, 35) == (35, True)   # 无战斗事实仍采新
    assert s.hp_suspect is None


def test_first_truth_frame_unaffected() -> None:
    """无旧真值(开局)首真值帧不经守卫,FALLBACK 语义不变。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    assert cw_reconcile.reconcile_hp(s, 88, node_t=1) == (88, True)
    assert s.last_hp_real == 88 and s.last_hp_real_node == 1


# ===== 锁5:标定常量与消费面锚(源级)=====

def test_calibration_constants_locked() -> None:
    """L_cap p100 标定值/零损节点集/确认帧数/窗长(值单一源=注册表)。"""
    from sr_od.application.currency_war.kernel.cw_registry import (
        HP_LOSS_CAP_P100_BY_NODE,
        HP_SUSPECT_CONFIRM_FRAMES,
        HP_SUSPECT_WINDOW_NODES,
        HP_ZERO_LOSS_NODE_TYPES,
    )
    assert HP_LOSS_CAP_P100_BY_NODE == {'普通战斗': 23, '遭遇': 42, 'boss': 39}
    assert frozenset({'奖励', '补给'}) == HP_ZERO_LOSS_NODE_TYPES
    assert HP_SUSPECT_CONFIRM_FRAMES == 2
    assert HP_SUSPECT_WINDOW_NODES == 2


def test_consumer_face_zero_change_anchor() -> None:
    """谓词消费面零改锚:hp_decision_trusted 合取口径(hp_readable or
    hp_trusted)不随本批变化(ADR-0428 口径,行为锁另见 w332b/濒死带/C1)。"""
    import inspect

    from sr_od.application.currency_war.decision_v2 import posture_release
    src = inspect.getsource(posture_release)
    assert 'state.hp_readable or state.hp_trusted' in src


def test_reconcile_down_guard_wired() -> None:
    """源级锁:reconcile_hp 内下行守卫与复现通道接线存在。"""
    import inspect

    from sr_od.application.currency_war.kernel import cw_reconcile
    src = inspect.getsource(cw_reconcile.reconcile_hp)
    assert '_battle_fact_between' in src
    assert '_reject_down' in src
