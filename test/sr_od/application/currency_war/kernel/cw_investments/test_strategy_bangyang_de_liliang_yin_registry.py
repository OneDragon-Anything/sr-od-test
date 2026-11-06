"""榜样的力量·银注册面测试(cw_investments 分目录镜像;战力类零响应族
标记式单体选择卡,先例 = 同目录 test_strategy_jiceng_gongxian_registry.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-156-bangyang-
de-liliang-yin.md(定稿)§4 锁 1/锁 3/锁 4。卡面官方原文:「战斗中,
伤害统计排名第一的队员成为【榜样】，前/后台强度提高25%。」

- 登记面锁:条目五元组 = PLANE_START 占位形(战斗中标记评估,无离散
  触发事件,对齐 _portal_placeholder_spec 先例)× WHILE_HELD × UNIT_BUFF ×
  UnitBuffRef(官方效果原文)× duties 三位全 False(零计数器/零预知/
  零姿态);pending=False(触发时点/对象规则/属性/数值全 desc 明文);
  effect_text 与 base 注册表 .effect 单一源对拍(条目经
  PLAZA_AUGMENTS 数据面表达式引官方原文,防表达式被改字面量后漂移);
  现金分支 = 已注册名无 economy → (0.0, False)(战力类不进经济模型,
  防未来误加 STRATEGY_ECONOMY 条目或通道误开);
- 绑定负锁:卡不入 STRATEGY_BINDINGS(泛用标记单体 buff,无阵营/召唤物/
  星徽点名;「伤害统计排名第一」系通用战斗统计选择非阵营语义,「榜样」
  系官方卡文词面非召唤单位注册名——kernel 命中仅敌侧词缀「榜样激励」
  comp 适配映射面,与本卡注册名异键),strategy_bindings() 返回默认空
  元组——把现状固化为设计约定,防未来误绑;
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

_CARD = '榜样的力量·银'


def test_bangyang_de_liliang_yin_unit_buff_registration_surface() -> None:
    """榜样的力量·银 登记面锁(战力类零响应族标记式单体选择卡,同形先例 =
    全队的希望/溜佩佩/溜佩佩+/团队力量·银/应援团/正能量/完美开局/效率
    员工奖/基层贡献):条目五元组逐位 + 单一源对拍 + 现金 fail-closed 0;
    构建校验(孤儿键/id 双匹配)import 期已过——本测试存活即证。标记
    选择语义(伤害统计计量口径/并列排名第一取法/榜样标记持续期)与数值
    (25% 前/后台强度)游戏侧自算,bot 零建模零观察——live「数据统计」
    面板时点(结算屏)/粒度(求和)双不符,sim BattleOutcome 无角色级伤害
    统计,repo 无可接读口。"""
    spec = STRATEGY_EFFECTS[_CARD]
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    assert spec.id == '150801'
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


def test_bangyang_de_liliang_yin_no_faction_binding() -> None:
    """绑定负锁:榜样的力量·银不入 STRATEGY_BINDINGS——泛用数值(伤害
    统计排名第一者的前/后台强度增益)不绑,登记判据直辖(同形泛用卡全队
    的希望/应援团/正能量/完美开局/效率员工奖/基层贡献同不在表;「伤害
    统计排名第一」系通用战斗统计选择非阵营语义,「榜样」系官方卡文词面
    非召唤单位注册名);strategy_bindings() 对表外卡返回默认空元组
    (fail-closed,方向分 0)。"""
    assert _CARD not in STRATEGY_BINDINGS, '绑定表零触碰(泛用数值不绑)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_bangyang_de_liliang_yin_not_in_pick_effects_closed_set() -> None:
    """封闭集负锁:榜样的力量·银不得入 PICK_INVEST_EFFECTS(本卡零获得
    时点写状态副本,入集 = 实现错误;全集逐名断言归存量闭集锁,此处只锁
    本卡键不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '零响应登记卡不入发放族封闭集(负向防线)'
