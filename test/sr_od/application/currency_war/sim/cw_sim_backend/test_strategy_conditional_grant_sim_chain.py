"""sim 世界链测试(镜像 src = 获得链 check_strategy_conditional_grants
经 sim 节点推进;§2.4 申报 sim 零新增接入调用——tick 实机(live)和模拟器(sim)两边同链,sim 容器现值
= 世界真值)。

测试面依据 = 迭代设计 designs/T-102-guimo-xiaoying.md §4 锁 8:
持卡 + 容器直置齐 8 同名 → 推进节点(kernel advance_node_effective 尾段
tick,sim/live 同链零 sim 私有接线)→ sim equips 尾追完美投影仪 + 闩在
(strategy_conditional_done)。

直构形态先例 = 同目录 test_env_bond_tier_sim_chain.py(_backend 装配 +
uninstall 端口槽纪律 + 缺陷缓冲隔离 fixture 副本)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    Unit,
    advance_node_effective,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SimBackend,
    uninstall_backend,
)

_CARD = '规模效应'
_EQUIP = '完美投影仪'
_NAME = '希儿'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def test_scale_effect_grants_in_sim_world(_isolate_defect_buffer) -> None:
    """sim 端到端(锁 8):装配后端(1-1 窗已过 tick,持卡前零发放)→
    持卡 + 容器直置 8 同名 → 推进到 1-2(tick advanced 位闸)→ sim
    equips 尾追完美投影仪 + 闩落——世界真值,使用面(tool_use 上报链)
    天然可消费。"""
    b: SimBackend = _backend(7)
    try:
        gs = b.gs
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='test-seed', evidence='t:card', sig=_SIG)
        assert _EQUIP not in (gs.equips.value or []), '持卡前误发放'
        slots = [BenchSlot(kind='unit', unit=Unit(char_id=_NAME, star=1))
                 for _ in range(8)]
        slots += [BenchSlot(kind='empty')]
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9),
                   sig=_SIG_OBS)
        assert advance_node_effective(gs, (1, 2), actor='SimBackendTest',
                                      sig=_SIG, source='logic'), '推进被挡'
        assert gs.equips.value is not None \
            and gs.equips.value[-1] == _EQUIP, \
            f'sim 世界未发放: {gs.equips.value!r}'
        assert gs.strategy_conditional_done.value == (_CARD,), \
            f'闩未落: {gs.strategy_conditional_done.value!r}'
    finally:
        uninstall_backend()
