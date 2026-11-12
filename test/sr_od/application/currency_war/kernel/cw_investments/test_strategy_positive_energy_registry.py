"""正能量注册面测试(cw_investments 分目录镜像;战力类零响应族
第 6 条,族内首个恢复型(非增幅光环),先例 = 同目录
test_strategy_cheer_squad_registry.py)。

测试面依据 = 原稿锁面(定稿)§4 锁 1/锁 3/锁 4。卡面官方原文:「进入战斗
时，我方小队恢复等同于能量上限20%的能量。」

- 登记面锁:条目五元组 = PLANE_START 占位形(无离散触发事件,对齐
  _portal_placeholder_spec 环境源先例)× WHILE_HELD × UNIT_BUFF ×
  UnitBuffRef(官方效果原文)× duties 三位全 False(零计数器/零预知/
  零姿态);pending=False(触发时点/作用对象/动作/数值全 desc 明文;
  「能量上限」基数口径游戏侧定义,零行为落点,notes 判读注记留痕);
  effect_text 与 base 注册表 .effect 单一源对拍(条目经 PLAZA_AUGMENTS
  数据面表达式引官方原文,防表达式被改字面量后漂移);现金分支 =
  已注册名无 economy → (0.0, False)(战力类不进经济模型,防未来误加
  STRATEGY_ECONOMY 条目或通道误开);
- 绑定负锁:卡不入 STRATEGY_BINDINGS(泛用全队恢复,无阵营/召唤物/
  星徽点名;「恢复能量」≠能量队卡,登记判据注释同型噪声例证直辖),
  strategy_bindings() 返回默认空元组——把现状固化为设计约定,防未来
  误绑;
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

_CARD = '正能量'


def test_positive_energy_unit_buff_registration_surface() -> None:
    """正能量 登记面锁(战力类零响应族第 6 条,族内首个恢复型
    (非增幅光环),同形先例 = 全队的希望/溜佩佩/溜佩佩+/团队力量·银/
    应援团):条目五元组逐位 + 单一源对拍 + 现金 fail-closed 0;构建校验
    (孤儿键/id 双匹配)import 期已过——本测试存活即证。恢复事件(入场拍
    每名角色恢复自身能量上限 20%)游戏侧自算,bot 零建模零观察。"""
    spec = STRATEGY_EFFECTS[_CARD]
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    assert spec.id == '150301'
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


def test_positive_energy_no_faction_binding() -> None:
    """绑定负锁:正能量不入 STRATEGY_BINDINGS——泛用数值(全队恢复)
    不绑,登记判据直辖(「恢复能量」≠能量队卡,同型噪声例证在码;同形
    泛用卡团队力量·银/应援团同不在表);strategy_bindings() 对表外卡
    返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定表零触碰(泛用数值不绑)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_positive_energy_not_in_pick_effects_closed_set() -> None:
    """封闭集负锁:正能量不得入 PICK_INVEST_EFFECTS(本卡零获得时点
    写状态副本,入集 = 实现错误;全集逐名断言归存量闭集锁,此处只锁
    本卡键不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '零响应登记卡不入发放族封闭集(负向防线)'
