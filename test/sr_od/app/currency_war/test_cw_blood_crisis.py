"""test_cw_blood_crisis 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- adr0302_crisis_fixes: test_cw_adr0302_crisis_fixes.py
- blood_alarm_threshold_backing: test_cw_blood_alarm_threshold_backing.py
- blood_budget_stop: test_cw_blood_budget_stop.py
- blood_budget_wave2: test_cw_blood_budget_wave2.py
- c1_directed_spend: test_cw_c1_directed_spend.py
- w403_hp_down_guard: test_cw_w403_hp_down_guard.py
- w823_hp_none: test_cw_w823_hp_none.py
- w917_crisis_release: test_cw_w917_crisis_release.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations

# ==================== adr0302_crisis_fixes ====================
from types import SimpleNamespace

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    crisis_hoard_active,
    filter_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import score_candidate
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.sim.checks.decision_v2 import (
    check_decision_v2_crisis_gold_hoard,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟罗浮', cost: int = 1) -> object:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 8, 'gold': 72, 'level': 6,
            'board': {'公司': 6},
            'deployed': [_bench(f'板件{i}', faction='公司', slot=i)
                         for i in range(6)],
            'bench': [], 'shop': [], 'hp': 20}
    base.update(kw)
    return GameState(**base)


# --- ① 危机囤金买偏置 --------------------------------------------------------


def _formed_state(**kw) -> GameState:
    """已成型板(引擎 2:仙舟3+持续伤害2;藿藿不在板)→ 成型补充偏置
    (ADR-0332)不触发——危机偏置加性锁的双态隔离板(店藿藿=桥 core
    非副本,双态唯一差异=危机偏置)。"""
    base = {'plane': 1, 'round_num': 8, 'gold': 72, 'level': 6,
            'board': {'仙舟': 3, '持续伤害': 2, '公司': 1},
            'deployed': [_bench('爻光', faction='仙舟', slot=0),
                         _bench('符玄', faction='仙舟', slot=1),
                         _bench('停云', faction='仙舟', slot=2),
                         _bench('卡芙卡', faction='星核猎手', slot=3),
                         _bench('黑天鹅', faction='盛会之星', slot=4),
                         _bench('板件5', faction='公司', slot=5)],
            'bench': [], 'shop': [], 'hp': 20}
    base.update(kw)
    return GameState(**base)


def test_crisis_buy_bias_additive() -> None:
    """危机态战力买加分:hp 20 vs 40 同板差分恰=_CRISIS_BUY_BIAS
    (score_state 无 hp 项,双态唯一差异=偏置;板已成型→ADR-0332 成型
    偏置双态均不触发);且危机态分>0。"""
    sess = _sess()
    st_crisis = _formed_state(shop=[_card('藿藿')])     # hp=20 金=72
    st_ok = _formed_state(hp=40, shop=[_card('藿藿')])  # 非应急同板
    v = {}
    for key, st in (('crisis', st_crisis), ('ok', st_ok)):
        cands = [c for c in generate_candidates(st, sess, _REG)
                 if c.action.__class__.__name__ == 'BuyCard'
                 and c.action.card.name == '藿藿']
        assert cands, '桥 core 件(无方向)应生成买候选'
        v[key], _ = score_candidate(cands[0], st, sess, _REG)
    assert v['crisis'] - v['ok'] == _REG.crisis_buy_bias, v
    assert v['crisis'] > 0, '危机囤金态战力买应可执行(>0)'


def test_crisis_hoard_gold_gate() -> None:
    """囤金金线:金≥_CRISIS_HOARD_GOLD 才进危机囤金态;金 39 同应急
    hp 不触发(偏置/搜牌解锁都不生效)。"""
    assert crisis_hoard_active(
        _state(gold=_REG.crisis_hoard_gold), _REG)
    assert not crisis_hoard_active(
        _state(gold=_REG.crisis_hoard_gold - 1), _REG)
    assert not crisis_hoard_active(_state(hp=40), _REG)  # 非应急


def test_crisis_buy_bias_does_not_cross_interest_cliff() -> None:
    """息崖保持:金 52 买 3 费(52→49 跌破满息平台,息 EV −25)
    即使危机偏置在也恒负分——[18]「不为苟住破息」。"""
    sess = _sess()
    st = _state(gold=52, shop=[_card('藿藿', cost=3)])
    cands = [c for c in generate_candidates(st, sess, _REG)
             if c.action.__class__.__name__ == 'BuyCard']
    assert cands
    val, _ = score_candidate(cands[0], st, sess, _REG)
    assert val < 0, f'息崖下危机买应负分(实际 {val})'


# --- ② 危机搜牌 --------------------------------------------------------------


def test_crisis_refresh_unlocked_in_hoard_state() -> None:
    """危机囤金态:refresh 层2 放行(候选在场);**评分=V_D 同公式**
    (W126/ADR-0349 E7 应急 D 变现 EV 化——同一本账,不是另一个门:
    危机态锁定核心在概率窗内 → V_D 正分照常点火,无目标语境恒负分);
    金<40 应急态 refresh 仍滤出。"""
    sess = _sess()
    st = _state()          # hp20 金72 r8:危机囤金态(裸 session,无目标)
    cands = generate_candidates(st, sess, _REG)
    kept, flog = filter_candidates(cands, st, sess, _REG)
    assert any(c.tag == 'refresh' for c in kept), '危机囤金态应放行搜牌'
    rc = next(c for c in cands if c.tag == 'refresh')
    val, _ = score_candidate(rc, st, sess, _REG)
    assert val < 0, '危机态无目标语境:V_D 同账判负(恒不无证刷)'
    # 危机 + 锁定核心在概率窗内 → V_D 正分(变现通道活跃)
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    sess2 = _sess()
    sess2.v3_intention = IntentionState(phase='locked',
                                        locked_comp='DOT队')
    sess2.target_comp = get_comp('DOT队')
    st2 = _state(level=8, bench=[_bench('卡芙卡', faction='公司',
                                        slot=0),
                                 _bench('卡芙卡', faction='公司',
                                        slot=1)],
                 deployed=[_bench(f'板件{i}', faction='公司', slot=9 + i)
                           for i in range(6)])
    rc2 = [c for c in generate_candidates(st2, sess2, _REG)
           if c.tag == 'refresh'][0]
    val2, _ = score_candidate(rc2, st2, sess2, _REG)
    assert val2 > 0, f'危机+核心在窗:L8 卡芙卡 roll 窗 V_D 应正分(实际 {val2})'
    # 非囤金应急态(金 30):refresh 滤出
    st3 = _state(gold=30)
    kept3, _f = filter_candidates(generate_candidates(st3, sess, _REG),
                                  st3, sess, _REG)
    assert not any(c.tag == 'refresh' for c in kept3)


# --- ③ 应急集内容 ------------------------------------------------------------


def test_emergency_set_content() -> None:
    """应急集=战力买+卖弱件+升级(+危机囤金态的 refresh);
    经济类候选(pair/copy/bond_fallback/synthesize)滤出。"""
    sess = _sess()
    st = _state(gold=30, bench=[_bench('散件甲', faction='公司')],
                shop=[_card('藿藿'),
                      _card('凑档件', faction='公司', cost=1)])
    cands = generate_candidates(st, sess, _REG)
    kept, flog = filter_candidates(cands, st, sess, _REG)
    kept_tags = {c.tag for c in kept}
    assert {'bridge_core', 'for_gold', 'levelup'} <= kept_tags, kept_tags
    rejected = {e['tag'] for e in flog if not e['kept']}
    # 凑档件被 pair 通道接管(ADR-0300 标签序)——两标签都在应急滤出域
    assert {'refresh', 'pair'} <= rejected, rejected
    assert flog[0]['level'] == 'emergency'


# --- ④ 端到端:检查项 5→0 -----------------------------------------------------


def test_crisis_gold_hoard_check_zero_violations() -> None:
    """批㉝ F3 五危机局(s1/s25/s75/s79;s52 非危机对照)修复后
    decision_v2_crisis_gold_hoard 违规=0(修复前 5/100)。"""
    strat = DecisionV2Strategy()
    ledgers = [simulate_p1(sd, pool='fallback', strategy=strat).ledger
               for sd in (1, 25, 52, 75, 79)]
    chk = check_decision_v2_crisis_gold_hoard(ledgers)
    assert chk['violations'] == 0, chk['detail']


# ==================== blood_alarm_threshold_backing ====================

from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession as _blood_alarm_threshold_backing_StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    BLOOD_MARGIN_LOW_HP,
    BloodAlarmTracker,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _blood_alarm_threshold_backing_DEFAULT_REGISTRY,
)

_blood_alarm_threshold_backing_REG = _blood_alarm_threshold_backing_DEFAULT_REGISTRY


def _lc(rung: int) -> float:
    """P15 条件败局伤害期望(单一源=registry 拟合常数)。"""
    return (_blood_alarm_threshold_backing_REG.vd_p1_loss_intercept
            + _blood_alarm_threshold_backing_REG.vd_p1_loss_slope_rung * rung)


def test_emergency_hp_in_two_loss_buffer_band() -> None:
    """emergency_hp ∈ (2×L_c(rung2), rebirth_floor+L_c(rung2)):
    能吸收两次满额条件败局、且一次败局后仍可保住重生基数。"""
    lc2 = _lc(2)
    assert _blood_alarm_threshold_backing_REG.emergency_hp > 2 * lc2, \
        f'应急线({_blood_alarm_threshold_backing_REG.emergency_hp})须高于双失吸收上界 {2 * lc2:.1f}'
    assert _blood_alarm_threshold_backing_REG.emergency_hp < _blood_alarm_threshold_backing_REG.rebirth_floor + lc2, \
        (f'应急线({_blood_alarm_threshold_backing_REG.emergency_hp})须低于一次败局即破重生基数上界 '
         f'{_blood_alarm_threshold_backing_REG.rebirth_floor + lc2:.1f}')


def test_single_loss_line_at_conditional_loss_magnitude() -> None:
    """单场打输线 10 ∈ [L_c(rung4), L_c(rung0)] 且 ≥L_c(rung8):
    阈值落在条件败局期望的 rung 全域代表带内——达到该量级=结构性
    打输;低于它的败局(敌血近清空小伤害)作波动。"""
    assert _lc(8) <= 10 <= _lc(0)
    # L_c(4)=9.84 → 取整代表值容差:10 与中点差 <1
    assert abs(10 - _lc(4)) < 1.0


def test_cumulative_arms_are_loss_count_multiples() -> None:
    """②20/③30 = L_c(rung2) 的 2/3 倍取整(≤ 对应倍数、> 降一档):
    语义=窗内满额败局次数下限,而非任意魔数。"""
    lc2 = _lc(2)
    assert 2 * lc2 - 2 < 20 <= 2 * lc2      # 20 ≈ 2×10.58=21.2,取整容差 2
    assert 3 * lc2 - 2 < 30 <= 3 * lc2      # 30 ≈ 3×10.58=31.7


def test_arm1_two_consecutive_full_losses_trigger() -> None:
    """臂①:连续两场 ≥10 的满额败局 → 报警;单场不触发;
    连续两场 9(低于单场线)不触发——锁单场线的截断语义。"""
    t = BloodAlarmTracker()
    t.record('battle', 100, 89, t=1, plane=1)   # -11 ≥10
    assert not t.alarm_active()
    t.record('battle', 89, 78, t=2, plane=1)    # -11,连续第 2 场
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    t2.record('battle', 100, 92, t=1, plane=1)  # -8 <10(小伤害波动)
    t2.record('battle', 92, 84, t=2, plane=1)   # -8,连续但未达线
    assert not t2.alarm_active()


def test_arm2_three_battle_window_two_losses_equivalent() -> None:
    """臂②:3 个战斗节点累计 ≥20(≈2×L_c)触发——容 1 个良性节点
    的急性账;累计 18(两次小伤害败局)不触发。"""
    t = BloodAlarmTracker()
    t.record('battle', 100, 93, t=1, plane=1)   # -7
    t.record('battle', 93, 79, t=2, plane=1)    # -14
    t.record('battle', 79, 72, t=3, plane=1)    # -7,累计 28 ≥20
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    for i in range(3):
        t2.record('battle', 100 - 6 * i, 94 - 6 * i, t=i + 1, plane=1)
    assert sum(l for _t, l in t2.recent_losses) == 18
    assert not t2.alarm_active()


def test_arm3_five_battle_window_chronic_drift() -> None:
    """臂③:5 个战斗节点累计 ≥30(≈3×L_c)触发慢性漂移臂;
    窗口滚动——第 5 个节点喂入时含第 1 个节点的掉血。"""
    t = BloodAlarmTracker()
    losses = [6, 6, 6, 6, 6]   # 累计 30,无单场 ≥10、无 3 窗 ≥20
    hp = 100
    for i, l in enumerate(losses):
        t.record('battle', hp, hp - l, t=i + 1, plane=1)
        hp -= l
    assert t.alarm_active()

    t2 = BloodAlarmTracker()
    hp = 100
    for i, l in enumerate([5, 5, 5, 5, 5]):    # 累计 25 <30
        t2.record('battle', hp, hp - l, t=i + 1, plane=1)
        hp -= l
    assert not t2.alarm_active()


def test_25_40_gradient_semantics_unchanged() -> None:
    """两线并存梯度不因背书替换漂移:40=报警降档(discipline),
    25=应急覆盖态(registry),40>25 维持处置梯度。"""
    assert BLOOD_MARGIN_LOW_HP == 40
    assert _blood_alarm_threshold_backing_REG.emergency_hp == 25
    assert _blood_alarm_threshold_backing_REG.emergency_hp < BLOOD_MARGIN_LOW_HP


def _unused_session_guard() -> None:  # pragma: no cover
    # _blood_alarm_threshold_backing_StrategySession 导入保留:后续行为锁若需 session 挂载(v3_alarm)
    # 沿用同一构造口径;本文件当前锁常量与 tracker 行为,无需实例。
    _ = _blood_alarm_threshold_backing_StrategySession


# ==================== blood_budget_stop ====================

import dataclasses
import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession as _blood_budget_stop_StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _check_constraint,
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    blood_budget_levelup_blocked,
    p1_levelup_stop_hp,
    p2_levelup_stop_hp,
)
from sr_od.application.currency_war.decision.decision_v2.remediation import (
    steady_state_levelup_group,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _blood_budget_stop_DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _blood_budget_stop_BenchChar,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _blood_budget_stop_GameState,
)
from sr_od.application.currency_war.kernel.cw_state import LevelUp
from sr_od.application.currency_war.sim.checks.segments import (
    _P1_LEVELUP_STOP_HP,
    _P2_LEVELUP_STOP_HP,
    seg_check_p1_blood_budget_levelup,
    seg_check_p2_blood_budget_levelup,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)



def _p2_state(hp: int = 16, round_num: int = 3, node: str = 'battle',
              gold: int = 100) -> _blood_budget_stop_GameState:
    """P2 备战帧(⑳+1 型:hp 危机段;默认 hp=16<21 追级泵病灶态)。"""
    st = _blood_budget_stop_GameState()
    st.plane, st.level, st.gold, st.hp = 2, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _lv_cand() -> Candidate:
    return Candidate(action=LevelUp(cost=4), tag='levelup', source='shop')


def _allin_sess() -> _blood_budget_stop_StrategySession:
    """带 P2 槽序表(7 槽)的 session——plane_last_battle 真值源。"""
    s = _blood_budget_stop_StrategySession()
    s.plane_node_table = ['battle'] * 7
    return s


# ---------- 停线数值:单一源推导 + 镜像双向锁 ----------

def test_stop_lines_derive_from_registry() -> None:
    """P2=ceil(1×20.05)=21 / P1=ceil(1×10.58)=11(设计件 12 §6);
    cw_sim_checks 镜像常量 ↔ discipline 单一源双向锁(漂移即红)。"""
    assert p2_levelup_stop_hp(_blood_budget_stop_DEFAULT_REGISTRY) == 21
    assert p1_levelup_stop_hp(_blood_budget_stop_DEFAULT_REGISTRY) == 11
    assert p2_levelup_stop_hp(_blood_budget_stop_DEFAULT_REGISTRY) == _P2_LEVELUP_STOP_HP
    assert p1_levelup_stop_hp(_blood_budget_stop_DEFAULT_REGISTRY) == _P1_LEVELUP_STOP_HP


# ---------- 谓词辖域 ----------

def test_predicate_domain() -> None:
    """线内拒/线外放:P2 hp21 拒、hp22 放;P1 hp11 拒、hp12 放。"""
    sess = _blood_budget_stop_StrategySession()
    assert blood_budget_levelup_blocked(_p2_state(hp=21), sess,
                                        _blood_budget_stop_DEFAULT_REGISTRY)
    assert not blood_budget_levelup_blocked(_p2_state(hp=22), sess,
                                            _blood_budget_stop_DEFAULT_REGISTRY)
    p1 = _p2_state(hp=11)
    p1.plane = 1
    assert blood_budget_levelup_blocked(p1, sess, _blood_budget_stop_DEFAULT_REGISTRY)
    p1_ok = _p2_state(hp=12)
    p1_ok.plane = 1
    assert not blood_budget_levelup_blocked(p1_ok, sess, _blood_budget_stop_DEFAULT_REGISTRY)


def test_predicate_allin_exempt_counterexample() -> None:
    """ALL IN 豁免反例:P2 r7 boss 帧 hp=16(<21)不停手(位面末
    ALL IN 清零窗,停手让位;[18])。同帧非位面末(r3 boss 窗)照拒。"""
    allin = _p2_state(hp=16, round_num=7, node='boss')
    assert blood_budget_levelup_blocked(allin, _allin_sess(),
                                        _blood_budget_stop_DEFAULT_REGISTRY) is False
    not_last = _p2_state(hp=16, round_num=3, node='boss')
    assert blood_budget_levelup_blocked(not_last, _allin_sess(),
                                        _blood_budget_stop_DEFAULT_REGISTRY)


def test_predicate_flag_off_zero_scope() -> None:
    """开关 off=A/B 对照臂:同帧不辖(A/B 基线臂注入面)。"""
    reg_off = dataclasses.replace(_blood_budget_stop_DEFAULT_REGISTRY,
                                  blood_budget_stop_enabled=False)
    assert not blood_budget_levelup_blocked(_p2_state(hp=16),
                                            _blood_budget_stop_StrategySession(), reg_off)


def test_terminal_frame_still_blocks_levelup() -> None:
    """终止帧仍拒升级(设计 W659 v2 §3.2/§5.1 改判对照用例;ADR-0469):
    终止分支只释放刷新停付与末窗降格两门,停升级门**不在豁免辖内**——
    P21 数学(濒死升级 EV=−C−I 严格为负)与金是否零价值无关;防「释放
    扩散」回归的对照锚。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        terminal_release,
    )
    sess = _blood_budget_stop_StrategySession()
    sess.plane_node_table = ['battle'] * 9
    st = _p2_state(hp=10)
    st.plane = 1
    assert terminal_release(st, sess, _blood_budget_stop_DEFAULT_REGISTRY)
    assert blood_budget_levelup_blocked(st, sess, _blood_budget_stop_DEFAULT_REGISTRY)


