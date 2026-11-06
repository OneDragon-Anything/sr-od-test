"""策略卡赠礼条件两条效果条目注册表测试(cw_investments 分目录镜像;宿主
test_cw_investments.py 超行数线,登记面新锁落本镜像目录,先例 =
同目录 test_strategy_jiangben_zengxiao_registry.py)。

测试面依据 = 迭代设计 designs/T-283-mi-zhi-lvren.md(定稿)§4 锁 1/锁 5
+ 七裁决点全部默认案(经族级授权自动收尾,判定 = designs/REVIEW-T283.md)。
卡面官方原文(cw_invest_data.py 253601 行逐字):「激活4【巡海游侠】时，
其中3位巡海游侠会发生一次讨论，之后，你获得一个携带着【星间旅人星徽】
的2星【黄泉】。进入下一个奖励节点时，获得【波提欧】。」

- 表直测锁(锁 1):双表条目逐值 + 数据行 id 对拍 + 校验器复跑不炸
  (四漂移哨在役:孤儿键/角色/阵营/装备;星级值域/人数下界笔误哨按
  2026-10-28 治理判据删,行值精确断言即本文件);
- 校验器负例(monkeypatch 表值 → ValueError,import 炸形态同源);
- 交付通道锁(锁 5 零联动申报的本批自身契约面):两条效果条目世界发放 = 独立
  双表承载,不入效果体表 PICK_INVEST_EFFECTS(估值域 STRATEGY_GRANTS
  条目注释性底册维持,其 20.0 降档锁归 mandate_v1 域存量锁,本文件
  零重复断言)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_FACTION_COUNT_GRANTS,
    STRATEGY_REWARD_NODE_GRANTS,
)

_CARD = '迷之旅人'
_ID = '253601'


def test_faction_count_table_entry() -> None:
    """效果条目1 表条目锁:五元组逐值 = 卡面直读(判据阵营/人数/发放角色/星级/
    携带装备),值形 = 扁平 tuple 非容器(登记面单一形态)。"""
    assert STRATEGY_FACTION_COUNT_GRANTS[_CARD] == \
        ('巡海游侠', 4, '黄泉', 2, '星间旅人星徽')
    assert isinstance(STRATEGY_FACTION_COUNT_GRANTS[_CARD], tuple)


def test_reward_node_table_entry() -> None:
    """效果条目2 表条目锁:二元组逐值(发放角色/星级;星级 1 = desc 未标 1★
    先验,校准改表值常量即一行,响应停防线兜底)。"""
    assert STRATEGY_REWARD_NODE_GRANTS[_CARD] == ('波提欧', 1)


def test_data_row_id_anchor() -> None:
    """数据行锚对拍:base 溯源 id 253601 与卡名一致(表键 ↔ base 溯源;
    数据行 = 卡面冻结正本,表值漂移先炸孤儿键哨,本锁兜 id↔名换位形)。"""
    from sr_od.application.currency_war.kernel.cw_investments import (
        INVESTMENT_STRATEGIES,
    )
    assert INVESTMENT_STRATEGIES[_CARD].source == f'plaza:{_ID}'


def test_validator_passes_on_current_tables() -> None:
    """校验器复跑不炸(四漂移哨在役、现值表全绿;import 期已跑过一次,
    本锁防后继改表人删除校验调用点)。"""
    cw_investments._validate_strategy_gift_grants()


def test_validator_orphan_key_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·孤儿键(漂移哨①):表键不在 INVESTMENT_STRATEGIES →
    ValueError(防版本改名静默失联;键用注册表外幻影名——「躺平」等
    口语名实为已登记卡,不可作表外锚)。"""
    monkeypatch.setitem(STRATEGY_FACTION_COUNT_GRANTS, '不存在的卡',
                        ('巡海游侠', 4, '黄泉', 2, ''))
    with pytest.raises(ValueError, match='孤儿键'):
        cw_investments._validate_strategy_gift_grants()


def test_validator_char_drift_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·角色名漂移(漂移哨②):发放角色 ∉ CHARACTER_ROSTER →
    ValueError(错名运行期 = 幻影单位,import 期哨唯一响亮拦截面)。"""
    monkeypatch.setitem(STRATEGY_FACTION_COUNT_GRANTS, _CARD,
                        ('巡海游侠', 4, '不存在的角色', 2, ''))
    with pytest.raises(ValueError, match='角色名漂移'):
        cw_investments._validate_strategy_gift_grants()


def test_validator_faction_drift_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·阵营名漂移(漂移哨③):判据阵营 ∉ FACTIONS → ValueError
    (判据源失联 = 条件腿静默永不达标)。"""
    monkeypatch.setitem(STRATEGY_FACTION_COUNT_GRANTS, _CARD,
                        ('不存在的羁绊', 4, '黄泉', 2, ''))
    with pytest.raises(ValueError, match='阵营漂移'):
        cw_investments._validate_strategy_gift_grants()


def test_validator_equip_drift_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·装备名漂移(漂移哨④):携带装备非空且 ∉ EQUIPMENTS →
    ValueError(盲追加幻影装备入栏)。"""
    monkeypatch.setitem(STRATEGY_FACTION_COUNT_GRANTS, _CARD,
                        ('巡海游侠', 4, '黄泉', 2, '不存在的装备'))
    with pytest.raises(ValueError, match='装备名漂移'):
        cw_investments._validate_strategy_gift_grants()


def test_validator_reward_node_char_drift_negative(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """负例·效果条目2 角色名漂移(漂移哨②):REWARD_NODE 表发放角色 ∉
    CHARACTER_ROSTER → ValueError(独立用例:setitem 残留至用例结束,
    与效果条目1 负例同用例会先炸效果条目1 哨)。"""
    monkeypatch.setitem(STRATEGY_REWARD_NODE_GRANTS, _CARD,
                        ('不存在的角色', 1))
    with pytest.raises(ValueError, match='角色名漂移'):
        cw_investments._validate_strategy_gift_grants()


def test_delivery_channel_not_in_pick_effects() -> None:
    """交付通道锁:两条效果条目不入效果体表(世界发放唯一通道 = 双白名单表 +
    触发函数;效果体表键集闭集零扩,估值域底册条目维持注释性语义)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS
