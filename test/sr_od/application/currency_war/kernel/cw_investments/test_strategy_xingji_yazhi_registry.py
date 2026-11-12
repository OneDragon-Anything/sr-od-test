"""星级压制注册面测试(cw_investments 分目录镜像;战力类零响应族
第 14 条,先例 = 同目录 test_strategy_cheer_squad_registry.py)。

测试面依据 = 原稿锁面(定稿)§4 锁 1/锁 4。卡面官方原文:「我方小队获得10%速度增幅,
攻击星级低于自身的敌人后,额外造成1次等同于原伤害20%的真实伤害。」

- 登记面锁:条目五元组 = PLANE_START 占位形(无离散触发事件,对齐
  _portal_placeholder_spec 环境源先例)× WHILE_HELD × UNIT_BUFF ×
  UnitBuffRef(官方效果原文)× duties 三位全 False(零计数器/零预知/
  零姿态);pending=False(对象/数值/触发条件/效果形态/伤害性质全
  desc 明文);effect_text 与 base 注册表 .effect 单一源对拍(条目经
  PLAZA_AUGMENTS 数据面表达式引官方原文,防表达式被改字面量后漂移);
  现金分支 = 已注册名无 economy → (0.0, False)(战力类不进经济模型,
  防未来误加 STRATEGY_ECONOMY 条目或通道误开);
- 绑定负锁(本卡特有):卡不入 STRATEGY_BINDINGS(泛用全队速度 buff
  + 泛用攻击追伤被动,无阵营/召唤物/星徽点名;「星级」系单位养成通用
  轴非阵营语义),strategy_bindings() 返回默认空元组——把现状固化为
  设计约定,防未来误绑;
- 封闭集负锁:卡不入 PICK_INVEST_EFFECTS(无获得时点写状态副本,零响应
  登记不进发放族;断言本体 = 存量闭集锁,此处只锁本卡键不在集)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    DurationKind,
    EffectKind,
    TriggerKind,
    UnitBuffRef,
)
from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_investments import (
    INVESTMENT_STRATEGIES,
    STRATEGY_BINDINGS,
    STRATEGY_EFFECTS,
    strategy_bindings,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '星级压制'


def test_xingji_yazhi_unit_buff_registration_surface() -> None:
    """星级压制 登记面锁(战力类零响应族第 14 条,复合卡单条目:速度
    光环+攻击条件追伤,同构先例 = 全队的希望/应援团/延迟收益):条目
    五元组逐位 + 单一源对拍 + 现金 fail-closed 0;构建校验(孤儿键/
    id 双匹配)import 期已过——本测试存活即证。clause 2 触发(攻击星级
    低于自身的敌人后,战斗中逐攻击评估;星级读法判读申报制留痕)与数值
    (10% 速度/20% 原伤害真实伤害)游戏侧自算,bot 零建模零观察。"""
    spec = STRATEGY_EFFECTS[_CARD]
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    assert spec.id == '201001'
    assert spec.name == _CARD
    assert spec.trigger is TriggerKind.PLANE_START
    assert spec.duration is DurationKind.WHILE_HELD
    assert spec.category is EffectKind.UNIT_BUFF
    assert isinstance(spec.payload, UnitBuffRef)
    assert spec.payload.effect_text \
        == INVESTMENT_STRATEGIES[_CARD].effect, \
        'effect_text 单一源对拍(= base 注册表 .effect)'
    assert (spec.duties.track, spec.duties.predict, spec.duties.respond) \
        == (False, False, False), '零 duties(零响应登记)'
    assert spec.pending is False
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器(_seed_progress 双 None)'
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (0.0, False), \
        '已注册名无 economy → 现金 fail-closed 0(战力类不进经济模型)'


def test_xingji_yazhi_no_faction_binding() -> None:
    """绑定负锁(本卡特有):星级压制不入 STRATEGY_BINDINGS——泛用数值
    (全队速度 buff + 攻击条件追伤被动)不绑,登记判据直辖(「星级」系
    单位养成通用轴非阵营语义;同形泛用卡先例同不在表);
    strategy_bindings() 对表外卡返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定表零触碰(泛用数值不绑)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_xingji_yazhi_not_in_pick_effects_closed_set() -> None:
    """封闭集负锁:星级压制不得入 PICK_INVEST_EFFECTS(本卡零获得时点
    写状态副本,入集 = 实现错误;全集逐名断言归存量闭集锁,此处只锁
    本卡键不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '零响应登记卡不入发放族封闭集(负向防线)'
