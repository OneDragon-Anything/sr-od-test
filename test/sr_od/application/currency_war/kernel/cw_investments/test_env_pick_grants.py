"""ENV_PICK_GRANTS 取卡触发发放注册表构建校验测试(镜像 src =
kernel/cw_investments.py 的该注册表与 `_validate_env_pick_grants`;按拆目录
规范落位本目录,先例 = 同目录 test_env_bond_tier_grants.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 1(§2.1(a) 落地形态):
- 双源同值:同键在 ENV_ECONOMY 有非空 gold_per_strategy_coef → 相等,
  篡改任一侧 import 炸(估值面与世界面同出卡面 id 147,单侧改系数即失
  同步,构建期响);
- 值形:正 int 禁 bool(0/负/True/False 形混入 = 登记笔误);
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
    """登记在册 + 双源现值同值(T-46 设计 §2.1(a)):首例策略大师 coef 2
    (id 147 原文直读「2*已拥有投资策略数」),与 ENV_ECONOMY.
    gold_per_strategy_coef 同值;现表直调校验零炸。"""
    assert ENV_PICK_GRANTS == {'策略大师': 2}, '首例登记(id 147)'
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == \
        ENV_PICK_GRANTS['策略大师'], '双源现值同值(同出卡面)'
    cw_investments._validate_env_pick_grants()


@pytest.mark.parametrize('tampered_side', ['world', 'estimate'])
def test_pick_grants_dual_source_tamper_import_bomb(
        monkeypatch: pytest.MonkeyPatch, tampered_side: str) -> None:
    """双源同值闸(T-46 设计 §4 锁 1,import 即炸语义):任一侧单独改
    系数 → 校验炸(世界面与估值面失同步即构建期响)。"""
    if tampered_side == 'world':
        bad = dict(ENV_PICK_GRANTS)
        bad['策略大师'] = 3
        monkeypatch.setattr(cw_investments, 'ENV_PICK_GRANTS', bad)
    else:
        from dataclasses import replace
        _orig = ENV_ECONOMY['策略大师']
        monkeypatch.setattr(cw_investments, 'ENV_ECONOMY',
                            dict(ENV_ECONOMY
                                 | {'策略大师': replace(_orig,
                                                       gold_per_strategy_coef=3)}))
    with pytest.raises(ValueError, match='双源失同步'):
        cw_investments._validate_env_pick_grants()


@pytest.mark.parametrize('bad_coef', [0, -2, True, False])
def test_pick_grants_value_form_gate(
        monkeypatch: pytest.MonkeyPatch, bad_coef: int) -> None:
    """值形闸(T-46 设计 §4 锁 1):0/负(条件永真或倒扣)与 bool 形
    (isinstance(True, int) 为真,禁混入)→ 校验炸。"""
    bad = dict(ENV_PICK_GRANTS)
    bad['策略大师'] = bad_coef
    monkeypatch.setattr(cw_investments, 'ENV_PICK_GRANTS', bad)
    with pytest.raises(ValueError, match='值形'):
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
