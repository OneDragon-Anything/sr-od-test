"""环境 XP 窗口(成功经验 id 138)kernel 链测试:达成锚 + 节点窗口发放。

设计权威版本 = .debug/progress/2026-09-23-invest-effects-calc/designs/
T-38-chenggong-jingyan.md(§2 建模方案/§4 测试锁面;升到8级后进入
接下来3个节点每节点+12XP)。本文件承 §4 锁 1-9 与锁 10 的 kernel 半;
sim 状态副本里的值与同 seed 全链重放 = 同迭代
sim/cw_sim_backend/test_env_xp_window_sim_chain.py。

锁面 → 测试对照:
- 锁 1 迁移等值 = test_xp_apply_amount_home_input_domain +
  test_apply_node_xp_regression_after_migration;
- 锁 2 主调用点达成记录 = test_main_hook_records_anchor_once;
- 锁 3 结算时点达成记录 = test_fallback_detection_at_node_boundary;
- 锁 4 窗口发放矩阵 = test_window_grant_matrix_and_repeat_tick +
  test_grant_cross_level_carry + test_plane_flip_lex_monotonic;
- 锁 5 未达 8 全局零行为 = test_below_threshold_zero_world_behavior;
- 锁 6 满级窗口 = test_level_cap_window_burns_zero_advance;
- 锁 7 live 覆盖回归 = test_settlement_cover_wins_over_bookkeeping;
- 锁 8 估值回归 = test_env_economy_value_regression;
- 锁 9 修饰局序差 = test_modified_seq_p1_ten_window_real_counts;
- 锁 10(留置与幂等,kernel 半)=
  test_exhausted_entry_kept_and_chain_replay_identical。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_level_up_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
    xp_apply_amount,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    CounterKey,
    env_portal_effects,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    ShopActionExecuted,
    _record_lv8_window_start,
    advance_node_effective,
    apply_settlement_cover,
    tick_effect_boundary,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    resolve_plane_node_seqs,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionLevelUpParam,
)
from sr_od.application.currency_war.sim.cw_sim_backend import apply_node_xp
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    XP_GOLD_RATE,
    env_economy_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='TestXpWindow', mode='read')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='TestXpWindow',
                       mode='compute')
_ENV_ID = '138'   # 成功经验 plaza id(env_portal_effects 结构化条目主键)


def _seed_gs(level: int, xp_cur: int, *, with_env: bool = True,
             other_env: bool = False):
    """种子状态容器(观察链同写入口;等级近门槛 + 成功经验已登记)。
    ``with_env=False`` = 空账本;``other_env`` = 已登记他环境(无
    xp_after_level 载荷)——条目不在场臂的表驱动过滤证据。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.level, int(level), evidence='t:seed', sig=_SIG_OBS)
    gs.observe(gs.xp, (int(xp_cur), XP_TO_NEXT_LEVEL.get(int(level), 4)),
               evidence='t:seed', sig=_SIG_OBS)
    if with_env:
        gs.effects.register_portal(env_portal_effects()['成功经验'],
                                   acquired_key=(1, 1))
    if other_env:
        gs.effects.register_portal(env_portal_effects()['增发货币'],
                                   acquired_key=(1, 1))
    return gs


def _advance(gs, pos) -> bool:
    """推进生效原语驱动(生产同口:尾段效果推进 = tick 桥调用点)。"""
    return advance_node_effective(gs, pos, actor='TestXpWindow',
                                  sig=_SIG_LOGIC, source='logic')


def _buy(gs, clicks: int = 1):
    """购买经验上报(生产同口;executed 击数回执形态)。"""
    return report_action_level_up_param(
        gs, CwActionLevelUpParam(cost=4), _SIG_LOGIC,
        executed=ShopActionExecuted(levelup_clicks=clicks))


def _granted(entry) -> int:
    return entry.counters.get(CounterKey.XP_GRANTED, 0)


# ================ 锁 1:迁移等值 ================

def test_xp_apply_amount_home_input_domain() -> None:
    """xp_apply_amount 新家(cw_economy 单一源)输入域代表点逐位:
    门槛内 / 52 门槛跨 1 级(7→8,锁 4 例证同源)/ 跨多级 / 满级封顶 /
    非正零推进。期望值按门槛表 XP_TO_NEXT_LEVEL 手工核算(纯函数迁移,
    sim 旧实现删除,对拍锚 = 表推进语义)。"""
    assert xp_apply_amount(7, 48, 4) == (8, 0), '52 门槛恰好跨级清零'
    assert xp_apply_amount(7, 48, 12) == (8, 8), '跨 1 级溢出结转'
    assert xp_apply_amount(5, 19, 100) == (8, 7), '跨多级(20/40/52 三门)'
    assert xp_apply_amount(10, 3, 500) == (10, 3), '满级封顶零推进'
    assert xp_apply_amount(7, 48, 0) == (7, 48) and \
        xp_apply_amount(7, 48, -3) == (7, 48), '非正零动作'


