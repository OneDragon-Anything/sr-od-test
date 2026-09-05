"""必花域落码锁(20 号稿 v2.1;用户裁定 =「无论什么 hp,金这么多都是
要花的」§1 授权文号)。

覆盖:G_must 判据单一源(§2.1,买断制出辖)/ L2 第二触发源(∨ 合并,
触发源分键)/ L3 升级(停付线域内让位 = ADR-0528,资格硬闸照常,
拒因分键 level_cap/batch_unaffordable)/ R1 域内残形切分线(g*/L 账
降期望核算,可负担性留资格硬闸,合格集空守卫照旧)。
负向锁(物理残量白名单形态,§3.2):店空无垫件 ⇒ fuel_not_on_sale
零消费;等级 cap ⇒ level_cap 零消费;域外帧零变化。
"""
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_economy import (
    in_must_spend_zone,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUpShop,
    RefreshShop,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import shop
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
    line_members,
)

_COMP = '列车同行'


def _bc(name: str, star: int = 2, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _zone_frame(gold: int, *, cards=None, level: int = 5,
                locked: bool = True) -> tuple[GameState, SimpleNamespace]:
    """必花域帧:锁线列车同行、level=level、gold 必入域(g > 50)。"""
    comp = get_comp(_COMP)
    km = list(line_members(comp))
    chaseable = [m for m in km if m != '瓦尔特']
    deployed = [_bc(m, star=2, slot=i + 1)
                for i, m in enumerate(chaseable)]
    st = GameState(gold=gold, level=level, round_num=2, hp=60)
    st.level_readable = True
    st.plane = 2
    st.node_type = 'battle'
    st.shop = list(cards) if cards is not None else []
    st.bench = []
    st.deployed = deployed
    st.refresh_probs = {5: 0}
    sess = SimpleNamespace(
        cw4_counters={},
        target_comp=comp,
        v3_intention=SimpleNamespace(
            locked_comp=(_COMP if locked else '')))
    return st, sess


def _decide(st, sess):
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


class TestZonePredicate:

    def test_zone_predicate_bounds(self):
        """G_must = 10×cap_resolved:g 越线 True/等值 False;买断制
        (cap=0)出辖恒 False。"""
        sess = SimpleNamespace(cw4_cap_override=None)
        assert in_must_spend_zone(51, sess) is True
        assert in_must_spend_zone(50, sess) is False
        buyout = SimpleNamespace(cw4_cap_override=0)
        assert in_must_spend_zone(999, buyout) is False
        rich = SimpleNamespace(cw4_cap_override=10)
        assert in_must_spend_zone(101, rich) is True
        assert in_must_spend_zone(100, rich) is False


class TestL2SecondTrigger:

    def test_zone_triggers_l2_despite_chaseable(self):
        """L2 第二触发源:必花域帧 A 支不辖(可追成员在场,Φ_stall 不
        成立)⇒ 仍发射垫件买 + must_spend_l2_trigger 分键。"""
        km = list(line_members(get_comp(_COMP)))
        pad = next(n for n, ch in __import__(
            'sr_od.application.currency_war.data.cw_chars',
            fromlist=['CHARACTERS']).CHARACTERS.items()
            if n not in km)
        st, sess = _zone_frame(
            gold=80, cards=[ShopCard(x=100, name=pad, cost=1, star=1)])
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'fuel_filler_stall'
        assert sess.cw4_counters.get('must_spend_l2_trigger') == 1
        assert 'fuel_filler_stall_buy' in sess.cw4_counters

    def test_outside_zone_no_l2(self):
        """负向对照:域外同形态(A 支不成立)⇒ 零发射(域外逐位零变化)。"""
        st, sess = _zone_frame(gold=40)   # gold 40 < 50 出域;店空
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')
        assert 'must_spend_l2_trigger' not in sess.cw4_counters

    def test_whitelist_empty_shop_no_consume(self):
        """白名单①:店空无垫件 ⇒ fuel_not_on_sale 分键零消费(不炸)。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = _decide(st, sess)
        assert sess.cw4_counters.get('fuel_not_on_sale') == 1
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'fuel_filler_stall')


class TestL3MustSpend:

    def test_zone_l3_consumes_when_arms_idle(self):
        """L3:必花域 ∧ M3 三臂空闲 ⇒ LevelUpShop(触发源分键
        auth_basis='m3_batch:must_spend')。"""
        st, sess = _zone_frame(gold=80, cards=[])
        act = _decide(st, sess)
        assert isinstance(act, LevelUpShop)
        assert act.auth_basis == 'm3_batch:must_spend'

    def test_l3_level_cap_rejects(self):
        """负向(白名单② 等级已到 cap):lv9 族硬闸 ⇒ level_cap 分键,
        零升级消费。帧 = 未锁线(R1 合格集空先拦刷新,域内降排序不越
        (ii) 守卫)+ level=9(lv9 cap 硬闸)⇒ L3 到位被资格硬闸拒。"""
        st, sess = _zone_frame(gold=80, cards=[], level=9, locked=False)
        st.deployed = [_bc(m, star=2, slot=i + 1)
                       for i, m in enumerate(line_members(get_comp(_COMP)))]
        act = _decide(st, sess)
        assert not isinstance(act, LevelUpShop)
        assert sess.cw4_counters.get('level_cap') == 1


class TestR1ZoneSplit:

    def test_r1_account_veto_demoted_in_zone(self):
        """R1 切分线:必花域内 account_over_budget 核算否决降排序——
        分层全 ladder 走完后零消费以 CloseShop 收口,且核算否决分键
        不在案(域外同形帧会记 account_over_budget)。"""
        km = list(line_members(get_comp(_COMP)))
        chaseable1 = km[0]   # 可追成员留 1★ ⇒ 合格集非空(D≠∅ 过)
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(km) if m != chaseable1]
        bench = [_bc(chaseable1, star=1, slot=1)]
        st = GameState(gold=51, level=9, round_num=2, hp=60)
        st.level_readable = True
        st.plane = 2
        st.node_type = 'battle'
        st.shop = []
        st.bench = bench
        st.deployed = deployed
        st.refresh_probs = {}
        st.shop_refresh_cost = 2
        sess = SimpleNamespace(cw4_counters={}, target_comp=get_comp(_COMP),
                               v3_intention=SimpleNamespace(
                                   locked_comp=_COMP))
        act = _decide(st, sess)
        # ladder 显影:L2 垫件缺 + L3 等级 cap(vl9 族硬闸)均零消费
        assert sess.cw4_counters.get('fuel_not_on_sale') == 1
        assert sess.cw4_counters.get('level_cap') == 1
        # 切分线生效:核算否决(g*/L 账)未拦 R1(域外同形帧会记该键)
        assert 'shop_r1_account_over_budget' not in sess.cw4_counters
        assert not isinstance(act, RefreshShop)   # 可负担性硬闸仍辖(金 51)
        from sr_od.application.currency_war.kernel.cw_state import CloseShop
        assert isinstance(act, CloseShop)

    def test_r1_no_chaseable_guard_stays(self):
        """负向:合格集空守卫((ii) fail-closed)必花域内照旧——不因
        切分线放行刷新。帧 = 未锁线(k_members 口径:线成员全 2★ ⇒
        合格集空),R1 不需锁线,L3 被 lv9 cap 硬闸拦。"""
        km = list(line_members(get_comp(_COMP)))
        deployed = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(km)]
        st = GameState(gold=120, level=9, round_num=2, hp=60)
        st.level_readable = True
        st.plane = 2
        st.node_type = 'battle'
        st.shop = []
        st.bench = [_bc('瓦尔特', star=2, slot=1)]
        st.deployed = deployed
        st.refresh_probs = {}
        st.shop_refresh_cost = 2
        sess = SimpleNamespace(cw4_counters={}, target_comp=get_comp(_COMP))
        act = _decide(st, sess)
        assert not isinstance(act, RefreshShop)
        assert sess.cw4_counters.get(
            'shop_r1_no_chaseable_member') == 1

    def test_r1_budget_fail_liveness_key(self):
        """刷新臂 liveness 显影(52 轮 sim 设计输入②):域内刷新尝试被
        可负担性硬闸拦 ⇒ must_spend_r1_budget_fail 显式分键(禁恒零
        盲区,directed_refresh_game_cap_lock 绿灯掩盖恒零教训)。"""
        st, sess = _zone_frame(gold=51, level=9, cards=[])
        act = _decide(st, sess)
        assert not isinstance(act, RefreshShop)
        assert sess.cw4_counters.get('must_spend_r1_budget_fail') == 1
