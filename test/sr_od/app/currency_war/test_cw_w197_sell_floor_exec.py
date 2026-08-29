# -*- coding: utf-8 -*-
"""W197/ADR-0380 卖侧下界守卫执行点补全单帧锁(own_gap 演进谱系)。

因果探针(池 861fc9f6,seed 136):own≥tier 的体系件被拆的两处执行点
缺口——
- 件① arbiter 批内聚合缺口:r7 同段两笔 off_target 卖三月七,候选
  生成对**批前状态**计数(列车在手 3>tier 2)逐笔合法,同批聚合
  3→1 跌破 tier——``sole_engine_sell_blocked`` 此前只在候选生成
  (candidates._sell_tag)生效,采纳点无复检;
- 件② execute_replacement 溢出卖出:保留序(_locked_protected_names)
  是相对优先级不是绝对保证,bench 满截断时 rank0 保护件被划进 sold。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 批内复检主锁:两笔同名 TT 件卖候选(在手 3>tier 2),第一笔
  采纳后第二笔对 working 复检被拒(sell_floor);
- ② 批量计划口径:同批多笔逐笔扣减(前序可卖件计减);单笔与
  sole_engine_sell_blocked 逐位一致;
- ③ 溢出留场:bench 满截断保留序时,TT 体系件(在手=tier)不被
  卖出而留场(undeploy/sell 均不含;新上场收紧;事务 applied);
- ④ 冗余不辖:在手 tier+1 的 TT 件溢出卖出照旧(体系有余量清仓);
- ⑤ flag off 逐位回 W195 后行为(①的两笔均采纳 + ③的溢出卖出恢复)。
"""
from __future__ import annotations

import dataclasses

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_evolution import (
    UpgradeOption,
    UpgradeVerdict,
    execute_replacement,
)
from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    SellBench,
    simulate,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision_v2.discipline import (
    sole_engine_sell_blocked,
)
from sr_od.application.currency_war.kernel.cw_discipline_rules import (
    sole_engine_sell_floor_plan,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY
_REG_OFF = dataclasses.replace(_REG, sell_floor_exec_guard_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 7,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _bc(name: str, slot: int = 0, star: int = 1,
        row: str = 'back') -> BenchChar:
    faction = (CHARACTERS[name].factions or ['?'])[0]
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     position_pref=row, star=star)


# ===== 件① arbiter 批内复检 =====


def test_arbitrate_batch_recheck_blocks_second_tt_sell() -> None:
    """①主锁(136 r7 形态):bench 三月七×2 + deployed 丹恒·饮月
    (列车在手 3>tier 2,逐笔合法),两笔 off_target 候选——第一笔采纳
    后第二笔对 working(计数 2≤2)复检被拒。"""
    sess = _sess()
    st = _state(bench=[_bc('三月七', 0), _bc('三月七', 1),
                       _bc('银枝', 2)],
                deployed=[_bc('丹恒·饮月', 9, row='front')])
    sells = [Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'}),
             Candidate(action=SellBench(bench_idx=1), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})]
    res = arbitrate([(sells[0], 5.0, {}), (sells[1], 4.0, {})],
                    st, sess, _REG)
    acts = [a for a in res.actions if isinstance(a, SellBench)]
    assert len(acts) == 1, f'第二笔应被批内复检拒:{res.log}'
    rejects = [r['reject'] for r in res.log if not r['accepted']]
    assert any('sell_floor' in (r or '') for r in rejects), rejects


def test_arbitrate_batch_recheck_flag_off_restores_w195() -> None:
    """⑤off 臂:flag off 时两笔均采纳(=W195 后行为,逐位回退)。"""
    sess = _sess()
    st = _state(bench=[_bc('三月七', 0), _bc('三月七', 1),
                       _bc('银枝', 2)],
                deployed=[_bc('丹恒·饮月', 9, row='front')])
    sells = [Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'}),
             Candidate(action=SellBench(bench_idx=1), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})]
    res = arbitrate([(sells[0], 5.0, {}), (sells[1], 4.0, {})],
                    st, sess, _REG_OFF)
    acts = [a for a in res.actions if isinstance(a, SellBench)]
    assert len(acts) == 2, f'flag off 两笔均应采纳(旧行为):{res.log}'


# ===== 件② 批量计划口径(discipline 单一源) =====


def test_floor_plan_single_matches_predicate() -> None:
    """②单笔一致性:plan 单笔输入与 sole_engine_sell_blocked 逐位同值
    (在手 3>tier 2 → False;在手 2≤tier 2 → True)。"""
    sess = _sess()
    st3 = _state(bench=[_bc('三月七', 0)], deployed=[
        _bc('三月七', 9), _bc('丹恒·饮月', 10)])
    st2 = _state(bench=[_bc('三月七', 0)],
                 deployed=[_bc('丹恒·饮月', 9)])
    for st in (st3, st2):
        assert sole_engine_sell_floor_plan([st.bench[0]], st) == [
            sole_engine_sell_blocked(st.bench[0], st, _REG)]


