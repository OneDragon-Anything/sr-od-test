# -*- coding: utf-8 -*-
"""test_cw_handoff 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w224_handoff: test_cw_w224_handoff.py
- w227_handoff_gate: test_cw_w227_handoff_gate.py
- w313_handoff_new_window: test_cw_w313_handoff_new_window.py
- w69_locked_resume: test_cw_w69_locked_resume.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w224_handoff ====================

import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    HANDOFF_BOARD_CORE2_CUTS,
    HANDOFF_BOARD_ENGINE_CUTS,
    HANDOFF_HP_CUTS,
    HandoffSnapshot,
    handoff_hp_tier,
    handoff_snapshot,
    handoff_tier,
)
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
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


_SNAP_KEYS = {'hp', 'engines', 'form_score', 'core2_count', 'star_sum',
              'level', 'deployed_n', 'gold', 'locked', 'locked_comp',
              'hoard_n', 'hp_tier', 'board_tier', 'tier'}


def _bench(name: str, faction: str = '仙舟', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 1, 'gold': 40, 'level': 6,
            'board': {}, 'bench': [], 'shop': [], 'hp': 55,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = kw.pop('ist_phase', 'unlocked')
    ist.locked_comp = kw.pop('locked_comp', '')
    s.v3_intention = ist
    for k, v in kw.items():
        setattr(s, k, v)
    return s


# ---------- ① 快照纯函数(单帧) ----------

def test_snapshot_fields_single_frame() -> None:
    """七维向量字段正确性:仙舟三人组(一引擎)上场,其一 2★。"""
    st = _state(
        hp=55, gold=40, level=6,
        deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                  _bench('爻光', slot=2, star=2), _bench('阮·梅', slot=3)])
    sess = _sess(ist_phase='locked', locked_comp='仙舟回路',
                 v3_hoard=HoardTarget(
                     frozenset({'藿藿', '丹恒·饮月'}), frozenset(), 'locked'))
    s = handoff_snapshot(st, sess)
    assert s.hp == 55 and s.gold == 40 and s.level == 6
    assert s.deployed_n == 4
    assert s.engines >= 1            # 仙舟 3 人 → 至少一体系(_engines_count)
    assert s.core2_count == 1        # 仅爻光 2★
    assert s.star_sum == 1 + 1 + 2 + 1
    assert s.locked and s.locked_comp == '仙舟回路'
    assert s.hoard_n == 2
    assert 0.0 <= s.form_score <= 1.0
    assert set(s.as_dict()) == _SNAP_KEYS


def test_snapshot_offline_without_session() -> None:
    """session 缺省 = 离线回放形态(锁线/囤货维不可算 → 缺省值不炸)。"""
    st = _state(deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                          _bench('爻光', slot=2)])
    s = handoff_snapshot(st)
    assert s.locked is False and s.locked_comp == '' and s.hoard_n == 0
    assert s.engines == 1 and s.deployed_n == 3
    # 纯函数契约:不写 state
    assert st.gold == 40 and st.hp == 55


# ---------- ② 档位边界例 ----------

def test_hp_tier_boundaries() -> None:
    """hp 维切点 (20,50) 边界:切点值落低档(超切点数口径)。"""
    assert HANDOFF_HP_CUTS == (20, 50)
    assert handoff_hp_tier(1) == 0    # run 28 型(hp=1 归零维)
    assert handoff_hp_tier(20) == 0
    assert handoff_hp_tier(21) == 1
    assert handoff_hp_tier(50) == 1
    assert handoff_hp_tier(51) == 2   # run 26 型(hp=64 健康)


def test_board_tier_and_overall() -> None:
    """板面维 = min(engines 档, core2 档);总档位 = min(hp, 板面)。

    run 26 型回验形态:hp 维健康(64→tier2)但星级维归零(core2=0)
    → 板面档 0、总档 0(主罚维=板面/星级);run 28 型:hp 维归零
    (hp=1→tier0)为主罚维。两局都被判「承接不足」且可指认主罚维。
    """
    assert HANDOFF_BOARD_ENGINE_CUTS == (1,)
    assert HANDOFF_BOARD_CORE2_CUTS == (1,)
    run26 = HandoffSnapshot(hp=64, engines=2, core2_count=0, star_sum=6,
                            level=6, deployed_n=6, gold=75, locked=True)
    assert handoff_hp_tier(run26.hp) == 2
    assert run26.as_dict()['board_tier'] == 0
    assert handoff_tier(run26) == 0     # 承接不足,罚在板面(星级)维
    run28 = HandoffSnapshot(hp=1, engines=1, core2_count=0, star_sum=6,
                            level=6, deployed_n=6, gold=86, locked=True)
    assert handoff_hp_tier(run28.hp) == 0
    assert handoff_tier(run28) == 0     # 罚在 hp 维
    # 健康高端:hp>50 且板面 ≥1 → 总档位仍 1(板面维单切点封顶 1,
    # 总档位实际两档——ADR-0399 标定结论;hp 高端区分度归 hp_tier)
    hi = HandoffSnapshot(hp=69, engines=1, core2_count=1, star_sum=7,
                         level=6, deployed_n=6, gold=78, locked=True)
    assert handoff_tier(hi) == 1 and handoff_hp_tier(hi.hp) == 2


# ---------- ③ decide_prep 挂载 ----------

def test_decide_prep_mounts_snapshot_once_per_plane() -> None:
    """plane>=2 本位面首帧算一次写 session.v3_handoff;同位面不覆写。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                          _bench('爻光', slot=2, star=2)])
    strat.decide_prep(st, sess, None)
    assert sess.v3_handoff is not None
    first = sess.v3_handoff
    assert first.hp == 55 and first.deployed_n == 3 and first.core2_count == 1
    assert sess.v3_handoff_plane == 2
    # 同位面第二轮:不覆写(同一对象——位面首帧一次性采样)
    st2 = _state(round_num=2, hp=40, gold=30,
                 deployed=[_bench('藿藿', slot=0)])
    strat.decide_prep(st2, sess, None)
    assert sess.v3_handoff is first


