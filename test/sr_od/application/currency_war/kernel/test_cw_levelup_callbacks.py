"""升级连锁值回调宿主锁(kernel 直驱;镜像 src cw_levelup_callbacks.py)。

设计唯一源 = 迭代 2026-09-23-invest-effects-calc T-432 设计稿 §5 锁面
(任意源跨级触发/单触发/live 观察零回调/连跳/满帽/守卫/逐源覆盖)。驱动
形态 = 裸容器直构 + 端口桩(install_sim_backend 桩对象 + rng 提供槽显式
注入——调度器只问 ``sim_backend_installed``,真后端行为锁归 sim 链测试
族,sim/cw_sim_backend/ 目录)。teardown 纪律:端口槽与 rng 提供槽随
fixture 卸载(模块槽进程全局,残留跨测试泄漏)。

锁面 → 测试对照:
- 锁 1 任意源跨级触发 = test_any_source_cross_level_fires_full_chain
  (+ live 形对照臂);
- 锁 2 买经验单触发 + 双源 gift 面 =
  test_buy_xp_single_gift_and_two_source_two_gifts;
- 锁 3 live 观察写零回调(+ relay 臂)= test_observe_and_relay_zero_chain;
- 锁 5 连跳逐级序列 = test_multi_level_jump_grants_per_intermediate_level;
- 锁 6 满级帽零触发 = test_level_cap_zero_advance_zero_chain;
- 锁 7 降级/同值守卫 = test_downgrade_and_same_value_guards;
- 锁 8 逐源连锁覆盖(源-函数对应表)= test_per_source_chain_coverage。
"""
from __future__ import annotations

import itertools
import random
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_level_up_param,
    set_action_rng_provider,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    env_portal_effects,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_first_buy_xp_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    ShopActionExecuted,
    grant_xp,
    shop_randomized_pending_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionLevelUpParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    apply_node_xp,
    apply_strategy_pick_xp,
    apply_strategy_plane_refire_xp,
)

