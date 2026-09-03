# -*- coding: utf-8 -*-
"""test_cw_buy_sell 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- buy_reason: test_cw_buy_reason.py
- w150_buy_lock_constraint: test_cw_w150_buy_lock_constraint.py
- w184_sole_engine_sell_guard: test_cw_w184_sole_engine_sell_guard.py
- w197_sell_floor_exec: test_cw_w197_sell_floor_exec.py
- w209_offtarget_sell_guard: test_cw_w209_offtarget_sell_guard.py
- w423_revoke_evidence: test_cw_w423_revoke_evidence.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== buy_reason ====================

from sr_od.application.currency_war.kernel.cw_line_defs import classify_buy
from sr_od.application.currency_war.kernel.cw_state import BenchChar, BuyCard, GameState, ShopCard


def _st(board: dict[str, int] | None = None, bench: list[BenchChar] | None = None) -> GameState:
    st = GameState()
    st.plane, st.round_num, st.level, st.gold = 1, 1, 3, 10
    st.board = board or {}
    st.bench = bench or []
    return st


def test_buy_card_has_reason_field() -> None:
    """BuyCard.reason 字段存在且默认空(旧调用兼容)。"""
    c = BuyCard(card=ShopCard(x=0, faction='仙舟', name='爻光', cost=1))
    assert c.reason == ''


def test_classify_coldstart_bridge_vs_off() -> None:
    """局49 判据面:冷启动(板面空+bench 空)身份分类。

    桥名单件=bridge_seed;引擎阵营=engine;线外杂卡=off——
    r368 门=白名单 {bridge_seed, engine},检查端读同源标签。
    """
    st = _st()   # 全空 = 冷启动形态
    # 桥名单件(P1 BRIDGE_POOL fixed∪core 成员,如 丹恒·饮月)
    assert classify_buy(ShopCard(x=0, faction='仙舟', name='丹恒·饮月', cost=1), st) == 'bridge_seed'
    # 引擎阵营件(非桥名单但属 ENGINE_FACTIONS)
    assert classify_buy(ShopCard(x=1, faction='持续伤害', name='卡芙卡', cost=2), st) in ('bridge_seed', 'engine')
    # 线外杂卡(局49 形态:盛会之星/公司)
    assert classify_buy(ShopCard(x=2, faction='公司', name='翡翠', cost=1), st) == 'off'


def test_classify_pair_when_owned() -> None:
    """非冷启动:同阵营=pair;桥名单件优先 bridge_seed(分类序:
    bridge_seed > engine > pair——桥名单件即使已拥有阵营也标
    桥身份,检查端判「方向件」时两类都算)。"""
    st = _st(board={'仙舟': 1})
    # 藿藿 ∈ 桥名单核心 → bridge_seed(优先于 pair)
    assert classify_buy(ShopCard(x=0, faction='仙舟', name='藿藿', cost=1), st) == 'bridge_seed'
    # 非桥名单的板面同阵营件 → pair
    assert classify_buy(ShopCard(x=1, faction='公司', name='托帕', cost=1),
                        _st(board={'公司': 1})) == 'pair'


def test_coldstart_gate_consumes_classify() -> None:
    """r368 门消费 classify_buy 单一源(门=白名单 label 集)。"""
    import inspect

    from sr_od.application.currency_war.decision.decision_v2 import discipline
    src = inspect.getsource(discipline.pair_wants)
    assert 'classify_buy' in src, 'r368 冷启动门应收口 classify_buy(防第二源)'


# ==================== w150_buy_lock_constraint ====================

from dataclasses import replace

from sr_od.application.currency_war.kernel.cw_intention import (
    HoardTarget,
    IntentionState,
    _pair_members,
    locked_buy_scope,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    _off_lock_demotion,
    score_candidate,
)

_REG = DEFAULT_REGISTRY
_REG_OFF = replace(DEFAULT_REGISTRY, buy_lock_constraint_enabled=False)


def _pair_sess(pair: tuple[str, ...]) -> StrategySession:
    """P1 配方锁定帧会话(p1_pair 非空;hoard=对成员集,生产真实形态)。"""
    s = StrategySession()
    ist = IntentionState()
    ist.p1_pair = pair
    s.v3_intention = ist
    s.v3_hoard = HoardTarget(
        frozenset(_pair_members(pair)), frozenset(), 'p1_pair')
    return s


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'level': 5, 'gold': 60,
            'hp': 80, 'board': {'仙舟': 2},
            'deployed': [BenchChar(slot=0, char_id='青雀', faction='仙舟')],
            'bench': [None] * 9}
    base.update(kw)
    st = GameState(**base)
    return st


def _cand(name: str, tag: str, faction: str, cost: int) -> Candidate:
    return Candidate(
        action=BuyCard(ShopCard(x=1, name=name, faction=faction, cost=cost),
                       reason=''),
        tag=tag, source='shop', breakdown_hint={'cost': cost})


# --- ① 锁定帧降级(候选 A) ---------------------------------------------------


def test_locked_pair_offscope_opportunistic_demoted() -> None:
    """锁定帧(仙舟+DOT 对)的非目标件(三月七=列车,引擎件但∉对)
    line_opportunistic 候选降级:评分 −penalty,bd 记依据。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(shop=[])
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'
    v_on, bd_on = score_candidate(cand, st, sess, _REG)
    v_off, bd_off = score_candidate(cand, st, sess, _REG_OFF)
    assert abs((v_off - v_on) - _REG.off_lock_buy_penalty) < 1e-9
    assert bd_on.get('off_lock') == 'demote'
    assert 'off_lock' not in bd_off


