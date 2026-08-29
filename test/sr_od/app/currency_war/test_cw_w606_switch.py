"""W606 批③·开关默认态与读取锁(设计 §2;策略开关生命周期门)。

锁面:
1. registry 两开关默认 False(零漂移锚:默认态旧环逐位不动、影子不跑);
2. 读取 helper:default 栈(无 registry)退 DEFAULT_REGISTRY=关;
   DecisionV2Strategy 载 registry 实例按字段取值(A/B 合法载体);
3. 分叉点行为:开关关时 prep_director 主循环不进入 v2 路径(旧环主体
   零改动由既有全量回归背书;本锁钉开关默认值与 helper 纯度)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.decision_v2.adapter import (
    director_v2_enabled,
    shadow_compare_enabled,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
    DecisionV2Registry,
)


def test_switches_default_off():
    assert DEFAULT_REGISTRY.director_v2_prep_enabled is False
    assert DEFAULT_REGISTRY.director_v2_shadow_compare is False


def test_default_stack_without_registry_reads_off():
    class _PlainDefaultStrategy:   # default 栈:无 .registry 属性
        pass

    assert director_v2_enabled(_PlainDefaultStrategy()) is False
    assert shadow_compare_enabled(_PlainDefaultStrategy()) is False


def test_registry_injection_carries_ab_arms():
    on = DecisionV2Registry(director_v2_prep_enabled=True)
    shadow_on = DecisionV2Registry(director_v2_shadow_compare=True)
    off = DecisionV2Registry()
    strat_on = SimpleNamespace(registry=on)
    strat_shadow = SimpleNamespace(registry=shadow_on)
    strat_off = SimpleNamespace(registry=off)
    assert director_v2_enabled(strat_on) is True
    assert director_v2_enabled(strat_shadow) is False   # 两开关独立
    assert shadow_compare_enabled(strat_shadow) is True
    assert shadow_compare_enabled(strat_on) is False
    assert director_v2_enabled(strat_off) is False


def test_frozen_registry_supports_field_addition_without_breaking_existing():
    """新增字段带缺省值:既有注入点(dataclasses.replace/关键字构造)不受扰。"""
    base = DecisionV2Registry(interest_floor=30)
    assert base.interest_floor == 30
    assert base.director_v2_prep_enabled is False