def test_floor_plan_sequential_decrement() -> None:
    """②同批扣减:在手 4(bench 三月七×3 + deployed 丹恒)的三笔
    同名计划 = [可卖, 可卖, 拒](前序卖出递减计数,第三笔时 2≤tier)
    ——136 r7 批内聚合缺口的批量口径。"""
    sess = _sess()
    st = _state(bench=[_bc('三月七', 0), _bc('三月七', 1),
                       _bc('三月七', 2)],
                deployed=[_bc('丹恒·饮月', 9)])
    assert sole_engine_sell_floor_plan(
        [b for b in st.bench if b], st) == [False, False, True]
    # 在手 5 的三笔(列车 count=5)逐笔可卖不受辖(始终 >tier)
    st5 = _state(bench=[_bc('三月七', 0), _bc('三月七', 1),
                        _bc('三月七', 2)],
                 deployed=[_bc('三月七', 9), _bc('丹恒·饮月', 10)])
    assert sole_engine_sell_floor_plan(
        [b for b in st5.bench if b], st5) == [False, False, False]


# ===== 件③ execute_replacement 溢出留场 =====


def _overflow_state() -> GameState:
    """bench 满(9,新线成员=绯英·欢愉 + 8 银枝散件);deployed 旧线 =
    三月七+姬子(列车在手 2=tier,均保护件)→ 保留序截断 bench_free=1
    时另一件被划进 sold(修前)。"""
    bench = [_bc('绯英', 0, row='front')]
    bench += [_bc('银枝', i) for i in range(1, BENCH_CAPACITY)]
    st = _state(bench=bench,
                deployed=[_bc('三月七', 9, row='front'),
                          _bc('姬子', 10)])
    return st


def _train_cnt(pool) -> int:
    return sum(1 for b in pool if b and b.char_id and '列车同行'
               in set(CHARACTERS[b.char_id].factions)
               | set(CHARACTERS[b.char_id].flows))


def _verdict() -> UpgradeVerdict:
    opt = UpgradeOption('new_faction', '欢愉', 2, 9.0, True, '', 'board')
    return UpgradeVerdict(opt, True, True, True, True, 'test')


def test_overflow_sell_floor_keeps_tt_piece_in_hand() -> None:
    """③主锁:列车在手 2=tier,溢出卖出下界 → 被截断的保护件不卖而
    留场(retained 件照旧进 bench 回滚窗),列车在手数不跌破 tier,
    事务 applied。"""
    st = _overflow_state()
    acts = execute_replacement(_verdict(), st, None, None,
                               sell_floor=True)
    tx = acts[0]
    sold = {st.deployed[i].char_id for i, dm in tx.sell
            if dm == 'deployed'}
    assert sold == set(), f'TT 体系件(在手=tier)不可溢出卖出:{sold}'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    pool = [*out.bench, *out.deployed]
    assert _train_cnt(pool) == 2, '列车在手数不得跌破 tier(2)'
    # 留场语义:被截断件(未进 retained)仍 deployed,不下场不卖
    downed = {d.char_id for i, d in enumerate(st.deployed)
              if i in (tx.undeploy or [])}
    kept = ({'三月七', '姬子'} - downed)
    assert kept, '截断保护件应留场(不在 undeploy)'


def test_overflow_redundant_tt_still_sellable() -> None:
    """④冗余不辖:列车在手 3(>tier 2)时,溢出卖出冗余件照旧
    (体系有余量时清仓合法面,ADR-0373 不辖清单第 2 条保持)。"""
    st = _overflow_state()
    st.deployed = [*_overflow_state().deployed, _bc('丹恒·饮月', 11)]
    acts = execute_replacement(_verdict(), st, None, None,
                               sell_floor=True)
    tx = acts[0]
    sold = {st.deployed[i].char_id for i, dm in tx.sell
            if dm == 'deployed'}
    assert sold, '冗余 TT 件(在手>tier)溢出卖出应照旧'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    pool = [*out.bench, *out.deployed]
    assert _train_cnt(pool) >= 2, '卖出后列车在手仍 ≥tier'


def test_overflow_flag_off_restores_w195() -> None:
    """⑤off 臂:sell_floor=False 时截断保护件被卖出(=W195 后行为,
    136 r9 benchOcc=9 形态的构造性复现)。"""
    st = _overflow_state()
    acts = execute_replacement(_verdict(), st, None, None,
                               sell_floor=False)
    tx = acts[0]
    sold = {st.deployed[i].char_id for i, dm in tx.sell
            if dm == 'deployed'}
    assert sold, 'flag off:溢出卖出保护件应照旧(旧行为)'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied'
    pool = [*out.bench, *out.deployed]
    assert _train_cnt(pool) == 1, f'旧行为:列车在手跌破 tier:{pool}'
