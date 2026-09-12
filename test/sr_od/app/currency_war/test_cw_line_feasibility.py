# -*- coding: utf-8 -*-
"""P2 锁线可行性加权(供给概率×剩余轮×血预算)+ 商店拒因投影口径锁。

设计出处:
- 锁线可行性三维 = cw_intention.p2_supply_horizon /
  line_completion_feasibility(H=min(位面剩余节点, ⌈hp/vd_p2_loss⌉);
  G=∏ 1−(1−q_m)^H,q 从 cw_shop_odds 注册表派生);判据阈值复用
  registry.revoke_miss_tolerance_eps,零新自由参数。
- 消费位(update_intention,均辖 plane==2):P2 移交强锁候选门槛 /
  P2 信号缓锁门 / 已锁线出口③「供给不可行降级」(降级到 unlocked,
  下一轮由 dd-033 handoff_lock 重锁可行线;不写 evicted=可逆,
  un-evict 同款)。
- 背景=sim_findings/R5 死法族:主死因为锁线目标件供给空缺(锁线波
  线内件出现率 16.7%),出口①证据门槛 N_req(3费@lv7=21 轮)在 P2
  7 轮视界内不可达,死守不可达线到 hp0+持金≥100。
- shop_unbought_reasons 帧内投影修复:买/卖/拖拽同步投影席与回金,
  波内席满误标 missing_no_path → missing_bench_full(归因保真)。
"""
from __future__ import annotations

import math
from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
    shop_unbought_reasons,
)
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel import cw_intention as ci
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionSignal,
    IntentionState,
    line_completion_feasibility,
    p2_supply_horizon,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)

#: P2 位面轮数真值(ADR-0366 语料:P2=7)。
_P2_SESSION = SimpleNamespace(plane_node_table=[1] * 7)


def _state(plane: int = 2, round_num: int = 1, hp: int = 40,
           level: int = 7, gold: int = 0, **extra) -> BoardState:
    """W6 波3:可行性/意向面已切容器签名,旧帧经过渡桥装箱。
    extra = 其余字段(shop/bench 等);桥为一次性快照,变异须重建帧。"""
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.hp = hp
    st.level = level
    st.gold = gold
    for _k, _v in extra.items():
        setattr(st, _k, _v)
    return board_state_bridge(st)


def _locked_ist(comp_name: str) -> IntentionState:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = comp_name
    ist.lock_layer = 3
    ist.lock_plane = 2
    ist.lock_round = 1
    return ist


# ---------- 视界 H(剩余轮 × 血预算,注册表派生) ----------

def test_p2_supply_horizon_derivation():
    """H = min(位面剩余节点, ⌈hp/vd_p2_loss⌉);血预算用 registry 单一源。"""
    vd = DEFAULT_REGISTRY.vd_p2_loss
    st = _state(plane=2, round_num=1, hp=41)
    # ceil(41/20.05)=3,位面剩余 7 → 取 3
    assert p2_supply_horizon(st, _P2_SESSION, None) == 3
    st = _state(plane=2, round_num=1, hp=200)   # ceil(200/20.05)=10 > 7 → 位面剩余封顶
    assert p2_supply_horizon(st, _P2_SESSION, None) == 7
    st = _state(plane=2, round_num=1, hp=5)     # 濒死:ceil(5/20.05)=1
    assert p2_supply_horizon(st, _P2_SESSION, None) == 1
    st = _state(plane=2, round_num=1, hp=0)     # hp≤0 → 视界为零
    assert p2_supply_horizon(st, _P2_SESSION, None) == 0
    assert vd == 20.05   # 注册表锚(单一源,禁散写第二份)


# ---------- 线完成率 G(供给概率维,闭式对账) ----------

