"""W803 · P1 档位推进目标函数单帧锁组(PREREG_tier_push_AB v2 §5 六锁)。

设计出处:.debug/temp/currency_war/w803_tier_push_design/REPORT.md v2
(四件:缺口差分/r7 死线/散装门/r6 预算承诺)+ 同目录 PREREG v2 §5
(锁清单判前写死)+ W805 复核修正清单。决策 why=ADR-0494。

锁语义不锁牌面:成员名/散件名从注册表现场派生(断言策略决策行为,
不锁具体卡名)。开关组 p1_tier_push_*(伞+三子旗标)默认关 = 第 1 态
零漂移锚,每锁带 off 臂对照断言(策略开关生命周期第 3 态盘点义务:
开臂翻默认时按本锁组 off 臂清单重推语义)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)
from sr_od.application.currency_war.decision.decision_v2.tier_push import (
    candidate_gap_term,
    deadline_weight,
    gate_active,
    refresh_term,
)
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SEELE_AMP_FACTIONS,
    TRANSITION_TRAITS,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
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


def _flags_on(**kw) -> object:
    base = {
        'p1_tier_push_enabled': True,
        'p1_tier_push_gate_enabled': True,
        'p1_tier_push_deadline_enabled': True,
        'p1_tier_push_r6_budget_enabled': True,
    }
    base.update(kw)
    return dataclasses.replace(DEFAULT_REGISTRY, **base)


_REG_ON = _flags_on()
_REG_OFF = DEFAULT_REGISTRY

_ENGINE_KEY = dict(TRANSITION_TRAITS)
_EXPLORE_KEYS = frozenset(_ENGINE_KEY) | set(SEELE_AMP_FACTIONS)


def _line_members(cost: int | None = None) -> list[str]:
    """意向体系成员名(注册表派生,非牌面锁定)。"""
    return sorted(
        n for n, c in CHARACTERS.items()
        if ((set(c.factions or ()) | set(c.flows or ())) & _EXPLORE_KEYS
            and (cost is None or (c.cost or 0) == cost)))


def _scatter_names(cost: int | None = None) -> list[str]:
    """线外散件名(全部意向体系键零隶属;注册表派生)。"""
    return sorted(
        n for n, c in CHARACTERS.items()
        if (not ((set(c.factions or ()) | set(c.flows or ()))
                 & _EXPLORE_KEYS)
            and (cost is None or (c.cost or 0) == cost)))


def _sess() -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState()   # 探索期(未锁):四体系全域
    return s


def _st(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 6, 'streak': None,
            'board': {}, 'bench': [], 'shop': [], 'deployed': []}
    base.update(kw)
    return GameState(**base)


def _buy(name: str, cost: int, tag: str = 'pair',
         needs_slot: bool = False) -> Candidate:
    return Candidate(action=BuyCard(ShopCard(x=0, name=name, cost=cost)),
                     tag=tag, source='test', needs_slot=needs_slot)


# ===== 锁 0(开关组缺省态 + off 臂零漂移)=====

def test_lock0_switch_group_defaults_off_and_off_arm_zero() -> None:
    """伞+三子旗标默认全关(生命周期第 1 态);全部机制函数在默认
    registry 下恒 0/False(off 臂零漂移锚)。"""
    for f in ('p1_tier_push_enabled', 'p1_tier_push_gate_enabled',
              'p1_tier_push_deadline_enabled',
              'p1_tier_push_r6_budget_enabled'):
        assert getattr(DEFAULT_REGISTRY, f) is False
    st = _st()
    sess = _sess()
    members = _line_members()
    assert members
    cand = _buy(members[0], CHARACTERS[members[0]].cost or 1)
    assert candidate_gap_term(cand, st, st, sess, _REG_OFF) == 0.0
    assert refresh_term(st, sess, _REG_OFF) == 0.0
    assert gate_active(st, sess, _REG_OFF) is False


# ===== 锁 1 散装守门(PREREG #1)=====

def test_lock1_scatter_gate() -> None:
    """r4 起 max_bond_tier<2 帧拒纯散件买入(零缺口增量);首张豁免
    (与缺口差分同一 dist 函数)放行防自锁;r1-r3 生效域外门不辖;
    压库豁免 ≤2 费+每帧 ≤2 张;needs_slot(挤占门)不穿透豁免。"""
    sess = _sess()
    member = next(n for n in _line_members()
                  if CHARACTERS[n].cost not in (None, 0))
    member_cost = CHARACTERS[member].cost
    scatter3 = [n for n in _scatter_names(3)
                if n not in (member,)]
    scatter2 = [n for n in _scatter_names(2)]
    assert scatter3 and scatter2

    def _kept(cands: list[Candidate], st: GameState) -> list[str]:
        kept, _log = filter_candidates(cands, st, sess, _REG_ON)
        return [c.action.card.name for c in kept
                if isinstance(c.action, BuyCard)]

    # r4 档 0 帧:线内成员豁免(缺口前进),3 费纯散件拒
    st_r4 = _st(round_num=4)
    assert gate_active(st_r4, sess, _REG_ON)
    kept = _kept([_buy(member, member_cost),
                  _buy(scatter3[0], 3, tag='bond_fallback')], st_r4)
    assert kept == [member]
    # r1-r3 生效域外:空窗期豁免([31]①),散件不拒
    st_r2 = _st(round_num=2)
    assert not gate_active(st_r2, sess, _REG_ON)
    kept = _kept([_buy(scatter3[0], 3, tag='bond_fallback')], st_r2)
    assert kept == [scatter3[0]]
    # 压库豁免:2 费纯散件每帧 ≤2 张,第 3 张拒(逐轮计数轮内累计)
    st_p = _st(round_num=4)
    sess.v2_round_tp_press_key = None   # 轮键清零(测试隔离)
    kept = _kept([_buy(n, 2, tag='bond_fallback')
                  for n in scatter2[:3]], st_p)
    assert len(kept) == 2
    # 挤占门不穿透:needs_slot(bench 满需腾位)的 2 费候选不获豁免
    st_p2 = _st(round_num=4)
    sess.v2_round_tp_press_key = None
    kept, _log = filter_candidates(
        [_buy(scatter2[0], 2, tag='bond_fallback', needs_slot=True)],
        st_p2, sess, _REG_ON)
    assert kept == []
    # off 臂:门不辖,散件照旧走原链
    kept, _log = filter_candidates(
        [_buy(scatter3[0], 3, tag='bond_fallback')], st_r4, sess,
        _REG_OFF)
    assert [c.action.card.name for c in kept] == [scatter3[0]]


# ===== 锁 2 缺口差分排序 + 存量差分幂等(PREREG #2)=====

def test_lock2_gap_differential_ranking_and_idempotency() -> None:
    """同费档下「使意向引擎缺口缩小的候选」评分高于「线外正增量候选」
    (排序语义);同帧重复计算 ΔG 幂等(无跨帧累计账本——纯函数,
    二次调用同值且不改 state/session)。"""
    sess = _sess()
    member = next(n for n in _line_members(cost=2)
                  or _line_members(cost=1))
    cost = CHARACTERS[member].cost
    st = _st()
    member_cand = _buy(member, cost)
    scatter = _scatter_names(3)[0]
    scatter_cand = _buy(scatter, 3)
    v_member = score_candidate(member_cand, st, sess, _REG_ON)
    v_scatter = score_candidate(scatter_cand, st, sess, _REG_ON)
    assert v_member[0] > v_scatter[0]
    assert v_member[1]['tp_gap'] > 0
    assert 'tp_gap' not in v_scatter[1] \
        or v_scatter[1]['tp_gap'] == 0
    # 幂等:二次调用同值;off 臂恒 0(零漂移)
    g1 = candidate_gap_term(member_cand, st, st, sess, _REG_ON)
    g2 = candidate_gap_term(member_cand, st, st, sess, _REG_ON)
    assert g1 == g2
    assert candidate_gap_term(member_cand, st, st, sess, _REG_OFF) == 0.0


# ===== 锁 3 死线权重(PREREG #3)=====

def test_lock3_deadline_weight_shape() -> None:
    """r6 帧缺口差分权重 > r3 帧 > r8 帧(r8 残差仅 boss 分量);
    子旗标关恒 1.0(消融归因);单调递增至 r6、r7 后坍缩。"""
    sess = _sess()
    member = _line_members()[0]
    cand = _buy(member, CHARACTERS[member].cost or 1)
    w3 = deadline_weight(_st(round_num=3), _REG_ON)
    w6 = deadline_weight(_st(round_num=6), _REG_ON)
    w8 = deadline_weight(_st(round_num=8), _REG_ON)
    assert w6 > w3 > w8 > 0
    assert deadline_weight(_st(round_num=3), _REG_OFF) == 1.0
    # 权重作用于候选分:r6 分 > r3 分(同帧同候选)
    st3 = _st(round_num=3)
    st6 = _st(round_num=6)
    v3 = score_candidate(cand, st3, sess, _REG_ON)[1]['tp_gap']
    v6 = score_candidate(cand, st6, sess, _REG_ON)[1]['tp_gap']
    assert v6 > v3


# ===== 锁 4 r6 预算承诺 + 血线辖域门(PREREG #4)=====

def test_lock4_r6_budget_and_blood_gate() -> None:
    """r6 备战帧:缺口前进的买入可凭 EV 门放行击穿息线地板(预算承诺);
    血线恶化段(hp<报警线)授权否决([18] 报警线辖域);r5/r7 帧不在
    辖域;off 臂零漂移(同帧同候选被 HOARD 攒息拒)。"""
    sess = _sess()
    member = next(n for n in _line_members() if CHARACTERS[n].cost == 3) \
        or _line_members()[0]
    cost = CHARACTERS[member].cost or 3
    scatter = _scatter_names(3)[0]
    # 金 21-费 3=18 < form_floor 20:跨息档(p1_early 豁免不辖),无
    # 授权时地板拒;有 r6 授权(EV 门过)→ 击穿地板放行。
    # press 通道关(隔离授权面:同息档 [11] 前置臂不与地板判据竞争)。
    reg_r6 = dataclasses.replace(_REG_ON, press_channel_enabled=False)
    st_r6 = _st(round_num=6, gold=21)
    member_cand = _buy(member, cost, tag='line_opportunistic')
    scatter_cand = _buy(scatter, 3, tag='bond_fallback')
    v_m = score_candidate(member_cand, st_r6, sess, reg_r6)[0]
    v_s = score_candidate(scatter_cand, st_r6, sess, reg_r6)[0]
    res = arbitrate([(member_cand, v_m, {}),
                     (scatter_cand, v_s, {})],
                    st_r6, sess, reg_r6)
    rows = {r['desc']: r for r in res.log if '买' in r['desc']}
    m_rows = [r for d, r in rows.items() if member in d]
    s_rows = [r for d, r in rows.items() if scatter in d]
    assert m_rows and m_rows[0]['accepted'], m_rows
    assert (m_rows[0].get('ev_auth') or {}).get('tier_push_r6'), m_rows
    assert s_rows and not s_rows[0]['accepted'], s_rows
    # 血线恶化段:hp<报警线 → 授权否决(地板拒回归)
    st_low = _st(round_num=6, gold=21, hp=39)
    sess2 = _sess()
    v_m2 = score_candidate(member_cand, st_low, sess2, reg_r6)[0]
    res = arbitrate([(member_cand, v_m2, {})], st_low, sess2, reg_r6)
    m_rows = [r for r in res.log if '买' in r.get('desc', '')
              and member in r['desc']]
    assert m_rows and not m_rows[0]['accepted']
    # 辖域:r5 帧不在承诺域(off 臂同拒,零漂移)
    st_r5 = _st(round_num=5, gold=21)
    sess3 = _sess()
    v_m3 = score_candidate(member_cand, st_r5, sess3, reg_r6)[0]
    res = arbitrate([(member_cand, v_m3, {})], st_r5, sess3, reg_r6)
    m_rows = [r for r in res.log if '买' in r.get('desc', '')
              and member in r['desc']]
    assert m_rows and not m_rows[0]['accepted']


# ===== 锁 5 锁线语义不变(PREREG #5)=====

def test_lock5_intention_state_machine_untouched() -> None:
    """缺口差分项只改排序权重,不改意向锁定状态机:评分前后 ist 快照
    逐位一致(phase/p1_pair/transition_pair/last_event)。"""
    sess = _sess()
    ist = sess.v3_intention
    ist.phase = 'locked'
    ist.p1_pair = ('仙舟', '持续伤害')
    ist.last_event = 'p1_pair:仙舟+持续伤害'
    snapshot = dataclasses.asdict(ist)
    member = next(n for n in _line_members()
                  if CHARACTERS[n].cost not in (None, 0))
    st = _st(bench=[BenchChar(slot=0, char_id=member, star=1,
                              faction='列车同行')])
    score_candidate(_buy(member, CHARACTERS[member].cost or 1),
                    st, sess, _REG_ON)
    assert dataclasses.asdict(sess.v3_intention) == snapshot


# ===== 锁 6 off-lock 通道零触碰(PREREG #6)=====

def test_lock6_off_lock_kappa_channel_untouched() -> None:
    """κ 折扣为 W802 单一实现:本批不落任何对该通道的改写——缺口差分
    项加在降级之前,线外候选经既有通道被折扣;常数本体断言不改值
    (registry 字段缺省值回归)。"""
    assert DEFAULT_REGISTRY.realization_off_lock_kappa == 0.5
    assert DEFAULT_REGISTRY.off_lock_buy_penalty == 3.0
    sess = _sess()
    ist = sess.v3_intention
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    ist.p1_pair = ('列车同行', '持续伤害')
    member = next(n for n in _line_members(cost=3)
                  if n not in ('希儿',))
    scatter = _scatter_names(3)[0]
    st = _st(plane=1, round_num=5)
    # 线内候选不降级;线外候选(κ 关=常数罚 3.0)照旧降级
    member_cand = _buy(member, 3, tag='line_opportunistic')
    v_member = score_candidate(member_cand, st, sess, _REG_ON)
    assert 'off_lock' not in v_member[1]
    sc_cand = _buy(scatter, 3, tag='line_opportunistic')
    v_sc = score_candidate(sc_cand, st, sess, _REG_ON)
    v_sc_off = score_candidate(sc_cand, st, sess, _REG_OFF)
    assert v_sc[1].get('off_lock') == 'demote'
    assert v_sc_off[1].get('off_lock') == 'demote'
    # 零新增改写:on−off 分差恰等于本批缺口差分项(既有罚分/折扣通道
    # 两侧同值,不因本批变化)
    tp = v_member[1].get('tp_gap', 0.0)
    assert abs((v_member[0] - score_candidate(
        member_cand, st, sess, _REG_OFF)[0]) - tp) < 1e-6
