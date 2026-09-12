"""test_cw_strategy_helpers 主题锁——planner/strategy/blackboard 决策辅助代表锚。

覆盖面(四类承重件):
- 入口 smoke:黑板契约 abstract 面全集(冷建 1 + 分画面决策入口 11);
- fail-closed 代表:商店屏观察帧缺失 = 观察层失约 → 抛错,禁静默按空态决策;
- 决策真值代表锚:planner 三层档位定序(升费档 > 弱化档 > 装备档 + key_equip
  域内优先)/ 结算拆两半观察半(hp 高置信才存,低置信不覆盖可靠值)/
  升星合并完成买入(第三张 affordable 必买,g_20260904_054904 复盘候选)。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_planner_decision.py(planner 段,ADR-0524 档位语义);
- test_cw_strategy.py(结算拆两半观察半,ADR-0583 §2.5/D-94);
- test_cw_blackboard.py(黑板缺帧契约 + ADR-0583 契约形状 L6);
- test_cw_supply_merge_crisis.py(iter_7f 候选②升星合并完成买入 M2b)。
其余历史锁已退役(git 可复活)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_board_state import (
    board_state_bridge,
)
from sr_od.application.currency_war.kernel.cw_comps import (
    COMP_LIBRARY,
    get_comp,
)
from sr_od.application.currency_war.kernel.cw_events import (
    PlannerOption,
    decide_planner,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CwStrategy,
    StrategySession,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)
from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
    MandateV1Live,
)


def _cfg(**overrides) -> SimpleNamespace:
    """mock CurrencyWarConfig(纯属性,策略钩子用 getattr 读)。"""
    base = {
        "faction_priority": ["贝洛伯格", "仙舟", "巡海游侠"],
        "character_priority": ["阿格莱雅"],
        "character_build_around": [],
        "strategy_id": "mandate_v1",
        "strategy_seed": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fresh(strategy) -> SimpleNamespace:
    """同源 session(create_session 唯一冷建口,ADR-0583;两臂输入完全一致的对拍前提)。"""
    return strategy.create_session(None)


# ==================== planner 段(自 test_cw_planner_decision.py 迁入) ====================

def test_planner_strategy_tier_order_and_key_equip():
    """三层档位定序锁(ADR-0524,16 号稿 §1.7):升费档 > 弱化档 > 装备档;
    key_equip +15 = 装备域内命中优先键(域内排前,不跨域压弱化档);
    银狼不在场降档(40)< 弱化档的层间关系即「降档」语义本体。"""
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    # W6 波3:decide_planner 切容器签名,工作帧经桥装箱(单帧三连调共享
    # 一次装箱;bench 空 = 未观察 = 在场信息缺失,不降权语义不变)。
    st = board_state_bridge(GameState(hp=60))
    # 升费档 > 弱化档(无银狼线;bench 空 = 在场信息缺失 → 不降权,保守)
    opts = [PlannerOption(idx=0, text='使后续节点【弱化】,降低敌人属性。'),
            PlannerOption(idx=1, text='提升费用至4费,变为1星银狼')]
    pick = decide_planner(opts, st, None)
    assert pick.idx == 1 and '升费' in pick.reason, '升费档 > 弱化档'
    # key_equip 命中在装备域内排前(风暴潮 6+15 > 轮滑鞋 4)
    tgt = Comp(name='tk', factions=[], core_chars=[], form_tiers={}, strength='A',
               form_difficulty='medium', key_equips=['火力风暴潮'])
    opts2 = [PlannerOption(idx=0, text='轮滑鞋 简易装备'),
             PlannerOption(idx=1, text='火力风暴潮 进阶装备')]
    pick2 = decide_planner(opts2, st, tgt)
    assert pick2.idx == 1 and '+key_equip' in pick2.reason, f'key_equip 域内优先,实得 {pick2.reason}'
    # 装备档(21)不跨域压弱化档(55)
    opts3 = [PlannerOption(idx=0, text='火力风暴潮 进阶装备'),
             PlannerOption(idx=1, text='使后续节点【弱化】,降低敌人属性。')]
    pick3 = decide_planner(opts3, st, tgt)
    assert pick3.idx == 1, '弱化档 > 装备档(key_equip 命中不跨域)'


# ==================== strategy 段:结算拆两半观察半(自 test_cw_strategy.py 迁入) ====================

def test_settlement_observation_stores_last_hp_when_confident() -> None:
    """D-94:达阈置信度的结算 hp_after → 观察半即时存 session.last_hp
    (给下回合 prep state.hp;gated_hp 真值源)。出处 = ADR-0583 §2.5,
    写点单一源 = cw_screen_battle_wait._write_settlement_observation。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        _write_settlement_observation,
    )

    sess = MandateV1Strategy().create_session(_cfg())
    assert sess.last_hp is None
    obs = RoundOutcome(round_num=4, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=58, hp_confidence=1.0)   # 结算屏读对(高置信)
    _write_settlement_observation(sess, obs, 4)
    assert sess.last_hp == 58
    assert sess.last_hp_t == 4   # 时间锚同门写入(gated_hp gap 计算基准)


