# -*- coding: utf-8 -*-
"""test_cw_equip_flow 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w96_merge_progress: test_cw_w96_merge_progress.py
- w201_completion_dedup: test_cw_w201_completion_dedup.py
- adr0303_merge: test_cw_adr0303_merge.py
- w209_wear_synthesis: test_cw_w209_wear_synthesis.py
- w861_junk_first: test_cw_w861_junk_first.py
冲突改名:后来者顶层名/import 绑定加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w96_merge_progress ====================

from dataclasses import replace
from types import SimpleNamespace

import pytest


from sr_od.application.currency_war.sim.checks.ledger import check_overflow_gold_zero_buy_streak
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import generate_candidates
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY, DecisionV2Registry
from sr_od.application.currency_war.decision.decision_v2.scoring import score_candidate, score_state

_REG = DEFAULT_REGISTRY
_CARRY = '姬子·启行'          # 核心件(v3_core_names;line_carry)
_TARGET_FILLER = '花火'        # 目标件(锁线视窗内,非核心)
_FACTIONS = ('列车同行',)


def _bench(name: str, faction: str = '仙舟罗浮',
           slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _deployed(name: str, faction: str = '列车同行',
              star: int = 1, slot: int = 0) -> SimpleNamespace:
    return SimpleNamespace(char_id=name, faction=faction, star=star,
                           position_pref='back', equips=(), slot=slot)


def _shop_card(name: str, faction: str = '列车同行',
               cost: int = 4) -> SimpleNamespace:
    return SimpleNamespace(name=name, faction=faction, cost=cost,
                           x=0, star=1)


def _sess() -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import HoardTarget, IntentionState
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    s.v3_mode = 'economy'
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '姬子列车'
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset({'姬子·启行', '三月七', '花火', '瓦尔特'}),
        frozenset(), 'locked')
    s.v3_core_names = {'姬子·启行'}
    # 同轮买卖互斥守卫的 core 豁免面(target_comp;W93_报告 r9 帧吉尔伽美什=line_carry
    # 生成即此路径:core 显式保留 → 买副本合法)
    s.target_comp = SimpleNamespace(factions=_FACTIONS,
                                    core_chars=(_CARRY,))
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 9, 'gold': 60, 'level': 5,
            'board': {'列车同行': 2}, 'bench': [], 'shop': [], 'hp': 100}
    base.update(kw)
    return GameState(**base)


# --- 件1:merge_progress 项值 -------------------------------------------------


def test_merge_progress_term_values() -> None:
    """第 2 份显影、第 1 份不显影、star≥2 让位 core_star、非目标不显影。"""
    sess = _sess()
    # 1 份(bench):爬坡未开始
    st1 = _state(bench=[_bench(_TARGET_FILLER, slot=0)])
    assert score_state(st1, _REG, sess)['merge_progress'] == 0.0
    # 2 份纯 bench:折减权重
    st2b = _state(bench=[_bench(_TARGET_FILLER, slot=0),
                         _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st2b, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit * _REG.bench_form_weight)
    # 2 份含 deployed:全额
    st2d = _state(deployed=[_deployed(_TARGET_FILLER,
                                      faction='仙舟罗浮')],
                  bench=[_bench(_TARGET_FILLER, slot=0)])
    assert score_state(st2d, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit)
    # star≥2 持有:core_star 承接,本项让位(不双计)
    st_star2 = _state(bench=[_bench(_TARGET_FILLER, slot=0, star=2),
                             _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st_star2, _REG, sess)['merge_progress'] == 0.0
    assert score_state(st_star2, _REG, sess)['core_star'] > 0.0
    # 非目标件副本不显影([31] 反散件)
    st_off = _state(bench=[_bench('星期日', faction='盛会之星', slot=0),
                           _bench('星期日', faction='盛会之星', slot=1)])
    assert score_state(st_off, _REG, sess)['merge_progress'] == 0.0
    # unit=0 关闭(A/B 基线臂)
    reg_off = DecisionV2Registry(merge_progress_unit=0.0)
    assert score_state(st2d, reg_off, sess)['merge_progress'] == 0.0


def test_merge_progress_per_name_cap_second_copy_only() -> None:
    """每名只计一次(第 2 份,第 1 份不计);多名目标各计各的(不跨名合并)。"""
    sess = _sess()
    st = _state(deployed=[_deployed(_CARRY), _deployed(_TARGET_FILLER,
                                                      faction='仙舟罗浮')],
                bench=[_bench(_CARRY, faction='列车同行', slot=0),
                       _bench(_TARGET_FILLER, slot=1)])
    assert score_state(st, _REG, sess)['merge_progress'] == \
        pytest.approx(_REG.merge_progress_unit * 2)


# --- 件2:r9 病灶帧单帧锁(该买则买)-----------------------------------------


def test_r9_frame_second_copy_buy_scores_positive() -> None:
    """W93 r9 帧形态锁:deployed 核心件 1★ + 店内同名 1★ → 买入候选
    评分 >0(修前:候选生成但全维度零 delta,「非正分」拒——金 86
    溢出零买)。"""
    sess = _sess()
    st = _state(deployed=[_deployed(_CARRY)],
                shop=[_shop_card(_CARRY, cost=4)])
    cands = generate_candidates(st, sess, _REG)
    buy = [c for c in cands
           if c.action.__class__.__name__ == 'BuyCard'
           and c.action.card.name == _CARRY]
    assert buy, '核心件第 2 份候选应生成(r410 core 豁免面)'
    val, bd = score_candidate(buy[0], st, sess, _REG)
    assert val > 0, \
        f'第 2 份买入应正分(实际 {val},delta={bd["after"]})'
    assert bd['after']['merge_progress'] > bd['base']['merge_progress'], (
        '份数显影应构成 delta(基线 '
        f'{bd["base"]["merge_progress"]}'
        ' → 买后 '
        f'{bd["after"]["merge_progress"]})')


def test_r7_frame_generation_guard_unchanged() -> None:
    """W93 r7 帧形态锁(生成层不变式):deployed 非核心目标件的第 2 份
    在**授权窗外**仍不生成候选——同轮买卖互斥守卫未动(ADR-0303/0304 豁免默认
    关);生成层重估只写设计建议(W96_报告.md),归后续批。
    (语义演进史,ADR-0411:末窗承接缺口 gap>0 时同名副本候选经
    C 项定向授权放行——原构造帧恰落末窗缺口内,随 flag 家族清理转正
    后改用 r7 帧钉守卫基线;末窗放行行为由 test_cw_w242_star_directed
    锁。ADR-0418 gate_min_round 前移 8→6 后 r7 落进新授权窗
    {r6..r9},本锁用 replace 把 min_round 钉回 8 保住「非末窗守卫
    不动」的原边界意图——C 臂窗内放行行为另由 新窗锁覆盖。
    ADR-0438:copy_swap_target_exempt 开臂翻默认 True,本锁显式注入
    关臂钉「守卫直通」基线不变。)"""
    reg = replace(DEFAULT_REGISTRY, handoff_gate_min_round=8,
                  copy_swap_target_exempt=False)
    sess = _sess()
    st = _state(round_num=7,
                deployed=[_deployed(_TARGET_FILLER,
                                    faction='仙舟罗浮')],
                shop=[_shop_card(_TARGET_FILLER, faction='仙舟罗浮',
                                 cost=5)])
    cands = generate_candidates(st, sess, reg)
    names = {c.action.card.name for c in cands
             if c.action.__class__.__name__ == 'BuyCard'}
    assert _TARGET_FILLER not in names, \
        'r410 守卫行为不得被本批评分层改动波及(守卫未动)'


# --- 件3:溢出金断买检查器 ----------------------------------------------------


def _row(rn: int, gold: int, actions: list[dict],
         plane: int = 1, rid: str = 'r_test') -> dict:
    return {'plane': plane, 'round_num': rn, 'gold': gold,
            'actions': actions, 'state': {}, 'run_id': rid}


def _buy_row(name: str = '花火') -> dict:
    return {'__type__': 'BuyCard', 'reason': 'd2_line_carry',
            'card': {'name': name, 'cost': 5}}


def _lv_row() -> dict:
    return {'__type__': 'LevelUp'}


def test_checker_catches_w93_streak() -> None:
    """W93 病灶形态(r7-r9 金 59/70/86 三连零买)必须报。"""
    rows = [_row(7, 59, []), _row(8, 70, []), _row(9, 86, [])]
    v = check_overflow_gold_zero_buy_streak(rows)
    assert len(v) == 1 and '3 连' in v[0], f'三连断买未报(实际 {v})'


def test_checker_streak_requires_two_rounds() -> None:
    """单轮零买不报(金 51 单轮过线合法);金 ≤50 不计数。"""
    assert check_overflow_gold_zero_buy_streak(
        [_row(7, 55, [])]) == []
    assert check_overflow_gold_zero_buy_streak(
        [_row(7, 50, []), _row(8, 50, []), _row(9, 50, [])]) == []


def test_checker_spend_breaks_streak() -> None:
    """买入/升级都算花金([17] 滴漏不算冻结);P2 轮不辖。"""
    rows = [_row(7, 60, [_buy_row()]), _row(8, 70, [_lv_row()]),
            _row(9, 86, [])]
    assert check_overflow_gold_zero_buy_streak(rows) == []
    # P2 语义另裁:plane=2 的断买不计入 streak
    rows_p2 = [_row(7, 60, [], plane=2), _row(8, 70, [], plane=2)]
    assert check_overflow_gold_zero_buy_streak(rows_p2) == []


def test_checker_registered_in_batch_checks() -> None:
    """接线锁:检查器进 _BATCH_CHECKS(sim 批次 checks_violations 覆盖)。"""

    from sr_od.application.currency_war.sim.checks.runner import _BATCH_CHECKS
    assert _BATCH_CHECKS.get('overflow_gold_zero_buy_streak') \
        is check_overflow_gold_zero_buy_streak


# ==================== w201_completion_dedup ====================

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import EvolutionState, evolution_step
from sr_od.application.currency_war.kernel.cw_intention import IntentionState

from sr_od.application.currency_war.kernel.cw_battle_calib import _board_factions_of
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w201_completion_dedup_BenchChar, CompTransaction, GameState as _w201_completion_dedup_GameState, _recount_board, simulate
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _w201_completion_dedup_StrategySession


def _char(name: str, star: int = 1, row: str = 'back') -> _w201_completion_dedup_BenchChar:
    c = CHARACTERS[name]
    return _w201_completion_dedup_BenchChar(slot=0, char_id=name,
                     faction=(c.factions or ['?'])[0],
                     position_pref=row, star=star)


def _w201_completion_dedup_sess(pair: tuple[str, ...]) -> _w201_completion_dedup_StrategySession:
    sess = _w201_completion_dedup_StrategySession()
    sess.v3_intention = IntentionState(p1_pair=pair)
    return sess


# 非 DOT 散件占满 cap(与 W174 锁同款;DOT pair 缺口主体)
_B_FILLER = ('银枝', '刃', '镜流', '布洛妮娅', '阮·梅', '娜塔莎', '翡翠')


def _w201_completion_dedup_state(bench=(), deployed=_B_FILLER, level: int = 7,
           round_num: int = 4) -> _w201_completion_dedup_GameState:
    st = _w201_completion_dedup_GameState()
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
    st = _w201_completion_dedup_state(bench=(_char('椒丘', star=2), _char('椒丘', star=1),
                       _char('卡芙卡')))
    sess = _w201_completion_dedup_sess(('持续伤害', '仙舟'))
    txs = _completion_txs(evolution_step(st, sess, EvolutionState()))
    assert len(txs) == 1, 'DOT distinct owned(椒丘/卡芙卡)≥2 应发补完'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 同名只上一份:场上椒丘恰 1(且为高星那份)
    jqs = [d for d in out.deployed
           if d is not None and d.char_id == '椒丘']   # ADR-0392 滤 None
    assert len(jqs) == 1 and (jqs[0].star or 1) == 2
    # DOT on-board 达门槛(≥2)
    assert _board_factions_of(out.deployed).get('持续伤害', 0) >= 2


def test_distinct_owned_no_phantom_deficit():
    """②distinct 口径:bench 仅 椒丘×2 + 散件(全羁绊计数=2 但 distinct=1)
    → 幻影缺口不触发(distinct<tier=2,副本是 3合1 素材非配方件)。"""
    st = _w201_completion_dedup_state(bench=(_char('椒丘'), _char('椒丘'), _char('银枝')))
    sess = _w201_completion_dedup_sess(('持续伤害', '仙舟'))
    assert not _completion_txs(evolution_step(st, sess, EvolutionState()))


def test_distinct_flag_off_restores_full_count():
    """②flag off 回退:complete_distinct=False 回 W174 全羁绊逐件计数
    ——副本凑数也计 owned → 缺口触发,dedup 后部分补完(上 1 份椒丘,
    board DOT=1<2 的部分事务照发——旧口径行为面)。"""
    st = _w201_completion_dedup_state(bench=(_char('椒丘'), _char('椒丘'), _char('银枝')))
    sess = _w201_completion_dedup_sess(('持续伤害', '仙舟'))
    txs = _completion_txs(evolution_step(
        st, sess, EvolutionState(), complete_distinct=False))
    assert len(txs) == 1, '全羁绊计数 owned=2≥2 → 旧口径缺口应触发'
    out = simulate(st, txs[0])
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    # 部分补完:只上得了 1 份椒丘(distinct 供给只有 1)
    jqs = [d for d in out.deployed
           if d is not None and d.char_id == '椒丘']   # ADR-0392 滤 None
    assert len(jqs) == 1
    assert _board_factions_of(out.deployed).get('持续伤害', 0) == 1


# ==================== adr0303_merge ====================

from dataclasses import replace as _adr0303_merge_replace

from sr_od.application.currency_war.kernel.cw_bridge_pool import BRIDGE_POOL
from sr_od.application.currency_war.data.cw_chars import CHARACTERS as _adr0303_merge_CHARACTERS
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _adr0303_merge_BenchChar, GameState as _adr0303_merge_GameState, ShopCard
from sr_od.application.currency_war.decision.cw_strategy import StrategySession as _adr0303_merge_StrategySession
from sr_od.application.currency_war.decision.decision_v2 import candidates as _cands
from sr_od.application.currency_war.decision.decision_v2 import filters as _filters
from sr_od.application.currency_war.decision.decision_v2.candidates import generate_candidates as _adr0303_merge_generate_candidates
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY as _adr0303_merge_DEFAULT_REGISTRY

_adr0303_merge_REG = _adr0303_merge_DEFAULT_REGISTRY

# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True)。copy_swap 守卫锁与该通道无关,
# 锁守卫自身判据时注入关臂隔离 press 豁免臂。
_REG_NO_PRESS = _adr0303_merge_replace(_adr0303_merge_REG, press_channel_enabled=False)


def _adr0303_merge_sess() -> _adr0303_merge_StrategySession:
    s = _adr0303_merge_StrategySession()
    s.locked_line = None
    s.bridge_id = None
    return s


def _adr0303_merge_state(**kw) -> _adr0303_merge_GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 30, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return _adr0303_merge_GameState(**base)


def _buy_names(st: _adr0303_merge_GameState, sess: _adr0303_merge_StrategySession,
               reg: object | None = None) -> set[str]:
    """reg=None 用默认注册表;锁通道无关行为时传 _REG_NO_PRESS。"""
    use = _adr0303_merge_REG if reg is None else reg
    return {c.action.card.name for c in _adr0303_merge_generate_candidates(st, sess, use)
            if getattr(c.action, 'card', None) is not None}


# --- ① 常量上移 ---------------------------------------------------------------

# (原 test_crisis_constants_in_registry 逐值断言 crisis_hoard_gold==40 /
#  crisis_buy_bias==1.0 / crisis_buy_tags 集合 已并入
#  test_cw_adr0293_calibration 字段面锁——该表逐值辖危机三参(0293 明言
#  crisis 三参入表),独立逐值锁=双源漂移风险,重复构成删并理由(README
#  纪律 8);退场静态断言与 copy_swap 行为锁保留。)


def test_emergency_tags_merged_content() -> None:
    """应急集已并入 for_gold/levelup(ADR-0302 内容修正,合流落位)。"""
    assert {'for_gold', 'levelup'} <= _adr0303_merge_REG.emergency_tags
    # 应急集保持窄(ADR-0300):经济类仍滤出
    assert not ({'pair', 'copy', 'bond_fallback', 'synthesize'}
                & _adr0303_merge_REG.emergency_tags)


def test_filters_temp_constants_removed() -> None:
    """filters 暂驻常量已删(旧名残留=上移不彻底,双源即红)。"""
    for name in ('_EMERGENCY_EXTRA_TAGS', '_CRISIS_HOARD_GOLD',
                 '_CRISIS_BUY_BIAS', '_CRISIS_BUY_TAGS'):
        assert not hasattr(_filters, name), (
            f'filters.{name} 残留:危机常量应只在 registry(ADR-0303)')


# --- ② copy_swap 守卫×目标件豁免 ------------------------------------------------


def _target_and_non_target() -> tuple[str, str]:
    """目标件(桥 fixed∪core,无方向种子态口径)与非目标件载体。"""
    target = next(n for c in BRIDGE_POOL for n in c.fixed)
    non_target = '佩拉'   # 引擎阵营但非桥池件(0300 测试同款载体)
    assert non_target not in {n for c in BRIDGE_POOL
                              for n in set(c.fixed) | set(c.core)}
    return target, non_target


def test_copy_swap_exempts_onboard_target_piece() -> None:
    """锁(ADR-0304 语义化:豁免默认关,开关打开才放行):registry
    copy_swap_target_exempt=True 时目标件在场第 2 份不被守卫拦
    (第 2 份语义=3合1 素材/阵容深度,批㉞ M2:483 次误拦)。"""
    from dataclasses import replace as _adr0303_merge_replace
    target, _nt = _target_and_non_target()
    ch = _adr0303_merge_CHARACTERS[target]
    sess = _adr0303_merge_sess()   # 无方向:桥 fixed∪core 全是目标(保护集口径)
    sess.target_comp = None   # v1 守卫判据下本会被拦(豁免才放行)
    st = _adr0303_merge_state(
        board={ch.factions[0]: 1},
        deployed=[_adr0303_merge_BenchChar(slot=0, char_id=target,
                            faction=ch.factions[0], position_pref='back')],
        shop=[ShopCard(x=0, name=target, faction=ch.factions[0],
                       cost=ch.cost)],
    )
    # 镜像:v1 守卫本身会拦(target_comp=None 无保留判据)
    assert _cands._copy_swap_useless(st.shop[0], st, sess)
    # 回退态(旧 ADR-0304 裁决;ADR-0438 已开臂翻默认 True——历史
    # 「默认关守卫直通」锁随语义演进改显式注入关臂;开臂依据=W436
    # A/B:生成通道打通后本开关买率 +9.15pp 显著/守卫全净)
    # 注入关臂隔离 press 豁免臂(默认注册表该臂会放行 band 内副本)
    assert _adr0303_merge_REG.copy_swap_target_exempt
    assert _cands._copy_swap_blocked(
        st.shop[0], st, sess,
        _adr0303_merge_replace(_REG_NO_PRESS, copy_swap_target_exempt=False))
    assert target not in _buy_names(
        st, sess, _adr0303_merge_replace(_REG_NO_PRESS, copy_swap_target_exempt=False))
    # 开关开(ADR-0303 豁免,A/B 通道):不拦 + 买候选生成
    reg_on = _adr0303_merge_replace(_adr0303_merge_REG, copy_swap_target_exempt=True)
    assert not _cands._copy_swap_blocked(st.shop[0], st, sess, reg_on)
    assert target in {c.action.card.name
                      for c in _adr0303_merge_generate_candidates(st, sess, reg_on)
                      if getattr(c.action, 'card', None) is not None}


def test_copy_swap_still_blocks_non_target_piece() -> None:
    """锁:非目标件在场第 2 份照旧被拦(v1 r410 判据不动;豁免=
    目标件名单交叉,非守卫整体下线——开/关两态皆拦)。"""
    from dataclasses import replace as _adr0303_merge_replace
    _t, non_target = _target_and_non_target()
    ch = _adr0303_merge_CHARACTERS[non_target]
    sess = _adr0303_merge_sess()
    sess.target_comp = None
    st = _adr0303_merge_state(
        board={ch.factions[0]: 1},
        deployed=[_adr0303_merge_BenchChar(slot=0, char_id=non_target,
                            faction=ch.factions[0], position_pref='back')],
        shop=[ShopCard(x=0, name=non_target, faction=ch.factions[0],
                       cost=ch.cost)],
    )
    assert _cands._copy_swap_useless(st.shop[0], st, sess)
    assert _cands._copy_swap_blocked(st.shop[0], st, sess, _REG_NO_PRESS)
    reg_on = _adr0303_merge_replace(_REG_NO_PRESS, copy_swap_target_exempt=True)
    assert _cands._copy_swap_blocked(st.shop[0], st, sess, reg_on)
    assert non_target not in _buy_names(st, sess, _REG_NO_PRESS)
    assert non_target not in {
        c.action.card.name
        for c in _adr0303_merge_generate_candidates(st, sess, reg_on)
        if getattr(c.action, 'card', None) is not None}


# ==================== w209_wear_synthesis ====================

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.kernel.cw_bench_equips import assert_equips_consistency, wear_synthesis_equivalent
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w209_wear_synthesis_BenchChar


def test_run26_self_recipe_equivalent() -> None:
    """实锤①:账面 [量产型装甲×2] ↔ 画面 [很硬的甲](自配)。"""
    assert wear_synthesis_equivalent(['量产型装甲', '量产型装甲'], ['很硬的甲'])


def test_run26_cross_recipe_equivalent() -> None:
    """实锤②:账面 [光能电池,生命之花] ↔ 画面 [绝对热量](交叉)。"""
    assert wear_synthesis_equivalent(['光能电池', '生命之花'], ['绝对热量'])


def test_multistep_closure() -> None:
    """闭包:多次合成链(组件×3 → 进阶+组件 → 再合成)可达即等价。"""
    # 量产型装甲×3 → 很硬的甲 + 装甲×1(不可再合)≠ [很硬的甲];
    # 但 组件A×2 合成后恰与第三件再交叉的场景可达:
    # 光能电池×2 → 永动机(自配),再与任意件共存 = [永动机, X]
    assert wear_synthesis_equivalent(['光能电池', '光能电池', '生命之花'],
                                     ['永动机', '生命之花'])


def test_no_recipe_not_equivalent() -> None:
    """无配方关联的多重集不等价(豁免不得放水)。"""
    assert not wear_synthesis_equivalent(['光能电池'], ['永动机'])  # 单件不够自配
    assert not wear_synthesis_equivalent(['甲', '乙'], ['丙'])      # 未知配方
    assert not wear_synthesis_equivalent([], ['很硬的甲'])
    assert not wear_synthesis_equivalent(['很硬的甲'], ['很硬的甲', '很硬的甲'])
    # 反向(账面进阶 画面组件)不等价——合成不可逆
    assert not wear_synthesis_equivalent(['很硬的甲'], ['量产型装甲', '量产型装甲'])


def test_assert_consistency_exempt_and_real_mismatch() -> None:
    """assert_equips_consistency:等价豁免不 raise;真漂移照 raise。"""
    c = _w209_wear_synthesis_BenchChar(slot=1, char_id='风堇', position_pref='back')
    c.equips = ['量产型装甲', '量产型装甲']
    assert_equips_consistency(c, ['很硬的甲'], 'test')   # 豁免
    c2 = _w209_wear_synthesis_BenchChar(slot=2, char_id='卡芙卡', position_pref='back')
    c2.equips = ['光能电池']
    try:
        assert_equips_consistency(c2, ['永动机'], 'test')
        raise SystemExit('should raise')
    except SystemExit:
        raise
    except Exception:
        pass   # EquipsInconsistencyError 预期


# ==================== w861_junk_first ====================

from types import SimpleNamespace as _w861_junk_first_SimpleNamespace

from sr_od.application.currency_war.data.affix_effects_data import AFFIX_EFFECTS
from sr_od.application.currency_war.data.cw_synthesis import component_demand, recycle_qualified, synthesize_target
from sr_od.application.currency_war.kernel.cw_junk_first import JUNK_FIRST_AFFIX, JUNK_FIRST_DEFER_BUDGET, apply_junk_first, find_high_value_completions, find_sacrifice_pair, junk_first_allocation, junk_first_env_active, worn_basics_by_char
from sr_od.application.currency_war.kernel.cw_state import BenchChar as _w861_junk_first_BenchChar

# 阿雅需求线(w211 同例):key 组件 = 轮滑鞋×5 + 折叠小刀×1;
# 回收合格 = 以太钻头/光能电池/和平手枪/幸运星/生命之花/量产型装甲
_K_AYA = ['反重力皮靴', '反重力皮靴', '白昼·光速螺旋桨', '火力风暴潮']


def _mkcomp(key_equips: list[str], cores: list[str]):
    from sr_od.application.currency_war.kernel.cw_comps import Comp
    return Comp(name='伪comp', factions=['追击'], core_chars=cores,
                form_tiers={'追击': 2}, strength='S',
                form_difficulty='easy', key_equips=key_equips)


def _aya_pair() -> tuple[str, str]:
    """阿雅回收合格集内一对真实互为配方的基础件(锁语义不锁具体对)。"""
    rq = sorted(recycle_qualified(_K_AYA))
    pair = next(((a, b) for a in rq for b in rq
                 if a != b and synthesize_target(a, b) is not None), None)
    assert pair is not None, '图谱前提:阿雅死库存内存在可配对'
    return pair


# ===== 1. 环境判据 =====

def test_env_active_contains() -> None:
    assert junk_first_env_active([JUNK_FIRST_AFFIX, '其他词缀'])
    assert junk_first_env_active(['其他词缀', JUNK_FIRST_AFFIX])


def test_env_inactive_defaults_safe() -> None:
    """读不到(空/None/其他词缀)= 无该环境 → 不启用(安全默认)。"""
    assert not junk_first_env_active([])
    assert not junk_first_env_active(None)
    assert not junk_first_env_active(['库藏生锈', '倒计时'])


# ===== 2. 牺牲排序(sacrifice_first)=====

def test_high_value_completion_detection() -> None:
    """core 已穿 轮滑鞋,本趟发 折叠小刀 → 完成高价值合成 火力风暴潮(∈key)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('三月七', '以太钻头'), ('阿雅', '折叠小刀')]
    assert find_high_value_completions(alloc, worn, comp) == [1]


