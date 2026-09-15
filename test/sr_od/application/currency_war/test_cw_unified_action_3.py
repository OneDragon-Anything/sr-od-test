"""CW 统一动作工厂 批3 锁面(备战执行器收编:体迁零行为,出战链在册
例外)。

出处 = docs/develop/sr_od/application/currency_war/changes/
2026-09-14-unified-action-factory/landing.md §3.3 判据 +
design.md §2.4(分派改查注册表 / PrepExecEnv detail-emitted 旁路 /
终结判定对齐 terminal+terminal_wait / OpenShopOp terminal 承载行 /
StartBattleOp 基类契约在册例外)。规则正本 =
flow/action-logic-state.md 与 flow/logic-updates/prep-executor-actions.md。

锁面全部为运行时行为锁(源码扫描测试禁止,AGENTS.md §10.4);
kernel/执行器级用桩宿主,零真实 IO(harness 惯例同 test_cw_unified_action_2a)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_vocab import (
    ClickSpheres,
    DeployMove,
    FurnaceUse,
    LevelUp,
    LevelUpShop,
    LuckyTokenUse,
    OpenBookcard,
    OpenBox,
    OpenShop,
    OpenTome,
    SellBench,
    SellDeployed,
    StartBattle,
    WearEquip,
    WrenchUse,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for,
    action_op_for,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_box_action import (
    OpenBoxOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_shop_action import (
    OpenShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_sell_bench_action import (
    PrepSellBenchOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_tool_use_action import (
    ToolUseOp,
)
from sr_od.application.currency_war.prep_actions import (
    _OVERLAY_ANIM_WAIT_S,
    PrepActionExecutor,
)

# ===== 终结集与 terminal 等价锁(判据:终结集与 terminal 属性逐一等价;
# ===== OpenBox terminal_wait 同源比对随行迁并)=====

def _op_cls(action):
    return action_op_class_for(action)


def test_prep_terminal_set_matches_registry_terminal_attrs():
    """备战环终结集 = {StartBattle, OpenShop, OpenBox}(R7 并入 OpenBox)
    ⟺ 注册表 op 类 terminal=True,逐一等价;备战机械动作全部非终结
    (终结判定改读 op 类属性后,消费点两处共用本判据面)。OpenBox
    terminal_wait 同源比对:op 类属性 = 批2a 落地交回等待常量对象
    (``_OVERLAY_ANIM_WAIT_S``,漂移即红,禁消费点私表)。"""
    terminal_cases = [StartBattle(), OpenShop(), OpenBox()]
    for a in terminal_cases:
        assert _op_cls(a).terminal is True, type(a).__name__
    assert OpenBoxOp.terminal_wait == _OVERLAY_ANIM_WAIT_S
    mechanical_cases = [
        SellBench(bench_idx=0),
        SellDeployed(deployed_idx=0),
        DeployMove(bench_idx=0, to_row='front', faction=''),
        WearEquip(item_name='轮滑鞋', char_name='刃', row='front', slot=1),
        ClickSpheres(points=((1, 2),)),
        OpenTome(),
        OpenBookcard(),
        LevelUp(cost=4),
        LevelUpShop(cost=4),
        FurnaceUse(target_kind='char', row='front', slot=1),
        WrenchUse(row='front', slot=1),
        LuckyTokenUse(row='front', slot=1),
    ]
    for a in mechanical_cases:
        assert _op_cls(a).terminal is False, type(a).__name__


# ===== OpenShop 注册行不可达性锁(判据:OpenShop 行不可达性锁)=====

def test_open_shop_row_is_terminal_carrier_and_execute_loud_fails():
    """OpenShopOp = terminal 承载行:注册表解析可命中;execute 抛
    AssertionError(防静默复活)——OpenShop 流程编排归画面 op 流程层
    (cw_screen_prep._act_execute_default 截流),注册行在正常路径不可达,
    可达即分派漏斗被绕过。read_only 两形态 = 动作字段承载(op 实例持
    动作对象,注册表不表达形态分叉)。"""
    for a in (OpenShop(), OpenShop(read_only=True)):
        op = action_op_for(a)
        assert type(op) is OpenShopOp
        assert op.action.read_only == a.read_only
        env = SimpleNamespace(detail='', emitted=False)
        with pytest.raises(AssertionError):
            op.execute(env)


# ===== StartBattle 基类契约在册例外锁(判据:例外条款落基类契约登记口;
# ===== A6 挂账指向在册 = StartBattleOp 模块头申报,本锁锁行为半)=====

class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[Point] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point) -> None:
        self.clicks.append(p)


def _make_executor(controller: _RecordingController) -> PrepActionExecutor:
    """执行器桩宿主(同 unified_action_2a harness 形状;本文件自持)。"""
    op = SimpleNamespace(park_cursor=lambda **kw: None,
                         screenshot=lambda: object(),
                         save_screenshot=lambda prefix='': 'stub.png')
    ctx = SimpleNamespace(controller=controller, cw_match=None,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return PrepActionExecutor(op, ctx)


def test_start_battle_execute_and_envelope_write_launch_fact(monkeypatch):
    """在册例外 + 包络腿(两条并 1):StartBattleOp.execute 返回值 =
    发射位**内部事实**(非恒 True;找不到按钮/未落地 = False),并经
    env 旁路写 (detail, emitted) 供 runner 包络消费(last_launch_ok/
    exec_state 写点在包络);经注册表分派后写 ``executor.last_launch_ok``
    旁路(cw_loop 发射链读点;A6 判效面批4 同退役)与机械摘要
    ``last_detail``,执行缝金差恒 0(非卖非点球),薄委托替身缝返回序
    保持原 (ok, detail)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
        StartBattleOp as _SBO,
    )
    op = _SBO(StartBattle())
    ex = _make_executor(_RecordingController())
    env = SimpleNamespace(op=ex._op, match=None, config=None,
                          executor=ex, detail='', emitted=False)
    # 未落地形态:常规发射与重发均未落地(session 缺 = 连败计数挂空,
    # escalate 放行)→ execute 返回 False
    monkeypatch.setattr(_SBO, '_launch_attempt',
                        lambda self, ex, press_time=0.1:
                        (False, '出战 click 未落地'))
    assert op.execute(env) is False            # 返回值非恒 True(内部事实)
    assert env.emitted is False
    assert '未落地' in env.detail
    # 落地形态:execute True + env 旁路 (detail, emitted)
    monkeypatch.setattr(_SBO, '_launch_attempt',
                        lambda self, ex, press_time=0.1: (True, '出战成功'))
    assert op.execute(env) is True
    assert env.emitted is True and env.detail == '出战成功'
    # 包络腿:发射位内部事实写 executor 旁路与机械摘要
    ex.execute(StartBattle())
    assert ex.last_launch_ok is True
    assert ex.last_detail == '出战成功'
    assert ex.last_gold_delta == 0
    # 薄委托替身缝:返回序保持原 (ok, detail)
    assert ex._start_battle() == (True, '出战成功')


# ===== 分派收编锁(判据:分派链删除改查注册表)=====

def test_prep_dispatch_resolves_registry_rows_and_loud_unknown():
    """备战分派单一注册表:词表类解析到批3 收编 op 类(代表行 = 基础
    卖件行 + 工具族并行行;分派查同一张注册表,逐类行对账由终结集锁与
    OpenShop 锁分面承压);词表外类型 = 注册表 AssertionError 响亮暴露
    (原 isinstance 链尾「未知动作类型」静默回退退役;生产不可达,
    F3 validate 先拒)。"""
    rows = [
        (SellBench(bench_idx=0), PrepSellBenchOp),
        (FurnaceUse(target_kind='char', row='front', slot=1), ToolUseOp),
    ]
    for a, expected in rows:
        assert type(action_op_for(a)) is expected
        assert _op_cls(a) is expected
    ex = PrepActionExecutor.__new__(PrepActionExecutor)
    ex._op = SimpleNamespace()
    ex._ctx = SimpleNamespace(cw_match=None)
    with pytest.raises(AssertionError):
        ex._dispatch_action(SimpleNamespace())   # 词表外 → 响亮暴露
