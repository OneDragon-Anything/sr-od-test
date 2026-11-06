"""策略位面-节点合取条件写状态副本发放注册表测试(cw_investments 分目录镜像;宿主
test_cw_investments.py 超行数线,登记面新锁落本镜像目录,先例 =
同目录 test_strategy_gift_grant_tables.py)。

测试面依据 = 迭代设计 designs/T-407-daoyong-shenfen.md(定稿)§4 锁 1
+ 裁决点全部默认案(对抗 2 轮收敛)。卡面官方原文(cw_invest_data.py
352401 行逐字):「进入第二位面的首领节点时，获得一个穿着2个【动能激发剑】
和【列车同行星徽】的【火花】和1个【开拓者】。」

- 表直测锁:条目逐值 + 数据行 id 对拍 + 值形契约(治理口径:值形/星级
  值域/双源对账不入 import 期校验,归本文件把关,防线强于 import 期形查)
  + 校验器复跑不炸(三漂移哨在役:孤儿键/角色名漂移/合取可达性);
- 校验器负例(monkeypatch 表值 → ValueError,import 炸形态同源);
- 交付通道锁:本卡不入效果体表 PICK_INVEST_EFFECTS(写状态副本发放唯一通道 =
  白名单表 + 触发函数,效果体表键集闭集零扩)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_GRANTS,
    STRATEGY_PLANE_BOSS_GRANTS,
)

_CARD = '盗用身份'
_ID = '352401'
_CHAR = '火花'


def test_table_entry() -> None:
    """表条目锁:四元组逐值 = 卡面直读(位面 2/boss 节点/发放角色/星级
    1 = 卡面未标先验),值形 = 扁平 tuple 非容器(登记面单一形态)。"""
    assert STRATEGY_PLANE_BOSS_GRANTS[_CARD] == (2, 'boss', _CHAR, 1)
    assert isinstance(STRATEGY_PLANE_BOSS_GRANTS[_CARD], tuple)


def test_row_shape_contract() -> None:
    """值形契约锁(治理口径归表域把关):逐条目 len==4 且
    (int, str, str, int) 类型序(bool 非 int 位);星级 ∈ {1,2,3};
    位面 ∈ 节点日程真值表键集;节点类型 ∈ 词表;合取位在对应序列恰
    ≥1 次(可达性复核)。"""
    from sr_od.application.currency_war.data.cw_chars import (
        CHARACTER_ROSTER,
    )
    from sr_od.application.currency_war.kernel.cw_node_schedule import (
        NODE_KINDS,
        PLANE_NODE_TABLES,
    )
    for name, (plane, kind, char, star) in STRATEGY_PLANE_BOSS_GRANTS.items():
        assert isinstance(plane, int) and not isinstance(plane, bool), \
            f'{name}: 位面类型漂移'
        assert isinstance(kind, str) and isinstance(char, str), \
            f'{name}: 名段类型漂移'
        assert isinstance(star, int) and not isinstance(star, bool), \
            f'{name}: 星级类型漂移'
        assert star in (1, 2, 3), f'{name}: 星级值域漂移'
        assert char in CHARACTER_ROSTER, f'{name}: 角色名漂移'
        assert plane in PLANE_NODE_TABLES, f'{name}: 位面越界'
        assert kind in NODE_KINDS, f'{name}: 节点类型集外'
        assert kind in PLANE_NODE_TABLES[plane], f'{name}: 合取不可达'


def test_dual_source_reconciliation() -> None:
    """双源对账锁(防两注册面一改一漏):键 ∈ STRATEGY_GRANTS(估值域
    底册)且其 chars_conditional 具名集含本表发放角色(两注册面同出卡面,
    任一侧单独改名即漂移)。"""
    grant = STRATEGY_GRANTS[_CARD]
    named = {c for c, _note in grant.chars_conditional}
    assert _CHAR in named, 'GRANTS 条目具名集缺本表发放角色'


def test_data_row_id_anchor() -> None:
    """数据行锚对拍:base 溯源 id 与卡名一致(表键 ↔ base 溯源;
    数据行 = 卡面冻结权威版本)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
    )
    assert INVESTMENT_STRATEGIES[_CARD].source == f'plaza:{_ID}'


def test_validator_passes_on_current_tables() -> None:
    """校验器复跑不炸(三漂移哨在役、现值表全绿;import 期已跑过一次,
    本锁防后继改表人删除校验调用点)。"""
    cw_investments._validate_strategy_plane_boss_grants()


def test_validator_orphan_key_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·孤儿键(漂移哨①):表键不在 INVESTMENT_STRATEGIES →
    ValueError(版本改名/移除后静默失联;键用注册表外幻影名——已登记卡
    名不可作表外锚)。"""
    monkeypatch.setitem(STRATEGY_PLANE_BOSS_GRANTS, '不存在的卡',
                        (2, 'boss', _CHAR, 1))
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_strategy_plane_boss_grants()


def test_validator_char_drift_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·角色名漂移(漂移哨②):发放角色 ∉ CHARACTER_ROSTER →
    ValueError(错名运行期 = 幻影单位,import 期哨唯一响亮拦截面)。"""
    monkeypatch.setitem(STRATEGY_PLANE_BOSS_GRANTS, _CARD,
                        (2, 'boss', '不存在的角色', 1))
    with pytest.raises(ValueError, match='角色名漂移'):
        cw_investments._validate_strategy_plane_boss_grants()


def test_validator_combo_unreachable_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·合取不可达(漂移哨③):触发位面不在节点日程真值表 →
    ValueError(注册进永不触发节点 = 静默永不发放;位面越界与节点类型
    集外同哨并查,本例取位面越界形——三位面真值表现值含全部合法节点
    类型,合法 kind 的合取恒可达,越界位面是现值下唯一可达负例形)。"""
    monkeypatch.setitem(STRATEGY_PLANE_BOSS_GRANTS, _CARD,
                        (4, 'boss', _CHAR, 1))
    with pytest.raises(ValueError, match='不可达'):
        cw_investments._validate_strategy_plane_boss_grants()


def test_delivery_channel_not_in_pick_effects() -> None:
    """交付通道锁:本卡不入效果体表(写状态副本发放唯一通道 = 白名单表 +
    触发函数;效果体表键集闭集零扩)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS
