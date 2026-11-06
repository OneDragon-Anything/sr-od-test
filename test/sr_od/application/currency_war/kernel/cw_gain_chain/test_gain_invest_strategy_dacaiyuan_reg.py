"""大裁员只登记不写状态的实现分支测试(gain_invest_strategy 分目录镜像;卖全场族登记型
建模——BattlefieldEffect 载体携 burst 首例,单条目双桥同拍各司其职,
先例 = 同目录 test_gain_invest_strategy_refresh_pair_burst.py)。

锁 4(只登记不写状态的实现分支 burst 挂点锁,镜像固定理财/合并同类项 burst 锁形):
session 在场选「大裁员」→ 获得链只登记不写状态的实现分支 register_strategy 入册 + burst 桥
把 ``payload.free_refresh_burst=6`` 一次性累加进免费刷新余额(None 基 =
0 起算)+ 板面重写桥出售面同拍执行(预种 2★1 费退款恰 3——cost=1 无
手续费,×2 两候选口径同值的确定性锚;缺口 G4 闭合前按基础公式记)。
挂点 = 只登记不写状态的实现分支(②段)回归钉,防漂移到 ③段效果体。
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
    Unit,
    deployed_rows_of_view,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    deployed_view_sequential as _dvs,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')

_SOLD = ('三月七', 2)   # 2★1 费:退款 = max(1,1)×3 = 3,cost=1 无手续费


def _lsig() -> ChannelSig:
    return ChannelSig(family='logic_action', actor='CwGainChain',
                      mode='compute')


def _make_gs() -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    gs.observe(gs.equips, [], sig=_SIG_OBS)
    # 金观察底座(退款入金前置:gold 未读 = 无累加基座,桥跳过金写)。
    gs.observe(gs.gold, 10, sig=_SIG_OBS)
    return gs


def test_gain_invest_strategy_dacaiyuan_burst_and_sell(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 4:选卡只登记不写状态的实现分支一拍双桥——burst +6(常量源 =
    STRATEGY_ECONOMY['大裁员'].free_refresh_burst 直读禁写死)+ 出售面
    清场退款(2★1 费锚恰 3)。写端 = write_logic 逻辑直写,burst 笔
    evidence effect_burst[@frame]、produced_by 带卡名。"""
    captured: list[tuple] = []
    real_write = GameState.write_logic

    def _spy(self: GameState, target, value, **kw):
        captured.append((self._field_name(target), value,
                         kw.get('produced_by'), kw.get('evidence')))
        return real_write(self, target, value, **kw)

    monkeypatch.setattr(GameState, 'write_logic', _spy)
    gs = _make_gs()
    gs.observe(gs.deployed,
               _dvs([Unit(char_id=_SOLD[0], star=_SOLD[1])], []),
               sig=_SIG_OBS)
    gain_invest_strategy(gs, object(), '大裁员', rand=False, sig=_lsig())
    assert gs.active_strategies.value == ['大裁员'], '注册入表'
    assert [e.spec.name for e in gs.effects.by_source(SOURCE_STRATEGY)] \
        == ['大裁员'], 'register_strategy 入册'
    burst = STRATEGY_ECONOMY['大裁员'].free_refresh_burst
    assert burst == 6 and gs.free_refresh_left.value == burst, \
        'None 基 = 0 起算,一次 +6(只登记不写状态的实现分支 burst 插入位置,防漂移到 ③段)'
    assert gs.free_refresh_left.source == 'logic', 'write_logic 逻辑直写'
    assert (gs.free_refresh_left.evidence or '').startswith('effect_burst'), \
        'burst 桥 evidence(effect_burst[@frame])'
    _f, _bk = deployed_rows_of_view(gs.deployed.value)
    assert (_f, _bk) == ([], []), '场清空(出售面,板面重写桥同拍)'
    assert gs.gold.value == 13, \
        '退款恰 3(2★1 费,cost=1 无手续费,×2 两候选口径同值锚;G4 缺口' \
        '闭合前基础公式记)'
    burst_rows = [c for c in captured
                  if c[0] == 'free_refresh_left'
                  and str(c[3] or '').startswith('effect_burst')]
    assert burst_rows and burst_rows[-1][2] == 'EffectLedgerBridge:大裁员', \
        f'produced_by 带卡名: {burst_rows}'
