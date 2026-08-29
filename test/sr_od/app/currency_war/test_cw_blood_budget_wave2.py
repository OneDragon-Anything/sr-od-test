"""血预算停手·第二波锁(设计件 12 §2.3-P1-a/P1-c、§3.2;ADR-0451)。

锁面:
- P1 末窗血预算不足谓词辖域(p1_exit_blood_short:末窗起点/线值/位面);
- 搜索型刷新停付分型豁免:急救型保留(应急带)、ALL IN 窗让位、
  P2 标定前零辖域、开关 off=零辖域;
- P1-a 末窗支出降格:承接门定向 copy 授权臂在血预算不足帧降格
  (gap 豁免不再生成 'copy' 标签);减损型动作族不在辖域;
- arbiter refresh 收尾拒付:血预算不足帧 RefreshShop 拒付 + 计数披露
  (M-A 预算不消耗);应急带豁免帧照常放行;
- cw_sim_checks 镜像常量双向锁 + 段级检查 seg_p1_blood_budget_refresh
  违规/豁免反例;
- sim 账本披露键存在性(单局冒烟,不锁分布)。

判据出处:设计件 12 §2.3-P1-a/P1-c(60 线=W524 审计后期望预算线,
充分不必要)、§3.2(停刷新结构语义;数值线需标定挂 β 门)、§5.2-5.3
接缝(独立谓词 AND 血线胜/承接授权不豁免/ALL IN 让位)。
"""
from __future__ import annotations

import dataclasses
import logging

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.cw_sim_checks import (
    _P1_EMERGENCY_HP,
    _P1_EXIT_BLOOD_TARGET,
    _P1_HANDOFF_GATE_MIN_ROUND,
    seg_check_p1_blood_budget_refresh,
)
from sr_od.application.currency_war.decision_v2 import candidates as cands_mod
from sr_od.application.currency_war.decision_v2 import handoff as handoff_mod
from sr_od.application.currency_war.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision_v2.candidates import (
    Candidate,
    _buy_tag,
)
from sr_od.application.currency_war.decision_v2.discipline import (
    blood_budget_refresh_blocked,
    p1_directed_downgrade_active,
    p1_exit_blood_short,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

logging.disable(logging.CRITICAL)


def _p1_state(hp: int = 40, round_num: int = 7, node: str = 'battle',
              gold: int = 100) -> GameState:
    """P1 末窗备战帧(默认 hp=40 ∈ (25,60) 血预算不足带)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 1, 6, gold, hp
    st.round_num = round_num
    st.node_type = node
    return st


def _non_target_name() -> str:
    """注册表内非引擎件名(避开 _target_names 的引擎全集)。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        engine_char_names,
    )
    engines = set(engine_char_names())
    for name in CHARACTERS:
        if name not in engines:
            return name
    raise AssertionError('注册表内无非引擎件名(测试构造前提失效)')


def _p1_allin_sess() -> StrategySession:
    """带 P1 槽序表(9 槽)的 session——plane_last_battle 真值源。"""
    s = StrategySession()
    s.plane_node_table = ['battle'] * 9
    return s


# ---------- P1-a/P1-c 共用辖域谓词 ----------

def test_p1_exit_blood_short_band() -> None:
    """末窗起点/线值/位面边界:r≥6 ∧ hp<60 ∧ plane=1(设计件 12 §2.2)。"""
    reg = DEFAULT_REGISTRY
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
    sess = StrategySession()
    reg = DEFAULT_REGISTRY
    assert blood_budget_refresh_blocked(_p1_state(hp=40), sess, reg)
    assert not blood_budget_refresh_blocked(_p1_state(hp=25), sess, reg)
    assert not blood_budget_refresh_blocked(_p1_state(hp=24), sess, reg)
    allin = _p1_state(hp=40, round_num=9, node='boss')
    assert not blood_budget_refresh_blocked(allin, _p1_allin_sess(), reg)
    p2 = _p1_state()
    p2.plane = 2
    assert not blood_budget_refresh_blocked(p2, sess, reg)
    reg_off = dataclasses.replace(
        DEFAULT_REGISTRY, blood_budget_refresh_stop_enabled=False)
    assert not blood_budget_refresh_blocked(_p1_state(hp=40), sess, reg_off)


