"""W606 批③·适配器 Snapshot→决策输入 映射锁(设计 §3 逐字段表)。

锁面:
1. snapshot_to_obs 逐字段映射与 None 保守裁决(free_bench_slots None→9
   「宁多收球不误卖」/deploy_vacancy None→0);
2. decision_state 的 W598 四义务字段注入——active_strategies 注入即修复
   现役 _pseudo_state 漏拷裂缝(持有策略判据步级静默失效,cw_intention
   ._direct_line_qualified 消费面);
3. slot 双基:bench 容器下标 0-based 与 BenchChar.slot 1-based 并存,
   适配器不篡改 slot(策略 DeployMove(from_slot=bc.slot) 直消费);
4. hp 过 gated_hp 同一门(session 锚);F2:gold_untrusted 不进决策 state;
5. snapshot_from_obs 实机 None 语义(读不到=None 禁兜底,与 decide 侧
   消费映射方向相反,两方向分别锁)。
"""
from __future__ import annotations

from sr_od.application.currency_war.decision.cw_strategy import StrategySession, gated_hp
from sr_od.application.currency_war.decision_assembly import snapshot_from_obs
from sr_od.application.currency_war.decision.decision_v2.adapter import (
    decision_state,
    snapshot_to_obs,
)
from sr_od.application.currency_war.decision.decision_v2.contracts import (
    Snapshot,
    SubstateClassification,
)
from sr_od.application.currency_war.kernel.cw_state import BENCH_CAPACITY, BenchChar


def _snap(**kw) -> Snapshot:
    kw.setdefault(
        'classification', SubstateClassification(name='prep_shop', confident=True))
    return Snapshot(**kw)


def _session(**kw) -> StrategySession:
    s = StrategySession()
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_free_bench_slots_none_conservative_to_capacity():
    """free_bench_slots None → BENCH_CAPACITY(宁多收球不误卖;设计 §3.1 钉死)。"""
    obs = snapshot_to_obs(_snap(free_bench_slots=None), _session())
    assert obs.free_bench_slots == BENCH_CAPACITY
    # 对照:int 值原样(不做任何再解释)
    assert snapshot_to_obs(_snap(free_bench_slots=0), _session()).free_bench_slots == 0


def test_deploy_vacancy_none_conservative_zero():
    assert snapshot_to_obs(_snap(deploy_vacancy=None), _session()).deploy_vacancy == 0


def test_w598_four_obligation_fields_injected():
    """四义务字段从 session/last_state 显式注入(禁静默缺省)。"""
    sess = _session(dual_track_phase=True,
                    active_strategies=['黑塔纪元', '运筹帷幄'],
                    last_owned_equips=['量子同频'])
    from sr_od.application.currency_war.kernel.cw_state import GameState
    last = GameState()
    last.refresh_probs = {1: 0.7, 2: 0.2}
    sess.last_state = last
    st = decision_state(_snap(), sess)
    assert st.dual_track_phase is True
    assert st.active_strategies == ['黑塔纪元', '运筹帷幄']
    assert st.equips == ['量子同频']
    assert st.refresh_probs == {1: 0.7, 2: 0.2}


def test_active_strategies_gap_fix_nonempty_flows_to_decision_state():
    """裂缝修复行为锁:session 非空持有集 → decision_state 非空。

    现役 _pseudo_state 漏拷该字段 → 链 a/c 的 decision_target 走
    cw_intention._direct_line_qualified(state.active_strategies) 时恒空;
    适配器路径必须非空(否则该锁红)。"""
    sess = _session(active_strategies=['黑塔纪元'])
    st = decision_state(_snap(), sess)
    assert st.active_strategies == ['黑塔纪元']


def test_refresh_probs_missing_last_state_is_none():
    """refresh_probs 无 heavy 帧 → None(未读),不造空 dict 假真值。"""
    assert decision_state(_snap(), _session()).refresh_probs is None


def test_slot_dual_base_preserved():
    """bench 容器下标 0-based / 元素 BenchChar.slot 1-based 双基并存不篡改。"""
    bc = BenchChar(slot=3, char_id='希儿', faction='?', star=1)
    obs = snapshot_to_obs(_snap(bench=(None, None, bc)), _session())
    assert obs.bench_chars == [bc]
    assert obs.bench_chars[0].slot == 3   # slot 保持 1-based 屏幕槽号(信息位)


def test_gold_f2_untrusted_not_adopted():
    """F2:gold_trusted=False → 决策 state 不采用金(镜像现役伪态保守口径);
    gold_readable 保真位独立记录「读到了」。"""
    st = decision_state(_snap(gold=47, gold_trusted=False), _session())
    assert st.gold == 0
    assert st.gold_readable is True
    st2 = decision_state(_snap(gold=47, gold_trusted=True), _session())
    assert st2.gold == 47


def test_hp_none_uses_session_anchor_via_gated_hp():
    """hp None = 现读失败 → session 锚经 gated_hp 同一门(禁 0/100 兜底改值)。"""
    sess = _session()
    sess.last_hp = 55
    sess.last_hp_t = 4
    st = decision_state(_snap(hp=None, hp_readable=False, plane=1, round_num=5), sess)
    expect = gated_hp(55, sess, 4, current_readable=False)
    assert st.hp == expect
    assert st.hp_readable is False


def test_snapshot_from_obs_none_semantics():
    """实机观察 → 快照:读不到=None 禁兜底(decide 侧消费映射的逆方向)。"""
    from sr_od.application.currency_war.kernel.cw_prep_actions import PrepObservation
    obs = PrepObservation(state=None, state_gold_trusted=False)
    sess = _session()
    snap = snapshot_from_obs(obs, sess)
    assert snap.gold is None
    assert snap.gold_trusted is False
    assert snap.board is None
    assert snap.hp is None
    assert snap.hp_readable is False
    assert snap.classification.confident is True
    assert snap.classification.name == 'prep_shop'
    # spheres/boxes/tomes 坐标透传(1080p 绝对像素)
    from one_dragon.base.geometry.point import Point
    obs2 = PrepObservation(
        state=None,
        spheres=[('blue', Point(100, 200), 5)],
        boxes=[(3, Point(300, 400))],
        tomes=[(None, Point(500, 600))],
    )
    snap2 = snapshot_from_obs(obs2, sess)
    assert snap2.spheres[0].color == 'blue'
    assert (snap2.spheres[0].x, snap2.spheres[0].y) == (100, 200)
    assert (snap2.boxes[0].x, snap2.boxes[0].y) == (300, 400)
    assert (snap2.tomes[0].x, snap2.tomes[0].y) == (500, 600)


def test_snapshot_to_obs_rejects_unconfident():
    """非 confident 快照不可进 decide(框架门职责,适配器断言兜底)。"""
    import pytest
    bad = Snapshot(classification=SubstateClassification(
        name='unknown', confident=False))
    with pytest.raises(ValueError):
        snapshot_to_obs(bad, _session())
