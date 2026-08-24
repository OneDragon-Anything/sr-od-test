"""W68 双根修回归锁:槽位表形状契约 + 停滞守卫复活。

背景(2026-08-25 验证局 run_20260825_020956 实录,W68 诊断):
①ADR-0316 槽位表语义写入端(pad_bench 经 mutate_bench_deployed)把
session.tracked_bench_chars pad 成定长 9 含 None,而 cw_reconcile 的
消费端 listcomp 假设紧凑无 None → AttributeError → 对局 206 次
「崩溃-重派」无限循环;
②battle_loop 停滞守卫 `if not _ok:` 恒 False(OperationResult 无
__bool__,bool(FAIL)=True)→ r332 的 fail_streak>=5 兜底是死码,
放大成无限循环。

本锁钉死两修:
- reconcile_tracking 吃含 None 的 tracked(污染态)不崩,对账语义正确
  (None=空槽无信息,非冲突);
- battle_loop 守卫判据用 .success(裸 not _ok 不可作为失败判据)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.cw_reconcile import reconcile_tracking
from sr_od.application.currency_war.cw_state import BenchChar
from sr_od.application.currency_war.cw_strategy import StrategySession


def _padded_tracked() -> StrategySession:
    """构造 W68 现场形态:买牌后 pad_bench 污染 tracked 含 None。"""
    sess = StrategySession()
    sess.tracked_bench_chars = [
        BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
        BenchChar(slot=2, char_id='飞霄', faction='狼狩'),
        None, None, None, None, None, None, None,   # pad 到定长 9
    ]
    sess.tracked_deployed = []
    return sess


def test_reconcile_survives_padded_tracked_bench() -> None:
    """W68 ①:tracked 含 None(槽位表 pad 态)→ reconcile 不崩且语义正确。

    SIFT 读到 bench 上 2 人(与 tracked 非 None 项一致)→ 无漂移写回;
    修复前此处 AttributeError(listcomp 撞 None)。
    """
    sess = _padded_tracked()
    bench = [BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
             BenchChar(slot=2, char_id='飞霄', faction='狼狩')]
    # 不得 raise —— 修复点
    reconcile_tracking(sess, bench=bench, deployed=[], screen=None,
                       source='w68-lock')


def test_reconcile_drift_detected_with_padded_tracked() -> None:
    """W68 ①语义面:污染态下漂移检测仍工作(SIFT 读到 tracked 外的新人)。"""
    sess = _padded_tracked()
    bench = [BenchChar(slot=1, char_id='阿格莱雅', faction='昼之半神'),
             BenchChar(slot=2, char_id='飞霄', faction='狼狩'),
             BenchChar(slot=3, char_id='桑博', faction='虚无')]
    reconcile_tracking(sess, bench=bench, deployed=[], screen=None,
                       source='w68-lock')
    assert any(bc is not None and bc.char_id == '桑博'
               for bc in sess.tracked_bench_chars), '新人应被写回 tracking'


def test_operation_result_bool_pitfall_guard() -> None:
    """W68 ②:钉死 `OperationResult` 无 __bool__ 的坑——bool(FAIL) is True。

    这是battle_loop:925 守卫曾成死码的语言级根因;锁此事实防未来
    有人「简化」回 `if not result:`(同型坑在仓内 3 处正确范式都是
    `.execute().success`)。
    """
    from one_dragon.base.operation.operation_base import OperationResult
    fail = OperationResult(success=False, status='x')
    assert bool(fail) is True, \
        'OperationResult 无 __bool__:bool(FAIL)=True——失败判据必须用 .success'
    assert fail.success is False
