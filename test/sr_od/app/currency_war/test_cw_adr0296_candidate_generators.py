# -*- coding: utf-8 -*-
"""ADR-0296 候选生成补完锁(sell/synthesize 两通道)。

锁定对象(decision_v2/candidates.py,ADR-0296):
① sell 生成器:标签正确性(off_target 常态死库存 / for_gold 应急态
   弱件 / free_bench 腾位让位)+ 引擎件无阵营级卖禁(件值经评分层
   板面形态显影);
② 豁免过滤(v1 卖通道语义对齐,生成器层):r408 同轮已买(3合1
   ≥3 让位豁免放行)/ engine_seed 2 轮年龄窗 / 完整 3合1 份素材;
③ synthesize 独立生成器:全场域(bench∪deployed)同名同星 ≥3 →
   每组一候选(cw_state._merge_bench 口径镜像);不足 3 份/混星不生成;
④ 检查项 decision_v2_candidate_coverage 结构层转绿(ADR-0294 豁免
   表移除的依据)。
"""
from __future__ import annotations

from sr_od.application.currency_war.cw_sim_checks import (
    check_decision_v2_candidate_coverage,
)
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import (
    Synthesize,
    generate_candidates,
)
from sr_od.application.currency_war.decision_v2.registry import (
    DEFAULT_REGISTRY,
)

_REG = DEFAULT_REGISTRY


def _sess(line: str | None = None) -> StrategySession:
    s = StrategySession()
    s.locked_line = line
    s.bridge_id = None
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {'仙舟': 2}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sell_tags(st: GameState, sess: StrategySession) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in generate_candidates(st, sess, _REG):
        if c.tag in ('off_target', 'for_gold', 'free_bench'):
            out[c.breakdown_hint.get('name', '')] = c.tag
    return out


# --- ① sell 标签正确性 ------------------------------------------------------


def test_sell_off_target_normal_state() -> None:
    """常态:非目标 bench 件 → off_target(引擎阵营件无卖禁——旧
    engine 阵营级保护删除,件值交评分层;青雀=仙舟引擎阵营)。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟')])
    assert _sell_tags(st, sess) == {'青雀': 'off_target'}


def test_sell_target_piece_not_sellable() -> None:
    """目标件(锁线 opportunistic)常态不生成卖候选。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=0, char_id='娜塔莎', faction='护盾')])
    assert '娜塔莎' not in _sell_tags(st, sess)


def test_sell_for_gold_emergency() -> None:
    """应急态(hp≤emergency_hp):非目标弱件 → for_gold(折现换金)。"""
    sess = _sess(line='jizi')
    st = _state(hp=20, bench=[
        BenchChar(slot=0, char_id='青雀', faction='仙舟')])
    assert _sell_tags(st, sess) == {'青雀': 'for_gold'}


def test_sell_free_bench_full_target_yields() -> None:
    """bench 满:目标件也降保护集让位(free_bench,v1 carry 腾位门
    语义);非目标件在 bench 满时同样 free_bench 语义域。"""
    sess = _sess(line='jizi')
    bench = [BenchChar(slot=i, char_id='娜塔莎' if i == 0 else '青雀',
                       faction='护盾' if i == 0 else '仙舟')
             for i in range(_REG.bench_capacity)]
    st = _state(bench=bench)
    tags = _sell_tags(st, sess)
    assert tags.get('娜塔莎') == 'free_bench', \
        f'bench 满时目标件应让位:{tags}'


# --- ② 豁免过滤(v1 语义对齐,生成器层)------------------------------------