def test_locked_pair_inscope_not_demoted() -> None:
    """对内体系件(青雀=仙舟)不降级——方向件不受辖。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state()
    cand = _cand('青雀', 'line_opportunistic', '仙舟', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == ''
    v_on, _ = score_candidate(cand, st, sess, _REG)
    v_off, _ = score_candidate(cand, st, sess, _REG_OFF)
    assert abs(v_on - v_off) < 1e-9


def test_locked_pair_bond_fallback_offscope_demoted() -> None:
    """bond_fallback 非目标填充件(阿格莱雅=昼之半神,∉对)降级
    ——降级非禁绝([31]④ 填充通道保留,只让位目标件)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(board={'仙舟': 2, '昼之半神': 1})
    cand = _cand('阿格莱雅', 'bond_fallback', '昼之半神', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'


# --- ② 末轮围栏(候选 B) ---------------------------------------------------


def test_final_round_boss_fence_rejects_offscope_opportunistic() -> None:
    """位面末轮 boss 窗:非目标件 opportunistic 直接拒(非正分,
    W143 strict 型末轮面;run17 直证);开关关=不拒(回归)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    sess.node_type_current = 'boss'
    st = _state(round_num=9)
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'final_fence'
    v_on, bd_on = score_candidate(cand, st, sess, _REG)
    assert v_on <= 0
    assert bd_on.get('off_lock') == 'final_fence'
    assert _off_lock_demotion(cand, st, sess, _REG_OFF) == ''


def test_final_round_fence_not_before_r9_or_nonboss() -> None:
    """围栏只辖位面末轮 boss 窗:r8/非 boss 节点只走常规降级。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    sess.node_type_current = 'boss'
    assert _off_lock_demotion(cand, _state(round_num=8), sess, _REG) \
        == 'demote'
    sess.node_type_current = 'battle'
    assert _off_lock_demotion(cand, _state(round_num=9), sess, _REG) \
        == 'demote'


def test_final_round_bond_fallback_fill_preserved() -> None:
    """末轮填充照旧([31]④ 梯队):bond_fallback 非目标件末轮 boss 窗
    仍只降级不围栏——填充通道不被掐死。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    sess.node_type_current = 'boss'
    st = _state(round_num=9, board={'仙舟': 2, '昼之半神': 1})
    cand = _cand('阿格莱雅', 'bond_fallback', '昼之半神', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == 'demote'


# --- ③ 未锁局/边界回归 ------------------------------------------------------


def test_unlocked_frame_no_constraint() -> None:
    """未锁局(空窗/弱意向/降格)无锁定帧:不约束,评分与开关无关
    ——未锁局行为不变(回归)。"""
    for ist in (IntentionState(),
                IntentionState(phase='weak', weak_comp='DOT队'),
                IntentionState(demoted_endgame=True)):
        sess = StrategySession()
        sess.v3_intention = ist
        sess.v3_hoard = HoardTarget(frozenset(), frozenset(), 'p1_transition')
        st = _state()
        cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
        assert _off_lock_demotion(cand, st, sess, _REG) == ''
    # 空窗态(P1 配方锁开着但 p1_pair 空)同不辖
    ist = IntentionState()
    assert locked_buy_scope(ist) is None


def test_emergency_exempt() -> None:
    """应急态豁免([18] hp 报警战力优先,方向次要)。"""
    sess = _pair_sess(('仙舟', '持续伤害'))
    st = _state(hp=_REG.emergency_hp)
    cand = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand, st, sess, _REG) == ''


# --- ④ comp 锁定帧(P2+/P1①资格)约束基准 -------------------------------


def test_locked_comp_frame_scope() -> None:
    """comp 锁定帧:scope=comp 采购集(_line_hoard);线外件降级、
    线内件不辖。"""
    sess = StrategySession()
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = 'DOT队'
    sess.v3_intention = ist
    scope = locked_buy_scope(ist)
    assert scope is not None and scope
    # 线外件(三月七=列车)降级;线内件(采购集成员)不辖
    assert '三月七' not in scope
    st = _state(plane=2)
    cand_out = _cand('三月七', 'line_opportunistic', '列车同行', 1)
    assert _off_lock_demotion(cand_out, st, sess, _REG) == 'demote'
    cand_in = _cand(sorted(scope)[0], 'line_opportunistic', '持续伤害', 2)
    assert _off_lock_demotion(cand_in, st, sess, _REG) == ''


# ==================== w184_sole_engine_sell_guard ====================

import dataclasses

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    sell_priority_key,
    sole_engine_sell_blocked,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_w184_sole_engine_sell_guard_REG = DEFAULT_REGISTRY
_w184_sole_engine_sell_guard_REG_OFF = dataclasses.replace(_w184_sole_engine_sell_guard_REG, sell_sole_engine_guard_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _w184_sole_engine_sell_guard_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _bc(name: str, faction: str, slot: int = 0, star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _sell_cands(st: GameState, sess: StrategySession, reg=_w184_sole_engine_sell_guard_REG):
    return [c for c in generate_candidates(st, sess, reg)
            if c.tag in ('off_target', 'for_gold', 'free_bench')]


def test_guard_blocks_sole_engine_piece() -> None:
    """③清空边界:唯一 owned DOT 引擎件(艾丝妲,bench 单件)→ 三卖
    tag 候选全无 + 弱序键 None + 谓词真(W181 seed37/43/45 型:
    演进换线把体系件下场到 bench 后被 off_target 卖出)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('艾丝妲', '持续伤害')])
    assert sole_engine_sell_blocked(st.bench[0], st, _w184_sole_engine_sell_guard_REG) is True
    assert _sell_cands(st, sess) == []
    assert sell_priority_key(st.bench[0], st, sess, None, _w184_sole_engine_sell_guard_REG) is None