def test_terminal_frame_release_counterexample() -> None:
    """终止帧反例(设计 W659 v2 §2.3/§3.1;ADR-0469):hp=26 行进带
    boss 单链(rung1,p_boss=0.027≤ε=0.03)→ 终止分支触发,双门开帧
    刷新停付解除;同帧降格短路。hp=26>应急线,豁免来自终止分支而非
    急救面——语义取代的显形锚。"""
    from sr_od.application.currency_war.decision_v2.discipline import (
        terminal_release,
    )
    sess = _p1_allin_sess()
    sess.plane_node_table = ['battle'] * 7 + ['encounter', 'boss']
    st = _p1_state(hp=26, round_num=8)
    st.deployed = [BenchChar(slot=i + 1, char_id='艾丝妲' if i == 0
                             else '椒丘', faction='仙舟')
                   for i in range(2)]
    assert terminal_release(st, sess, DEFAULT_REGISTRY)
    assert not blood_budget_refresh_blocked(st, sess, DEFAULT_REGISTRY)
    assert not p1_directed_downgrade_active(st, DEFAULT_REGISTRY,
                                            session=sess)


def test_downgrade_active_flag() -> None:
    """P1-a 触发面=辖域谓词 ∧ 降格开关(flag off=A/B 对照臂)。"""
    reg = DEFAULT_REGISTRY
    assert p1_directed_downgrade_active(_p1_state(hp=40), reg)
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
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
    st.bench[0] = BenchChar(slot=1, char_id=name, faction='仙舟')
    card = ShopCard(x=0, name=name, cost=3, faction='仙舟')
    sess = StrategySession()
    # 血预算不足帧:定向授权降格,无 'copy' 标签(落入后续通道或 None)
    assert _buy_tag(card, st, sess, DEFAULT_REGISTRY) != 'copy'
    # 对照臂(降格开关 off):gap 豁免照常生成定向 'copy'
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  p1_exit_downgrade_enabled=False)
    assert _buy_tag(card, st, sess, reg_off) == 'copy'
    # 非末窗(r5):gap 恒 0 语境被 monkeypatch,但降格辖域含末窗轮判
    # ——末窗外降格不辖,定向 'copy' 照常(零漂移面)
    st5 = _p1_state(hp=40, round_num=5)
    st5.bench[0] = BenchChar(slot=1, char_id=name, faction='仙舟')
    assert _buy_tag(card, st5, sess, DEFAULT_REGISTRY) == 'copy'


# ---------- P1-c:refresh 收尾拒付 ----------

def _refresh_cand() -> Candidate:
    return Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')


def test_arbitrate_refresh_rejected_in_band() -> None:
    """端到端:血预算不足帧正分刷新候选被拒(拒因带血预算停手)+
    拒付计数 +1;M-A 定向刷新局耗不消耗(预算零消耗)。"""
    sess = StrategySession()
    st = _p1_state(hp=40)
    res = arbitrate([(_refresh_cand(), 5.0, {})], st, sess,
                    DEFAULT_REGISTRY)
    assert not res.actions
    assert any('搜索型刷新停拒' in (row.get('reject') or '')
               for row in res.log)
    assert sess.v3_blood_budget_refresh_rejects == 1
    assert getattr(sess, 'v3_dir_refresh_used', 0) == 0


def test_arbitrate_refresh_rescued_in_emergency_band() -> None:
    """急救型豁免反例:应急带帧(hp≤emergency_hp)同构造刷新照常放行
    (搜牌补板当轮转化;[31]④ 合法用途),拒付计数不增。"""
    sess = StrategySession()
    st = _p1_state(hp=_P1_EMERGENCY_HP - 1)
    res = arbitrate([(_refresh_cand(), 5.0, {})], st, sess,
                    DEFAULT_REGISTRY)
    assert any(isinstance(a, RefreshShop) for a in res.actions)
    assert sess.v3_blood_budget_refresh_rejects == 0


# ---------- 镜像常量 + 段级检查 ----------

def test_mirror_constants_match_registry() -> None:
    """cw_sim_checks 镜像常量 ↔ registry 单一源双向锁(漂移即红)。"""
    assert _P1_EXIT_BLOOD_TARGET == DEFAULT_REGISTRY.p1_exit_blood_target
    assert (_P1_HANDOFF_GATE_MIN_ROUND
            == DEFAULT_REGISTRY.handoff_gate_min_round)
    assert _P1_EMERGENCY_HP == DEFAULT_REGISTRY.emergency_hp


def _row(plane: int, hp: int, rn: int, node: str,
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
        _row(1, 80, 1, 'battle', 0),    # 局首:决策 hp=开局,不出
        _row(1, 70, 6, 'battle', 1),    # 决策 hp=80(线外)→ 不出
        _row(1, 45, 7, 'battle', 1),    # 决策 hp=70? 否——决策 hp=70→
        _row(1, 40, 8, 'battle', 2),    # 决策 hp=45 ∈ 带 → 违规事件
        _row(1, 20, 9, 'battle', 1),    # 决策 hp=40 但应急带豁免域?
        _row(1, 15, 9, 'boss', 3),      # 决策 hp=20(应急带)→ 急救豁免
    ]
    ev = seg_check_p1_blood_budget_refresh(rows)
    # 逐帧行为:r7 决策 hp=70 线外不出;r8 决策 hp=45 出 1 事件;
    # r9 battle 决策 hp=40 出事件(血预算不足,应急豁免只看 hp 不看节点)
    assert [e['round_num'] for e in ev] == [8, 9]
    assert ev[0]['hp'] == 45 and ev[0]['refreshes'] == 2
    # ALL IN 豁免:r9 boss 帧(决策 hp=20 应急带也不出,双豁免)
    rows_allin = [
        _row(1, 30, 8, 'battle', 0),
        _row(1, 28, 9, 'boss', 2),      # 决策 hp=30 ∈ 带 ∧ ALL IN → 豁免
    ]
    assert seg_check_p1_blood_budget_refresh(rows_allin) == []


def test_seg_check_terminal_bit_exemption() -> None:
    """账本终止位豁免(设计 W659 v2 §5.1 R4;ADR-0469):同带帧
    terminal_release=真 → 刷新为终止豁免辖内,不出事件;位假 → 照旧
    出事件;键缺省(旧批账本)按假处理,行为兼容。"""
    base = {'plane': 1, 'hp': 30, 'sim': {'node': 'battle'}}
    rows = [
        {**base, 'round_num': 7, 'terminal_release': True,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},
        {**base, 'round_num': 8, 'terminal_release': False,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},
        {**base, 'round_num': 9,
         'actions': [{'__type__': 'RefreshShop', 'cost': 2}]},  # 缺省=假
    ]
    ev = seg_check_p1_blood_budget_refresh(rows)
    assert [e['round_num'] for e in ev] == [8, 9]


# ---------- sim 账本披露键(单局冒烟,不锁分布) ----------

def test_sim_ledger_discloses_refresh_reject_key() -> None:
    """账本行 sim.blood_budget_refresh_rejects 键存在(批量聚合的
    数据源;单局冒烟,pool='fallback' 免快照依赖)。"""
    from sr_od.application.currency_war import cw_sim
    r = cw_sim.simulate_p1(0, pool='fallback', planes=2)
    assert r.ledger
    for row in r.ledger:
        assert 'blood_budget_refresh_rejects' in (row.get('sim') or {})
