"""CW 委任决策(mandate decide)真值测试(#6):四硬约束检查点 / 换线
(swap)决策 / boss 硬节点释放 / 供给(supply)/ 刷新(refresh)/
事件轴 每真实分支 1 代表行。

收缩注记(CUT9 二次收缩:原 20 测试→10 测试;同分支变体砍,git 可复活):
- decide 门四硬约束留 affordable(金钱门)/s_reserve 两代表,
  seats/irreversible 同拦截集分支变体砍;
- swap 正例 + θ 缺失 fail-closed 双向全留;boss D-B 三态门全留;
- 发射契约 fail-closed + 入口 smoke 全留;M2→M4 行为真值留;
- supply 留带钻碾压 1 代表,encounter 留全克刷新换批 1 代表(refresh
  分支锚);supply 无钻刷新/key 契合/通用价值、encounter 刷新已用/
  未成型低难/成型利高难、事件轴 strategy_forbid/env 两行砍。

覆盖面:
- decide 门:affordable / s_reserve 各一例(§3.2 唯一合法拦截集);
- swap(换线):should_switch 换线活正例(R196 症1 接线修活,事故背书)
  + θ/D_min/δ 缺失 fail-closed(theta_unavailable 分键,禁复用旧键);
- boss/硬节点:D-B 三态门(简易件即穿/里程碑收窄/boss 强敌节点释放);
- 发射契约:词表外动作截断+计数披露(fail-closed,禁静默丢弃)+
  _emit 全链冒烟(探针语料,契约符合性 = 本域入口 smoke);
- 行为真值:M2→M4 腾席重试环(单帧闭环 swap-out-and-buy);
- 供给 decide_supply 带钻分支 + 遭遇 decide_encounter 全克刷新分支
  各 1 代表行。

来源:mandate_v1(mv 主干,保留代表行)/ decisions 核之 decide 真值族
(economy 真值两行已归 #4;2026-09-09 套件重建批 A,#6;CUT9 二次收缩
见收缩注记)。其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_line_switch
from sr_od.application.currency_war.kernel.cw_comps import COMP_LIBRARY, Comp
from sr_od.application.currency_war.kernel.cw_events import (
    EncounterOption,
    SupplyOption,
    decide_encounter,
    decide_supply,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    LevelUp,
    PrepAction,
    PrepObservation,
    SellBench,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.decision_assembly import snapshot_from_obs
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
    mandate,
    proof,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble as assemble_turn,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    equipment as crit_equip,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

# ===== 测试基建(自 mandate_v1 原样保留)=====

def _bench(slot: int, name: str, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


class _Pt:
    """探针点(spheres/boxes/tomes 元素坐标载体;snapshot_from_obs 消费)。"""

    def __init__(self, x: int = 100, y: int = 100) -> None:
        self.x, self.y = x, y


def _frame(gold: int = 20, bench=None, deployed=None, cap: int = 4,
           node=None, stop: bool = False, k=(), level: int = 3,
           round_num: int = 3) -> mandate.MandateFrame:
    return mandate.MandateFrame(
        gold=gold, level=level, bench=bench or [], deployed=deployed or [],
        deploy_cap=cap, node_type=node, stop_flag=stop, k_members=k,
        round_num=round_num)


def _session() -> StrategySession:
    s = StrategySession()
    state_of(s).cw4_counters = {}
    return s


def _obs(state: GameState | None = None, bench=None, deployed=None,
         spheres=(), boxes=(), tomes=(), vacancy: int = 4) -> PrepObservation:
    return PrepObservation(
        state=state or GameState(gold=20),
        bench_chars=bench or [], deployed_chars=deployed or [],
        spheres=list(spheres), boxes=list(boxes), tomes=list(tomes),
        deploy_vacancy=vacancy)


# ===== ① decide 门:四硬约束检查点(§3.2 唯一合法拦截集)=====

class TestHardConstraints:

    def test_checkpoint1_affordable(self):
        ok, why = mandate.check_affordable(3, 5)
        assert not ok and 'gold' in why
        ok, _ = mandate.check_affordable(5, 5)
        assert ok
        # 整批成本按 M3 批量合计
        ok, _ = mandate.check_affordable(9, 0, batch_cost=12)
        assert not ok

    def test_checkpoint3_s_reserve(self):
        # 10−4=6 ≥5 ⇒ 过;10−4=6 <7 ⇒ 拦(检查点③辖 EV 买入面+M6+dominance)
        ok, _ = mandate.check_s_reserve(10, 4, s_reserve=5)
        assert ok
        ok, _ = mandate.check_s_reserve(10, 4, s_reserve=7)
        assert not ok


# ===== ② swap(换线)决策真值:正例 + fail-closed =====


class TestSwapDecide:
    """换线 should_switch 代表行(R196 修复批承继;其余回锁窗/冲突
    丢弃/影子键行退役 git 可复活)。"""

    def setup_method(self):
        provisional.reset()

    def teardown_method(self):
        provisional.reset()

    def test_theta_none_no_evaluation_with_split_key(self):
        """θ/D_min/δ 任一 None ⇒ should_switch 不评估 + theta_unavailable
        分键(R24-2:禁复用 switchline_skipped / switchline_exit_blocked)。"""
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        out = proof.should_switch(GameState(gold=20), session, None, None)
        assert not out.event
        assert out.key == 'theta_unavailable'
        assert 'theta_unavailable' in state_of(session).cw4_counters
        assert 'switchline_skipped' not in state_of(session).cw4_counters
        assert 'switchline_exit_blocked' not in state_of(session).cw4_counters

    def test_should_switch_event_with_alt_supply(self, monkeypatch):
        """换线活:参数齐备 + 候选更优 ⇒ 事件真 + alt_comp 非空(entry 不再
        构造性恒 no_op)。"""
        provisional.inject('THETA', provisional.CalibValue(1.0))
        provisional.inject('D_MIN', provisional.CalibValue(2))
        provisional.inject('DELTA_HYST', provisional.CalibValue(0.15))
        provisional.inject('U_X', provisional.CalibValue(1.0))
        provisional.inject('V_MS', provisional.CalibValue(1.0))
        comps = [c for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
        session = _session()
        state_of(session).target_comp = comps[0]
        for _ in range(3):
            proof.update_line_state(session, comps[0], [], [])   # dwell=2 ≥ D_min

        def _fake_e(comp, state, registry=None, session=None):
            return 20.0 if comp.name == comps[0].name else 1.0
        monkeypatch.setattr(cw_line_switch, 'e_rounds', _fake_e)
        out = proof.should_switch(GameState(gold=30), session, None, None)
        assert out.event and out.alt_comp is not None
        assert out.alt_comp.name != comps[0].name


# ===== ③ boss/硬节点决策真值:D-B 三态门 =====


class TestBossNodeRelease:

    def test_d_b_wear_release_three_states(self):
        """D-B 三态门:简易件即穿/里程碑收窄释放/强敌节点释放。"""
        ok, why = crit_equip.wear_release(False, None, simple_item=True)
        assert ok and why == 'simple_item'
        ok, why = crit_equip.wear_release(True, None, simple_item=False)
        assert ok and why == 'opening_achieved'
        ok, why = crit_equip.wear_release(False, 'boss', simple_item=False)
        assert ok and why == 'hard_node'


# ===== ④ 发射契约:fail-closed + 入口 smoke =====


class TestEmitterContract:

    def test_section_3_3_fail_closed_unknown(self):
        """词表外动作:截断+计数披露(禁静默丢弃)。"""
        class Rogue(PrepAction):
            pass

        session = _session()
        out = entry.truncate_frame_stable(
            [LevelUp(), Rogue(), LevelUp()], session)
        assert [type(a) for a in out] == [LevelUp]
        assert state_of(session).cw4_counters['emitter_unknown_action_truncated'] == 1

    def _run_emit_raw(self, ev_arm: str) -> list:
        strat = MandateV1Strategy()
        session = _session()
        state_of(session).target_comp = COMP_LIBRARY[0]
        cases = [
            _obs(bench=[_bench(1, '燃料件')]),
            _obs(bench=[_bench(i, '燃料' + str(i)) for i in range(1, 10)],
                 vacancy=0),
            _obs(state=GameState(gold=99), bench=[_bench(1, '目标件')],
                 vacancy=0),
            _obs(spheres=[('red', _Pt(), 3)]),
            _obs(boxes=[(2, _Pt())]),
            _obs(),
        ]
        outs = []
        for obs in cases:
            session.prep_obs_frame = obs
            turn = assemble_turn(
                snapshot_from_obs(obs, session), session,
                registry=strat.registry)
            outs.append(entry.emit(obs, turn, session, None, ev_arm=ev_arm,
                                   registry=strat.registry))
        return outs

    def test_emit_full_no_exception_and_contract_conform(self):
        """入口 smoke:探针语料跑 _emit 全链无异常 + 截断判符合契约
        (截断点/终点必在末位,零 unknown 判型)。"""
        outs = self._run_emit_raw('full')
        trunc_session = _session()
        for emitted in outs:
            actions = entry.truncate_frame_stable(
                [e.action for e in emitted], trunc_session)
            assert isinstance(actions, list)
            for a in actions:
                assert isinstance(a, PrepAction)
            # 截断判符合 v2:若含截断点/终点,必在末位
            for i, a in enumerate(actions):
                kind = entry.classify_frame_stability(a)
                assert kind != 'unknown'
                if kind in ('truncation', 'terminal'):
                    assert i == len(actions) - 1


# ===== ⑤ 行为真值:M2→M4 腾席重试环(swap-out-and-buy 单帧闭环)=====


class TestMandateBehavior:

    def test_m2_m4_retry_frees_seat(self):
        """M2→M4 重试环:bench 满 ∧ 线内缺件 ⇒ 现场腾席(燃料件卖出)
        后再买(R8-8 单帧闭环)。发射载体 reason 归因面已随 2026-09-08
        用户归因遥测删除指令拆除(缺省 '' 未标;腾席卖出发射行为由
        PrepSellBench 判型断言承载)。"""
        k = ('目标件',)
        bench = [_bench(i, '燃料' + str(i)) for i in range(1, 10)]
        frame = _frame(gold=30, bench=bench, k=k)
        session = _session()
        out = mandate.run_mandate(frame, session)
        reasons = [e.reason for e in out]
        assert any(isinstance(e.action, SellBench) for e in out), \
            '腾席卖出发射缺席'
        assert 'm2_buy' in reasons
        # 席满无燃料可腾(全 3★)⇒ 放弃:耗竭帧零买入意图
        #(m2_retry_exhausted / bench_full_buy_abandon 计数由
        # test_cw_stall_cache.TestPrepStallCache 同帧形 ==1 强断言辖)
        bench2 = [_bench(i, '高价', star=3) for i in range(1, 10)]
        out2 = mandate.run_mandate(_frame(gold=30, bench=bench2, k=k),
                                   _session())
        assert not any(e.reason == 'm2_buy' for e in out2)


# ===== ⑥ decide_supply / decide_encounter 真值(自 test_cw_decisions 并入)=====

def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,决策函数用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _mcomp(attrs: list[str]) -> Comp:
    """构造测试 comp(控 mechanic_attributes,验 mechanics_fit 克/利)。"""
    return Comp(name="t", factions=["燃血"], core_chars=[], form_tiers={"燃血": 4},
                strength="A", form_difficulty="medium", mechanic_attributes=attrs)


def _comp_key(key_equips: list[str]) -> Comp:
    """构造测试 comp(控 key_equips,验 decide_supply key 契合)。"""
    return Comp(name="t", factions=[], core_chars=[], form_tiers={},
                strength="A", form_difficulty="medium", key_equips=key_equips)


def test_decide_encounter_refresh_when_all_counter() -> None:
    """全分支词缀都克 comp + 刷新未用 → 刷新换批(避开高危)。"""
    cfg = _cfg()
    comp = _mcomp(["速度依赖"])  # 忽快忽慢→速度抑制 counter(克)
    opts = [EncounterOption(idx=0, difficulty=1, affixes=["忽快忽慢"]),
            EncounterOption(idx=1, difficulty=2, affixes=["忽快忽慢"])]
    pick = decide_encounter(opts, GameState(), comp, cfg, refresh_used=False)
    assert pick.refresh, "全分支克 comp 应刷新换批"


def test_decide_supply_diamond_first() -> None:
    """带钻选项 → 选它(碾压装备价值)。"""
    cfg = _cfg()
    opts = [SupplyOption(idx=0, equip="反重力皮靴"),                 # 高价值但无钻
            SupplyOption(idx=1, equip="光能电池", has_diamond=True)]  # 带钻
    pick = decide_supply(opts, GameState(), _comp_key([]), cfg)
    assert pick.idx == 1, "带钻应优先选"
    assert not pick.refresh