def test_apply_node_xp_regression_after_migration() -> None:
    """sim apply_node_xp 回归行为不变(算子迁移后):boss +12 跨 52
    门槛 / 战斗 +2 / 补给 +0 不入账。"""
    gs = _seed_gs(7, 50)
    assert apply_node_xp(gs, node_type='boss') == 12
    assert (gs.level.value, gs.xp.value) == (8, (10, 72)), 'boss +12 跨级'
    gs2 = _seed_gs(7, 50)
    assert apply_node_xp(gs2, node_type='battle') == 2
    assert (gs2.level.value, gs2.xp.value) == (8, (0, 72)), 'battle +2 跨级'
    gs3 = _seed_gs(7, 50)
    assert apply_node_xp(gs3, node_type='supply') == 0
    assert (gs3.level.value, gs3.xp.value) == (7, (50, 52)), '补给零入账'


# ================ 锁 2:主调用点达成记录 ================

def test_main_hook_records_anchor_once() -> None:
    """购买经验上报推 8(48+4=52 跨 52 门槛)→ anchor_pos = 当拍生效位、
    XP_GRANTED 零、无任何「剩余」键播种(单调计数器模型);未达 8 →
    零记录;条目不在场(他环境/空账本)→ 上报后零记录;重复上报(已
    达标已记录)→ 锚不重写(一次性语义)。"""
    # 达成记录臂
    gs = _seed_gs(7, 48)
    _advance(gs, (1, 2))
    out = _buy(gs, clicks=1)
    assert out.applied
    assert (gs.level.value, gs.xp.value) == (8, (0, 72)), '上报推 8 跨门槛'
    entry = gs.effects.first(_ENV_ID)
    assert entry is not None and entry.anchor_pos == (1, 2), '达成位 = 当拍生效位'
    assert _granted(entry) == 0, '达成当拍不计入窗口'
    assert 'xp_left' not in entry.counters and \
        'xp_granted' not in entry.counters, '零剩余键播种(单调模型)'
    # 重复上报臂:进一节点再买,锚不重写
    _advance(gs, (1, 3))
    _buy(gs, clicks=1)
    assert entry.anchor_pos == (1, 2), '锚一次性,不随重复上报重写'
    # 未达 8 臂
    gs2 = _seed_gs(7, 0)
    _advance(gs2, (1, 1))
    _buy(gs2, clicks=1)
    assert gs2.effects.first(_ENV_ID).anchor_pos is None, '未达标零记录'
    # 条目不在场臂(他环境 / 空账本)
    gs3 = _seed_gs(7, 48, with_env=False, other_env=True)
    _advance(gs3, (1, 2))
    _buy(gs3, clicks=1)
    assert (gs3.level.value) == 8
    assert all(e.anchor_pos is None for e in gs3.effects.entries), \
        '无 xp_after_level 载荷条目零记录'
    gs4 = _seed_gs(7, 48, with_env=False)
    _advance(gs4, (1, 2))
    _buy(gs4, clicks=1)
    assert gs4.effects.entries == [], '空账本零记录'


# ================ 锁 3:兜底达成记录 ================

def test_fallback_detection_at_node_boundary() -> None:
    """apply_node_xp 推 8(sim 直调,跳过主调用点)→ 结算时点即记(设计稿
    裁决点 3 定案,行为变化 = 设计意图):跨级当拍记达成位 = 当拍生效位、
    当拍零发放(「接下来 N 个节点」= 达成当拍的后继 N 节点);次拍 tick
    起按后继节点发放一拍。生效位 None 窗 → 零记录零写。"""
    gs = _seed_gs(7, 50)
    _advance(gs, (1, 1))
    assert apply_node_xp(gs, node_type='boss') == 12, '基础经验推 8'
    entry = gs.effects.first(_ENV_ID)
    assert entry.anchor_pos == (1, 1), '结算时点记锚 = 跨级当拍生效位'
    assert _granted(entry) == 0 and gs.xp.value == (10, 72), '当拍零发放'
    _advance(gs, (1, 2))   # 次拍 tick:窗口首发放(达成位后继)
    assert _granted(entry) == 1 and gs.xp.value == (22, 72), \
        '次拍发放一拍(达成位后继 N 节点各计)'
    # None 窗:生效位未锚定 → 零记录零写
    gs2 = _seed_gs(8, 0)
    _record_lv8_window_start(gs2)
    assert gs2.effects.first(_ENV_ID).anchor_pos is None, 'None 窗零记录'
    assert gs2.xp.value == (0, 72), '零写'