def test_guard_blocks_tier_drop_boundary() -> None:
    """②跌破 tier 边界:两件 DOT(owned=tier=2)卖任一件 → 拒
    (seed71 卡芙卡型:owned 2→1 < tier 2)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('艾丝妲', '持续伤害', 0),
                       _bc('卡芙卡', '公司', 1)])
    for i in (0, 1):
        assert sole_engine_sell_blocked(st.bench[i], st, _w184_sole_engine_sell_guard_REG) is True
        assert sell_priority_key(st.bench[i], st, sess, None, _w184_sole_engine_sell_guard_REG) is None
    assert _sell_cands(st, sess) == []


def test_guard_not_govern_non_tt_piece() -> None:
    """④不辖·非 TT 件:银枝(智识,非四过渡体系)照旧 off_target
    (bench 溢出腾位/economy 散件清理的合法面)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('银枝', '智识')])
    assert sole_engine_sell_blocked(st.bench[0], st, _w184_sole_engine_sell_guard_REG) is False
    cands = _sell_cands(st, sess)
    assert [c.breakdown_hint.get('name') for c in cands] == ['银枝']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _w184_sole_engine_sell_guard_REG) is not None


def test_guard_not_govern_redundant_tt_piece() -> None:
    """⑤不辖·冗余件:仙舟 4 distinct 件(owned=4>tier=3)→ 青雀
    照旧生成 off_target 卖候选(体系有余量时的清仓不受辖)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('青雀', '仙舟', 0), _bc('停云', '仙舟', 1),
                       _bc('藿藿', '仙舟', 2), _bc('爻光', '仙舟', 3)])
    names = [c.breakdown_hint.get('name')
             for c in _sell_cands(st, sess)]
    assert '青雀' in names, f'冗余 TT 件应可卖:{names}'


def test_guard_covers_deployed_and_flows_caliber() -> None:
    """辖域口径:owned=bench∪deployed 逐件计(deployed 的 DOT 件也
    计入 owned——53 卡芙卡在场+bench 卖不因「场上还有」放行恒真,
    本锁锁 bench 单件与 deployed 计数合并后的 tier 边界)。"""
    sess = _sess()
    # bench 桑博 + deployed 椒丘 = owned DOT 2 = tier → 桑博卖拒
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('桑博', '持续伤害')],
                deployed=[_bc('椒丘', '持续伤害', slot=9)])
    assert sole_engine_sell_blocked(st.bench[0], st, _w184_sole_engine_sell_guard_REG) is True
    # 再加 deployed 艾丝妲 → owned 3 > tier 2 → 桑博可卖
    # (W192/ADR-0375 适配:桑博=贝+DOT 双籍,希儿系侧另辖——补 deployed
    # 娜塔莎(贝)使希儿系在手 2>1,本锁回归纯 TT 口径;希儿系辖域由
    # test_cw_w192_seele_scope ⑤ 锁)
    st2 = _w184_sole_engine_sell_guard_state(bench=[_bc('桑博', '持续伤害')],
                 deployed=[_bc('椒丘', '持续伤害', slot=9),
                           _bc('艾丝妲', '持续伤害', slot=10),
                           _bc('娜塔莎', '贝洛伯格', slot=11)])
    assert sole_engine_sell_blocked(st.bench[0], st2, _w184_sole_engine_sell_guard_REG) is False


def test_guard_emergency_not_liquidated() -> None:
    """⑦应急态:hp≤emergency_hp 时唯一 DOT 引擎件也不为折现清空
    (for_gold 候选不生成——[18] 应急是最小必要支出,不是清空引擎)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(hp=20, bench=[_bc('艾丝妲', '持续伤害')])
    assert _sell_cands(st, sess) == []


