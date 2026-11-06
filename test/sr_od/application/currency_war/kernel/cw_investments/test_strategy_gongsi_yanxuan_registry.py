"""公司严选注册面测试(cw_investments 分目录镜像;「现在及每个位面
开始时」族位面周期金首例 + 商店改写对首例,先例 = 同目录
test_strategy_gudinglicai_registry.py)。

测试面依据 = 迭代设计 designs/T-309-gongsi-yanxuan.md §2.1/§2.2/§2.4
+ REVIEW-T309 §3(裁决点 5 = B 案改判:用户裁定 2026-11-01 族级拍定
「中途拿卡所在位面补发 = 补发·当前位面全额」,固定理财族级明文覆盖;
裁决点 6 = 增条 pending=False 定谳;裁决点 7 = 三新字段入待建模塌 0)。
卡面官方原文(cw_invest_data.py 逐字):
「现在及每个位面开始时，开启一个由5个独特4费角色组成的商店，并获得3金币。」

- 注册行锁(锁 1):四字段现值 instant_gold=3 / gold_per_plane=3 /
  shop_rewrite_forced_cost=4 / shop_rewrite_forced_unique=True;
- EffectSpec 条目锁(锁 2):五元组 + payload 同实例(单一源)+ pending
  定谳(裁定记录住 notes,尾行特征串 = 条目锚,防与注释同名文本误触)
  + duties 对表姊妹落码形(track+respond);
- 引擎通道闭集锁(治理后形 = 测试锁对账,非 import 炸):三字段入
  _ENGINE_CHANNEL_SINGLE_FIELDS 且不入排除桶(位面周期发放/可重复
  触发 = 持续通道,非一次性/结构登记);
- 待建模登记锁:卡级行存续 + 描述非空;
- 现金分激活锁:instant_gold=3 面值计分,位面段/改写对三字段待建模
  塌 0 不重复计(策略侧打分归估值批,范围外纪律)。
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
    _ENGINE_CHANNEL_EXCLUDED_FIELDS,
    _ENGINE_CHANNEL_SINGLE_FIELDS,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    STRATEGY_ECONOMY_PENDING_MODELING,
    strategy_economy_value,
)

_CARD = '公司严选'
_SISTER = '固定理财'


def test_gongsi_yanxuan_registration_row_four_fields() -> None:
    """注册行锁(锁 1):四字段现值(卡面数值直读 3 金/4 费/独特);
    姊妹行位面段两字段维持(同族参照防误伤)。"""
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    eff = STRATEGY_ECONOMY[_CARD]
    assert (eff.instant_gold, eff.gold_per_plane,
            eff.shop_rewrite_forced_cost, eff.shop_rewrite_forced_unique) \
        == (3, 3, 4, True)
    sister = STRATEGY_ECONOMY[_SISTER]
    assert (sister.xp_instant, sister.xp_per_plane,
            sister.free_refresh_burst, sister.free_refresh_per_plane) \
        == (4, 4, 2, 2), '姊妹行四字段现值(同族参照)'


def test_gongsi_yanxuan_effect_spec_entry() -> None:
    """EffectSpec 条目锁(锁 2,B 案定谳形):五元组 + payload 同一实例
    + pending 撤除(裁定记录住 notes)+ duties 对表姊妹落码形 +
    notes 尾行特征串(条目锚,多行文本判据用尾行特征防同名误触)。"""
    spec = STRATEGY_EFFECTS[_CARD]
    assert spec.id == '301401'
    assert spec.trigger is TriggerKind.PLANE_START
    assert spec.duration is DurationKind.PERMANENT
    assert spec.category is EffectKind.STATE
    assert spec.payload is STRATEGY_ECONOMY[_CARD], \
        'payload 引注册行同一实例(单一源)'
    assert spec.pending is False, \
        '位面段补发读法经用户裁定(2026-11-01 族级)定谳,非冻结'
    sister = STRATEGY_EFFECTS[_SISTER]
    assert (spec.duties.track, spec.duties.respond) \
        == (sister.duties.track, sister.duties.respond), \
        'duties 对表姊妹落码形(裁决联动禁两态)'
    for token in ('位面段', '补发', '2026-11-01', '固定理财族同判', '独特'):
        assert token in (spec.notes or ''), f'notes 承载裁定语义缺 {token}'
    assert (spec.notes or '').endswith('2★ 直出翻星效果条目与基线共享(人才下沉局)'), \
        'notes 尾行特征串(条目锚)'


def test_gongsi_yanxuan_engine_channel_membership() -> None:
    """引擎通道闭集锁(治理后形 = 测试锁对账):三字段入
    _ENGINE_CHANNEL_SINGLE_FIELDS(默认值对账)且不入排除桶——位面
    周期金与可重复触发的改写 = 持续通道;改写为呈现面腿非刷新激励,
    引擎旗标语义 = 持卡在场即帧级顶级(P81 划界:持续/一次性结构事实)。"""
    members = dict(_ENGINE_CHANNEL_SINGLE_FIELDS)
    assert members.get('gold_per_plane') == 0
    assert members.get('shop_rewrite_forced_cost') == 0
    assert members.get('shop_rewrite_forced_unique') is False
    for field_name in ('gold_per_plane', 'shop_rewrite_forced_cost',
                       'shop_rewrite_forced_unique'):
        assert field_name not in _ENGINE_CHANNEL_EXCLUDED_FIELDS, field_name


def test_gongsi_yanxuan_pending_modeling_row() -> None:
    """待建模登记锁:卡级行存续 + 描述非空 + 缺口语义
    (位面段/改写对估值通道未建)。"""
    assert _CARD in STRATEGY_ECONOMY_PENDING_MODELING
    desc = STRATEGY_ECONOMY_PENDING_MODELING[_CARD]
    assert desc, '描述非空'
    assert '估值通道未建' in desc


def test_gongsi_yanxuan_cash_score_instant_only() -> None:
    """现金分激活锁:instant_gold=3 面值计分;位面段金与商店改写对三
    字段待建模塌 0,估值面不重复计(裁决点 7:面值计分归用户另裁)。"""
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (3.0, True)