def test_line_completion_feasibility_closed_form():
    """G = ∏_缺件 1−(1−q)^H,与手工闭式逐位一致;在店/到手件 F=1;
    等级不出该费(refresh_prob=0)→ G=0。"""
    comp = get_comp('希儿量子')
    st = _state(plane=2, round_num=1, hp=41, level=7)
    h = p2_supply_horizon(st, _P2_SESSION, None)
    expect = 1.0
    for m in comp.core_chars:
        q = ci._core_miss_q(m, 7)
        expect *= 1.0 - (1.0 - q) ** h
    got = line_completion_feasibility(st, comp, _P2_SESSION, None)
    assert math.isclose(got, expect, rel_tol=1e-12)
    # 在店核心:该件 F=1(当轮可买),G 只剩其余缺件
    st = _state(plane=2, round_num=1, hp=41, level=7,
                shop=[ShopCard(x=0, name='希儿', cost=3)])
    got_vis = line_completion_feasibility(st, comp, _P2_SESSION, None)
    expect_vis = 1.0
    for m in comp.core_chars:
        if m == '希儿':
            continue
        q = ci._core_miss_q(m, 7)
        expect_vis *= 1.0 - (1.0 - q) ** h
    assert math.isclose(got_vis, expect_vis, rel_tol=1e-12)
    assert got_vis > got
    # 等级 1:3 费+核心不出 → q=0 → G=0(先验零)
    st_l1 = _state(plane=2, round_num=1, hp=100, level=1)
    assert line_completion_feasibility(st_l1, comp, _P2_SESSION, None) == 0.0


# ---------- 出口③:供给不可行降级(P2 死守不可达线的解法) ----------

def _fake_q_by_line(low_chars: set[str], high_chars: set[str]):
    """受控 q 桩:low 线缺件几乎不出(G≤ε),high 线缺件高概率出(G>ε)。"""
    def fake(char_name: str, level: int) -> float:
        if char_name in high_chars:
            return 0.5
        if char_name in low_chars:
            return 0.01
        return 0.5
    return fake


def test_p2_exit3_supply_infeasible_downgrade(monkeypatch):
    """G_locked ≤ ε ∧ 存在 G_alt > ε ∧ 在店断供达阈 ⇒ 降级 unlocked +
    证据落档 + 同轮不重锁(一回合最多一次转移;下一轮 handoff_lock
    接管)。断供计数经两轮自然累积(有店无线内成员)。"""
    locked = get_comp('希儿量子')
    alt_cores: set[str] = set()
    for c in ci._v2_comps():
        if c.name != locked.name:
            alt_cores |= set(c.core_chars)
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), alt_cores))
    ist = _locked_ist('希儿量子')
    # 第 1 轮:有店无线内成员 → drought=1,先验 G≤ε 但证据未足,不撤
    st1 = _state(plane=2, round_num=2, hp=40, level=7,
                 shop=[ShopCard(x=0, name='娜塔莎', cost=2)])
    out1 = update_intention(st1, ist, _P2_SESSION, None)
    assert out1.phase == 'locked'
    assert ci._track(out1, '希儿量子').member_drought == 1
    # 第 2 轮:断供=2 达 PAIR_SUPPLY_CONFIRM_ROUNDS,且替代线核心(白厄)
    # 在店=已验证可达 → 出口③开
    st2 = _state(plane=2, round_num=3, hp=40, level=7,
                 shop=[ShopCard(x=0, name='娜塔莎', cost=2),
                       ShopCard(x=1, name='白厄', cost=4)])
    out = update_intention(st2, out1, _P2_SESSION, None)
    assert out.phase == 'unlocked'
    assert out.locked_comp == ''
    assert out.revoke_evidence['kind'] == 'supply_infeasible'
    assert out.revoke_evidence['alt_comp'] == '反甲白厄'
    assert out.revoke_evidence['g_alt'] > out.revoke_evidence['eps']
    assert out.revoke_evidence['member_drought'] == 2
    assert out.last_event.startswith('revoke:supply_infeasible:')
    # 可逆性契约:不写 evicted(现线缺件兑现后可经信号/移交重锁)
    assert '希儿量子' not in out.evicted
    # 同轮不重锁:phase 停在 unlocked(weak_comp 留降级来源遥测)
    assert out.weak_comp == '希儿量子'