def test_flag_off_restores_w179_behavior() -> None:
    """⑥flag off 逐位回退:sole 引擎件重新生成 off_target 卖候选
    + 弱序键非 None(= W179 后行为)。"""
    sess = _sess()
    st = _w184_sole_engine_sell_guard_state(bench=[_bc('艾丝妲', '持续伤害')])
    assert sole_engine_sell_blocked(st.bench[0], st, _w184_sole_engine_sell_guard_REG_OFF) is False
    cands = _sell_cands(st, sess, _w184_sole_engine_sell_guard_REG_OFF)
    assert [c.breakdown_hint.get('name') for c in cands] == ['艾丝妲']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _w184_sole_engine_sell_guard_REG_OFF) \
        is not None


# ==================== w197_sell_floor_exec ====================

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import (
    UpgradeOption,
    UpgradeVerdict,
    execute_replacement,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
    SellBench,
    simulate,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    sole_engine_sell_blocked,
)
from sr_od.application.currency_war.kernel.cw_discipline_rules import (
    sole_engine_sell_floor_plan,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

_w197_sell_floor_exec_REG = DEFAULT_REGISTRY
_w197_sell_floor_exec_REG_OFF = dataclasses.replace(_w197_sell_floor_exec_REG, sell_floor_exec_guard_enabled=False)


def _w197_sell_floor_exec_sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _w197_sell_floor_exec_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 7,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _w197_sell_floor_exec_bc(name: str, slot: int = 0, star: int = 1,
        row: str = 'back') -> BenchChar:
    faction = (CHARACTERS[name].factions or ['?'])[0]
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     position_pref=row, star=star)


