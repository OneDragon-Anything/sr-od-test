"""固定理财+ 登记腿测试(gain_invest_strategy 分目录镜像;即时段 burst
解锁 + 位面段中途拿卡补发,登记拍双桥;先例 =
test_gain_invest_strategy_gudinglicai_reg.py)。

测试面依据 = 迭代设计 designs/T-183-gudinglicai-plus.md §4(锁 3 burst
解锁回归)+ 用户裁定书 T-182 节同判(2026-11-01 拍定:中途拿卡时当前
已开始的位面,其位面段奖励照常发放〔全额〕,两卡一次拍定):
- burst 解锁回归锁(锁 3):本卡此前无 STRATEGY_EFFECTS 条目 = 登记腿闸
  整体跳过,+3 恒不发(死建模);补条后窗内登记 burst +3 照发——死建模
  解锁的回归面(改前该断言必红);
- 补发锁(同判 B):窗内登记(session 在场 ∧ node 在场)→ 补发桥再
  +3(evidence ``effect_plane_refire@frame``,与 burst 笔分键),合计 +6;
- node 缺席(直构容器局外形态)= burst 照发、补发保守零(「已开始」
  判据不可评估,禁猜);
- session=None 登记分支整体跳过形不另设对照腿(姊妹同形测试已辖同代码
  路径,两条测同一件事 = 冗余,沿设计稿补充对账裁剪)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    SOURCE_STRATEGY,
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
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _make_gs(*, node: tuple[int, int] | None = (2, 3)) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    if node is not None:
        gs.observe(gs.node, NodeKey(plane=node[0], round_num=node[1],
                                    kind='battle'),
                   evidence='t:seed', sig=_SIG_OBS)
    return gs


def test_gain_fixed_licai_plus_burst_plus_plane_refire() -> None:
    """窗内登记:burst(+3 即时段)+ 补发桥(+3 当前已开始位面段)
    合计 +6(死建模解锁回归:改前无条目恒零发)。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '固定理财+', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['固定理财+']
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['固定理财+'], 'register_strategy 入册'
    assert gs.free_refresh_left.value == STRATEGY_ECONOMY['固定理财+'] \
        .free_refresh_burst + STRATEGY_ECONOMY['固定理财+'] \
        .free_refresh_per_plane, 'burst + 补发合计 +6'
    assert gs.free_refresh_left.source == 'logic'


def test_gain_fixed_licai_plus_node_absent_burst_only() -> None:
    """node 缺席(局外形态):burst 照发(+3),补发保守零——「当前
    位面已开始」判据不可评估禁猜。"""
    gs = _make_gs(node=None)
    gain_invest_strategy(gs, object(), '固定理财+', rand=False, sig=_lsig())
    assert gs.free_refresh_left.value == 3, '仅即时段 burst'
    assert (gs.free_refresh_left.evidence or '').startswith('effect_burst')
