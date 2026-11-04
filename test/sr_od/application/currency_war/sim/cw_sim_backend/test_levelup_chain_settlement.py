"""升级连锁 sim 结算时点定案锁(T-432 设计稿 §5-4;镜像面 = SimBackend
advance 尾统一排空段)。kernel 直驱锁 = kernel/test_cw_levelup_callbacks.py,
本文件锁模拟器侧「声明队列 → advance 尾排空」的消费时点与双源不丢:

- 锁 4 主臂:节点经验(boss +12)跨级 → 结算时点信号置位 + advance 尾
  排空后队列空 + spy_deal_count +1(商店分支已执行)+ gift 入席;
- 锁 4 对照臂:无 spy 无 gift → 零商店副作用(零抽牌零入席零信号);
- 锁 4 双源负例(S1 队列化定谳):同栈双源跨级(节点经验 + 窗口分支
  装备计数腿叠加)→ 队列两项 → 商店分支恰两次(单值槽覆盖丢笔形态
  被本锁钉死);
- 锁 4 消费时点断言(B1):选卡即时 XP 跨级 → 排空发生在该选卡 advance
  尾(当拍);首购 XP 跨级 → 排空发生在窗内次声明拍(买牌动作不喂声明,
  上限 = 下一声明驱动 advance,设计稿申报制残余)。

引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限拆分债文件,
禁追加,只 import 复用不改;先例 = 同目录 test_env_xp_window_sim_chain.py)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _node_advance_feed,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    check_strategy_first_buy_xp_grants,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeKey,
    shop_randomized_pending_of,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG = ChannelSig(family='logic_action', actor='LevelupChainTest',
                  mode='compute')
_SIG_OBS = ChannelSig(family='obs', actor='LevelupChainTest', mode='read')
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)


def _to_prep(seed: int = 7) -> SimBackend:
    """构造 + 走到 P1r1 备战屏(窗起点发牌已落);调用方负责卸载。"""
    b = SimBackend(seed=seed, cfg=_CFG)
    install_backend(b)
    b._handle_click_source('货币战争-简报', '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _seed_pre_advance(b: SimBackend, *, strategies: list[str],
                      level: int = 7, xp_cur: int = 50,
                      equips: list[str] | None = None) -> None:
    """种等级/经验/持卡与节点态到「(1,8) boss 节点待推进」位(观察链同
    写入口;node_pos 观察锚定态 = report_node_advance 观察态门放行前提;
    kind = boss → 被离开节点基础经验 +12)。"""
    gs = b.gs
    gs.observe(gs.level, level, evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.xp, (xp_cur, XP_TO_NEXT_LEVEL[level]),
               evidence='t:seed', sig=_SIG_OBS)
    if strategies:
        gs.observe(gs.active_strategies, strategies,
                   evidence='t:seed', sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, equips, evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.node_pos, (1, 8), evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.node, NodeKey(plane=1, round_num=8, kind='boss'),
               evidence='t:seed', sig=_SIG_OBS)


def _bench_names(b: SimBackend) -> list[str]:
    return [s.unit.char_id for s in b.gs.bench.value.slots
            if s.kind == 'unit' and s.unit is not None]


def _bench_star2_names(b: SimBackend) -> list[str]:
    """备战席 2★ 单位名(gift 断言面;间谍偷牌入席全为 1★ 商店卡,
    2★ 唯一来源 = 节节高升发放)。"""
    return [s.unit.char_id for s in b.gs.bench.value.slots
            if s.kind == 'unit' and s.unit is not None
            and s.unit.star == 2]


def test_node_advance_cross_fires_and_drains_same_advance() -> None:
    """锁 4 主臂:boss 节点推进(+12)跨级 → 结算时点(apply_node_xp 调
    settle_xp_observe 刻)信号已置位;同一 advance 尾排空段把队列取走
    即清(队列空)+ spy_deal_count +1(商店分支已执行)+ gift 入席 1 名
    2★。"""
    b = _to_prep()
    try:
        bench_before = _bench_names(b)
        _seed_pre_advance(b, strategies=['商业间谍', '节节高升'])
        assert b.disclosures.get('spy_deal_count', 0) == 0, '前置:零抽牌'
        _node_advance_feed(b.gs, trigger='settle_confirm')
        # 结算时点信号(同 advance 内置位,非下一帧)
        assert shop_randomized_pending_of(b.gs) is True, '结算时点信号置位'
        assert b.gs.pending_levelup_world_decls == [], \
            'advance 尾排空后队列空(取走即清)'
        assert b.disclosures.get('spy_deal_count') == 1, \
            '商店分支已执行(排空段直调)'
        gained = [n for n in _bench_names(b) if n not in bench_before]
        assert len(gained) == 4, \
            '入席合计 = spy 偷 3 + gift 1(差分,开局手牌不计)'
        assert len(_bench_star2_names(b)) == 1, 'gift 恰 1 名 2★(唯一 2★ 源)'
    finally:
        uninstall_backend()


def test_no_cards_zero_shop_side_effect() -> None:
    """锁 4 对照臂:无 spy 无 gift → 节点推进跨级零商店副作用(零抽牌/
    零入席/零信号/队列恒空;M05 常规窗发牌与间谍分支无关,不断言牌面)。"""
    b = _to_prep()
    try:
        _seed_pre_advance(b, strategies=[])
        before = _bench_names(b)
        _node_advance_feed(b.gs, trigger='settle_confirm')
        assert b.disclosures.get('spy_deal_count', 0) == 0, '零抽牌'
        assert _bench_names(b) == before, '零入席'
        assert shop_randomized_pending_of(b.gs) is False, '零信号'
        assert b.gs.pending_levelup_world_decls == [], '队列恒空'
    finally:
        uninstall_backend()


def test_same_stack_double_cross_two_decls_two_deals() -> None:
    """锁 4 双源负例(S1 队列化定谳):同栈双源跨级 = 节点经验(boss +12
    推 7→8)+ 同 advance 窗口分支装备计数腿(赞美太阳 70 件白昼装备 +70
    推 8→9)→ 队列两项 → 商店分支恰两次(单值槽会覆盖丢一次,本锁钉死
    队列化修复)。"""
    b = _to_prep()
    try:
        _seed_pre_advance(
            b, strategies=['商业间谍', '节节高升', '赞美太阳'],
            equips=['武器大师'] * 70)
        _node_advance_feed(b.gs, trigger='settle_confirm')
        assert b.disclosures.get('spy_deal_count') == 2, \
            '同栈双源 → 商店分支恰两次(队列不丢笔)'
        assert b.gs.pending_levelup_world_decls == [], '排空取走即清'
        assert len(_bench_star2_names(b)) == 2, '双源 gift 各发一名 2★'
    finally:
        uninstall_backend()


def test_pick_xp_drains_same_advance_first_buy_next_decl() -> None:
    """锁 4 消费时点断言(B1):选卡即时 XP 跨级 → 排空发生在该选卡
    advance 尾(当拍,spy_deal_count 立即可读);首购 XP 跨级 → 买牌上报
    链内队列滞留(买牌动作不喂声明,设计稿申报制残余),排空发生在窗内
    次声明拍(本测以纯转移声明触发,上限 = 下一声明驱动 advance)。"""
    # (a) 选卡即时:真身 pick advance(呈现闩 = 生产 offer 呈现置位形态)
    b = _to_prep()
    try:
        gs = b.gs
        gs.observe(gs.active_strategies, ['商业间谍', '伟大征服'],
                   evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.invest_strategy_opts, ['伟大征服'],
                   evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.level, 7, evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.xp, (50, XP_TO_NEXT_LEVEL[7]),
                   evidence='t:seed', sig=_SIG_OBS)
        b._present_modal(SCREEN_INVEST_STRATEGY)
        b._strategy_pick_xp_latch = True
        cw_sim_ports.declare_world(WorldDecl(next_screen=SCREEN_PREP,
                                             trigger='pick_invest_strategy'))
        assert b.disclosures.get('spy_deal_count') == 1, \
            '选卡即时 XP 跨级 → 排空发生在该选卡 advance 尾(当拍)'
        assert b.gs.pending_levelup_world_decls == [], '当拍取走即清'
    finally:
        uninstall_backend()
    # (b) 首购:上报链内(直驱 = kernel 检查函数真身)队列滞留 → 次声明
    # 拍(纯转移 advance)排空。
    b2 = _to_prep()
    try:
        gs = b2.gs
        gs.observe(gs.active_strategies, ['商业间谍', '孪生素数'],
                   evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.level, 7, evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.xp, (50, XP_TO_NEXT_LEVEL[7]),
                   evidence='t:seed', sig=_SIG_OBS)
        assert check_strategy_first_buy_xp_grants(gs, cost=1,
                                                  sig=_SIG) == 2, '首购 +2'
        assert (gs.level.value,) == (8,), '首购 XP 跨级'
        assert len(gs.pending_levelup_world_decls) == 1, \
            '买牌上报链内队列滞留(买牌动作不喂声明)'
        cw_sim_ports.declare_world(WorldDecl(next_screen=SCREEN_PREP,
                                             trigger=''))
        assert b2.disclosures.get('spy_deal_count') == 1, \
            '排空发生在窗内次声明拍(申报制残余的行为边界)'
        assert gs.pending_levelup_world_decls == [], '次声明拍取走即清'
    finally:
        uninstall_backend()
