"""gain_invest_env 契约族回归测试(镜像 src = kernel/cw_gain_chain.py 的
被测函数 ``gain_invest_env``;按被测方法拆目录规范落位)。

测试面依据 = 设计稿(原件已退役)
设计稿(原件已退役)§4.7:量子同频契约经获得链整入口
落地 → 无即时发放(效果无即时分支,「获得环境当刻不发任何东西」现状
逐位不变;触发分支只在合并升星事件时序上,env-gain 时点零消费)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_invest_env,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG = ChannelSig(family='logic_action', actor='CwGainChainTest',
                  mode='compute')


def test_merge_contract_env_gain_no_immediate_grant() -> None:
    """契约族整入口回归(T-26 设计 §4.7):gain_invest_env('量子同频契约')
    → active_env 注册照常,bench 零新增(无即时分支,登记表写状态副本发放通道
    chars_immediate 空——随本迭代触发注册表新增,获得时点行为逐位不变;
    on_env_gained 直调负态 = kernel/test_gain_chain.py
    test_env_gift_conditional_only_quiet_after_random_leg,不重复)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench,
               BenchView(slots=[BenchSlot(kind='empty')] * 9, capacity=9),
               sig=_SIG_OBS)
    seq_before = gs.write_seq
    out = gain_invest_env(gs, None, '量子同频契约', rand=False, sig=_SIG)
    assert out.placed and out.effects == (), '无即时发放、零效果串'
    units = [s.unit.char_id for s in gs.bench.value.slots
             if s is not None and s.kind == 'unit' and s.unit is not None]
    assert units == [], 'bench 零新增'
    assert gs.active_env.value == '量子同频契约', '环境注册照常'
    # 恰两行 = active_env 注册 + 节点序列场(获得链固定两写),无发放行
    assert gs.write_seq - seq_before == 2, \
        f'零发放写(仅注册两行): {gs.write_seq - seq_before}'
