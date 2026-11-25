"""主角光环团队规模代价事实测试(``knowledge/cw_aura_facts``)。

锁的设计约定(契约正文 = ``cw_aura_facts`` 模块 docstring):

- 规模代价表由注册表效果原文派生(「占用N团队规模」),零手抄——本测试不
  复刻派生逻辑,只锁**已知事实对账**:全注册表 82 条里代价 ≠ 1 的只有
  「高傲巨人」(官方原文「上阵该角色占用2团队规模」;实机样本 = 局 43 选该
  光环后 5 个单位占 6 > 上限 5)。注册表重跑或原文改写让派生漂移 → 本条红;
- 缺省代价 1:未知名 / None 同 1(代价缺省永远落在「不额外占用」侧,不虚构超限)。
"""
from __future__ import annotations

from sr_od.application.currency_war.data.cw_spot_lights import SPOT_LIGHTS
from sr_od.application.currency_war.knowledge.cw_aura_facts import (
    aura_team_size_cost,
)


def test_only_proud_giant_costs_two() -> None:
    """注册表全量对账:代价 ≠ 1 的光环仅「高傲巨人」(= 2)。"""
    names = [x.name for x in SPOT_LIGHTS]
    assert names, '注册表为空(生成器产物缺失)'
    off_default = {n: aura_team_size_cost(n) for n in names
                   if aura_team_size_cost(n) != 1}
    assert off_default == {'高傲巨人': 2}, \
        f'规模代价派生表与注册表原文对账失败,实际 {off_default}'


def test_default_cost_is_one() -> None:
    """缺省代价 1:无光环 / 未知名。"""
    assert aura_team_size_cost(None) == 1
    assert aura_team_size_cost('') == 1
    assert aura_team_size_cost('不存在的光环') == 1
    assert aura_team_size_cost('从师') == 1
