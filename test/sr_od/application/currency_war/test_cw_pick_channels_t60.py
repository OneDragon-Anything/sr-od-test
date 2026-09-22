"""T-60 验收修复批锁:零写迁移通道锁(补给确认 pick_supply,银狼闭环
design.md §2.2 确定性通道·通道宿主迁移)。

设计正本 = changes/2026-09-18-yinlang-exclusive-loop/design.md §2.2 +
landing.md §3.2④(3.2 批漏项,本批补齐)。锁面:

- **补给单位腿锁** = 按实际开出内容应用(char 入席 +
  装备后果腿;supply 为即时单相上报——确认点击后一口写
  owned 规范名 + 单位腿 + 后果腿,补给确认无第二写边);
- **零写退役锁**:zero_writes 两行委托不复存在,包级命名规约解析路由到
  具名模块;发射相写入者登记面锁(op 模块导入期全量自登记,缺登记 =
  实机发射相 ValueError 炸动作链);
- **未解析名翻来源锁**(既有形态):随机开出件名未解析 = 值不变翻来源
  + 留证行;补给内容全未知(兜底点卡路径)= 受影响域值不变翻来源;
- **载荷扩展不换键**:归一件名/角色载荷字段 action_key_exclude(幂等键
  不变,PickInvest 先例)。

(原选择装备屏 pick_equip 通道锁已随该屏误判退役删除——屏不存在,
见外循环退役号 0a0。)

观察收口基座锁(等值静默/差异 logic_rand_outcome)=
test_cw_game_state.py::test_write_logic_rand_and_observe_random_outcome,
不重复。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    pick_supply as pick_supply_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report import (
    zero_writes as zero_writes_mod,
)
from sr_od.application.currency_war.kernel.cw_action_report.pick_supply import (
    report_action_pick_supply_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    bench_units_of,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionPickSupplyParam,
    action_key,
)

# 本文件签名写入者登记(测试惯例;发射相 actor = 动作 op 类名)。

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')


def _lsig(actor: str) -> ChannelSig:
    return ChannelSig(family='logic_action', actor=actor, mode='compute')


def _make_gs(*, bench: list[tuple[str, int]] | None = None,
             equips: list[str] | None = None) -> GameState:
    """观测面按参组装(None = 保持未观察,供 None 边界腿)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if bench is not None:
        slots = [BenchSlot(kind='unit',
                           unit=Unit(char_id=c, star=s, slot=i + 1))
                 for i, (c, s) in enumerate(bench)]
        slots += [BenchSlot(kind='empty')] * (9 - len(slots))
        gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    if equips is not None:
        gs.observe(gs.equips, list(equips), sig=_SIG_OBS)
    return gs


def _units(gs: GameState) -> list[tuple[str, int]]:
    return [(u.char_id, u.star) for u in bench_units_of(gs)]


