# -*- coding: utf-8 -*-
"""W107/ADR-0343 成型停手纪律单帧锁。

锁行为(每条=一个确定输入下的确定行为):
- 成型态五项判定([13] 三件套+r7+/P1)逐项:满足→买候选被拦/缺一→放行;
- 边界:应急态不豁免(反因路径正是对象)/等级买·刷新·卖·上阵例外/[12][33];
- 开关:formed_stop_enabled=False=旧行为;
- 检查器联动:overflow_gold_zero_buy_streak 对 formed_stop 轮重置 streak
  (旧局无字段不受影响);
- sim 端到端:seed 33(已知 r7-r9 触发)账本行带标志且该轮零 BuyCard;
  关臂同 seed 标志恒 False。
"""
from __future__ import annotations

from dataclasses import replace

from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.cw_sim import simulate_p1
from sr_od.application.currency_war.cw_sim_checks import (
    check_overflow_gold_zero_buy_streak,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    DeployMove,
    GameState,
    LevelUp,
    RefreshShop,
    SellBench,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.filters import (
    filter_candidates,
    formed_stop_active,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.cw_comps import get_comp


def _card(name: str = '测试卡', cost: int = 1) -> ShopCard:
    return ShopCard(name=name, faction='仙舟罗浮', cost=cost, x=0, star=1)


def _cands() -> list[Candidate]:
    """四类候选各一(买/等级买/刷新/卖+上阵)。"""
    return [
        Candidate(action=BuyCard(_card(), reason=''), tag='line_carry',
                  source='shop'),
        Candidate(action=LevelUp(cost=4), tag='levelup', source='xp'),
        Candidate(action=RefreshShop(cost=2), tag='refresh', source='shop'),
        Candidate(action=SellBench(bench_idx=0, income=1, expect=''),
                  tag='for_gold', source='bench'),
        Candidate(action=DeployMove(bench_idx=1, to_row='front',
                                    faction='仙舟罗浮'),
                  tag='deploy', source='fence'),
    ]


def _formed_state(**kw) -> GameState:
    """成型态:DOT队 form_tiers 全满 + 核心 2★ + lv5 + P1 r7。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    board = {f: t for f, t in comp.form_tiers.items()}
    base = {
        'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
        'hp': 60, 'board': board,
        'bench': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                            star=2)],
        'shop': [],
    }
    base.update(kw)
    return GameState(**base)


def _sess_locked(comp_name: str = 'DOT队') -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp_name)
    return sess


def test_formed_stop_blocks_buy_keeps_exceptions() -> None:
    """成型态:买被拦;等级买/刷新/卖/上阵保留([12]/[33] 例外)。"""
    state = _formed_state()
    sess = _sess_locked()
    kept, log = filter_candidates(_cands(), state, sess, DEFAULT_REGISTRY)
    tags = {c.tag for c in kept}
    assert 'line_carry' not in tags, '成型 r7+ 买候选必须被拦'
    assert {'levelup', 'refresh', 'for_gold', 'deploy'} <= tags
    assert sess.v3_formed_stop is True
    dropped = [e for e in log if e['formed_stop']]
    assert dropped and all(not e['kept'] for e in dropped)


def test_unformed_each_piece_passes() -> None:
    """[13] 三件套缺一即不辖:等级不足/羁绊未满/核心未 2★。"""
    comp = get_comp('DOT队')
    # ① 等级 <5
    s1 = _formed_state(level=4)
    # ② 羁绊未满(主档缺 1)
    board2 = dict(comp.form_tiers)
    k0 = next(iter(board2))
    board2[k0] = board2[k0] - 1
    s2 = _formed_state(board=board2)
    # ③ 核心 1★
    s3 = _formed_state(bench=[BenchChar(slot=0, char_id=intention_core(comp),
                                        faction='仙舟罗浮', star=1)])
    for s in (s1, s2, s3):
        sess = _sess_locked()
        assert formed_stop_active(s, sess, DEFAULT_REGISTRY) is False
        kept, _ = filter_candidates(_cands(), s, sess, DEFAULT_REGISTRY)
        assert any(isinstance(c.action, BuyCard) for c in kept)


def test_window_and_plane_gates() -> None:
    """r6 不辖(证据窗 r7+);P2 不辖([13] 是 P1 语义)。"""
    sess1 = _sess_locked()
    assert formed_stop_active(_formed_state(round_num=6), sess1,
                              DEFAULT_REGISTRY) is False
    sess2 = _sess_locked()
    assert formed_stop_active(_formed_state(plane=2), sess2,
                              DEFAULT_REGISTRY) is False


def test_unlocked_intent_not_governed() -> None:
    """意向未锁(unlocked/兜底):「羁绊凑够」无定义,保守不辖。"""
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='unlocked')
    assert formed_stop_active(_formed_state(), sess, DEFAULT_REGISTRY) is False


def test_emergency_does_not_exempt() -> None:
    """应急态(hp≤emergency_hp)不豁免——W105 反因路径正是对象。"""
    s = _formed_state(hp=10)   # hp ≤ 25 = emergency
    sess = _sess_locked()
    kept, _ = filter_candidates(_cands(), s, sess, DEFAULT_REGISTRY)
    assert not any(isinstance(c.action, BuyCard) for c in kept)
    # 等级买在应急集内本就放行,停手不额外拦
    assert any(c.tag == 'levelup' for c in kept)


def test_switch_off_restores_old_behavior() -> None:
    """总开关 False=旧行为(成型照买)。"""
    reg = replace(DEFAULT_REGISTRY, formed_stop_enabled=False)
    sess = _sess_locked()
    kept, log = filter_candidates(_cands(), _formed_state(), sess, reg)
    assert any(isinstance(c.action, BuyCard) for c in kept)
    assert sess.v3_formed_stop is False


def test_checker_exempts_formed_stop_rounds() -> None:
    """检查器联动:formed_stop 轮重置 streak;旧局无字段不受影响。"""
    def _row(r: int, gold: int = 60, fs: bool | None = None) -> dict:
        d = {'plane': 1, 'round_num': r, 'gold': gold, 'actions': [],
             'run_id': 't'}
        if fs is not None:
            d['formed_stop'] = fs
        return d
    # 旧语义保持:两轮金>50 零买零升级(无标志)→ 违规
    assert check_overflow_gold_zero_buy_streak([_row(7), _row(8)])
    # 成型停手轮夹在中间 → streak 被重置,不再连成 ≥2
    assert not check_overflow_gold_zero_buy_streak(
        [_row(7), _row(8, fs=True), _row(9)])
    # 成型前(未成型)的断买仍报——停手不回溯洗白早前违规
    assert check_overflow_gold_zero_buy_streak(
        [_row(5), _row(6), _row(7, fs=True), _row(8)])


def test_sim_seed33_ledger_flag_and_no_buy() -> None:
    """sim 端到端:seed 33 成型 r7-r9 触发——标志入账本(轮内 OR 聚合,
    演进可轮中点亮成型,段前买入合法故锁「门咬住」而非零买);
    关臂同 seed 标志恒 False;检查器对开臂账本不误报。"""
    r_on = simulate_p1(33, pool='snapshot')
    fs_rows = [row for row in r_on.ledger if row.get('formed_stop')]
    assert fs_rows, 'seed 33 应有成型停手轮(触发面扫描实证)'

    def _buys_r7plus(res) -> int:
        return sum(1 for row in res.ledger
                   if (row.get('round_num') or 0) >= 7
                   for a in row.get('actions') or []
                   if a.get('__type__') == 'BuyCard')

    reg_off = replace(DEFAULT_REGISTRY, formed_stop_enabled=False)
    r_off = simulate_p1(33, pool='snapshot',
                        strategy=DecisionV2Strategy(registry=reg_off))
    assert not any(row.get('formed_stop') for row in r_off.ledger)
    # 门必须咬住:开臂 r7+ 买入数严格少于关臂(该局成型态店内有可买候选)
    assert _buys_r7plus(r_on) < _buys_r7plus(r_off), (
        f'gate 未生效:on={_buys_r7plus(r_on)} off={_buys_r7plus(r_off)}')
    # 检查器不误报:开臂账本(成型轮零买不进 streak)整体无违规
    assert check_overflow_gold_zero_buy_streak(r_on.ledger) == []
