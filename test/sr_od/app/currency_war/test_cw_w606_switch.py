"""W620 批 1·DirectorV2 接线升正锁(蓝图 §7 批 1 行 + §8 无开关 directive)。

锁面:
1. 无开关:``director_v2_prep_enabled`` 已从 registry 删除(接线完成 =
   存在理由消失;回退 = git revert,不留字段);
2. adapter 不再暴露 ``director_v2_enabled`` 读取 helper;
3. 影子比对开关(纯诊断)默认关、可注入,与生产行为零耦合;
4. prep_director 环入口无条件走新环(源码锁:分叉点无条件 return)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.decision_v2.adapter import (
    shadow_compare_enabled,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)

_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')


def test_switch_field_deleted_from_registry():
    """无开关 directive:开臂开关物理消失(语义升格 = 新环唯一路径)。"""
    assert not hasattr(DEFAULT_REGISTRY, 'director_v2_prep_enabled')
    import dataclasses
    names = {f.name for f in dataclasses.fields(DecisionV2Registry)}
    assert 'director_v2_prep_enabled' not in names


def test_adapter_no_longer_exports_enablement_helper():
    import sr_od.application.currency_war.decision_v2.adapter as adapter
    assert not hasattr(adapter, 'director_v2_enabled')


def test_shadow_compare_diagnostic_default_off_and_injectable():
    class _PlainDefaultStrategy:   # default 栈:无 .registry 属性
        pass

    assert shadow_compare_enabled(_PlainDefaultStrategy()) is False
    strat = SimpleNamespace(registry=DecisionV2Registry(
        director_v2_shadow_compare=True))
    assert shadow_compare_enabled(strat) is True


def test_prep_director_fork_is_unconditional_v2():
    """环入口升正源码锁:分叉点无条件 return _run_prep_loop_v2。"""
    src = (_SRC / 'prep_director.py').read_text(encoding='utf-8')
    assert 'return self._run_prep_loop_v2(match, session, config)' in src
    assert 'director_v2_enabled' not in src


def test_frozen_registry_supports_field_addition_without_breaking_existing():
    """新增字段带缺省值:既有注入点(dataclasses.replace/关键字构造)不受扰。"""
    base = DecisionV2Registry(interest_floor_override=30)
    assert base.interest_floor() == 30
    assert base.director_v2_shadow_compare is False