class _RowSink:
    """缺陷台账行收集(set_defect_sink 缺省关,fixture 装配 + 必达收尾)。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        set_defect_sink(self.rows.append)

    def close(self) -> None:
        set_defect_sink(None)
        consume_defect_sink()

    def kinds(self) -> list[str]:
        return [r['kind'] for r in self.rows]


@pytest.fixture
def rows_sink() -> _RowSink:
    s = _RowSink()
    try:
        yield s
    finally:
        s.close()


# ============================================================ 通道迁移锁


def test_pick_supply_immediate_char_and_consequence(
        rows_sink: _RowSink) -> None:
    """补给确认即时单相上报锁(迭代 2026-09-21-event-refresh-unify-
    supply-pick design §2.0B):一口写 owned 规范名 + 单位腿(char 入席
    1★ + 合成级联)+ 装备后果腿(命中表 → 送角色腿)——无发射/落地
    两相,无证据参数。"""
    gs = _make_gs(bench=[('银狼', 1), ('银狼', 1)], equips=[])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='银狼',
                                    norm_item='分身墨镜'),
        _lsig('CwActionPickSupplyOp'))
    assert out.applied is True
    units = _units(gs)
    assert ('银狼', 2) in units and ('银狼', 1) in units, \
        '单位腿 1★入席合成 2★ + 后果腿送出 1★(购买同语义)'
    assert gs.bench.source == 'logic', '双腿同源 write_logic'
    assert gs.equips.value == ['分身墨镜'], 'owned += 规范名(即时入栏)'
    assert gs.equips.source == 'logic', '入栏 write_logic(单相一口写)'


# ============================================================ 零写退役锁


def test_zero_write_delegates_retired_and_routing_migrated() -> None:
    """零写退役锁:zero_writes 委托行(pick_supply + 工具七类,
    后者随 tool-gain-report 迭代迁 tool_use)不复存在;包级命名规约解析
    路由到具名模块(直接 import 零写委托的旧消费面 = AttributeError
    响亮)。"""
    assert not hasattr(zero_writes_mod, 'report_action_pick_supply_param'), \
        'pick_supply 零写委托已迁出'
    for name in ('report_action_furnace_use_param',
                 'report_action_privilege_card_use_param',
                 'report_action_wrench_use_param',
                 'report_action_precision_wrench_use_param',
                 'report_action_staff_projector_use_param',
                 'report_action_perfect_projector_use_param',
                 'report_action_lucky_token_use_param'):
        assert not hasattr(zero_writes_mod, name), \
            f'{name} 零写委托已迁出(tool_use 容器写)'
    assert pick_supply_mod.report_action_pick_supply_param.__module__ \
        .endswith('.pick_supply'), '包级解析路由到 pick_supply 具名模块'


def test_pick_channels_payload_fields_excluded_from_action_key() -> None:
    """载荷扩展不换键(照 PickInvest 先例):归一件名/角色载荷字段
    action_key_exclude,幂等键与纯 idx 形态恒等。"""
    assert action_key(CwActionPickSupplyParam(idx=2, char_name='银狼',
                                              norm_item='分身墨镜Max')) \
        == action_key(CwActionPickSupplyParam(idx=2)), 'supply 载荷不入键'


# ============================================================ 未解析名翻来源锁


def test_pick_supply_equip_unresolved_flips_source(
        rows_sink: _RowSink) -> None:
    """补给装备名未解析(既有形态):单位腿照常应用,装备腿禁猜——
    equips 值不变翻来源 + 留证行。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['折叠小刀'])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0, char_name='希儿', norm_item=''),
        _lsig('CwScreenSupplyNode'))
    assert out.applied is True
    assert ('希儿', 1) in _units(gs), '单位腿不受装备名未解析影响'
    assert gs.equips.value == ['折叠小刀'], '装备腿值不变'
    assert gs.equips.source == 'logic_rand', '翻来源'
    assert rows_sink.kinds() == ['pick_supply_name_unresolved'], '留证行 kind'


def test_pick_supply_content_unknown_flips_domains(
        rows_sink: _RowSink) -> None:
    """补给内容全未知(兜底点卡路径,载荷空):禁猜——bench/equips 值
    不变翻来源 + 留证行(观察覆盖差异收口自愈)。"""
    gs = _make_gs(bench=[('希儿', 1)], equips=['折叠小刀'])
    out = report_action_pick_supply_param(
        gs, CwActionPickSupplyParam(idx=0),
        _lsig('CwScreenSupplyNode'))
    assert out.applied is True and out.reason == 'content_unresolved'
    assert _units(gs) == [('希儿', 1)] and gs.bench.source == 'logic_rand', \
        'bench 值不变翻来源'
    assert gs.equips.value == ['折叠小刀'] and gs.equips.source == 'logic_rand', \
        'equips 值不变翻来源'
    assert rows_sink.kinds() == ['pick_supply_content_unresolved'], '留证行 kind'
