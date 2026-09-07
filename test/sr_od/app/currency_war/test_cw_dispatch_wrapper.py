"""dispatch 包装锁(T-121/ADR-0584:画面分支统一经 _dispatch_screen_op 分发)。

锁面(T-121 方案 §6.1 测试面声明;判定/排他/序位/守卫域归属不在此辖):
- 包装行为:journal enter/exit 成对 + outcome 口径(.success)+ 默认映射
  wait/on_fail_retry + on_result 覆盖默认返回 + frame_tag=None 跳过落帧;
- 0n 元组适配:visit_open_shop 形的 (ok, detail) 可调用经包装落 op 行;
- 链形透传(0j/3c):返回 OperationRoundResult 的零参可调用原样交回;
- 心跳不变量:三处流程心跳载体行(锁定直出战/补给分流/收益耗尽臂出战,
  ADR-0554;方案审 N1 计数口径)不随推进分支包装增减;
- S11 接线:0n 转交通道 journal_name='商店访问'(复盘按 journal 直读商店
  访问边界的对齐关键行,ADR-0584 §3.3);
- B5 守卫钩子:窗口关/闩清在 on_result 闭包(战斗宽限守卫域留外循环)。

测试纪律:零真实副作用(journal 重定向 tmp_path、帧落盘替身、等待替身)。
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.telemetry import op_journal

_LOOP_SRC = inspect.getsource(cw_loop.CwLoop.loop)


@pytest.fixture()
def journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """journal 落盘重定向 tmp_path(测试纪律 1/2,与 test_cw_op_journal 同款)。"""
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(op_journal, '_JOURNAL', out)
    monkeypatch.setattr(op_journal, '_frame_seq_by_run', {})
    monkeypatch.setattr(op_journal, 'current_run_id', lambda: 'run_wrap')
    return out


def _bare_loop(monkeypatch: pytest.MonkeyPatch) -> Any:
    """裸 CwLoop 实例(绕过 __init__ 的 run 级装配):ctx 桩 + 副作用替身。"""
    op = cw_loop.CwLoop.__new__(cw_loop.CwLoop)
    op.ctx = SimpleNamespace(cw_match=None)   # _op_journal_pos → (0, 0)
    op.last_screenshot = None   # 包装落帧实参替身(save_decision_frame 已桩)
    monkeypatch.setattr(op, '_interruptible_sleep', lambda s: None,
                        raising=False)
    monkeypatch.setattr(cw_loop, 'save_decision_frame',
                        lambda *a, **k: 'frame.png')
    return op


def _op_result(ok: bool, status: str = 'stub') -> SimpleNamespace:
    """op.execute() 返回形态替身(OperationResult 的 .success/.status 读面)。"""
    return SimpleNamespace(success=ok, status=status)


def _op_rows(path: Path, op_name: str) -> list[dict]:
    rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    return [r for r in rows if r.get('kind') == 'op' and r.get('op') == op_name]


# ==================== 包装行为(journal 成对/结果映射) ====================


def test_wrapper_journal_pair_and_outcome(journal: Path, monkeypatch) -> None:
    """journal enter/exit 成对 + outcome 按 .success 口径(ADR-0579 流形态)。"""
    op = _bare_loop(monkeypatch)
    ret = op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: _op_result(True)),
        journal_name='位面过渡', frame_tag=None, wait=0)
    rows = _op_rows(journal, '位面过渡')
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'ok'
    assert ret.result == OperationRoundResultEnum.WAIT   # 默认映射 round_wait


def test_wrapper_fail_without_retry_still_waits(journal: Path, monkeypatch) -> None:
    """on_fail_retry 缺省:失败也走 round_wait(overlay 消费面既有口径)。"""
    op = _bare_loop(monkeypatch)
    ret = op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: _op_result(False)),
        journal_name='遭遇节点', frame_tag=None, wait=0)
    rows = _op_rows(journal, '遭遇节点')
    assert rows[1]['outcome'] == 'fail'
    assert ret.result == OperationRoundResultEnum.WAIT


def test_wrapper_on_fail_retry_maps_retry(journal: Path, monkeypatch) -> None:
    """on_fail_retry=True:op 失败映射 loop 级 round_retry(单尝试合同的重试
    预算承接面;与原分支内联 round_retry 消费同一 retry 池)。"""
    op = _bare_loop(monkeypatch)
    ret = op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: _op_result(False)),
        journal_name='策划事件', frame_tag=None, wait=0, on_fail_retry=True)
    assert ret.result == OperationRoundResultEnum.RETRY


def test_wrapper_on_result_overrides_default(journal: Path, monkeypatch) -> None:
    """on_result 返回 round 对象 = 覆盖默认返回(0q 超限 round_fail 形);
    返回 None = 走默认映射(A1/0n/B5 形)。"""
    op = _bare_loop(monkeypatch)
    fail_ret = op.round_fail('超限')
    ret1 = op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: _op_result(False)),
        journal_name='A', frame_tag=None, wait=0,
        on_result=lambda ok, res: fail_ret)
    ret2 = op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: _op_result(True)),
        journal_name='B', frame_tag=None, wait=0,
        on_result=lambda ok, res: None)
    assert ret1 is fail_ret
    assert ret2.result == OperationRoundResultEnum.WAIT


def test_wrapper_frame_tag_none_skips_frame(journal: Path, monkeypatch) -> None:
    """frame_tag=None = 跳过落帧(留证面零扩的可退选项,ADR-0584 §2.3)。"""
    op = _bare_loop(monkeypatch)
    seen: list[Any] = []
    monkeypatch.setattr(cw_loop, 'save_decision_frame',
                        lambda *a, **k: seen.append(a) or 'f.png')
    op._dispatch_screen_op(SimpleNamespace(execute=lambda: _op_result(True)),
                           journal_name='X', frame_tag=None, wait=0)
    assert not seen           # None 跳过
    op._dispatch_screen_op(SimpleNamespace(execute=lambda: _op_result(True)),
                           journal_name='Y', frame_tag='tag_y', wait=0)
    assert seen and seen[0][1] == 'tag_y'   # 带 tag 落帧


# ==================== 0n 元组适配 + 链形透传 ====================


def test_wrapper_callable_tuple_adapter(journal: Path, monkeypatch) -> None:
    """0n 形:零参可调用返回 (ok, detail) 元组 → 包装经 _FnResult 适配落行
    (visit_open_shop 本体不进本测,壳契约在此锁;S11 op='商店访问' 同形)。"""
    op = _bare_loop(monkeypatch)
    ret = op._dispatch_screen_op(
        lambda: (True, '买牌 x3'),   # 访问成功形态
        journal_name='商店访问', frame_tag=None, wait=0)
    rows = _op_rows(journal, '商店访问')
    assert rows[1]['outcome'] == 'ok'
    assert ret.result == OperationRoundResultEnum.WAIT


def test_wrapper_chain_result_passthrough(journal: Path, monkeypatch) -> None:
    """链形(0j/3c):可调用返回 OperationRoundResult → 原样透传,journal
    outcome = 非 FAIL/RETRY 即 ok。"""
    op = _bare_loop(monkeypatch)
    wait3 = op.round_wait(wait=0)
    ret = op._dispatch_screen_op(
        lambda: wait3, journal_name='回大厅收口', frame_tag=None, wait=0)
    assert ret is wait3
    rows = _op_rows(journal, '回大厅收口')
    assert rows[1]['outcome'] == 'ok'
    fail_ret = op.round_fail('超限')
    op._dispatch_screen_op(lambda: fail_ret,
                           journal_name='前台无角色恢复', frame_tag=None, wait=0)
    rows = _op_rows(journal, '前台无角色恢复')
    assert rows[1]['outcome'] == 'fail'


# ==================== 源码接线不变量(顺序即语义档) ====================


def test_heartbeat_carrier_rows_invariant() -> None:
    """心跳不变量(方案审 N1 计数口径):流程心跳载体行恰三处——锁定直出战/
    补给分流/收益耗尽臂出战(ADR-0554;cw_loop.register_flow_heartbeat docstring
    自陈「三类流程心跳」)。推进分支包装零新增载体行(推进分支零 decisions 行
    是正确归属,ADR-0584 §3.2);第 4 处出现 = 红时登记「该分支为何需要心跳」。"""
    assert _LOOP_SRC.count('register_flow_heartbeat(') == 3


def test_0n_shop_visit_journal_wired() -> None:
    """S11 对齐关键行(ADR-0584 §3.3):0n 转交通道经包装落 op='商店访问' 行
    (复盘按 journal 直读商店访问边界;显式开店通道走 OpenShop 决策行段,
    两载体并存口径见 ADR-0584 §4.4-2)。"""
    assert "journal_name='商店访问'" in _LOOP_SRC


def test_battle_window_guard_hooks_in_closure() -> None:
    """B5 守卫钩子在分支闭包(settle 注入/窗口关/闩清 = ADR-0250 守卫域,
    留外循环不进 op):窗口关(saw_settlement)与闩清在 on_battle_wait 闭包内,
    且闩清在源内恰一处赋 False(包装外的第二清点 = 出口归一被破坏)。"""
    i_def = _LOOP_SRC.find('def _on_battle_wait')
    i_dispatch = _LOOP_SRC.find('self._battle_wait,')
    assert 0 < i_def < i_dispatch, '战斗窗守卫钩子未内联于分支(守卫域外泄)'
    seg = _LOOP_SRC[i_def:i_dispatch]
    assert 'saw_settlement' in seg
    assert 'self._battle_wait_active = False' in seg
