"""应援团只登记不写状态的实现分支测试(镜像 src = kernel/cw_gain_chain.py 的
gain_invest_strategy 登记分支 × kernel/cw_investments.py 的
STRATEGY_EFFECTS 应援团条目;战力类零响应族第 5 条)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-151-yingyuan-
tuan.md(定稿)§4 锁 2。构造沿现役获得链测试先例
(cw_gain_chain/test_gain_invest_strategy_level_reg.py 同款 helpers
副本,债文件禁追加)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
    apply_board_rewrite,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_strategy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    apply_effect_burst_grant,
    grant_effect_node_refresh_balance,
    project_effect_capacity,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')

_CARD = '应援团'


def _make_gs() -> GameState:
    """观测面组装(bench/equips 直构;登记链 best-effort 分支零触碰面)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    slots = [BenchSlot(kind='empty')] * 9
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_registration_chain_and_four_bridges_noop() -> None:
    """登记链锁 + 四桥负锁:session 在场选卡 → active_strategies 注册 +
    效果账本入册(category=unit_buff);payload=UnitBuffRef 无任何状态副本
    写入字段 → 四桥鸭子类型读取(duck typing)全量缺省守卫 no-op(burst 桥 free_refresh_burst
    缺省 0 / 板面重写桥 board_rewrite 缺省 '' → None / 节点边界桥
    per_node 族缺省 0 / 容量直写桥 capacity_limit 缺省 0 → 早退),bot
    零响应(后排≥4 条件判定与 15% 速度增幅游戏侧自算)。session=None
    支登记跳过、注册照常。注:测试直调 session=None 跳过只登记不写状态的实现分支 = 测试
    形态;生产对局动作 op 与 sim 驱动器均装配 session,只登记不写状态的实现分支真实执行。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=_LSIG)
    assert gs.active_strategies.value == [_CARD], '注册入表'
    entries = gs.effects.by_source(SOURCE_STRATEGY)
    assert [e.spec.name for e in entries] == [_CARD], '登记入册'
    assert entries[0].spec.category.value == 'unit_buff', '战力类零响应载体'
    # burst 桥负锁:UnitBuffRef 无 free_refresh_burst → 缺省 0 no-op 零 Field 行
    # (只登记不写状态的实现分支内部已调,free_refresh_left 保持 None 即证;显式补调一次同证幂等)
    assert gs.free_refresh_left.value is None, 'burst 桥 no-op(零 Field 行)'
    seq_after_gain = gs.write_seq   # 入册本身占账本写;四桥零写以此为基
    spec = entries[0].spec
    apply_effect_burst_grant(gs, spec)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, 'burst 桥显式调用零写'
    # 板面重写桥负锁:board_rewrite 缺省 '' → None
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.write_seq == seq_after_gain
    # 节点边界桥负锁:free_refresh_per_node/on_node_enter 族缺省 0 → 零授予
    grant_effect_node_refresh_balance(gs)
    assert gs.free_refresh_left.value is None \
        and gs.write_seq == seq_after_gain, '节点边界桥 no-op'
    # 容量直写桥负锁:capacity_limit 缺省 0 → target=默认 9,bench 容量原值早退
    project_effect_capacity(gs)
    assert gs.write_seq == seq_after_gain, '容量直写桥 no-op'
    assert gs.bench.value.capacity == 9, '容量默认值未被改写'
    # session=None 支:登记跳过、注册照常(登记分支同型断言)
    gs2 = _make_gs()
    gain_invest_strategy(gs2, None, _CARD, rand=False, sig=_LSIG)
    assert gs2.active_strategies.value == [_CARD], '注册照常'
    assert gs2.effects.by_source(SOURCE_STRATEGY) == [], 'session=None 跳过'
