"""部署围栏 0 锁击穿回归锁(seed 31016 p1r6;二十九跳增补)。

形态:非满板 hold 豁免路径击穿 ADR-0287 检查——重放 bench 上下文缩减
(主趟 up 后剩余)把主趟按容量/成对留置的件翻转成可上 ⇒ lag 假阳。
根修 = 重放 lag 扣除主趟围栏已仲裁 hold 的槽位(W678:围栏 hold 不计
漏上)。seed 回归锁为慢桶(整局仿真),快速集跳过、直跑验证。
"""
import pytest

from sr_od.application.currency_war.sim import engine_p1
from sr_od.application.currency_war.sim.engine_p1 import (
    _lag_excluding_fenced_holds,
)


class TestLagExcludingFencedHolds:

    def test_main_held_slot_excluded(self):
        """重放认可的件若槽位属主趟 hold 仲裁 ⇒ 不计 lag。"""
        assert _lag_excluding_fenced_holds(
            [1], [3, 4, 6, 7], {4}) == 0

    def test_non_held_slot_still_counts(self):
        """主趟未仲裁(新翻转认可)的件 ⇒ 照常计 lag(检查不失明)。"""
        assert _lag_excluding_fenced_holds(
            [1], [3, 4, 6, 7], {6}) == 1
        assert _lag_excluding_fenced_holds(
            [0, 1], [3, 4, 6, 7], {4}) == 1

    def test_out_of_range_index_ignored(self):
        """越界下标忽略(防御;正常输入不出现)。"""
        assert _lag_excluding_fenced_holds([9], [3, 4], {4}) == 0


@pytest.mark.slow
def test_seed_31016_p1r6_lag_zero_regression():
    """回归锁(慢桶,整局仿真):seed 31016 p1r6 非满板 hold 形态
    ⇒ deploy_lag_units 回 0(修复前 =1 假阳)。"""
    res = engine_p1.simulate_p1(31016, pool='snapshot')
    for row in res.ledger:
        if row.get('plane') == 1 and row.get('round_num') == 6:
            lag = (row.get('sim') or {}).get('deploy_lag_units')
            assert lag == 0, f'p1r6 deploy_lag_units={lag}(0 锁假阳未闭)'