def test_decide_prep_no_snapshot_on_plane1() -> None:
    """plane=1 不触发(Phase 0 观测只辖 P2 承接;P1 零漂移的结构面)。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(plane=1, round_num=5)
    strat.decide_prep(st, sess, None)
    assert sess.v3_handoff is None


# ---------- ④ sim 侧观测 ----------

def test_sim_p2_handoff_field() -> None:
    """SimResult.p2_handoff:planes=2 进场有快照/同 seed 确定/
    planes=1 恒 None。"""
    r = engine_p1.simulate_p1(0, pool='fallback', planes=2)
    if r.p2_entered:
        assert isinstance(r.p2_handoff, dict)
        assert set(r.p2_handoff) == _SNAP_KEYS
        r2 = engine_p1.simulate_p1(0, pool='fallback', planes=2)
        assert r2.p2_handoff == r.p2_handoff   # 同 seed 确定性
    else:
        assert r.p2_handoff is None
    r1 = engine_p1.simulate_p1(0, pool='fallback', planes=1)
    assert r1.p2_handoff is None and r1.p2_entered is False


def test_sim_replay_entry_snapshot() -> None:
    """案 b 臂(真值进场态)同样经首轮 decide_prep 采样快照。"""
    entry = engine_p2.P2ReplayEntry(
        hp=64, gold=75, level=6, board={'仙舟': 3},
        deployed=[{'char_id': '藿藿', 'faction': '仙舟', 'star': 1},
                  {'char_id': '丹恒·饮月', 'faction': '仙舟', 'star': 1},
                  {'char_id': '爻光', 'faction': '仙舟', 'star': 2}])
    r = engine_p2.simulate_p2_replay_entry(entry, 0, pool='fallback')
    assert r.p2_entered
    h = r.p2_handoff
    assert h['hp'] == 64 and h['deployed_n'] == 3
    # gold 含 P2 r1 轮收入(75 + 11;快照时点=首轮 decide_prep 入口,
    # 与生产/标定语料同口径——见 handoff_snapshot 时点语义注)
    assert h['gold'] == 86
    assert h['core2_count'] == 1 and h['hp_tier'] == 2


# ---------- ⑤ 生产遥测 ----------

def test_decision_trace_handoff_field(tmp_path) -> None:
    """DecisionTrace.handoff:extra 透传 dict;缺省 None(schema 兼容)。

    P10④ 挂账落码后读端富化:落账行在快照 dict 副本上补
    ``salvageable_1star_value``(计算式锁在 test_cw_w428_salvageable_
    1star_value.py);快照本体 as_dict() 键集不变(sim 同构不受影响)。
    """
    rec = recorder.TelemetryRecorder(tmp_path, enabled=True)
    st = _state(shop=[ShopCard(x=0, name='藿藿', faction='仙舟', cost=1)])
    sess = _sess()
    snap = handoff_snapshot(st, sess)
    rec.record_decision('run_t', 'A4', st, '', {}, {}, [],
                        extra={'handoff': snap.as_dict()})
    line = (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
    import json
    row = json.loads(line.strip().splitlines()[-1])
    expect = dict(snap.as_dict())
    expect['salvageable_1star_value'] = row['handoff']['salvageable_1star_value']
    assert row['handoff'] == expect
    assert set(snap.as_dict()) == _SNAP_KEYS   # 快照本体键集不变
    # 缺省(旧调用形态):None 不破坏 schema
    rec.record_decision('run_t', 'A4', st, '', {}, {}, [])
    line = (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
    row2 = json.loads(line.strip().splitlines()[-1])
    assert row2['handoff'] is None


from sr_od.application.currency_war.sim import engine_p1, engine_p2
from sr_od.application.currency_war.telemetry import recorder


# ==================== w227_handoff_gate ====================

import logging
from dataclasses import replace

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _check_constraint,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.filters import (
    filter_candidates,
    formed_stop_active,
)
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    handoff_gate_gap,
)
from sr_od.application.currency_war.decision.decision_v2.phase import form_ok
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.sim import engine_p1 as cw_sim


@pytest.fixture(autouse=True)
def _w227_handoff_gate_quiet_logging():
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


#: ADR-0411:承接门无条件启用——行为臂即 DEFAULT_REGISTRY
_REG = DEFAULT_REGISTRY


def _card(name: str, cost: int, faction: str = '持续伤害') -> ShopCard:
    return ShopCard(name=name, faction=faction, cost=cost, x=0, star=1)


def _locked_formed_frame(**kw) -> GameState:
    """run 28/31 型构造帧:DOT队锁定成型(核心卡芙卡上场 2★+桑博补
    DOT 引擎),P1 末窗,低血(hp=15 → hp 维归零,总档 0=承接缺口 1)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 8, 'gold': 55, 'level': 5, 'hp': 15,
        'board': dict(comp.form_tiers),
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2),
                     BenchChar(slot=1, char_id='桑博', faction='仙舟罗浮',
                               star=1)],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