def test_sacrifice_pair_ordered_before_high_value() -> None:
    """牺牲对(死库存配方对,非 core 共位)两条分配移到队首——
    拖拽序 = 合成事件序,牺牲合成先消耗垃圾化,高价值合成免触发。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    a, b = _aya_pair()
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀'), ('三月七', a), ('三月七', b)]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'sacrifice_first'
    assert new_alloc[0][1] in (a, b) and new_alloc[1][1] in (a, b), \
        f'牺牲对必须先于高价值合成: {new_alloc}'
    assert new_alloc[-1] == ('阿雅', '折叠小刀')
    assert sorted(map(tuple, new_alloc)) == sorted(map(tuple, alloc)), '成员无损'


def test_sacrifice_pair_with_worn_partner_moved_front() -> None:
    """对的一件已在前帧穿上(非 core),本趟只发另一件 → 该条分配移队首。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    a, b = _aya_pair()
    worn = {'阿雅': ['轮滑鞋'], '三月七': [a]}
    alloc = [('阿雅', '折叠小刀'), ('三月七', b)]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'sacrifice_first'
    assert new_alloc == [('三月七', b), ('阿雅', '折叠小刀')]


def test_sacrifice_pair_rejects_mainline_components() -> None:
    """主线组件(需求向量内,非回收合格)不当牺牲对:绝对热量 = 光能电池+
    生命之花,都 ∈ 绝对热量需求 → 即便非 core 共位也不牺牲(不碰主线凑件)。"""
    comp = _mkcomp(['绝对热量'], ['飞霄'])
    demand = set(component_demand(['绝对热量']))
    assert {'光能电池', '生命之花'} <= demand
    worn = {'三月七': ['光能电池']}
    alloc = [('三月七', '生命之花')]
    assert find_sacrifice_pair(alloc, worn, comp) is None


