"""成长基金只登记不写状态的实现分支可见性测试(镜像 src = kernel/cw_gain_chain.py 的
gain_invest_strategy 登记分支 × kernel/cw_investments.py 的
STRATEGY_EFFECTS 成长基金条目)。

测试面依据 = 迭代设计 designs/T-108-chengzhang-jijin.md §4 锁 5:
- gain_invest_strategy(session 在场)拿卡 → 效果账本含成长基金条目
  (trigger=CONDITIONAL / duration=WHILE_HELD / category=ECONOMY /
  payload 为 STRATEGY_ECONOMY 注册行同一实例 = 单一源);
- burst/板面两桥零行为(payload 无 instant/burst 字段、非
  BattlefieldEffect → 桥对空载荷 no-op):免费刷新余额零 Field 行、
  金零写(登记链跑完金现值/来源不变)。

构造沿现役获得链测试先例(kernel/test_gain_chain.py 全队的希望
登记链锁同形;本文件自带 helpers 副本,债文件禁追加)。
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
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_LSIG = ChannelSig(family='logic_action', actor='CwGainChain', mode='compute')

_CARD = '成长基金'


def _make_gs() -> GameState:
    """观测面组装(bench/equips 直构;登记链 best-effort 分支零触碰面)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.prep_anchored = True
    slots = [BenchSlot(kind='empty')] * 9
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_registration_visibility_and_spec_shape() -> None:
    """只登记不写状态的实现分支可见性(锁 5):session 在场拿卡 → 效果账本入册,条目规格
    四元组逐位 + payload 同一实例(单一源,误复制实例即红)。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=_LSIG)
    assert gs.active_strategies.value == [_CARD], '持卡注册'
    entries = gs.effects.by_source(SOURCE_STRATEGY)
    assert [e.spec.name for e in entries] == [_CARD], '效果账本未入册'
    spec = entries[0].spec
    assert spec.id == '101701', 'plaza id 对拍'
    assert spec.trigger.value == 'conditional', '到级型占 CONDITIONAL'
    assert spec.duration.value == 'while_held', '策略卡缺省持有绑定'
    assert spec.category.value == 'economy', '金发放归 ECONOMY'
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 必须为注册行同一实例(单一源)'


def test_bridges_noop_zero_world_write() -> None:
    """两桥零行为(锁 5 后半):登记链跑完(桥已内联调)免费刷新余额
    零 Field 行、金零写;显式补调两桥同证幂等 no-op。"""
    gs = _make_gs()
    gain_invest_strategy(gs, object(), _CARD, rand=False, sig=_LSIG)
    assert gs.free_refresh_left.value is None, 'burst 桥 no-op(零 Field 行)'
    assert gs.gold.value is None, '只登记不写状态的实现分支误写金'
    seq_before = gs.write_seq
    spec = gs.effects.by_source(SOURCE_STRATEGY)[0].spec
    apply_effect_burst_grant(gs, spec)
    assert apply_board_rewrite(gs, spec) is None, '板面重写桥 no-op'
    assert gs.free_refresh_left.value is None and gs.gold.value is None, \
        '补调误写'
    assert gs.write_seq == seq_before, '两桥补调零字段写操作'
