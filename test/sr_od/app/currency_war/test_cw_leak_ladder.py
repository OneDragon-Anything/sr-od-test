"""T-165 泄金阶梯单帧锁(ADR-0604 判据锁;锁清单 = 设计方案 §4.3
本批归属 L1-L7 + 档 2 轮内新鲜度排除,方案正本指针 = ADR-0604 头注)。

锁清单(§4.3 表;本批 8 条):
- L1  档 1 可上场买发射(锁线 ∧ 必花域 ∧ vacancy ∧ 围栏可落非垫件)。
- L1b 档 1/出口③ 候选互斥切分(F12):垫件类(1★ 零重叠全额退)不归档 1。
- L2  档 2 压库买发射(线未齐帧不再被 stop_flag 关死;窗口=在产 ω 塌缩带)。
- L3  dominance 摘旗后线未齐帧发射 + 先于档 2(支配性优先序);prep 位
      M6 摘旗扩域可达性(m6_bench_full 拒因在 stop=False 帧显影)。
- L4  NORMAL 帧 P72 拒 → 档 1/档 2 同帧挂起(预留金不被击穿)。
- L5  档 2 买后 bench 满(投影下一帧)→ 不再发射(bench 硬闸)。
- LF  档 2 轮内新鲜度排除:同轮卖 X 买回 X 禁(模拟批#5 s108 实证)。
- L7  ALL IN 类别过滤:P21 域(kernel all_in_xp_domain_hit)内非支A XP
      经 P72 闸拒;支A 形态/域外帧放行(指标 G=0 的判据面)。

测试构造声明:档 2 锁帧以 ``mandate.dominance_buy_eligible`` 猴补关闭
承载——档 0(dominance)按 ADR-0604 §2 发射序申报物理先于档 2,且
摘旗后两臂候选集有包含关系(1★ 全额退非线内件同属两臂候选);L2/L5/
LF 钉的是档 2 自身闸链(档匹配/s_reserve/新鲜度/bench 硬闸),不声明
「该帧档 2 无条件可达」。围栏预检(kernel can_deploy_single)在 L1 帧
猴补放行——围栏语义归 kernel 锁
(test_cw_deploy_single_source 等)辖,本文件钉档 1 的接线。
"""
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

if TYPE_CHECKING:
    from sr_od.application.currency_war.kernel.cw_board_state import BoardState
from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_REGISTRY_CORE,
    TIER_TRANSITION,
    line_identity_tier,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUpShop,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.odds import (
    tier_search_window,
)

_COMP = '列车同行'


# ===== 测试基建(exit3 同族口径)=====


def _km() -> list[str]:
    return list(predicates.line_members(get_comp(_COMP)))


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _card(name: str, cost: int = 2, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _off_name(exclude: tuple[str, ...] = (), *, min_cost: int = 1) -> str:
    """线外且非核心/转线层的注册表角色名(档 1/档 2 候选;避开 C1/④
    候选身份,防邻近臂抢发射)。"""
    bad = set(exclude)
    for n, ch in CHARACTERS.items():
        if n in bad or (ch.cost or 0) < min_cost:
            continue
        tier = line_identity_tier(n)
        if tier in (TIER_REGISTRY_CORE, TIER_TRANSITION):
            continue
        return n
    raise AssertionError('注册表缺少合适线外角色(锁前提失效)')


def _session_stub(locked: bool = True, target_comp=None) -> SimpleNamespace:
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = target_comp if target_comp is not None else get_comp(_COMP)
    st.v3_intention = SimpleNamespace(
        locked_comp=(_COMP if locked else ''))
    return s


def _st(gold: int, cards, *, locked: bool = True, level: int = 5,
        deploy_cap: int | None = None, bench=None, deployed=None,
        plane: int = 2, hp: int = 60, xp=None) -> GameState:
    km = _km()
    if deployed is None:
        # 席位构造:cap=level(缺省)时上板 level−1 人 → vacancy≥1 且
        # arm0 的 level≥cap 短路(M3 三臂全静,防抢发射)。
        n_dep = max(level - 1, 0)
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(km[:n_dep])]
    st = GameState(gold=gold, level=level, round_num=2, hp=hp)
    st.level_readable = True
    st.plane = plane
    st.shop = list(cards)
    st.bench = list(bench) if bench is not None else []
    st.deployed = deployed
    if deploy_cap is not None:
        st.deploy_cap = deploy_cap
    if xp is not None:
        st.xp_progress = xp
    return st


def _decide(st: GameState, sess) -> object:
    return shop.decide_shop_action(st, sess, SimpleNamespace(ev_arm='full'))


