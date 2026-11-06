"""嘴硬败局修饰族 sim 链测试(镜像 src = sim/cw_sim_backend.py 的
_resolve_battle 败局 hp 腿与 streak 转移 keep_on_loss 形参;kernel 聚合
helper 注册面 = kernel/cw_investments/test_strategy_zuiying_registry.py)。

测试面依据 = 迭代设计 designs/T-181-zuiying.md §4 锁 1/锁 2/锁 5:
- 锁 1 转移纯函数:keep_on_loss 形参辖域 = 战斗类与扑满帧两败局分支,
  仅带符号正值维持(读法 B:「原来的连胜数」字面辖域 = 连胜计数,零/
  连败无连胜数可维持;desc 未写负值分支 = 判读申报制);胜局/奖励/补给
  分支形参不参与;缺省 False = 现行为逐位不变(存量测试零扰动的对账
  锁)。镜像口 streak_income_after 无 piggy 形参,keep 形参仅辖战斗类
  分支,扑满帧维持语义不在其辖域(禁在此设扑满帧断言);
- 锁 2 hp 腿:持卡败局帧 = 基础采样追加扣血(强制结算输出 −23 →
  −28,不依赖随机面);扑满败局豁免优先(hp_delta=0 零基础不产生伤害,
  「扑满不掉血」同向);胜局帧零影响;
- 锁 5 walk 收入边界:败局收入行无连胜分量(维持的是计数,不使败局获
  连胜金)+ 下一节点窗开收入按维持后连胜兑现(共享链端到端;常规链
  收入在窗开拍轮初口径,战斗位结算拍零收入回归基准)。
- 驱动形态 = 出战动作触发结算(2026-10-29 流程模型);引擎驱动助手
  import 自 sim/test_sim_backend.py(已登记超限拆分债文件,禁追加,只
  import 复用不改;先例 = 本目录 test_strategy_win_gold_sim_chain.py)。
"""
from __future__ import annotations

import pytest
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
    _backend,
    _close_shop_feed,
    _drive_env_grant_step,
    _force_settle,
    _node_advance_feed,
    _start_battle_feed,
)

from sr_od.application.currency_war.kernel.cw_economy import (
    loss_compensation_base,
    reward_base_gold,
    streak_gold,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BOSS_BRIEFING,
    SCREEN_BRIEFING,
    SCREEN_ENCOUNTER,
    SCREEN_INVEST_STRATEGY,
    SCREEN_MEGASTAR,
    SCREEN_PLANNER,
    SCREEN_PREP,
    SCREEN_SETTLE,
    SCREEN_SHOP,
    SCREEN_SUPPLY,
    SimBackend,
    streak_income_after,
    streak_signed_after,
    uninstall_backend,
)

_CARD = '嘴硬'
_PLANE_TRANSITION = '货币战争-位面过渡'
_TRANSIT_SCREENS = (SCREEN_SETTLE, _PLANE_TRANSITION, SCREEN_INVEST_STRATEGY,
                    SCREEN_SUPPLY, SCREEN_ENCOUNTER, SCREEN_BOSS_BRIEFING,
                    SCREEN_MEGASTAR, SCREEN_PLANNER, SCREEN_SHOP)
_PIGGY_ENV = '经济过热'


def _hold_card(gs) -> None:
    """持卡直置(注册状态容器直写 = 持卡事实单一源;不经 pick 链,
    test_strategy_win_gold_sim_chain 同形)。"""
    gs.write_logic(gs.active_strategies, [_CARD],
                   produced_by='test-seed', evidence='t:card', sig=_SIG)


