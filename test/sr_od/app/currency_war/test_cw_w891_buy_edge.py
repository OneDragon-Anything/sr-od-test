"""W891 候选① · 买牌执行边界固定开销压缩 单帧锁组。

设计出处:.debug/temp/currency_war/w891_c1_buy_edge/REPORT.md §1
(判据/落地规格);审计依据 = w891_latency_audit/REPORT.md 候选①
(duration ≈ 19.0s + 2.14s×操作数;固定开销压缩只压等待与重复读,
指纹机制语义不得破坏)。

三组锁:
- 仅刷新波判定(w592 勘误的边界条件化,连击共享往返单一判据);
- 买后重估增量态构造(gold 真读 / tracked 重播 / 机制不变量沿用 /
  失读 fail-closed 回退);
- 回归锚:gate 文件本批零改动——稳定窗/预估等待常量与
  wait_stable_frame 签名不变(指纹机制零触碰的漂移锚)。
"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
    bench_occupied,
)
from sr_od.application.currency_war.obs import cw_observation_gate
from sr_od.application.currency_war.operations.prep.shop import (
    build_post_buy_incremental_state,
    refresh_wave_is_refresh_only,
)


def _st(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 3, 'node_type': '战斗', 'gold': 60,
            'hp': 80, 'hp_readable': True, 'level': 7, 'streak': None,
            'board': {'列车同行': 1}, 'bench': [], 'shop': []}
    base.update(kw)
    return GameState(**base)


def _tracked() -> list[BenchChar]:
    return [BenchChar(slot=1, char_id='姬子·启行', star=1, faction='列车'),
            BenchChar(slot=2, char_id='囤件', star=1, faction='公司')]


# ===== 锁 1:仅刷新波判定(连击共享往返的边界)=====

def test_refresh_only_wave_predicate() -> None:
    """首动作即 RefreshShop = 仅刷新波(可复用波循环顶读当刷前现读);
    前缀含买/升/卖的波一票否决(w592 勘误失效条件只在含买波成立);
    空 plan 非(无刷新可谈)。"""
    assert refresh_wave_is_refresh_only([RefreshShop()]) is True
    assert refresh_wave_is_refresh_only(
        [BuyCard(ShopCard(x=0, name='姬子·启行', cost=3)), RefreshShop()]) is False
    assert refresh_wave_is_refresh_only([LevelUp(cost=40)]) is False
    assert refresh_wave_is_refresh_only(
        [SellBench(bench_idx=0, income=1), RefreshShop()]) is False
    assert refresh_wave_is_refresh_only([]) is False


# ===== 锁 2:买后重估增量态构造 =====

def test_post_buy_incremental_state_gold_truth_and_bench_replay() -> None:
    """gold=关店帧真读覆盖(末波垫底值是执行前快照,必须换真值);
    bench 重播 tracked(执行侧 mutate 逐动作同步的权威源,垫底值过期)。"""
    last = _st(gold=55, bench=[])   # 末波垫底:买前金/买前 bench
    post = build_post_buy_incremental_state(
        last, 41, _tracked(), '战斗', 80, True, True)
    assert post is not None
    assert post.gold == 41
    assert bench_occupied(post.bench) == 2
    assert post.hp == 80 and post.hp_readable and post.hp_trusted
    assert post.node_type == '战斗'


def test_post_buy_incremental_state_invariants_preserved() -> None:
    """机制不变量沿用末波读值:本单元动作(无升级)不触 plane/round/
    board/level/xp——增量构造不得回退这些面为缺省/零值。"""
    last = _st(plane=2, round_num=3, level=7, board={'列车同行': 1})
    post = build_post_buy_incremental_state(last, 41, [], None, 80, True, True)
    assert post is not None
    assert (post.plane, post.round_num, post.level) == (2, 3, 7)
    assert post.board == {'列车同行': 1}
    assert post.shop == []   # 沿用垫底(刷后牌面不进重估消费面,保真边界见报告 §1.5)
    assert post.hp_readable is True and post.hp_trusted is True


def test_post_buy_incremental_state_hp_unreadable_not_overwritten() -> None:
    """hp 不产值链(hp_value=None)→ _apply_hp 不覆盖:保留垫底帧的
    值+位(对账层产物),增量构造不引入假 hp/假可信位。"""
    last = _st(hp=80, hp_readable=True)
    post = build_post_buy_incremental_state(last, 41, [], None,
                                            None, False, False)
    assert post is not None
    assert post.hp == 80
    # 不覆盖语义:值+位与垫底帧逐位相同(不引入假 hp/假可信位)
    assert post.hp_readable == last.hp_readable
    assert post.hp_trusted == last.hp_trusted


def test_post_buy_incremental_state_gold_miss_fails_closed() -> None:
    """金失读 → None(调用方回退全量 read_game_state):宁全量不造值。"""
    assert build_post_buy_incremental_state(
        _st(), None, _tracked(), None, 80, True, True) is None


def test_post_buy_incremental_state_no_mutation_of_last_state() -> None:
    """垫底 state 不得被就地改写(round_success 仍消费其 gold/plane)。"""
    last = _st(gold=55, bench=[])
    build_post_buy_incremental_state(last, 41, _tracked(), None, 80, True, True)
    assert last.gold == 55 and bench_occupied(last.bench) == 0


# ===== 锁 3:gate 零触碰回归锚 =====

def test_gate_fingerprint_mechanism_constants_untouched() -> None:
    """指纹机制零触碰锚:稳定窗地板/预估等待/gate 签名本批不变
    (压缩的是 shop.py 波循环的等待与重复读,不是验证本身)。"""
    assert cw_observation_gate._OP_SETTLE_S == 1.2
    assert cw_observation_gate._OP_SETTLE_MIN_STABLE_S == 0.6
    for prof in (cw_observation_gate.PROFILE_CLOSED,
                 cw_observation_gate.PROFILE_OPEN):
        assert prof['min_stable_s'] == 0.6
        assert 'fingerprint_rects' in prof and prof['fingerprint_rects']
    assert list(inspect.signature(
        cw_observation_gate.wait_stable_frame).parameters) == [
        'op', 'profile', 'timeout_s', 'fast_confirm', 'segment', 'clock']