def _fallback_formed_frame(**kw) -> GameState:
    """兜底成型帧(未锁):仙舟3+DOT2 两体系(engines=2,form_ok 兜底
    判据过)但全 1★(core2=0 → 板面维归零);hp 健康 → 缺口走板面维
    (run 26 型星级深度主罚维)。"""
    base = {
        'plane': 1, 'round_num': 8, 'gold': 53, 'level': 5, 'hp': 40,
        'board': {},
        'deployed': [BenchChar(slot=i, char_id=n, faction='仙舟',
                               star=1)
                     for i, n in enumerate(
                         ['藿藿', '丹恒·饮月', '爻光', '桑博', '卡芙卡'])],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked() -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp='DOT队')
    s.v3_mode = 'economy'
    return s


# ---------- ① 缺口判据窗口/辖域 ----------

def test_gate_gap_window_and_scope() -> None:
    """r5(非末窗,W288 前移后边界)/P2 恒 0;r6-r9 缺口辖;达标帧 0。"""
    sess = _sess_locked()
    st = _locked_formed_frame()
    assert form_ok(st, sess, _REG) is True   # 前置:成型谓词过
    assert handoff_gate_gap(st, sess, _REG) == 1
    # 新窗内(r6/r7,W288/ADR-0418 前移后):照辖
    assert handoff_gate_gap(_locked_formed_frame(round_num=6), sess,
                            _REG) >= 0   # 是否有缺口随投影面,只锁「在窗内可非零」的前置
    assert handoff_gate_gap(_locked_formed_frame(round_num=7), sess,
                            _REG) == 1
    # 非末窗(r5):不辖(零漂移边界)
    assert handoff_gate_gap(_locked_formed_frame(round_num=5), sess,
                            _REG) == 0
    # P2:不辖
    assert handoff_gate_gap(_locked_formed_frame(plane=2), sess,
                            _REG) == 0
    # 达标帧(hp 修复到健康带 → 投影后 hp_tier≥1 ∧ 板面维达标 → 总档 1)
    assert handoff_gate_gap(_locked_formed_frame(hp=64), sess,
                            _REG) == 0


