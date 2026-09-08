"""op 边界遥测补全锁(T-130;口径单一源 = ADR-0584 §5 三载体扩展)。

锁面:
- dispatch 包装异常安全:op 体/on_result 抛异常时仍发 op exit 行
  (outcome='error')后原样上抛——孤儿 enter 语义回归「进程中断专属」
  (ADR-0584 §5.2);
- 达标臂仲裁段第三载体:仲裁触发的商店访问落 op='发射帧仲裁商店访问'
  enter/exit 成对行,非访问路径(预检未过/带内 fail-closed)零行
  (ADR-0584 §5.1);
- 预清场收编接线:备战前书册卡清场经包装落 op='专家邀请函' 行,与 0k
  分支同名(消灭「同一 op 双通道行不一致」,ADR-0584 §5.3)。

测试纪律:journal 重定向 tmp_path;kernel/op 缝替身 = 模块属性替换(与
test_cw_launch_arbitrage 行为锁同缝位)。既有 test_cw_dispatch_wrapper 的
行为锁面不在此重复;仅保留一条 ok 对照臂证明 error 断言有牙(该文件
fixture 在遥测面改动后破损,修复后按重复断言纪律并回)。
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.telemetry import op_journal


@pytest.fixture()
def journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """journal 落盘重定向 tmp_path(零真实副作用;不桩已删除的软上限计数)。"""
    out = tmp_path / 'op_journal.jsonl'
    monkeypatch.setattr(op_journal, '_JOURNAL', out)
    monkeypatch.setattr(op_journal, '_frame_seq_by_run', {})
    monkeypatch.setattr(op_journal, 'current_run_id', lambda: 'run_boundary')
    return out


def _bare_loop(monkeypatch: pytest.MonkeyPatch) -> Any:
    """裸 CwLoop 实例(绕过 __init__ 的 run 级装配;与既有包装锁同形)。"""
    op = cw_loop.CwLoop.__new__(cw_loop.CwLoop)
    op.ctx = SimpleNamespace(cw_match=None)   # _op_journal_pos → (0, 0)
    op.last_screenshot = None
    monkeypatch.setattr(op, '_interruptible_sleep', lambda s: None,
                        raising=False)
    monkeypatch.setattr(cw_loop, 'save_decision_frame',
                        lambda *a, **k: 'frame.png')
    return op


def _op_rows(path: Path, op_name: str) -> list[dict]:
    if not path.exists():   # 零行路径(文件未落)等价空流
        return []
    rows = [json.loads(x) for x in
            path.read_text(encoding='utf-8').splitlines()]
    return [r for r in rows
            if r.get('kind') == 'op' and r.get('op') == op_name]


# ==================== 包装异常安全(异常注入红测) ====================


def test_wrapper_ok_path_control(journal: Path, monkeypatch) -> None:
    """对照臂:正常路径 enter/exit 成对且 outcome='ok'——证明 error 断言
    非恒真(error 行只出现在异常路径)。"""
    op = _bare_loop(monkeypatch)
    op._dispatch_screen_op(
        SimpleNamespace(execute=lambda: SimpleNamespace(success=True,
                                                        status='stub')),
        journal_name='位面过渡', frame_tag=None, wait=0)
    rows = _op_rows(journal, '位面过渡')
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'ok'


def test_wrapper_execute_exception_still_emits_exit(
        journal: Path, monkeypatch) -> None:
    """异常注入(op 体抛):exit 行仍发(outcome='error')且异常原样上抛——
    异常语义归节点级重试链,包装只保 journal 配对(ADR-0584 §5.2)。"""
    op = _bare_loop(monkeypatch)

    def _boom() -> None:
        raise RuntimeError('op体异常注入')

    with pytest.raises(RuntimeError):
        op._dispatch_screen_op(
            SimpleNamespace(execute=_boom),
            journal_name='遭遇节点', frame_tag=None, wait=0)
    rows = _op_rows(journal, '遭遇节点')
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'error'
    assert rows[1].get('detail')   # 异常摘要在行内可辨


def test_wrapper_on_result_exception_still_emits_exit(
        journal: Path, monkeypatch) -> None:
    """异常注入(on_result 守卫钩子抛):exit 行仍发——钩子调用点在
    record_op_exit 之前,异常路径不跳过闭合(ADR-0584 §5.2)。"""
    op = _bare_loop(monkeypatch)

    def _hook_boom(ok: bool, res: Any) -> None:
        raise ValueError('钩子异常注入')

    with pytest.raises(ValueError):
        op._dispatch_screen_op(
            SimpleNamespace(execute=lambda: SimpleNamespace(success=True,
                                                            status='stub')),
            journal_name='位面过渡', frame_tag=None, wait=0,
            on_result=_hook_boom)
    rows = _op_rows(journal, '位面过渡')
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'error'


# ==================== 仲裁段第三载体(journal 行流对照) ====================


def _arb_op(monkeypatch: pytest.MonkeyPatch, *, prep_hit: bool = True,
            open_ok: bool = True, gold: int = 80, hp: int = 42,
            waves: str = 'ok', close_ok: bool = True,
            waves_exc: Exception | None = None) -> tuple[Any, Any, dict]:
    """仲裁宿主 op 桩 + 模块缝替身(test_cw_launch_arbitrage 同缝位)。

    带内/溢出分界用与该锁相同的 gold 值(80 溢出 / 40 带内),判定走真实
    kernel 函数(不桩判据)。返回 (op, session, calls)。"""
    from sr_od.application.currency_war.obs import cw_observation
    from sr_od.application.currency_war.operations.cw_op import (
        cw_op_buy_cards,
        cw_op_close_shop,
        cw_op_open_shop,
    )

    st = SimpleNamespace(cw4_counters={})
    sess = SimpleNamespace(strategy_state=st,
                           shop_state_frame=SimpleNamespace(gold=gold))
    calls = {'open': 0, 'close': 0, 'waves': 0}

    def _find_area(screen: Any, screen_name: str, area_name: str,
                   **kw: Any) -> Any:
        hit = prep_hit or (screen_name, area_name) != (
            '货币战争-备战', '备战标识-购买经验')
        return SimpleNamespace(is_success=hit)

    def _fake_open(op_obj: Any) -> Any:
        calls['open'] += 1
        return SimpleNamespace(is_success=open_ok)

    def _fake_close(op_obj: Any) -> Any:
        calls['close'] += 1
        return SimpleNamespace(is_success=close_ok)

    def _fake_waves(op_obj: Any, match: Any, hp_value: Any,
                    hp_readable: bool, hp_trusted: bool, *,
                    spend_gate: Any = None) -> tuple[Any, Any]:
        calls['waves'] += 1
        if waves_exc is not None:
            raise waves_exc
        if waves == 'fail':
            return 'FAIL', None
        outcome = SimpleNamespace(
            total_buy=1, total_level=0, total_refresh=1,
            state=SimpleNamespace(gold=gold - 5))
        return None, outcome

    monkeypatch.setattr(
        cw_observation, 'read_game_state',
        lambda *a, **k: SimpleNamespace(gold=gold, hp=hp, hp_readable=True,
                                        hp_trusted=True))
    monkeypatch.setattr(cw_op_open_shop, 'open_shop', _fake_open)
    monkeypatch.setattr(cw_op_close_shop, 'close_shop', _fake_close)
    monkeypatch.setattr(cw_op_buy_cards, 'run_buy_waves', _fake_waves)

    op = SimpleNamespace(
        screenshot=lambda: object(),
        round_by_find_area=_find_area,
        ctx=SimpleNamespace(cw_match=SimpleNamespace(session=sess)),
    )
    return op, sess, calls


_ARB_OP_NAME = '发射帧仲裁商店访问'


def test_arbitration_visit_emits_pair(journal: Path, monkeypatch) -> None:
    """溢出帧受限访问:enter/exit 成对行(outcome='ok')——仲裁访问从
    「无 OpenShop 头的商店段决策行 + 游离 action 行」(复盘误归 0n)变为
    op 行直读可辨(ADR-0584 §5.1)。"""
    op, sess, calls = _arb_op(monkeypatch, gold=80)
    report = cw_loop._launch_frame_arbitration(op)
    assert report['entered'] is True
    assert calls['open'] == 1 and calls['close'] == 1
    rows = _op_rows(journal, _ARB_OP_NAME)
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'ok'


def test_arbitration_non_visit_paths_emit_no_rows(
        journal: Path, monkeypatch) -> None:
    """非访问路径零行(对照臂):预检未过与带内 fail-closed 都不开店,
    不产生商店访问 op 行(行只辖真实访问窗口,零噪声)。"""
    op_skip, _s1, c1 = _arb_op(monkeypatch, prep_hit=False)
    report = cw_loop._launch_frame_arbitration(op_skip)
    assert report['entered'] is False and c1['open'] == 0
    op_inband, _s2, c2 = _arb_op(monkeypatch, gold=40)
    report = cw_loop._launch_frame_arbitration(op_inband)
    assert report['entered'] is False and c2['open'] == 0
    assert _op_rows(journal, _ARB_OP_NAME) == []


def test_arbitration_open_fail_pair(journal: Path, monkeypatch) -> None:
    """开店未生效:仍是一对行,outcome='fail'——行窗口 = 访问尝试边界,
    失败形态可辨(分键 KEY_OPEN_FAILED 之外多一层时间边界)。"""
    op, _sess, _calls = _arb_op(monkeypatch, gold=80, open_ok=False)
    report = cw_loop._launch_frame_arbitration(op)
    assert report['entered'] is False
    rows = _op_rows(journal, _ARB_OP_NAME)
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'fail'
    assert rows[1].get('detail') == 'open_failed'


def test_arbitration_abort_pair(journal: Path, monkeypatch) -> None:
    """访问失败 abort 路径(未识别卡停机钩子等):exit outcome='fail' 且
    detail='abort'——店留着保画面,行面如实记非正常出口。"""
    op, _sess, calls = _arb_op(monkeypatch, gold=80, waves='fail')
    report = cw_loop._launch_frame_arbitration(op)
    assert report.get('abort') is True
    assert calls['close'] == 0
    rows = _op_rows(journal, _ARB_OP_NAME)
    assert rows[1]['outcome'] == 'fail'
    assert rows[1].get('detail') == 'abort'


def test_arbitration_close_fail_marks_fail(journal: Path,
                                           monkeypatch) -> None:
    """关店未生效(交发射核复验裁定的残量路径):outcome='fail'——与 0n
    载体口径一致(关店失败 = 访问非正常出口)。"""
    op, _sess, _calls = _arb_op(monkeypatch, gold=80, close_ok=False)
    report = cw_loop._launch_frame_arbitration(op)
    assert report['entered'] is True
    rows = _op_rows(journal, _ARB_OP_NAME)
    assert rows[1]['outcome'] == 'fail'
    assert rows[1].get('detail') == 'close_failed'


def test_arbitration_exception_closes_row_with_error(
        journal: Path, monkeypatch) -> None:
    """异常注入(run_buy_waves 抛):仲裁按出口契约吞异常不阻塞发射,但
    op exit 行仍以 outcome='error' 闭合——仲裁段自身也是异常安全的行
    生产者(孤儿 enter 不因本补行而新增)。"""
    op, _sess, _calls = _arb_op(
        monkeypatch, gold=80, waves_exc=RuntimeError('仲裁异常注入'))
    report = cw_loop._launch_frame_arbitration(op)   # 契约:吞异常返报告
    assert isinstance(report, dict)
    rows = _op_rows(journal, _ARB_OP_NAME)
    assert [r['event'] for r in rows] == ['enter', 'exit']
    assert rows[1]['outcome'] == 'error'


# ==================== 预清场收编接线(接线烟雾,至多 1 条) ====================


def test_preclear_expert_invite_wired_via_wrapper() -> None:
    """书册卡预清场经包装分发(ADR-0584 §5.3 收编件)。

    接线烟雾(容差档):断言调用点存在,防「同一 op 双通道行缺口」回归
    ——失守事故 = S11 族同型:0k 分支经包装有 op 行、预清场直调
    .execute() 无行,复盘同 op 归属不一致(084421 三窗误标 0n 的近亲)。
    语义 = 预清场段(书册卡清场注释锚 → 备战 dispatch 之间)出现
    _dispatch_screen_op 调用且 journal_name 与 0k 分支同名。
    """
    loop_src = inspect.getsource(cw_loop.CwLoop.loop)
    i_st = loop_src.index('书册卡清场')
    i_end = loop_src.index("journal_name='备战'", i_st)
    seg = loop_src[i_st:i_end]
    assert '_dispatch_screen_op(' in seg, '预清场未走包装(行缺口回归)'
    assert "journal_name='专家邀请函'" in seg, '预清场 op 行须与 0k 同名'
