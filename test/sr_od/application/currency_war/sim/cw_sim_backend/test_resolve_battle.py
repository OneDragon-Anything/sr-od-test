"""sim 扑满结算腿利息接线测试(镜像 src = sim/cw_sim_backend.py 的
_resolve_battle 扑满收入落账段;常规轮首接线测试 =
本目录 test_apply_round_start_income.py,按被测方法拆目录规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.4 条 2 + §4.5:
- 扑满节点收入递延(T-6 现役)语义下的利息入账:窗口开只冻快照
  **零计数**,结算腿一次性入账 = 递延 row 的息分量(**窗口开金口径**,
  非结算刻现值——窗口内金波动不影响);
- 胜局/败局同构(败局 = 基础+息,无连胜成分,息分量同链)。
  扑满域 = 扑满环境的奖励节点(is_piggy_node);途经非扑满节点窗开
  即收属现役口径,不辖断言。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(在册超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_reward_ore_panel.py)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _drive_step,
    _force_settle,
    _piggy_backend,
    _start_battle_feed,
)

from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SUPPLY,
    SimBackend,
    is_piggy_node,
    uninstall_backend,
)

_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING)


def _drive_to_interest_band_piggy_window(
        monkeypatch: pytest.MonkeyPatch, b: SimBackend, min_gold: int = 20
) -> tuple[int, int]:
    """自当前扑满窗起逐扑满窗推进至窗口开金 ≥ ``min_gold``(停在窗,
    未结算);返回 (窗口开金, 到窗息账)。每个途经扑满窗:结算腿一次
    入账 = 窗口开金口径息(逐窗对账);途经非扑满节点(战斗类全胜强制/
    补给·遭遇·首领走真写端)窗开即收属现役口径,不辖断言。"""
    gs = b.gs
    for _ in range(16):
        assert b.screen_identity() == SCREEN_PREP and is_piggy_node(gs), \
            '应停在扑满节点备战窗'
        counter_at_window = gs.effects.interest_earned
        gold_at_window = int(gs.gold.value or 0)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == \
            counter_at_window + min(gold_at_window // 10, 5), \
            '结算腿一次入账 = 窗口开金口径息(递延生效)'
        reached = False
        for _ in range(16):
            screen = b.screen_identity()
            if screen == SCREEN_PREP:
                if is_piggy_node(gs):
                    reached = True
                    break
                # 非扑满战斗节点:全胜强制穿过(防随机败局死局)
                _force_settle(monkeypatch, won=True)
                _start_battle_feed(gs)
                continue
            if screen in _TRANSIT_SCREENS:
                _drive_step(b, 7)   # 中间屏(含补给/遭遇/首领窗)真写端消费
                continue
            raise AssertionError(f'推进途遇未预期屏 {screen}')
        assert reached, '16 步未遇扑满窗(节点序列漂移?)'
        if int(gs.gold.value or 0) >= min_gold:
            return int(gs.gold.value or 0), gs.effects.interest_earned
    raise AssertionError('16 窗未达息档扑满窗(经济序列漂移?)')


def test_piggy_settle_leg_interest_accounting(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满结算腿利息入账(T-27 设计 §4.5):窗口开零计数(递延生效,
    逐扑满窗对账);结算腿恰一次入账 = 窗口开快照金的息(现算 =
    min(窗口金//10, 5),期望自统一公式单一源);推进至息档非平凡窗
    (窗口金 ≥20 → 息 ≥2)。"""
    b = _piggy_backend()
    try:
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        assert is_piggy_node(gs), 'r1 = 扑满节点(经济过热奖励节点)'
        assert gs.effects.interest_earned == 0, '开局窗零基线'
        gold_at_window, counter_at_window = \
            _drive_to_interest_band_piggy_window(monkeypatch, b)
        assert gold_at_window >= 20, '息档非平凡(断言退化面)'
        assert gs.effects.interest_earned == counter_at_window, \
            '扑满窗开零计数(递延生效,息随结算腿入账)'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == counter_at_window + \
            min(gold_at_window // 10, 5), '结算腿一次入账 = 窗口开金口径息'
    finally:
        uninstall_backend()


def test_piggy_loss_leg_interest_same_chain(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """败局结算腿同构(T-27 设计 §4.5「胜局同构」半边):败局收入 =
    基础+息(无连胜成分),息分量仍按窗口开快照基数入账;连胜清零
    (T-6/M15 现役,回归锚)。"""
    b = _piggy_backend()
    try:
        gs = b.gs
        gold_at_window, counter_at_window = \
            _drive_to_interest_band_piggy_window(monkeypatch, b)
        streak_before = int(gs.streak.value or 0)
        assert streak_before > 0, '前置胜局连胜在账(回归锚前置态)'
        assert gs.effects.interest_earned == counter_at_window, \
            '扑满窗开零计数(递延生效)'
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == counter_at_window + \
            min(gold_at_window // 10, 5), '败局腿息同链(窗口开金口径)'
        assert int(gs.streak.value or 0) == 0, '连胜清零(现役回归锚)'
    finally:
        uninstall_backend()
