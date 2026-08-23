# -*- coding: utf-8 -*-
"""A3 修复1 锁(ADR-0260):P1 引擎件放行通道(engine_seed)。

实弹依据(A3_实机弹药 v2.1,局63-67 五局 48 次引擎件上架对拍):
判据漏 21%——金够的 cost1-3 引擎核心件(姬子·启行×3/丹恒·饮月×2/
藿藿×2/忘归人×2/星期日)被既有 seed/pair 门跳过(r6 金 19-52 不买)。

锁:
- 金够+未持有+P1 → 买,reason='engine_seed'(遥测可检索);
- 已持有同名(bench/deployed)→ 不走本通道(r383b copy 门辖区);
- 金不够 → 不买;
- 息档地板保留(满息期金 50 地板 50 → 不买);
- P2 不走本通道(过渡期语义)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.line_strategy import (
    LineStrategy,
)


def _mk(gold: int = 30, plane: int = 1, round_num: int = 6):
    s = LineStrategy()
    st = GameState()
    st.plane, st.round_num = plane, round_num
    st.level, st.gold, st.hp = 8, gold, 100   # lv8:免 LevelUp 分食预算
    st.board = {'护盾': 2}   # 板面非引擎配方件(列车不在 owned)
    sess = StrategySession()
    sess.v2_state = None
    sess.locked_line = None
    sess.bridge_id = None
    return s, st, sess


def _jizi() -> ShopCard:
    # 姬子·启行:独立列车角色 cost3(ammo 判据漏名单头名,
    # 非 r383b 桥名单件——bridge_seed 门不辖)
    return ShopCard(x=0, faction='列车同行', name='姬子·启行', cost=3)


def test_engine_seed_bought_when_gold_enough() -> None:
    """P1 r6 金 30,店有 姬子·启行(cost3)未持有 → 买,标签 engine_seed。"""
    s, st, sess = _mk(gold=30)
    st.shop = [_jizi()]
    acts = s.decide_prep(st, sess, None)
    buys = [a for a in acts if isinstance(a, BuyCard)
            and a.card.name == '姬子·启行']
    assert buys, '金够的引擎核心件被跳过(A3 判据漏回归)'
    assert any(a.reason == 'engine_seed' for a in buys)


def test_engine_seed_not_when_held() -> None:
    """bench 已有同名 → 本通道关闭(r383b copy 门辖区,不双通道)。"""
    s, st, sess = _mk(gold=30)
    st.shop = [_jizi()]
    st.bench = [BenchChar(char_id='姬子·启行', faction='列车同行', slot=1)]
    assert s._engine_seed_wants(_jizi(), st) is False
    acts = s.decide_prep(st, sess, None)
    jz = [a for a in acts if isinstance(a, BuyCard)
          and a.card.name == '姬子·启行']
    assert all(a.reason != 'engine_seed' for a in jz)


def test_engine_seed_deployed_held_also_blocks() -> None:
    """deployed 同名同样关闭本通道(bench+deployed 任一持有即算)。"""
    s, st, sess = _mk(gold=30)
    st.deployed = [BenchChar(char_id='姬子·启行', faction='列车同行',
                             slot=1)]
    assert s._engine_seed_wants(_jizi(), st) is False


def test_engine_seed_not_when_gold_insufficient() -> None:
    """金 2 < cost3 → 不买(金够门)。"""
    s, st, sess = _mk(gold=2)
    st.shop = [_jizi()]
    acts = s.decide_prep(st, sess, None)
    assert not [a for a in acts if isinstance(a, BuyCard)]


def test_engine_seed_floor_preserved() -> None:
    """息档地板保留(unit 级,floor 由调用方传入——破息窗 boss-breaker
    的低地板语义不受本通道影响):floor=50 时 cost3 破息 → 不买;
    floor=0 → 买。"""
    s, st, sess = _mk(gold=50)
    st.shop = [_jizi()]
    assert not s._buy_actions(st, sess, 50)
    buys = s._buy_actions(st, sess, 0)
    assert any(isinstance(a, BuyCard) and a.card.name == '姬子·启行'
               and a.reason == 'engine_seed' for a in buys)


def test_engine_seed_plane2_off() -> None:
    """P2 不走本通道(过渡期 = P1 语义)。"""
    s, st, sess = _mk(gold=30, plane=2)
    assert s._engine_seed_wants(_jizi(), st) is False


def test_engine_seed_non_transition_faction_off() -> None:
    """非过渡体系阵营(黑塔·银河学者)不走本通道。"""
    s, st, sess = _mk(gold=30)
    card = ShopCard(x=0, faction='银河学者', name='黑塔', cost=3)
    assert s._engine_seed_wants(card, st) is False
