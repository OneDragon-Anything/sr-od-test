"""证据门接线批锁(T-213:影子评估 + missing 分解单一源 + 帧装配器)。

设计出处 = ``.debug/temp/currency_war/T-213-接线设计.md`` + ADR-0637
(接线批)+ math_proofs P76 §4.4(夹界帧项)/P38 ③层(slot_q_tag 含
池衰减)+ T-124-r1 §四.1 四要件(①分解生产者 ②帧装配器 ③A/B 同批
④消费位接线方案审)。形态 = R197 症2 同族影子面(输出只进
cw4_counters 分键,零行为;封印期恒「不可评」诚实显影,NMF §6/§5.3
绝不向骨架层渗漏为否决)。

数值锚纪律:q/m/trials/帧项全部由注册表原语与 kernel 单一源在测试内
独立复算(锁的是装配公式与接线形态,不锁数据巧合);分键断言只锁
键结构。守卫移除验证 = ④ 源级影子申报锁 + ⑤ emit 调用位锁
(摘 entry 调用行 / 摘成因桶写入行必红)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import (
    DISTINCT_CARDS_PER_COST,
    POOL_COPIES_PER_CARD,
    SHOP_SLOTS,
)
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_bridge as _bridge,
)
from sr_od.application.currency_war.kernel.cw_line_switch import (
    line_distance,
)
from sr_od.application.currency_war.kernel.cw_plane_table import r_remaining
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BENCH_CAPACITY,
    BenchChar,
    CwWorkFrame,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    proof,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import (
    provisional,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    odds,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.vopt import (
    a7_lower_bound,
    p_complete,
    p_miss,
)
from test.sr_od.app.currency_war._cw_helpers import cw4_feed

_COMP = COMP_LIBRARY[0]          # 列车同行,form_tiers = {'列车同行': 4}
_TIER = '列车同行'
_PT_COST_MEMBERS = None          # 惰性:逐费档该档成员数(测试内派生)


def _tier_members(tag: str) -> list[str]:
    """标签合格集成员名(CHARACTERS 直查,factions∪flows 与生产同口径)。"""
    return [n for n, ch in CHARACTERS.items()
            if getattr(ch, 'cost', 0) and tag in
            ((getattr(ch, 'factions', ()) or ())
             + (getattr(ch, 'flows', ()) or ()))]


def _session(target: object = _COMP) -> SimpleNamespace:
    """桩 session(策略态经 ``state_of`` 惰建载体写入——target/counters
    必须落在 StrategyState 上,与生产 state_of 读口同源)。"""
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = target
    return s


def _counters(sess: SimpleNamespace) -> dict:
    return state_of(sess).cw4_counters


@pytest.fixture(autouse=True)
def _clean_slots():
    """provisional 槽位全局态隔离(测试纪律:改全局态必须复原)。"""
    provisional.reset()
    yield
    provisional.reset()


# ===== ① missing 分解生产者(单一源;T-124-r1 §四.1 要件①)=====

class TestLineMissingDecomposition:

    def test_items_and_dual_with_line_distance(self):
        """无超持态:逐档缺口项在手 + Σm == line_distance(口径对偶锁,
        防 tier_progress 分叉漂移)。"""
        st = CwWorkFrame(gold=30, level=7, board={}, shop=[])
        md = proof.line_missing_decomposition(_COMP, _bridge(st))
        assert md, '空板局缺口非空'
        assert md[0][0] == _COMP.form_tiers[_TIER]
        assert 0.0 <= md[0][1] <= 1.0
        assert sum(m for m, _q in md) == line_distance(_COMP, _bridge(st))

    def test_satisfied_items_dropped(self):
        """已满足件剔除(P38 配方):板面齐档 ⇒ 空表(complete 域归
        调用方,本函数不发 complete)。"""
        st = CwWorkFrame(gold=30, level=7,
                       board=dict(_COMP.form_tiers),
                       shop=[])
        assert proof.line_missing_decomposition(_COMP, _bridge(st)) == []

    def test_shelf_subtracts_gap_and_enters_pool_decay(self):
        """货架件「买走即 held」(line_distance 同式):缺口减 1 + 同标签
        池衰减经 extra 通道生效(与 slot_q_tag extra 直算逐位一致)。"""
        members = _tier_members(_TIER)
        cost = CHARACTERS[members[0]].cost
        shelf = [SimpleNamespace(faction=_TIER, cost=cost)]
        st = CwWorkFrame(gold=30, level=7, board={}, shop=shelf)
        md = proof.line_missing_decomposition(_COMP, _bridge(st))
        assert md[0][0] == _COMP.form_tiers[_TIER] - 1
        assert md[0][1] == pytest.approx(
            odds.slot_q_tag(_TIER, 7, {}, {cost: 1}))

    def test_unreachable_q_zero_still_in_table(self):
        """q=0(该级刷不出)项照常入表:p_complete 对 q≤0 返 0 → 必要侧
        拒,静态不可达线诚实出「锁劣」向,禁静默剔除。

        comp 动态选激活(T-278 随手件,T-213 落地审修瑕②):静态
        _COMP(列车同行)各档含 1 费成员,L1 恒可达 ⇒ 旧锁恒 skip。
        本锁扫 COMP_LIBRARY 选「存在无 1 费成员档」的 comp(现库唯一
        = 希儿量子/量子同频档,成员费 2/2/3/4/4),扫描不出 =
        pytest.fail(注册表退化显影,非静默 skip)。"""
        target = None
        unreachable_need = 0
        for comp in COMP_LIBRARY:
            tiers = getattr(comp, 'form_tiers', {}) or {}
            for tag, need_t in tiers.items():
                members = _tier_members(tag)
                if members and all(CHARACTERS[n].cost >= 2 for n in members):
                    target = comp
                    unreachable_need = need_t
                    break
            if target is not None:
                break
        assert target is not None, '全库无「无 1 费成员档」comp,q=0 锁失配'
        st = CwWorkFrame(gold=30, level=1, board={}, shop=[])   # L1 只出 1 费
        md = proof.line_missing_decomposition(target, _bridge(st))
        assert (unreachable_need, 0.0) in md, 'q=0 不可达项被静默剔除'

    def test_per_tier_clamp_ge_global_declared(self):
        """有意分歧申报锁:逐档 clamp 分解和 ≥ 全局 clamp 标量
        (line_distance),跨 comp × 板面态扫域成立(两形态并存、
        禁统一的设计申报,见接线设计 §3)。"""
        boards: dict[str, dict[str, int]] = {
            'empty': {},
            'satisfied': dict(_COMP.form_tiers),
        }
        for comp in COMP_LIBRARY[:20]:
            for bd in boards.values():
                st = CwWorkFrame(gold=30, level=7, board=dict(bd), shop=[])
                total_m = sum(m for m, _q in
                              proof.line_missing_decomposition(comp, _bridge(st)))
                assert total_m >= line_distance(comp, _bridge(st)), (comp.name, bd)

    def test_shelf_overshoot_both_zero(self):
        """货架超额域:单档 need<shelf ⇒ 逐档与全局同为 0(发散下界域,
        不产负缺口项)。"""
        members = _tier_members(_TIER)
        cost = CHARACTERS[members[0]].cost
        shop = [SimpleNamespace(faction=_TIER, cost=cost)
                for _ in range(_COMP.form_tiers[_TIER] + 2)]
        st = CwWorkFrame(gold=30, level=7, board={}, shop=shop)
        assert proof.line_missing_decomposition(_COMP, _bridge(st)) == []
        assert line_distance(_COMP, _bridge(st)) == 0


# ===== ② slot_q_tag(P38 ③层单一源;odds.py)=====

class TestSlotQTag:

    def test_degenerate_domain_formula(self):
        """单费档退化域公式锁:L1 只出 1 费 ⇒ q_tag = p·(n·a−j)/(v·a−j−t)
        在测试内按 P38 ③层原式独立复算(n=该档 1 费成员数,j=标签持有,
        t=同费非标签持有——分子分母同扣 j,R200 勘误约定)。"""
        members = [n for n in _tier_members(_TIER)
                   if CHARACTERS[n].cost == 1]
        assert members, '该档应含 1 费成员'
        a = POOL_COPIES_PER_CARD[1]
        v = DISTINCT_CARDS_PER_COST[1]
        held = {members[0]: 2}
        other = next(n for n, ch in CHARACTERS.items()
                     if getattr(ch, 'cost', 0) == 1 and n not in members)
        held[other] = 1      # 同费非标签 1 张 → t=1
        n_c = len(members)
        expected = 1.0 * (n_c * a - 2) / (v * a - 2 - 1)
        assert odds.slot_q_tag(_TIER, 1, held) == pytest.approx(expected)

    def test_extra_copies_decay(self):
        """extra_copies_by_cost(货架将买件)加深同档池衰减:q 严格变小。"""
        level = 7
        base = odds.slot_q_tag(_TIER, level, {}, {})
        assert base > 0.0, 'L7 该档应可达'
        bd = odds.slot_q_tag_by_cost(_TIER, level, {}, {})
        cost = max(bd, key=lambda c: bd[c])
        assert odds.slot_q_tag(_TIER, level, {}, {cost: 1}) < base


# ===== ③ 帧装配器(LockSandwichFrame 六项;T-124-r1 §四.1 要件②)=====

class TestAssembleLockFrame:

    def test_trials_mapping_and_e_p_next(self):
        """试验数映射锁:trials = SHOP_SLOTS×(R_全局 + 付费刷数)、
        e_p_next = p_complete(missing, trials − SHOP_SLOTS)(等待一帧
        只自然刷)。付费刷数语义迁移(标定批 T-278/ADR-0639):静态
        预算近似退役,源 = P38 ⑤层金位递推(statefn/budget,公式锁
        与递推×装配一致性锁在 test_cw_evidence_gate_calibration.py
        单一承载,本锁只辖映射与等待一帧语义)。"""
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        missing, trials, frame = proof.assemble_lock_frame(_bridge(st), sess)
        assert missing
        r_rem = r_remaining(sess, 1, 3)
        assert trials % SHOP_SLOTS == 0
        assert trials >= SHOP_SLOTS * r_rem
        assert frame.e_p_next == pytest.approx(
            p_complete(missing, max(0, trials - SHOP_SLOTS)))

    def test_sealed_fields_none(self):
        """o_plus/d_death 恒 None(V_ms/Δλ【拟】挂账):None 期门恒不可评,
        ADR-0637 敞口申报的机器可读形态。"""
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        _missing, _trials, frame = proof.assemble_lock_frame(_bridge(st), sess)
        assert frame.o_plus is None
        assert frame.d_death is None

    def test_side_line_h_minus_star_and_handling_fee(self):
        """H−* 差分口径(修正 4):侧线件计入手续费与重建期权;f_plus 形 =
        (1−P)Σ(P_miss·C_rescue+1) 在测试内以 vopt 原语独立复算(锁装配
        公式);H_S = star≥2∧cost≥2 侧线件数,1 金 = 甲.2 机制真值。"""
        k_names = set(_COMP.core_chars)
        side_name = next(n for n, ch in CHARACTERS.items()
                         if getattr(ch, 'cost', 0) >= 2
                         and n not in k_names)
        cost = CHARACTERS[side_name].cost
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        st.bench = [BenchChar(slot=1, char_id=side_name, star=2)]
        missing, trials, frame = proof.assemble_lock_frame(_bridge(st), sess)
        p_lock = p_complete(missing, trials)
        rescue = a7_lower_bound(7, cost, 2, 1, 0)
        expected_f = (1.0 - p_lock) * (p_miss(7, cost, 1, 0) * rescue + 1.0)
        assert frame.f_plus == pytest.approx(expected_f)
        assert frame.c_hold >= 1.0   # H_S = 1(star2 ∧ cost≥2)
        assert frame.b_plus >= 0.0

    def test_csat_gate_by_free_bench(self):
        """C_sat 事件门在库(v_slot:free>1 ⇒ 0):空 bench 无侧线 ⇒ c_hold
        = 0;满 bench(free≤1)∧ 缺件可评 ⇒ c_hold > 0(缺件购入期权被
        阻断的饱和成本显影)。"""
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        _missing, _trials, frame = proof.assemble_lock_frame(_bridge(st), sess)
        assert frame.c_hold == 0.0     # 无侧线件 ∧ free=9>1
        st2 = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                        shop=[])
        st2.bench = [BenchChar(slot=i, char_id=f'燃料{i}')
                     for i in range(1, BENCH_CAPACITY + 1)]
        missing2, _t2, frame2 = proof.assemble_lock_frame(_bridge(st2), sess)
        assert missing2     # L7 该档可达,缺件在册
        assert frame2.c_hold > 0.0


# ===== ④ 影子评估(分键;守卫在 entry 调用位)=====

class TestEvaluateEvidenceGate:

    def test_state_none_or_no_target_skip(self):
        sess = _session(target=None)
        assert proof.evaluate_evidence_gate(CwWorkFrame(gold=20), sess) is None
        assert _counters(sess) == {}

    def test_empty_missing_not_evaluated(self):
        """缺口空帧不评估(锁线时机问题不存在;不产计数噪声)。"""
        sess = _session()
        st = CwWorkFrame(gold=30, level=7,
                       board=dict(_COMP.form_tiers),
                       shop=[])
        assert proof.evaluate_evidence_gate(_bridge(st), sess) is None
        assert 'evidence_gate_evaluated' not in _counters(sess)

    def test_sealed_unavailable_aggregate_and_causes(self):
        """封印期:聚合键 + 成因分桶键逐键(聚合与成因不同键防混计,
        R24-2 纪律;摘任一成因桶写入行本锁红 = 守卫移除验证)。"""
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        ok, reason = proof.evaluate_evidence_gate(_bridge(st), sess)
        assert ok is False
        assert reason.startswith('sandwich_unavailable')
        ct = _counters(sess)
        assert ct['evidence_gate_evaluated'] == 1
        assert ct['evidence_gate_unavailable'] == 1
        for cause in ('d_death', 'delta', 'e2', 'o_plus'):
            assert ct[f'evidence_gate_unavailable_{cause}'] == 1, cause

    def test_injected_end_to_end_suff_key(self, monkeypatch):
        """端到端实质裁决键:Δ/ε₂ 注入 + 全装配帧(monkeypatch 装配器,
        因 o_plus/d_death 值因子在册挂账未落地)⇒ sandwich_suff 分键。
        锁键推导 = reason '(' 前缀(带数值串禁作键)。"""
        provisional.inject('V_C_MINUS_V_F', provisional.CalibValue(10.0))
        provisional.inject('E2_CONCENTRATION_BAND',
                           provisional.CalibValue(0.0))
        frame = proof.LockSandwichFrame(
            e_p_next=0.3, o_plus=0.5, f_plus=0.5, b_plus=0.5,
            c_hold=1.0, d_death=1.0)
        monkeypatch.setattr(proof, 'assemble_lock_frame',
                            lambda st_, sess_: ([(1, 0.5)], 1, frame))
        sess = _session()
        st = CwWorkFrame(gold=60, level=7, round_num=3, plane=1, board={},
                       shop=[])
        ok, reason = proof.evaluate_evidence_gate(_bridge(st), sess)
        assert ok is True
        assert reason.startswith('sandwich_suff(')   # 数值串在 '(' 后
        assert _counters(sess)['evidence_gate_sandwich_suff'] == 1

    def test_shadow_return_not_consumed_by_entry(self):
        """影子面机器可读申报:entry 消费位对返回值零使用(源级守卫:
        调用行为表达式语句,无赋值消费)。"""
        import inspect
        import re
        src = inspect.getsource(entry)
        call_lines = [ln for ln in src.splitlines()
                      if 'evaluate_evidence_gate' in ln
                      and not ln.strip().startswith('#')]
        assert call_lines, 'entry 影子评估调用行缺位(守卫移除)'
        for ln in call_lines:
            assert not re.match(r'\s*\w+\s*=\s*.*evaluate_evidence_gate', ln), \
                f'返回值被消费,违背影子面申报:{ln}'


# ===== ⑤ 守卫移除验证(entry 调用位;摘行必红)=====

class TestWiringGuard:

    def test_emit_invokes_shadow_evaluation(self):
        """入口 emit 后 evidence_gate_evaluated ≥ 1(摘 entry 调用行即红;
        harness 形态 = test_cw_mandate_decide 入口 smoke 同款轻桩)。"""
        from sr_od.application.currency_war.decision_assembly import (
            snapshot_from_obs,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
            assemble as assemble_turn,
        )
        from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
            MandateV1Strategy,
        )
        strat = MandateV1Strategy()
        sess = _session()
        st = CwWorkFrame(gold=30, level=7, round_num=3, plane=1,
                       board={}, shop=[])
        # obs.state 视图槽已退役(容器化段 2):局内事实经容器喂入单一源
        # 进 session 容器,emit 决策面走容器读口。
        cw4_feed(sess, st)
        obs = PrepObservation(bench_chars=[], deployed_chars=[],
                              spheres=[], boxes=[], tomes=[], deploy_vacancy=4)
        sess.prep_obs_frame = obs
        turn = assemble_turn(snapshot_from_obs(obs, sess), sess,
                             registry=strat.registry)
        entry.emit(obs, turn, sess, None, ev_arm='full',
                   registry=strat.registry)
        assert _counters(sess).get('evidence_gate_evaluated', 0) >= 1
