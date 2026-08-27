"""W308 行为锁:补给节点停机钩子(遇补给画面即停机保画面,供人工观察基础金币)。

临时捕获类钩子(od-dev-stop-hooks §2.1),观察完成后整段删除——本测试文件随之删除。
锁两件事:①触发时 stop_running 被调 + sentinel flag 落盘(flag 路径 monkeypatch 指 tmp_path,
不写真实 .debug);②非补给画面(前置门未命中)不触发。补一个源码级弱锁保底:handle 入口
真接线(先于 _run_node 调钩子),防「钩子还在但没人调」的假活。
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResult,
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.operations.run_nodes import run_supply_node
from sr_od.application.currency_war.operations.run_nodes.run_supply_node import (
    RunSupplyNode,
)


def _make_op(monkeypatch, tmp_path, *, in_node: bool):
    """构 RunSupplyNode 桩(bypass __init__),mock 全部外设面。

    返回 (op, calls):calls = {'stop': int, 'shot': list[str], 'round_wait_status': list[str]}。
    """
    op = object.__new__(RunSupplyNode)
    rc = SimpleNamespace(stop_running=lambda: None)
    op.ctx = SimpleNamespace(
        run_context=rc,
        cw_match=None,
        current_instance_idx=1,
    )

    calls: dict = {'stop': 0, 'shot': [], 'round_wait_status': []}
    orig_stop = rc.stop_running
    rc.stop_running = lambda: calls.__setitem__('stop', calls['stop'] + 1)
    monkeypatch.setattr(op, '_in_node', lambda screen: in_node, raising=False)
    monkeypatch.setattr(op, 'save_screenshot', lambda prefix=None: f'{tmp_path}/{prefix}.png')
    # round_wait 走基类框架态(_after_round_wait 等),桩实例无;替换为记录型桩
    def _fake_round_wait(self, status: str | None = None, **_kw) -> OperationRoundResult:
        calls['round_wait_status'].append(status or '')
        return OperationRoundResult(result=OperationRoundResultEnum.WAIT, status=status)
    monkeypatch.setattr(RunSupplyNode, 'round_wait', _fake_round_wait)
    # 保险:若误触 controller/点击面,让测试炸出来而非静默发点击
    op.ctx.controller = SimpleNamespace(
        screenshot=lambda: (0.0, None),   # 框架 screenshot() 协议:(时间, 帧)
        mouse_move=lambda p: (_ for _ in ()).throw(AssertionError('钩子内不得 mouse_move/click')),
        click=lambda p: (_ for _ in ()).throw(AssertionError('钩子内不得 click')),
    )
    del orig_stop
    return op, calls


def test_hook_triggers_stop_and_flag(monkeypatch, tmp_path) -> None:
    """补给画面锚命中 → 截图存证 + flag 三要素落盘(tmp_path)+ stop_running 被调 + round_wait。"""
    flag = tmp_path / 'supply_stop_hook.flag'
    monkeypatch.setattr(run_supply_node, 'SUPPLY_STOP_HOOK_FLAG', flag)
    op, calls = _make_op(monkeypatch, tmp_path, in_node=True)

    result = op._supply_stop_hook()

    assert calls['stop'] == 1                                   # 停机被直调一次
    assert result is not None
    assert result.result == OperationRoundResultEnum.WAIT       # round_wait:不推进不消耗 retry 预算语义外的动作
    assert 'W308' in (result.status or '')
    assert flag.exists()
    text = flag.read_text(encoding='utf-8')
    assert 'HOOK-STOP' in text                                  # 要素① 触发定位
    assert '处理步骤' in text                                    # 要素② 可执行处理步骤
    assert '删除条件' in text                                    # 要素③ 删除条件


def test_hook_no_trigger_off_supply_screen(monkeypatch, tmp_path) -> None:
    """前置门未命中(非补给画面)→ 不停机不落盘,返回 None 走原流程。"""
    flag = tmp_path / 'supply_stop_hook.flag'
    monkeypatch.setattr(run_supply_node, 'SUPPLY_STOP_HOOK_FLAG', flag)
    op, calls = _make_op(monkeypatch, tmp_path, in_node=False)

    result = op._supply_stop_hook()

    assert result is None
    assert calls['stop'] == 0
    assert not flag.exists()


def test_handle_wiring_source_lock() -> None:
    """弱锁保底:handle 入口在 _run_node 前真接线调用停机钩子。"""
    src = inspect.getsource(RunSupplyNode.handle)
    assert '_supply_stop_hook()' in src
    hook_src = inspect.getsource(RunSupplyNode._supply_stop_hook)
    assert 'stop_running()' in hook_src
