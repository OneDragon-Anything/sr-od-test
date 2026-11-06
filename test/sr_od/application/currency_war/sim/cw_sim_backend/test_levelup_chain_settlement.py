"""升级连锁 sim 结算时点定案锁(T-432 设计稿 §5-4;镜像面 = SimBackend
advance 尾统一排空段)。kernel 直驱锁 = kernel/test_cw_levelup_callbacks.py,
本文件锁模拟器侧「声明队列 → advance 尾排空」的消费时点与双源不丢:

- 锁 4 主臂:节点经验(boss +12)跨级 → 结算时点信号置位 + advance 尾
  排空后队列空 + spy_deal_count +1(商店分支已执行)+ gift 入席;
- 锁 4 对照臂:无 spy 无 gift → 零商店副作用(零抽牌零入席零信号);
- 锁 4 双源负例(S1 队列化定论):同栈双源跨级(节点经验 + 窗口分支
  装备计数效果条目叠加)→ 队列两项 → 商店分支恰两次(单值槽覆盖丢笔形态
  被本锁钉死);
- 锁 4 消费时点断言(B1):选卡即时 XP 跨级 → 排空发生在该选卡 advance
  尾(当拍);首购 XP 跨级 → 排空发生在窗内次声明拍(买牌动作不喂声明,
  上限 = 下一声明驱动 advance,设计稿申报制残余);
- 来源代次锁·免战跳过路径(迭代 2026-09-23-invest-effects-calc T-434):
  被跳节点 XP 跨级置位的信号,代次戳在间谍分支执行尾刷新为牌面所属窗
  (免战路径 = 模拟器本地推进,置位时点序位滞后一节点)——节点边界
  清扫按代次判据保留新源,重开效果条目对免战源不破。

引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限拆分债文件,
禁追加,只 import 复用不改;先例 = 同目录 test_env_xp_window_sim_chain.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _node_advance_feed,
)

from sr_od.application.currency_war.kernel.cw_action_report.start_battle import (
    report_action_start_battle_param,
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
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
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
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    session_scope,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

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
    """锁 4 双源负例(S1 队列化定论):同栈双源跨级 = 节点经验(boss +12
    推 7→8)+ 同 advance 窗口分支装备计数效果条目(赞美太阳 70 件白昼装备 +70
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
    # (a) 选卡即时:真身 pick advance(呈现一次性标志位 = 生产 offer 呈现置位形态)
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


def test_skip_battle_cross_stamp_refreshed_to_board_window() -> None:
    """来源代次锁·免战跳过路径(T-434):被跳节点 XP(reward +2)跨级
    置位的信号,置位时点序位 = 被离开节点(免战路径 = 模拟器本地推进,
    经验入账先于直进下一窗),间谍分支执行尾把代次戳刷新为牌面所属窗
    ——下一备战帧节点边界按代次判据保留新源,重开效果条目对免战源不破
    (无刷新则戳滞后一节点,信号被当过期代次清掉 = T-432 偏差 A 同形
    复发)。"""
    b = _to_prep()
    try:
        gs = b.gs
        gs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'],
                                     acquired_key=(1, 1))
        gs.observe(gs.active_strategies, ['商业间谍'],
                   evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.level, 3, evidence='t:seed', sig=_SIG_OBS)
        gs.observe(gs.xp, (2, XP_TO_NEXT_LEVEL[3]),
                   evidence='t:seed', sig=_SIG_OBS)
        st = state_of(gs)
        st.node_boundary_last_pos = (1, 1)   # (1,1) 备战帧边界已过(生产形态)
        out = report_action_start_battle_param(
            gs, SimpleNamespace(), _SIG, session=gs, skip_substate=True)
        assert out.applied, f'免战跳过上报未落账: {out.reason!r}'
        cw_sim_ports.declare_world(out.world_decl)
        assert b.disclosures.get('spy_deal_count') == 1, \
            '被跳节点 XP 跨级 → 商店分支当拍执行(advance 尾排空)'
        assert shop_randomized_pending_of(gs) is True, '跨级信号置位'
        assert gs.shop_randomized_pending == (1, 2), \
            '代次戳 = 牌面所属窗(免战路径分支执行尾刷新,非滞留被离开节点)'
        session_scope.handle_node_boundary(gs)
        assert gs.shop_randomized_pending is not None, \
            '节点边界 (1,1)→(1,2) 检出变化仍保留新源(重开效果条目恢复)'
    finally:
        uninstall_backend()
