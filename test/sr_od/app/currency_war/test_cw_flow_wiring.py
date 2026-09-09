"""W971 P3b 段1 接线锁(现役面):环接线守卫族(环入口锚 / 备战链接线)
+ 罕见干扰弹窗分支锚。

设计单一源 = docs/develop/currency_war/prereg/w971_flow_layer/
01-opening.md(开局序列/接管局/位面切换)、06-overlays.md(完成承诺两口径)。
源码结构锁(inspect.getsource):锁「分发接线与退役清单」,不锁分布数值。

2026-09-09 合并批:原 test_cw_loop_wiring_guards.py 按同机制同域并入本文件
(环入口锚半面,原 test_cw_loop_entry_anchor.py;备战链接线半面,原
test_cw_prep_chain_wiring_smoke.py)——两半面同以源码静态守卫锁
CwLoop/CwScreenPrep 的接线在位,防接线静默脱落;备战链接线半面带事故
背书:OperationResult 无 __bool__,裸 not ok 恒 False,r332 停滞守卫曾成
死码(验证局 206 次崩溃-重派无限循环实录),streak 守卫现无行为锁,该
烟雾为接线唯一保底(升级行为锁挂账 = DEBTS.md D77;行为锁本体属新增
测试,见 D77 处置)。dispatch 包装出处 ADR-0584(包装面行为锁 =
test_cw_dispatch_wrapper 主题文件)。

CUT6 瘦身批(2026-09-09):实机每局反复走过的开局编排/overlay 分发/
ctx 信箱退役/简报入口接线锁砍除(接线数周稳定,失守即实机现场炸,
哨兵可闻);保留 = 实机罕见分支(干扰弹窗)与「hp 读互斥」决策输入
前置(收起探针)——保留核清单 = reports/_cluster_CUT6.md。
"""

import inspect

from sr_od.application.currency_war.operations import cw_loop
from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_prep,
)


def _loop_src() -> str:
    return inspect.getsource(cw_loop.CwLoop)


# ==================== overlay 分发接管(06-overlays §4) ====================


def test_interference_popup_branches_retained() -> None:
    """干扰弹窗分支保留(06-overlays §4:死循环修复史分支不退役)。

    只留矩阵未辖的两锚(概率表/简易装备);其余四锚(祈愿试炼/专家邀请函/
    未达上限警告/位面详情标题)的「判定调用位在场+先于备战双锚」已由
    test_cw_dispatch_order_matrix.py 序锁矩阵同名行以更强形态锁定
    (调用位+序位,分支被删/被挪后置均红),裸串在场是其弱化重复
    (2026-09-08 瘦身批删除)。"""
    src = _loop_src()
    for anchor in ('标识-刷新概率表',  # 0e2 概率表
                   '标识-简易装备',      # 0g 阿哈装备选择
                   ):
        assert anchor in src, f'干扰/兜底分支锚 {anchor} 消失(静默丢弃退避停机风险)'


# ==================== 环接线守卫(承 test_cw_loop_wiring_guards) ====================


def test_loop_entry_anchor_is_stage_only() -> None:
    """环入口锚(P0①→r347→W971 P3b 拆内环返工定稿):旧「按钮-出战」
    双态区分锚退役;环入口消化语义 = 外循环每轮重识别 + 单轮 op 清场/
    开店收起探针(gate 时间稳定窗随内环拆除)。锁:旧锚不得回流 + 收起
    探针在。(原 test_cw_loop_entry_anchor.py 半面,2026-09-03 拆分归档批
    自 test_cw_legacy_audit.py 按 member 拆回,纯移动零改动;本文件级
    合并亦零断言改动。)"""
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
    回调内联于 loop 源。事故背书与升级行为锁挂账见文件头(D77)。
    """
    src = _loop_src()
    assert 'CwScreenPrep(self.ctx)' in src   # 备战分支经包装委托(备战单轮)
    assert '_director_fail_streak' in src
    # (_dispatch_screen_op 在场断言已删:该面全仓 6 处在锁——主题文件
    #  test_cw_dispatch_wrapper 行为锁 + battle_wait_op/decision_frame_hooks/
    #  op_boundary/telemetry_collect 各自段落,本处零增量判别力。)
