"""CW 全 op 模块可导入烟雾锁。

背景(2026-08-25 实锤):handle_planner_event.py 曾用 ``node_name=`` 传参而框架
``operation_node`` 签名是 ``name=`` —— import 期即 TypeError。因 battle_loop 对
该 handler 是惰性 import,常规测试与全量 pytest 都不触发,地雷存活 6 天,
直到 MCP server ``list_operations`` 扫描注册表才暴露;期间任何撞上银狼
「我来当策划」overlay 的实机局都会 ImportError → 节点重试耗尽 → 对局失败。

本锁=r98「改后必真调用一次」纪律的代码化:walk 全部 CW operations 模块,
逐个 import,任何签名/语法级错误在此立即红。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import importlib
import pkgutil

import pytest

import sr_od.application.currency_war.operations as cw_ops_pkg


def _iter_cw_op_modules() -> list[str]:
    """枚举 CW operations 包下全部模块(递归)。"""
    names: list[str] = []
    for info in pkgutil.walk_packages(cw_ops_pkg.__path__, prefix=cw_ops_pkg.__name__ + '.'):
        names.append(info.name)
    return sorted(names)


@pytest.mark.parametrize('module_name', _iter_cw_op_modules())
def test_cw_op_module_importable(module_name: str) -> None:
    """每个 CW operations 子模块必须可导入(kwarg/语法/顶层符号错误在此暴露)。"""
    importlib.import_module(module_name)