def test_p2_exit3_negative_alt_core_not_visible(monkeypatch):
    """替代线核心不在店 ⇒ 无已验证可达的换线目标,不撤(G 略高于 ε
    的替代自己也完成不了,A/B s3 局实证为净伤害)。"""
    locked = get_comp('希儿量子')
    alt_cores: set[str] = set()
    for c in ci._v2_comps():
        if c.name != locked.name:
            alt_cores |= set(c.core_chars)
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), alt_cores))
    st = _state(plane=2, round_num=3, hp=40, level=7,
                shop=[ShopCard(x=0, name='娜塔莎', cost=2)])   # 断供=2 但无替代核心
    ist = _locked_ist('希儿量子')
    # 先把断供累积到阈(第 1 轮)
    st1 = _state(plane=2, round_num=2, hp=40, level=7,
                 shop=[ShopCard(x=0, name='娜塔莎', cost=2)])
    out1 = update_intention(st1, ist, _P2_SESSION, None)
    assert out1.phase == 'locked'
    out = update_intention(st, out1, _P2_SESSION, None)
    assert out.phase == 'locked'
    assert out.locked_comp == '希儿量子'


def test_p2_exit3_negative_line_still_supplied(monkeypatch):
    """证据合取防误杀:G ≤ ε 但线内成员持续在店(活线,如引擎线)
    ⇒ 不撤——纯先验不可行不构成换线理由(A/B s3 局教训)。"""
    locked = get_comp('希儿量子')
    alt_cores: set[str] = set()
    for c in ci._v2_comps():
        if c.name != locked.name:
            alt_cores |= set(c.core_chars)
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), alt_cores))
    st = _state(plane=2, round_num=2, hp=40, level=7,
                shop=[ShopCard(x=0, name='符玄', cost=4)])
    # 线内非核心成员符玄在店:断供清零(G 仍 ≤ ε:其余缺件先验极低)
    ist = _locked_ist('希儿量子')
    out = update_intention(st, ist, _P2_SESSION, None)
    assert out.phase == 'locked'
    assert out.locked_comp == '希儿量子'


def test_p2_exit3_negative_all_lines_infeasible(monkeypatch):
    """全线不可行(无 G>ε 替代)不降级:换线是 ε 级噪声,P25 锁线价值
    保留(维持现任方向)。"""
    all_cores: set[str] = set()
    for c in ci._v2_comps():
        all_cores |= set(c.core_chars)
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(all_cores, set()))
    st = _state(plane=2, round_num=1, hp=40, level=7)
    ist = _locked_ist('希儿量子')
    out = update_intention(st, ist, _P2_SESSION, None)
    assert out.phase == 'locked'
    assert out.locked_comp == '希儿量子'


def test_p2_exit3_negative_core_visible(monkeypatch):
    """核心在店帧不辖:当轮可买(P25 核心出现即买),不降级。"""
    locked = get_comp('希儿量子')
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), set(locked.core_chars)))
    st = _state(plane=2, round_num=1, hp=40, level=7,
                shop=[ShopCard(x=0, name='希儿', cost=3)])
    ist = _locked_ist('希儿量子')
    out = update_intention(st, ist, _P2_SESSION, None)
    assert out.phase == 'locked'
    assert out.locked_comp == '希儿量子'


def test_p2_exit3_negative_plane3_scope(monkeypatch):
    """辖域=P2:plane 3 不出口③(强锁/降格终局语义不动)。"""
    locked = get_comp('希儿量子')
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), set(locked.core_chars)))
    st = _state(plane=3, round_num=1, hp=40, level=7)
    ist = _locked_ist('希儿量子')
    out = update_intention(st, ist, _P2_SESSION, None)
    assert out.phase == 'locked'


def test_p2_exit3_next_round_handoff_relock(monkeypatch):
    """降级次轮:dd-033 移交通道重锁可行线(换线闭环)。"""
    locked = get_comp('希儿量子')
    alt_cores: set[str] = set()
    for c in ci._v2_comps():
        if c.name != locked.name:
            alt_cores |= set(c.core_chars)
    monkeypatch.setattr(ci, '_core_miss_q', _fake_q_by_line(
        set(locked.core_chars), alt_cores))
    st = _state(plane=2, round_num=2, hp=40, level=7)
    ist = IntentionState()          # unlocked(上轮出口③产物形态)
    ist.weak_comp = '希儿量子'
    out = update_intention(st, ist, _P2_SESSION, None)
    assert out.phase == 'locked'
    # 重锁目标 = 上轮出口③指认的可行替代线(确定性换线,非信号运气)
    assert out.locked_comp != '希儿量子'
    assert out.last_event.startswith('handoff_lock:')


