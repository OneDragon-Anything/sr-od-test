"""容器开局种子底座 + 锚定闩 + carry 收窄行为锁(kernel)。

期望表现(kernel 单一源 = ``cw_game_state.seed_opening_state`` /
``GameState.prep_anchored`` / ``GameState.carry`` 注,语义出处 = 容器
正本 game_state/fields.md 的「开局种子底座」语义域):

- 冷建局容器(经 game_state_of 缓存单例支,接管局同构)即含全部开局
  种子:A 类字段逐字段值 + 来源(logic_rand + evidence seed:opening)
  断言;journal 种子行过滤键 = actor GsOpeningSeed、mode compute;
  B/C 类字段(None 为设计语义或无观察源)仍 None;board 禁双写;
  session=None 一次性支与直构容器不种;
- 观察覆盖种子 = 随机态落地预期内:差异只落 logic_rand_outcome 台账行,
  不进失配三分流(零 observe_vs_logic_mismatch 行),覆盖照常采新;
- 锚定闩:reconcile_tracking bench 侧屏幕真值写回成功 → prep_anchored
  置位(读口解析);bench 侧未读(deployed-only 写回)不置位;测试/
  直构域置闩专口 = 直赋生效;
- carry 收窄双臂:现值来源 logic_rand(种子/采样值)失读不沿用——值与
  来源不变,宁保持未验证态不洗白;非 rand 来源(logic)存量行为不变。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel import cw_game_state as gs_mod
from sr_od.application.currency_war.kernel.cw_economy import (
    REFRESH_COST_BASE,
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BENCH_CAPACITY_DEFAULT,
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    OreSight,
    Unit,
    consume_defect_sink,
    game_state_of,
    prep_anchored_of,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    OPENING_HP_BASE,
)
from sr_od.application.currency_war.kernel.cw_reconcile import (
    reconcile_tracking,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

#: A 类种子字段全集(与 seed_opening_state 写面一一对应;board 不入——
#: 派生量禁双写,journal 行面断言兜住)。
_A_SEEDED: tuple[str, ...] = (
    'front_row', 'back_row', 'bench', 'equips', 'occupied_equips',
    'spheres', 'gold', 'level', 'xp', 'hp', 'streak', 'back_layout',
    'deploy_cap', 'overflow_warning', 'overflow_card', 'active_env',
    'active_strategies', 'enemy_affixes', 'shop_refresh_cost',
    'prev_node_spent', 'encounter_refresh_used', 'supply_refresh_used',
    'strategy_refresh_left',
)

#: B/C 类抽检面(None = 设计语义或无观察源,设计分诊表禁种)。
_BC_UNSEEDED: tuple[str, ...] = (
    'node', 'node_ord', 'node_path', 'shop', 'encounter', 'supply',
    'settlement', 'match_final', 'selected_difficulty', 'enemy_difficulty',
    'game_mode', 'env_refresh_left', 'plane_bosses', 'event_overlay',
    'lv999_cost_tier', 'round_fresh_buys', 'level_up_cost', 'top_bar_raw',
    'tracked_account_observed', 'consumables', 'board',
)

_OBS_SIG = ChannelSig(family='obs', actor='CwScreenPrep', mode='read')


def test_cold_build_seeds_all_a_fields(monkeypatch) -> None:
    """冷建即含种子(缓存单例支):A 类逐字段值 + 来源(logic_rand/
    seed:opening)+ journal 种子行过滤键(actor/mode);B/C 类仍 None;
    board 不落种子行;锚定闩缺省 False。"""
    rows: list[dict] = []
    monkeypatch.setattr(gs_mod, '_STATE_JOURNAL_SINK', rows.append)
    monkeypatch.setattr(gs_mod, '_RUN_ID_PROVIDER', lambda: 'seed-t')
    session = StrategySession()
    gs = game_state_of(session)

    # —— A 类逐字段值(种子值语义:常量引用单一源,不手抄可查表值)——
    assert gs.bench.value == BenchView(
        slots=[BenchSlot(kind='empty')] * BENCH_CAPACITY_DEFAULT,
        capacity=BENCH_CAPACITY_DEFAULT)
    assert gs.front_row.value == []
    assert gs.back_row.value == []
    assert gs.equips.value == []
    assert gs.occupied_equips.value == {}
    assert gs.spheres.value == OreSight()
    assert gs.gold.value == 3
    assert gs.level.value == 3
    assert gs.xp.value == (0, XP_TO_NEXT_LEVEL[3])
    assert gs.hp.value == OPENING_HP_BASE
    assert gs.streak.value == 0
    assert gs.back_layout.value == 6
    assert gs.deploy_cap.value == 3
    assert gs.overflow_warning.value is False
    assert gs.overflow_card.value == ''
    assert gs.active_env.value == ''
    assert gs.active_strategies.value == []
    assert gs.enemy_affixes.value == []
    assert gs.shop_refresh_cost.value == REFRESH_COST_BASE
    assert gs.prev_node_spent.value is False
    assert gs.encounter_refresh_used.value == 0
    assert gs.supply_refresh_used.value == 0
    assert gs.strategy_refresh_left.value == {}
    # —— 来源断言:logic_rand + seed:opening(种子字段全集)——
    for name in _A_SEEDED:
        f = getattr(gs, name)
        assert f.source == 'logic_rand', name
        assert f.evidence == 'seed:opening', name
    # —— journal 种子行:过滤键 actor + mode;行字段集 = 种子全集
    # (board 派生行不产:种子空行零差 + 板未读无派生基座 = 禁双写守住)——
    seed_rows = [r for r in rows if r['sig']['actor'] == 'GsOpeningSeed']
    assert {r['field'] for r in seed_rows} == set(_A_SEEDED)
    assert all(r['sig']['mode'] == 'compute' for r in seed_rows)
    # —— B/C 类字段仍 None ——
    for name in _BC_UNSEEDED:
        assert getattr(gs, name).value is None, name
    # —— 锚定闩缺省 False(直读 + 读口解析,本体直通形态)——
    assert gs.prep_anchored is False
    assert prep_anchored_of(session) is False
    assert prep_anchored_of(gs) is False


def test_none_session_and_direct_construct_not_seeded() -> None:
    """session=None 一次性支与直构 GameState 不种(种子只挂两个缓存单例
    建支;测试/sim 直构域依赖未写形态)。"""
    gs_none = game_state_of(None)
    assert gs_none.gold.value is None
    assert gs_none.gold.source == 'observation'   # 从未写(非种子通道)
    assert gs_none.bench.value is None

    direct = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert direct.gold.value is None and direct.bench.value is None
    assert direct.level.value is None and direct.hp.value is None


def test_observe_over_seed_lands_rand_outcome_not_mismatch() -> None:
    """观察覆盖种子 = 随机态落地预期内:差异只落 logic_rand_outcome 台账
    行(零 observe_vs_logic_mismatch 三分流行),覆盖照常采新翻 observation。"""
    gs = game_state_of(StrategySession())
    consume_defect_sink()   # 清跨用例残留(模块级缓冲,防污染)
    seed_gold = gs.gold.value

    gs.observe(gs.gold, seed_gold + 4, sig=_OBS_SIG)

    rows = consume_defect_sink()
    assert [r['kind'] for r in rows] == ['logic_rand_outcome']
    assert rows[0]['field'] == 'gold'
    assert rows[0]['expected'] == seed_gold
    assert rows[0]['actual'] == seed_gold + 4
    assert gs.gold.value == seed_gold + 4
    assert gs.gold.source == 'observation'


def test_reconcile_bench_anchor_sets_prep_anchored() -> None:
    """锚定闩生产置位:reconcile_tracking bench 侧屏幕真值写回成功 →
    prep_anchored 置位 + 读口 True(tracked True 同一成功条件)。"""
    session = StrategySession()
    assert prep_anchored_of(session) is False

    ok, _, _ = reconcile_tracking(session, _bench_view1('花火', 1),
                                  ([], []), screen=None, source='test')

    assert ok is True
    assert game_state_of(session).tracked_account_observed.value is True
    assert game_state_of(session).prep_anchored is True
    assert prep_anchored_of(session) is True


def test_reconcile_deployed_only_keeps_prep_anchored_off() -> None:
    """失败形态不置位:bench 侧未读(deployed-only 写回成功)= 未锚定,
    闩保持 False——两闩同一成功条件,不新增判断分支。"""
    session = StrategySession()

    ok, _, _ = reconcile_tracking(session, None, ([], []), screen=None,
                                  source='test')

    assert ok is True   # deployed 侧照常写回
    assert game_state_of(session).tracked_account_observed.value is None
    assert prep_anchored_of(session) is False


def test_direct_assign_is_test_domain_latch_port() -> None:
    """测试/直构域置闩专口 = 直赋生效(直构容器视同未锚定,缺省 False)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    assert gs.prep_anchored is False

    gs.prep_anchored = True

    assert gs.prep_anchored is True
    assert prep_anchored_of(gs) is True   # 本体直通解析