def test_settlement_observation_skips_low_confidence_hp() -> None:
    """D-94:低置信(hp_confidence<阈,如结算屏 OCR 失败 hp_after=0)→ 不存
    (防 0 污染下回合 prep;门随迁义务,ADR-0583 D2)。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
        _write_settlement_observation,
    )

    sess = MandateV1Strategy().create_session(_cfg())
    sess.last_hp = 70   # 上轮已存的可靠值
    obs = RoundOutcome(round_num=5, plane=1, node_type='普通战斗', comp_tag='DOT队',
                       hp_after=0, hp_confidence=0.0)   # OCR 失败(conf 0)
    _write_settlement_observation(sess, obs, 5)
    assert sess.last_hp == 70, "低置信结算不应覆盖已存的可靠 HP"
    assert sess.last_hp_t is None   # 时间锚同门,低置信不写


# ==================== blackboard 段(自 test_cw_blackboard.py 迁入) ====================

def test_shop_screen_missing_frame_raises() -> None:
    """黑板契约:观察帧缺失 = 观察层失约 → 抛错,禁静默按空态决策。"""
    strat = MandateV1Live()
    sess = _fresh(strat)
    assert sess.shop_state_frame is None
    with pytest.raises(ValueError, match='shop_state_frame'):
        strat.decide_shop_screen(sess, None)


def test_abstract_members_exact_set() -> None:
    """abstract 面 = 冷建 1 + 分画面决策入口 11,恰 12 个;create_state
    非 abstract(保留总成员 13);退役成员出契约面(墓碑,否定式 +
    ADR-0583 退役背书)。"""
    expected = {
        'create_session',
        'decide_prep_screen', 'decide_shop_action',
        'decide_invest', 'decide_supply', 'decide_encounter',
        'decide_megastar', 'decide_partner', 'decide_planner',
        'decide_star_tome', 'decide_wish_trial', 'decide_box_card',
    }
    assert set(CwStrategy.__abstractmethods__) == expected
    assert 'create_state' not in CwStrategy.__abstractmethods__
    for retired in ('update_target', 'on_match_start', 'on_round_end',
                    'on_match_end', 'decide_prep_action',
                    'decide_shop_screen'):
        assert not hasattr(CwStrategy, retired), (
            f'{retired} 已随 ADR-0583 出契约面,禁回流 ABC')
    # 驱动器降格落点:decide_shop_screen = flow 层非 abstract 缺省实现
    from sr_od.application.currency_war.strategies.impl.flow import (
        CwFlowStrategy,
    )
    assert callable(CwFlowStrategy.decide_shop_screen)


# ==================== supply_merge_crisis 段(自 test_cw_supply_merge_crisis.py 迁入) ====================
# iter_7f 候选② 升星合并完成买入(M2b;dd-032 merge_completion_exempt 同款判读)。

def _bc(name: str, slot: int = 0, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions or ['?'])[0])


def _supply_comp():
    names = [c.name for c in COMP_LIBRARY if getattr(c, 'core_chars', None)]
    return get_comp(names[0])


def _members(comp) -> list[str]:
    ms = list(comp.core_chars) + list(getattr(comp, 'shared_chars', []) or [])
    return list(dict.fromkeys(ms))


def _shop_session(comp) -> StrategySession:
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import proof
    s = StrategySession()
    state_of(s).cw4_counters = {}
    state_of(s).target_comp = comp
    state_of(s).cw4_line_state = proof.LineState()
    return s


def _shop_state(gold: int = 30, shop=None, bench=None, deployed=None,
                level: int = 3) -> GameState:
    st = GameState(gold=gold, level=level, round_num=2)
    st.shop = shop if shop is not None else []
    st.bench = bench if bench is not None else []
    st.deployed = deployed if deployed is not None else []
    return st


def _decide_shop(state: GameState, session: StrategySession):
    from sr_od.application.currency_war.sim.engine_p1 import (
        sim_decision_registry,
    )
    strat = MandateV1Strategy(registry=sim_decision_registry())
    session.shop_state_frame = state
    return strat.decide_shop_screen(session, SimpleNamespace(ev_arm='full'))


def test_third_copy_bought_as_merge_completion() -> None:
    """已持 2 张同名同星 1★、第三张在店 affordable ⇒ 必须买入
    (reason=m2_merge_completion 可归因)——旧形态 owned 拒后无人买,
    同帧经验支出=优先级倒置(g_20260904_054904 p2r1)。"""
    comp = _supply_comp()
    m = _members(comp)[0]
    st = _shop_state(gold=30, shop=[ShopCard(x=100, name=m, cost=3)],
                     bench=[_bc(m, slot=1), _bc(m, slot=2)])
    acts = _decide_shop(st, _shop_session(comp))
    merge_buys = [a for a in acts if isinstance(a, BuyCard)
                  and a.reason == 'm2_merge_completion']
    assert any(b.card.name == m for b in merge_buys), \
        '合并完成件(第三张)在店 affordable 必须买入'
