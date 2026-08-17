"""15 号敌情强度表测试。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_enemy_strength import (  # noqa: E402
    StrengthTable,
    calibrate_strength,
)


def test_calibrate_real_replay() -> None:
    """真实 telemetry 校准:表非空 + 关键档在 + P1 奖励节点 0 掉血。"""
    t = calibrate_strength(_REPO / '.debug' / 'temp' / 'currency_war' / 'replay')
    assert len(t.rows) >= 5
    assert t.lookup(1, 9) is not None          # boss 档
    assert t.lookup(1, 9).n >= 2
    r2 = t.lookup(1, 2)                         # 奖励节点(p1-2)
    if r2 is not None:
        assert r2.mean_loss == 0.0              # 奖励节点无战斗


def test_lookup_missing() -> None:
    """未采样档返 None(消费端回退先验,不硬编)。"""
    t = StrengthTable()
    assert t.lookup(3, 5) is None
