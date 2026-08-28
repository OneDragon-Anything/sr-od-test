# -*- coding: utf-8 -*-
"""W502 / math_proofs P21:P2 濒死 LevelUp 雨期望收益为负——纯函数推导锁。

出处:docs/game/currency_war/research/proofs/p21-p2-deathbed-levelup-ev.md
(计算脚本 tools/cw/proofs/w502_p21_deathbed_levelup_ev.py 可重跑)。
本文件**镜像**命题公式与常量做推导锁,不 import 生产决策代码、
不向 registry 添加任何常量(命题边界声明:只裁决行为经济性,不改决策面)。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 购买经验点击数阶梯:ceil(XP_TO_NEXT_LEVEL/XP_PER_BUY) = 5/10/13/18
  (lv5→9;cw_state 注册表镜像),与 W490 实测帧(×13 击≈50金,lv7→8)吻合;
- ② 濒死域 EV(hp≤10,单场败局伤害下界>H0 ⇒ 全胜存活模型):
  代表参数下严格为负,且随到账延迟 d 严格单调递减;
- ③ 全参数网格 (p,Δp,d,c) 3×3×3×3 = 81 cells 无一 EV≥0(锁推导结论);
- ④ 判据式:「存活到账 h > d·L_c」在濒死域(≤10)内对 d≥1 恒假;
  受益覆盖上界 Δp·L_c·Σ(p+Δp)^j ≤ Δp·L_c·m:Δp=0.36 经验上界下,
  覆盖 C=20 需 m≥4;濒死实测帧剩余 m≤3 ⇒ 上界 <20,覆盖不可满足。
"""
from __future__ import annotations

import itertools
import math

# —— 机制常量(cw_state 镜像;单一源 src/sr_od/application/currency_war/cw_state.py)——
XP_PER_BUY = 4
XP_TO_NEXT_LEVEL = {3: 4, 4: 6, 5: 20, 6: 40, 7: 52, 8: 72, 9: 84}
INTEREST_FLOOR = 50
INTEREST_PER_ROUND = 5

# —— P21 语料标定常量(单一源 = P21 单篇;非 registry 常量)——
H0 = 10
L_C = 15.39
P_BASE = 0.19


def clicks_to_level(level: int) -> int:
    """跨 1 级所需购买经验点击数(P21 ①;同 cw_horizon.clicks_to_level 公式)。"""
    need = XP_TO_NEXT_LEVEL.get(level, 84)
    return max(1, math.ceil(need / XP_PER_BUY))


def deathbed_ev(p: float, dp: float, d: int, b: int, cost: float, v_live: float,
                g: float = 60.0) -> float:
    """濒死域(hp≤H0<L_C)升级 burst 期望收益(P21 命题式;镜像实现)。"""
    if b - d <= 0:
        return -cost
    s0 = p ** b
    s1 = (p ** d) * ((p + dp) ** (b - d))
    i = INTEREST_PER_ROUND * min(d, 3) if g - cost < INTEREST_FLOOR else 0.0
    return (s1 - s0) * v_live - cost - i


def alive_survives_arrival(h: float, d: int, l_c: float = L_C) -> bool:
    """判据式:存活到账 h > d·L_c(P21 命题 2)。"""
    return h > d * l_c


def test_clicks_ladder_matches_registry_and_w490() -> None:
    # ① 点击数阶梯:lv5→6 / 6→7 / 7→8 / 8→9 = 5/10/13/18
    assert [clicks_to_level(lv) for lv in (5, 6, 7, 8)] == [5, 10, 13, 18]
    # W490 ⑰ P2r2 实测:LevelUp×13、87→37 金、lv7→8 —— 与 c=4 的 C=52 吻合
    assert clicks_to_level(7) == 13
    assert clicks_to_level(7) * 4 == 52


def test_deathbed_ev_negative_and_monotone_in_delay() -> None:
    # ② 代表参数(p=0.19, Δp=0.12, B=6, V_live=300):全负 + d 单调递减
    evs = [deathbed_ev(P_BASE, 0.12, d, 6, clicks_to_level(7) * 4, 300.0) for d in (0, 1, 2)]
    assert all(ev < 0 for ev in evs), evs
    assert evs[0] > evs[1] > evs[2], evs
    # 到账前已无战斗(d≥B):纯支出
    assert deathbed_ev(P_BASE, 0.12, 6, 6, 52.0, 300.0) == -52.0


def test_full_grid_negative() -> None:
    # ③ 81-cell 网格全负(与 P21 ③ 敏感性表同网格;最有利 cell EV=−40.80)
    cells = list(itertools.product(
        (0.10, 0.19, 0.30), (0.05, 0.12, 0.28), (0, 1, 2), (4, 6, 8)))
    assert len(cells) == 81
    evs = [deathbed_ev(p, dp, d, 6, clicks_to_level(7) * c, 300.0) for p, dp, d, c in cells]
    assert all(ev < 0 for ev in evs)
    assert max(evs) < 0


def test_criterion_unreachable_in_deathbed_domain() -> None:
    # ④ 存活到账判据在濒死域内恒假(d≥1 需 h>15.39;h≤10)
    assert not any(alive_survives_arrival(h, d) for h in (0, 5, 10) for d in (1, 2))
    assert alive_survives_arrival(16, 1)

    def benefit_upper(dp: float, m: int) -> float:
        # benefit = Δp·L_c·Σ_{j=0}^{m-1} p'^j,上界取 p'=1(最有利)
        return dp * L_C * m

    # 覆盖最低升级费 C=20 需 m ≥ ceil(20/(0.36×15.39)) = 4(Δp 经验上界 0.36)
    assert benefit_upper(0.36, 3) < 20   # 濒死实测帧(⑰⑱ r5/r7,7 槽)剩余 m≤3
    assert math.ceil(20 / (0.36 * L_C)) == 4
    assert benefit_upper(0.36, 4) >= 20  # 理论可达域仅在位面早期(m≥4),与濒死域不相交
