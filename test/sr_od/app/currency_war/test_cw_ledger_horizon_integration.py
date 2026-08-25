"""cw_effect_ledger × cw_horizon 台账注入 DP 的涌现验证(53 号盲区 2 根治的端到端测试)。

v6 向量化后求解本体 ~0.3s,断言直接在 flat 数组上做(numpy 逐元素比对,毫秒级)——
**不触碰 ``.policy`` / ``.value`` 惰性 dict 视图**:3M 状态物化 ~6s/次,是旧版
「重求解分钟级」标记的真实成本来源(生产路径不消费 dict 视图,测试也不该消费)。

等价性:动作码 0-7 与 ``(level_up, refresh_budget)`` 的 8 种组合成双射
(0=存息/F/0, 1=F/2, 2=F/4, 3=F/6, 4=T/0, 5=T/2, 6=T/4, 7=T/6)——
姿态面变化数 = ``_act`` 数组不等元素数;V 值差数 = ``_val`` 逐元素 |diff|>1e-9 计数。
"""
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_effect_ledger import (  # noqa: E402
    AggregateEffect,
    build_ledger,
)
from sr_od.application.currency_war.cw_horizon import _solved, solve  # noqa: E402


def test_spy_earlier_levelup_emergence() -> None:
    """商业间谍(单击 −1)→ 升级成本 −25% → 姿态面变化(新增升级/刷预算增多)+ V 值差
    (首验 2026-08-17 金步长 1:全量新增升级 340+/20000 抽查、V 差 18.7%)。
    断言用 V 值差(对键序与阈值最稳健)+ 姿态差 >0。"""
    s_base = _solved()
    s_spy = solve(build_ledger([AggregateEffect('商业间谍', 'xp_click_delta', -1.0)]))
    n_posture_diff = int(np.count_nonzero(s_base._act != s_spy._act))  # noqa: SLF001
    n_v_diff = int(np.count_nonzero(np.abs(s_base._val - s_spy._val) > 1e-9))  # noqa: SLF001
    total = s_base._val.size  # noqa: SLF001
    assert n_v_diff > total * 0.05, f'V 值差波及面不足: {n_v_diff}/{total}'
    assert n_posture_diff > 100, f'姿态面变化不足: {n_posture_diff}'


def test_buyout_value_drop_widespread() -> None:
    """买断制(cap 0)→ 息流归零 → V 值差覆盖大半状态(首验:494k/644k=77%)。"""
    s_base = _solved()
    s_buy = solve(build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)]))
    n_diff = int(np.count_nonzero(np.abs(s_buy._val - s_base._val) > 1e-9))  # noqa: SLF001
    total = s_buy._val.size  # noqa: SLF001
    assert n_diff > total * 0.3, f'息覆写波及面不足: {n_diff}/{total}'
