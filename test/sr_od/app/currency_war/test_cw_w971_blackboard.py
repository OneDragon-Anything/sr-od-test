# -*- coding: utf-8 -*-
"""W971 §2 黑板模式 P2 落地测试:决策接口签名改造 + 观察写路径 + match 前移。

验证口径(任务书④):同 session 快照喂新旧两接口,决策序列逐字段全等。
- 商店屏:旧 ``decide_prep(state, session, config)`` vs 新
  ``decide_shop_screen(session, config)``(先写 shop_state_frame);
  升级意图类型差(LevelUpShop vs LevelUp)按归一化比较(子类 is-a 基类,
  字段逐项同值)。
- 备战屏:旧 ``decide_prep_action(obs, session, config)`` vs 新
  ``decide_prep_screen(session, config)``(先写 prep_obs_frame)。
全部离线纯逻辑,零 IO。
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_prep_actions import (
    PrepObservation,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    LevelUpShop,
    ShopCard,
)


def _make_state() -> GameState:
    """探针态:中局常态(金足/店有目标件/bench 有件)——决策必有产出。"""
    s = GameState()
    s.plane, s.round_num, s.level, s.gold, s.hp = 1, 5, 5, 60, 80
    s.board = {'仙舟': 2, '持续伤害': 1}
    s.deployed = [BenchChar(slot=0, char_id='藿藿', faction='仙舟'),
                  BenchChar(slot=1, char_id='爻光', faction='仙舟')]
    s.bench = [BenchChar(slot=0, char_id='丹恒·饮月', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟'),
               None, None, None, None, None, None, None]   # ADR-0316 pad
    s.shop = [ShopCard(x=1, faction='仙舟', name='丹恒·饮月', cost=2),
              ShopCard(x=2, faction='护盾', name='三月七', cost=1)]
    return s


def _fresh(strategy) -> SimpleNamespace:
    """同源 session(on_match_start 后;两臂输入完全一致的对拍前提)。"""
    sess = strategy.create_session(None)
    strategy.on_match_start(_make_state(), sess, None)
    return sess


def _norm_seq(actions: list) -> list[tuple[str, dict]]:
    """动作序列归一化:类型名(LevelUpShop≡LevelUp)+ 字段 dict(对拍口径)。"""
    out = []
    for a in actions:
        name = type(a).__name__
        if name == 'LevelUpShop':
            name = 'LevelUp'
        out.append((name, dict(dataclasses.asdict(a))))
    return out


# ===== 商店屏:新旧入口决策对拍 =====


def test_shop_screen_probe_smoke() -> None:
    """商店屏唯一入口冒烟(退役批:decide_prep 兼容 shim 已删,对拍锁随删)。

    探针态(金足/店有目标件)经黑板入口应产出采纳动作;等价性保障改由
    结构承载(单一入口 = decide_shop_screen,无第二实现可漂移)。
    """
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    state = _make_state()
    sess = _fresh(strat)
    sess.shop_state_frame = state
    acts = strat.decide_shop_screen(sess, None)
    assert len(acts) > 0, '探针态(金足/店有目标件)应有采纳动作'

def test_shop_screen_emits_levelup_shop() -> None:
    """新入口升级意图 = LevelUpShop(is-a LevelUp);旧入口仍产基类 LevelUp。

    执行器/buy_cards 波循环按 isinstance(a, LevelUp) 消费 → 子类零改动兼容;
    本锁钉住「拆分只换型不改行为」的出口映射语义。
    """
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    sess = _fresh(strat)
    sess.shop_state_frame = _make_state()
    # 出口映射单点验证(探针态不保证出 LevelUp,用决策核桩直验映射):
    strat._decide_shop_plan = lambda state, session, config: [  # noqa: SLF001
        LevelUp(cost=4, auth_basis='dp'), BuyCard(
            card=ShopCard(x=1, faction='仙舟', name='丹恒·饮月', cost=2))]
    acts = strat.decide_shop_screen(sess, None)
    assert [type(a) for a in acts] == [LevelUpShop, BuyCard]
    assert acts[0].cost == 4 and acts[0].auth_basis == 'dp'
    assert isinstance(acts[0], LevelUp)   # 执行器兼容形态


def test_shop_screen_missing_frame_raises() -> None:
    """黑板契约:观察帧缺失 = 观察层失约 → 抛错,禁静默按空态决策。"""
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    sess = _fresh(strat)
    assert sess.shop_state_frame is None
    with pytest.raises(ValueError, match='shop_state_frame'):
        strat.decide_shop_screen(sess, None)


# ===== 备战屏:新旧入口决策对拍 =====


def _make_obs() -> PrepObservation:
    """探针观察帧:有球有空席 → 规则 3 ClickSpheres(确定分支)。"""
    from one_dragon.base.geometry.point import Point
    obs = PrepObservation()
    obs.spheres = [('blue', Point(500, 500), 20), ('blue', Point(700, 500), 20)]
    obs.free_bench_slots = 3
    obs.shop_open = False
    return obs


def test_prep_screen_par_old_vs_new() -> None:
    """同 obs 帧:旧 decide_prep_action vs 新 decide_prep_screen 决策全等。

    旧入口 = 薄委托(写 prep_obs_frame → 新入口),等价由构造保证;
    本锁防未来两条路径漂移。
    """
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    obs = _make_obs()
    strat_old = DecisionV2Strategy()
    strat_new = DecisionV2Strategy()
    sess_old = _fresh(strat_old)
    sess_new = _fresh(strat_new)
    old_act = strat_old.decide_prep_action(obs, sess_old, None)
    sess_new.prep_obs_frame = obs
    new_act = strat_new.decide_prep_screen(sess_new, None)
    assert type(old_act) is type(new_act)
    assert dataclasses.asdict(old_act) == dataclasses.asdict(new_act)
    assert type(old_act).__name__ == 'ClickSpheres'


def test_prep_screen_missing_frame_raises() -> None:
    """黑板契约:prep_obs_frame 缺失 → 抛错(同商店屏)。"""
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    sess = _fresh(strat)
    with pytest.raises(ValueError, match='prep_obs_frame'):
        strat.decide_prep_screen(sess, None)


def test_prep_action_delegates_via_frame() -> None:
    """兼容薄委托:旧入口把 obs 写进 session.prep_obs_frame(写路径收编形态)。"""
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy()
    sess = _fresh(strat)
    obs = _make_obs()
    strat.decide_prep_action(obs, sess, None)
    assert sess.prep_obs_frame is obs


# ===== match 建立前移(W971 §2.1)=====


def test_establish_new_match_and_idempotent(monkeypatch) -> None:
    """入口建立:新建 → True + 职级拷入;已存在 → False 幂等(保续跑语义)。"""
    from sr_od.application.currency_war.decision.cw_strategy_manager import (
        establish_new_match,
    )
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )

    ctx = SimpleNamespace(
        cw_match=None,
        currency_war_strategy_plugin_dirs=[],
        cw_selected_difficulty='A5',
    )
    monkeypatch.setattr(
        'sr_od.application.currency_war.decision.cw_strategy_manager.'
        'StrategyManager.instantiate',
        lambda self, strategy_id: DecisionV2Strategy())
    assert establish_new_match(ctx, SimpleNamespace(
        strategy_id='decision_v2', strategy_seed=None)) is True
    assert ctx.cw_match is not None
    assert ctx.cw_match.session.selected_difficulty == 'A5'
    assert establish_new_match(ctx, SimpleNamespace(
        strategy_id='decision_v2', strategy_seed=None)) is False   # 幂等


def test_absorb_selected_difficulty_only_after_mailbox_retirement() -> None:
    """run loop 入口中转(P3 改写):ctx 信箱退役(01-opening §1)——吸收段
    只剩职级难度;简报三字段唯一写点 = BriefingOp 直写 session,不再经 ctx。"""
    from sr_od.application.currency_war.decision.cw_strategy import (
        StrategySession,
    )
    from sr_od.application.currency_war.operations.cw_loop import (
        CwLoop,
    )
    rl = CwLoop.__new__(CwLoop)
    rl.ctx = SimpleNamespace(
        cw_briefing_affixes=['酸性浓缩'],
        cw_selected_difficulty='A8',
        cw_enemy_difficulty=55,
        cw_briefing_bosses=['虫王·断壳'],
    )
    sess = StrategySession()
    rl._absorb_selected_difficulty(sess)
    # 只吸收职级难度(3.5.1 接线);简报字段不被吸收(信箱退役口径)
    assert sess.selected_difficulty == 'A8'
    assert rl.ctx.cw_selected_difficulty is None
    assert sess.briefing_affixes == []
    assert sess.enemy_difficulty is None
    assert sess.briefing_bosses == []
    assert rl.ctx.cw_briefing_affixes == ['酸性浓缩']
    assert rl.ctx.cw_briefing_bosses == ['虫王·断壳']