def _tier_cost(level: int = 5) -> int:
    """在产 ω 塌缩带内的费档(窗口单一源 tier_search_window 现查,
    零拍定——费档随表走,不硬编码)。"""
    window = tier_search_window(level,
                                DEFAULT_REGISTRY.omega_collapse_ratio)
    if not window:
        raise AssertionError('level 5 塌缩带空(锁前提失效)')
    return sorted(window)[0]


# ===== L1:档 1 可上场买发射 =====


class TestL1DeployableBuy:

    def test_l1_press_buy_deployable_emits(self, monkeypatch):
        """锁 L1:锁线 ∧ 必花域 ∧ vacancy>0 ∧ bench_free≥1 ∧ 可上场非垫件
        在售 ⇒ BuyCard('press_buy_deployable') + hit 分键。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        km = _km()
        cand = _off_name(exclude=tuple(km))
        st = _st(60, [_card(cand, cost=2, star=2)])   # 2★=非垫件类,非支配候选
        sess = _session_stub(locked=True)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'press_buy_deployable'
        assert state_of(sess).cw4_counters.get('press_buy_deployable_hit') == 1

    def test_l1_filler_class_excluded_f12(self, monkeypatch):
        """锁 L1b(F12 候选互斥切分):垫件类(1★ 零重叠全额退)不归档 1
        ——filler_excluded 分键显影,发射让位出口③ 既有臂。(dominance
        猴补关:垫件类同属档 0 支配候选,不关则帧被档 0 先吃,F12 的
        档 1 侧排除面不可见——文件头构造声明同款。)"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        km = _km()
        cand = _off_name(exclude=tuple(km), min_cost=1)
        st = _st(60, [_card(cand, cost=1, star=1)])   # 1★=垫件类形态
        sess = _session_stub(locked=True)
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'press_buy_deployable')
        assert state_of(sess).cw4_counters.get(
            'press_buy_deployable_filler_excluded', 0) >= 1

    def test_l1_unlocked_frame_off(self):
        """档 1 锁线门(单一源 _ist.locked_comp):未锁帧不发射。"""
        km = _km()
        cand = _off_name(exclude=tuple(km))
        st = _st(60, [_card(cand, cost=2, star=2)])
        sess = _session_stub(locked=False)
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'press_buy_deployable')


# ===== L2/L5/LF:档 2 压库买(摘旗扩域 + 窗口维持 + 新鲜度)=====
# 帧构造声明:dominance 猴补关(档 0 物理先行,见文件头);未锁帧构造
# (档 1 锁线门天然关,隔离档 2 自身闸链)。


def _m6_frame(gold: int = 60, cand: str | None = None, *,
              bench=None, level: int = 5):
    km = _km()
    cost = _tier_cost(level)
    if cand is None:
        cand = _off_name(exclude=tuple(km), min_cost=cost)
    st = _st(gold, [_card(cand, cost=min(cost, gold - 1), star=1)],
             locked=False, level=level, bench=bench)
    sess = _session_stub(locked=False)
    return st, sess, cand


class TestL2L5LFM6Compression:

    def test_l2_m6_fires_on_unformed_line(self, monkeypatch):
        """锁 L2:线未齐 ∧ 必花域 ∧ bench_free≥1 ∧ 塌缩带档匹配件在售
        ⇒ BuyCard('m6_stockpile')——摘旗前 stop_flag=False 帧该臂整体
        关死(本批病灶三合取之二),摘旗后发射。"""
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        st, sess, _cand = _m6_frame(gold=60)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'm6_stockpile'
        # 席位闸拒因零显影(发射帧)
        assert state_of(sess).cw4_counters.get('m6_bench_full', 0) == 0

    def test_l5_bench_full_stops_after_buy(self, monkeypatch):
        """锁 L5:档 2 买入(bench_free=1→0 投影)后下一帧不再发射
        (bench 硬闸;框架 simulate 纯投影推进)。"""
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        from sr_od.application.currency_war.kernel import cw_state
        km = _km()
        cost = _tier_cost()
        cand = _off_name(exclude=tuple(km), min_cost=cost)
        fill = [_bc(f'压库垫件{i}', star=1, slot=i + 1) for i in range(8)]
        st, sess, _ = _m6_frame(gold=60, cand=cand, bench=fill)
        act1 = _decide(st, sess)
        assert isinstance(act1, BuyCard) and act1.reason == 'm6_stockpile'
        st2 = cw_state.simulate(st, act1)
        act2 = _decide(st2, sess)
        assert not (isinstance(act2, BuyCard)
                    and act2.reason == 'm6_stockpile')

    def test_lf_round_sold_excluded(self, monkeypatch):
        """锁 LF(档 2 轮内新鲜度排除):同轮卖 X → 档 2 不买回 X
        (m6_round_sold_excluded 分键);未卖的同档名照常发射——排除
        面按名精确,非整臂关死(设计方案 §1.2 档 2;s108 实证)。"""
        monkeypatch.setattr(mandate, 'dominance_buy_eligible',
                            lambda *a, **kw: False)
        km = _km()
        cost = _tier_cost()
        sold = _off_name(exclude=tuple(km), min_cost=cost)
        st, sess, _ = _m6_frame(gold=60, cand=sold)
        # 同轮卖出登记(写端单元面;发射位写点 = shop._note_sell 收口 +
        # prep 凑息/M4,由 LF-写端锁另行覆盖)
        mandate.record_round_sold(sess, st, sold)
        act = _decide(st, sess)
        assert not (isinstance(act, BuyCard)
                    and act.reason == 'm6_stockpile')
        assert state_of(sess).cw4_counters.get(
            'm6_round_sold_excluded', 0) >= 1
        # 对照:另一未卖名(同费档)照常发射
        other = _off_name(exclude=tuple(km) + (sold,), min_cost=cost)
        st2, sess2, _ = _m6_frame(gold=60, cand=other)
        act2 = _decide(st2, sess2)
        assert isinstance(act2, BuyCard) and act2.reason == 'm6_stockpile'

    def test_lf_round_registry_expiry(self):
        """新鲜度载体键式相位过期:跨轮/跨位面读数空集(排除上界 ≤1 轮)。"""
        sess = SimpleNamespace()
        st = GameState(gold=10, level=5, round_num=3)
        st.plane = 2
        mandate.record_round_sold(sess, st, '甲')
        assert mandate.round_sold_names(sess, st) == frozenset({'甲'})
        st.round_num = 4
        assert mandate.round_sold_names(sess, st) == frozenset()
        st.round_num = 3
        st.plane = 3
        assert mandate.round_sold_names(sess, st) == frozenset()