def test_carry_narrows_logic_rand_keeps_legacy() -> None:
    """carry 收窄双臂:现值来源 logic_rand(种子态)失读不沿用——值与
    来源不变,宁保持未验证态不洗白成 carried;非 rand 来源(logic)存量
    行为不变(沿用 + carried:<帧> 注记)。"""
    logic_sig = ChannelSig(family='logic_action', actor='test',
                           mode='compute')
    # 收窄臂:logic_rand 现值(种子形态)→ carry 不动
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.write_logic_rand(gs.gold, 3, produced_by='GsOpeningSeed',
                        evidence='seed:opening', sig=logic_sig)
    gs.carry(gs.gold, frame='f1', sig=_OBS_SIG)
    assert gs.gold.value == 3
    assert gs.gold.source == 'logic_rand'
    assert gs.gold.evidence == 'seed:opening'
    # 存量回归臂:logic 现值照旧沿用
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs2.write_logic(gs2.hp, 80, produced_by='test', sig=logic_sig)
    gs2.carry(gs2.hp, frame='f1', sig=_OBS_SIG)
    assert gs2.hp.source == 'carried'
    assert gs2.hp.evidence == 'carried:f1'
    assert gs2.hp.value == 80


def _bench_view1(name: str, star: int) -> BenchView:
    """单占用槽视图(槽 1)构造(P6 直产读载体,同 tracked 观察态锁)。"""
    slots = [BenchSlot(kind='empty')] * 8
    return BenchView(slots=[BenchSlot(
        kind='unit', unit=Unit(char_id=name, star=star, slot=1))] + slots)
