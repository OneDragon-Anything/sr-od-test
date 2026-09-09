"""CwLoop 备战链接线烟雾(streak 停滞守卫 + 备战委托;弱锁保底)。

事故背书:生产 cw_loop.py 备战环 on_result 注释——OperationResult 无 __bool__,
裸 not ok 恒 False,r332 停滞守卫曾成死码(验证局 206 次崩溃-重派无限循环实录);
streak 守卫现无行为锁,本烟雾为接线唯一保底(升级行为锁挂账待办)。
dispatch 包装出处 ADR-0584(包装面行为锁 = test_cw_dispatch_wrapper 主题文件)。"""
from __future__ import annotations


def test_source_has_real_wiring() -> None:
    """备战链接线存在(streak 守卫 + 备战分支委托 CwScreenPrep)。

    ADR-0584 改写:备战单轮经 dispatch 包装分发(原字面直调随包装上收),
    接线语义不变——备战分支委托 CwScreenPrep + streak 守卫在 on_result
    回调内联于 loop 源。
    """
    import inspect

    from sr_od.application.currency_war.operations import cw_loop
    src = inspect.getsource(cw_loop.CwLoop)
    assert 'CwScreenPrep(self.ctx)' in src   # 备战分支经包装委托(备战单轮)
    assert '_director_fail_streak' in src
    # (_dispatch_screen_op 在场断言已删:该面全仓 6 处在锁——主题文件
    #  test_cw_dispatch_wrapper 行为锁 + battle_wait_op/decision_frame_hooks/
    #  op_boundary/telemetry_collect 各自段落,本处零增量判别力。)
