"""deployed 计数双源仲裁内核测试(``combine_deployed_count``)。

锁的设计约定(契约正文 = ``cw_arbitration.combine_deployed_count`` docstring
与注册键 ``deployed_count`` 的 fail_closed_side 声明):

- 常规态两源取低值(fail-closed 向「板未满」侧:paddle 高估 → 板满假判 →
  no-op 死锁,贵;低估 → 多试一次拖拽被游戏拒,廉价),分歧告警带 |Δ| > 1;
- **超限态不取低值**:cap 已知且 paddle X > cap → 返 X。依据 = 游戏计数器 X 是
  团队规模占用数(含主角光环持有者的额外占用),CV 占用只数单位、看不见规模,
  取低值会把超限信号压掉(6 被压回 5 = 机器人看不见超限态的一环);
- cap 是裁决辅助输入不是第三源:cap 未知(None)→ 退回取低值;注册面
  ``arbitrate`` 的 verdict 判定不因 cap 在场改变(带内 Δ = noise)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.obs.cw_arbitration import (
    VERDICT_NOISE,
    VERDICT_REJECTED,
    arbitrate,
    combine_deployed_count,
)


@pytest.mark.parametrize(('paddle_x', 'cv', 'cap', 'expected'), [
    (6, 5, 5, (6, False)),        # 超限态:X > cap → 不取低值;Δ=1 带内
    (7, 5, 5, (7, True)),         # 超限态分歧带判据不变(|Δ|>1 = 结构性分歧)
    (6, 5, None, (5, False)),     # cap 未知 → 退回取低值(旧规则)
    (6, 5, 7, (5, False)),        # X ≤ cap 非超限 → 取低值(旧规则)
    (5, 3, 5, (3, True)),         # 常规态带外分歧(|Δ|=2)
    (5, 4, 5, (4, False)),        # 常规态带内分歧(|Δ|=1)
    (5, 5, 5, (5, False)),
    (None, 5, 5, (5, False)),     # 单源缺席退化
    (6, None, 5, (6, False)),
    (None, None, 5, (None, False)),
])
def test_combine_deployed_count(paddle_x, cv, cap, expected) -> None:
    """裁决值与分歧位(超限态不取低值;cap 未知退回旧规则)。"""
    assert combine_deployed_count(paddle_x, cv, cap=cap) == expected


def test_arbitrate_registry_accepts_cap_as_aux_input() -> None:
    """注册面:cap 随 readings 传入即生效,verdict 仍按两源判定(Δ=1 = noise)。"""
    value, verdict, divergent = arbitrate(
        'deployed_count', {'paddle_x': 6, 'cv_occupied': 5, 'cap': 5})
    assert (value, verdict, divergent) == (6, VERDICT_NOISE, False)
    value2, verdict2, _ = arbitrate(
        'deployed_count', {'paddle_x': 6, 'cv_occupied': 5})
    assert (value2, verdict2) == (5, VERDICT_NOISE)
    value3, verdict3, _ = arbitrate(
        'deployed_count', {'paddle_x': 6, 'cv_occupied': None, 'cap': 5})
    assert (value3, verdict3) == (6, VERDICT_REJECTED)
