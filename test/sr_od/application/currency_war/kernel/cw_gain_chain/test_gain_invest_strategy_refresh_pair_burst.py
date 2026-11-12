"""合并同类项只登记不写状态的实现分支 burst 发放测试(gain_invest_strategy 分目录镜像;
free_refresh_burst 登记期发放族)。

锁 1:session 在场选「合并同类项」→ 获得链只登记不写状态的实现分支 register_strategy 入册 +
burst 桥把 ``payload.free_refresh_burst=4`` 一次性累加进免费刷新余额
(None 基 = 0 起算)。断言形 = 免费午餐/市场干预 burst 锁同款
write_logic 调用面捕获(produced_by 带卡名、evidence effect_burst[@frame])。
"""
from __future__ import annotations

import pytest

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
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _make_gs() -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    return gs


def test_gain_invest_strategy_refresh_pair_burst_grant(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 1:选卡只登记不写状态的实现分支 → burst 桥 +free_refresh_burst 一次性发放(常量源 =
    STRATEGY_ECONOMY['合并同类项'].free_refresh_burst 直读禁写死);写端 =
    write_logic 逻辑直写、evidence effect_burst[@frame]、produced_by 带卡名。
    锁面出处:「合并同类项」设计稿 §4 锁 1(卡面:「获得4次免费刷新」)。"""
    captured: list[tuple] = []
    real_write = GameState.write_logic

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), value,
                         kw.get('produced_by'), kw.get('evidence')))
        return real_write(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic', _spy)
    gs = _make_gs()
    gain_invest_strategy(gs, object(), '合并同类项', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['合并同类项'], '注册入表'
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['合并同类项'], 'register_strategy 入册'
    burst = STRATEGY_ECONOMY['合并同类项'].free_refresh_burst
    assert gs.free_refresh_left.value == burst, \
        'None 基 = 0 起算,一次 +burst'
    assert gs.free_refresh_left.source == 'logic', 'write_logic 逻辑直写'
    assert (gs.free_refresh_left.evidence or '').startswith('effect_burst'), \
        'burst 桥 evidence(effect_burst[@frame])'
    assert captured[-1][2] == 'EffectLedgerBridge:合并同类项', \
        f'produced_by 带卡名: {captured[-1]}'
