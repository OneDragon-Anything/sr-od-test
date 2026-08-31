"""r112:record_decision 便捷函数 extra 参数回归(局30 整局报废的根因)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.telemetry import recorder as t
from sr_od.application.currency_war.kernel.cw_state import GameState


def test_record_decision_accepts_extra():
    """shop.py 的调用形态(带 extra=sess_*)不再 TypeError。

    局30 实证:r101 加 session 快照时 shop.py 传 extra=,但模块级便捷函数
    签名没有该参数 → 买牌 op 每轮 TypeError → 金 3→110 全程闲置,整局报废。
    """
    st = GameState(gold=5)
    t.record_decision(st, 'x', {}, {}, [],
                      extra={'sess_framework': '仙舟', 'sess_dual_track': True})
    # 不 start_run → early return,不落盘;到这里 = 签名对齐,不再 TypeError


def test_recorder_method_and_helper_signatures_align():
    """便捷函数签名 ⊇ recorder 方法签名(防再漂移)。"""
    import inspect

    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    helper_params = set(inspect.signature(t.record_decision).parameters)
    method_params = set(inspect.signature(
        TelemetryRecorder.record_decision).parameters) - {'self', 'run_id', 'difficulty'}
    missing = method_params - helper_params
    assert not missing, f'便捷函数缺参数 {missing}——与方法签名对齐防再犯'