_SIG = ChannelSig(family='logic_action', actor='LevelupCbTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='LevelupCbTest', mode='read')
_ENV_ID = '138'   # 成功经验 plaza id(窗口锚断言的条目主键)


@pytest.fixture()
def sim_armed():
    """端口桩 + rng 提供槽装配(调度器模拟器门判据为真;teardown 双卸)。
    桩对象零方法——调度器只问装配与否,状态副本过程不触桩。"""
    cw_sim_ports.install_sim_backend(SimpleNamespace())
    seq = itertools.count()
    set_action_rng_provider(
        lambda tool: random.Random(f'test-levelup/{tool}/{next(seq)}'))
    yield
    set_action_rng_provider(None)
    cw_sim_ports.uninstall_sim_backend()


def _seed_gs(level: int, xp_cur: int, *, strategies: list[str] | None = None,
             with_env: bool = False) -> GameState:
    """裸容器种子(观察链同写入口;bench 9 空槽供 gift 入席断言)。
    ``strategies`` = 持卡观察种子;``with_env`` = 成功经验已登记(锚断言)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.level, int(level), evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.xp, (int(xp_cur), XP_TO_NEXT_LEVEL.get(int(level), 4)),
               evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), evidence='t:seed',
               sig=_SIG_OBS)
    if strategies is not None:
        gs.observe(gs.active_strategies, strategies,
                   evidence='t:seed', sig=_SIG_OBS)
    if with_env:
        gs.effects.register_portal(env_portal_effects()['成功经验'],
                                   acquired_key=(1, 1))
    return gs


def _bench_names(gs: GameState) -> list[str]:
    """备战席单位名清单(gift 入席断言面)。"""
    return [s.unit.char_id for s in gs.bench.value.slots
            if s.kind == 'unit' and s.unit is not None]


def _buy(gs: GameState, clicks: int = 1):
    """买经验上报(生产同口;executed 击数回执形态)。"""
    return report_action_level_up_param(
        gs, CwActionLevelUpParam(cost=4), _SIG,
        executed=ShopActionExecuted(levelup_clicks=clicks))


def _chain_marks(gs: GameState) -> tuple[bool, int, list[str]]:
    """连锁三面快照 (信号, 队列声明数, 备战席名单)。"""
    return (shop_randomized_pending_of(gs),
            len(gs.pending_levelup_world_decls),
            _bench_names(gs))


# ================ 锁 1:任意源跨级触发(核心新锁)================

def test_any_source_cross_level_fires_full_chain(sim_armed) -> None:
    """grant_xp(环境窗口发放原语)跨级 → 四面连锁齐发:信号置位 + 队列
    含 spy 声明(trigger=spy_shop_refresh)+ gift 发放 1 名 2★ + 锚记录
    (成功经验条目;生效位 None = 零记录,不炸不写)。"""
    gs = _seed_gs(7, 50, strategies=['商业间谍', '节节高升'], with_env=True)
    grant_xp(gs, 12, sig=_SIG, evidence='t:grant')
    assert (gs.level.value, gs.xp.value) == (8, (10, 72)), '跨级推进对'
    pending, n_decl, names = _chain_marks(gs)
    assert pending is True, '信号置位'
    assert n_decl == 1, '队列含 spy 声明(模拟器装配写入)'
    decl = gs.pending_levelup_world_decls[0]
    assert decl.trigger == 'spy_shop_refresh' \
        and decl.next_screen == '货币战争-备战', '声明词面'
    assert len(names) == 1, 'gift 恰发 1 名'
    assert all(s.unit.star == 2 for s in gs.bench.value.slots
               if s.kind == 'unit' and s.unit is not None), '2★ 卡面明写'
    assert gs.effects.first(_ENV_ID).anchor_pos is None, \
        '生效位未锚定 → 锚零记录(检测体自判,零旁路)'


def test_live_form_chain_without_port(sim_armed) -> None:
    """live 形对照臂(端口未装):grant_xp 跨级 → 信号照置位(实机真刷店,
    反映真实游戏行为)+ 队列空(live 不构造,防陈积脏声明)+ gift 零写
    (实机该角色由游戏引擎发放)。"""
    gs = _seed_gs(7, 50, strategies=['商业间谍', '节节高升'])
    set_action_rng_provider(None)   # 覆盖 fixture 注入:live 形无采样槽
    cw_sim_ports.uninstall_sim_backend()
    grant_xp(gs, 12, sig=_SIG, evidence='t:grant')
    assert (gs.level.value, gs.xp.value) == (8, (10, 72)), '跨级推进对'
    pending, n_decl, names = _chain_marks(gs)
    assert pending is True, '信号照置位(live)'
    assert n_decl == 0, '队列空(live 不构造)'
    assert names == [], 'gift 零写(live)'


# ================ 锁 2:买经验单触发 + 双源 gift 面 ================

def test_buy_xp_single_gift_and_two_source_two_gifts(sim_armed) -> None:
    """买经验上报跨级(经 level 写尾回调):Δ=1 gift 恰发 1 名(旧上报
    内联块残留会双发 2 名,结构性暴露)+ 上报尾 world_decl 经队列读出
    (trigger=spy_shop_refresh,动作执行点喂入形态);双源面:两来源各
    跨一级(买经验 6→7 + 环境发放 7→8)→ 各发一名总数 2。"""
    gs = _seed_gs(6, 0, strategies=['商业间谍', '节节高升'])
    out = _buy(gs, clicks=XP_TO_NEXT_LEVEL[6] // 4)
    assert out.applied and (gs.level.value,) == (7,)
    assert len(_bench_names(gs)) == 1, 'Δ=1 gift 恰 1 名(防双发)'
    assert out.world_decl is not None \
        and out.world_decl.trigger == 'spy_shop_refresh', \
        '上报尾队列头读出(声明管道重接,行为等价)'
    # 双源面:第二来源(环境窗口发放)再跨一级 → 累计 2 名
    grant_xp(gs, XP_TO_NEXT_LEVEL[7], sig=_SIG, evidence='t:grant2')
    assert (gs.level.value,) == (8,), '第二来源跨级'
    assert len(_bench_names(gs)) == 2, '两来源各发一名,总数 2'


# ================ 锁 3:live 观察写零回调(+ relay 臂)================

def test_observe_and_relay_zero_chain(sim_armed) -> None:
    """持 spy 局,观察写 level 5→6(live 观察摄取形态,值即便跨级)→
    信号不动、队列空、gift 零写、锚不动——「观察写零回调」契约逐字保持;
    relay 臂:接管播种写 level(从未写过字段)→ 同样零回调。"""
    gs = _seed_gs(5, 0, strategies=['商业间谍'], with_env=True)
    gs.observe(gs.level, 6, evidence='t:obs', sig=_SIG_OBS)
    pending, n_decl, names = _chain_marks(gs)
    assert (pending, n_decl, names) == (False, 0, []), '观察写零回调'
    assert gs.effects.first(_ENV_ID).anchor_pos is None, '锚零记录'
    # relay 臂:从未写过的字段中继(接管播种;source=logic 但不经落帧
    # 回调宿主;relay 契约 family=logic_hook)。
    gs2 = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs2.observe(gs2.active_strategies, ['商业间谍'], evidence='t:seed',
                sig=_SIG_OBS)
    _relay_sig = ChannelSig(family='logic_hook', actor='LevelupCbTest',
                            mode='compute')
    relayed = gs2.relay(gs2.level, 3, _relay_sig)
    assert relayed is True, '前置:中继落写(契约 True)'
    assert shop_randomized_pending_of(gs2) is False, 'relay 播种零回调'


# ================ 锁 5:连跳逐级序列 ================

def test_multi_level_jump_grants_per_intermediate_level(sim_armed) -> None:
    """单笔大额结算跨 2 级(6→8)→ gift 按中间等级序列各发 1 名,费用档
    随各自等级(7 级 3 费 + 8 级 4 费,现口径继承)。"""
    gs = _seed_gs(6, 0, strategies=['节节高升'])
    grant_xp(gs, XP_TO_NEXT_LEVEL[6] + XP_TO_NEXT_LEVEL[7],
             sig=_SIG, evidence='t:grant')
    assert (gs.level.value,) == (8,), '跨 2 级'
    gained = _bench_names(gs)
    assert len(gained) == 2, '逐级各发 1 名(Δ=2 → 2 名)'
    from sr_od.application.currency_war.data.cw_chars import chars_by_cost
    units = [s.unit for s in gs.bench.value.slots
             if s.kind == 'unit' and s.unit is not None]
    pool3 = {c.name for c in chars_by_cost(3)}
    pool4 = {c.name for c in chars_by_cost(4)}
    assert sum(1 for u in units if u.char_id in pool3) == 1, '7 级档 3 费一名'
    assert sum(1 for u in units if u.char_id in pool4) == 1, '8 级档 4 费一名'


# ================ 锁 6:满级帽零触发 ================

def test_level_cap_zero_advance_zero_chain(sim_armed) -> None:
    """满级局 grant_xp/settle_xp_observe → 算子零推进 → 零写行零连锁
    (write_seq 不动 = 零观察行;值完全不变)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        settle_xp_observe,
    )
    for fn in (
        lambda g: grant_xp(g, 12, sig=_SIG, evidence='t:grant'),
        lambda g: settle_xp_observe(g, 12, sig=_SIG_OBS, evidence='t:settle'),
    ):
        gs = _seed_gs(10, 3, strategies=['商业间谍', '节节高升'])
        seq0 = gs.write_seq
        _lv0, _xp0 = gs.level.value, gs.xp.value
        fn(gs)
        assert (gs.level.value, gs.xp.value) == (_lv0, _xp0), '满级值不变'
        assert gs.write_seq == seq0, '零写行(跳写,零观察笔)'
        pending, n_decl, names = _chain_marks(gs)
        assert (pending, n_decl, names) == (False, 0, []), '满级零连锁'


