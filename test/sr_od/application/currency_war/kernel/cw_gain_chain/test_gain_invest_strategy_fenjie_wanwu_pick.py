"""分解万物(id 331801)效果条目1 发放链行为锁(镜像 src = kernel/cw_gain_chain.py
on_strategy_gained 效果体分支消费 cw_gain_effects.PICK_INVEST_EFFECTS
分解万物行 = 具名装备授予工厂;按被测方法拆目录规范落位——
test_gain_chain.py 超线冻结禁追加,先例 = 同目录 test_strategy_* 链锁
文件)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/T-376-fenjie-
wanwu.md(定稿)§4 锁 2/锁 4/锁 5(REVIEW-T376 §5④):
- 锁 2 效果条目1 行为:效果串恰 1 条 named_equip_grant:物质分解液(placed=True)
  (零后果链承 EQUIP_ACQUIRE_CONSEQUENCES 三键零本卡)+ gs.equips 新增
  物质分解液恰 1 件(rand=False 确定发放,gain-chain.md §5 卡文无随机词);
- 锁 4 估值 fail-closed:strategy_economy_value 恒 (0.0, False)
  (效果条目3 战力类零建模,不进经济模型);
- 锁 5 负锁:'分解万物' 不入 STRATEGY_BINDINGS(绑定域零本卡)。

效果条目2 变换腿登记形态由同目录
test_gain_invest_strategy_fenjie_wanwu_reg.py 承载(两注册面分域)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    EQUIP_ACQUIRE_CONSEQUENCES,
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_BINDINGS,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.invest_strategy import (
    strategy_economy_value,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')

_LSIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                   mode='compute')


def _make_gs_with_equip() -> GameState:
    """equips 预种非空状态容器(已观察,防未观察拒落分支)+ 空席装配。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty')] * 9,
                                   capacity=9), sig=_SIG_OBS)
    gs.observe(gs.equips, [('生命之花', 1)], sig=_SIG_OBS)
    return gs


def test_gain_invest_strategy_fenjie_wanwu_pick_grant() -> None:
    """分解万物 效果条目1 发放行为锁:on_strategy_gained → 具名工厂效果体恰发
    物质分解液×1 入栏(rand=False 确定发放——卡文「获得一个」无随机词,
    rand 两通道分野 = fields.md §3.2.15 策略卡侧具名分支);效果串恰 1 条
    named_equip_grant:物质分解液(placed=True)(零后果链承
    EQUIP_ACQUIRE_CONSEQUENCES:物质分解液 ∉ 后果表,入栏即终态零级联)。"""
    assert '物质分解液' not in EQUIP_ACQUIRE_CONSEQUENCES, '零后果链前提'
    gs = _make_gs_with_equip()
    effects = on_strategy_gained(gs, '分解万物', rand=False, sig=_LSIG)
    assert effects == ('named_equip_grant:物质分解液(placed=True)',), (
        '效果串恰 1 条(具名确定发放,placed = 入栏成败)')
    assert gs.equips.value.count('物质分解液') == 1, '入栏恰 1 件'


def test_gain_invest_strategy_fenjie_wanwu_value_and_binding_negative() -> None:
    """锁 4 估值 fail-closed + 锁 5 负锁:效果条目3 战力类零建模 → 策略侧估值
    恒 (0.0, False)(不进经济模型,invest_effects.md 战力类裁定);
    '分解万物' 不入 STRATEGY_BINDINGS(绑定型随机角色授予域零本卡)。"""
    gs = _make_gs_with_equip()
    assert strategy_economy_value('分解万物', gs) == (0.0, False), (
        '估值 fail-closed(战力类零建模)')
    assert '分解万物' not in STRATEGY_BINDINGS, '绑定域零本卡'
