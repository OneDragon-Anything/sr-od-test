"""固定理财+ 注册面测试(cw_investments 分目录镜像;「现在以及每个位面
开始时」族展开卡,先例 = 同目录 test_strategy_gudinglicai_registry.py)。

测试面依据 = 迭代设计 designs/T-183-gudinglicai-plus.md §2.1/§2.2/§4
(锁 1/锁 2)+ 用户裁定书 T-182 节同判(2026-11-01 用户决定:中途拿卡时当前
已开始的位面,其位面段奖励照常发放〔全额〕,后续位面照常——两卡一次
用户决定,裁决联动禁两态)。卡面官方原文(cw_invest_data.py:131 逐字):
「现在以及每个位面开始时，获得6经验值和3次免费刷新。」

机制件零新增(桥/腿按 payload 字段鸭子类型读取(duck typing),全量承姊妹批),本文件只锁
注册面两处:注册行四字段现值 + EffectSpec 条目定论形态;行为面(桥/
腿/登记拍/sim walk)由姊妹锁文件与同目录 gain-chain/sim 镜像辖。

- 注册行锁(锁 1):四字段现值 xp_instant=6 / xp_per_plane=6 /
  free_refresh_burst=3 / free_refresh_per_plane=3 + 其余字段缺省
  (对照 EconomyEffect() 默认实例逐字段比);
- EffectSpec 条目锁(锁 2,定论形):trigger=PLANE_START /
  duration=PERMANENT / category=STATE / payload is STRATEGY_ECONOMY
  ['固定理财+'](同一实例)/ pending=False(二义经用户裁定补发,
  与姊妹同判,notes 记裁定)/ notes 含两条效果条目分段与同判裁定语义。
"""
from __future__ import annotations

import dataclasses
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
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.env_economy import (
    XP_GOLD_RATE,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '固定理财+'
_PLANE_FIELDS = ('xp_instant', 'xp_per_plane',
                 'free_refresh_burst', 'free_refresh_per_plane')


def test_gudinglicai_plus_registration_row_four_fields() -> None:
    """注册行锁(锁 1):四字段现值(6/6/3/3)+ 其余字段缺省(对照
    EconomyEffect() 默认实例逐字段比,防并行批静默带值)。"""
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    eff = STRATEGY_ECONOMY[_CARD]
    assert (eff.xp_instant, eff.xp_per_plane,
            eff.free_refresh_burst, eff.free_refresh_per_plane) == (6, 6, 3, 3)
    assert eff.xp_per_node == 0, '本卡行无显式零占位,缺省即 0'
    default = EconomyEffect()
    drifted = [f.name for f in dataclasses.fields(EconomyEffect)
               if getattr(eff, f.name) != getattr(default, f.name)
               and f.name not in _PLANE_FIELDS]
    assert drifted == [], f'四字段之外静默带值: {drifted}'


def test_gudinglicai_plus_effect_spec_entry() -> None:
    """EffectSpec 条目锁(锁 2,定论形):五元组 + 单一实例 payload +
    pending 撤除(与姊妹同判记 notes)+ notes 两条效果条目分段与同判裁定语义。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '201802'
    assert spec.trigger is TriggerKind.PLANE_START
    assert spec.duration is DurationKind.PERMANENT
    assert spec.category is EffectKind.STATE
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 引注册行同一实例(单一源)'
    assert spec.pending is False, \
        '所在位面补发读法经用户裁定(2026-11-01)补发,与姊妹同判定论'
    for token in ('位面段', '补发', '2026-11-01', '同判'):
        assert token in (spec.notes or ''), f'notes 承载裁定语义缺 {token}'


def test_gudinglicai_plus_cash_score_instant_active() -> None:
    """现金分激活锁:xp_instant=6 已登记计分分类字段,注册挂值即通道自动
    生效(6×XP_GOLD_RATE;位面段两字段待建模塌 0,估值面不重复计;
    存量并排断言见 test_invest_strategy,本锁为镜像位单卡点)。"""
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (6.0 * XP_GOLD_RATE, True)
