"""sim 奖励面板矿占位增量与扑满 super 变体冒烟 · 测试面(cw_sim_backend)。

设计依据 = invest-effects-calc 迭代 designs/T-20-jingji-yanzhong-guore.md
§2.1.3/§2.1.4(用户改判 2026-10-15:扑满卡面「掉落(超)多战利品」幅度
差异以 sim 面板矿占位增量承载,量级单一源 = kernel
``ENV_ORE_PANEL_BONUS``;占位非核实游戏事实,待实机采证校准)。测试面:

- 面板矿点数三档(**现算形期望**):装配单点真消费注册表——普通 =
  锚 8 / 经济过热 = 12 / 经济严重过热 = 16;增量灰矿续接面板序,与
  位面开局声明矿的续接位互不撞键;
- 后端装配 + 扑满链三条分支变体冒烟(两卡谓词同构,参数化双环境):备战帧
  金对开局种子值直断(递延锐度)/胜局结算分支一次落账 + 连胜 0→1 /
  败局基础+息 + 连胜清零 + 不掉血,super 局同样生效;
- 占位披露回归:``PIGGY_ORE_PANEL_BONUS_PLACEHOLDER`` 随局披露在册
  (先例 = ORE_PLANE_START_PENDING 直断,sim/test_sim_backend.py),
  封死「键在册但未接线 = 永不发射死常量」回归通道。

复用声明:装配/结算/推进助手 import 自 sim/test_sim_backend.py(在册
超限拆分债文件,禁追加,只 import 复用不改,设计 §2.1 落点约束);
装配环境参数化经该模块 ``_PIGGY_ENV`` 名单旋钮(monkeypatch 运行时
替换,装配函数本体零改)。
"""
from __future__ import annotations

import pytest
import test.sr_od.application.currency_war.sim.test_sim_backend as piggy_helpers
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _force_settle,
    _node_advance_feed,
    _piggy_backend,
    _reward_expect,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    REWARD_BASE_GOLD_BY_ROUND,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ORE_PANEL_BONUS,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    PIGGY_ORE_PANEL_BONUS_PLACEHOLDER,
    REWARD_ORE_PANEL_ANCHOR,
    SCREEN_PREP,
    SimBackend,
    reward_ore_panel_points,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

#: 参数化扑满环境(两卡;普通对照 = 表外环境零增量)。
_PIGGY_ENVS: tuple[str, ...] = ('经济过热', '经济严重过热')


def test_reward_ore_panel_points_count_and_continuation() -> None:
    """面板矿点数三档(现算形期望,防同义反复):期望 = 锚合计 +
    注册表增量 → 普通 8 / 经济过热 12 / 经济严重过热 16;表外环境零
    增量;增量矿灰档、x 同列顺延续接面板序;位面开局声明矿续接位
    (10*(N+1), 10) 随扩尾外移,恒不与面板点撞键(声明矿消费方传
    len(panel) 续接,联动零改码)。"""
    anchor = sum(count for _, count in REWARD_ORE_PANEL_ANCHOR)
    assert anchor == 8, '锚 8 矿(U23);锚形变更须连声明矿锁一起重锚'
    for env in ('', '轮岗', '增发货币'):
        assert len(reward_ore_panel_points(env)) == anchor, \
            f'表外环境零增量: {env!r}'
    for env in _PIGGY_ENVS:
        pts = reward_ore_panel_points(env)
        expected = anchor + ENV_ORE_PANEL_BONUS[env]
        assert len(pts) == expected, \
            f'{env}: 期望 = 锚 {anchor} + 注册表增量,现算形'
        assert all(color == '灰' for color, *_rest in pts[anchor:]), \
            '增量矿灰档(占位呈现身份)'
        assert [(x, y) for _c, x, y, _r in pts] == \
            [(10 * (i + 1), 10) for i in range(expected)], '续接面板序'
        declared_xy = (10 * (len(pts) + 1), 10)
        assert declared_xy not in [(x, y) for _c, x, y, _r in pts], \
            '声明矿续接位不与面板撞键'


@pytest.mark.parametrize('piggy_env', _PIGGY_ENVS)
def test_piggy_super_panel_and_income_legs(
        piggy_env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """后端装配单点接线 + 扑满链三条分支变体冒烟(递延/连胜例外/不掉血):
    备战帧 spheres 点数 = 锚 + 注册表增量(现算形,装配点未消费注册表
    即红);备战帧金 = 开局种子值(kernel ``seed_opening_state`` 金种子,
    T-6 验收锐度建议的直断);胜局结算分支一次落账 = 基础+息+连胜、连胜
    0→1;败局 = 基础+息、连胜清零、hp 不动。期望收入现算自统一公式
    单一源(kernel cw_economy,与既有扑满锁同式)。"""
    monkeypatch.setattr(piggy_helpers, '_PIGGY_ENV', piggy_env)
    b = _piggy_backend()
    try:
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        expected_panel = (sum(count for _, count in REWARD_ORE_PANEL_ANCHOR)
                          + ENV_ORE_PANEL_BONUS[piggy_env])
        pts = gs.spheres.value.points
        assert len(pts) == expected_panel, \
            f'{piggy_env}: 后端装配面板点数真消费注册表'
        assert [(p[1], p[2]) for p in pts[8:]] == \
            [(10 * (i + 1), 10) for i in range(8, expected_panel)], \
            '增量灰矿续接面板序'
        assert int(gs.gold.value or 0) == 3, \
            '备战帧金 = 开局种子值(递延生效,窗开不落账)'
        # 胜局分支:递延基数 3,结算分支一次落账
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        expect1 = 3 + _reward_expect(
            3, REWARD_BASE_GOLD_BY_ROUND[1], 0, won=True)
        assert int(gs.gold.value or 0) == expect1, \
            '结算分支一次落账 = 基础+息+进轮连胜'
        assert int(gs.streak.value or 0) == 1, '扑满胜局连胜 +1'
        # 败局分支:基础+息、连胜清零、不掉血
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_PREP
        hp_before = int(gs.hp.value or 0)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert int(gs.gold.value or 0) == expect1 + _reward_expect(
            expect1, REWARD_BASE_GOLD_BY_ROUND[2], 1, won=False), \
            '败局收入 = 基础+息(无连胜成分)'
        assert int(gs.streak.value or 0) == 0, '扑满败局连胜清零'
        assert int(gs.hp.value or 0) == hp_before, '扑满不掉血豁免'
    finally:
        uninstall_backend()


def test_piggy_ore_panel_bonus_disclosure_registered() -> None:
    """占位披露回归锁:PIGGY_ORE_PANEL_BONUS_PLACEHOLDER 在后端披露集
    在册(_BASE_DISCLOSURES 接线即随局披露;键在册但未接线 = 永不发射
    死常量的回归通道由此封死;先例 = ORE_PLANE_START_PENDING 直断,
    sim/test_sim_backend.py)。裸构造即断:基座披露与局进程无关。"""
    b = SimBackend(seed=1, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    assert b.disclosures.get(PIGGY_ORE_PANEL_BONUS_PLACEHOLDER) is not None, \
        '占位披露键未接线(死常量回归)'
