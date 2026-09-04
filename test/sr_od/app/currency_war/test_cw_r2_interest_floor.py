"""修 R2 批测试:R2 预算门息线 floor 落码(P54/dd-026)。

锁(出处=P54-r2-interest-floor §③/§④ + dd-026-r2-interest-floor):
- floor 结构:门过帧的刷后投影金 ≥ 息线 g* + Σ预留卡价 ρ(刷新通道
  永不掉满息档 + 至少一张命中卡可买不破线,P54 §③ 两推论的帧级锁);
- 贴线拒刷:g* ≤ 金 < g*+ρ+c_eff 帧 ⇒ r1 过而 r2 关,不发射刷新
  (P40 R2 溢余段刷窗 n_max=0 的行为面);
- ρ 注册表派生:Σ预留卡价 = 合格集最低费卡价(CHARACTERS 现读),
  禁字面量;可追过滤与 R1 装配侧同一(2★ 出集/该级不出此费);
- cap 语境:g* 随 cap_resolved 参数化(息律投资 cap=10 局息线 100,
  防把 50 拍成域常数 = dd-026 备选 2 禁案的判别锁)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import refresh_prob
from sr_od.application.currency_war.strategies.impl.mandate_v1.audit import provisional
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import _r2_card_reserve
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.interest import (
    saturation_line,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    RefreshShop,
    ShopCard,
)

# ===== 测试基建(与 test_cw_zero_refresh_fix 同款桩)=====


def _comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _session(comp=None):
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )

    s = StrategySession()
    s.cw4_counters = {}
    s.target_comp = comp
    s.cw4_line_state = proof.LineState()
    return s


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _state(gold: int, level: int = 3) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2)
    st.shop = [ShopCard(x=100, name='垫', cost=3, star=1)]
    st.bench = []
    st.deployed = []
    return st


def _decide(state: GameState, session) -> list:
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )

    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, SimpleNamespace(ev_arm='full'))


class TestR2InterestFloor:

    @staticmethod
    def _floor(comp, level: int, bench: list) -> int:
        """帧内 floor = g*(默认局 cap_resolved=5) + ρ(合格集最低费)。"""
        return saturation_line(5) + _r2_card_reserve(
            tuple(_members(comp)), bench, [], GameState(
                gold=0, level=level, round_num=2))

    def _frame(self, gold: int):
        """长视界(j=1 浅缺口,lv3 1费账 ≈9)帧:R1 必过,R2 成唯一门。

        出处=test_cw_zero_refresh_fix.test_injected_value_opens_r1_into_r2
        同型帧构造(lv3、j=2 成员账 ≈9.4 ≤ V̄_net);视界回退先验
        (9,9,9)下 r≈26,V̄_net 远超账 ⇒ r1 恒开。
        """
        provisional.reset('V_GAP')
        provisional.inject('V_GAP', provisional.CalibValue(
            value=24.7, ci_lo=16.7, ci_hi=24.7, injected_form=True))
        comp = _comp()
        ms = _members(comp)
        bench = [_bc(ms[0]), _bc(ms[0], slot=2)]
        st = _state(gold)
        st.bench = bench + [_bc(m, slot=i + 3) for i, m in enumerate(ms[2:7])]
        return comp, st, _session(comp)

    def test_floor_respected_when_gate_opens(self):
        """floor 结构锁(帧级,P54 §③):门过帧的刷后投影金 ≥ g*+ρ
        ——刷新通道永不掉满息档;本帧金=60 > g*+ρ+刷价 ⇒ 发射。"""
        try:
            comp, st, sess = self._frame(60)
            acts = _decide(st, sess)
            rs = [a for a in acts if isinstance(a, RefreshShop)]
            assert rs, '门过帧应发射刷新(健康带下界 >0,P54 §④)'
            floor = self._floor(comp, 3, st.bench)
            assert st.gold - rs[0].cost >= floor
        finally:
            provisional.reset('V_GAP')

    def test_just_below_floor_rejected(self):
        """贴线拒刷(账本级):金 = g*+ρ(P40 刷窗 n_max=0)⇒ r1 过而
        r2 关,不发射刷新——旧值 b_target(0,0,0)=0 使此帧发射
        (gold≥2 病灶,P53 §④ 申报 1),floor 落码后为判别锁。"""
        try:
            comp = _comp()
            gold_at_floor = (saturation_line(5)
                             + _r2_card_reserve(tuple(_members(comp)),
                                                [], [], _state(0)))
            _c, st, sess = self._frame(gold_at_floor)
            acts = _decide(st, sess)
            assert not [a for a in acts if isinstance(a, RefreshShop)]
        finally:
            provisional.reset('V_GAP')

    def test_cap_resolved_parameterizes_floor(self):
        """cap 语境锁:g*=10×cap_resolved 随 session 覆写参数化——
        cap=10(息律投资语境)下金 60 < 100+ρ ⇒ 拒(50 非域常数,
        dd-026 备选 2「拍常数」禁案的判别锁)。"""
        try:
            comp, st, sess = self._frame(60)
            sess.cw4_cap_override = 10
            acts = _decide(st, sess)
            assert not [a for a in acts if isinstance(a, RefreshShop)]
        finally:
            provisional.reset('V_GAP')

    def test_card_reserve_is_registry_derived(self):
        """ρ 注册表派生锁:= 合格集最低费卡价(CHARACTERS 现读 min),
        可追过滤与 R1 装配侧同一(2★ 出集/该级不出此费),禁字面量。"""
        comp = _comp()
        ms = _members(comp)
        bench = [_bc(ms[0])]
        st = _state(60)
        st.bench = bench
        level = 3
        expected = min(
            int(CHARACTERS[m].cost) for m in ms
            if CHARACTERS.get(m) is not None and CHARACTERS[m].cost
            and refresh_prob(level, CHARACTERS[m].cost) > 0.0)
        got = _r2_card_reserve(tuple(ms), bench, [], st)
        assert got == expected
        # 反面 1:成员全部 2★ ⇒ 出合格集 ⇒ 0(兜底值,R1 先关,R2 不可达)
        star2 = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(ms)]
        assert _r2_card_reserve(tuple(ms), star2, [], st) == 0
        # 反面 2:场上副本并入计数域(bench∪deployed 同过滤)
        assert _r2_card_reserve(tuple(ms), [], star2, st) == 0
