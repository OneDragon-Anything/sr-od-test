"""当头一棒注册面测试(cw_investments 分目录镜像;战力类零响应族敌方侧
被动卡,先例 = 同目录 test_strategy_bangyang_de_liliang_yin_registry.py)。

测试面依据 = 原稿锁面(定稿)§4 锁 1/锁 3/锁 4。卡面官方原文:「每个波次开始时，对
生命上限最高的敌方目标造成1000%基础伤害，并使其陷入【脆弱】：受到的
伤害提高30%。」

- 登记面锁:条目五元组 = PLANE_START 占位形(波次开始系游戏侧战斗内
  评估拍,无离散触发事件,对齐 _portal_placeholder_spec 先例)×
  WHILE_HELD × UNIT_BUFF × UnitBuffRef(官方效果原文)× duties 三位全
  False(零计数器/零预知/零姿态);pending=False(触发时点/目标规则/
  效果/数值五要素全 desc 明文);effect_text 与 base 注册表 .effect 单一
  源对拍(条目经 PLAZA_AUGMENTS 数据面表达式引官方原文,防表达式被改
  字面量后漂移);现金分支 = 已注册名无 economy → (0.0, False)(战力类
  不进经济模型,防未来误加 STRATEGY_ECONOMY 条目或通道误开);
- 绑定负锁:卡不入 STRATEGY_BINDINGS(泛用对敌战斗数值,无阵营/召唤物/
  星徽点名;「生命上限最高的敌方目标」系战斗通用域选择非阵营语义),
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

_CARD = '当头一棒'


def test_dangtou_yibang_unit_buff_registration_surface() -> None:
    """当头一棒 登记面锁(战力类零响应族首条敌方侧效果卡,同形先例 =
    全队的希望/溜佩佩/溜佩佩+/团队力量·银/应援团/正能量/完美开局/效率
    员工奖/基层贡献/榜样的力量·银):条目五元组逐位 + 单一源对拍 + 现金
    fail-closed 0;构建校验(孤儿键/id 双匹配)import 期已过——本测试存活
    即证。载体词面张力申报:对敌伤害+易伤非「单位强化」我方增益,零响应
    桶机制对效果方向中立(设计 §5 裁决点 1 默认案)。波次触发/目标选取
    (生命上限最高)与数值(1000% 伤害/30% 易伤)游戏侧自算,bot 零建模
    零观察——波次与脆弱词面 kernel/sim 全域零命中,cw_sim_enemy 系难度
    记录非战斗单位,敌方目标域无读口可接。"""
    spec = STRATEGY_EFFECTS[_CARD]
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    assert spec.id == '150901'
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


def test_dangtou_yibang_no_faction_binding() -> None:
    """绑定负锁:当头一棒不入 STRATEGY_BINDINGS——泛用数值(对敌 1000%
    伤害+30% 易伤)不绑,登记判据直辖(同形泛用卡全队的希望/应援团/正
    能量/完美开局/效率员工奖/基层贡献/榜样的力量·银同不在表;「生命上限
    最高的敌方目标」系战斗通用域选取非阵营语义,敌方侧无阵营点名);
    strategy_bindings() 对表外卡返回默认空元组(fail-closed,方向分 0)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定表零触碰(泛用数值不绑)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_dangtou_yibang_not_in_pick_effects_closed_set() -> None:
    """封闭集负锁:当头一棒不得入 PICK_INVEST_EFFECTS(本卡零获得时点
    写状态副本,入集 = 实现错误;全集逐名断言归存量闭集锁,此处只锁本卡键
    不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '零响应登记卡不入发放族封闭集(负向防线)'
