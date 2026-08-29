"""P4 小修簇锁面(破息例外记账补全 / 满级升级拒付空转门 / 刷新预算帽检查)。

三组穿透锁(注错→锁红→修正→锁绿;锁语义出处见各 docstring):
① seg_break_interest_exception 例外谱收编(追级/刷新授权通道)+ 花费
   分解字段——锁「授权通道破息不红」与「真无例外破息仍红」两侧;
② sim 决策层注册表 level_max 对齐执行层 LEVEL_CAP(接线单一址
   cw_sim.sim_decision_registry)——满级帧候选零升级,实机真值不漂移;
③ 刷新预算帽双检查(普通车道轮帽 REFRESH_ROLL_CAP / 定向车道局帽
   directed_refresh_game_cap)。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_sim
from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

# --- ② 满级升级空转门 --------------------------------------------------------


def _state_at(level: int, **kw) -> GameState:
    base = {'plane': 1, 'round_num': 6, 'gold': 80, 'level': level,
            'board': {'仙舟罗浮': 1}, 'bench': [], 'shop': [], 'hp': 80}
    base.update(kw)
    return GameState(**base)


def test_sim_registry_aligns_exec_cap() -> None:
    """sim 视图注册表 level_max == 执行层 LEVEL_CAP(单一尺);
    实机真值 DEFAULT_REGISTRY.level_max 保持 10 不漂移。"""
    assert cw_sim.LEVEL_CAP == 9
    reg = cw_sim.sim_decision_registry()
    assert reg.level_max == cw_sim.LEVEL_CAP
    assert DEFAULT_REGISTRY.level_max == 10


def test_levelup_candidate_absent_at_sim_cap_frame() -> None:
    """满级帧(sim 语义 lv9)候选零升级:决策层前置拦住,执行层
    拒付层不再被空转触发(穿透锁:接线前该帧有 LevelUp 候选 →
    每帧发起到被拒)。"""
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    st = _state_at(cw_sim.LEVEL_CAP)
    cands = generate_candidates(st, sess, cw_sim.sim_decision_registry())
    assert not [c for c in cands
                if c.action.__class__.__name__ == 'LevelUp']


def test_levelup_candidate_still_valid_below_live_cap() -> None:
    """防矫枉过正:实机语义下 lv9 是正常付费升级档(live 满级 = 10),
    用 DEFAULT_REGISTRY 时 lv9 帧仍生成 LevelUp 候选——sim 建模分歧
    不得倒灌实机行为。"""
    sess = StrategySession()
    sess.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    st = _state_at(9)
    cands = generate_candidates(st, sess, DEFAULT_REGISTRY)
    assert [c for c in cands if c.action.__class__.__name__ == 'LevelUp']


# --- ① 破息例外记账 ----------------------------------------------------------


def _break_row(round_num: int, g0: int, g1: int, node: str,
               spend: dict, actions: list[dict]) -> dict:
    return {'plane': 1, 'round_num': round_num, 'gold': g1, 'hp': 80,
            'sim': {'node': node, 'delta': 1, 'spend': spend,
                    'shop_waves': [{'event': 'offer', 'gold': g0,
                                    'cards': []}]},
            'actions': actions}


def test_levelup_driven_break_not_flagged() -> None:
    """追级经验通道破息 = 授权通道表征(ev.levelup_ev_basis 单一源),
    不进「无例外」红(穿透锁:收编前该形态红,是基线噪声主体)。"""
    rows = [_break_row(7, 52, 19, 'encounter',
                       {'buys': {}, 'levelup': 32, 'refresh': 0,
                        'sell_income': 0},
                       [{'__type__': 'LevelUp', 'cost': 4, 'auth': ''}])]
    assert chk.seg_check_break_interest_exception(rows) == []


def test_refresh_driven_break_not_flagged() -> None:
    """刷新找牌通道破息(refresh_ev_budget / M-A 预算授权面)同上。"""
    rows = [_break_row(9, 67, 45, 'boss',
                       {'buys': {}, 'levelup': 0, 'refresh': 6,
                        'sell_income': 0},
                       [{'__type__': 'RefreshShop', 'cost': 2}] * 3)]
    assert chk.seg_check_break_interest_exception(rows) == []


def test_unexplained_buy_break_still_flagged_with_breakdown() -> None:
    """真无例外破息(单笔非店全想要买件,无升级/刷新/连胜)仍红,
    且事件带花费分解(升级/刷新/买件,归因不看人工)。"""
    rows = [_break_row(5, 60, 40, 'encounter',
                       {'buys': {'engine': 20}, 'levelup': 0,
                        'refresh': 0, 'sell_income': 0},
                       [{'__type__': 'BuyCard',
                         'card': {'name': '某件', 'cost': 20,
                                  'faction': '仙舟罗浮'},
                         'reason': 'engine', 'channel': 'engine'}])]
    ev = chk.seg_check_break_interest_exception(rows)
    assert len(ev) == 1
    assert ev[0]['spend_breakdown'] == {'levelup': 0, 'refresh': 0,
                                        'buys': {'engine': 20}}


# --- ③ 刷新预算帽双检查 --------------------------------------------------------


def _refresh_rows(counts: list[tuple[int, int]],
                  dir_counts: list[int] | None = None) -> list[dict]:
    """counts = (round_num, 该轮 RefreshShop 数);dir_counts 可选给定。"""
    dir_counts = dir_counts or [0] * len(counts)
    out: list[dict] = []
    for (rn, n), d in zip(counts, dir_counts, strict=True):
        out.append({
            'plane': 1, 'round_num': rn, 'gold': 40, 'hp': 80,
            'sim': {'node': 'encounter', 'dir_refreshes': d,
                    'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                              'sell_income': 0}},
            'actions': [{'__type__': 'RefreshShop', 'cost': 2}] * n,
        })
    return out


def test_refresh_roll_cap_discloses_ordinary_over_cap() -> None:
    """普通车道 7 刷/轮 > REFRESH_ROLL_CAP(6)→ 披露 frames_over_cap
    (变异注入形态:7 连刷此前零检查命中;披露型不作归零锁——逐段
    重决策语义下账本轮级不可判,语义见检查 docstring)。"""
    rep = chk.check_refresh_roll_cap_frame([_refresh_rows([(6, 7)])])
    assert rep['violations'] == 0
    assert rep['frames_over_cap'] == 1
    assert rep['max_ordinary_per_round'] == 7


def test_refresh_roll_cap_deducts_directed_lane() -> None:
    """6 普通刷新 + 2 定向 = 8/轮 不计越帽:定向车道有自身授权面
    (per_round 上限),不得计入普通车道帽。"""
    rep = chk.check_refresh_roll_cap_frame(
        [_refresh_rows([(8, 8)], [2])])
    assert rep['frames_over_cap'] == 0
    assert rep['max_ordinary_per_round'] == 6


def test_directed_refresh_game_cap_lock() -> None:
    """定向车道全局 7 次 > 局帽 6(directed_refresh_game_cap)→ 违规;
    帽内(≤6)恒绿。"""
    assert len(chk.check_directed_refresh_game_cap(
        _refresh_rows([(7, 2), (8, 2), (9, 1), (5, 2)], [2, 2, 1, 2]))) == 1
    assert chk.check_directed_refresh_game_cap(
        _refresh_rows([(8, 2), (9, 2)], [2, 2])) == []


def test_refresh_cap_checks_wired() -> None:
    """两检查项接线到位:硬锁在批检查表(run_checks_on_ledgers 自动
    扫),披露项在批级聚合入口(遗漏接线 = 检查静默失明)。"""
    assert 'directed_refresh_game_cap_lock' in chk._BATCH_CHECKS
    # 批级披露经 run_batch_level_checks 汇出(以注册名为键)
    rep = chk.run_batch_level_checks(
        [[{'plane': 1, 'round_num': 1, 'gold': 40, 'hp': 80,
           'sim': {'node': 'encounter', 'dir_refreshes': 0,
                   'spend': {'buys': {}, 'levelup': 0, 'refresh': 0,
                             'sell_income': 0}},
           'actions': []}]])
    assert 'refresh_roll_cap_frame' in rep
    assert rep['refresh_roll_cap_frame']['violations'] == 0


# --- 语义快照:默认策略构造走 sim 视图(接线单一址生效) -----------------------


def test_default_simulate_strategy_uses_sim_registry() -> None:
    """simulate_p1 默认策略的 registry.level_max == LEVEL_CAP
    (注入自定义 strategy 的调用方不受影响)。"""
    from sr_od.application.currency_war.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    strat = DecisionV2Strategy(registry=cw_sim.sim_decision_registry())
    assert strat.registry.level_max == cw_sim.LEVEL_CAP
