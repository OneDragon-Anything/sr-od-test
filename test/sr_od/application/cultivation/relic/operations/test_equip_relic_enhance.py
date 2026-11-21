"""EquipRelicEnhanceOp(遗器强化)构造守卫与 MCP registry 注解测试。

锁的内容(出处 src/sr_od/operations/equip_relic_enhance.py):
- 构造守卫:auto_insert 非法值抛 ValueError 且列出全部合法值;target_level
  越界显式失败;
- MCP run_operation 路径:auto_insert 注解为 ``str``(非 Literal)→ registry
  判 JSON 可序列化、validate_args 接受 'plus3'/'off'/'max' 传值 —— Literal
  注解会被 operation_registry 判 false 导致该参数经 MCP 整体被拒(设计约定:
  合法值校验归 op 构造期,registry 只做类型形态校验)。
"""

from __future__ import annotations

import pytest

from sr_od.backend.operation_registry import (
    _annotation_json_serializable,
    _resolve_annotations,
    validate_args,
)
from sr_od.application.cultivation.relic.operations.equip_relic_enhance import EquipRelicEnhanceOp
from test.conftest import SrTestContext


def test_construction_guard(test_context: SrTestContext) -> None:
    """非法 auto_insert 抛 ValueError 并列出合法值;target_level 越界显式失败。"""
    with pytest.raises(ValueError, match='off/plus3/max'):
        EquipRelicEnhanceOp(test_context, auto_insert='nope')
    with pytest.raises(ValueError, match='1-15'):
        EquipRelicEnhanceOp(test_context, target_level=16)


def test_registry_accepts_auto_insert_via_mcp_args() -> None:
    """MCP 路径:注解 str → JSON 可序列化;plus3/off/max 经 validate_args 放行
    (非法值归 op 构造期拦截,registry 只校验类型形态)。"""
    hints = _resolve_annotations(EquipRelicEnhanceOp)
    assert hints['auto_insert'] is str, \
        f'注解应保持 str(Literal 会被 registry 判不可序列化):{hints["auto_insert"]!r}'
    assert _annotation_json_serializable(hints['auto_insert']) is True
    for legal in ('off', 'plus3', 'max'):
        assert validate_args(EquipRelicEnhanceOp, {'auto_insert': legal}) is None, \
            f'合法档位 {legal} 应通过 registry 校验'