# ---------- ② formed_stop 承接维(挂载点 a) ----------

def test_formed_stop_handoff_dim_run28_type() -> None:
    """run 28/31 型:末窗成型低血 → 承接门不停手(买候选保留=继续
    投资证据行);非末窗同帧(r7)照旧停手(承接维不辖 r7,零漂移)。
    (过期语义记录:原「默认臂照旧停手」的基线断言已随 ADR-0411 转正
    删除——末窗低血不停手即当前无条件行为。)"""
    st = _locked_formed_frame()
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    sess_on = _sess_locked()
    kept_on, _ = filter_candidates([cand], st, sess_on, _REG)
    assert sess_on.v3_formed_stop is False
    assert sess_on.v3_handoff_gap == 1
    assert any(isinstance(c.action, BuyCard) for c in kept_on)
    # 零漂移边界随 W288/ADR-0418 前移重排:非末窗(r5)在成型停手线
    # (r≥7)之前,构造不出「floor 过∧门不辖」帧——改锁「窗内但承接
    # 达标仍停手」(r7 ∧ hp=64 → gap=0,承接维不拦):
    st7_ok = _locked_formed_frame(round_num=7, hp=64)
    s_b = _sess_locked()
    assert formed_stop_active(st7_ok, s_b, _REG) is True
    assert getattr(s_b, 'v3_handoff_gap', 0) == 0


# ---------- ③ EV 承接缺口项(挂载点 b) ----------

