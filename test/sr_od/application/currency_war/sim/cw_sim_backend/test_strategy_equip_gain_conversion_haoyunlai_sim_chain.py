"""好运来 sim 世界真值链测试(镜像 src 主断言对象 = 获得链 gain_equipment
顶段转换拦截经 sim 后端全链;拦截在 kernel 原语,sim 零新增接入调用——sim
容器现值 = 状态副本里的值,live 零写观察覆盖为实机(live)和模拟器(sim)两边同真值的另一端口径)。

测试面依据 = 迭代设计 designs/T-248-haoyunlai.md §4 锁 7(合成域休眠
申报锁):
- 箱链零转换:sim 开箱候选池现值全简易(SYNTHESIS_BASES 派生),持本卡
  局开箱选定简易件 → 进阶谓词零命中**不转换**照常入栏(休眠正确路径,
  与模式卡自由市场的开箱环路转换互为镜像——自由市场版见
  test_strategy_equip_gain_conversion_sim_chain.py 锁 8);
- 合成域零事件:sim 无合成执行写端(穿戴/手动拖拽合成均不在 sim 现役
  写端面),持卡局合成域零事件零转换 = 结构性边界回归(任一 sim 进阶
  获得通道落地时,原语顶段自动入拦截,无需本域接入调用)。

直构形态先例 = 同目录 test_strategy_equip_gain_conversion_sim_chain.py
(_backend 装配 + uninstall 端口槽纪律 + 缺陷缓冲隔离 fixture 副本)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _backend,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_open_box_param,
    report_action_pick_box_card_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOX,
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    uninstall_backend,
)

_CARD = '好运来'

_TARGET = '好运令牌'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _box_count(gs) -> int:
    return sum(1 for s in gs.bench.value.slots
               if s is not None and s.kind == 'supply_box')


def test_held_card_box_chain_dormant_zero_conversion(
        _isolate_defect_buffer) -> None:
    """持卡箱链休眠锁(设计 §4 锁 7):持本卡(sim 直置)+ 种 1 箱 →
    开箱选定简易件 → **零转换**照常入栏(候选全简易不命中进阶谓词,
    休眠正确路径)、零箱落位、零令牌;开箱腾席 = 观察域容器零写,sim
    侧开掉的箱槽不移除(断言用箱数不变量)。前提守卫:箱候选池现值全
    简易——若未来箱池混入进阶件,持本卡局开箱选中进阶件将自动入转换
    (原语顶段单咽喉,行为正确、本锁前提失效须随批改,勿盲改断言)。"""
    b: SimBackend = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='Test', evidence='t:card', sig=_SIG)
        from sr_od.application.currency_war.kernel.cw_gain_chain import (
            gain_bench_item,
        )
        assert gain_bench_item(gs, '简易武装箱', rand=False, sig=_SIG,
                               evidence='t:seed-box'), '种箱落位'
        assert _box_count(gs) == 1, '种箱基线'
        box_out = report_action_open_box_param(
            gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(box_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX, '箱画面呈现'
        cands = gs.box_card_names.value
        assert cands is not None and len(cands) == 4, '候选写容器'
        assert all(c in equips_by_category('简易') for c in cands), \
            f'箱候选须全简易(休眠前提): {cands!r}'
        b._handle_click_source(SCREEN_BOX, '装备卡-1')
        pick_box = report_action_pick_box_card_param(
            gs, SimpleNamespace(), _SIG)
        assert pick_box.applied
        cw_sim_ports.declare_world(pick_box.world_decl)
        assert cands[0] in (gs.equips.value or []), \
            f'被选简易件照常入栏(零转换): {gs.equips.value!r}'
        assert _TARGET not in (gs.equips.value or []), '零令牌(零转换)'
        assert _box_count(gs) == 1, '零箱落位(开掉的箱槽零写不移除)'
        assert b.screen_identity() == SCREEN_PREP, '模态交回备战'
    finally:
        uninstall_backend()
