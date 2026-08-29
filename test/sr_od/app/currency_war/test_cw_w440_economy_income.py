"""sim 收入口径修正锁(ADR-0439):败轮节点金 + 奖励轮 base/streak 成对。

锁四面:
1. LOSS_GOLD_BY_NODE 值锁(实机 gold 差分:普通 2/遭遇 4/boss 4;
   STREAK_GOLD_TABLE/BASE_INCOME 零触碰——胜轮表是弹窗真值,ADR-0262);
2. 败轮收入路径锁(生产 sim 账本:败掉的战斗类节点,下一轮收入按
   败掉那轮的节点类型取 LOSS_GOLD);
3. 奖励轮成对锁(streak 照发表 + base 查表 REWARD_BASE_GOLD_BY_ROUND,
   成对防「单改 streak 变多发」回归);
4. 版本披露锁(economy_calib_version 独立进 manifest,不占粗模型版本)。
"""
from __future__ import annotations

import json

from sr_od.application.currency_war.sim import engine_p1 as cw_sim
from sr_od.application.currency_war.sim.checks import runner
from sr_od.application.currency_war.kernel import cw_economy
from sr_od.application.currency_war.kernel.cw_economy import (
    BASE_INCOME,
    LOSS_GOLD_BY_NODE,
    REWARD_BASE_GOLD_BY_ROUND,
    STREAK_GOLD_TABLE,
    streak_gold,
)

# 路径锁扫描的 seed 数(断言成立的最小覆盖:9 轮/局,败轮高频)
_PATH_SEEDS = 8


def test_loss_gold_by_node_values() -> None:
    """败轮节点金值锁(实机差分众数;独立常量,不动胜轮真值表)。"""
    assert LOSS_GOLD_BY_NODE == {'battle': 2, 'encounter': 4, 'boss': 4}
    # 胜轮表零触碰(ADR-0262):败轮修正不得外溢到 streak_gold 域
    assert STREAK_GOLD_TABLE == (1, 1, 2, 2, 2, 3, 4)
    assert streak_gold(0) == 1 and streak_gold(1) == 1
    assert BASE_INCOME == 5   # 统一近似常量不动(非奖励节点仍 5)


def test_loss_round_income_path_in_sim_ledger() -> None:
    """败轮收入路径锁:生产账本中,败掉的战斗类节点 → 下一轮收入
    streak 分量 = LOSS_GOLD_BY_NODE[败掉节点的类型](奖励轮照发表/
    补给轮恒 0 的分支不受败态影响,与 cw_sim 收入段分支一致)。
    """
    loss_seen = 0
    for seed in range(_PATH_SEEDS):
        r = cw_sim.simulate_p1(seed, pool='fallback')
        rows = r.ledger
        for i, row in enumerate(rows[:-1]):
            s = row['sim']
            if (s['node'] not in LOSS_GOLD_BY_NODE
                    or (s.get('delta') or 0) > 0):
                continue
            loss_seen += 1
            nxt = rows[i + 1]['sim']
            got = nxt['income']['streak']
            if nxt['node'] == 'supply':
                assert got == 0, f'seed{seed}: 败后补给轮不得带 streak'
            elif nxt['node'] == 'reward':
                assert got == streak_gold(0), \
                    f'seed{seed}: 败后奖励轮照发表[0]=1'
            else:
                assert got == LOSS_GOLD_BY_NODE[s['node']], \
                    f'seed{seed} r{row["round_num"]}: 败轮金路径断'
    assert loss_seen > 0, '扫描窗口内无败局样本,锁空转(扩 seed 数)'


def test_reward_round_pair_income_in_sim_ledger() -> None:
    """奖励轮成对锁:base 查表(r1=3/r2=4/其余 5)+ streak 照发表,
    两分量同轮成立——单改 streak 的回归会在此红(净多发 1)。
    """
    reward_seen = 0
    for seed in range(_PATH_SEEDS):
        streak = 0   # 进轮连胜重放(战斗轮 delta>0 计胜,同 sim 结算段)
        for row in cw_sim.simulate_p1(seed, pool='fallback').ledger:
            s = row['sim']
            if s['node'] == 'reward':
                reward_seen += 1
                rn = row['round_num']
                inc = s['income']
                assert inc['base'] == REWARD_BASE_GOLD_BY_ROUND.get(
                    rn, BASE_INCOME), \
                    f'seed{seed} r{rn}: 奖励轮 base 未成对查表'
                assert inc['streak'] == streak_gold(streak), \
                    f'seed{seed} r{rn}: 奖励轮 streak 未照发表'
            elif s['node'] in LOSS_GOLD_BY_NODE:
                streak = streak + 1 if (s.get('delta') or 0) > 0 else 0
    assert reward_seen > 0, '扫描窗口内无奖励轮样本,锁空转'


def test_economy_calib_version_disclosed_in_manifest(tmp_path) -> None:
    """版本披露锁:收入口径版本独立进 sim 台账 manifest,
    与粗模型版本(coarse_calib_version)分键、互不占用。
    """
    assert cw_economy.ECONOMY_CALIB_VERSION == 2   # ADR-0443 事件金重整定
    r = cw_sim.simulate_p1(1, pool='fallback')
    out = runner.write_batch_ledger([r], tmp_path / 'batch')
    manifest = json.loads(
        (out / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['economy_calib_version'] == \
        cw_economy.ECONOMY_CALIB_VERSION
    assert 'coarse_calib_version' in manifest   # 粗模型键原样保留


from sr_od.application.currency_war.sim import runner