# ---------- 接线:约束拒付 / 稳态组 / 计数披露 ----------

def test_constraint_rejects_with_reason_and_counter() -> None:
    """arbiter 约束拒付:RejectReason 带血预算停手原因 + session 计数+1。"""
    sess = _blood_budget_stop_StrategySession()
    st = _p2_state(hp=16)
    r = _check_constraint('blood_budget_stop', _lv_cand(), st, st, sess,
                          _blood_budget_stop_DEFAULT_REGISTRY)
    assert r is not None and '血预算停手拒' in r.describe
    assert sess.v3_blood_budget_rejects == 1
    # 线外帧:本约束放行(None=交给后续约束链)
    sess2 = _blood_budget_stop_StrategySession()
    assert _check_constraint('blood_budget_stop', _lv_cand(),
                             _p2_state(hp=30), _p2_state(hp=30), sess2,
                             _blood_budget_stop_DEFAULT_REGISTRY) is None
    assert sess2.v3_blood_budget_rejects == 0


def test_arbitrate_end_to_end_no_levelup_in_stop_band() -> None:
    """端到端:血线内帧的升级候选不产 LevelUp 动作(ALL IN 外)。"""
    sess = _blood_budget_stop_StrategySession()
    st = _p2_state(hp=16)
    res = arbitrate([(_lv_cand(), 5.0, {})], st, sess, _blood_budget_stop_DEFAULT_REGISTRY)
    assert not [a for a in res.actions
                if isinstance(a, LevelUp)]
    assert any('blood_budget_stop' in (row.get('reject') or '')
               for row in res.log)


