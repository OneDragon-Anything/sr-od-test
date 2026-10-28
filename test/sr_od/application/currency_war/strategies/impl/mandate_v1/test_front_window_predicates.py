"""前窗两谓词数据源测试(P90 面①;T-3 验收裁缺陷修:前窗/表就绪谓词
数据源归位 ``gs.node_books`` 单一源)。

病灶形态(本测试防复发):两谓词曾经裸 ``getattr(session, 'plane_node_table
/plane_node_table_plane')`` 读已退役 session 探针族(StrategySession 现值
仅 rng/performance/strategy_state)→ 恒 None → 谓词恒 False → 生产消费面
(shop.decide_shop_action 的零成型武装)fail-closed 静默失效。写端唯一 =
cw_screen_prep.store_plane_table(写 ``gs.node_books``),读端必须同源。

测试面(此前零覆盖):
1. 表在场真路径:node_books 在册(位面锚=1)→ 表就绪 True / 前窗帧
   轮窗(轮 1..首战槽+1)True,出窗 False;
2. fail-closed 负路径:表缺(裸容器)/ 锚不符(旧表滞留 P2)/ state
   位面非 1 / 脏表(全零战斗词)→ False(前窗行为不发生);
3. 写入点形状契约:store_plane_table 写入的形状(list[str] 槽序 + 位面
   锚落 ``gs.node_books``)= 谓词读的形状——写读异源即病灶本身,本测试
   单一源对账。

第二部分(原 press_narrow_transition 并入)——锁线转型域收窄:
出处(单一源):命题正本 = docs/develop/sr_od/application/currency_war/
proofs/p88.md(§0 辖域/§1 调和引理/§3 解封方向式;收窄集 S_spec =
{dominance_buy, hub_option_buy},豁免 ⇔ reason ∈ LAUNCH_CAUSE_BY_ARM
∖ S_spec 闭集单一源);落码 = shop.py 两 S_spec 发射位辖域前置
(分键 press_narrowed_transition_domain / press_narrowed_transition_
domain_hub)+ mandate.swap_transition_narrow_frame(域谓词单一源 =
 kernel ``swap_bond_gate_domain_of`` 转型域判别子全合取,design
 2026-10-26-swap-channel-unified §2.3.1 谓词源迁移)。
(F4 闭集对账正本与 S_spec 辖域分支迁并
 test_sell_window_launch::test_launch_cause_closed_set(15 臂映射段);
 F1 开火/F2/F3 豁免/F5 零漂移/F6 M6 零触碰/F7 单一源/F8 prep 对称/
 F9 wiring 旗位各测试已退役。)
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_box as _bridge,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_gs,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _bc as _lad_bc,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _card as _lad_card,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _km as _lad_km,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _off_name as _lad_off_name,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _session_stub as _lad_session,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_leak_ladder import (
    _st as _lad_st,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    IntentionState,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    _card as _hub_card,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    _ct as _hub_ct,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    _decide as _hub_decide,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    _session as _hub_session,
)
from test.sr_od.application.currency_war.strategies.impl.mandate_v1.test_no_target_three_arms import (
    _state as _hub_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    NodeKey,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionBuyCardParam,
    ShopCard,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    store_plane_table,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    mandate,
    shop,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates,
)

_SIG = ChannelSig(family='obs', actor='TestCwFrontWindowPredicates', mode='read')

#: P1 众数表形样例:首战在第 3 槽(0 基 idx=2)→ 前窗轮窗 = 1..3。
_P1_TABLE: list[str] = ['奖励', '补给', '战斗', '战斗', '战斗',
                        '战斗', '战斗', '战斗', '首领']


def _gs(plane: int = 1, round_num: int = 1) -> GameState:
    """容器 + 节点读口种子(位面/轮次即谓词的 plane/round 读口输入)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.node, NodeKey(plane=plane, round_num=round_num, kind='prep'),
               evidence='t', sig=_SIG)
    return gs


def _seed_table(gs: GameState, plane: int = 1,
                table: list[str] | None = None) -> None:
    """直写 node_books(谓词读端形状;表缺负路径不调用)。"""
    gs.node_books.plane_node_table = list(table or _P1_TABLE)
    gs.node_books.plane_node_table_plane = plane


def test_table_ready_true_and_front_window_round_window():
    """表在场真路径:node_books 在册(位面锚=1)→ 表就绪 True;前窗帧
    = 轮 1..首战槽+1(样例表首战第 3 槽 → 轮 1/2/3 True,轮 4 出窗)。"""
    gs = _gs(plane=1, round_num=1)
    _seed_table(gs)
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is True
    for r in (2, 3):
        gs_r = _gs(plane=1, round_num=r)
        _seed_table(gs_r)
        assert predicates.front_window_frame(gs_r) is True, f'轮 {r} 在前窗'
    gs_out = _gs(plane=1, round_num=4)
    _seed_table(gs_out)
    assert predicates.front_window_frame(gs_out) is False, '首战槽后帧出窗'


