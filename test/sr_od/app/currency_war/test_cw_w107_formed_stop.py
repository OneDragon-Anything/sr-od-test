# -*- coding: utf-8 -*-
"""W107/ADR-0343 成型停手纪律单帧锁。

锁行为(每条=一个确定输入下的确定行为):
- 成型态五项判定([13] 三件套+r7+/P1)逐项:满足→买候选被拦/缺一→放行;
- 边界:应急态不豁免(反因路径正是对象)/等级买·刷新·卖·上阵例外/[12][33];
- 开关:formed_stop_enabled=False=旧行为;
- 检查器联动:overflow_gold_zero_buy_streak 对 formed_stop 轮重置 streak
  (旧局无字段不受影响);
- sim 端到端(W111 改 regen-robust):小窗 seed 扫描证存在性——池内
  必有成型停手触发局,标志入账本且门咬住(固定 seed 触发面随池
  再生漂移,锁瞬时 seed=池耦合 change-detector);
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
    """成型态:DOT队 form_tiers 全满 + 核心**上场** 2★ + P1 r7。

    W119/ADR-0347 构造适配:formed_stop 收编 form_ok——核心须上场
    (旧帧核心躺 bench;「核心须上场」是 2026-08-25 用户裁决,
    W114 影子批已注记本锁需同步)。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    board = {f: t for f, t in comp.form_tiers.items()}
    base = {
        'plane': 1, 'round_num': 7, 'gold': 60, 'level': 5,
        'hp': 60, 'board': board,
        'deployed': [BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                               star=2)],
        'bench': [],
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
    """form_ok 谓词缺一即不辖(W119/ADR-0347 收编后;Q2 裁决:等级
    不再是独立条件——lv4 帧随裁决改为合法成型,不辖项换成谓词族):
    ① 核心 2★ 躺 bench(未上场,「核心须上场」裁决);
    ② 羁绊未满(主档缺 1);
    ③ 核心上场但 1★。"""
    comp = get_comp('DOT队')
    core = intention_core(comp)
    # ① 核心 2★ 在 bench 不上场
    s1 = _formed_state(
        deployed=[BenchChar(slot=0, char_id='桑博', faction='仙舟罗浮',
                            star=1)],
        bench=[BenchChar(slot=0, char_id=core, faction='仙舟罗浮',
                         star=2)])
    # ② 羁绊未满(主档缺 1)
    board2 = dict(comp.form_tiers)
    k0 = next(iter(board2))
    board2[k0] = board2[k0] - 1
    s2 = _formed_state(board=board2)
    # ③ 核心上场但 1★
    s3 = _formed_state(deployed=[BenchChar(slot=0, char_id=core,
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


def test_sim_formed_stop_e2e_seed_scan() -> None:
    """sim 端到端(regen-robust,W111):快照池每次局终自动再生
    (ADR-0344),固定 seed 的触发面随池内容漂移(W109 实证:seed 33
    在池 4d28822c 下无触发轮)——改锁**存在性语义**:小窗 seed 扫描
    证明「池内必有成型停手触发局且门咬住」;窗口内无任何触发局 =
    成型停手在 sim 真实轨迹上失活,锁必须红(检测价值不降)。
    门咬住的锁法(轨迹因果不变式,比总数对比诚实):开/关臂同 seed
    同 RNG 流,闸门不拦截时两臂动作逐位相同 → **账本首个分歧行
    =闸门首次实际拦截处**——该行必为成型停手轮且关臂买入数严格
    多于开臂(总数对比在分歧后轨迹分叉,不再可比)。触发轮标志入
    账本为轮内 OR 聚合(演进可轮中点亮成型,段前买入合法,故标记
    轮内仍可有合法买入);关臂同 seed 标志恒 False;检查器对开臂
    账本不误报。"""
    reg_off = replace(DEFAULT_REGISTRY, formed_stop_enabled=False)

    def _buys_in(row: dict) -> int:
        return sum(1 for a in row.get('actions') or []
                   if a.get('__type__') == 'BuyCard')

    def _behavior(row: dict) -> dict:
        return {k: v for k, v in row.items() if k != 'formed_stop'}

    # W132/ADR-0353:兜底门改结构判据后,窗口内首个触发局可能是
    # 「仅标志局」(触发轮无被拦买入,两臂行为同)——扫描取首个
    # **咬合局**(有触发且有行为分歧且分歧轮被拦),存在性语义不变。
    picked = None
    for seed in range(80):
        r_on = simulate_p1(seed, pool='snapshot')
        if not any(row.get('formed_stop') for row in r_on.ledger):
            continue
        r_off = simulate_p1(
            seed, pool='snapshot',
            strategy=DecisionV2Strategy(registry=reg_off))
        assert not any(row.get('formed_stop') for row in r_off.ledger)
        pair = next(((a, b) for a, b in zip(r_on.ledger, r_off.ledger,
                                            strict=False)
                     if _behavior(a) != _behavior(b)), None)
        if pair is None:
            continue
        if pair[0].get('formed_stop') is not True:
            continue
        if not _buys_in(pair[0]) < _buys_in(pair[1]):
            continue
        picked = (seed, r_on, r_off, pair)
        break
    assert picked, ('seed 窗口 0-79 无成型停手咬合局——成型停手在'
                    ' sim 真实轨迹上失活(或只余仅标志局)')
    seed, r_on, r_off, pair = picked
    diff_on, diff_off = pair
    assert diff_on.get('formed_stop') is True, (
        f'首个分歧行非成型停手轮(r{diff_on.get("round_num")})'
        '——分歧非闸门所致')
    assert _buys_in(diff_on) < _buys_in(diff_off), (
        f'分歧轮买入 on={_buys_in(diff_on)} off={_buys_in(diff_off)}'
        '——关臂未多买,门未咬住')
    # 检查器不误报:开臂账本(成型轮零买不进 streak)整体无违规
    assert check_overflow_gold_zero_buy_streak(r_on.ledger) == []
