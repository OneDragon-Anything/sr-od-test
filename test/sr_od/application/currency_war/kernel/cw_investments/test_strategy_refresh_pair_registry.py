"""合并同类项注册面测试(cw_investments 分目录镜像;等值迁移 + 单一源 +
两闭集落位)。

- 锁 6:STRATEGY_EFFECTS 条目 payload is STRATEGY_ECONOMY 注册行同一实例
  (单一源)+ plaza id / 触发 / 类别对拍;
- 锁 7:闭集落位——kernel 侧引擎单字段桶谓词直测;策略侧字段分类 =
  待建模桶在册 + 选卡估值 fail-closed 0(条件概率型,现金分 1→0 失真修正
  方向 = 低估);
- 锁 8:注册行等值迁移完整性——instant_gold 缺省 ∧ gold_per_refresh_pair=1
  ∧ free_refresh_burst=4(防迁移半途;同形先例 = test_economy 尾款交付
  迁移锁)。

卡面官方原文:「刷新商店时，若刷新的角色中出现2个相同的角色，获得1金币。
获得4次免费刷新。」
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import cw4_gs

from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
    is_economy_engine,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    _PENDING_MODELING_FIELDS,
    strategy_economy_value,
)


def test_refresh_pair_spec_single_source_identity() -> None:
    """锁 6:条目 payload 必须为注册行同一实例(误复制实例即红;市场干预
    单一源锁同型),plaza id 对拍 + 触发/类别声明对拍。"""
    spec = STRATEGY_EFFECTS['合并同类项']
    assert spec.payload is STRATEGY_ECONOMY['合并同类项'], \
        'payload 必须为注册行同一实例(单一源)'
    assert spec.id == '102901', 'plaza id 对拍'
    assert spec.trigger is TriggerKind.ON_REFRESH, '触发声明 = 手动刷新事件'
    assert spec.category is EffectKind.ECONOMY, '类别声明 = 经济发放'


def test_refresh_pair_migration_completeness() -> None:
    """锁 8:注册行等值迁移完整性——instant_gold 缺省(0)∧
    gold_per_refresh_pair=1 ∧ free_refresh_burst=4。防「双登记」回潮:
    双登记下未来 instant_gold 世界发放腿建模时本卡金腿双发,需排除集特判
    = 弃案埋雷。"""
    eff = STRATEGY_ECONOMY['合并同类项']
    assert eff.instant_gold == 0, '迁移完整性:instant_gold 缺省(防双登记)'
    assert eff.gold_per_refresh_pair == 1, '迁移完整性:条件金腿挂新字段'
    assert eff.free_refresh_burst == 4, 'burst 腿原值保持(卡面 4 明写)'


def test_refresh_pair_engine_and_pending_classification() -> None:
    """锁 7:闭集落位两断言(kernel 侧引擎桶谓词直测 + 策略侧待建模桶在册),
    附选卡估值 fail-closed 行为锁(条件概率型现金分 1→0 = 失真修正,
    方向低估)。"""
    assert is_economy_engine(EconomyEffect(gold_per_refresh_pair=1)) is True, \
        '引擎单字段桶生效(与 free_refresh_burst 同族;迁移前后引擎判定恒真)'
    assert 'gold_per_refresh_pair' in _PENDING_MODELING_FIELDS, \
        '策略侧分类 = 待建模桶(出对频次分布未采,分类校验闭集成员)'
    gs = cw4_gs(node_fill=False, shop_screen='off')
    assert strategy_economy_value('合并同类项', gs) == (0.0, False), \
        '估值 fail-closed:条件概率型不入现金分(条件刷新腿同判据先例:' \
        '按兑现结构性归待建模桶)'