# ================ 锁 4:窗口发放矩阵 ================

def test_window_grant_matrix_and_repeat_tick() -> None:
    """达成位 (1,2) → 后继 (1,3)/(1,4)/(1,5) 各 +12(72 门槛域推进对),
    XP_GRANTED 逐发放 +1 至 3;R+4 拍零发放;同拍重复 tick 零双发
    (advanced 位闸继承回归)。"""
    gs = _seed_gs(7, 48)
    _advance(gs, (1, 2))
    _buy(gs, clicks=1)
    entry = gs.effects.first(_ENV_ID)
    seq = [(1, 3), (1, 4), (1, 5), (1, 6)]
    expected_xp = [(12, 72), (24, 72), (36, 72), (36, 72)]
    expected_granted = [1, 2, 3, 3]
    for pos, xp_want, n_want in zip(seq, expected_xp, expected_granted,
                                strict=True):
        _advance(gs, pos)
        assert gs.xp.value == xp_want, f'{pos} 推进对'
        assert _granted(entry) == n_want, f'{pos} 已发放计数'
        if n_want == 1:
            # 窗口中段同拍重复 tick 零双发(真锁 advanced 位闸——耗尽态
            # 的剩余检查单独即可阻断,中段才隔离「双发放」本身)
            tick_effect_boundary(gs)
            assert _granted(entry) == 1 and gs.xp.value == (12, 72), \
                '窗口中段重复 tick 零双发(advanced 位闸)'
    # 同拍重复 tick 零双发(耗尽态)
    tick_effect_boundary(gs)
    assert _granted(entry) == 3 and gs.xp.value == (36, 72), \
        '同拍重复 tick 零双发(advanced 位闸)'


def test_grant_cross_level_carry() -> None:
    """发放跨级溢出结转(72 门槛 8→9):发放 +12 恰跨门槛 → level 9、
    结转清零、分母随新级查表。"""
    gs = _seed_gs(8, 60)
    _advance(gs, (1, 1))
    entry = gs.effects.first(_ENV_ID)
    assert entry.anchor_pos == (1, 1), '等级已达标,首拍 tick 记锚'
    _advance(gs, (1, 2))
    assert (gs.level.value, gs.xp.value) == (9, (0, 84)), '发放跨级结转'


def test_plane_flip_lex_monotonic() -> None:
    """位面翻页(轮次重基 (1,9)→(2,1))后元组字典序单调性照常:窗口
    三发放跨页照计,R+4 零发放。"""
    gs = _seed_gs(8, 0)
    _advance(gs, (1, 9))   # P1 末位
    entry = gs.effects.first(_ENV_ID)
    assert entry.anchor_pos == (1, 9)
    for pos, n_want in zip([(2, 1), (2, 2), (2, 3), (2, 4)],
                           [1, 2, 3, 3], strict=True):
        _advance(gs, pos)
        assert _granted(entry) == n_want, f'{pos} 跨页发放计数'
        assert gs.xp.value == (12 * n_want, 72), f'{pos} 累计推进对'


# ================ 锁 5:未达 8 全局零行为 ================

def test_below_threshold_zero_world_behavior() -> None:
    """等级恒 <8 的局:节点推进对 xp/level 零额外写、锚零记录、计数
    零播种(状态副本这一侧按真实等级,不继承估值「升 8 必然发生」假设)。"""
    gs = _seed_gs(5, 0)
    for pos in [(1, 1), (1, 2), (1, 3)]:
        _advance(gs, pos)
    assert (gs.level.value, gs.xp.value) == (5, (0, 20)), '零额外写'
    entry = gs.effects.first(_ENV_ID)
    assert entry.anchor_pos is None and entry.counters == {}, '零记录零播种'


# ================ 锁 6:满级窗口 ================

