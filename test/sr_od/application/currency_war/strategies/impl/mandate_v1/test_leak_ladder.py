"""泄金阶梯单帧测试(ADR-0604 判据测试;测试清单 = 设计方案 §4.3
本批归属 L1-L7 + 档 2 轮内新鲜度排除,方案正本指针 = ADR-0604 头注)。

测试清单(§4.3 表存续面):
- LF′ 档 2 轮内新鲜度排除载体相位过期:跨轮/跨位面读数空集(排除
      上界 ≤1 轮;发射位排除面归写端与消费位测试辖)。
- L3′ prep 位 M6 摘旗可达性:stop_flag=False(线未齐)∧ gold>g* ∧
      席满帧,M6 prep 块被触达(m6_bench_full 拒因显影——摘旗前该帧
      被 stop_flag 短路、拒因结构性不可见)。
- L7  ALL IN 类别过滤:P21 域(kernel all_in_xp_domain_hit)内非支A XP
      经 P72 闸拒;支A 形态/域外帧放行(指标 G=0 的判据面)。

测试构造声明:候选/帧构造基建(_km/_bc/_card/_off_name/_session_stub/
_st)保留 = test_front_window_predicates 的候选构造单一源(跨文件
消费);L1/L1b/L2/L3/L5/LF 发射面测试与档 1 锁线门负腿已退役。
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
    CORE_SINGLE_CARD_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.protection import (
    four_system_members,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

_COMP = '列车同行'


# ===== 测试基建(exit3 同族口径)=====


def _km() -> list[str]:
    return list(predicates.line_members(get_comp(_COMP)))


def _bc(name: str, star: int = 1):
    """行域单位(容器形状;本文件与 press_narrow 转型域共用直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    return Unit(char_id=name, star=star)


def _st(gold: int, cards, *, locked: bool = True, level: int = 5,
        deploy_cap: int | None = None, bench=None, deployed=None,
        plane: int = 2, hp: int = 60, xp=None) -> dict:
    """漏斗阶梯场景种子轴(旧帧配方退役承接 = 桥/feed 两配方公共
    kwargs;``deployed`` = 旧槽表序 Units,前 4 位前排/其余后排的语义
    在此分行承接,槽号 1 基信息位随行重排;``locked`` 轴不在容器域,
    保留参数位 = session 侧语义,由调用方自持)。"""
    axes: dict = {'gold': gold, 'level': level, 'round_num': 2, 'hp': hp,
                  'plane': plane, 'shop': list(cards)}
    if bench is not None:
        axes['bench'] = bench
    if deployed is not None:
        from sr_od.application.currency_war.kernel.cw_game_state import Unit
        axes['front_row'] = [
            Unit(char_id=u.char_id, star=u.star,
                 equips=list(u.equips or []))
            for i, u in enumerate(deployed[:4])]
        axes['back_row'] = [
            Unit(char_id=u.char_id, star=u.star,
                 equips=list(u.equips or []))
            for i, u in enumerate(deployed[4:], start=4)]
    if deploy_cap is not None:
        axes['deploy_cap'] = deploy_cap
    if xp is not None:
        axes['xp'] = xp
    return axes


def _bs(name: str, star: int = 1, slot: int = 1):
    """容器占席条目(P4 载体迁移:MandateFrame/判据直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        BenchSlot,
        Unit,
    )
    return BenchSlot(kind='unit', unit=Unit(char_id=name, star=star))


def _bu(name: str, star: int = 1, slot: int = 1):
    """容器行域单位(P4 载体迁移:deployed 直构面)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import Unit
    return Unit(char_id=name, star=star)


def _card(name: str, cost: int = 2, star: int = 1) -> ShopCard:
    return ShopCard(x=100, name=name, cost=cost, star=star)


def _off_name(exclude: tuple[str, ...] = (), *, min_cost: int = 1) -> str:
    """线外且非核心/非保护集的注册表角色名(档 1/档 2 候选;避开 C1/
    囤货臂候选身份,防邻近臂抢发射——身份单一源 = protection.
    four_system_members,注册表现算防漂移)。"""
    bad = set(exclude)
    for n, ch in CHARACTERS.items():
        if n in bad or (ch.cost or 0) < min_cost:
            continue
        if n in CORE_SINGLE_CARD_REGISTRY or n in four_system_members():
            continue
        return n
    raise AssertionError('注册表缺少合适线外角色(测试前提失效)')


def _session_stub(locked: bool = True, target_comp=None) -> SimpleNamespace:
    s = SimpleNamespace()
    st = state_of(s)
    st.cw4_counters = {}
    st.target_comp = target_comp if target_comp is not None else get_comp(_COMP)
    st.v3_intention = SimpleNamespace(
        locked_comp=(_COMP if locked else ''))
    return s


# ===== LF′:档 2 轮内新鲜度排除载体相位过期 =====


class TestL2L5LFM6Compression:

    def test_lf_round_registry_expiry(self):
        """新鲜度载体键式相位过期:跨轮/跨位面读数空集(排除上界 ≤1 轮)。"""
        sess = SimpleNamespace()
        axes = {'gold': 10, 'level': 5, 'round_num': 3, 'plane': 2}
        mandate.record_round_sold(sess, _bsb(**axes), '甲')
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset({'甲'})
        axes['round_num'] = 4
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset()
        axes['round_num'] = 3
        axes['plane'] = 3
        assert mandate.round_sold_names(sess, _bsb(**axes)) == frozenset()


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
        bench = [_bs(f'高价{i}', star=3, slot=i + 1) for i in range(9)]
        frame = mandate.MandateFrame(
            gold=60, level=3, bench=bench, deployed=[],
            deploy_cap=5, node_type=None, stop_flag=False,
            k_members=('目标件',), round_num=3)
        state = _bsb(gold=60, level=3, round_num=3, hp=60)
        mandate.run_mandate(frame, sess, state=state)
        assert state_of(sess).cw4_counters.get('m6_bench_full', 0) >= 1


# (原 L4:P72 拒帧档 1/2 挂起测试随 P72 预算闸/L4 挂起面退役删除
#  商店期升级决策面收缩——闸写点不存在,挂起分支结构性死路;档 2 同帧
#  挂起的 TestShopM3M6 承载声明随之失效。)


# ===== L7:ALL IN 类别过滤(P21 域辖;XP 仅支A 合法)=====


class TestL7AllInCategoryFilter:

    def _allin_state(self, hp: int) -> dict:
        """ALL IN 闸场景种子轴(闸内一次性装箱;P2r7 boss 帧)。"""
        return {'gold': 30, 'level': 5, 'round_num': 7, 'node': 'boss',
                'hp': hp, 'plane': 2}

    def _allin_gs(self, hp: int | None, *, source: str = 'observation'
                  ) -> 'GameState':
        """P21 域判据容器帧(波 2 起门输入 = GameState):P2r7 boss 帧,
        来源三态 = 旧两位语义的容器形态(observation=真读/prior=不可信)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            GAME_STATE_SCHEMA_VERSION,
            ChannelSig,
            GameState,
            NodeKey,
        )
        sig = ChannelSig(family='obs', actor='cw_observation', mode='read')
        gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
        if hp is not None:
            if source == 'observation':
                gs.observe(gs.hp, hp, sig=sig)
            elif source == 'prior':
                gs.write_prior(gs.hp, hp, evidence='prior:adr-0559', sig=sig)
            else:
                raise ValueError(f'未知 source {source!r}')
        gs.observe(gs.node, NodeKey(plane=2, round_num=7, kind='boss'),
                   sig=sig)
        # 终态契约 §A′:探针宿主 = 流经 gs 本体(P2 真长 7,语料实证)。
        gs.node_books.plane_node_table = [object()] * 7
        return gs

    def _allin_session(self) -> SimpleNamespace:
        s = SimpleNamespace()
        s.node_type_current = 'boss'
        from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
        game_state_of(s).node_books.plane_node_table = [object()] * 7   # P2 真长 7(语料实证;§A′)
        return s

    def test_l7_domain_predicate_p21(self):
        """辖域判据(kernel 单一源):ALL IN boss 末轮 ∧ hp 真值可信
        ∧ 门后 hp ≤ 停升级线 → 域内;域外/不可信/None 帧不过滤(§7.4 域外
        不动 + [18] 豁免在不可信帧仍生效)。"""
        from sr_od.application.currency_war.kernel.cw_discipline_rules import (
            all_in_xp_domain_hit,
        )
        sess = self._allin_session()
        assert all_in_xp_domain_hit(self._allin_gs(10), sess,
                                    DEFAULT_REGISTRY) is True
        assert all_in_xp_domain_hit(self._allin_gs(100), sess,
                                    DEFAULT_REGISTRY) is False
        # 不可信帧(prior 支,旧两位皆 False 的容器形态)不过滤
        assert all_in_xp_domain_hit(self._allin_gs(10, source='prior'),
                                    sess, DEFAULT_REGISTRY) is False
        no_hp = self._allin_gs(None)
        assert all_in_xp_domain_hit(no_hp, sess,
                                    DEFAULT_REGISTRY) is False

    # (P72 闸 ALL IN 支收窄测试 test_l7_gate_rejects_non_support_xp 已随
    # levelup_budget_gate 量闸本体退役消亡——迭代 2026-10-12-prep-shop-
    # workflow-redesign 批 3.4;line_and_upgrade §2.3 P72(3a) 本体删除
    # 行:量闸整体不再存在,「ALL IN 帧类别白名单拒 XP」的防线语义随
    # 之消亡(ALL IN 帧花光拦截现役载体 = 无——末位面末战保底金门出辖
    # = ALL IN 花光原语义;替代语义考古走 git 历史)。辖域谓词本体
    # all_in_xp_domain_hit 的测试 = test_l7_domain_predicate_p21。)
