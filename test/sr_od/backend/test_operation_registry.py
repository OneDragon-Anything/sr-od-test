"""operation_registry 注解解析单元测试。

锁的设计约定(真实故障形态 2026-11-04/2026-11-07 两起):
- ``from __future__ import annotations`` 下 ``inspect.signature`` 拿到字符串注解,
  字符串裸名匹配认不得 ``list[str]`` 泛型写法 → 必须按定义模块命名空间求值还原;
- 求值必须**逐参数**:单个参数注解引用仅 TYPE_CHECKING 导入的前向引用名(如
  ``ctx: SrContext``)时,只该参数回退字符串注解,其余参数(list/dict 泛型)仍求值
  成功、可被 run_operation 接受——整体求值(get_type_hints)一败俱败,会拒收合法参数。
"""
from typing import TYPE_CHECKING

from one_dragon.base.operation.operation import Operation
from sr_od.backend.operation_registry import (
    _annotation_json_serializable,
    _resolve_annotations,
    validate_args,
)

if TYPE_CHECKING:
    from sr_od.context.sr_context import SrContext


class _OpWithForwardRef(Operation):
    """__init__ 注解含仅 TYPE_CHECKING 可见的前向引用名(复现真实故障形态)。

    ctx 注解同样引用前向引用名,但 ctx 被 _resolve_annotations 设计性剔除,
    另设 ``helper`` 参数在前向引用位置锁「单参数回退不拖垮其余参数」。
    测试只做反射、不实例化,``__init__`` 体不执行。"""

    def __init__(self, ctx: 'SrContext', team_names: list[str],
                 helper: 'SrContext' = None):
        super().__init__(ctx, op_name='fake')


def test_forward_ref_only_falls_back_self_param() -> None:
    """前向引用参数回退字符串,泛型参数仍求值为真实类型。"""
    hints = _resolve_annotations(_OpWithForwardRef)
    # SrContext 仅 TYPE_CHECKING 导入,运行时命名空间不可求值 → 该参数回退字符串
    assert hints['helper'] == 'SrContext'
    # list[str] 求值成功(不因同签名内其他前向引用失败而整体回退)
    assert str(hints['team_names']) == 'list[str]'


def test_generic_list_param_json_serializable() -> None:
    """泛型列表参数判定为 JSON 可序列化(run_operation 可传 list[str])。"""
    hints = _resolve_annotations(_OpWithForwardRef)
    assert _annotation_json_serializable(hints['team_names']) is True


def test_validate_args_accepts_list_value() -> None:
    """list 值通过校验(故障形态:曾被误判为不支持的数据类型)。"""
    err = validate_args(_OpWithForwardRef, {'team_names': ['黑天鹅', '卡芙卡']})
    assert err is None


def test_validate_args_rejects_missing_required() -> None:
    """缺必填参数报错误描述。"""
    err = validate_args(_OpWithForwardRef, {})
    assert err is not None
    assert 'team_names' in err
