"""operation_registry 注解解析单元测试。

锁的设计约定(真实故障形态 2026-11-04/2026-11-07 两起):
- ``from __future__ import annotations`` 下 ``inspect.signature`` 拿到字符串注解,
  字符串裸名匹配认不得 ``list[str]`` 泛型写法 → 必须按定义模块命名空间求值还原;
- 求值必须**逐参数**:单个参数注解引用仅 TYPE_CHECKING 导入的前向引用名(如
  ``ctx: SrContext``)时,只该参数回退字符串注解,其余参数(list/dict 泛型)仍求值
  成功、可被 run_operation 接受——整体求值(get_type_hints)一败俱败,会拒收合法参数。
"""
import sys
import types
from typing import TYPE_CHECKING

import pytest

from one_dragon.base.operation.operation import Operation
from sr_od.backend import operation_registry
from sr_od.backend.operation_registry import (
    _annotation_json_serializable,
    _resolve_annotations,
    compact_operation_list,
    describe_operation,
    match_short_name,
    resolve_unique_op,
    validate_args,
)
from sr_od.backend.schemas import OperationInfo, OperationListResult

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


# ===== 短名匹配(describe/run 支持「只传类名」,短名多命中分流)=====

_REAL_UNIQUE = 'GetRidOfStuck'
_REAL_FULL = 'sr_od.operations.move.get_rid_of_stuck.GetRidOfStuck'
# 同名假类的两个承载模块(动态注册进 sys.modules,收尾必须移除——进程级全局)
_FAKE_MODS = ('test_registry_fake_pkg.a', 'test_registry_fake_pkg.b')
_AMBIGUOUS_NAME = 'FakeAmbiguousRegistryOp'


def _install_ambiguous_scan(monkeypatch) -> list[str]:
    """注册同名假类到两个假模块并 patch 扫描结果,返回两个假 op_id。

    resolve_op_class 经 importlib 解析,假模块须注册进 sys.modules;
    调用方必须在 finally 里移除(进程级全局,泄漏会污染其他测试)。
    """
    operations = []
    for mod_name in _FAKE_MODS:
        mod = types.ModuleType(mod_name)
        cls = type(_AMBIGUOUS_NAME, (Operation,), {'__module__': mod_name})
        setattr(mod, _AMBIGUOUS_NAME, cls)
        sys.modules[mod_name] = mod
        operations.append(OperationInfo(
            op_id=f'{mod_name}.{_AMBIGUOUS_NAME}',
            class_name=_AMBIGUOUS_NAME,
            module=mod_name,
        ))
    fake = OperationListResult(operations=operations, failures=[])
    monkeypatch.setattr(
        operation_registry, 'scan_operations',
        lambda _ctx, refresh=False: fake)
    return [o.op_id for o in operations]


def test_match_short_name_returns_none_for_op_id() -> None:
    """含 ``.`` 是完整 op_id 形态 → None(调用方走实时解析路径)。"""
    assert match_short_name(_REAL_FULL) is None


def test_match_short_name_unique_hit() -> None:
    """真实项目类名唯一 → 短名命中 1 条。"""
    hits = match_short_name(_REAL_UNIQUE)
    assert len(hits) == 1
    assert hits[0].op_id == _REAL_FULL


def test_match_short_name_no_hit_returns_empty() -> None:
    """短名形态无命中 → 空列表(与 None 的「非短名形态」语义区分)。"""
    assert match_short_name('NoSuchOpXyz') == []


def test_resolve_unique_op_accepts_short_name() -> None:
    """短名唯一命中 → 解析出真类。"""
    from sr_od.operations.move.get_rid_of_stuck import GetRidOfStuck

    assert resolve_unique_op(_REAL_UNIQUE) is GetRidOfStuck


def test_resolve_unique_op_rejects_ambiguous(monkeypatch) -> None:
    """短名多命中 → ValueError 列出全部候选 op_id(防误运行)。"""
    fake_ids = _install_ambiguous_scan(monkeypatch)
    try:
        with pytest.raises(ValueError) as exc_info:
            resolve_unique_op(_AMBIGUOUS_NAME)
        for fake_id in fake_ids:
            assert fake_id in str(exc_info.value)
    finally:
        for mod_name in _FAKE_MODS:
            sys.modules.pop(mod_name, None)


def test_resolve_unique_op_not_found_suggests_similar() -> None:
    """短名未找到 → 报错附 difflib 相似类名建议。"""
    with pytest.raises(ValueError) as exc_info:
        resolve_unique_op('GetRidOfStuckkk')
    assert '未找到' in str(exc_info.value)
    assert _REAL_UNIQUE in str(exc_info.value)


def test_describe_operation_short_name_returns_full_op_id() -> None:
    """短名 describe → 返回单条 schema 且 op_id 回填完整形态。"""
    info = describe_operation(None, _REAL_UNIQUE)
    assert info['op_id'] == _REAL_FULL
    assert info['class_name'] == _REAL_UNIQUE


def test_describe_operation_ambiguous_returns_all_matches(monkeypatch) -> None:
    """短名多命中 → {ambiguous, count, matches[]} 全部候选。"""
    fake_ids = _install_ambiguous_scan(monkeypatch)
    try:
        info = describe_operation(None, _AMBIGUOUS_NAME)
    finally:
        for mod_name in _FAKE_MODS:
            sys.modules.pop(mod_name, None)
    assert info['ambiguous'] is True
    assert info['count'] == 2
    assert sorted(m['op_id'] for m in info['matches']) == sorted(fake_ids)


# ===== compact_operation_list(list 返回元素:无冲突短名 / 冲突完整 op_id)=====

def test_compact_operation_list_short_names_and_conflict() -> None:
    """无同名类 → 元素为类名短名;同名冲突类 → 保留完整 op_id。"""
    result = OperationListResult(operations=[
        OperationInfo(op_id='pkg.a.UniqueA', class_name='UniqueA', module='pkg.a'),
        OperationInfo(op_id='pkg.b.Dup', class_name='Dup', module='pkg.b'),
        OperationInfo(op_id='pkg.c.Dup', class_name='Dup', module='pkg.c'),
    ], failures=[])
    payload = compact_operation_list(result)
    assert payload['operations'] == ['UniqueA', 'pkg.b.Dup', 'pkg.c.Dup']
    assert payload['total'] == payload['count'] == 3


def test_compact_operation_list_query_filters_by_op_id() -> None:
    """query 按完整 op_id 匹配(模块路径词可用);命中冲突类返回完整 op_id。"""
    result = OperationListResult(operations=[
        OperationInfo(op_id='pkg.a.UniqueA', class_name='UniqueA', module='pkg.a'),
        OperationInfo(op_id='pkg.b.Dup', class_name='Dup', module='pkg.b'),
        OperationInfo(op_id='pkg.c.Dup', class_name='Dup', module='pkg.c'),
    ], failures=[])
    filtered = compact_operation_list(result, 'pkg.c')
    assert filtered['operations'] == ['pkg.c.Dup']
    assert filtered['total'] == 3
    assert filtered['count'] == 1
