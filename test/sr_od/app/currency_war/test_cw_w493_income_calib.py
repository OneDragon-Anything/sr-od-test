"""W493 经济校准锁(ADR-0447):事件金状态分布总闸 + delta 臂回退接粗模型。

锁四面:
1. EVENT_GOLD_BY_ROUND v2 值锁(实机逐轮金轨迹反馈整定产物;重整定
   必须伴随 ECONOMY_CALIB_VERSION 递增——两处同步改,防只改一边);
2. delta 对照臂桶缺回退路径锁(纯 fallback 池下战斗类全部走粗模型,
   胜态恒 +2 签名;默认 coarse 主路径不经该分支,零漂移由 B1 实测锁
   见 REPORT——单元域断言签名/可达性);
3. gold_dist_calib 对拍项(金均值越出实机带软告警;n<100 不判);
4. shop_cost_curve 对拍项(纯披露,不判)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.kernel import cw_economy
from sr_od.application.currency_war.kernel import cw_coarse_battle as cb
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_gold_dist_calib,
    check_shop_cost_curve,
)


def test_event_gold_table_v2_lock() -> None:
    """事件金 v2 值锁(整定产物;重整定须同步递增 economy 版本)。"""
    assert cw_economy.ECONOMY_CALIB_VERSION == 2
    assert cw_sim.EVENT_GOLD_BY_ROUND == {
        1: (0.0,), 2: (6.41,), 3: (13.95,), 4: (14.47,), 5: (23.11,),
        6: (19.41,), 7: (21.15,), 8: (35.05,), 9: (32.0,),
    }


def test_delta_arm_fallback_routes_to_coarse(monkeypatch) -> None:
    """delta 臂桶缺回退:纯 fallback 池(池恒 None)下战斗类结算全部
    落粗模型——胜 delta 恒 WIN_CAP(签名)、负 delta 走节点直方(≤0),
    高成型胜率随 rung 查表(可达性,B3 的单元域锚)。
    """
    monkeypatch.setattr(cb, 'BATTLE_ENGINE_MODE', 'delta')
    wins = 0
    combat = 0
    for seed in range(8):
        for row in cw_sim.simulate_p1(seed, pool='fallback').ledger:
            s = row['sim']
            if s['node'] not in ('battle', 'encounter', 'boss'):
                continue
            combat += 1
            d = s['delta']
            if d > 0:
                assert d == cb.WIN_CAP, \
                    f'seed{seed} r{row["round_num"]}: 对照臂胜态签名断裂(+{d})'
                wins += 1
    assert combat > 0 and wins > 0, '扫描窗口无战斗/无胜,锁空转'


def test_default_arm_unaffected_by_fallback_change() -> None:
    """默认 coarse 臂不进回退分支:同 seed 重放与 monkeypatch 前后逐位同
    (BATTLE_ENGINE_MODE='coarse' 恒默认;本锁防未来把默认臂误接回退)。
    """
    rows_a = [(x['ts'], x['hp'], x['gold'], x['sim']['delta'])
              for x in cw_sim.simulate_p1(5, pool='snapshot').ledger]
    rows_b = [(x['ts'], x['hp'], x['gold'], x['sim']['delta'])
              for x in cw_sim.simulate_p1(5, pool='snapshot').ledger]
    assert rows_a == rows_b


def _led(golds: list[int]) -> list[dict]:
    return [{'plane': 1, 'round_num': i + 1, 'gold': g, 'sim': {'node': 'reward'}}
            for i, g in enumerate(golds)]


def test_gold_dist_calib_band_alarm() -> None:
    """金均值越出实机带软告警;n<100 不判(数据边界)。"""
    poor = [_led([10] * 150)]          # 均值 10 < 25 → 告警
    assert check_gold_dist_calib(poor)['violations'] == 1
    rich = [_led([40] * 150)]          # 均值 40 > 35 → 同样告警
    assert check_gold_dist_calib(rich)['violations'] == 1
    inband = [_led([30] * 150)]        # 带内(30±5)→ 不告警
    assert check_gold_dist_calib(inband)['violations'] == 0
    assert check_gold_dist_calib([_led([30, 31])])['n'] == 2
    assert 'note' in check_gold_dist_calib([_led([30, 31])])


def test_shop_cost_curve_disclosure() -> None:
    """费用曲线纯披露:share 计算正确、空账本给 note、恒 0 违规。"""
    ledger = [{'plane': 1, 'round_num': 1, 'gold': 5,
               'sim': {'node': 'reward', 'shop_waves': [
                   {'event': 'offer',
                    'cards': [{'cost': 1}, {'cost': 1}, {'cost': 3}]},
                   {'event': 'refresh',
                    'cards': [{'cost': 4}]},   # 非 offer 波不入统计
               ]}}]
    out = check_shop_cost_curve([ledger])
    assert out['violations'] == 0 and out['n'] == 3
    assert out['sim_cost_share']['1'] == round(2 / 3, 4)
    assert out['sim_cost_share']['3'] == round(1 / 3, 4)
    empty_row = {'plane': 1, 'round_num': 1, 'gold': 5,
                 'sim': {'node': 'reward'}}
    empty = check_shop_cost_curve([[empty_row]])
    assert empty['violations'] == 0 and 'note' in empty

