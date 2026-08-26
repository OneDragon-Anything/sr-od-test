# -*- coding: utf-8 -*-
"""W205/ADR-0384 补偿器卖件组批量下界过滤单帧锁。

背景(W203 ①A 巡检实证,W197/ADR-0380 边界声明不实处):两补偿器
(``_compensate_gold``/``_compensate_bench``)的卖件候选对批前 ``state``
一次性构造,``sell_priority_key`` 内的 ``sole_engine_sell_blocked`` 对
state 单次评估——组内多笔**异名** TT 件逐笔合法(各见 count=tier+1)、
合计跌破 tier(136 型同批聚合窗在补偿通道未闭合)。修法=发射前按
``sole_engine_sell_floor_plan``(ADR-0380 批量口径,前序「可卖」件从
计数扣减)对 ``working`` 过滤(``_sell_floor_filter``)。

锁契约(不锁分布数值):
- ①金补偿主锁:列车在手 3=tier+1(三月七+姬子·启行在 bench,姬子
  在场),缺口需两笔回金——过滤后第二笔被逐笔扣减挡(2≤tier),
  凑不足 → 整组放弃(无部分卖出);
- ②金补偿不过度辖:缺口一笔即够时只卖一笔(三月七),另一 TT 件
  不动(体系余量 3→2=tier 合法面);
- ③金补偿 flag off 逐位回 W197 后行为(两笔均卖);
- ④bench 腾位主锁:缺 2 槽需卖两笔 TT 件 → 第二笔被挡,整组放弃;
  flag off 两笔均卖(旧行为)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    BuyCard,
    GameState,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.remediation import (
    RejectReason,
    Rejection,
    _compensate_bench,
    _compensate_gold,
)

_REG = DEFAULT_REGISTRY
_REG_OFF = dataclasses.replace(_REG, sell_floor_exec_guard_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _bc(name: str, slot: int = 0, star: int = 1,
        row: str = 'back') -> BenchChar:
    faction = (CHARACTERS[name].factions or ['?'])[0]
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     position_pref=row, star=star)


def _gold_state() -> GameState:
    """列车在手 3=tier+1(三月七 cost1 + 姬子·启行 cost3 在 bench,
    姬子在场);第三槽银枝(非 TT 散件,买目标=银枝时被 buy_name 排除)。
    board 空 → 边际羁绊贡献守卫不挡;board_factions 由 eval 派生。"""
    return GameState(plane=1, round_num=5, gold=0, level=7, board={},
                     hp=80,
                     bench=[_bc('三月七', 0), _bc('姬子·启行', 1),
                            _bc('银枝', 2), None, None, None, None,
                            None, None],
                     deployed=[_bc('姬子', 9, row='front')])


def _gold_rejection(cost: int) -> Rejection:
    """金拒:买银枝(与 bench 银枝同名 → sellable 排除银枝)。
    shortfall = 0(地板)+ cost − working.gold(0)。"""
    card = ShopCard(3, faction='星间旅人', name='银枝', cost=cost, star=1)
    cand = Candidate(action=BuyCard(card), tag='engine_seed',
                     source='test')
    return Rejection(RejectReason('gold_floor', 'gold', 0, 'test'),
                     cand, 5.0)


def _tt_in_hand(pool) -> int:
    return sum(1 for b in pool if b is not None and b.char_id
               and '列车同行' in set(CHARACTERS[b.char_id].factions)
               | set(CHARACTERS[b.char_id].flows))


# ===== ① 金补偿主锁 =====


def test_compensate_gold_batch_floor_blocks_second_tt() -> None:
    """①缺口=4(需三月七 1 + 姬子·启行 3 两笔回金):过滤后三月七
    可卖(计数 3→2),姬子·启行被逐笔扣减挡(2≤tier 2)→ got=1<4
    → 整组放弃(无部分卖出)。"""
    sess = _sess()
    st = _gold_state()
    acts = _compensate_gold(st, st, sess, _REG, _gold_rejection(4),
                            None, floor=0)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert not sells, f'聚合跌破 tier 的第二笔应被挡且整组放弃:{acts}'


def test_compensate_gold_single_need_not_overblocked() -> None:
    """②缺口=1(三月七一笔即够):只卖三月七,姬子·启行不动
    (3→2=tier 合法,不过度辖)。"""
    sess = _sess()
    st = _gold_state()
    acts = _compensate_gold(st, st, sess, _REG, _gold_rejection(1),
                            None, floor=0)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert len(sells) == 1 and sells[0].bench_idx == 0, acts
    assert any(isinstance(a, BuyCard) for a in acts), '受益买应重发'


def test_compensate_gold_flag_off_restores_w197() -> None:
    """③off 臂:flag off 时两笔 TT 件均卖(=W197 后旧行为,聚合
    跌破窗重现——本锁承载 136 型补偿通道形态)。"""
    sess = _sess()
    st = _gold_state()
    acts = _compensate_gold(st, st, sess, _REG_OFF, _gold_rejection(4),
                            None, floor=0)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert [s.bench_idx for s in sells] == [0, 1], acts


# ===== ④ bench 腾位 =====


def test_compensate_bench_batch_floor_blocks_second_tt() -> None:
    """④主锁:bench 满(9 槽占用)缺 2 槽,买银枝(排除银枝槽)→
    候选=[三月七, 姬子·启行]:第二笔被逐笔扣减挡 → 腾不足 →
    整组放弃;flag off 两笔均卖(旧行为)。"""
    sess = _sess()
    st = _gold_state()
    # bench 满:补满剩余空槽(非 TT 散件)
    st.bench = [st.bench[0], st.bench[1], st.bench[2],
                *[_bc('银枝', i) for i in range(3, BENCH_CAPACITY)]]
    card = ShopCard(3, faction='星间旅人', name='银枝', cost=2, star=1)
    cand = Candidate(action=BuyCard(card), tag='engine_seed',
                     source='test')
    rej = Rejection(RejectReason('bench_capacity', 'bench', 2, 'test'),
                    cand, 5.0)
    acts = _compensate_bench(st, st, sess, _REG, rej)
    sells = [a for a in acts if isinstance(a, SellBench)]
    assert not sells, f'第二笔 TT 应被挡且整组放弃:{acts}'
    # off 臂:两笔均卖(旧行为)
    acts_off = _compensate_bench(st, st, sess, _REG_OFF, rej)
    sells_off = [a for a in acts_off if isinstance(a, SellBench)]
    assert [s.bench_idx for s in sells_off] == [0, 1], acts_off