# ===== 件① arbiter 批内复检 =====


def test_arbitrate_batch_recheck_blocks_second_tt_sell() -> None:
    """①主锁(136 r7 形态):bench 三月七×2 + deployed 丹恒·饮月
    (列车在手 3>tier 2,逐笔合法),两笔 off_target 候选——第一笔采纳
    后第二笔对 working(计数 2≤2)复检被拒。"""
    sess = _w197_sell_floor_exec_sess()
    st = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0), _w197_sell_floor_exec_bc('三月七', 1),
                       _w197_sell_floor_exec_bc('银枝', 2)],
                deployed=[_w197_sell_floor_exec_bc('丹恒·饮月', 9, row='front')])
    sells = [Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'}),
             Candidate(action=SellBench(bench_idx=1), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})]
    res = arbitrate([(sells[0], 5.0, {}), (sells[1], 4.0, {})],
                    st, sess, _w197_sell_floor_exec_REG)
    acts = [a for a in res.actions if isinstance(a, SellBench)]
    assert len(acts) == 1, f'第二笔应被批内复检拒:{res.log}'
    rejects = [r['reject'] for r in res.log if not r['accepted']]
    assert any('sell_floor' in (r or '') for r in rejects), rejects


def test_arbitrate_batch_recheck_flag_off_restores_w195() -> None:
    """⑤off 臂:flag off 时两笔均采纳(=W195 后行为,逐位回退)。"""
    sess = _w197_sell_floor_exec_sess()
    st = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0), _w197_sell_floor_exec_bc('三月七', 1),
                       _w197_sell_floor_exec_bc('银枝', 2)],
                deployed=[_w197_sell_floor_exec_bc('丹恒·饮月', 9, row='front')])
    sells = [Candidate(action=SellBench(bench_idx=0), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'}),
             Candidate(action=SellBench(bench_idx=1), tag='off_target',
                       source='test', breakdown_hint={'name': '三月七'})]
    res = arbitrate([(sells[0], 5.0, {}), (sells[1], 4.0, {})],
                    st, sess, _w197_sell_floor_exec_REG_OFF)
    acts = [a for a in res.actions if isinstance(a, SellBench)]
    assert len(acts) == 2, f'flag off 两笔均应采纳(旧行为):{res.log}'


# ===== 件② 批量计划口径(discipline 单一源) =====


def test_floor_plan_single_matches_predicate() -> None:
    """②单笔一致性:plan 单笔输入与 sole_engine_sell_blocked 逐位同值
    (在手 3>tier 2 → False;在手 2≤tier 2 → True)。"""
    sess = _w197_sell_floor_exec_sess()
    st3 = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0)], deployed=[
        _w197_sell_floor_exec_bc('三月七', 9), _w197_sell_floor_exec_bc('丹恒·饮月', 10)])
    st2 = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0)],
                 deployed=[_w197_sell_floor_exec_bc('丹恒·饮月', 9)])
    for st in (st3, st2):
        assert sole_engine_sell_floor_plan([st.bench[0]], st) == [
            sole_engine_sell_blocked(st.bench[0], st, _w197_sell_floor_exec_REG)]


def test_floor_plan_sequential_decrement() -> None:
    """②同批扣减:在手 4(bench 三月七×3 + deployed 丹恒)的三笔
    同名计划 = [可卖, 可卖, 拒](前序卖出递减计数,第三笔时 2≤tier)
    ——136 r7 批内聚合缺口的批量口径。"""
    sess = _w197_sell_floor_exec_sess()
    st = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0), _w197_sell_floor_exec_bc('三月七', 1),
                       _w197_sell_floor_exec_bc('三月七', 2)],
                deployed=[_w197_sell_floor_exec_bc('丹恒·饮月', 9)])
    assert sole_engine_sell_floor_plan(
        [b for b in st.bench if b], st) == [False, False, True]
    # 在手 5 的三笔(列车 count=5)逐笔可卖不受辖(始终 >tier)
    st5 = _w197_sell_floor_exec_state(bench=[_w197_sell_floor_exec_bc('三月七', 0), _w197_sell_floor_exec_bc('三月七', 1),
                        _w197_sell_floor_exec_bc('三月七', 2)],
                 deployed=[_w197_sell_floor_exec_bc('三月七', 9), _w197_sell_floor_exec_bc('丹恒·饮月', 10)])
    assert sole_engine_sell_floor_plan(
        [b for b in st5.bench if b], st5) == [False, False, False]


