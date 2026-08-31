# -*- coding: utf-8 -*-
"""① 账本基建锁:classify_buy 单一源 + BuyCard.reason 打标。

对抗审查二轮#2/#5 定谳:检查端只读 reason 不重算(第二源漂移);
label 集合以代码分支为准(line/bridge_seed/engine/pair/p2_core/
board_focus/emergency/swap/plan),不预设三分法。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_line_defs import classify_buy
from sr_od.application.currency_war.kernel.cw_state import BenchChar, BuyCard, GameState, ShopCard


def _st(board: dict[str, int] | None = None, bench: list[BenchChar] | None = None) -> GameState:
    st = GameState()
    st.plane, st.round_num, st.level, st.gold = 1, 1, 3, 10
    st.board = board or {}
    st.bench = bench or []
    return st


def test_buy_card_has_reason_field() -> None:
    """BuyCard.reason 字段存在且默认空(旧调用兼容)。"""
    c = BuyCard(card=ShopCard(x=0, faction='仙舟', name='爻光', cost=1))
    assert c.reason == ''


def test_classify_coldstart_bridge_vs_off() -> None:
    """局49 判据面:冷启动(板面空+bench 空)身份分类。

    桥名单件=bridge_seed;引擎阵营=engine;线外杂卡=off——
    r368 门=白名单 {bridge_seed, engine},检查端读同源标签。
    """
    st = _st()   # 全空 = 冷启动形态
    # 桥名单件(P1 BRIDGE_POOL fixed∪core 成员,如 丹恒·饮月)
    assert classify_buy(ShopCard(x=0, faction='仙舟', name='丹恒·饮月', cost=1), st) == 'bridge_seed'
    # 引擎阵营件(非桥名单但属 ENGINE_FACTIONS)
    assert classify_buy(ShopCard(x=1, faction='持续伤害', name='卡芙卡', cost=2), st) in ('bridge_seed', 'engine')
    # 线外杂卡(局49 形态:盛会之星/公司)
    assert classify_buy(ShopCard(x=2, faction='公司', name='翡翠', cost=1), st) == 'off'


def test_classify_pair_when_owned() -> None:
    """非冷启动:同阵营=pair;桥名单件优先 bridge_seed(分类序:
    bridge_seed > engine > pair——桥名单件即使已拥有阵营也标
    桥身份,检查端判「方向件」时两类都算)。"""
    st = _st(board={'仙舟': 1})
    # 藿藿 ∈ 桥名单核心 → bridge_seed(优先于 pair)
    assert classify_buy(ShopCard(x=0, faction='仙舟', name='藿藿', cost=1), st) == 'bridge_seed'
    # 非桥名单的板面同阵营件 → pair
    assert classify_buy(ShopCard(x=1, faction='公司', name='托帕', cost=1),
                        _st(board={'公司': 1})) == 'pair'


def test_coldstart_gate_consumes_classify() -> None:
    """r368 门消费 classify_buy 单一源(门=白名单 label 集)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import discipline
    src = inspect.getsource(discipline.pair_wants)
    assert 'classify_buy' in src, 'r368 冷启动门应收口 classify_buy(防第二源)'