def test_steady_group_blocked_in_stop_band() -> None:
    """稳态多击组整组拒发 + 拒付计数(⑳+1「血线 16 追级泵 6 次」
    的形态反转:同帧稳态组=0 组)。"""
    sess = _blood_budget_stop_StrategySession()
    st = _p2_state(hp=16)
    st.deployed = [_blood_budget_stop_BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                   for i in range(6)]
    st.bench[0] = _blood_budget_stop_BenchChar(slot=1, char_id='希儿', faction='量子')
    st.xp_progress = (16, 40)
    assert steady_state_levelup_group(st.copy(), st, sess,
                                      _blood_budget_stop_DEFAULT_REGISTRY) == []
    assert sess.v3_blood_budget_rejects == 1
    # ALL IN 窗豁免:同构造在 r7 boss 帧照发(豁免面)
    sess2 = _allin_sess()
    st2 = _p2_state(hp=16, round_num=7, node='boss')
    st2.deployed = [_blood_budget_stop_BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                    for i in range(6)]
    st2.bench[0] = _blood_budget_stop_BenchChar(slot=1, char_id='希儿', faction='量子')
    st2.xp_progress = (16, 40)
    acts = steady_state_levelup_group(st2.copy(), st2, sess2,
                                      _blood_budget_stop_DEFAULT_REGISTRY)
    assert len(acts) == 6
    assert sess2.v3_blood_budget_rejects == 0


# ---------- 段级检查 ----------

def _row(plane: int, hp: int, rn: int, node: str,
         levelups: int) -> dict:
    return {
        'plane': plane, 'round_num': rn, 'hp': hp,
        'sim': {'node': node},
        'actions': ([{'__type__': 'LevelUp', 'cost': 4}] * levelups),
    }