# ===== 件③ execute_replacement 溢出留场 =====


def _overflow_state() -> GameState:
    """bench 满(9,新线成员=绯英·欢愉 + 8 银枝散件);deployed 旧线 =
    三月七+姬子(列车在手 2=tier,均保护件)→ 保留序截断 bench_free=1
    时另一件被划进 sold(修前)。"""
    bench = [_w197_sell_floor_exec_bc('绯英', 0, row='front')]
    bench += [_w197_sell_floor_exec_bc('银枝', i) for i in range(1, BENCH_CAPACITY)]
    st = _w197_sell_floor_exec_state(bench=bench,
                deployed=[_w197_sell_floor_exec_bc('三月七', 9, row='front'),
                          _w197_sell_floor_exec_bc('姬子', 10)])
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
    st.deployed = [*_overflow_state().deployed, _w197_sell_floor_exec_bc('丹恒·饮月', 11)]
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


# ==================== w209_offtarget_sell_guard ====================

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.operations.cw_op.cw_op_deploy import (
    offtarget_sell_allowed,
)

# run 26 终局 target 阵营集(希儿量子线,日志 target_factions 实录)
_RUN26_TARGET_FACTIONS = {'减益', '持续伤害', '星核猎手', '昼之半神',
                          '盛会之星', '量子同频'}
_RUN26_CORES: set[str] = set()


def test_run26_sold_trio_now_blocked() -> None:
    """run 26 实卖三件(藿藿/饮月/爻光,全羁绊含仙舟)→ 熔断后恒不可卖。"""
    cases = {
        '藿藿': {'仙舟', '治疗', '能量'},
        '丹恒·饮月': {'仙舟', '列车同行', '战技点'},
        '爻光': {'仙舟', '欢愉'},
    }
    for cid, bonds in cases.items():
        assert not offtarget_sell_allowed(cid, bonds, _RUN26_TARGET_FACTIONS,
                                          _RUN26_CORES), \
            f'{cid}(引擎/配方体系件)不得再被 off-target 卖(run 26 振荡熔断)'


def test_true_offtarget_still_sellable() -> None:
    """真 off-target(非 target / 非 core / 非引擎配方体系)照旧可卖——
    熔断只拦体系件,不废 D-10 腾位通道。"""
    assert offtarget_sell_allowed('艾丝妲', {'银河学者'}, _RUN26_TARGET_FACTIONS,
                                  _RUN26_CORES)
    assert offtarget_sell_allowed('风堇', {'记忆'}, _RUN26_TARGET_FACTIONS,
                                  _RUN26_CORES)


def test_core_and_target_members_protected_as_before() -> None:
    """core_char 辅助与 target 阵营成员保留(旧语义不回归)。"""
    assert not offtarget_sell_allowed('花火', {'欢愉'}, _RUN26_TARGET_FACTIONS,
                                      {'花火'})          # core 辅助
    assert not offtarget_sell_allowed('希儿', {'量子同频', '贝洛伯格'},
                                      _RUN26_TARGET_FACTIONS, _RUN26_CORES)  # target 阵营


def test_fence_source_shared_with_deploy_fence() -> None:
    """熔断保留集与散牌围栏 _DEPLOY_FENCE 同源(RECIPE ∪ ENGINE)——
    deploy 不许留 bench 的集合 = 不许卖出的集合,单一源防两处漂移。"""
    from sr_od.application.currency_war.kernel.cw_line_defs import (
        ENGINE_FACTIONS,
        RECIPE_FACTIONS,
    )
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy as deploy_bench
    assert frozenset(RECIPE_FACTIONS | ENGINE_FACTIONS) == deploy_bench._DEPLOY_FENCE
    # 引擎阵营抽查:仙舟/列车同行/持续伤害成员均被熔断覆盖
    for bond in ('仙舟', '列车同行', '持续伤害'):
        assert not offtarget_sell_allowed('任意', {bond}, set(), set()), \
            f'{bond} 体系件必须被熔断拦下'


