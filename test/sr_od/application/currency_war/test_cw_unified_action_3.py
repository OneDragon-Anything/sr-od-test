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
from test.harness.fixture_controller import fast_sleep

from one_dragon.base.geometry.point import Point
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionCollectOreParam,
    CwActionDeployMoveParam,
    CwActionFurnaceUseParam,
    CwActionLevelUpParam,
    CwActionLevelUpShopParam,
    CwActionLuckyTokenUseParam,
    CwActionObsParam,
    CwActionOpenBookcardParam,
    CwActionOpenBoxParam,
    CwActionOpenShopParam,
    CwActionOpenTomeParam,
    CwActionSellBenchParam,
    CwActionSellDeployedParam,
    CwActionStartBattleParam,
    CwActionWearEquipParam,
    CwActionWrenchUseParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_box_action import (
    CwActionOpenBoxOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_open_shop_action import (
    CwActionOpenShopOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_prep_sell_bench_action import (
    CwActionSellBenchOp,
)
from sr_od.application.currency_war.operations.cw_op.cw_tool_use_action import (
    CwActionToolUseOp,
)
from sr_od.application.currency_war.prep_actions import (
    _OVERLAY_ANIM_WAIT_S,
    PrepActionExecutor,
)

# ===== 终结集与 terminal 等价锁(判据:终结集与 terminal 属性逐一等价;
# ===== CwActionOpenBoxParam terminal_wait 同源比对随行迁并)=====

def _op_cls(action):
    return action_op_class_for(action)


def test_prep_terminal_set_matches_registry_terminal_attrs():
    """备战环终结集 = {CwActionStartBattleParam, CwActionOpenShopParam,
    CwActionOpenBoxParam, CwActionOpenBookcardParam}(R7 并入 CwActionOpenBoxParam;
    2026-09-19 用户裁定开卡时机归策略器,OpenBookcard 终结化——弹专家邀请函
    = 新事实,交回外循环重观察)⟺ 注册表 op 类 terminal=True,逐一等价;
    备战机械动作全部非终结。terminal_wait 同源比对:OpenBoxOp =
    ``_OVERLAY_ANIM_WAIT_S``(批2a 落地交回等待常量对象,漂移即红,禁消费点
    私表);OpenBookcardOp 同源(原画面 op 入口代交回等待同值)。"""
    terminal_cases = [
        CwActionStartBattleParam(),
        CwActionOpenShopParam(),
        CwActionOpenBoxParam(),
        CwActionOpenBookcardParam(),
    ]
    for a in terminal_cases:
        assert _op_cls(a).terminal is True, type(a).__name__
    assert CwActionOpenBoxOp.terminal_wait == _OVERLAY_ANIM_WAIT_S
    from sr_od.application.currency_war.operations.cw_op.cw_open_bookcard_action import (
        CwActionOpenBookcardOp,
    )
    assert CwActionOpenBookcardOp.terminal_wait == _OVERLAY_ANIM_WAIT_S
    mechanical_cases = [
        CwActionSellBenchParam(bench_idx=0),
        CwActionSellDeployedParam(deployed_idx=0),
        CwActionDeployMoveParam(bench_idx=0, to_row='front', faction=''),
        CwActionWearEquipParam(item_name='轮滑鞋', char_name='刃', row='front', slot=1),
        CwActionCollectOreParam(points=((1, 2),)),
        CwActionOpenTomeParam(),
        CwActionLevelUpParam(cost=4),
        CwActionLevelUpShopParam(cost=4),
        CwActionFurnaceUseParam(target_kind='char', row='front', slot=1),
        CwActionWrenchUseParam(row='front', slot=1),
        CwActionLuckyTokenUseParam(row='front', slot=1),
        CwActionObsParam(),   # 环内重观察:非终结(执行后决策环原地续跑)
    ]
    for a in mechanical_cases:
        assert _op_cls(a).terminal is False, type(a).__name__


# ===== CwActionOpenShopParam 注册行不可达性锁(判据:CwActionOpenShopParam 行不可达性锁)=====

def test_open_shop_row_is_terminal_carrier_and_execute_loud_fails():
    """CwActionOpenShopOp = terminal 承载行:注册表解析可命中;执行抛
    AssertionError(防静默复活)——CwActionOpenShopParam 流程编排归画面 op 流程层
    (cw_screen_prep._act_execute_default 截流),注册行在正常路径不可达,
    可达即分派漏斗被绕过。read_only 两形态 = 动作字段承载(op 实例持
    动作对象,注册表不表达形态分叉)。"""
    for a in (CwActionOpenShopParam(), CwActionOpenShopParam(read_only=True)):
        op = CwActionOpenShopOp(SimpleNamespace(), a, env=SimpleNamespace())
        assert op.param.read_only == a.read_only
        with pytest.raises(AssertionError):
            op.run()


# ===== CwActionStartBattleParam 基类契约在册例外锁(T-286 出战域重设计:点击序列语义;
# ===== 弹窗确认路径 + 免战子态上报 + 免战牌递减经 game state 上报路径)=====

#: 识别命中表的键 = (画面名, area 名)(op 桩 round_by_find_area 的判定面)。
_HIT_BTN = ('货币战争-备战', '按钮-出战')
_HIT_SKIP = ('货币战争-备战', '按钮-跳过')
_HIT_NOTFULL = ('货币战争-未达上限警告', '标识-未达上限警告')
_HIT_NOFRONT = ('货币战争-提示-前台无角色', '标识-无角色提示')

#: area_center 桩返回表:每个交互 area 一个定值点(区分点击对象)。
_AREA_POINTS = {
    _HIT_BTN: Point(100, 200),
    ('货币战争-备战-开商店', '按钮-出战'): Point(100, 200),
    _HIT_SKIP: Point(110, 200),
    ('货币战争-未达上限警告', '勾选-本局不再提示'): Point(300, 400),
    ('货币战争-未达上限警告', '按钮-确认'): Point(301, 401),
    ('货币战争-提示-前台无角色', '按钮-确认'): Point(302, 402),
}


class _RecordingController:
    def __init__(self) -> None:
        self.moves: list[Point] = []
        self.clicks: list[Point] = []

    def mouse_move(self, p: Point) -> None:
        self.moves.append(p)

    def click(self, p: Point) -> None:
        self.clicks.append(p)


def _patch_area_center(monkeypatch) -> None:
    """op 模块级 area_center 桩(命中表返回定值点;screen_info 坐标解析
    本身不属本锁面,本锁只锁 op 的决策/点击序列)。"""
    from sr_od.application.currency_war.operations.cw_op import (
        cw_start_battle_action as _sba,
    )
    monkeypatch.setattr(
        _sba, 'area_center',
        lambda ctx, name, screen_name=_sba.SCREEN_NAME:
        _AREA_POINTS.get((screen_name, name)))


def _make_stub_op(hits: set[tuple[str, str]]):
    """op 桩:screenshot 恒同帧对象,round_by_find_area 按命中表演。"""

    def _find(_screen, screen_name: str, area_name: str, **_kw):
        return SimpleNamespace(is_success=(screen_name, area_name) in hits)

    return SimpleNamespace(screenshot=lambda: object(),
                           round_by_find_area=_find,
                           save_screenshot=lambda prefix='': 'stub.png')


def _make_executor(controller: _RecordingController, stub_op,
                   cw_match=None) -> PrepActionExecutor:
    """执行器桩宿主(同 unified_action_2a harness 形状;本文件自持)。"""
    ctx = SimpleNamespace(controller=controller, cw_match=cw_match,
                          run_context=None,
                          screen_loader=SimpleNamespace(
                              get_screen=lambda name: None))
    return PrepActionExecutor(stub_op, ctx)


def _make_env(ex: PrepActionExecutor) -> SimpleNamespace:
    return SimpleNamespace(op=ex._op, match=None, config=None,
                           executor=ex, detail='', emitted=False,
                           skip_substate=False)


def test_start_battle_click_sequence_and_envelope(monkeypatch):
    """在册例外(点击序列语义)+ 三条弹窗路径 + 包络腿(并 1):

    - 常规帧:出战一次单击 → True(detail = 已点击无弹窗);零验证
      (无轮询/重试面,单击即完成交回);
    - 未达上限帧:勾选+确认两击后完成(勾选幂等,ADR-0136 行为对齐);
    - 前台无角色帧:确认一击后完成;
    - 找不到按钮:两屏查空 → False + 「未执行:找不到按钮」上报 + 零点击
      (交回外循环重判,不炸);
    - 包络腿:经注册表分派写 ``executor.last_launch_ok`` 旁路(点击序列
      已执行语义)与机械摘要 ``last_detail``,执行缝金差恒 0,薄委托
      替身缝返回序保持原 (ok, detail)。"""
    from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
        CwActionStartBattleOp as _SBO,
    )
    _patch_area_center(monkeypatch)
    # op 桩构造基座(op 自 ctx 仅作 SrOperation 形参;无 cw_match = 上报跳过)
    def _make(ex):
        env = _make_env(ex)
        return _SBO(SimpleNamespace(), CwActionStartBattleParam(), env=env), env

    _patch_area_center(monkeypatch)
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op({_HIT_BTN}))
    op, env = _make(ex)
    # 常规帧:无弹窗(直调路径 status 走 round 结果;last_detail 是 runner
    # 包装写点,包络腿段另验)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN]]
    assert '出战已点击' in result.status and '无弹窗' in result.status
    # 未达上限帧:勾选 + 确认
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op({_HIT_BTN, _HIT_NOTFULL}))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN],
                          _AREA_POINTS[('货币战争-未达上限警告',
                                        '勾选-本局不再提示')],
                          _AREA_POINTS[('货币战争-未达上限警告',
                                        '按钮-确认')]]
    assert '未达上限警告:勾选+确认' in result.status
    assert result.is_success is True and env.skip_substate is False
    # 前台无角色帧:确认
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op({_HIT_BTN, _HIT_NOFRONT}))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_BTN],
                          _AREA_POINTS[('货币战争-提示-前台无角色',
                                        '按钮-确认')]]
    assert '前台无角色提示:确认' in result.status
    # 找不到按钮:未执行上报 + 零点击
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op(set()))
    op, env = _make(ex)
    with fast_sleep():
        result = op.run()
    assert result.is_success is False
    assert result.status == '未执行:找不到按钮'
    assert ctl.clicks == []
    # 包络腿:注册表分派路径的旁路写点(点击序列已执行语义)
    _patch_area_center(monkeypatch)
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op({_HIT_BTN}))
    with fast_sleep():
        ex.execute(CwActionStartBattleParam())
    assert ex.last_launch_ok is True
    assert '出战已点击' in ex.last_detail
    assert ex.last_gold_delta == 0
    # 薄委托替身缝:返回序保持原 (ok, detail)
    assert ex._start_battle()[0] is True