def test_sell_blocked_same_round_bought_r408() -> None:
    """r408:同轮已买件不生成卖候选;同名 ≥3 份(让位语境)放行。"""
    sess = _sess(line='jizi')
    sess.v2_round_key = (1, 5)
    sess.v2_round_bought = {'青雀'}
    st = _state(bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟')])
    assert '青雀' not in _sell_tags(st, sess), '同轮已买不卖(r408)'
    # 3合1 让位豁免:3 份(其中含同轮买入)→ 放行(free_bench 域外
    # 不可卖因素材豁免,构造 4 份冗余语境 → 可卖)
    st2 = _state(bench=[BenchChar(slot=i, char_id='青雀', faction='仙舟')
                        for i in range(4)])
    assert '青雀' in _sell_tags(st2, sess), \
        '同轮买 ≥3 份让位语境应放行(r408 豁免边)'


def test_sell_blocked_seed_age_window() -> None:
    """ADR-0289 §5:买入 ≤2 轮的种子(engine_seed)不进可卖集。"""
    sess = _sess(line='jizi')
    sess.v2_seed_bought = {'青雀': ((1, 3), 1)}   # r3 买 1 份
    st = _state(round_num=4, bench=[
        BenchChar(slot=0, char_id='青雀', faction='仙舟')])
    assert '青雀' not in _sell_tags(st, sess), '种子 2 轮窗内不卖'
    st3 = _state(round_num=7, bench=[   # r7 = 买后第 4 轮 → 可卖
        BenchChar(slot=0, char_id='青雀', faction='仙舟')])
    assert _sell_tags(st3, sess).get('青雀') == 'off_target'


def test_sell_blocked_complete_merge_material() -> None:
    """3合1 素材豁免:同名星级加权恰 3 份(完整合成份)不卖;
    >3 冗余份可卖(v1 copies>cap 优先腾语义)。"""
    sess = _sess(line='jizi')
    st = _state(bench=[BenchChar(slot=i, char_id='青雀', faction='仙舟')
                       for i in range(3)])
    assert '青雀' not in _sell_tags(st, sess), '完整 3合1 份不拆卖'
    st4 = _state(bench=[BenchChar(slot=i, char_id='青雀', faction='仙舟')
                        for i in range(4)])
    assert '青雀' in _sell_tags(st4, sess), '第 4 份冗余可卖'


# --- ③ synthesize 独立生成器 ------------------------------------------------


def test_synthesize_full_field_group() -> None:
    """全场域同名同星 ≥3(bench 2 + deployed 1)→ 每组一个候选
    (cw_state._merge_bench 口径镜像;ADR-0296)。"""
    sess = _sess(line='jizi')
    st = _state(
        bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟')],
        deployed=[BenchChar(slot=0, char_id='青雀', faction='仙舟')],
    )
    syn = [c for c in generate_candidates(st, sess, _REG)
           if c.tag == 'synthesize']
    assert len(syn) == 1
    assert isinstance(syn[0].action, Synthesize)
    assert syn[0].action.name == '青雀' and syn[0].action.star == 1
    assert syn[0].action.copies == 3 and syn[0].merge


def test_synthesize_insufficient_or_mixed_star() -> None:
    """不足 3 份 / 同名混星(2+1 不成组)不生成。"""
    sess = _sess(line='jizi')
    st = _state(
        bench=[BenchChar(slot=0, char_id='青雀', faction='仙舟'),
               BenchChar(slot=1, char_id='青雀', faction='仙舟',
                         star=2)],
        deployed=[BenchChar(slot=0, char_id='青雀', faction='仙舟')],
    )
    assert not [c for c in generate_candidates(st, sess, _REG)
                if c.tag == 'synthesize']


# --- ④ 检查项转绿锁 --------------------------------------------------------


def test_candidate_coverage_check_green() -> None:
    """decision_v2_candidate_coverage 结构层 0 违规(ADR-0294 豁免
    表移除的依据;红 = 生成器覆盖面回归)。"""
    r = check_decision_v2_candidate_coverage()
    assert r['violations'] == 0, f'{r}'
    assert set(r['struct_classes']) >= {'buy', 'sell', 'synthesize',
                                        'levelup', 'refresh', 'deploy'}
