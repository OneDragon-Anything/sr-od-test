"""test_cw_loop_wiring_guards 主题锁——环接线守卫族(inspect.getsource 源码静态守卫)。

2026-09-09 合并批:原 test_cw_loop_entry_anchor.py(环入口锚半面)+
test_cw_prep_chain_wiring_smoke.py(CwLoop 备战链接线半面)按同机制同域归并
——两者都以源码静态守卫锁 CwLoop/CwScreenPrep 的接线在位,防接线静默脱落。

**环入口锚半面**(原 test_cw_loop_entry_anchor.py;2026-09-03 拆分归档批自混合文件
test_cw_legacy_audit.py 按 member 拆回独立文件,纯移动断言零改动):P0①→r347→
W971 P3b 拆内环(返工定稿)——旧「按钮-出战」双态区分锚退役;环入口消化语义 =
外循环每轮重识别 + 单轮 op 清场/开店收起探针(gate 时间稳定窗随内环拆除)。

**备战链接线半面**(原 test_cw_prep_chain_wiring_smoke.py;弱锁保底):事故背书:
生产 cw_loop.py 备战环 on_result 注释——OperationResult 无 __bool__,裸 not ok 恒
False,r332 停滞守卫曾成死码(验证局 206 次崩溃-重派无限循环实录);streak 守卫
现无行为锁,本烟雾为接线唯一保底(升级行为锁挂账 = DEBTS.md D77)。dispatch 包装
出处 ADR-0584(包装面行为锁 = test_cw_dispatch_wrapper 主题文件)。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep


def test_loop_entry_anchor_is_stage_only() -> None:
    """P0①→r347→W971 P3b 拆内环(返工定稿):旧「按钮-出战」双态区分锚
    退役;环入口消化语义 = 外循环每轮重识别 + 单轮 op 清场/开店收起探针
    (gate 时间稳定窗随内环拆除)。锁:旧锚不得回流 + 收起探针在。"""
    src = inspect.getsource(cw_screen_prep.CwScreenPrep.run)
    assert "'按钮-出战'" not in src, \
        '旧 3 探针锚已删(r347),不得回流单轮入口'
    assert '_try_collapse_open_shop()' in src, \
        '单轮入口必须探开商店合法态并收起(读互斥:hp 关态可读)'
    assert 'wait_stable_frame' not in src, \
        'gate 时间稳定窗已随内环拆除(W971 P3b 返工定稿),不得回流'
    assert '_bail(' not in src and 'bail_reason_counts' not in src, (
        '内环 bail/同因计数机制不得回流(拆内环定稿;'
        '原 test_no_fallthrough_blind_observe 墓碑句,2026-09-03 瘦身批并入)')


def test_source_has_real_wiring() -> None:
    """备战链接线存在(streak 守卫 + 备战分支委托 CwScreenPrep)。

    ADR-0584 改写:备战单轮经 dispatch 包装分发(原字面直调随包装上收),
    接线语义不变——备战分支委托 CwScreenPrep + streak 守卫在 on_result
    回调内联于 loop 源。
    """
    src = inspect.getsource(cw_loop.CwLoop)
    assert 'CwScreenPrep(self.ctx)' in src   # 备战分支经包装委托(备战单轮)
    assert '_director_fail_streak' in src
    # (_dispatch_screen_op 在场断言已删:该面全仓 6 处在锁——主题文件
    #  test_cw_dispatch_wrapper 行为锁 + battle_wait_op/decision_frame_hooks/
    #  op_boundary/telemetry_collect 各自段落,本处零增量判别力。)