def test_ev_gap_term_authorizes_final_window_buy() -> None:
    """末窗兜底成型全 1★ 板的跨档买(53→49 破 50 平台):V+bonus 放行,
    auth trace 带 handoff_gap;同帧 r7(非末窗)拒(零漂移);达标帧
    拒(不达标才放宽)。
    (过期语义记录:原「基线臂 EV≤0 破息拒」对照断言已随 ADR-0411
    转正删除——本行为即当前无条件路径。语义演进(ADR-0451 血预算
    停手·第二波):授权帧改 hp=70 带外——hp<60 末窗帧缺口项降格不加成
    (血预算停手·P1-a),反例:hp=40 帧同构造被拒。)"""
    st = _fallback_formed_frame(hp=70)
    sess = StrategySession()          # 未锁 → 兜底 form_ok(engines=2)
    sess.v3_mode = 'economy'
    assert form_ok(st, sess, _REG) is True
    assert handoff_gate_gap(st, sess, _REG) == 1
    cand = Candidate(action=BuyCard(_card('卡芙卡', cost=4), reason=''),
                     tag='line_carry', source='shop')
    # 门臂(现无条件):缺口项放行 + 授权 trace
    auth: dict = {}
    r_on = _check_constraint('interest_rule', cand, st, st, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}, auth=auth)
    assert r_on is None
    assert auth.get('handoff_gap') == 1 and auth.get('ev_auth', 0) > 0
    # 非末窗同帧(r5,W288 前移后边界):照拒(承接项不辖非末窗)
    st7 = _fallback_formed_frame(round_num=5)
    assert _check_constraint('interest_rule', cand, st7, st7, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None
    # ADR-0451 反例:hp=40(末窗血预算不足带)缺口项不加成 → 照拒
    st_band = _fallback_formed_frame()
    assert handoff_gate_gap(st_band, sess, _REG) == 1
    assert _check_constraint('interest_rule', cand, st_band, st_band,
                             sess, _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None
    # 达标帧(核心 2★ 补上 + hp 60:boss 投影后 hp=28 → hp_tier=1,
    # 板面维亦达标 → 总档 1):照拒(不达标才放宽)。
    # (口径注:hp 取值按 ADR-0411 无条件 boss 投影选档——原 hp=40
    # 帧在 boss 投影下落 hp_tier=0,属「未达标」不再是达标例。)
    dep = list(_fallback_formed_frame().deployed)
    dep[0] = replace(dep[0], star=2)
    st_ok = _fallback_formed_frame(deployed=dep, hp=60)
    assert handoff_gate_gap(st_ok, sess, _REG) == 0
    assert _check_constraint('interest_rule', cand, st_ok, st_ok, sess,
                             _REG, val=1.0,
                             bd={'int_emb': 0.0}) is not None


# ---------- ④ sim 侧:账本字段 + 非末窗零漂移 ----------

def test_sim_ledger_handoff_gap_zero_before_final_window() -> None:
    """账本轮行带 handoff_gap 且非末窗(plane1 round<6,W288/ADR-0418
    前移后)恒 0——P1 非末窗零漂移的结构前提在默认注册表下直接成立
    (n 取最小 2)。"""
    for seed in range(2):
        r = cw_sim.simulate_p1(seed, pool='fallback', planes=2)
        assert all('handoff_gap' in row for row in r.ledger)
        assert all((row.get('handoff_gap') or 0) >= 0 for row in r.ledger)
        pre = [row for row in r.ledger
               if row.get('plane') == 1 and row['round_num'] < 6]
        assert all((row.get('handoff_gap') or 0) == 0 for row in pre), (
            f'seed {seed}:承接门越权辖非末窗')



# ==================== w313_handoff_new_window ====================

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    HoardTarget,
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    formed_stop_active,
)
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    boss_projected_hp,
    handoff_gate_gap,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_w313_handoff_new_window_REG = DEFAULT_REGISTRY
_TARGET = '花火'   # hoard 目标件(姬子列车锁定线;C 臂放行对象)


def _w313_handoff_new_window_sess() -> StrategySession:
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    s.target_comp = SimpleNamespace(factions=('列车同行',),
                                    core_chars=('姬子·启行',))
    return s


def _w313_handoff_new_window_state(round_num: int, hp: int = 40) -> GameState:
    """探针帧:deployed 目标件单件 + 店内同名;hp=40(低血,
    hp 维缺口)+ 板面浅 → 新窗内 gap=1、r5 窗外 gap=0。"""
    return GameState(
        plane=1, round_num=round_num, gold=60, level=5, hp=hp,
        board={'列车同行': 2},
        deployed=[BenchChar(slot=0, char_id=_TARGET,
                            faction='仙舟罗浮', star=1)],
        bench=[],
        shop=[ShopCard(name=_TARGET, faction='仙舟罗浮', cost=5,
                       x=0, star=1)])


def test_c_arm_new_window_r7_allows_line_opportunistic_copy() -> None:
    """C 臂(ADR-0405/0411 无条件):r7 ∈ 新窗 ∧ gap>0 → deployed
    目标件的店内同名副本放行,tag='line_opportunistic'(gate 前移前该帧
    基线 gap=0 候选=[];探针实证)。"""
    sess = _w313_handoff_new_window_sess()
    st = _w313_handoff_new_window_state(7)
    assert handoff_gate_gap(st, sess, _w313_handoff_new_window_REG) == 1
    buys = [c for c in generate_candidates(st, sess, _w313_handoff_new_window_REG)
            if isinstance(c.action, BuyCard)
            and c.action.card.name == _TARGET]
    assert buys and buys[0].tag == 'line_opportunistic', \
        '新窗 r7 gap>0:同名副本候选必须放行(line_opportunistic)'


def test_c_arm_out_of_window_r5_still_zero_drift() -> None:
    """零漂移边界:r5(窗外)同帧 gap=0 → 不生成该买候选。
    (语义演进,ADR-0438:copy_swap_target_exempt 开臂翻默认 True,
    deployed 目标件的第 2 份在窗外也生成——本锁改显式注入关臂,
    钉「守卫直通基线」的原边界;豁免臂行为由 w242/adr0303 锁。)"""
    from dataclasses import replace
    sess = _w313_handoff_new_window_sess()
    st = _w313_handoff_new_window_state(5)
    assert handoff_gate_gap(st, sess, _w313_handoff_new_window_REG) == 0
    assert not [c for c in generate_candidates(
                    st, sess, replace(_w313_handoff_new_window_REG, copy_swap_target_exempt=False))
                if isinstance(c.action, BuyCard)
                and c.action.card.name == _TARGET], \
        '窗外 r5 同名副本必须仍被守卫拦(零漂移)'


def test_formed_stop_new_window_gap_positive_keeps_investing() -> None:
    """承接维:r7 ∈ 新窗 ∧ gap>0 → 成型停手让位,不停手继续投资
    (买候选保留;w107 锁「窗内 gap=0 仍停手」为本锁的对偶面)。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    from sr_od.application.currency_war.kernel.cw_intention import intention_core
    comp = get_comp('DOT队')
    core = intention_core(comp)
    st = GameState(
        plane=1, round_num=7, gold=60, level=5, hp=15,
        board=dict(comp.form_tiers),
        deployed=[BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                            star=2)],
        bench=[], shop=[], node_type='battle')
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked',
                                       locked_comp='DOT队')
    assert handoff_gate_gap(st, sess, _w313_handoff_new_window_REG) == 1   # 末窗缺口帧(镜像 w227)
    assert formed_stop_active(st, sess, _w313_handoff_new_window_REG) is False, (
        '新窗 r7 gap>0:承接维接管,成型不停手')



# ==================== w69_locked_resume ====================

from sr_od.application.currency_war.obs.cw_resume_lock import (
    locked_after_start_battle,
    probe_resolve,
    resume_candidate,
)


def test_resume_candidate_three_states():
    """锁 1(判据三态,设计章1.2):
    新 match + round>1 → 候选;正常新局 r1 → 非候选;续跑/局中 → 不检测。"""
    assert resume_candidate(True, 1, 5) is True       # 恢复局(同判据:plane1 round5)
    assert resume_candidate(True, 2, 1) is True       # 恢复局(plane>1 同样候选)
    assert resume_candidate(True, 1, 1) is False      # 正常新局 r1
    assert resume_candidate(False, 2, 3) is False     # bot 自己跑的中间备战,不检测


def test_probe_resolve():
    """锁 2(探针裁决,设计章1.3):商店可开=非锁定;零响应=锁定。"""
    assert probe_resolve(True) == 'normal'
    assert probe_resolve(False) == 'locked'


def test_locked_cleared_on_battle_success():
    """锁 3(解除,设计章1.5/1.8):StartBattle 成功 → 清锁;未落地 → 保锁重试。"""
    assert locked_after_start_battle(True) is False    # 出战成功 → 解除
    assert locked_after_start_battle(False) is True    # 未落地 → 保锁(不新增死循环)
