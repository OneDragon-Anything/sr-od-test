# -*- coding: utf-8 -*-
"""T-185 spy 锁:引擎动作应用必经单一转移函数(运行时行为断言,非源码扫描)。

monkeypatch 包装 kernel 转移函数计数,跑最小 seed 局,断言:
①引擎动作路径调用转移函数 ≥1(写面反转的单一源纪律);
②返回 LogicOutcome(出参通道存在;详设 sim-state-switch §3 转移结果通道)。
"""
from __future__ import annotations

import logging

import pytest

import sr_od.application.currency_war.sim.engine_p1 as engine_p1


@pytest.mark.filterwarnings('ignore')
def test_cw_engine_actions_route_through_transfer(monkeypatch) -> None:
    logging.disable(logging.CRITICAL)
    calls: list[str] = []
    orig = engine_p1.apply_shop_action_logic

    def spy(bs, action, **kwargs):
        out = orig(bs, action, **kwargs)
        calls.append(type(action).__name__)
        assert type(out).__name__ == 'LogicOutcome'
        return out

    monkeypatch.setattr(engine_p1, 'apply_shop_action_logic', spy)
    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
    r = simulate_p1(0, pool='snapshot', planes=1)
    assert calls, '引擎动作未经单一转移函数(写面反转纪律破)'
    assert r.final_hp is not None