# ===== L3:dominance 摘旗(档 0)+ prep 位 M6 摘旗可达性 =====


class TestL3FlagRemoval:

    def test_l3_dominance_fires_unformed_before_m6(self, monkeypatch):
        """锁 L3:线未齐帧 dominance 摘旗后发射,且同帧在售档匹配件时
        仍 dominance 先发(支配性优先序先于带参档 2,设计方案 §1.2
        发射序申报;单动作契约下物理位次即优先序)。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        km = _km()
        cost = _tier_cost()
        tier_cand = _off_name(exclude=tuple(km), min_cost=cost)
        st = _st(60, [_card(tier_cand, cost=cost, star=1),
                       _card('燃料件X', cost=1, star=1)],
                 locked=True)
        sess = _session_stub(locked=True)
        act = _decide(st, sess)
        assert isinstance(act, BuyCard) and act.reason == 'dominance_buy'

    def test_l3_prep_m6_reachable_without_stop_flag(self):
        """prep 位 M6 摘旗可达性:stop_flag=False(线未齐)∧ gold>g*
        ∧ 席满帧,M6 prep 块被触达(m6_bench_full 拒因显影)——摘旗前
        该帧 M6 prep 被 stop_flag 短路、拒因结构性不可见。"""
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            StrategySession,
        )
        sess = StrategySession()
        state_of(sess).cw4_counters = {}
        bench = [_bc(f'高价{i}', star=3, slot=i + 1) for i in range(9)]
        frame = mandate.MandateFrame(
            gold=60, level=3, bench=bench, deployed=[],
            deploy_cap=5, node_type=None, stop_flag=False,
            k_members=('目标件',), round_num=3)
        state = GameState(gold=60, level=3, round_num=3)
        state.hp = 60
        state.hp_readable = True
        mandate.run_mandate(frame, sess, state=state)
        assert state_of(sess).cw4_counters.get('m6_bench_full', 0) >= 1


# ===== L4:P72 拒帧档 1/2 挂起 =====


class TestL4BudgetGateSuspend:

    def test_l4_p72_reject_suspends_ladder(self, monkeypatch):
        """锁 L4(NORMAL 限定):P72 预算闸拒帧,档 1 挂起(预留金不被
        同帧击穿;复用 m6_budget_gate_suspend 先例,ADR-0560;FLOOR_ON
        让位随 hp 闸批,本帧为 NORMAL)。档 2 同帧挂起(m6_budget_gate_
        suspend 分键)同事实由 test_cw_budget_gate.TestShopM3M6
        承载,本测不再双锁。"""
        monkeypatch.setattr(shop, 'can_deploy_single',
                            lambda *a, **kw: (True, ''))
        km = _km()
        cand = _off_name(exclude=tuple(km))
        # arm0 触发形态(level 3 < cap 4,bench 线内候补 2 名)→ M3 评估
        # → P72 闸拒(整批金不足 10τ+ρ+Σ预留)→ _budget_gate_blocked
        st = _st(55, [_card(cand, cost=2, star=2)], locked=True,
                 level=3, deploy_cap=4,
                 deployed=[_bc(km[0], star=2, slot=1),
                           _bc(km[1], star=2, slot=2)],
                 bench=[_bc(km[2], slot=3), _bc(km[3], slot=4)],
                 xp=(0, 8))
        sess = _session_stub(locked=True)
        act = _decide(st, sess)
        assert not isinstance(act, (BuyCard, LevelUpShop))
        assert state_of(sess).cw4_counters.get(
            'press_buy_deployable_budget_suspend', 0) >= 1


# ===== L7:ALL IN 类别过滤(P21 域辖;XP 仅支A 合法)=====


class TestL7AllInCategoryFilter:

    def _allin_state(self, hp: int, *, readable: bool = True) -> GameState:
        """GameState 帧(mandate_v1 闸入口仍持 GameState,闸内经桥装箱;
        位面/节点语义同 _allin_bs)。"""
        st = GameState(gold=30, level=5, round_num=7, node_type='boss',
                       hp=hp)
        st.plane = 2
        st.hp_readable = readable
        st.hp_trusted = False
        return st

    def _allin_bs(self, hp: int | None, *, source: str = 'observation'
                  ) -> 'BoardState':
        """P21 域判据容器帧(波 2 起门输入 = BoardState):P2r7 boss 帧,
        来源三态 = 旧两位语义的容器形态(observation=真读/prior=不可信)。"""
        from sr_od.application.currency_war.kernel.cw_board_state import (
            BS_SCHEMA_VERSION,
            BoardState,
            ChannelSig,
            NodeKey,
        )
        sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
        bs = BoardState(schema_version=BS_SCHEMA_VERSION)
        if hp is not None:
            if source == 'observation':
                bs.observe(bs.hp, hp, sig=sig)
            elif source == 'prior':
                bs.write_prior(bs.hp, hp, evidence='prior:adr-0559', sig=sig)
            else:
                raise ValueError(f'未知 source {source!r}')
        bs.observe(bs.node, NodeKey(plane=2, round_num=7, kind='boss'),
                   sig=sig)
        return bs

    def _allin_session(self) -> SimpleNamespace:
        s = SimpleNamespace()
        s.node_type_current = 'boss'
        s.plane_node_table = [object()] * 7   # P2 真长 7(语料实证)
        return s

    def test_l7_domain_predicate_p21(self):
        """辖域判据(kernel 单一源):ALL IN boss 末轮 ∧ hp 真值可信
        ∧ 门后 hp ≤ 停升级线 → 域内;域外/不可信/None 帧不过滤(§7.4 域外
        不动 + [18] 豁免在不可信帧仍生效)。"""
        from sr_od.application.currency_war.kernel.cw_discipline_rules import (
            all_in_xp_domain_hit,
        )
        sess = self._allin_session()
        assert all_in_xp_domain_hit(self._allin_bs(10), sess,
                                    DEFAULT_REGISTRY) is True
        assert all_in_xp_domain_hit(self._allin_bs(100), sess,
                                    DEFAULT_REGISTRY) is False
        # 不可信帧(prior 支,旧两位皆 False 的容器形态)不过滤
        assert all_in_xp_domain_hit(self._allin_bs(10, source='prior'),
                                    sess, DEFAULT_REGISTRY) is False
        no_hp = self._allin_bs(None)
        assert all_in_xp_domain_hit(no_hp, sess,
                                    DEFAULT_REGISTRY) is False

    def test_l7_gate_rejects_non_support_xp(self):
        """P72 闸 ALL IN 支收窄:P21 域内非支A 帧 XP 拒(新拒因分键);
        支A 形态(板满 ∧ bench 2★)与域外帧维持全豁免。保底金门注
        (ADR-0603):「全豁免」指 (3a) 量闸——两形态另受豁免支花后
        ≥1 息档下界辖(本类场景 g=30 批 8 花后 22 ≥10,不受影响)。"""
        sess = self._allin_session()
        st = self._allin_state(10)
        ok, why = crit_levelup.levelup_budget_gate(
            st, sess, 30, 5, ('甲',), [], [], 2, 4)
        assert ok is False and why == 'all_in_xp_category_filtered'
        # 支A:板满(cap 5)+ bench 有 2★ 等待件 → 兑现链当帧可兑现
        deployed = [_bc(f'甲{i}', star=2, slot=i + 1) for i in range(5)]
        bench = [_bc('乙', star=2, slot=1)]
        ok2, why2 = crit_levelup.levelup_budget_gate(
            st, sess, 30, 5, ('甲', '乙'), bench, deployed, 2, 4)
        assert ok2 is True and why2 == ''
        # 域外(hp>停线):全豁免放行
        st_out = self._allin_state(100)
        ok3, why3 = crit_levelup.levelup_budget_gate(
            st_out, sess, 30, 5, ('甲',), [], [], 2, 4)
        assert ok3 is True and why3 == ''