# ==================== w423_revoke_evidence ====================

import dataclasses
import math

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_intention import (
    CORE_MISS_N,
    IntentionState,
    core_miss_n_required,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard
from sr_od.application.currency_war.kernel.cw_intention import serialize_intention
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

#: 证据组 B 厚度边界夹具(异线「万敌单C」=v2 家族载体,
#: core=[万敌,千冶·刃,长夜月,刻律德菈,缇宝];骨架重叠=千冶·刃/
#: 刻律德菈/缇宝,每件 ×0.5):
#: 4 终局件 → 厚度 4+1.0=5.0 = A_min(开);3 终局件 → 3+0.5=3.5 <5(不开)。
THK_ABOVE = ['万敌', '千冶·刃', '长夜月', '刻律德菈']
THK_BELOW = ['万敌', '长夜月', '刻律德菈']
#: 异线核心不可达夹具:资产够厚(4 终局件+骨架=5.5)但核心万敌不在手,
#: P3 末轮剩余节点 < 再遇窗口 → _core_reachable=False。
THK_UNREACHABLE = ['千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _w423_revoke_evidence_state(**kw) -> GameState:
    s = GameState()
    s.plane = kw.get('plane', 2)
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions
                               else '?',
                               cost=ch.cost if ch else 3))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions
                                 else '?',
                                 star=kw.get('bench_star', 1)))
    return s


def _locked_xier() -> IntentionState:
    ist = update_intention(_w423_revoke_evidence_state(shop=['希儿']), IntentionState())
    assert ist.locked_comp == '希儿量子'
    return ist


def _n_req_default(core: str, level: int = 5) -> int:
    return core_miss_n_required(
        core, level, DEFAULT_REGISTRY.revoke_miss_tolerance_eps)


def _drive_to(ist: IntentionState, frame: GameState,
              target_miss: int) -> IntentionState:
    """推 miss 计数到 target_miss(核心缺席帧逐轮驱动;状态机就地改)。"""
    for _ in range(target_miss):
        update_intention(frame, ist)
    return ist


# --- C1 三条件合取锁 -----------------------------------------------------------


def test_c1_miss_threshold_with_evidence_opens() -> None:
    """miss 达 max(CORE_MISS_N, N_req) ∧ 异线资产证据 → 开窗降弱意向。"""
    ist = _locked_xier()
    frame = _w423_revoke_evidence_state(bench=THK_ABOVE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total)
    assert out.phase == 'weak' and out.weak_comp == '希儿量子'
    assert out.last_event.startswith('revoke:miss')
    assert out.revoke_evidence['alt_comp'] == '万敌单C'


def test_c1_miss_threshold_without_alt_asset_stays_locked() -> None:
    """miss 达标 ∧ 无异线在场资产 → 不开窗(缺证据组 B,噪声不进撤销)。"""
    ist = _locked_xier()
    frame = _w423_revoke_evidence_state()
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total + 3)
    assert out.phase == 'locked'
    assert out.tracks['希儿量子'].miss_count == total + 3   # 计数继续,不弃


def test_c1_miss_threshold_alt_core_unreachable_stays_locked() -> None:
    """miss 达标 ∧ 异线厚但核心不可达(P3 末轮剩余节点 < 再遇窗口)
    → 不开窗(证据组 A 的异线可达半边缺)。"""
    ist = _locked_xier()
    frame = _w423_revoke_evidence_state(plane=3, round_num=9, bench=THK_UNREACHABLE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total + 3)
    assert out.phase == 'locked'


def test_c1_miss_below_threshold_with_evidence_stays_locked() -> None:
    """miss 未达(证据已在场)→ 不开窗:断供强度是必要条件,资产在场
    不单独构成意图。"""
    ist = _locked_xier()
    frame = _w423_revoke_evidence_state(bench=THK_ABOVE)
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    out = _drive_to(ist, frame, total - 1)
    assert out.phase == 'locked'