# ===== 3. 无牺牲对推迟一帧 =====

def test_defer_without_sacrifice_pair() -> None:
    """无牺牲对 → 高价值完成件本帧不出分配(件留 owned 等死库存对)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀')]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 1)
    assert action == 'deferred' and new_alloc == []


def test_defer_budget_exhausted_releases() -> None:
    """预算耗尽(推迟一帧上限)→ 原样放行(接受垃圾化风险,防无限等)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    worn = {'阿雅': ['轮滑鞋']}
    alloc = [('阿雅', '折叠小刀')]
    new_alloc, action = apply_junk_first(alloc, worn, comp, True, 0)
    assert action == 'budget_exhausted' and new_alloc == alloc


def test_defer_budget_per_plane_and_mechanism_truth_in_registry() -> None:
    """机制真值单一源锁:词缀效果在 affix_effects_data 注册表内为游戏原文
    (每位面首次进阶合成 / 50% / 垃圾袋)——禁第二数据源;推迟预算=每位面
    1 帧(50% × 进阶件损失 ≫ 一帧推迟成本,预算只防无限推迟)。"""
    effect = AFFIX_EFFECTS['变宝为废']
    assert '每个位面开始时' in effect and '首次合成' in effect
    assert '50%' in effect and '垃圾袋' in effect
    assert JUNK_FIRST_DEFER_BUDGET == 1


