"""黄晶矿工(id 302101)立刻效果条目效果体锁(镜像 src = cw_gain_effects.py
_make_ore_open_pick_effect + PICK_INVEST_EFFECTS 工厂条目;按被测模块拆
目录规范落新位,先例 = 同级 cw_investments/cw_gain_chain 拆目录族)。

测试面依据 = 原稿锁面
原稿锁面(定稿,原稿评审锁 无需用户决定 7/7)§4 锁 3:
- 直构持卡 pick → spheres +1 '金' 点 + ore_rewards +1(获得链分派契约
  消费,注册表键集闭集内注册即生效);
- level 缺读 → 授予矿无附着不炸(矿仍入状态副本,点击走既有缺项兜底);
- 未收录卡安静不写 = 既有双锁语义正向辖入(「不登记安静」双锁,零新增
  断言,本文件不重复)。

状态副本写单源说明: spheres/ore_rewards 写经 cw_gain_chain._grant_ores_to_world
(触发效果条目+立刻效果条目同一授予写函数),其撞键/续接/附着语义由
cw_gain_chain/test_check_strategy_ore_open_effects.py 撞键负例锁承载,
本文件只锁获得链分派接入调用与本效果条目特有语义(金档固定/分派 rng 消费)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.kernel.cw_gain_chain import (
    on_strategy_gained,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
)

_SIG = ChannelSig(family='logic_action', actor='CwActionPickInvestOp',
                  mode='compute')
_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')
_LSIG = ChannelSig(family='logic_action', actor='test-seed', mode='compute')

_CARD = '黄晶矿工'


def _make_gs(*, level: int | None = 3) -> GameState:
    """直构状态容器(持卡由 on_strategy_gained 前置写入;gold 效果条目不涉——本卡
    无经济数值,STRATEGY_ECONOMY 零行)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if level is not None:
        gs.observe(gs.level, level, sig=_OBS)
    return gs


def test_pick_grants_gold_ore_with_attachment() -> None:
    """立刻效果条目授予锁(T-316 设计 §4 锁 3):持卡 pick → spheres +1 '金'
    点(合成形基准 0 起专用带 (10,10))+ ore_rewards +1 附着。"""
    gs = _make_gs()
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', sig=_LSIG)
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_SIG,
                                 rng=random.Random(7))
    assert any(e.startswith('strategy_ore_pick_grant#') for e in effects), \
        f'效果串登记前缀: {effects}'
    pts = gs.spheres.value.points if gs.spheres.value else ()
    assert ('金', 10, 10, 10) in pts, f'金矿授予点: {pts}'
    assert len(pts) == 1, f'spheres +1: {pts}'
    attach = gs.ore_rewards.value or {}
    assert '10,10' in attach, f'附着键已生成: {attach.keys()}'


def test_pick_level_none_grants_without_attachment() -> None:
    """level 缺读不炸锁:授予照常入状态副本,ore_rewards 零写(既有缺项兜底
    路径承接,禁炸)。"""
    gs = _make_gs(level=None)
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', sig=_LSIG)
    effects = on_strategy_gained(gs, _CARD, rand=False, sig=_SIG,
                                 rng=random.Random(7))
    assert effects, f'效果串照返: {effects}'
    pts = gs.spheres.value.points if gs.spheres.value else ()
    assert ('金', 10, 10, 10) in pts, '金矿授予点(无附着形态)'
    assert gs.ore_rewards.value is None, 'ore_rewards 零写'


def test_pick_consumes_dispatch_rng_via_report_injection() -> None:
    """分派 rng 流键锁(T-316 设计 §2.5 rng 口径):矿内容采样必耗随机
    (roll_ore_reward),流键 = pick_invest_strategy 既有注入零新流键——
    直驱上报入口(rng=None → 上报函数经注入槽以 'pick_invest_strategy'
    解析,恰一次;新立流键/链内自掷回归形态均红灯)。"""
    from sr_od.application.currency_war.kernel.cw_action_report import (
        report_action_pick_invest_strategy_param,
        set_action_rng_provider,
    )
    from sr_od.application.currency_war.kernel.cw_vocab import (
        CwActionPickInvestStrategyParam,
    )
    calls: list[str] = []

    def counting_provider(tool: str) -> random.Random:
        calls.append(tool)
        return random.Random(11)

    set_action_rng_provider(counting_provider)
    try:
        gs = _make_gs()
        out = report_action_pick_invest_strategy_param(
            gs, CwActionPickInvestStrategyParam(idx=0, norm_name=_CARD),
            _LSIG)
        assert out.applied, f'pick 受理: {out.reason}'
        assert calls == ['pick_invest_strategy'], \
            f'分派流键既有注入恰一次零新流键: {calls}'
        pts = gs.spheres.value.points if gs.spheres.value else ()
        assert ('金', 10, 10, 10) in pts, '授予照常(注入 rng 消费面)'
    finally:
        set_action_rng_provider(None)
