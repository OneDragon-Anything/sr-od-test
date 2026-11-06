"""自由市场 sim 世界真值链测试(镜像 src 主断言对象 = 获得链 gain_equipment
顶段转换拦截经 sim 后端全链;拦截在 kernel 原语,sim 零新增接线——sim
容器现值 = 世界真值,live 零写观察覆盖为双端同真值的另一端口径)。

测试面依据 = 迭代设计 designs/T-143-ziyou-shichang.md §4 锁 7/锁 8 +
REVIEW-T143 §4③ 裁决点 3 默认案(转换辖域 = 全域字面含开箱所得,机械
回归 = 本文件锁 8,防「辖域含开箱」裁定落地后被静默豁免):
- 锁 7 选卡链:offer 注入自由市场 → pick → bench 含箱 ∧ equips 零新增
  (效果条目2 采样名被转换消费,净得 1 箱);
- 锁 8 开箱环路:持卡 + 开箱选定简易件 → 被选件不入栏 + 转换箱落位 +1
  (开箱腾席 = 观察域容器零写,sim 侧开掉的箱槽不移除;live 真值 = 净
  箱数守恒「开一箱转换回一箱」,装备零净得两侧同真)。

直构形态先例 = 同目录 test_strategy_conditional_grant_sim_chain.py(_backend
装配 + uninstall 端口槽纪律 + 缺陷缓冲隔离 fixture 副本)/
test_env_expert_invite_sim_chain.py(开箱链三上报形态)。
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
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_gain_chain import (
    gain_bench_item,
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
    stream_rng,
    uninstall_backend,
)

_CARD = '自由市场'


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


def test_free_market_pick_chain_converts_leg2(
        _isolate_defect_buffer) -> None:
    """sim 选卡链(锁 7):装配后端 → offer 注入 → pick 自由市场 →
    bench 恰 +1 简易武装箱(带名槽件)∧ equips 零新增(效果条目2 采样名被
    转换消费)——世界真值,使用面(tool_use 上报链)天然可消费;
    rng 显式流键构造(缺省回退自掷破 sim 确定性,采样腿族纪律)。"""
    b: SimBackend = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        equips_before = list(gs.equips.value or [])
        gs.write_logic(gs.invest_strategy_opts,
                       [_CARD, '躺平', '淘金客'],
                       produced_by='Test', evidence='t:opts', sig=_SIG)
        out = report_action_pick_invest_strategy_param(
            gs, SimpleNamespace(norm_name=_CARD), _SIG,
            session=SimpleNamespace(),
            rng=stream_rng(7, 'M25/equip-gain-conv'))
        assert out.applied
        assert _CARD in gs.active_strategies.value, '注册入表'
        boxes = [s for s in gs.bench.value.slots
                 if s is not None and s.kind == 'supply_box']
        assert len(boxes) == 1 and boxes[0].item == '简易武装箱', \
            f'效果条目2 采样经转换净得 1 箱: {[(s.kind, s.item) for s in gs.bench.value.slots if s is not None and s.kind != "empty"]!r}'
        assert gs.equips.value == equips_before, \
            f'被转换装备零入栏: {gs.equips.value!r}'
    finally:
        uninstall_backend()


def test_box_open_loop_intercepts_chosen_equip(
        _isolate_defect_buffer) -> None:
    """sim 开箱环路(锁 8,裁决点 3 默认案机械回归):持卡(sim 直置,
    T-102 sim 链先例形态)+ 种 1 箱 → 开箱选定简易件 → 被选件不入栏 +
    转换箱落位恰 +1。开箱腾席 = 观察域容器零写(zero_writes 正本申报),
    sim 侧开掉的箱槽不被移除——断言用 +1 非「箱数守恒」;live 真值 =
    净箱数守恒(开一箱转换回一箱),装备零净得两侧同真。"""
    b: SimBackend = _backend(7)
    try:
        b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        gs.write_logic(gs.active_strategies, [_CARD],
                       produced_by='Test', evidence='t:card', sig=_SIG)
        assert gain_bench_item(gs, '简易武装箱', rand=False, sig=_SIG,
                               evidence='t:seed-box'), '种箱落位'
        boxes_before = _box_count(gs)
        assert boxes_before == 1, '种箱基线'
        box_out = report_action_open_box_param(
            gs, CwActionOpenBoxParam(), _SIG)
        cw_sim_ports.declare_world(box_out.world_decl)
        assert b.screen_identity() == SCREEN_BOX, '箱画面呈现'
        cands = gs.box_card_names.value
        assert cands is not None and len(cands) == 4, '候选写容器'
        # 前提守卫:箱候选池现值全简易(裁决点 3 全域辖域的前提;若未来
        # 箱池混入非简易件,转换不命中属卡面字面正确行为,本锁前提失效
        # 须随批改,勿盲改断言)
        assert all(c in equips_by_category('简易') for c in cands), \
            f'箱候选须全简易: {cands!r}'
        b._handle_click_source(SCREEN_BOX, '装备卡-3')
        pick_box = report_action_pick_box_card_param(
            gs, SimpleNamespace(), _SIG)
        assert pick_box.applied
        cw_sim_ports.declare_world(pick_box.world_decl)
        assert cands[2] not in (gs.equips.value or []), \
            f'被选简易件不入栏(转换): {gs.equips.value!r}'
        assert _box_count(gs) == boxes_before + 1, \
            '转换箱落位恰 +1(开掉的箱槽零写不移除)'
        assert b.screen_identity() == SCREEN_PREP, '模态交回备战'
    finally:
        uninstall_backend()