def _prep_backend(seed: int, *, piggy: bool = False) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;先例 =
    test_strategy_win_gold_sim_chain 同名助手形)。piggy = 窗开前置
    扑满环境(窗口收尾 is_piggy_node 现读)。P1 序列现值 P1r1 = reward 位。"""
    b = _backend(seed)
    if piggy:
        b.gs.observe(b.gs.active_env, _PIGGY_ENV, sig=_SIG_OBS)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP, '前置:未达 P1r1 备战屏'
    assert b.gs.node.value.kind == 'reward', '前置:P1r1 应为奖励位(现值序列)'
    return b


def _drive_to_kind_prep(monkeypatch: pytest.MonkeyPatch, b: SimBackend,
                        *, target_kind: str) -> None:
    """自当前窗驱动到指定位面 1 节点类型的备战窗(途经战斗/奖励节点
    全胜强制穿过,中间屏走现役驱动步;test_strategy_win_gold_sim_chain
    同形副本)。"""
    gs = b.gs
    for _ in range(80):
        node = gs.node.value
        screen = b.screen_identity()
        if screen == SCREEN_PREP and node is not None \
                and node.kind == target_kind:
            return
        if screen in _TRANSIT_SCREENS:
            _drive_env_grant_step(b)
        elif screen == '货币战争-备战-开商店':
            # 备战开店形态(窗起发牌后自动弹店):关店动作单轨回备战
            _close_shop_feed(b)
        elif screen == SCREEN_PREP:
            _force_settle(monkeypatch, won=True)
            _start_battle_feed(gs)
        else:
            raise AssertionError(
                f'未预期屏 {screen!r}(target={target_kind})')
    raise AssertionError(f'驱动步数超限:未达 {target_kind} 备战窗')


# ============================================================ 锁 1:转移纯函数

def test_streak_keep_on_loss_battle_positive_only() -> None:
    """战斗类败局分支读法 B:带符号正值维持原值;零与负值照常败局
    转移(零/连败无「原来的连胜数」可维持,desc 未写负值分支 =
    判读申报制)。"""
    assert streak_signed_after(3, node_type='battle', won=False,
                               keep_on_loss=True) == 3, '正值维持'
    assert streak_signed_after(0, node_type='battle', won=False,
                               keep_on_loss=True) == -1, '零照常转负'
    assert streak_signed_after(-2, node_type='battle', won=False,
                               keep_on_loss=True) == -3, '负值照常延展'


def test_streak_keep_on_loss_piggy_and_other_branches() -> None:
    """扑满败局分支正值维持/非正值照旧清零(裁决点 4:修饰统一适用
    一切败局转移,卡面「战斗失败时」无节点类型限定);胜局/奖励/补给
    分支形参不参与照旧。"""
    assert streak_signed_after(2, node_type='reward', won=False,
                               piggy=True, keep_on_loss=True) == 2, \
        '扑满败局正值维持'
    assert streak_signed_after(0, node_type='reward', won=False,
                               piggy=True, keep_on_loss=True) == 0, \
        '扑满败局零照旧清零(等值)'
    assert streak_signed_after(-1, node_type='reward', won=False,
                               piggy=True, keep_on_loss=True) == 0, \
        '扑满败局非正值照旧清零'
    assert streak_signed_after(3, node_type='battle', won=True,
                               keep_on_loss=True) == 4, '胜局照旧 +1'
    assert streak_signed_after(3, node_type='supply', won=False,
                               keep_on_loss=True) == 3, '补给分支不动'


def test_streak_keep_default_bitwise_identity() -> None:
    """缺省 False = 现行为逐位不变(存量测试零扰动的对账锁):两纯函数
    不传形参的全代表分支与历史行为逐位一致。"""
    assert streak_signed_after(3, node_type='battle', won=False) == -1
    assert streak_signed_after(-2, node_type='battle', won=False) == -3
    assert streak_signed_after(2, node_type='battle', won=True) == 3
    assert streak_signed_after(2, node_type='reward', won=False,
                               piggy=True) == 0
    assert streak_signed_after(2, node_type='reward', won=True,
                               piggy=True) == 3
    assert streak_income_after(3, node_type='battle', won=False) == 0
    assert streak_income_after(3, node_type='battle', won=True) == 4


def test_streak_income_mirror_keep_battle_scope_only() -> None:
    """镜像口辖域(r1-S1):streak_income_after 无 piggy 形参,keep 形参
    仅辖战斗类败局分支(正值保留/零维持与清零等值);奖励节点原样返回;
    扑满帧维持语义不在本口辖域,禁在此设扑满帧断言(断言归
    streak_signed_after 面)。"""
    assert streak_income_after(3, node_type='battle', won=False,
                               keep_on_loss=True) == 3, '战斗类正值保留'
    assert streak_income_after(0, node_type='battle', won=False,
                               keep_on_loss=True) == 0, '零维持与清零等值'
    assert streak_income_after(3, node_type='reward', won=False,
                               keep_on_loss=True) == 3, '奖励分支形参不参与'


# ============================================================ 锁 2 + 锁 5:引擎链

def test_battle_loss_hp_extra_streak_kept_loss_comp_branch(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2a + 锁 5①战域 walk(1-3/1-4 连续战斗位):持卡 + 前置连胜
    直置 2(奖励位不计连胜,前置连胜以观察直置模拟上一结算帧真值)
    → 1-3 败局 = 基础采样 −23 追加 −5(三重门全开)∧ 连胜维持 2 ∧
    结算拍零收入(轮初口径回归基准)→ 1-4 窗开走败补支(被败节点补发
    基项+息,连胜分量恒 0——维持的是计数,败轮不获连胜金)。"""
    b = _prep_backend(61)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        gs.observe(gs.streak, 2, sig=_SIG_OBS)
        assert int(gs.streak.value or 0) == 2, '前置连胜直置'
        gold_at_prep = int(gs.gold.value or 0)
        hp_before = int(gs.hp.value or 0)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert int(gs.hp.value or 0) == hp_before - 23 - 5, \
            '败局额外扣血 = 基础采样 −23 + 卡面 5'
        assert int(gs.streak.value or 0) == 2, '战斗败局连胜维持'
        assert int(gs.gold.value or 0) == gold_at_prep, \
            '战斗位结算拍零收入(轮初口径,窗开已落账)'
        gold_after = int(gs.gold.value or 0)
        _node_advance_feed(gs, trigger='settle_confirm')
        if b.screen_identity() == SCREEN_SHOP:
            _close_shop_feed(b)
        assert b.screen_identity() == SCREEN_PREP, '1-4 备战窗'
        assert int(gs.gold.value or 0) == gold_after + \
            loss_compensation_base(1, 3, 'battle') + \
            min(gold_after // 10, 5), \
            '1-4 窗开走败补支(补发基项+息,无连胜分量)'
    finally:
        uninstall_backend()


def test_piggy_loss_hp_exempt_income_boundary_streak_kept(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2b + 锁 5①②(扑满域):r1 扑满胜局前置连胜 1 → r2 持卡败局 =
    豁免优先 hp 恒不动(零基础不产生伤害)∧ 收入 = 基础+息无连胜分量
    (维持不使败局获连胜金)∧ 连胜维持 1(修饰层对 T-6 基线账:不持卡
    同分支照旧清零,存量锁已登记)→ r3 窗开常规支按维持后连胜兑现
    (扑满败局不登记败补待办,下一战斗轮走常规胜轮支——共享链端到端)。"""
    b = _prep_backend(64, piggy=True)
    try:
        gs = b.gs
        _hold_card(gs)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert int(gs.streak.value or 0) == 1, '前置:r1 扑满胜局连胜 1'
        gold1 = int(gs.gold.value or 0)
        _node_advance_feed(gs, trigger='settle_confirm')
        assert b.screen_identity() == SCREEN_SHOP, '(1,2) 窗收尾自动弹店'
        _close_shop_feed(b)
        hp_before = int(gs.hp.value or 0)
        _force_settle(monkeypatch, won=False)
        _start_battle_feed(gs)
        assert int(gs.hp.value or 0) == hp_before, \
            '扑满败局豁免优先(零基础不产生伤害)'
        assert int(gs.gold.value or 0) == gold1 + reward_base_gold(1, 2) + \
            min(gold1 // 10, 5), '败局收入 = 基础+息(无连胜分量)'
        assert int(gs.streak.value or 0) == 1, '扑满败局连胜维持(持卡修饰层)'
        gold2 = int(gs.gold.value or 0)
        _node_advance_feed(gs, trigger='settle_confirm')
        # r3 窗开拍收入已落账;泊屏形态不定(投资三选一/弹店/备战),
        # 只断言金不锚定屏面。选卡面(若有)在断言之后,不入本锁面。
        assert int(gs.gold.value or 0) == gold2 + reward_base_gold(1, 3) + \
            streak_gold(1) + min(gold2 // 10, 5), \
            '下一节点窗开收入按维持后连胜兑现(常规支共享链)'
    finally:
        uninstall_backend()


def test_win_frame_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """锁 2c:持卡战斗类胜局帧零影响(三重门 not won 短路)——hp 不动、
    连胜照旧 +1。"""
    b = _prep_backend(63)
    try:
        gs = b.gs
        _hold_card(gs)
        _drive_to_kind_prep(monkeypatch, b, target_kind='battle')
        hp_before = int(gs.hp.value or 0)
        _force_settle(monkeypatch, won=True)
        _start_battle_feed(gs)
        assert int(gs.hp.value or 0) == hp_before, '胜局帧 hp 零影响'
        assert int(gs.streak.value or 0) == 1, '胜局连胜照旧 +1'
    finally:
        uninstall_backend()
