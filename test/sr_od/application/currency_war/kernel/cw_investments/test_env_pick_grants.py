"""ENV_PICK_GRANTS 取卡触发发放注册表构建校验测试(镜像 src =
kernel/cw_investments.py 的该注册表与 `_validate_env_pick_grants`;按拆目录
规范落位本目录,先例 = 同目录 test_env_bond_tier_grants.py)。

测试面依据 = 原稿锁面
原稿锁面§4 锁 1(§2.1(a) 落地形态;2026-10-28 治理后
只留漂移哨,双源同值/值形闸随删,现值同值断言保留作登记数据性质):
- 已登记 + 与 ENV_ECONOMY 系数现值同值(同出卡面,数据性质非快照);
- 孤儿键:键必须在 INVESTMENT_ENVS。
注入 + 直调沿本目录惯用法(monkeypatch.setattr 替表后直调校验器)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    ENV_PICK_GRANTS,
)


def test_pick_grants_registered_and_coefs_synced() -> None:
    """已登记 + 双源现值同值(T-46 设计 §2.1(a)):首例策略大师 coef 2
    (id 147 原文直读「2*已拥有投资策略数」),与 ENV_ECONOMY.
    gold_per_strategy_coef 同值;现表直调校验零炸。"""
    assert ENV_PICK_GRANTS == {'策略大师': 2}, '首例登记(id 147)'
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == \
        ENV_PICK_GRANTS['策略大师'], '双源现值同值(同出卡面)'
    cw_investments._validate_env_pick_grants()


def test_pick_grants_orphan_key_gate(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """孤儿键闸(家族先例同款):键不在 INVESTMENT_ENVS(版本更新改名/
    移除后静默失联)→ 校验炸。"""
    bad = dict(ENV_PICK_GRANTS)
    bad['不存在环境X'] = 2
    monkeypatch.setattr(cw_investments, 'ENV_PICK_GRANTS', bad)
    with pytest.raises(ValueError, match='ENV_PICK_GRANTS 孤儿键'):
        cw_investments._validate_env_pick_grants()