# ===== 4. 缺环境 / 开关关不启用(零漂移锚)=====

def _dep() -> list:
    return [_w861_junk_first_BenchChar(slot=1, char_id='阿雅', position_pref='back'),
            _w861_junk_first_BenchChar(slot=2, char_id='三月七', position_pref='front')]


def test_disabled_env_returns_base_alloc() -> None:
    """环境不在场:开关开也返回基分配(安全默认不启用)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = _w861_junk_first_SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = _w861_junk_first_SimpleNamespace(junk_first_done_plane=None)
    a, b = _aya_pair()
    base = junk_first_allocation(sess, reg, comp, _dep(),
                                 [a, b, '轮滑鞋', '折叠小刀'], None, [])
    enabled = junk_first_allocation(sess, reg, comp, _dep(),
                                    [a, b, '轮滑鞋', '折叠小刀'], None,
                                    [JUNK_FIRST_AFFIX])
    assert base == enabled


def test_disabled_switch_zero_drift() -> None:
    """开关关(默认):环境在场也返回基分配 = equip_allocation 原语义(零漂移锚)。"""
    from sr_od.application.currency_war.kernel.cw_comps import equip_allocation
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = _w861_junk_first_SimpleNamespace(junk_first_sacrifice_enabled=False)
    sess = _w861_junk_first_SimpleNamespace(junk_first_done_plane=None)
    a, b = _aya_pair()
    owned = [a, b, '轮滑鞋', '折叠小刀']
    got = junk_first_allocation(sess, reg, comp, _dep(), owned, None,
                                [JUNK_FIRST_AFFIX])
    assert got == equip_allocation(comp, _dep(), owned, None)


def test_registry_switch_defaults_off_lifecycle_state1() -> None:
    """开关默认关 = 生命周期第 1 态(落码默认关+开臂判据挂账,禁悬置):
    开臂判据=环境读取通道稳定+牺牲对识别可靠(阈值见 registry 字段注释)。"""
    import dataclasses
    from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY, DecisionV2Registry
    fld = {f.name: f for f in dataclasses.fields(DecisionV2Registry)}
    assert 'junk_first_sacrifice_enabled' in fld
    assert fld['junk_first_sacrifice_enabled'].default is False
    assert getattr(DEFAULT_REGISTRY, 'junk_first_sacrifice_enabled') is False


def _w861_junk_first_sess(plane: int | None) -> _w861_junk_first_SimpleNamespace:
    """带 last_state.plane 的最小 session(位面消耗记账的宿主形态)。"""
    last = _w861_junk_first_SimpleNamespace(plane=plane) if plane is not None else None
    return _w861_junk_first_SimpleNamespace(last_state=last, junk_first_done_plane=None)


def test_wrapper_plane_consumption_once_per_plane() -> None:
    """位面消耗记账(机制=每位面首次合成各判定一次):
    P1 推迟一次后记账;同位面后续帧不再推迟(判定已消耗);
    进位面 2 → 风险窗口重开,可再推迟一次并记账 P2。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = _w861_junk_first_SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = _w861_junk_first_sess(1)
    got = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                {('back', 1): ['轮滑鞋']},
                                [JUNK_FIRST_AFFIX])
    assert got == [] and sess.junk_first_done_plane == 1
    got2 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got2 == [('阿雅', '折叠小刀')], '同位面判定已消耗,不再推迟'
    sess.last_state.plane = 2
    got3 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got3 == [] and sess.junk_first_done_plane == 2, \
        'P2 首次合成风险独立,推迟预算重开'


