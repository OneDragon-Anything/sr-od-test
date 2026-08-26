# -*- coding: utf-8 -*-
"""W201/ADR-0381 补完修法①② 单帧锁(同名去重 + distinct 口径)。

锁验收(锁契约不锁分布):
1. 修①(无 flag 实 bug):bench 持同名两份副本(都未在场)时,
   deploy 列表内同名只上一份(最高星)——simulate applied 无
   duplicate_on_board 拒(旧版双副本同进列表被整事务拒 → 退避关窗,
   W200:13/144/204 三局搁浅);
2. 修②(flag ``engine_complete_distinct_owned``):缺口 owned 口径
   distinct 名单数——同名副本是 3合1 升星素材非配方件([20] 配方=
   不同成员),distinct<tier = 幻影缺口不触发补完;
3. flag off(complete_distinct=False)回 W174 后全羁绊逐件计数
   (副本凑数也计 owned → 缺口触发,部分补完上场)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_evolution import (
    EvolutionState,
    evolution_step,
)
from sr_od.application.currency_war.cw_intention import IntentionState
from sr_od.application.currency_war.cw_sim import _board_factions_of
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
)
from sr_od.application.currency_war.cw_strategy import StrategySession


def _char(name: str, star: int = 1, row: str = 'back') -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _sess(pair: tuple[str, ...]) -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(p1_pair=pair)
    return sess


# 非 DOT 散件占满 cap(与 W174 锁同款;DOT pair 缺口主体)
_B_FILLER = ('银枝', '刃', '镜流', '布洛妮娅', '阮·梅', '娜塔莎', '翡翠')


def _state(bench=(), deployed=_B_FILLER, level: int = 7,
           round_num: int = 4) -> GameState:
    st = GameState()
    st.plane = 1
    st.round_num = round_num
    st.level = level
    st.gold = 30
    st.bench = list(bench)
    st.deployed = [(_char(n, row='front') if i < 3 else _char(n))
                   for i, n in enumerate(deployed)]
    st.board = _recount_board(st.deployed)
    return st


def _completion_txs(actions: list) -> list[CompTransaction]:
    return [a for a in actions if isinstance(a, CompTransaction)
            and 'engine_complete' in (a.reason or '')]


def test_dedup_same_name_copies_single_deploy():
    """①列表内同名去重:bench 椒丘×2(2★/1★)+卡芙卡,DOT 缺口 2 →
    同名只上最高星一份(另一份留 bench),simulate applied 无
    duplicate_on_board——旧版双副本同进 deploy 列表被整事务拒。"""
    st = _state(bench=(_char('椒丘', star=2), _char('椒丘', star=1),
                       _char('卡芙卡')))
    sess = _sess(('持续伤害', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert len(txs) == 1, 'DOT distinct owned(椒丘/卡芙卡)≥2 应发补完'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 同名只上一份:场上椒丘恰 1(且为高星那份)
    jqs = [d for d in out.deployed if d.char_id == '椒丘']
    assert len(jqs) == 1 and (jqs[0].star or 1) == 2
    # DOT on-board 达门槛(≥2)
    assert _board_factions_of(out.deployed).get('持续伤害', 0) >= 2


def test_distinct_owned_no_phantom_deficit():
    """②distinct 口径:bench 仅 椒丘×2 + 散件(全羁绊计数=2 但 distinct=1)
    → 幻影缺口不触发(distinct<tier=2,副本是 3合1 素材非配方件)。"""
    st = _state(bench=(_char('椒丘'), _char('椒丘'), _char('银枝')))
    sess = _sess(('持续伤害', '仙舟'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_distinct_flag_off_restores_full_count():
    """②flag off 回退:complete_distinct=False 回 W174 全羁绊逐件计数
    ——副本凑数也计 owned → 缺口触发,dedup 后部分补完(上 1 份椒丘,
    board DOT=1<2 的部分事务照发——旧口径行为面)。"""
    st = _state(bench=(_char('椒丘'), _char('椒丘'), _char('银枝')))
    sess = _sess(('持续伤害', '仙舟'))
    txs = _completion_txs(evolution_step(
        st, sess, EvolutionState(), complete_distinct=False))
    assert len(txs) == 1, '全羁绊计数 owned=2≥2 → 旧口径缺口应触发'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 部分补完:只上得了 1 份椒丘(distinct 供给只有 1)
    jqs = [d for d in out.deployed if d.char_id == '椒丘']
    assert len(jqs) == 1
    assert _board_factions_of(out.deployed).get('持续伤害', 0) == 1
