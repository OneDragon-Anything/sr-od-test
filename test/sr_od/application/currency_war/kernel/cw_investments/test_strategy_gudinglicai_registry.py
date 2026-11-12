"""固定理财注册面测试(cw_investments 分目录镜像;「现在以及每个位面
开始时」族位面周期发放首例,先例 = 同目录 test_strategy_xingbian_
registry.py)。

测试面依据 = 原稿锁面(§ 号 = 原稿节序)§2.1/§2.2/§2.6/§4
(锁 1/锁 2/锁 8;锁 3 可达面按裁定 B 改形)+ 用户裁定书 T-182 节
(2026-11-01 用户决定:中途拿卡时当前已开始的位面,其位面段奖励照常发放
〔全额〕,后续位面照常)。卡面官方原文(cw_invest_data.py:130 逐字):
「现在以及每个位面开始时，获得4经验值和2次免费刷新。」

- 注册行锁(锁 1):四字段现值 xp_instant=4 / xp_per_plane=4 /
  free_refresh_burst=2 / free_refresh_per_plane=2 + xp_per_node 缺省
  (0;显式零占位已删);姊妹行四字段现值 6/6/3/3(展开批落地后逐批
  显式扩面改写,原冻结断言 T-183 批随批解除);
- EffectSpec 条目锁(锁 2):trigger=PLANE_START / duration=PERMANENT /
  category=STATE / payload is STRATEGY_ECONOMY['固定理财'](同一实例)
  / pending=False(二义经用户裁定补发,定论非冻结,notes 记裁定,
  T-180 星变同先例)/ notes 含两条效果条目分段与裁定语义;
- 引擎通道闭集锁:双字段入 _ENGINE_CHANNEL_SINGLE_FIELDS(周期发放 =
  持续通道,非一次性/结构登记排除桶);
- 待建模登记锁(锁 8):两行存续 + 描述非空(闭集断言④点名,删行即
  import 炸——本测试存活即证);
- 现金分激活锁:xp_instant=4 已登记计分分类字段,注册挂值即通道自动
  生效(4×XP_GOLD_RATE;位面段两字段待建模塌 0 不重复计)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    _ENGINE_CHANNEL_SINGLE_FIELDS,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    XP_GOLD_RATE,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    STRATEGY_ECONOMY_PENDING_MODELING,
    strategy_economy_value,
)

_CARD = '固定理财'
_SISTER = '固定理财+'


def test_gudinglicai_registration_row_four_fields() -> None:
    """注册行锁(锁 1):四字段现值 + xp_per_node 缺省 0;姊妹行四字段
    现值(6/6/3/3,展开批落地后逐批显式扩面改写,键集/行锁 +1 家族
    先例同型)。"""
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    eff = STRATEGY_ECONOMY[_CARD]
    assert (eff.xp_instant, eff.xp_per_plane,
            eff.free_refresh_burst, eff.free_refresh_per_plane) == (4, 4, 2, 2)
    assert eff.xp_per_node == 0, 'xp_per_node 显式零占位已删,缺省即 0'
    sister = STRATEGY_ECONOMY[_SISTER]
    assert (sister.xp_instant, sister.xp_per_plane,
            sister.free_refresh_burst, sister.free_refresh_per_plane) \
        == (6, 6, 3, 3), '姊妹展开批落地四字段现值'
    assert sister.xp_per_node == 0, '姊妹行无显式零占位,缺省即 0'


def test_gudinglicai_effect_spec_entry() -> None:
    """EffectSpec 条目锁(锁 2,裁定 B 形):五元组 + 单一实例 payload +
    pending 撤除(定论记 notes)+ notes 两条效果条目分段与裁定语义。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '201801'
    assert spec.trigger is TriggerKind.PLANE_START
    assert spec.duration is DurationKind.PERMANENT
    assert spec.category is EffectKind.STATE
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 引注册行同一实例(单一源)'
    assert spec.pending is False, \
        '所在位面补发读法经用户裁定(2026-11-01)补发,定论非冻结'
    for token in ('位面段', '补发', '2026-11-01'):
        assert token in (spec.notes or ''), f'notes 承载裁定语义缺 {token}'


def test_gudinglicai_engine_channel_membership() -> None:
    """引擎通道闭集锁:位面段双字段入 _ENGINE_CHANNEL_SINGLE_FIELDS
    (周期发放 = 持续通道,不入一次性/结构登记排除桶)。"""
    members = dict(_ENGINE_CHANNEL_SINGLE_FIELDS)
    assert members.get('xp_per_plane') == 0
    assert members.get('free_refresh_per_plane') == 0


def test_gudinglicai_pending_modeling_rows() -> None:
    """待建模登记锁(锁 8):两行存续 + 描述非空(闭集断言④点名卡,
    删行即 import 炸——本测试存活即证);描述改写为建模落地后形态
    (位面段发放类效果条目已建,估值通道未建)。"""
    for name in (_CARD, _SISTER):
        assert name in STRATEGY_ECONOMY_PENDING_MODELING, name
        assert STRATEGY_ECONOMY_PENDING_MODELING[name], f'{name} 描述非空'
        assert '估值通道未建' in STRATEGY_ECONOMY_PENDING_MODELING[name], \
            f'{name} 行描述改写为建模落地后形态(位面段效果条目已建,估值未建)'


def test_gudinglicai_cash_score_instant_active() -> None:
    """现金分激活锁:xp_instant=4 已登记计分分类字段,注册挂值即通道自动
    生效(4×XP_GOLD_RATE;裁决点 6 默认案);位面段两字段待建模塌 0,
    估值面不重复计。"""
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (4.0 * XP_GOLD_RATE, True)