def test_seg_checks_violation_and_allin_exempt() -> None:
    """违规帧出事件;ALL IN 豁免帧与线外帧不出(反例内嵌)。

    hp 口径=决策帧(=上一行结算 hp):违规行的**前一行** hp 在线内。"""
    rows_p2 = [
        _row(2, 35, 1, 'battle', 0),    # 局首:决策 hp=开局,不出事件
        _row(2, 18, 2, 'battle', 2),    # 决策 hp=35(线外)→ 不出
        _row(2, 10, 3, 'battle', 1),    # 决策 hp=18≤21 → 违规事件
        _row(2, 5, 7, 'boss', 6),       # 决策 hp=10 但 ALL IN 帧 → 豁免
        _row(2, 30, 8, 'battle', 0),    # 无升级:不出事件
    ]
    ev = seg_check_p2_blood_budget_levelup(rows_p2)
    assert len(ev) == 1 and ev[0]['round_num'] == 3 and ev[0]['hp'] == 18
    rows_p1 = [
        _row(1, 12, 4, 'battle', 0),
        _row(1, 10, 5, 'battle', 1),    # 决策 hp=12(线外)→ 不出
        _row(1, 9, 6, 'battle', 1),     # 决策 hp=10≤11 → 违规事件
        _row(1, 8, 7, 'battle', 0),     # 无升级
        _row(1, 7, 9, 'boss', 2),       # ALL IN 豁免(P1 r9)
    ]
    ev1 = seg_check_p1_blood_budget_levelup(rows_p1)
    assert len(ev1) == 1 and ev1[0]['plane'] == 1 and ev1[0]['hp'] == 10


# ---------- sim 账本披露键(单局冒烟,不锁分布) ----------

# (≤2 层收敛,sim 台账披露键测试已删:键语义由 predicate+arbiter 两层承载;
#  批量聚合侧由 sim_suite 段检查覆盖)


# ==================== blood_budget_wave2 ====================

import dataclasses as _blood_budget_wave2_dataclasses
import logging as _blood_budget_wave2_logging

import pytest as _blood_budget_wave2_pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession as _blood_budget_wave2_StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2 import candidates as cands_mod
from sr_od.application.currency_war.decision.decision_v2 import handoff as handoff_mod
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    arbitrate as _blood_budget_wave2_arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate as _blood_budget_wave2_Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import _buy_tag
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    blood_budget_refresh_blocked,
    p1_directed_downgrade_active,
    p1_exit_blood_short,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _blood_budget_wave2_DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _blood_budget_wave2_BenchChar,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _blood_budget_wave2_GameState,
)
from sr_od.application.currency_war.kernel.cw_state import RefreshShop, ShopCard
from sr_od.application.currency_war.sim.checks.segments import (
    _P1_EMERGENCY_HP,
    _P1_EXIT_BLOOD_TARGET,
    _P1_HANDOFF_GATE_MIN_ROUND,
    seg_check_p1_blood_budget_refresh,
)


@_blood_budget_wave2_pytest.fixture(autouse=True)
def _blood_budget_wave2_quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 _blood_budget_wave2_logging.disable 是全局态:_blood_budget_wave2_pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = _blood_budget_wave2_logging.root.manager.disable
    _blood_budget_wave2_logging.disable(_blood_budget_wave2_logging.CRITICAL)
    yield
    _blood_budget_wave2_logging.disable(prev)



def _p1_state(hp: int = 40, round_num: int = 7, node: str = 'battle',
              gold: int = 100) -> _blood_budget_wave2_GameState:
    """P1 末窗备战帧(默认 hp=40 ∈ (25,60) 血预算不足带)。"""
    st = _blood_budget_wave2_GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _non_target_name() -> str:
    """注册表内非引擎件名(避开 _target_names 的引擎全集)。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        engine_char_names,
    )
    engines = set(engine_char_names())
    for name in CHARACTERS:
        if name not in engines:
            return name
    raise AssertionError('注册表内无非引擎件名(测试构造前提失效)')


def _p1_allin_sess() -> _blood_budget_wave2_StrategySession:
    """带 P1 槽序表(9 槽)的 session——plane_last_battle 真值源。"""
    s = _blood_budget_wave2_StrategySession()
    s.plane_node_table = ['battle'] * 9
    return s


# ---------- P1-a/P1-c 共用辖域谓词 ----------

def test_p1_exit_blood_short_band() -> None:
    """末窗起点/线值/位面边界:r≥6 ∧ hp<60 ∧ plane=1(设计件 12 §2.2)。"""
    reg = _blood_budget_wave2_DEFAULT_REGISTRY
    assert p1_exit_blood_short(_p1_state(hp=59), reg)
    assert not p1_exit_blood_short(_p1_state(hp=60), reg)   # 线值本身不辖
    assert not p1_exit_blood_short(_p1_state(round_num=5), reg)  # 非末窗
    p2 = _p1_state()
    p2.plane = 2
    assert not p1_exit_blood_short(p2, reg)


def test_refresh_blocked_domain_and_exemptions() -> None:
    """分型豁免:急救型保留(应急带 hp≤emergency_hp)、ALL IN 窗让位、
    P2 标定前零辖域、开关 off=零辖域(A/B 对照臂注入面)。

    辖域声明(设计 W659 v2 §5.1 改判;ADR-0469):血预算带停付辖域 =
    **非终止帧**——默认 hp=40 构造帧无节点表时全按 battle 档,L 最大
    11.32 < 40 → K=∅ → S0=1,结构上落不进终止域,断言不翻转;终止帧
    反例见 test_terminal_frame_release_counterexample。"""
    sess = _blood_budget_wave2_StrategySession()
    reg = _blood_budget_wave2_DEFAULT_REGISTRY
    assert blood_budget_refresh_blocked(_p1_state(hp=40), sess, reg)
    assert not blood_budget_refresh_blocked(_p1_state(hp=25), sess, reg)
    assert not blood_budget_refresh_blocked(_p1_state(hp=24), sess, reg)
    allin = _p1_state(hp=40, round_num=9, node='boss')
    assert not blood_budget_refresh_blocked(allin, _p1_allin_sess(), reg)
    p2 = _p1_state()
    p2.plane = 2
    assert not blood_budget_refresh_blocked(p2, sess, reg)
    reg_off = _blood_budget_wave2_dataclasses.replace(
        _blood_budget_wave2_DEFAULT_REGISTRY, blood_budget_refresh_stop_enabled=False)
    assert not blood_budget_refresh_blocked(_p1_state(hp=40), sess, reg_off)


def test_terminal_frame_release_counterexample() -> None:
    """终止帧反例(设计 W659 v2 §2.3/§3.1;ADR-0469):hp=26 行进带
    boss 单链(rung1,p_boss=0.027≤ε=0.03)→ 终止分支触发,双门开帧
    刷新停付解除;同帧降格短路。hp=26>应急线,豁免来自终止分支而非
    急救面——语义取代的显形锚。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        terminal_release,
    )
    sess = _p1_allin_sess()
    sess.plane_node_table = ['battle'] * 7 + ['encounter', 'boss']
    st = _p1_state(hp=26, round_num=8)
    st.deployed = [_blood_budget_wave2_BenchChar(slot=i + 1, char_id='艾丝妲' if i == 0
                             else '椒丘', faction='仙舟')
                   for i in range(2)]
    assert terminal_release(st, sess, _blood_budget_wave2_DEFAULT_REGISTRY)
    assert not blood_budget_refresh_blocked(st, sess, _blood_budget_wave2_DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, _blood_budget_wave2_DEFAULT_REGISTRY,
                                            session=sess)


def test_downgrade_active_flag() -> None:
    """P1-a 触发面=辖域谓词 ∧ 降格开关(flag off=A/B 对照臂)。"""
    reg = _blood_budget_wave2_DEFAULT_REGISTRY
    assert p1_directed_downgrade_active(_p1_state(hp=40), reg)
    reg_off = _blood_budget_wave2_dataclasses.replace(_blood_budget_wave2_DEFAULT_REGISTRY,
                                  p1_exit_downgrade_enabled=False)
    assert not p1_directed_downgrade_active(_p1_state(hp=40), reg_off)


# ---------- P1-a:承接门定向 copy 授权臂降格 ----------

def test_buy_tag_copy_arm_downgraded_in_band(monkeypatch) -> None:
    """血预算不足帧 gap>0 不再生成定向 'copy' 标签(降格=授权豁免通道
    停;设计件 12 §5.3 承接授权不豁免停手);对照:开关 off/非末窗照常。

    gap 与 pair 通道 monkeypatch 隔离——本锁只辖降格接线的方向性。"""
    monkeypatch.setattr(handoff_mod, 'handoff_gate_gap',
                        lambda *a, **k: 1)
    monkeypatch.setattr(cands_mod, 'pair_wants', lambda *a, **k: False)
    name = _non_target_name()
    st = _p1_state(hp=40)
    st.bench[0] = _blood_budget_wave2_BenchChar(slot=1, char_id=name, faction='仙舟')
    card = ShopCard(x=0, name=name, cost=3, faction='仙舟')
    sess = _blood_budget_wave2_StrategySession()
    # 血预算不足帧:定向授权降格,无 'copy' 标签(落入后续通道或 None)
    assert _buy_tag(card, st, sess, _blood_budget_wave2_DEFAULT_REGISTRY) != 'copy'
    # 对照臂(降格开关 off):gap 豁免照常生成定向 'copy'
    reg_off = _blood_budget_wave2_dataclasses.replace(_blood_budget_wave2_DEFAULT_REGISTRY,
                                  p1_exit_downgrade_enabled=False)
    assert _buy_tag(card, st, sess, reg_off) == 'copy'
    # 非末窗(r5):gap 恒 0 语境被 monkeypatch,但降格辖域含末窗轮判
    # ——末窗外降格不辖,定向 'copy' 照常(零漂移面)
    st5 = _p1_state(hp=40, round_num=5)
    st5.bench[0] = _blood_budget_wave2_BenchChar(slot=1, char_id=name, faction='仙舟')
    assert _buy_tag(card, st5, sess, _blood_budget_wave2_DEFAULT_REGISTRY) == 'copy'


# ---------- P1-c:refresh 收尾拒付 ----------

def _refresh_cand() -> _blood_budget_wave2_Candidate:
    return _blood_budget_wave2_Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')


def test_arbitrate_refresh_rejected_in_band() -> None:
    """端到端:血预算不足帧正分刷新候选被拒(拒因带血预算停手)+
    拒付计数 +1;M-A 定向刷新局耗不消耗(预算零消耗)。"""
    sess = _blood_budget_wave2_StrategySession()
    st = _p1_state(hp=40)
    res = _blood_budget_wave2_arbitrate([(_refresh_cand(), 5.0, {})], st, sess,
                    _blood_budget_wave2_DEFAULT_REGISTRY)
    assert not res.actions
    assert any('搜索型刷新停拒' in (row.get('reject') or '')
               for row in res.log)
    assert sess.v3_blood_budget_refresh_rejects == 1
    assert getattr(sess, 'v3_dir_refresh_used', 0) == 0


def test_arbitrate_refresh_rescued_in_emergency_band() -> None:
    """急救型豁免反例:应急带帧(hp≤emergency_hp)同构造刷新照常放行
    (搜牌补板当轮转化;[31]④ 合法用途),拒付计数不增。"""
    sess = _blood_budget_wave2_StrategySession()
    st = _p1_state(hp=_P1_EMERGENCY_HP - 1)
    res = _blood_budget_wave2_arbitrate([(_refresh_cand(), 5.0, {})], st, sess,
                    _blood_budget_wave2_DEFAULT_REGISTRY)
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert sess.v3_blood_budget_refresh_rejects == 0


# ---------- 镜像常量 + 段级检查 ----------

def test_mirror_constants_match_registry() -> None:
    """cw_sim_checks 镜像常量 ↔ registry 单一源双向锁(漂移即红)。"""
    assert _blood_budget_wave2_DEFAULT_REGISTRY.p1_exit_blood_target == _P1_EXIT_BLOOD_TARGET
    assert (_blood_budget_wave2_DEFAULT_REGISTRY.handoff_gate_min_round
            == _P1_HANDOFF_GATE_MIN_ROUND)
    assert _blood_budget_wave2_DEFAULT_REGISTRY.emergency_hp == _P1_EMERGENCY_HP


def _blood_budget_wave2_row(plane: int, hp: int, rn: int, node: str,
         refreshes: int) -> dict:
    return {
        'plane': plane, 'round_num': rn, 'hp': hp,
        'sim': {'node': node},
        'actions': ([{'__type__': 'RefreshShop', 'cost': 2}] * refreshes),
    }


def test_seg_check_violation_and_exemptions() -> None:
    """违规帧出事件;应急带/ALL IN/线外帧不出(反例内嵌)。

    hp 口径=决策帧(上一行结算 hp),与停升级检查同式。"""
    rows = [
        _blood_budget_wave2_row(1, 80, 1, 'battle', 0),    # 局首:决策 hp=开局,不出
        _blood_budget_wave2_row(1, 70, 6, 'battle', 1),    # 决策 hp=80(线外)→ 不出
        _blood_budget_wave2_row(1, 45, 7, 'battle', 1),    # 决策 hp=70? 否——决策 hp=70→
        _blood_budget_wave2_row(1, 40, 8, 'battle', 2),    # 决策 hp=45 ∈ 带 → 违规事件
        _blood_budget_wave2_row(1, 20, 9, 'battle', 1),    # 决策 hp=40 但应急带豁免域?
        _blood_budget_wave2_row(1, 15, 9, 'boss', 3),      # 决策 hp=20(应急带)→ 急救豁免
    ]
    ev = seg_check_p1_blood_budget_refresh(rows)
    # 逐帧行为:r7 决策 hp=70 线外不出;r8 决策 hp=45 出 1 事件;
    # r9 battle 决策 hp=40 出事件(血预算不足,应急豁免只看 hp 不看节点)
    assert [e['round_num'] for e in ev] == [8, 9]
    assert ev[0]['hp'] == 45 and ev[0]['refreshes'] == 2
    # ALL IN 豁免:r9 boss 帧(决策 hp=20 应急带也不出,双豁免)
    rows_allin = [
        _blood_budget_wave2_row(1, 30, 8, 'battle', 0),
        _blood_budget_wave2_row(1, 28, 9, 'boss', 2),      # 决策 hp=30 ∈ 带 ∧ ALL IN → 豁免
    ]
    assert seg_check_p1_blood_budget_refresh(rows_allin) == []

    # 终止位豁免(设计 W659 v2 §5.1 R4;ADR-0469):同带帧 terminal_release=真
    # → 终止豁免不出事件;位假/键缺省 → 照旧出事件(决策层终态反例见
    # test_terminal_frame_release_counterexample)。
    base = {'plane': 1, 'hp': 30, 'sim': {'node': 'battle'}}
    rows_term = [
        {**base, 'round_num': 7, 'terminal_release': True,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},
        {**base, 'round_num': 8, 'terminal_release': False,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},
        {**base, 'round_num': 9,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},  # 缺省=假
    ]
    ev_term = seg_check_p1_blood_budget_refresh(rows_term)
    assert [e['round_num'] for e in ev_term] == [8, 9]


# ---------- (sim 账本披露键与 C1 锁段已随各自开关族删除——旧方案
# ---------- 清退批,清查报告 OLD_MIX_AUDIT §1.3) ----------

def _mk_session():
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
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
    # 边界精确:遭遇 Δ=42 恰在上界 → 采新;Δ=43 超界 → 拒
    sb = _mk_session()
    _seed_real(sb, 60, 5)
    sb.performance.record(_outcome(1, 6, '遭遇', killed=False))
    assert cw_reconcile.reconcile_hp(sb, 18, node_t=6) == (18, True)
    sb2 = _mk_session()
    _seed_real(sb2, 60, 5)
    sb2.performance.record(_outcome(1, 6, '遭遇', killed=False))
    assert cw_reconcile.reconcile_hp(sb2, 17, node_t=6) == (60, False)


def test_loss_unknown_node_type_accepted_with_evidence(monkeypatch) -> None:
    """节点型未标定(精英)不拍值:下行有 loss 背书 → 采新 + 幅度留证攒标定。

    判据修订(2026-09-02 hp 守卫重推导):扣血只发生在节点结算的战败
    (user_playstyle [27] 机制锚),loss 行已观测即下行有机制背书;「无标定
    谱」只该留证攒标定,不应拒信——旧实现拒信把标定缺口惩罚在读数上,
    是 hp 冲突噪声环的一臂(2026-09-02 分诊:抽样 5/6 合法下行被拒)。
    修前本场景返回 (60, False) —— 修复前红。
    """
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '精英', killed=False))
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    assert cw_reconcile.reconcile_hp(s, 40, node_t=6) == (40, True)
    assert s.last_hp_real == 40 and s.hp_suspect is None
    assert len(calls) == 1
    assert calls[0][1].get('direction') == 'down'   # 幅度留证(攒标定),不拒信


# ===== 锁3:跨节点下行判据(2026-09-02 修订面)=====

def test_no_fact_down_accepted_with_evidence(monkeypatch) -> None:
    """跨节点下行 + 窗内无已观测战斗(观察缺口)→ 采新 + 留证。

    判据修订(2026-09-02):扣血只发生在节点结算战败(机制锚),观察缺口
    (结算漏采/telemetry 断/shop 开态 OCR 恢复)≠ 没发生战斗;下行方向机制
    合法,采新留证。旧实现拒信把观察回路缺口惩罚在读数上:每个合法下行
    固化旧值 + 每帧留证直到双帧确认,是 hp post-ADR 冲突暴涨主源
    (2026-09-02 分诊 §3-B:5/6 抽样帧合法下行被拒)。修前返回 (60, False)
    —— 修复前红。
    """
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    assert s.performance.history == []
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (20, True)
    assert s.last_hp_real == 20 and s.hp_suspect is None
    assert len(calls) == 1
    assert calls[0][1].get('direction') == 'down'   # 留证不拒信


def test_window_earlier_loss_latest_win_down_accepted(monkeypatch) -> None:
    """真值帧跨多节点:窗内先 loss 后 win,下行背书看 loss 行(幅度对谱)。

    旧实现只看窗内**最新**行(=win)→ 判「无背书」拒信,把机制合法的
    下行误拒(shop 开态跨节点漏读的真值恢复帧即此形态)。修前返回
    (60, False) —— 修复前红。
    """
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 3)
    s.performance.record(_outcome(1, 4, '普通战斗', killed=False))   # t=4 loss
    s.performance.record(_outcome(1, 5, '普通战斗', killed=True))    # t=5 win(最新)
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    # Δ=20 ≤ 普通战斗 p100=23 → 谱内静默采新,零留证
    assert cw_reconcile.reconcile_hp(s, 40, node_t=5) == (40, True)
    assert s.last_hp_real == 40 and s.hp_suspect is None
    assert calls == []


def test_same_node_down_rejected(monkeypatch) -> None:
    """同节点下行:hp 节点内恒定是机制事实(扣血只发生在节点结算),
    任何下行必为误读 → 拒信进复现通道(守卫最硬的机制分支)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 6)
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)
    assert s.last_hp_real == 60
    assert s.hp_suspect['value'] == 20
    assert calls[0][1].get('direction') == 'down'


def test_reject_class_regression_confirms_misread(monkeypatch) -> None:
    """拒信类(胜战帧下行)1 帧低位 + 1 帧回归旧值 → 误读确认,丢弃 suspect。

    复现确认通道语义自 ADR-0431 不变,只是辖域收窄到机制不可能的下行
    (同节点/胜战零损/超谱);此处以胜战帧为宿主锁通道行为。
    """
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '普通战斗', killed=True))
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
    assert cw_reconcile.reconcile_hp(s, 20, node_t=6) == (60, False)
    assert cw_reconcile.reconcile_hp(s, 60, node_t=6) == (60, True)    # 回归 → 误读确认
    assert s.hp_suspect is None
    assert s.last_hp_real == 60


def test_suspect_window_expiry(monkeypatch) -> None:
    """超窗(>2 节点)未复现 → suspect 过期,下次下行重新走首拒帧
    (拒信类宿主 = 胜战帧下行;复现通道语义 ADR-0431 不变)。"""
    from sr_od.application.currency_war.kernel import cw_reconcile
    s = _mk_session()
    _seed_real(s, 60, 5)
    s.performance.record(_outcome(1, 6, '普通战斗', killed=True))
    calls: list[tuple] = []
    monkeypatch.setattr(cw_reconcile, '_conflict', lambda *a, **k: calls.append((a, k)))
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


def test_reconcile_down_guard_wired() -> None:
    """源级锁:reconcile_hp 内下行守卫与复现通道接线存在。"""
    import inspect

    from sr_od.application.currency_war.kernel import cw_reconcile
    src = inspect.getsource(cw_reconcile.reconcile_hp)
    assert '_battle_facts_between' in src
    assert '_reject_down' in src


# ==================== w823_hp_none ====================

from pathlib import Path

# ===== 1. None 化:字段默认与对账层 =====


def test_game_state_default_hp_none() -> None:
    """默认构造 = 未观测态:hp=None(不再兜底 100)。"""
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert GameState().hp is None


def test_reconcile_no_truth_returns_none() -> None:
    """开局全无真值:reconcile_hp 返回 (None, False),不兜底 100。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = StrategySession()
    assert reconcile_hp(s, None) == (None, False)
    assert s.last_hp_real is None   # None 不写回真值锚


def test_reconcile_read_none_keeps_inherited_int() -> None:
    """读不到但有真值:沿用 last_hp_real(int)——沿用语义与 None 化并存。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = StrategySession()
    s.last_hp_real = 55
    hp, readable = reconcile_hp(s, None)
    assert hp == 55 and readable is False


# ===== 2. 消费点 None 守卫(保守方向锁,抽样代表面)=====


def test_is_emergency_none_false() -> None:
    """应急触发(None=无真值)→ False(不进应急带,保守)。"""
    from sr_od.application.currency_war.kernel.cw_economy import is_emergency
    from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert is_emergency(GameState(hp=None), DEFAULT_REGISTRY) is False


def test_decision_state_none_hp_stays_none() -> None:
    """快照无真值 → 策略态 hp=None(不落 100 兜底;W823 adapter 改型点)。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision.decision_v2.adapter import (
        decision_state,
    )
    from sr_od.application.currency_war.decision.decision_v2.contracts import (
        Snapshot,
        SubstateClassification,
    )
    snap = Snapshot(hp=None, hp_readable=False,
                    classification=SubstateClassification(name='prep_shop'))
    st = decision_state(snap, StrategySession())
    assert st.hp is None


