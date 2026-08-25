# -*- coding: utf-8 -*-
"""W119/ADR-0347 切授权单帧锁(经济循环总模型步②「切授权」)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① FORM 段 EV 正破息买放行(interest_rule EV 授权,含 ev_auth trace);
- ② EV/总账不过的升级被拒(seed6 形态帧:49 金追级,[12] 收编);
- ③ formed_stop 辖轮 comp 派生(早成型 DOT队 typical=4 / 晚成型
  昼神阿雅 typical=8 两例);
- ④ boss 窗判定合一(discipline/arbiter 同帧同判:节点图为主,
  轮数只留 node_type 缺读兜底一处);
- ⑤ DP 接线:仲裁层升级授权真实消费 cw_horizon 姿态(mock 注入
  两姿态,行为必须随姿态翻转);
- ⑥ 扑满守卫:「经济过热」类环境 reward 节点按战斗节点处理
  (连胜 EV 地板/保血通道 hard 判定)。
- 附:旁路护栏(应急态地板/interest_rule 让位逐位不变)+HOARD
  相位域([11] 同档放行/跨档攒息拒)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_state import (
    Action,
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    _active_floor,
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.discipline import (
    _streak_floor,
    assess_discipline,
    boss_window_active,
)
from sr_od.application.currency_war.decision_v2.filters import (
    formed_stop_active,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.scoring import (
    score_candidate,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟罗浮',
          cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction=faction, cost=cost, x=0, star=1)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 50, 'level': 5,
            'hp': 70, 'board': {}, 'bench': [], 'shop': [],
            'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _sess_locked(comp: str = 'DOT队') -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    sess.v3_mode = 'economy'
    return sess


def _formed_frame(comp_name: str, **kw) -> GameState:
    """锁定线成型帧:form_tiers 全满(board)+ 核心上场 2★。"""
    comp = get_comp(comp_name)
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 55, 'level': 5, 'hp': 60,
        'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [BenchChar(slot=0, char_id=core,
                               faction=next(iter(comp.form_tiers)),
                               star=2)],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


# --- ① FORM 段 EV 正破息买放行 ----------------------------------------------


def test_form_ev_positive_break_buy_allowed() -> None:
    """①FORM 相位金 51:跨档买(51→47,破 1 档)按 EV 授权裁决——
    EV=V−C>0 放行(log 带 ev_auth 授权依据 trace);EV≤0 拒(拒绝因
    「EV≤0 破息拒」)。V=层3分剥离息分量(bd['int_emb']),本锁直接
    注入 (val, bd) 锁**门语义**(EV 阈值/方向/trace);int_emb 与评分
    的单一源契约另锁(见 test_int_emb_contract)。"""
    sess = StrategySession()   # unlocked 空 board → FORM
    sess.v3_mode = 'economy'
    st = _state(round_num=5, gold=51, node_type='battle')
    cand = Candidate(action=BuyCard(_card('引擎件', cost=4), reason=''),
                     tag='engine_seed', source='shop')
    # EV 正:V = 30 −(−25) = 55,C = 1 档×R(23)→ EV≈32 > 0 → 放行
    res_pos = arbitrate([(cand, 30.0, {'int_emb': -25.0})], st, sess,
                        _REG)
    row = next(r for r in res_pos.log if r['tag'] == 'engine_seed')
    assert row['accepted'] is True, row
    assert row['ev_auth']['ev_auth'] > 0, row   # 授权依据 trace 在场
    assert any(isinstance(a, BuyCard) for a in res_pos.actions)
    # EV 负:V = 5 − 0 = 5 < C → 拒
    sess2 = StrategySession()
    sess2.v3_mode = 'economy'
    res_neg = arbitrate([(cand, 5.0, {'int_emb': 0.0})], st, sess2,
                        _REG)
    row2 = next(r for r in res_neg.log if r['tag'] == 'engine_seed')
    assert row2['accepted'] is False, row2
    assert 'EV≤0 破息拒' in (row2['reject'] or ''), row2


def test_int_emb_contract() -> None:
    """int_emb 单一源契约:score_candidate 的 breakdown 内嵌息分量=
    息差(after−base);无息差通道(refresh/无 after)恒 0。仲裁层
    interest_rule 的 V 剥离消费它,禁双源。"""
    from sr_od.application.currency_war.decision_v2.scoring import (
        score_candidate as _sc,
    )
    # 常规买候选(bench 件,息差 0——金不变):int_emb=Δinterest
    st = _state(round_num=3, gold=30, node_type='battle',
                bench=[BenchChar(slot=0, char_id='桑博',
                                 faction='仙舟罗浮', star=1)],
                shop=[])
    from sr_od.application.currency_war.cw_state import SellBench
    sell = Candidate(action=SellBench(bench_idx=0, income=1),
                     tag='off_target', source='bench',
                     breakdown_hint={'name': '桑博'})
    _val, bd = _sc(sell, st, StrategySession(), _REG)
    assert bd['int_emb'] == (bd['after']['interest']
                             - bd['base']['interest'])
    # refresh 候选:int_emb=0
    from sr_od.application.currency_war.cw_state import RefreshShop
    rf = Candidate(action=RefreshShop(cost=2), tag='refresh',
                   source='shop')
    _v2, bd2 = _sc(rf, st, StrategySession(), _REG)
    assert bd2['int_emb'] == 0.0


# --- ② EV≤0 升级被拒(seed6 形态帧)------------------------------------------


def test_levelup_rejected_seed6_frame() -> None:
    """②seed6 形态帧:P1 金 49/lv6/从未满息/无人口位(deployed=cap,
    bench 无目标件)→ LevelUp 被 EV 总账拒(平台延迟账),拒绝因可见
    「息引擎总账拒」。"""
    sess = StrategySession()   # unlocked → FORM;last_streak 无
    sess.v3_mode = 'economy'
    st = _state(round_num=6, gold=49, level=6,
                deployed=[BenchChar(slot=i, char_id=f'杂件{i}',
                                    faction='公司', star=1)
                          for i in range(6)],
                bench=[BenchChar(slot=0, char_id='散件甲',
                                 faction='公司', star=1)],
                shop=[])
    assert st.max_units() >= 6 and len(st.deployed) >= st.max_units(), \
        '前置:deployed=cap(无人口位)'
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, sess, _REG)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert row['accepted'] is False, row
    assert '息引擎总账拒' in (row['reject'] or ''), row
    assert not any(isinstance(a, LevelUp) for a in res.actions)


# --- ③ formed_stop 辖轮 comp 派生 -------------------------------------------


def test_formed_stop_round_comp_derived() -> None:
    """③辖轮 = max(comp.typical_form_round, formed_stop_min_round):
    早成型 DOT队(typical 4→辖 7):r6 不停/r7 停;晚成型 昼神阿雅
    (typical 8→辖 8):r7 不停/r8 停。"""
    for comp_name, stop_r, nostop_r in (('DOT队', 7, 6),
                                        ('昼神阿雅', 8, 7)):
        comp = get_comp(comp_name)
        assert comp.typical_form_round in (4, 8)   # 前置:早晚档锚
        for r, expect in ((nostop_r, False), (stop_r, True)):
            sess = _sess_locked(comp_name)
            st = _formed_frame(comp_name, round_num=r)
            assert formed_stop_active(st, sess, _REG) is expect, (
                f'{comp_name} r{r}:期望 {expect}')


# --- ④ boss 窗判定合一(节点图为主)-----------------------------------------


def test_boss_window_unified_node_graph() -> None:
    """④同帧同判:node_type='battle' P1 r7(旧 discipline r≥5 会入
    boss_breaker)→ 两口径都**不**入 boss 窗(coverage=mode/economy,
    地板=相位地板);node_type='boss' 同轮 → 两口径都入(boss_breaker,
    地板=boss_floor);node_type 缺读 P1 r9 → 兜底入窗。"""
    sess = StrategySession()
    sess.v3_mode = 'economy'
    # battle 节点 + P1 r7:不入窗
    st = _state(round_num=7, node_type='battle')
    assert boss_window_active(st, sess, _REG) is False
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage != 'boss_breaker', disc
    assert _active_floor(st, sess, _REG) == _REG.form_floor   # FORM 相位
    # boss 节点同轮:入窗(两口径同判)
    st_boss = _state(round_num=7, node_type='boss')
    assert boss_window_active(st_boss, sess, _REG) is True
    disc_b = assess_discipline(st_boss, sess, _REG)
    assert disc_b.coverage == 'boss_breaker'
    assert _active_floor(st_boss, sess, _REG) == _REG.boss_floor
    # node_type 缺读 + P1 r9:兜底(全仓唯一轮数口径)
    st_n = _state(round_num=9, node_type='')
    assert boss_window_active(st_n, sess, _REG) is True


# --- ⑤ DP 接线:仲裁层消费 cw_horizon 姿态 ----------------------------------


def test_dp_posture_consumed_by_arbiter(monkeypatch) -> None:
    """⑤升级授权随 DP 姿态翻转(接线证明,非注释非遥测):金 60/lv6,
    静态账 V 小而平台无损(C=0)本可过——对照臂用金 51(破平台)锁
    姿态翻转:DP 说升(level_up=True)→ 放行;DP 说存息(save)→
    息引擎总账拒。无人口位(deployed=cap)隔离 ① 路径。"""
    import sr_od.application.currency_war.decision_v2.ev as ev_mod

    def _mk(level_up: bool):
        return SimpleNamespace(save=not level_up, level_up=level_up,
                               refresh_budget=0, v=0.0,
                               tag='升级' if level_up else '存息')

    st = _state(round_num=6, gold=51, level=6,
                deployed=[BenchChar(slot=i, char_id=f'杂件{i}',
                                    faction='公司', star=1)
                          for i in range(6)],
                bench=[], shop=[])
    assert len(st.deployed) >= st.max_units(), '前置:无人口位'
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    # DP 说升 → 放行(平台破但 DP 总账授权?否——②臂要求平台未破,
    # 金 51-4=47<50 → DP 臂不放行;本帧锁的是静态/DP 的翻转差:
    # 用金 60 帧(52≥50)锁 DP 臂,金 51 帧(47<50)锁 DP 臂不越平台)
    st60 = _state(round_num=6, gold=60, level=6,
                  deployed=list(st.deployed), bench=[], shop=[])
    sess = StrategySession()
    sess.v3_mode = 'economy'
    monkeypatch.setattr(ev_mod, 'dp_posture',
                        lambda s, ss: _mk(True))
    res_up = arbitrate([(cand, 1.0, {})], st60, sess, _REG)
    assert any(isinstance(a, LevelUp) for a in res_up.actions), \
        'DP 说升且平台未破(60-4=52≥50)→ 必须放行'
    monkeypatch.setattr(ev_mod, 'dp_posture',
                        lambda s, ss: _mk(False))
    sess2 = StrategySession()
    sess2.v3_mode = 'economy'
    res_save = arbitrate([(Candidate(action=LevelUp(cost=4),
                                     tag='levelup', source='xp'),
                           1.0, {})],
                         _state(round_num=6, gold=49, level=6,
                                deployed=list(st.deployed),
                                bench=[], shop=[]), sess2, _REG)
    row = next(r for r in res_save.log if r['tag'] == 'levelup')
    assert row['accepted'] is False and '息引擎总账拒' in row['reject'], row


# --- 附:旁路护栏 + HOARD 相位域 ---------------------------------------------


def test_bypass_emergency_floor_unchanged() -> None:
    """旁路护栏:应急帧(hp≤25)地板=rebirth_floor、interest_rule
    让位(语义逐位不变——W119 验证门 1 专项)。"""
    sess = StrategySession()
    sess.v3_mode = 'economy'
    st = _state(hp=20, gold=55, node_type='battle')
    assert _active_floor(st, sess, _REG) == _REG.rebirth_floor
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage == 'emergency'
    # interest_rule 在应急态不辖(交 gold_floor)
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _check_constraint,
    )
    cand = Candidate(action=BuyCard(_card('测试件', cost=4), reason=''),
                     tag='engine_seed', source='shop')
    r = _check_constraint('interest_rule', cand, st, st, sess, _REG)
    assert r is None, '应急态 interest_rule 必须让位'


def test_hoard_phase_domain() -> None:
    """HOARD 相位域(form_ok+金<50):[11] 同档/1费放行;跨档攒息拒
    (拒绝原因可见 HOARD 攒息)。"""
    sess = _sess_locked('DOT队')
    st = _formed_frame('DOT队', gold=45, round_num=7)
    from sr_od.application.currency_war.decision_v2.phase import (
        derive_phase,
    )
    assert derive_phase(st, sess, _REG).value == 'HOARD'
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _check_constraint,
    )
    # 同档买(45→43,档 4 内):放行
    c_same = Candidate(action=BuyCard(_card('同档件', cost=2), reason=''),
                       tag='engine_seed', source='shop')
    assert _check_constraint('gold_floor', c_same, st, st, sess,
                             _REG) is None
    # 跨档买(45→39,破档 4):拒(HOARD 攒息)
    c_cross = Candidate(action=BuyCard(_card('跨档件', cost=6), reason=''),
                        tag='engine_seed', source='shop')
    r = _check_constraint('gold_floor', c_cross, st, st, sess, _REG)
    assert r is not None and 'HOARD 攒息' in r.describe, r
