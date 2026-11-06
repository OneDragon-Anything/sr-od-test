"""星变注册面测试(cw_investments 分目录镜像;战力类零响应族
第 15 条,先例 = 同目录 test_strategy_xingji_yazhi_registry.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-180-xingbian.md
(定稿)§4 锁 1/锁 3/锁 4 + 用户裁定书 PENDING-DECISIONS.md T-180 节
(2026-11-01 用户决定:变形持续性 = A 临时 + 随机目标选卡默认不选)。
卡面官方原文:「战斗开始时，使一个随机1费角色变为3星。」

- 登记面锁:条目五元组 = PLANE_START 占位形(无离散触发事件,对齐
  _portal_placeholder_spec 环境源先例)× WHILE_HELD × UNIT_BUFF ×
  UnitBuffRef(官方效果原文)× duties 三位全 False(零计数器/零预知/
  零姿态);pending=False(变形持续性经用户裁定定为临时——仅当次战斗内
  生效,战斗结束复原,板面零净变化,裁定已定论非二义冻结,条目 notes 记
  裁定;变形世界写端未建模,临时性仅申报);effect_text 与 base 注册表
  .effect 单一源对拍(条目经 PLAZA_AUGMENTS 数据面表达式引官方原文,防
  表达式被改字面量后漂移);现金分支 = 已注册名无 economy → (0.0, False)
  (战力类不进经济模型,防未来误加 STRATEGY_ECONOMY 条目或通道误开);
- 策略默认不选承载锁(本卡特有):变形随机改写羁绊构成,破坏策略预判,
  随机目标效果不入具名打分(「随机发放不可具名,不入具名打分,恒 off」
  已登记先例口径 = invest_effects.md 人才引进条)——选卡具名承载四面全不在
  册(STRATEGY_ECONOMY 现金 / STRATEGY_GRANTS 赠卡 / STANCE_SCORE 立场 /
  STRATEGY_BINDINGS 方向),五组件恒 0 即恒 off;把缺席固化为设计约定,
  防未来误入具名打分表;
- 封闭集负锁:卡不入 PICK_INVEST_EFFECTS(无获得时点世界写入,零响应
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
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    STRATEGY_GRANTS,
    strategy_bindings,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.invest_strategy import (
    STANCE_SCORE,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.strategy_economy import (
    strategy_economy_value,
)

_CARD = '星变'


def test_xingbian_unit_buff_registration_surface() -> None:
    """星变 登记面锁(战力类零响应族第 15 条,族内首张战斗变形卡):
    条目五元组逐位 + 单一源对拍 + 现金 fail-closed 0;构建校验(孤儿键/
    id 双匹配)import 期已过——本测试存活即证。触发拍(战斗开始时)/对象
    选取(随机1费角色)/变形数值游戏侧自算,bot 零建模零观察;变形持续性
    经用户裁定(2026-11-01)定为临时,板面零净变化。"""
    spec = STRATEGY_EFFECTS[_CARD]
    cw_investments._validate_strategy_effects()   # 构建校验复跑不炸
    assert spec.id == '201601'
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
    assert spec.pending is False, \
        '变形持续性经用户裁定定为临时(定论非二义冻结,notes 记裁定)'
    assert spec.duration_nodes == 0 and spec.duration_uses == 0, \
        'WHILE_HELD 无余期计数器(_seed_progress 双 None)'
    gs = game_state_of(SimpleNamespace())
    assert strategy_economy_value(_CARD, gs) == (0.0, False), \
        '已注册名无 economy → 现金 fail-closed 0(战力类不进经济模型)'


def test_xingbian_strategy_valuation_off_by_default() -> None:
    """策略默认不选承载锁(本卡特有):变形随机改写羁绊构成破坏策略预判,
    随机目标效果不入具名打分(「随机发放不可具名,不入具名打分,恒 off」
    已登记先例口径)——选卡估值具名承载四面全未登记,五组件恒 0 即恒 off,
    策略默认实现自然避开本卡(仅全零帧平分裁决可能选中,该形态不属具名
    打分承载);把缺席固化为设计约定,防未来误入任一具名表。"""
    assert _CARD not in STRATEGY_ECONOMY, '不入现金打分表(随机目标不入具名打分)'
    assert _CARD not in STRATEGY_GRANTS, '不入赠卡发放估值表'
    assert _CARD not in STANCE_SCORE, '不入立场分表'
    assert _CARD not in STRATEGY_BINDINGS, '不入阵营绑定表(方向分零承载)'
    assert strategy_bindings(INVESTMENT_STRATEGIES[_CARD]) \
        == (frozenset(), frozenset()), '表外默认空绑定(fail-closed)'


def test_xingbian_not_in_pick_effects_closed_set() -> None:
    """封闭集负锁:星变不得入 PICK_INVEST_EFFECTS(本卡零获得时点
    世界写入,入集 = 实现错误;全集逐名断言归存量闭集锁,此处只锁
    本卡键不在集)。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        PICK_INVEST_EFFECTS,
    )
    assert _CARD not in PICK_INVEST_EFFECTS, \
        '零响应登记卡不入发放族封闭集(负向防线)'