# ================ 锁 7:降级/同值守卫 ================

def test_downgrade_and_same_value_guards(sim_armed) -> None:
    """level 逻辑写降格写(5→4)与同值重写(5→5)→ 零连锁(守卫全挡:
    观察纠偏、重放、错账形态);写行照落(纠偏本身合法)。"""
    for target in (4, 5):
        gs = _seed_gs(5, 0, strategies=['商业间谍', '节节高升'])
        gs.write_logic(gs.level, target, produced_by='TestXp',
                       evidence='t:guard', sig=_SIG)
        pending, n_decl, names = _chain_marks(gs)
        assert (pending, n_decl, names) == (False, 0, []), \
            f'{target} 写零连锁'


# ================ 锁 8:逐源连锁覆盖(源-函数对应表)================

def test_per_source_chain_coverage(sim_armed) -> None:
    """设计稿 §1.3 表 13 源逐源一例跨级断言(轻量直驱):将来写源漏走
    两个经验入账函数(逻辑写 grant_xp/上报口;观察写 settle_xp_observe)
    时,本清单即「源-函数对应表」扩员检查单。对应表(源 → 本测驱动入口):
    1 买经验上报 → report;2 环境窗口 → grant_xp;3 节点基础 →
    apply_node_xp;4-9 模拟器窗口/位面腿(写体已收敛 settle_xp_observe,
    逐源独立 evidence 词面透传 = 分账身份)→ settle_xp_observe 逐词面;
    10 位面段补发 → apply_strategy_plane_refire_xp;11 选卡即时 →
    apply_strategy_pick_xp;12 首购 → check_strategy_first_buy_xp_grants;
    13 淘金客刷新(前瞻,T-311)= 行 2 同通道,实现即自动获得,不重复。
    """
    def _fresh(level: int = 7, xp_cur: int = 50,
               strategies: list[str] | None = None) -> GameState:
        gs = _seed_gs(level, xp_cur, strategies=strategies or ['商业间谍'])
        gs.observe(gs.node, (1, 1), evidence='t:seed', sig=_SIG_OBS)
        return gs

    # 源 1:买经验上报(观察种子域内升级;真身入口)
    gs = _fresh(6, 0)
    assert _buy(gs, clicks=XP_TO_NEXT_LEVEL[6] // 4).applied
    assert shop_randomized_pending_of(gs), '源 1 买经验上报'
    # 源 2:环境窗口 grant_xp(真身入口)
    gs = _fresh()
    grant_xp(gs, 12, sig=_SIG, evidence='t:grant')
    assert shop_randomized_pending_of(gs), '源 2 环境窗口发放'
    # 源 3:节点基础经验(真身入口;返回入账量)
    gs = _fresh()
    assert apply_node_xp(gs, node_type='boss') == 12
    assert shop_randomized_pending_of(gs), '源 3 节点基础经验'
    # 源 4-9:窗口/位面腿写体收敛 settle_xp_observe,逐源 evidence 词面
    # (xp:strategy_per_node / bench_count / empty_slot / equip_count /
    #  bench_left_cost / strategy_plane:p1)——直驱收敛体 + 词面透传断言。
    for evidence in ('xp:strategy_per_node', 'xp:bench_count',
                     'xp:empty_slot', 'xp:equip_count',
                     'xp:bench_left_cost', 'xp:strategy_plane:p1'):
        gs = _fresh()
        from sr_od.application.currency_war.kernel.cw_game_state import (
            settle_xp_observe,
        )
        settle_xp_observe(gs, 12, sig=_SIG_OBS, evidence=evidence)
        assert shop_randomized_pending_of(gs), f'源 4-9 收敛体:{evidence}'
        assert gs.xp.evidence == evidence, 'evidence 逐源透传(分账身份)'
    # 源 10:位面段补发(真身入口;持固定理财 xp_per_plane=4)
    gs = _fresh(7, 50, ['固定理财', '商业间谍'])
    assert apply_strategy_plane_refire_xp(gs, ['固定理财']) == 4
    assert shop_randomized_pending_of(gs), '源 10 位面段补发'
    # 源 11:选卡即时(真身入口;持伟大征服 xp_instant=12)
    gs = _fresh(7, 50, ['伟大征服', '商业间谍'])
    assert apply_strategy_pick_xp(gs, ['伟大征服']) == 12
    assert shop_randomized_pending_of(gs), '源 11 选卡即时'
    # 源 12:首购(真身入口;持孪生素数 1 费桶 +2)
    gs = _fresh(7, 50, ['孪生素数', '商业间谍'])
    assert check_strategy_first_buy_xp_grants(gs, cost=1, sig=_SIG) == 2
    assert shop_randomized_pending_of(gs), '源 12 首购经验'
