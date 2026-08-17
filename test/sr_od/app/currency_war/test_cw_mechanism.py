"""机制常数注册表测试(redesign 23 号落地件):登记完整性 + 读口 + 语义约束。"""
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_mechanism import MechanismConstant, get_mechanism, _REGISTRY  # noqa: E402


def test_registry_nonempty_first_batch() -> None:
    """首批 ≥12 常数登记(23 号清单)。"""
    assert len(_REGISTRY) >= 12


def test_get_known_and_unknown() -> None:
    """读口:已知名返对象;未知名返 None(消费端 fallback 原值约定)。"""
    assert get_mechanism('SHOP_REFRESH_COST') is not None
    assert get_mechanism('NOT_EXIST') is None


def test_status_vocabulary() -> None:
    """status 词汇表封闭(23 号 §2.1:unverified→bracketed→verified;refuted/stale)。"""
    allowed = {'unverified', 'bracketed', 'verified', 'refuted', 'stale'}
    for c in _REGISTRY.values():
        assert c.status in allowed, f'{c.name} status={c.status}'


def test_kind_vocabulary() -> None:
    """kind 词汇表封闭(physics/income/odds/prior/meta)。"""
    allowed = {'physics', 'income', 'odds', 'prior', 'meta'}
    for c in _REGISTRY.values():
        assert c.kind in allowed, f'{c.name} kind={c.kind}'


def test_consumers_present_for_load_bearing() -> None:
    """承重常数(被 DP/plan 消费)必须登记 consumers(告警反查影响面)。"""
    for name in ('SHOP_REFRESH_COST', 'XP_CLICK_COST_FLAT', 'INTEREST_THRESHOLD'):
        assert get_mechanism(name).consumers, f'{name} 缺 consumers'


def test_unverified_flagged_honestly() -> None:
    """来源诚实标注(23 号 §1 实锤案例的后续):SHOP_REFRESH_COST 旧=粗估 unverified,
    2026-08-17 telemetry 实测(ADR-0177,n=1098 众数 2)→ 升 verified 且 provenance 带实测。"""
    c = get_mechanism('SHOP_REFRESH_COST')
    assert c.status == 'verified'
    assert '实测' in c.provenance
