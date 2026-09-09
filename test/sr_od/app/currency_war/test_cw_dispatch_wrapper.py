"""dispatch 包装锁(T-121/ADR-0584:画面分支统一经 _dispatch_screen_op 分发)。

锁面(判定/排他/序位/守卫域归属不在此辖):
- 包装行为:journal enter/exit 成对 + outcome 口径(.success)(ADR-0579
  流形态;ok 路径对照臂的唯一承载,异常注入臂在 test_cw_op_boundary);
- 0n 元组适配:visit_open_shop 形的 (ok, detail) 可调用经包装落 op 行;
- S11 接线:0n 转交通道 journal_name='商店访问'(复盘按 journal 直读商店
  访问边界的对齐关键行,ADR-0584 §3.3)。

CUT6 瘦身批(2026-09-09):实机每局反复走过的映射/透传/选项面砍除
(默认映射 wait/on_fail_retry、on_result 覆盖、frame_tag 落帧、链形
透传 0j/3c、心跳计数、B5 闭包守卫域)——包装被实机逐屏走过,失守即
现场炸;保留核清单 = reports/_cluster_CUT6.md。

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


# ==================== 源码接线不变量(顺序即语义档) ====================


def test_0n_shop_visit_journal_wired() -> None:
    """S11 对齐关键行(ADR-0584 §3.3):0n 转交通道经包装落 op='商店访问' 行
    (复盘按 journal 直读商店访问边界;显式开店通道走 OpenShop 决策行段,
    两载体并存口径见 ADR-0584 §4.4-2)。"""
    assert "journal_name='商店访问'" in _LOOP_SRC


