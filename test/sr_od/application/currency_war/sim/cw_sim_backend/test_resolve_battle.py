"""sim 扑满结算分支利息接线测试(镜像 src = sim/cw_sim_backend.py 的
_resolve_battle 扑满收入落账段;常规轮首接线测试 =
本目录 test_apply_round_start_income.py,按被测方法拆目录规范落位)。

测试面依据 = 迭代 T-27 公司契约利息累计触发设计(v2.3 定稿)§2.4 条 2 + §4.5:
- 扑满节点收入递延(T-6 现役)语义下的利息入账:窗口开只冻快照
  **零计数**,结算分支一次性入账 = 递延 row 的息分量(**窗口开金口径**,
  非结算刻现值——窗口内金波动不影响);
- 胜局/败局同构(败局 = 基础+息,无连胜成分,息分量同链)。
  扑满域 = 扑满环境的奖励节点(is_piggy_node);途经非扑满节点窗开
  即收属现役口径,不辖断言。

追加面 = T-33 英雄登场设计(.debug/progress/2026-09-23-invest-effects-
calc/designs/T-33-yingxiong-dengchang.md)§2.4 数据面 + §4 锁 8(sim
半边):结算分支补写环帧(killed = won 语义同口 / hp_after = apply 后
gs.hp 现值;与 live 同一 ring 读口,sim 节点 kind → 结算行词表)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改;先例 = 本目录
test_reward_ore_panel.py)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _backend,
    _close_shop_feed,
    _drive_step,
    _force_settle,
    _node_advance_feed,
    _piggy_backend,
    _start_battle_feed,
)

from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    is_piggy_node,
    uninstall_backend,
)

_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_SHOP)


def _drive_to_interest_band_piggy_window(
        monkeypatch: pytest.MonkeyPatch, b: SimBackend, min_gold: int = 20
) -> tuple[int, int]:
    """自当前扑满窗起逐扑满窗推进至窗口开金 ≥ ``min_gold``(停在窗,
    未结算);返回 (窗口开金, 到窗息账)。每个途经扑满窗:结算分支一次
    入账 = 窗口开金口径息(逐窗对账);途经非扑满节点(战斗类全胜强制/
    补给·遭遇·首领走真写端)窗开即收属现役口径,不辖断言。
    2026-10-29 流程模型对齐:节点窗收尾/节点弹窗关闭回备战即自动弹店
    (商店档),关店回备战后才是可操作备战帧。"""
    gs = b.gs
    for _ in range(16):
        if b.screen_identity() == SCREEN_SHOP:
            _close_shop_feed(b)   # 窗收尾自动弹店 → 关店回备战
        assert b.screen_identity() == SCREEN_PREP and is_piggy_node(gs), \
            '应停在扑满节点备战窗'
        counter_at_window = gs.effects.interest_earned
        gold_at_window = int(gs.gold.value or 0)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == \
            counter_at_window + min(gold_at_window // 10, 5), \
            '结算分支一次入账 = 窗口开金口径息(递延生效)'
        reached = False
        for _ in range(48):
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
        assert reached, '48 步未遇扑满窗(节点序列漂移?)'
        if int(gs.gold.value or 0) >= min_gold:
            return int(gs.gold.value or 0), gs.effects.interest_earned
    raise AssertionError('16 窗未达息档扑满窗(经济序列漂移?)')


def test_piggy_settle_leg_interest_accounting(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满结算分支利息入账(T-27 设计 §4.5):窗口开零计数(递延生效,
    逐扑满窗对账);结算分支恰一次入账 = 窗口开快照金的息(现算 =
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
            '扑满窗开零计数(递延生效,息随结算分支入账)'
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == counter_at_window + \
            min(gold_at_window // 10, 5), '结算分支一次入账 = 窗口开金口径息'
    finally:
        uninstall_backend()


def test_piggy_loss_leg_interest_same_chain(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """败局结算分支同构(T-27 设计 §4.5「胜局同构」半边):败局收入 =
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
            min(gold_at_window // 10, 5), '败局分支息同链(窗口开金口径)'
        assert int(gs.streak.value or 0) == 0, '连胜清零(现役回归锚)'
    finally:
        uninstall_backend()


# ============================================================ 结算环帧补写
# (T-33 英雄登场设计 §2.4 数据面 + §4 锁 8 sim 半边:结算分支补写环帧,
# 与 live 同一 ring 读口;killed = won / hp_after = apply 后 gs.hp。)

def test_resolve_battle_writes_ring_frames(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """结算分支补写环帧(T-33 设计 §4 锁 8 sim 半边):战斗类节点结算
    恰入一环帧——胜局 killed=True、hp_after = apply 后 hp 现值(恒胜
    零扣血 = 上一帧值);败局 killed=False、hp_after = 扣血后现值;
    node_type 走 sim kind → 结算行词表映射(奖励帧 '奖励'/战斗帧
    '普通战斗';P1 序列 1-1/1-2 = 奖励、1-3 = 战斗)。"""
    b = _backend(7)
    try:
        b._handle_click_source('货币战争-简报', '按钮-下一步')
        b._maybe_finish_wait()
        gs = b.gs
        # 1-1 奖励节点:恒胜白拿 → 环帧 1(killed=True)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert len(gs.settlement_ring) == 1, '恰一环帧'
        frame1 = gs.settlement_ring.last_row()
        assert (frame1.plane, frame1.round_num, frame1.node_type) == \
            (1, 1, '奖励'), 'sim kind → 结算行词表'
        assert frame1.killed is True, 'killed = won(语义同口)'
        assert frame1.hp_after == int(gs.hp.value or 0), \
            'hp_after = apply 后 gs.hp 现值'
        _node_advance_feed(gs, trigger='settle_confirm')
        # 1-2 奖励节点:强制败局被恒胜白拿改写(won=True)→ 环帧 2;
        # settle_confirm 推进至 1-3
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert len(gs.settlement_ring) == 2, '每战斗结算恰一帧'
        frame2 = gs.settlement_ring.last_row()
        assert (frame2.plane, frame2.round_num, frame2.node_type) == \
            (1, 2, '奖励'), '奖励节点恒胜白拿(强制败局被改写)'
        assert frame2.killed is True, '奖励帧恒胜 killed=True'
        _node_advance_feed(gs, trigger='settle_confirm')
        assert (gs.node.value.plane, gs.node.value.round_num) == (1, 3), \
            '到 1-3 战斗节点(P1 序列 reward/reward/battle)'
        # 1-3 战斗节点:真败局 → 环帧 3(killed=False,掉血)
        _start_battle_feed(gs)
        assert len(gs.settlement_ring) == 3, '每战斗结算恰一帧'
        frame3 = gs.settlement_ring.last_row()
        assert (frame3.plane, frame3.round_num, frame3.node_type) == \
            (1, 3, '普通战斗')
        assert frame3.killed is False, '败局帧 killed=False'
        assert frame3.hp_after == int(gs.hp.value or 0), \
            '败局 hp_after = 扣血后现值'
        assert frame3.hp_after < frame2.hp_after, '掉血入帧(差分基准数据)'
    finally:
        uninstall_backend()


# ============================================================ 开源节流扑满递延(floor 快照随行)

def test_piggy_floor_snapshot_deferred_topup(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """扑满递延快照 floor 元(T-295 设计 §2.3-3;锁 5):持卡局扑满窗开,
    tick 捕获载体在窗开消费入快照(扩元第 4 位,载体即清);结算腿息分量
    顶满至 resolved 帽且利息累计账计顶满值(record_interest_earned 消费
    row.interest 同源,T-27 计数源随计——公司契约下游联动申报面,方向与
    实机一致)。floor 评估时点 = 进节点时点(tick 捕获),非结算刻——结算
    刻重评估会读扑满节点自身的花费,时点漂移禁,快照随行承担。r1 窗开在
    持卡前(快照无 floor),断言自 r2 同扑满窗起算;窗口金压到顶满可观察
    区(<90,自然息 < 帽 9 显影)。"""
    from types import SimpleNamespace

    from sr_od.application.currency_war.kernel.cw_effect_inventory import (
        CounterKey,
    )
    from sr_od.application.currency_war.kernel.cw_gain_chain import (
        gain_invest_strategy,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        STRATEGY_EFFECTS,
    )

    b = _piggy_backend()
    try:
        gs = b.gs
        assert b.screen_identity() == SCREEN_PREP
        assert is_piggy_node(gs), '前置:r1 = 扑满节点(经济过热奖励节点)'
        # 持卡缝:kernel 获得链入口直接喂卡(①名单 + ②条目登记;选卡
        # 上报形态先例 = test_strategy_pick_gudinglicai._pick 的
        # session=SimpleNamespace 形)。
        out = gain_invest_strategy(gs, SimpleNamespace(), '开源节流',
                                   rand=False, sig=_SIG)
        assert out.placed
        gs.write_logic(gs.gold, 25, produced_by='Test', evidence='t:gold',
                       sig=_SIG)
        # r1 结算推进(窗开在持卡前,息自然值,不作精确断言)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        # 推进至 r2 同扑满窗:tick 捕获(prev=False,无花费)→ 载体 = 9
        # → 窗开消费入快照(载体即清)。
        _node_advance_feed(gs, trigger='settle_confirm')
        assert is_piggy_node(gs), '前置:r2 同为扑满奖励节点'
        gold_at_window = int(gs.gold.value or 0)
        assert gold_at_window < 90, '前置:窗口金在顶满可观察区'
        counter_at_window = gs.effects.interest_earned
        assert gs.effects.counter(STRATEGY_EFFECTS['开源节流'].id,
                                  CounterKey.INTEREST_TOPUP) == 0, \
            '载体窗开消费清零(入快照递延)'
        # r2 结算:息分量顶满 9(自然 = gold_at_window//10 < 9 显影);
        # 利息累计账计顶满值(计数 = row.interest 同源)。
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert gs.effects.interest_earned == counter_at_window + 9, \
            (f'结算腿息分量顶满至 resolved 帽: '
             f'{counter_at_window} -> {gs.effects.interest_earned}')
    finally:
        uninstall_backend()
