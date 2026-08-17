"""cw_horizon DP 盘缓存(ADR-0202 v3)测试:指纹语义 + 缓存命中。"""
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_effect_ledger import (  # noqa: E402
    AggregateEffect,
    build_ledger,
)
from sr_od.application.currency_war.cw_horizon import (  # noqa: E402
    ledger_fingerprint,
    solve_cached,
)


def test_fingerprint_excludes_non_dp_effects() -> None:
    """指纹只含 DP 世界字段:纯时点金效果(不在台账)不改变指纹 → 命中即免重算。"""
    assert ledger_fingerprint(None) == 'base'
    led = build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)])
    assert ledger_fingerprint(led) != 'base'
    # 同效果同指纹;不同效果不同指纹
    led2 = build_ledger([AggregateEffect('买断制', 'interest_cap', 0.0)])
    assert ledger_fingerprint(led2) == ledger_fingerprint(led)
    led_spy = build_ledger([AggregateEffect('商业间谍', 'xp_click_delta', -1.0)])
    assert ledger_fingerprint(led_spy) != ledger_fingerprint(led)


def test_cache_roundtrip_and_hit() -> None:
    """盘缓存:同进程第二次调用 memo 直返(<1s;基线冷解 ~67s、盘载 ~5s[232MB pickle])。"""
    t0 = time.time()
    s1 = solve_cached(None)
    t1 = time.time()
    s2 = solve_cached(None)
    t2 = time.time()
    assert len(s1.policy) > 1_000_000
    assert t2 - t1 < 1.0, f'memo 命中过慢: {t2 - t1:.2f}s'
    assert s1.policy.keys() == s2.policy.keys()
