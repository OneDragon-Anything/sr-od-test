# -*- coding: utf-8 -*-
"""ADR-0407:Δ池 encounter 桶键 depth→rung(v11)方向锁。

断言「投资换伤害减免主通道断裂」的 encounter 维裁决:
扩容+逐样本键查证(n=56,P1)证明——
- dep(Σboard)与 sd(净星深)键下期望伤害**真平**(中位分界两组
  置换检验 p=0.87;Spearman(dep,Δ)=−0.001;宽桶 w=6 两桶 CI 大幅
  交叠)——不是桶太粗,是板深维机制层面不可兑换;
- rung 键下梯度单调显著:r0 n=23 EΔ−24.9 / r1 n=27 −15.6 /
  r2 n=6 −4.3(bootstrap CI 不交叠)。
本文件把该方向性钉成快照锁;机制叙述见 ADR-0407。
"""
from __future__ import annotations

from sr_od.application.currency_war.sim import engine_p1 as _sim
from sr_od.application.currency_war.sim import pool
def _p1_means() -> dict[int, float]:
    m, _, _ = pool.resolve_pool('snapshot')
    m = pool.plane_view(m)
    enc = m.get('encounter') or {}
    return {int(b): sum(v) / len(v)
            for b, v in enc.items() if len(v) >= 5}


def test_v11_pool_encounter_main_buckets_monotonic() -> None:
    """encounter 主桶均值随 rung 单调趋 0(梯度真实,非随机分箱)。"""
    means = _p1_means()
    assert {0, 1} <= set(means), f'encounter 双主桶缺失: {sorted(means)}'
    assert means[0] < means[1], \
        f'encounter rung 梯度不成立: r0={means[0]:.1f} >= r1={means[1]:.1f}'
    if 2 in means:
        assert means[1] < means[2], \
            f'encounter rung 梯度在 r2 反向: r1={means[1]:.1f} ' \
            f'>= r2={means[2]:.1f}'


def test_v11_pool_encounter_no_depth_keys() -> None:
    """快照 encounter 桶键无 depth 域残留(键迁移完整性)。"""
    m, _, _ = pool.resolve_pool('snapshot')
    m = pool.plane_view(m)
    enc = m.get('encounter') or {}
    assert enc and all(int(b) <= 4 for b in enc), \
        f'v11 快照仍带 depth 域键: {sorted(enc)}'


def test_v11_settle_wiring_encounter_rung_source() -> None:
    """结算接线:simulate_p1 encounter 走 _settle_rung 单一源
    (与 battle 同式;防「池已 rung 化、采样仍喂 depth」错位)。"""
    import inspect
    src = inspect.getsource(_sim.simulate_p1)
    assert "live_delta_for('encounter', _settle_rung(st)" in src

