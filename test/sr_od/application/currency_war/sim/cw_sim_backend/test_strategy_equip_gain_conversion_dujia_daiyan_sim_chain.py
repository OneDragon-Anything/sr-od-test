"""独家代言 sim 世界真值链测试(镜像 src 主断言对象 = 获得链 gain_equipment
顶段转换拦截经 sim 后端开箱全链;拦截在 kernel 原语,sim 零新增接线——
sim 容器现值 = 世界真值,live 零写观察覆盖为双端同真值的另一端口径)。

测试面依据 = 迭代设计 designs/T-372-dujia-daiyan.md §4 锁 5(开箱链
机械回归:名单集转换辖域含开箱所得——候选前缀 ∋ 幸运星,持卡局开箱
选定幸运星即转换,防默认辖域被静默豁免)+ REVIEW-T372 §3.2.8(开箱链
现址亲测)。直构形态先例 = 同目录
test_strategy_equip_gain_conversion_sim_chain.py 锁 8〔自由市场版〕/
test_strategy_equip_gain_conversion_haoyunlai_sim_chain.py〔休眠镜像面〕。
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
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOX,
    SCREEN_BRIEFING,
    SCREEN_PREP,
    SimBackend,
    box_options,
    uninstall_backend,
)

_CARD = '独家代言'

_TARGET = '以牙还牙甲'

_MEMBER = '幸运星'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(沿同目录同名 fixture 先例,fixture 不可跨文件
    import 故本文件自带同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def test_held_card_box_chain_converts_member_pick(
        _isolate_defect_buffer) -> None:
    """持卡箱链转换锁(设计 §4 锁 5):持本卡(sim 直置)+ 种 1 箱 →
    开箱选定名单成员幸运星 → **转换生效**(幸运星不入栏、以牙还牙甲
    入栏)、零箱落位;开箱腾席 = 观察域容器零写,sim 侧开掉的箱槽不移除
    (断言用箱数不变量)。前提守卫:开箱候选前缀 ∋ 幸运星——若未来
    候选池改版踢出名单成员,持本卡局开箱零转换属卡面字面正确行为,本锁
    前提失效须随批改,勿盲改断言。"""
    cands = box_options()
    assert _MEMBER in cands, \
        f'前提:开箱候选 ∋ 名单成员(漂移须随批改): {cands!r}'
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
        box_out = report_action_open_box_param(
            gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(box_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX, '箱画面呈现'
        shown = gs.box_card_names.value
        assert shown is not None and len(shown) == 4, '候选写容器'
        idx = list(shown).index(_MEMBER)
        b._handle_click_source(SCREEN_BOX, f'装备卡-{idx + 1}')
        pick_box = report_action_pick_box_card_param(
            gs, SimpleNamespace(), _SIG)
        assert pick_box.applied
        cw_sim_ports.declare_world(pick_box.world_decl)
        assert _MEMBER not in (gs.equips.value or []), \
            f'被选名单成员不入栏(转换): {gs.equips.value!r}'
        assert gs.equips.value == [_TARGET], '转换产物入栏恰 +1'
        boxes = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert len(boxes) == 1, '零箱落位(开掉的箱槽零写不移除)'
        assert b.screen_identity() == SCREEN_PREP, '模态交回备战'
    finally:
        uninstall_backend()


def test_held_card_box_chain_non_member_passes(
        _isolate_defect_buffer) -> None:
    """持卡箱链非成员面(锁 5 姊妹面):开箱选定非名单成员(以太钻头,
    简易但 ∉ 名单集)→ 照常入栏零转换(转换按名单不按类别)。前提守卫:
    候选 ∋ 以太钻头(漂移须随批改)。"""
    cands = box_options()
    assert '以太钻头' in cands, \
        f'前提:开箱候选 ∋ 非名单简易件(漂移须随批改): {cands!r}'
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
        box_out = report_action_open_box_param(
            gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(box_out.world_decl)
        shown = gs.box_card_names.value
        idx = list(shown).index('以太钻头')
        b._handle_click_source(SCREEN_BOX, f'装备卡-{idx + 1}')
        pick_box = report_action_pick_box_card_param(
            gs, SimpleNamespace(), _SIG)
        assert pick_box.applied
        cw_sim_ports.declare_world(pick_box.world_decl)
        assert '以太钻头' in (gs.equips.value or []), \
            f'非名单成员照常入栏(零转换): {gs.equips.value!r}'
        assert _TARGET not in (gs.equips.value or []), '零转换产物'
        assert b.screen_identity() == SCREEN_PREP, '模态交回备战'
    finally:
        uninstall_backend()