def test_start_battle_skip_substate_reported_not_consumed(monkeypatch):
    """免战子态上报锁(T-286):出战 miss + 「按钮-跳过」命中 → 点跳过
    坐标 + env.skip_substate True;递减本体 = op 自上报(行为锁见免战牌
    递减锁),op 直调层零多余容器写。"""
    from sr_od.application.currency_war.operations.cw_op.cw_start_battle_action import (
        CwActionStartBattleOp as _SBO,
    )
    _patch_area_center(monkeypatch)
    ctl = _RecordingController()
    ex = _make_executor(ctl, _make_stub_op({_HIT_SKIP}))
    env = _make_env(ex)
    op = _SBO(SimpleNamespace(), CwActionStartBattleParam(), env=env)
    with fast_sleep():
        result = op.run()
    assert result.is_success is True
    assert env.skip_substate is True
    assert ctl.clicks == [_AREA_POINTS[_HIT_SKIP]]
    assert '出战已点击' in result.status


def test_freeze_card_decrement_via_report_path(monkeypatch):
    """免战牌递减经 op 自上报锁(T-286;批③ 接线):PrepActionExecutor
    .execute(跳过型 CwActionStartBattleParam)→ op 自上报
    report_action_start_battle_param 在 session effects 递减 remaining_uses
    (上报时递减);常规出战零递减;未登记(登记面缺位)零动作不炸。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        game_state_of,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )
    _patch_area_center(monkeypatch)
    # 跳过型:登记免战牌 → 经包络执行 → 递减 2→1
    sess = SimpleNamespace()
    gs = game_state_of(sess)
    gs.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=None)
    ex = _make_executor(_RecordingController(), _make_stub_op({_HIT_SKIP}),
                        cw_match=SimpleNamespace(session=sess))
    with fast_sleep():
        ex.execute(CwActionStartBattleParam())
    assert gs.effects.first(STRATEGY_EFFECTS['免战牌'].id).remaining_uses == 1
    # 常规出战(非跳过):零递减
    sess2 = SimpleNamespace()
    bs2 = game_state_of(sess2)
    bs2.effects.register_strategy(STRATEGY_EFFECTS['免战牌'], acquired_t=None)
    ex2 = _make_executor(_RecordingController(), _make_stub_op({_HIT_BTN}),
                         cw_match=SimpleNamespace(session=sess2))
    with fast_sleep():
        ex2.execute(CwActionStartBattleParam())
    assert bs2.effects.first(
        STRATEGY_EFFECTS['免战牌'].id).remaining_uses == 2
    # 未登记:零动作不炸(递减挂点与登记面解耦;execute 无返回契约,
    # 不抛 = 链路完整)
    sess3 = SimpleNamespace()
    ex3 = _make_executor(_RecordingController(), _make_stub_op({_HIT_SKIP}),
                         cw_match=SimpleNamespace(session=sess3))
    with fast_sleep():
        ex3.execute(CwActionStartBattleParam())
    assert ex3.last_launch_ok is True


# ===== 分派收编锁(判据:分派链删除改查注册表)=====

def test_prep_dispatch_resolves_registry_rows_and_loud_unknown():
    """备战分派单一注册表:词表类解析到批3 收编 op 类(代表行 = 基础
    卖件行 + 工具族并行行;分派查同一张注册表,逐类行对账由终结集锁与
    CwActionOpenShopParam 锁分面承压);词表外类型 = 注册表 AssertionError 响亮暴露
    (原 isinstance 链尾「未知动作类型」静默回退退役;生产不可达,
    F3 validate 先拒)。"""
    rows = [
        (CwActionSellBenchParam(bench_idx=0), CwActionSellBenchOp),
        (CwActionFurnaceUseParam(target_kind='char', row='front', slot=1), CwActionToolUseOp),
    ]
    for a, expected in rows:
        assert action_op_class_for(a) is expected
        assert _op_cls(a) is expected
    ex = PrepActionExecutor.__new__(PrepActionExecutor)
    ex._op = SimpleNamespace()
    ex._ctx = SimpleNamespace(cw_match=None)
    with pytest.raises(AssertionError):
        ex._dispatch_action(SimpleNamespace())   # 词表外 → 响亮暴露