def test_p2_handoff_feasibility_gate(monkeypatch):
    """移交候选补 G>ε 门:全线不可行 ⇒ 无候选 ⇒ 保持 unlocked
    (dd-033 ⑤兜底语义;不可行线不进强锁)。"""
    monkeypatch.setattr(ci, 'line_completion_feasibility',
                        lambda *a, **k: 0.0)
    st = _state(plane=2, round_num=1, hp=40, level=7)
    out = update_intention(st, IntentionState(), _P2_SESSION, None)
    assert out.phase == 'unlocked'
    assert out.locked_comp == ''


# ---------- P2 信号缓锁门 ----------

def test_p2_signal_gate_blocks_infeasible_allows_core_visible(monkeypatch):
    """①/②类信号线核心不在店 ∧ G≤ε ⇒ 本轮不锁(缓锁);核心在店信号
    不辖(当轮可买,P25)→ 照锁。"""
    comp = get_comp('绯英欢愉')

    def fake_feas(state, c, session=None, registry=None, visible=None):
        # 全局不可行:任何线都不给可行分 → 缓锁后 handoff 也无候选可锁,
        # 缓锁语义可独立观测(不被移交重锁掩盖)
        return 0.01

    monkeypatch.setattr(ci, 'line_completion_feasibility', fake_feas)
    st = _state(plane=2, round_num=2, hp=40, level=7)
    sig = IntentionSignal(1, 'strategy', comp.name, 'test', 1.0)
    monkeypatch.setattr(ci, 'detect_signals', lambda s: [sig])
    out = update_intention(st, IntentionState(), _P2_SESSION, None)
    assert out.phase == 'unlocked'      # 缓锁:方向不落不可行线
    # 核心在店:门放行 → 锁定(P25 价值面,即使 G 低)
    st = _state(plane=2, round_num=1, hp=40, level=7,
                shop=[ShopCard(x=0, name=ci.intention_core(comp), cost=3)])
    out2 = update_intention(st, out, _P2_SESSION, None)
    assert out2.phase == 'locked'
    assert out2.locked_comp == comp.name


# ---------- 商店拒因投影口径(生产 cw4 面) ----------

def _bench(n: int) -> list[BenchChar]:
    out = []
    for i in range(n):
        ch = CHARACTERS['娜塔莎']
        out.append(BenchChar(slot=i, char_id='娜塔莎',
                             faction=(ch.factions or ['?'])[0],
                             position_pref=ch.position_pref()))
    return out


def test_shop_rejects_projects_bench_across_buys():
    """波内先买占掉末席后,同波后续线内件应归 missing_bench_full
    (旧口径误标 missing_no_path)。"""
    comp = None                       # transition 分类不辖,聚焦投影
    # shop_unbought_reasons 属 mandate_v1(波4 面,GameState 签名)——喂原始帧
    st = GameState()
    st.gold = 99
    st.bench = _bench(BENCH_CAPACITY - 1)     # 8/9,剩 1 席
    a = ShopCard(x=0, name='甲一', cost=3)
    b = ShopCard(x=1, name='乙二', cost=3)
    st.shop = [a, b]
    rejects = shop_unbought_reasons(st, comp, ('甲一', '乙二'),
                                    [BuyCard(card=a, reason='t')])
    assert '甲一' not in rejects            # 已买不进拒因
    assert rejects['乙二'] == 'missing_bench_full'   # 波内席满如实归因


def test_shop_rejects_projects_sell_refund_and_seat():
    """卖买同帧:卖出回金与席释放进投影——席满帧经 M4 腾席后线内件
    买入可行,不再留拒因。"""
    comp = None
    # 同上:mandate_v1 拒因面喂原始 GameState 帧
    st = GameState()
    st.gold = 5
    st.bench = _bench(BENCH_CAPACITY)         # 席满
    b = ShopCard(x=0, name='乙二', cost=5)
    st.shop = [b]
    sell = SellBench(bench_idx=0, income=2, expect='娜塔莎')
    rejects = shop_unbought_reasons(st, comp, ('乙二',),
                                    [sell, BuyCard(card=b, reason='t')])
    assert '乙二' not in rejects              # 卖 1 买 1:席/金投影可行已买
    # 反事实:同帧只卖不买(买入未发射)→ 席空金足,如实归 no_path 侧语义
    rejects2 = shop_unbought_reasons(st, comp, ('乙二',), [sell])
    assert rejects2['乙二'] == 'missing_no_path'