def test_fail_closed_when_table_or_anchor_or_plane_gate_fails():
    """fail-closed 负路径:表缺(裸容器)/ 锚不符(旧表滞留 P2)/
    state 位面非 1 → 两谓词 False(前窗行为不发生,不静默武装)。"""
    gs_bare = _gs()   # 未写表:plane_node_table / 位面锚均 None
    assert predicates.front_window_table_ready(gs_bare) is False
    assert predicates.front_window_frame(gs_bare) is False

    gs_stale = _gs()
    _seed_table(gs_stale, plane=2)   # 表在场但位面锚 = 2(旧表滞留形态)
    assert predicates.front_window_table_ready(gs_stale) is False
    assert predicates.front_window_frame(gs_stale) is False

    gs_p2 = _gs(plane=2, round_num=1)   # P2 帧挂 P1 表:位面门先拒
    _seed_table(gs_p2, plane=1)
    assert predicates.front_window_frame(gs_p2) is False


def test_dirty_table_frame_silent_false():
    """脏表退化域:表全为零战斗词(位面必有战斗的结构下不可能)→
    frame 静默 False(表就绪探针只辖「在场」,不受脏表辖)。"""
    gs = _gs()
    _seed_table(gs, table=['奖励', '补给'] * 4 + ['奖励'])
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is False


def test_store_plane_table_shape_feeds_predicates():
    """写入点形状契约:store_plane_table 写入(经 session 桥落
    ``gs.node_books``,与生产唯一写端同路)= 谓词读的形状 → 两谓词
    True。写读异源(session 探针读法)即本缺陷病灶,本测试单一源对账。"""
    session = SimpleNamespace()
    gs = game_state_of(session)
    gs.observe(gs.node, NodeKey(plane=1, round_num=2, kind='prep'),
               evidence='t', sig=_SIG)
    assert store_plane_table(session, _P1_TABLE, 1) is True
    assert gs.node_books.plane_node_table == _P1_TABLE, '槽序表按写端形状落位'
    assert gs.node_books.plane_node_table_plane == 1, '位面锚落位'
    assert predicates.front_window_table_ready(gs) is True
    assert predicates.front_window_frame(gs) is True, '写端形状 → 谓词 True'


# ==================== 锁线转型域收窄(原 press_narrow_transition 并入)===

_NARROW_KEY = 'press_narrowed_transition_domain'
_NARROW_HUB_KEY = 'press_narrowed_transition_domain_hub'


def _d_frame_deps(n_km: int = 0) -> tuple[list[Unit], frozenset[str]]:
    """板满构造(level 5 ⇒ max_units=5,bench 空):锁线采购集前 n_km 名
    2★ 上板(其余线内名留作缺员),余位线外 2★ 垫件补满。
    返回 (板上件, 板上名集)——候选/缺员选取须 exclude 板上名集。"""
    km = _lad_km()
    names = list(km[:n_km])
    while len(names) < 5:
        names.append(_lad_off_name(exclude=tuple(names)))
    deps = [_lad_bc(m, star=2) for i, m in enumerate(names)]
    return deps, frozenset(names)


def _d_frame_st(gold: int, cards: list[ShopCard]) -> dict:
    """D 帧默认形(n_km=0 纯垫件板):锁线 ∧ fp<1.00(board 空)∧ 板满。"""
    deps, _names = _d_frame_deps(0)
    return _lad_st(gold, cards, locked=True, deployed=deps)


def _decide(st: dict, sess) -> object:
    return shop.decide_shop_action(cw4_gs(sess, **st), sess, SimpleNamespace(ev_arm='full'))


class TestDominanceNarrowFire:

    def test_f1b_candidate_none_frame_key_silent(self):
        """分键口径 = 将发射笔:同 D 帧但店无 dominance 候选(仅 2★
        线外卡,refund 门先拒)⇒ 无将发射笔,收窄分键零显影(禁把辖域
        机会帧计入开火数,防 §4.1-⑦① 覆盖比畸变)。"""
        _deps, dep_names = _d_frame_deps(0)
        cand = _lad_off_name(exclude=tuple(dep_names))
        st = _d_frame_st(60, [_lad_card(cand, cost=2, star=2)])
        sess = _lad_session(locked=True)
        assert mandate.swap_transition_narrow_frame(_bridge(**st), sess) is True
        _decide(st, sess)
        assert _NARROW_KEY not in state_of(sess).cw4_counters, \
            '无可发射笔帧分键照计 = 口径漂移(帧内无将发射笔)'


class TestHubSentinel:
    def test_f9_hub_natural_frame_untouched(self):
        """校验 F9 控制(空开火面申报的常态面)→ 3.6 乙臂收编改校验:未锁
        无目标帧(枢纽件自然辖域)收窄旗恒 False ⇒ 枢纽件经序 1 成员面
        照常发射(m2 买因;hub_option_buy 发射位随乙臂收编退役)、
        哨兵键零显影。"""
        st = _hub_state(shop_cards=[_hub_card('花火', cost=2)])
        sess = _hub_session(IntentionState())
        assert mandate.swap_transition_narrow_frame(_bridge(**st), sess) is False
        act = _hub_decide(st, sess)
        assert isinstance(act, CwActionBuyCardParam), act
        assert act.card.name == '花火'
        assert act.reason.startswith('m2_'), act.reason
        ct = _hub_ct(sess)
        assert 'hub_option_buy_hit' not in ct
        assert _NARROW_HUB_KEY not in ct
