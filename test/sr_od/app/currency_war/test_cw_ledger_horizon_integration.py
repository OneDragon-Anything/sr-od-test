"""cw_effect_ledger × cw_horizon 台账注入 DP 的涌现验证(53 号盲区 2 根治的端到端测试)。

重求解分钟级 → 标记 slow(默认跑;CI 超时环境可 -m 'not slow' 跳过)。
零漂移部分用 mock 台账(空 mutations)在单点抽查上验,不全量重解。
"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_effect_ledger import (  # noqa: E402
    AggregateEffect,
    build_ledger,
)
from sr_od.application.currency_war.cw_horizon import _solved, solve  # noqa: E402

pytestmark = pytest.mark.slow


def test_spy_earlier_levelup_emergence() -> None:
    """商业间谍(单击 −1)→ 升级成本 −25% → 姿态面变化(新增升级/刷预算增多)+ V 值差
    (首验 2026-08-17 金步长 1:全量新增升级 340+/20000 抽查、V 差 18.7%)。
    断言用 V 值差(对键序与阈值最稳健)+ 姿态差 >0。"""
    s_base = _solved()
    s_spy = solve(build_ledger([AggregateEffect('商业间谍', 'xp_click_delta', -1.0)]))
    n_v_diff = n_posture_diff = 0
    for k, b in s_base.policy.items():
        s = s_spy.policy.get(k)
        if s and (s.level_up != b.level_up or s.refresh_budget != b.refresh_budget):
            n_posture_diff += 1
    for k, vb in s_base.value.items():
        vs = s_spy.value.get(k)
        if vs is not None and abs(vs - vb) > 1e-9:
            n_v_diff += 1
    assert n_v_diff > len(s_base.value) * 0.05, f'V 值差波及面不足: {n_v_diff}/{len(s_base.value)}'
    assert n_posture_diff > 100, f'姿态面变化不足: {n_posture_diff}'


def test_buyout_value_drop_widespread() -> None:
    """买断制(cap 0)→ 息流归零 → V 值差覆盖大半状态(首验:494k/644k=77%)。"""
    s_base = _solved()
    s_buy = solve(build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)]))
    n_diff = sum(1 for k, v in s_buy.value.items()
                 if k in s_base.value and abs(v - s_base.value[k]) > 1e-9)
    assert n_diff > len(s_buy.value) * 0.3, f'息覆写波及面不足: {n_diff}/{len(s_buy.value)}'