def test_wrapper_plane_unreadable_consumed_once() -> None:
    """位面读不到(None):首次动作后记哨兵,后续帧按已消耗降级
    (整局一次,防位面不可读时无限推迟)。"""
    comp = _mkcomp(_K_AYA, ['阿雅'])
    reg = _w861_junk_first_SimpleNamespace(junk_first_sacrifice_enabled=True)
    sess = _w861_junk_first_sess(None)
    got = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                {('back', 1): ['轮滑鞋']},
                                [JUNK_FIRST_AFFIX])
    assert got == [] and sess.junk_first_done_plane == -1
    got2 = junk_first_allocation(sess, reg, comp, _dep(), ['折叠小刀'],
                                 {('back', 1): ['轮滑鞋']},
                                 [JUNK_FIRST_AFFIX])
    assert got2 == [('阿雅', '折叠小刀')], '哨兵后不再推迟'


def test_worn_basics_projection() -> None:
    """(row,slot) 占用 + deployed 身份 → 角色名已穿基础件投影(非基础件滤除)。"""
    dep = [_w861_junk_first_BenchChar(slot=1, char_id='阿雅', position_pref='back')]
    worn = worn_basics_by_char(dep, {('back', 1): ['轮滑鞋', '火力风暴潮']})
    assert worn == {'阿雅': ['轮滑鞋']}