# --- C2 N_req 推导锁 -----------------------------------------------------------


def test_c2_n_req_worked_example_cost3_lv5() -> None:
    """闭式代入例(锁定表值,表或公式漂移即碎):3 费@lv5,
    refresh_prob=0.20 → r=0.20/14,q=1−(1−r)^5≈0.0693,
    N_req=⌈ln 0.05/ln(1−q)⌉=⌈41.71⌉=42。"""
    from sr_od.application.currency_war.data.cw_shop_odds import (
        DISTINCT_CARDS_PER_COST,
        refresh_prob,
    )
    p = refresh_prob(5, 3)
    assert p == 0.20
    r = p / DISTINCT_CARDS_PER_COST[3]
    q = 1.0 - (1.0 - r) ** 5
    assert 0.0692 < q < 0.0695
    assert math.ceil(math.log(0.05) / math.log(1.0 - q)) == 42
    assert core_miss_n_required('希儿', 5, 0.05) == 42


def test_c2_n_req_monotone_and_eps_scaling() -> None:
    """方向锁:高概率窗要求更少轮(3 费@lv7=21 < @lv5=42);
    ε 收紧要求更多轮(ε=1% → 65);未识别角色退化=上限保险 CORE_MISS_N。"""
    assert core_miss_n_required('希儿', 7, 0.05) == 21
    assert core_miss_n_required('希儿', 5, 0.01) == 65
    assert core_miss_n_required('不存在角色', 5, 0.05) == CORE_MISS_N


# --- C3 A_min 基线锁 -----------------------------------------------------------


def test_c3_a_min_registry_value_is_measured_baseline() -> None:
    """A_min=冻结池 f0 曲线 5% 点测量值(协议与实测曲线见 registry 注释
    与测量产物 a_min_measurement.json):f0(4)=7.68%>5%,f0(5)=1.27%≤5%
    → 5.0。改值必须重跑测量协议,禁拍值。"""
    assert DEFAULT_REGISTRY.revoke_evidence_min_thickness == 5.0


def test_c3_thickness_boundary_around_a_min() -> None:
    """边界行为:异线厚度 5.5(≥5)→ 开窗;4.0(<5)→ 不开窗。"""
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    ist = _drive_to(_locked_xier(), _w423_revoke_evidence_state(bench=THK_BELOW), total)
    assert ist.phase == 'locked'
    ist2 = _drive_to(_locked_xier(), _w423_revoke_evidence_state(bench=THK_ABOVE), total)
    assert ist2.phase == 'weak'


# --- C4 零漂移锚 + 证据字段遥测 -------------------------------------------------


def test_c4_default_registry_off_arm_structural_anchor() -> None:
    """零漂移锚的结构前提:撤 C4 门后 revoke 常量链不动(W379 off 臂
    语义不变;C4 开关族已随旧方案清退批删除,清查报告 OLD_MIX_AUDIT
    §1.3,常量断言保留)。"""
    assert DEFAULT_REGISTRY.revoke_miss_tolerance_eps == 0.05
    assert dataclasses.replace(
        DEFAULT_REGISTRY, revoke_miss_tolerance_eps=0.01
    ).revoke_miss_tolerance_eps == 0.01   # A/B 注入臂可达(dataclasses.replace)


def test_c4_evidence_fields_reach_telemetry() -> None:
    """开窗证据字段落 serialize_intention(实机判读锚:无证据字段的开窗
    =守卫失效,判读即报警;设计 R3.5)。"""
    total = max(CORE_MISS_N, _n_req_default('希儿'))
    ist = _drive_to(_locked_xier(), _w423_revoke_evidence_state(bench=THK_ABOVE), total)
    d = serialize_intention(ist)
    assert d is not None
    ev = d['revoke_evidence']
    assert ev['kind'] == 'miss' and ev['n_req'] == total
    assert ev['alt_comp'] == '万敌单C' and ev['q'] > 0
    assert ev['asset_thickness'] >= ev['a_min']