def test_discipline_predicates_none_false() -> None:
    """血预算谓词(None=无真值)→ False(不触发停手/降格辖域)。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        p1_exit_blood_short,
    )
    from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert p1_exit_blood_short(GameState(hp=None), DEFAULT_REGISTRY) is False


# ===== 3. 档案 r1 真值反推修数锁(档案缺位时 skip,不假绿)=====

_ARCHIVE_ROOT = Path(__file__).resolve().parents[4] / ".debug/temp/currency_war/replay/matches"

# 反推法:各局 rounds 表 r1 行结算屏真值(r1 节点无战斗,结算 hp=开局值)
# = 该局 2 条兜底 100 帧的回填真值。锁值出处 = w823 反推表(REPORT)。
_EXPECT_TRUTH = {
    "g_20260830_071711": 82, "g_20260830_073750": 82,
    "g_20260830_083542": 82, "g_20260830_094754": 62,
    "g_20260830_103601": 82, "g_20260830_113824": 82,
    "g_20260830_125824": 82, "g_20260830_140843": 82,
    "g_20260830_150029": 82,
}


def _load_frames(gid: str):
    import json

    import pytest
    p = _ARCHIVE_ROOT / f"match_{gid}.json"
    if not p.exists():
        pytest.skip(f"档案缺位:{p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return [json.loads(f) if isinstance(f, str) else f
            for f in doc["slices"]["decisions.jsonl"]]


def test_archive_r1_repaired_truth_values() -> None:
    """9 局 18 帧:反推真值回填正确,source=rule_per_game,无 hp=100 残留。"""
    for gid, truth in _EXPECT_TRUTH.items():
        frames = _load_frames(gid)
        r1 = [f for f in frames if f.get("plane") == 1 and f.get("round_num") == 1]
        assert len(r1) >= 2, gid
        hits = [f for f in r1
                if f.get("hp") == truth
                and (f.get("hp_repair") or {}).get("source") == "rule_per_game"]
        assert len(hits) == 2, (gid, len(hits))
        assert not [f for f in r1 if f.get("hp") == 100], gid   # 0 兜底残留


def test_archive_index_r1_rule_value_synced() -> None:
    """index.jsonl:r1_hp_rule_value 与帧值一致(additive 键同步)。"""
    import json

    import pytest
    ip = _ARCHIVE_ROOT / "index.jsonl"
    if not ip.exists():
        pytest.skip("index.jsonl 缺位")
    rows = {json.loads(l)["game_id"]: json.loads(l)
            for l in ip.read_text(encoding="utf-8").splitlines() if l.strip()}
    for gid, truth in _EXPECT_TRUTH.items():
        row = rows.get(gid)
        assert row is not None, gid
        assert row.get("r1_hp_rule_value") == truth, gid


# ==================== w917_crisis_release ====================

import dataclasses as _w917_crisis_release_dataclasses

from sr_od.application.currency_war.decision.cw_strategy import (
    StrategySession as _w917_crisis_release_StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2.ev import RoundPosture
from sr_od.application.currency_war.decision.decision_v2.posture import Posture
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    authorize_release_refresh,
    evaluate_release,
)
from sr_od.application.currency_war.decision.decision_v2.posture_release import (
    flip_hit as _w917_crisis_release_flip_hit,
)
from sr_od.application.currency_war.kernel.cw_economy import REFRESH_ROLL_CAP
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _w917_crisis_release_DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import BENCH_CAPACITY
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar as _w917_crisis_release_BenchChar,
)
from sr_od.application.currency_war.kernel.cw_state import (
    GameState as _w917_crisis_release_GameState,
)

_REG_ON = _w917_crisis_release_dataclasses.replace(_w917_crisis_release_DEFAULT_REGISTRY, crisis_release_enabled=True)
# 关行为锁显式注入(开臂后默认 registry=True,零漂移锚不再由缺省承载;
# 开关生命周期第 3 态义务=关行为仍测不删,ADR-0503)。
_REG_OFF = _w917_crisis_release_dataclasses.replace(_w917_crisis_release_DEFAULT_REGISTRY, crisis_release_enabled=False)


def _w917_crisis_release_state(*, gold: int = 90, hp: int = 1, plane: int = 1, r: int = 5,
           level: int = 6) -> _w917_crisis_release_GameState:
    """危机溢余帧基准构造:r=5 无排程姿态缓存 → R*=50,溢余=40。"""
    return _w917_crisis_release_GameState(
        plane=plane, round_num=r, gold=gold, level=level, hp=hp,
        shop_refresh_cost=2,
        deployed=[_w917_crisis_release_BenchChar(slot=20 + i, char_id=f'杂{i}', faction='公司',
                            star=1) for i in range(5)],
        bench=[_w917_crisis_release_BenchChar(slot=0, char_id='席0', faction='公司', star=1)]
        + [None] * (BENCH_CAPACITY - 1),
        shop=[], node_type='battle')


def _w917_crisis_release_sess(state: _w917_crisis_release_GameState, *, save: bool = True) -> _w917_crisis_release_StrategySession:
    """带确定性 DP 姿态缓存的 session(缺省=存息姿态,W907 病灶帧形)。"""
    s = _w917_crisis_release_StrategySession()
    s.v3_dp_posture = RoundPosture(
        (state.plane, state.round_num),
        Posture(save=save, level_up=False, refresh_budget=0))
    return s


# --- ① 开关关零漂移 -----------------------------------------------------------


def test_crisis_off_zero_drift() -> None:
    """显式注入 False 的危机溢余帧:指令 None、姿态原样、session 无
    release(W907 病灶行为原样保留=零漂移锚;开臂后关行为靠显式注入
    测,不靠缺省——开关生命周期第 3 态义务)。"""
    st = _w917_crisis_release_state()
    wrapped, d = evaluate_release(st, _w917_crisis_release_sess(st), _REG_OFF, 'FORM',
                                  _w917_crisis_release_sess(st).v3_dp_posture.posture)
    assert d is None
    assert wrapped.tag != 'release'
    assert wrapped.save is True


# --- ② 开臂形态 ---------------------------------------------------------------


def test_crisis_arm_budget_and_downgrade() -> None:
    """开臂危机溢余帧:预算=min(40, 6×2)=12、rolls=6;存息姿态降级
    tag='release' 且 save=False;session.v3_release 同源写入。"""
    st = _w917_crisis_release_state()
    sess = _w917_crisis_release_sess(st)
    dp = sess.v3_dp_posture.posture
    wrapped, d = evaluate_release(st, sess, _REG_ON, 'FORM', dp)
    assert d is not None and d.reason == 'crisis'
    assert d.budget_gold == min(90 - 50, REFRESH_ROLL_CAP * 2) == 12
    assert d.rolls == 6
    assert wrapped.tag == 'release'
    assert wrapped.save is False
    assert sess.v3_release is d


def test_crisis_arm_downgraded_overflow_basis() -> None:
    """危机臂溢余基降档(P36-a′/ADR-0506 后继;无条件):应急带内溢余基=
    g 本身(R*_crisis≡0),g 在息线/储备线以下也开火——旧语义「息线以内
    零漂移不触发」随储备线保护前提在应急带被 P23.4 证伪而过期(证明=
    p36 单篇 P36-a′;病灶=match4 p2r1 hp3/金89/R*90 臂静默)。预算式
    形态不变:min(50, 6×2)=12。"""
    st = _w917_crisis_release_state(gold=50)
    _, d = evaluate_release(st, _w917_crisis_release_sess(st), _REG_ON, 'FORM',
                            _w917_crisis_release_sess(st).v3_dp_posture.posture)
    assert d is not None and d.reason == 'crisis'
    assert d.budget_gold == min(50, REFRESH_ROLL_CAP * 2) == 12


def test_crisis_arm_zero_gold_stays_none() -> None:
    """静默唯一残留=金 0(危机溢余基=g,g=0 物理无金可泄,合法残余)。"""
    st = _w917_crisis_release_state(gold=0)
    _, d = evaluate_release(st, _w917_crisis_release_sess(st), _REG_ON, 'FORM',
                            _w917_crisis_release_sess(st).v3_dp_posture.posture)
    assert d is None


def test_crisis_arm_latch_within_round() -> None:
    """latch 语义:指令每轮入口重算为等值指令(纯函数,轮键内不因 hp
    抖动翻转为 None);session 持有最新指令(判据单一址)。"""
    st = _w917_crisis_release_state()
    sess = _w917_crisis_release_sess(st)
    _, d1 = evaluate_release(st, sess, _REG_ON, 'FORM',
                             sess.v3_dp_posture.posture)
    assert d1 is not None
    _, d2 = evaluate_release(st, sess, _REG_ON, 'FORM',
                             sess.v3_dp_posture.posture)
    assert d2 == d1 and sess.v3_release is d2


# --- ③ 辖域边界 ---------------------------------------------------------------


def test_non_emergency_frames_untouched() -> None:
    """非应急帧开臂不劫持 flip 臂:hp>30 溢余帧仍 reason='flip'
    (crisis 臂只辖应急让位分支,正常 flip 辖区零漂移)。"""
    st = _w917_crisis_release_state(hp=30)
    sess = _w917_crisis_release_sess(st, save=False)
    _, d = evaluate_release(st, sess, _REG_ON, 'FORM',
                            sess.v3_dp_posture.posture)
    assert d is not None and d.reason == 'flip'


def test_flip_hit_still_cedes_emergency() -> None:
    """_w917_crisis_release_flip_hit 应急让位结构保留(ADR-0426 辖区不相交不动;危机臂是
    存息准入门层的独立第三臂)。"""
    st = _w917_crisis_release_state(hp=25, gold=90)
    assert not _w917_crisis_release_flip_hit(st, _w917_crisis_release_sess(st), _REG_ON, 'FORM')


# --- ④ 放行门 -----------------------------------------------------------------


def test_crisis_budget_bounded_release() -> None:
    """危机预算有界放行:direct budget=2 下 cost=1 第 1/2 笔放行,
    第 3 笔累计越预算拒(累计 ≤ 预算语义,与 flip 臂同一消费门)。"""
    from sr_od.application.currency_war.decision.decision_v2.posture_release import (
        ReleaseDirective,
    )
    st = _w917_crisis_release_state(gold=99)
    sess = _w917_crisis_release_sess(st)
    sess.v3_release = ReleaseDirective(budget_gold=2, rolls=2,
                                       reason='crisis')
    assert authorize_release_refresh(sess, 99, 1, _REG_ON)
    assert authorize_release_refresh(sess, 98, 1, _REG_ON)
    assert authorize_release_refresh(sess, 97, 1, _REG_ON) == ''


def test_crisis_tier_truncation_gate() -> None:
    """息档截断门在危机臂的**常态刷新**照常辖(ADR-0506 开臂重推):gold=98
    (档内余量 8)逐笔 2 金放行至 90,跨档帧拒。首刷豁免面(ADR-0506)只辖
    本帧第一刷且生产计数在 arbiter 采纳点——本锁置 v2_round_refreshes=1
    钉「首刷已兑现后的常态截断」语义;被取代的旧表述(essential=False
    车道不因危机豁免,隐含全域适用)随 ADR-0506 过期。"""
    st = _w917_crisis_release_state(gold=98)
    sess = _w917_crisis_release_sess(st)
    evaluate_release(st, sess, _REG_ON, 'FORM', sess.v3_dp_posture.posture)
    sess.v2_round_refreshes = 1    # 首刷已兑现:豁免面之外,常态截断辖
    gold = 98
    spent = 0
    for _ in range(6):
        if not authorize_release_refresh(sess, gold, 2, _REG_ON):
            break
        gold -= 2
        spent += 2
        sess.v2_round_refreshes += 1    # 生产计数镜像(arbiter 采纳点)
    assert spent == 8 and gold == 90
    assert authorize_release_refresh(sess, gold, 2, _REG_ON) == ''


def test_crisis_boss_floor_guard() -> None:
    """花后金低于 boss_floor:危机臂不放行(g≥0 硬钳制/地板语义与
    flip 臂同一消费门,不因危机豁免)。"""
    st = _w917_crisis_release_state(gold=11)
    sess = _w917_crisis_release_sess(st)
    evaluate_release(st, sess, _REG_ON, 'FORM', sess.v3_dp_posture.posture)
    assert authorize_release_refresh(sess, 11, 2, _REG_ON) == ''


# --- ⑤ registry 字段面 --------------------------------------------------------


def test_registry_field_default_on() -> None:
    """字段面:crisis_release_enabled 默认 True(开关生命周期第 3 态:
    sim A/B 实花面过(W917/W930)+ 首局实机病灶复现(g_20260831_032006)
    翻默认;实机观察局 ≥2 为确认门非开臂门,挂账 ADR-0503 尾注)。"""
    assert _w917_crisis_release_DEFAULT_REGISTRY.crisis_release_enabled is True


# --- ⑥ 血预算防线(危机 wrap 保留 level_up 的兜底论证,W930 补锁) --------------


def test_crisis_wrap_level_up_still_blood_budget_gated() -> None:
    """危机帧 wrap 保留 level_up(DP 追级姿态经 crisis 臂包装后
    tag='release' ∧ level_up 仍 True——危险消费面确实存在)时,血预算
    停升级门在同一危机帧仍拒付:门判据只读 state.hp 对停升级线,不读
    posture tag / session.v3_release,crisis 臂不可能绕开它。
    hp=5 ≤ P1 停升级线(≈11,W907 血预算 levelup 拒付病灶帧形)。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        blood_budget_levelup_blocked,
        p1_levelup_stop_hp,
    )
    st = _w917_crisis_release_state(hp=5)
    assert st.hp <= p1_levelup_stop_hp(_REG_ON)
    sess = _w917_crisis_release_sess(st)
    wrapped, d = evaluate_release(st, sess, _REG_ON, 'FORM',
                                  Posture(save=True, level_up=True,
                                          refresh_budget=0))
    assert d is not None and d.reason == 'crisis'
    assert wrapped.tag == 'release' and wrapped.level_up is True
    assert blood_budget_levelup_blocked(st, sess, _REG_ON) is True