def test_level_cap_window_burns_zero_advance() -> None:
    """level=10:窗口照耗(XP_GRANTED 单调递增至 3、条目留置),
    grant_xp 满级门零推进且零写行(level/xp 值完全不变——设计 §4 锁 6
    字面,算子零变化跳写,分母不被归一改写)。"""
    lv_seed = 10
    xp_seed = (0, XP_TO_NEXT_LEVEL.get(lv_seed, 4))
    gs = _seed_gs(lv_seed, 0)
    _advance(gs, (1, 1))
    entry = gs.effects.first(_ENV_ID)
    for pos, n_want in zip([(1, 2), (1, 3), (1, 4)], [1, 2, 3],
                           strict=True):
        _advance(gs, pos)
        assert _granted(entry) == n_want, f'{pos} 窗口照耗'
    assert (gs.level.value, gs.xp.value) == (lv_seed, xp_seed), \
        '满级零推进(值完全不变,零写行)'
    assert entry in gs.effects.entries, '条目留置'
    _advance(gs, (1, 5))
    assert _granted(entry) == 3, '耗尽后零发放'


# ================ 锁 7:live 覆盖回归 ================

def test_settlement_cover_wins_over_bookkeeping() -> None:
    """发放记账(logic)后同节点结算页 apply_settlement_cover 观察
    覆盖 → 值取观察真值、source=observation(observe 直写覆盖,真值赢)。"""
    gs = _seed_gs(7, 48)
    _advance(gs, (1, 2))
    _buy(gs, clicks=1)
    _advance(gs, (1, 3))   # 窗口首发放,(12, 72) logic
    assert gs.xp.source == 'logic', '前置:发放为记账写'
    apply_settlement_cover(gs, hp_after=50, streak_after=1,
                           level=8, xp=(20, 72))
    assert (gs.level.value, gs.level.source) == (8, 'observation')
    assert (gs.xp.value, gs.xp.source) == ((20, 72), 'observation'), \
        '覆盖为真值赢'


# ================ 锁 8:估值回归 ================

def test_env_economy_value_regression() -> None:
    """env_economy_value 对成功经验的估值不变:xp_after_level 表现值
    零改,期望 = 节点数×每节点XP×XP_GOLD_RATE(单一来源现算)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    payload = ENV_ECONOMY['成功经验']
    assert payload.xp_after_level == (8, 3, 12), '表现值零改'
    nodes, per = payload.xp_after_level[1], payload.xp_after_level[2]
    expected = float(nodes * per * XP_GOLD_RATE)
    assert env_economy_value('成功经验', gs) == (expected, True), \
        '估值通道回归不变'


# ================ 锁 9:修饰局序差 ================

def test_modified_seq_p1_ten_window_real_counts() -> None:
    """T-8 人身意外险场字段(P1=10)下:达成位与窗口节点 = 变长制真实
    节点数——(1,9) 记锚,窗口 = (1,10)/(2,1)/(2,2)(NodePos 同键契约,
    位面翻页照常)。"""
    gs = _seed_gs(8, 0)
    seqs = resolve_plane_node_seqs('人身意外险')
    assert len(seqs[1]) == 10, '前置:修饰表 P1=10'
    gs.observe(gs.node_seq_by_plane, seqs, evidence='t:seed', sig=_SIG_OBS)
    _advance(gs, (1, 9))
    entry = gs.effects.first(_ENV_ID)
    assert entry.anchor_pos == (1, 9), '变长制位记锚'
    for pos, n_want in zip([(1, 10), (2, 1), (2, 2), (2, 3)],
                           [1, 2, 3, 3], strict=True):
        _advance(gs, pos)
        assert _granted(entry) == n_want, f'{pos} 真实节点数计窗'


# ================ 锁 10:留置与幂等(kernel 半)================

def test_exhausted_entry_kept_and_chain_replay_identical() -> None:
    """窗口耗尽后条目已登记(XP_GRANTED=3、剩余计算侧导出 = 0)、后续
    节点零发放;同链重放(同种子状态同推进序,两个新状态容器)发放序列
    逐位一致(发放链零 rng 消费;sim 全链重放半 = sim 侧文件)。"""

    def _walk():
        gs = _seed_gs(7, 48)
        _advance(gs, (1, 2))
        _buy(gs, clicks=1)
        entry = gs.effects.first(_ENV_ID)
        trail = [((1, 2), gs.level.value, gs.xp.value, 0)]
        for pos in [(1, 3), (1, 4), (1, 5), (1, 6), (1, 7)]:
            _advance(gs, pos)
            trail.append((pos, gs.level.value, gs.xp.value,
                          _granted(entry)))
        return gs, entry, trail

    gs, entry, trail = _walk()
    assert _granted(entry) == 3 and entry in gs.effects.entries, \
        '耗尽留置'
    assert 3 - entry.counters[CounterKey.XP_GRANTED] == 0, '剩余导出零'
    assert gs.xp.value == (36, 72), '耗尽后零发放'
    _, _, trail2 = _walk()
    assert trail == trail2, '同链重放发放序列逐位一致'
