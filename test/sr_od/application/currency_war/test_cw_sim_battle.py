"""sim 重做 S4(M12/M13/M14 战斗结算)回归锁。

设计正本 = ``docs/develop/sr_od/application/currency_war/changes/
2026-09-15-sim-redesign/design.md``;锁面 = U01 随机输出面(胜负 P=0.5
均匀伯努利/扣血均匀区间 [23,70]/流键可复现)/U03 分项置 None/简化档
标记/M14 结构规则(败才扣血/首次 0hp 保底剩 1/再次归零局终)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    ChannelSig,
    GameState,
    register_sig_actors,
)
from sr_od.application.currency_war.sim.cw_sim_battle import (
    SIM_BATTLE_FACE,
    SIM_HP_LOSS_MAX,
    SIM_HP_LOSS_MIN,
    SIM_WIN_PROB,
    apply_hp_outcome,
    settle_battle,
)
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng

register_sig_actors('TestSigWriter')

_OBS_SIG = ChannelSig(family='obs', actor='TestSigWriter')


def _gs(hp: int | None = None) -> GameState:
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    if hp is not None:
        gs.observe(gs.hp, hp, sig=_OBS_SIG)
    return gs


def test_battle_face_domain_over_seeds() -> None:
    """U01 输出域:胜 → hp_delta 0/进度达标;败 → 总扣血 ∈ [23,70]/
    进度均匀采样;分项恒 None(U03 直扣不拆);输出面带简化档标记。"""
    wins = 0
    rounds = 400
    for seed in range(rounds):
        out = settle_battle(stream_rng(seed, 'M13/p1/r7'),
                            plane=1, round_num=7)
        assert out.face == SIM_BATTLE_FACE
        assert out.base_damage is None and out.progress_damage is None, \
            'U03:分项第一期不拆,置 None 占位'
        if out.won:
            wins += 1
            assert out.hp_delta == 0 and out.progress == 1.0
        else:
            assert SIM_HP_LOSS_MIN <= -out.hp_delta <= SIM_HP_LOSS_MAX
            assert 0.0 <= out.progress < 1.0
    ratio = wins / rounds
    assert 0.42 <= ratio <= 0.58, \
        f'胜率 {ratio:.3f} 偏离 U01 定案 P=0.5(宽带 ±6σ)'


def test_battle_stream_reproducible() -> None:
    """§2.0.4:同 (seed, 流键) 结算逐位可复现(胜负+扣血+进度)。"""
    a = settle_battle(stream_rng(9, 'M13/p2/r3'), plane=2, round_num=3)
    b = settle_battle(stream_rng(9, 'M13/p2/r3'), plane=2, round_num=3)
    assert a == b


class BattleLike:
    """apply_hp_outcome 入参最小桩(只辖 HP 折算消费面)。"""

    def __init__(self, won: bool, hp_delta: int) -> None:
        self.won = won
        self.hp_delta = hp_delta
        self.face = SIM_BATTLE_FACE
        self.progress = 0.0
        self.base_damage = None
        self.progress_damage = None


def test_hp_outcome_loss_and_win_paths() -> None:
    """M14:胜不扣血;败扣 hp(总扣血直扣,分项不拆)。"""
    gs = _gs(82)
    floor_now, dead = apply_hp_outcome(gs, BattleLike(won=True, hp_delta=0))
    assert floor_now is False and dead is False
    assert int(gs.hp.value or 0) == 82, '胜利不掉血(多局确认口径)'
    bs2 = _gs(82)
    loss_hp = 30
    floor_now, dead = apply_hp_outcome(bs2, BattleLike(won=False,
                                                       hp_delta=-loss_hp))
    assert (floor_now, dead) == (False, False)
    assert int(bs2.hp.value or 0) == 82 - loss_hp


def test_hp_floor_guarantee_once_then_game_over() -> None:
    """M14:首次归零保底剩 1(容器保底位翻真);再次归零 → 局终。"""
    gs = _gs(40)
    first = BattleLike(won=False, hp_delta=-40)
    floor_now, dead = apply_hp_outcome(gs, first)
    assert (floor_now, dead) == (True, False)
    assert int(gs.hp.value or 0) == 1
    assert gs.hp_floor_triggered.value is True, '保底事件位翻真(已消费)'
    second = BattleLike(won=False, hp_delta=-23)
    floor_now2, dead2 = apply_hp_outcome(gs, second)
    assert (floor_now2, dead2) == (False, True), '再次归零 = 整局结束'
    assert int(gs.hp.value or 0) == 0


def test_win_prob_constant_is_ruling_value() -> None:
    """U01 定案常量钉死:P=0.5 / 区间 [23,70](锚定规则改常量须经
    新实测样本并入,常量漂移 = 设计裁决漂移)。"""
    assert SIM_WIN_PROB == 0.5
    assert (SIM_HP_LOSS_MIN, SIM_HP_LOSS_MAX) == (23, 70)