def test_crisis_level_up_band_between_lines_is_preexisting_design() -> None:
    """线间带论证锁:停升级线 < hp ≤ 应急线(P1:11<hp≤25)的危机帧
    停升级门不拦——该带的升级许可由 ADR-0448 停升级线设计承载(线=
    期望预算线,设计件 12 §2.3 明言「线很深、预期触发少」,刻意不与
    应急带同线),不是 crisis 臂新开的消费面:同一帧形在 flip 臂(溢余
    非应急帧)许可面完全相同。锁钉住该边界语义,防后续误把「危机帧能
    升级」读成危机臂引入的回归。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        blood_budget_levelup_blocked,
        p1_levelup_stop_hp,
    )
    hp_mid = p1_levelup_stop_hp(_REG_ON) + 1
    assert hp_mid <= _REG_ON.emergency_hp    # 线间带在 P1 非空(11<hp≤25)
    st = _w917_crisis_release_state(hp=hp_mid)
    sess = _w917_crisis_release_sess(st)
    _, d = evaluate_release(st, sess, _REG_ON, 'FORM',
                            Posture(save=True, level_up=True,
                                    refresh_budget=0))
    assert d is not None and d.reason == 'crisis'
    assert blood_budget_levelup_blocked(st, sess, _REG_ON) is False
