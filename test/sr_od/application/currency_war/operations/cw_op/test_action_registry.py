"""动作注册表完备性机械约束测试。

锁的设计约定(注册表单一源 = cw_action_registry,词表外类型 = AssertionError):
统一词表 ``CW_ACTION_TYPES`` 与事件线 pick 族 ``PICK_ACTION_TYPES`` 逐类
断言类级解析可命中——漏登记 = 执行面拒「动作词表外类型」,动作从未真正
执行(登记是入口门;CwActionOpenTomeParam 曾漏登记数百次拒绝被误读为
执行失败的教训)。
"""

from sr_od.application.currency_war.kernel.cw_vocab import (
    CW_ACTION_TYPES,
    PICK_ACTION_TYPES,
    CwActionRefreshInvestCardsParam,
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshSupplyParam,
)
from sr_od.application.currency_war.operations.cw_op.cw_action_registry import (
    action_op_class_for_type,
)

#: 三刷新建议动作不经注册表(分屏形态各异,刷新链由画面 op 内置动作
#: 承载,action-op.md §2;词表在场但注册表解析不辖)。
_NOT_IN_REGISTRY: tuple[type, ...] = (
    CwActionRefreshNodeOptionsParam,
    CwActionRefreshSupplyParam,
    CwActionRefreshInvestCardsParam,
)


def test_registry_resolves_all_vocab_types() -> None:
    """统一词表全量可解析(刷新三动作豁免;行序 isinstance 首中语义的
    类级同构)。"""
    for action_type in CW_ACTION_TYPES:
        if action_type in _NOT_IN_REGISTRY:
            continue
        op_cls = action_op_class_for_type(action_type)
        assert op_cls is not None and callable(op_cls)


def test_registry_resolves_all_pick_types() -> None:
    """事件线 pick 族全量可解析。"""
    for action_type in PICK_ACTION_TYPES:
        op_cls = action_op_class_for_type(action_type)
        assert op_cls is not None and callable(op_cls)
