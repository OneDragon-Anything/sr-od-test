"""r411/ADR-0272 锁:sim 牌池无费用截断(批④F1,实机裁决)。

旧 _Pool(max_cost=3) 把 4/5 费概率质量静默重归一化(lv9 4费
.30→0),14 个 4 费角色不进池。锁:
- 池含 4/5 费角色(构造即全费入池);
- lv5+ 商店出现率 >0(4 费 lv5 起、5 费 lv9);
- 检查项双向:真池 0 违规;截断池必报(去门变异涌现违规)。
"""
from __future__ import annotations

import random

from sr_od.application.currency_war.data.cw_chars import CHARACTERS

from sr_od.application.currency_war.sim.pool import _Pool

from sr_od.application.currency_war.sim.checks.ledger import check_sim_pool_no_cost_truncation


def test_pool_contains_cost_4_and_5() -> None:
    """全费入池:copies 含 4 费与 5 费角色(无 max_cost 过滤)。"""
    p = _Pool(random.Random(7))
    costs = {CHARACTERS[n].cost for n in p.copies}
    assert 4 in costs and 5 in costs
    # 14 个 4 费角色全部在池(批④ F1 实证口径)
    n4 = sum(1 for n in p.copies if CHARACTERS[n].cost == 4)
    n5 = sum(1 for n in p.copies if CHARACTERS[n].cost == 5)
    assert n4 >= 14, f'4 费角色 {n4} < 14(截断回归)'
    assert n5 >= 9, f'5 费角色 {n5} < 9'


def test_four_cost_appears_at_lv5() -> None:
    """lv5 起商店 4 费出现率 > 0(REFRESH_PROB .02)。"""
    p = _Pool(random.Random(11))
    hits = sum(1 for _ in range(2000) for c in p.draw_shop(5)
               if c.cost == 4)
    assert hits > 0, 'lv5 未见 4 费(池截断或概率未接)'


def test_five_cost_appears_at_lv9() -> None:
    """lv9 商店 5 费出现率 > 0(P1 可达等级;REFRESH_PROB .10)。"""
    p = _Pool(random.Random(13))
    hits = sum(1 for _ in range(2000) for c in p.draw_shop(9)
               if c.cost == 5)
    assert hits > 0, 'lv9 未见 5 费(池截断或概率未接)'


def test_check_passes_on_real_pool() -> None:
    """检查项:真池(全费)0 违规。"""
    p = _Pool(random.Random(1))
    rep = check_sim_pool_no_cost_truncation(p.copies)
    assert rep == {'violations': 0, 'missing_costs': []}


def test_check_fires_on_truncated_pool() -> None:
    """检查项双向:截断池(去门变异)必报缺失费用。"""
    p = _Pool(random.Random(1))
    truncated = {n: c for n, c in p.copies.items()
                 if CHARACTERS[n].cost <= 3}   # 变异:重建 max_cost=3
    rep = check_sim_pool_no_cost_truncation(truncated)
    assert rep['violations'] == 2
    assert rep['missing_costs'] == [4, 5]
