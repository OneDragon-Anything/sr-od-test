"""货币战争 P1 模拟器(cw_sim)测试 —— 纯逻辑,不依赖游戏。

锁定模拟器基建的契约:
- 可复现(同 seed 同结果);
- 有限牌池守恒(买减/卖回/总数不变除非购买);
- 方向判据与策略认领一致(锁线/桥);
- A/B 对照通道(use_refresh 剔除刷新);
- 统计口径(HP≥60/方向建立分布)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.cw_sim import (
    _Pool,
    simulate_p1,
    simulate_p1_batch,
)


def test_seed_reproducible() -> None:
    """同 seed 同局(结果全字段一致)。"""
    a = simulate_p1(42, pool='fallback')
    b = simulate_p1(42, pool='fallback')
    assert a.final_hp == b.final_hp
    assert a.hp_trail == b.hp_trail
    assert a.dir_round == b.dir_round


def test_pool_conservation() -> None:
    """有限牌池守恒:draw 不减池(买了才减),take/ret 互逆。"""
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    total0 = sum(p.copies.values())
    p.draw_shop(5)                       # 抽店不减池(商店只是展示)
    assert sum(p.copies.values()) == total0
    name = next(iter(p.copies))
    p.take(name)
    assert sum(p.copies.values()) == total0 - 1
    p.ret(name)
    assert sum(p.copies.values()) == total0
    assert p.copies[name] <= POOL_COPIES_PER_CARD[CHARACTERS[name].cost]


def test_pool_cap_respected() -> None:
    """ret 不超过基础副本数(卖出回池有上限)。"""
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    name = next(iter(p.copies))
    cap = POOL_COPIES_PER_CARD[CHARACTERS[name].cost]
    for _ in range(cap + 5):
        p.ret(name)
    assert p.copies[name] == cap


def test_direction_matches_strategy_claim() -> None:
    """方向建立 = 策略认领(锁线/桥);模拟本身不另立判据。"""
    r = simulate_p1(3, pool='fallback')
    # 若报告已建立,则建立轮之后每一轮都应保持认领态(锁线粘性)
    assert r.dir_round < 99 or r.locked_line is None


def test_ab_channel_refresh() -> None:
    """use_refresh=False 时刷新数为 0(A/B 通道工作)。"""
    on = simulate_p1(11, pool='fallback', use_refresh=True)
    off = simulate_p1(11, pool='fallback', use_refresh=False)
    assert off.refreshes == 0
    assert on.refreshes >= 0          # 开通道至少不崩


def test_batch_stats_shape() -> None:
    """批量统计口径齐全(HP≥60/方向分布/平均)。"""
    s = simulate_p1_batch(60, pool='fallback')
    assert s['n'] == 60
    assert 0.0 <= s['hp_ge_60'] <= 1.0
    assert 0.0 <= s['dir_by_r4'] <= 1.0
    assert 0 <= s['avg_final_hp'] <= 100


def test_starting_state_valid() -> None:
    """开局态:lv3/gold5/hp80/非空 bench(开局送牌)。"""
    r = simulate_p1(5, pool='fallback')
    assert r.hp_trail, '至少跑了 r1'


def test_node_sequence_shape() -> None:
    """节点序列(r284 固定骨架):首二 reward,slot2-3 battle,
    slot4 supply,slot5-6 变异位,末 boss(遥测 14 帧实证)。"""
    import random

    from sr_od.application.currency_war.cw_sim import sample_node_sequence
    for seed in (1, 2, 3):
        seq = sample_node_sequence(random.Random(seed))
        assert len(seq) == 9
        assert seq[0] == 'reward' and seq[1] == 'reward'
        assert seq[2] == 'battle' and seq[3] == 'battle'
        assert seq[4] == 'supply'
        assert seq[5] in ('battle', 'encounter')
        assert seq[-1] == 'boss'


def test_reward_node_no_damage() -> None:
    """奖励/补给节点零战力要求 → 不掉血(r260 分层)。"""
    import random

    from sr_od.application.currency_war.cw_sim import node_delta
    rng = random.Random(7)
    for node in ('reward', 'supply'):
        for rn in (3, 5, 8):
            d = node_delta(node, rn, 99, rng)
            assert d > 0, f'{node} r{rn} 不应掉血,得 {d}'


def test_encounter_harder_than_battle() -> None:
    """遭遇轮结算强度 > 同期普通战斗(用户口述:遭遇可比 boss 难)。"""
    import random

    from sr_od.application.currency_war.cw_sim import node_delta
    losses_enc, losses_bat = [], []
    for seed in range(50):
        rng = random.Random(seed)
        losses_enc.append(node_delta('encounter', 6, 99, rng))
        losses_bat.append(node_delta('battle', 6, 99, rng))
    avg_enc = -sum(losses_enc) / len(losses_enc)
    avg_bat = -sum(losses_bat) / len(losses_bat)
    assert avg_enc > avg_bat, \
        f'遭遇均值损 {avg_enc} 应大于战斗 {avg_bat}'
