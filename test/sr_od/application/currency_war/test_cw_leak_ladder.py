"""泄金阶梯单帧锁(ADR-0604 判据锁;锁清单 = 设计方案 §4.3
本批归属 L1-L7 + 档 2 轮内新鲜度排除,方案正本指针 = ADR-0604 头注)。

锁清单(§4.3 表存续面):
- LF′ 档 2 轮内新鲜度排除载体相位过期:跨轮/跨位面读数空集(排除
      上界 ≤1 轮;发射位排除面归写端与消费位锁辖)。
- L3′ prep 位 M6 摘旗可达性:stop_flag=False(线未齐)∧ gold>g* ∧
      席满帧,M6 prep 块被触达(m6_bench_full 拒因显影——摘旗前该帧
      被 stop_flag 短路、拒因结构性不可见)。
- L7  ALL IN 类别过滤:P21 域(kernel all_in_xp_domain_hit)内非支A XP
      经 P72 闸拒;支A 形态/域外帧放行(指标 G=0 的判据面)。

测试构造声明:候选/帧构造基建(_km/_bc/_card/_off_name/_session_stub/
_st)保留 = test_cw_press_narrow_transition 的候选构造单一源(跨文件
消费);L1/L1b/L2/L3/L5/LF 发射面锁与档 1 锁线门负腿已退役。
"""
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

if TYPE_CHECKING:
    from sr_od.application.currency_war.kernel.cw_game_state import GameState
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bsb,
)

from sr_od.application.currency_war.kernel.cw_card_identity import (
    TIER_REGISTRY_CORE,
    TIER_TRANSITION,
    line_identity_tier,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    CwSimFrame,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
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
        plane: int = 2, hp: int = 60, xp=None) -> CwSimFrame:
    km = _km()
    if deployed is None:
        # 席位构造:cap=level(缺省)时上板 level−1 人 → vacancy≥1 且
        # arm0 的 level≥cap 短路(M3 三臂全静,防抢发射)。
        n_dep = max(level - 1, 0)
        deployed = [_bc(m, star=2, slot=i + 1)
                    for i, m in enumerate(km[:n_dep])]
    st = CwSimFrame(gold=gold, level=level, round_num=2, hp=hp)
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


# ===== LF′:档 2 轮内新鲜度排除载体相位过期 =====


class TestL2L5LFM6Compression:

    def test_lf_round_registry_expiry(self):
        """新鲜度载体键式相位过期:跨轮/跨位面读数空集(排除上界 ≤1 轮)。"""
        sess = SimpleNamespace()
        st = CwSimFrame(gold=10, level=5, round_num=3)
        st.plane = 2
        mandate.record_round_sold(sess, _bsb(st), '甲')
        assert mandate.round_sold_names(sess, _bsb(st)) == frozenset({'甲'})
        st.round_num = 4
        assert mandate.round_sold_names(sess, _bsb(st)) == frozenset()
        st.round_num = 3
        st.plane = 3
        assert mandate.round_sold_names(sess, _bsb(st)) == frozenset()


# ===== L3′:prep 位 M6 摘旗可达性 =====


class TestL3FlagRemoval:

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
        state = CwSimFrame(gold=60, level=3, round_num=3)
        state.hp = 60
        state.hp_readable = True
        mandate.run_mandate(frame, sess, state=_bsb(state))
        assert state_of(sess).cw4_counters.get('m6_bench_full', 0) >= 1


# (原 L4:P72 拒帧档 1/2 挂起锁随 P72 预算闸/L4 挂起面退役删除
#  商店期升级决策面收缩——闸写点不存在,挂起分支结构性死路;档 2 同帧
#  挂起的 TestShopM3M6 承载声明随之失效。)


# ===== L7:ALL IN 类别过滤(P21 域辖;XP 仅支A 合法)=====


class TestL7AllInCategoryFilter:

    def _allin_state(self, hp: int, *, readable: bool = True) -> CwSimFrame:
        """CwSimFrame 帧(mandate_v1 闸入口仍持 CwSimFrame,闸内经一次性装箱;
        位面/节点语义同 _allin_bs)。"""
        st = CwSimFrame(gold=30, level=5, round_num=7, node_type='boss',
                       hp=hp)
        st.plane = 2
        st.hp_readable = readable
        st.hp_trusted = False
        return st

    def _allin_bs(self, hp: int | None, *, source: str = 'observation'
                  ) -> 'GameState':
        """P21 域判据容器帧(波 2 起门输入 = GameState):P2r7 boss 帧,
        来源三态 = 旧两位语义的容器形态(observation=真读/prior=不可信)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            BS_SCHEMA_VERSION,
            ChannelSig,
            GameState,
            NodeKey,
        )
        sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
        bs = GameState(schema_version=BS_SCHEMA_VERSION)
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
            _bsb(st), sess, 30, 5, ('甲',), [], [], 2, 4)
        assert ok is False and why == 'all_in_xp_category_filtered'
        # 支A:板满(cap 5)+ bench 有 2★ 等待件 → 兑现链当帧可兑现
        deployed = [_bc(f'甲{i}', star=2, slot=i + 1) for i in range(5)]
        bench = [_bc('乙', star=2, slot=1)]
        ok2, why2 = crit_levelup.levelup_budget_gate(
            _bsb(st), sess, 30, 5, ('甲', '乙'), bench, deployed, 2, 4)
        assert ok2 is True and why2 == ''
        # 域外(hp>停线):全豁免放行
        st_out = self._allin_state(100)
        ok3, why3 = crit_levelup.levelup_budget_gate(
            _bsb(st_out), sess, 30, 5, ('甲',), [], [], 2, 4)
        assert ok3 is True and why3 == ''
