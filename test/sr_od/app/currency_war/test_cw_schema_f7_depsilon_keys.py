# -*- coding: utf-8 -*-
"""F7/D_ε 判读面观察键 schema 锁(判前锁 v6 挂账行 7/11/13 的最小锁)。

- 规格 = IMPL_DESIGN §5.1 行 7/11/13 原文 + design_telemetry.md 对应键节
  (单一源);本测试只锁「判读面含键」与置位事件记录格式三件,不锁行为面
  (计数端/槽位载体在 decision 层与 audit/provisional.py,另行落锁)。
- v6 text 行 7/11/13 判据=键名在 telemetry/schema.py 可检索,本测试即其
  等强判据的直读形态(不经 sim 侧 _text_of,避免测试耦合 sim 模块)。
"""
from __future__ import annotations

from sr_od.application.currency_war.telemetry import schema


def test_v6_row7_f7_contingency_armed_in_schema() -> None:
    """行 7:键名在 schema 判读面 + 置位事件记录格式三件(门红事件 id/
    归因批 id/时间戳)。"""
    assert schema.F7_CONTINGENCY_ARMED == 'f7_contingency_armed'
    assert schema.F7_CONTINGENCY_ARMED_EVENT_FIELDS == (
        'gate_red_event_id', 'attribution_batch_id', 'ts')


def test_v6_row11_depsilon_advisor_violation_in_schema() -> None:
    """行 11:漂移哨兵键名在 schema 判读面(键>0 ⇔ 门/检测两路实现漂移,
    计数对象=非豁免族 ∧ 瞬时检测域)。"""
    assert schema.DEPSILON_ADVISOR_VIOLATION == 'depsilon_advisor_violation'


def test_v6_row13_f7_exempt_emission_in_schema() -> None:
    """行 13:豁免发射计量键名在 schema 判读面(观察级不进门,分键含
    真濒死∧D_ε 子态)。"""
    assert schema.F7_EXEMPT_EMISSION == 'f7_exempt_emission'


def test_f7_depsilon_obs_keys_domain() -> None:
    """三键域单一源:v6 text 锚对象与键名常量一致(防手写名单漂移)。"""
    assert schema.F7_DEPSILON_OBS_KEYS == (
        'f7_contingency_armed',
        'depsilon_advisor_violation',
        'f7_exempt_emission',
    )
