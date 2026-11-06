"""固定理财只登记不写状态的实现分支测试(gain_invest_strategy 分目录镜像;即时段 burst +
位面段中途拿卡补发,登记拍双桥)。

测试面依据 = 迭代设计 designs/T-182-gudinglicai.md §2.6/§4(锁 7 burst
回归 + 锁 3 裁定 B 改形)+ 用户裁定书 T-182 节(2026-11-01 用户决定:中途
拿卡时当前已开始的位面,其位面段奖励照常发放〔全额〕):
- burst 回归锁(锁 7):即时段 free_refresh_burst=2 现值不变(防注册行
  改写误伤即时段);
- 补发锁(裁定 B):窗内登记(session 在场 ∧ node 在场)→ 补发桥再
  +2(evidence ``effect_plane_refire@frame``,与 burst 笔分键),合计 +4;
- session=None = 登记分支跳过(登记分支 best-effort 语义),burst/补发
  双零——直发形态(T-46 策略大师 session=None)与 burst 桥同域,本批
  不扩(申报面);
- node 缺席(直构状态容器局外形态)= burst 照发、补发保守零(「已开始」
  判据不可评估,禁猜)。
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


def test_gain_fixed_licai_burst_plus_plane_refire() -> None:
    """窗内登记:burst(+2 即时段)+ 补发桥(+2 当前已开始位面段)
    合计 +4,两笔 evidence 分键(effect_burst / effect_plane_refire)。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '固定理财', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['固定理财']
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['固定理财'], 'register_strategy 入册'
    assert gs.free_refresh_left.value == STRATEGY_ECONOMY['固定理财'] \
        .free_refresh_burst + STRATEGY_ECONOMY['固定理财'] \
        .free_refresh_per_plane, 'burst + 补发合计 +4'
    assert gs.free_refresh_left.source == 'logic'


def test_gain_fixed_licai_session_none_skips_both_legs() -> None:
    """session=None = 登记分支跳过(直发形态与 burst 同域申报):注册
    照常,burst/补发双零(None 基不动)。"""
    gs = _make_gs()
    gain_invest_strategy(gs, None, '固定理财', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['固定理财'], '注册照常'
    assert gs.effects.by_source(SOURCE_STRATEGY) == [], '登记分支跳过'
    assert gs.free_refresh_left.value is None, '双零累加(零 Field 行)'


def test_gain_fixed_licai_node_absent_burst_only() -> None:
    """node 缺席(局外形态):burst 照发(+2),补发保守零——「当前
    位面已开始」判据不可评估禁猜。"""
    gs = _make_gs(node=None)
    gain_invest_strategy(gs, object(), '固定理财', rand=False, sig=_lsig())
    assert gs.free_refresh_left.value == 2, '仅即时段 burst'
    assert (gs.free_refresh_left.evidence or '').startswith('effect_burst')
