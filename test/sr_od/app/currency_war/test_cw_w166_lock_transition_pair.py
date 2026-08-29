# -*- coding: utf-8 -*-
"""W166/ADR-0366 ①资格锁定局的过渡对保护副方向锁(W164 R1+R2 裁决落地)。

锁定对象(cw_intention.py + decision_v2/discipline.py + decision_v2/phase.py):

- ①锁局(P1 锁终局 comp)同时派生 ``transition_pair`` 副方向(与 p1_pair
  同口径,随资产重派生;撤销/出 P1 清空);
- ``locked_buy_scope``/``locked_faction_scope`` ∪ 过渡对成员/体系键:
  对件免 demote/免 final_fence([22]④ 二级囤货),guard 保护基准扩辖
  (R2:对件引擎贡献含希儿系不受拆);
- ``_direction_factions`` locked∧对非空放行对体系键(pair 通道);
- ``form_ok`` ①锁局补体系对判据([13] P1 验收仍是体系对);
- comp 主方向/核心件优先级/hoard 目标件集不动(主序对副序);
- 回归:配方锁局(p1_pair)零漂移/未锁局不变/A-B 通道
  (P1_LOCK_TRANSITION_PAIR=False 逐位回 W164 前)。
"""
from __future__ import annotations

from types import SimpleNamespace

import sr_od.application.currency_war.cw_intention as cw_intention
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_intention import (
    IntentionState,
    _pair_members,
    hoard_target_set,
    intention_core,
    locked_buy_scope,
    locked_faction_scope,
    update_intention,
)
from sr_od.application.currency_war.cw_comps import get_comp
from sr_od.application.currency_war.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.candidates import Candidate
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.decision_v2.scoring import _off_lock_demotion
from sr_od.application.currency_war.decision_v2.discipline import (
    _direction_factions,
)
from sr_od.application.currency_war.decision_v2.phase import form_ok
from sr_od.application.currency_war.cw_evolution import _locked_protected_names

#: ①资格策略(黑塔纪元 → 大黑塔银河学者;群攻/银河学者线,采购集
#: 不含列车/仙舟件 → 对件在旧口径下是 off-scope)。
_QUAL_STRATEGY = '黑塔纪元'
_COMP = '大黑塔银河学者'

#: 证据组 B 夹具(W423 起撤销出口①须异线资产证据,同 test_cw_intention):
#: 异线「万敌单C」(v2 家族)终局件 5 张在手,核心万敌可达 → 厚度 ≥ A_min。
EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _state(bench=(), plane=1, round_num=1, strategies=(), board=None,
           level=5) -> GameState:
    s = GameState()
    s.plane = plane
    s.round_num = round_num
    s.level = level
    s.active_strategies = list(strategies)
    for n in bench:
        ch = CHARACTERS[n]
        s.bench.append(BenchChar(
            slot=len(s.bench), char_id=n,
            faction=ch.factions[0] if ch.factions else '?'))
    for fac, num in (board or {}).items():
        s.board[fac] = num
    return s


def _cand(name: str, tag: str) -> Candidate:
    ch = CHARACTERS[name]
    return Candidate(
        action=BuyCard(ShopCard(x=1, name=name,
                                faction=ch.factions[0] if ch.factions else '?',
                                cost=ch.cost), reason=''),
        tag=tag, source='shop',
        breakdown_hint={'cost': ch.cost})


def _qlock_session(pair: tuple[str, ...] = (),
                   locked: bool = True) -> StrategySession:
    """①锁局帧 session(生产真实形态:v3_intention + v3_hoard)。"""
    s = StrategySession()
    ist = IntentionState()
    if locked:
        ist.phase = 'locked'
        ist.locked_comp = _COMP
    ist.transition_pair = tuple(pair)
    s.v3_intention = ist
    s.v3_hoard = hoard_target_set(_state(), ist)
    return s


# --- ① 意向层:①锁局派生 + scope ∪ 对集 -------------------------------


def test_qlock_derives_transition_pair_and_scope_union() -> None:
    """①资格锁 r1:锁定产物=comp 不变([23] 直通权),同时派生过渡对
    副方向;scope=comp 采购集 ∪ 对成员集(对件免约束,comp 件仍在)。"""
    st = _state(bench=('三月七', '丹恒·饮月'),
                strategies=(_QUAL_STRATEGY,))
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == _COMP
    assert ist.transition_pair, '①锁局必须派生过渡对副方向'
    scope = locked_buy_scope(ist)
    assert '三月七' in scope, '对件(列车)须并入 scope'
    comp = get_comp(_COMP)
    core = intention_core(comp)
    assert core in scope, 'comp 核心件仍为主方向(scope 不缩)'
    # 阵营口径同式:对体系键 ∪ comp 主副档键
    fs = locked_faction_scope(ist)
    assert {'列车同行'} <= fs and set(comp.form_tiers) <= fs


def test_qlock_rederive_and_clear_lifecycle() -> None:
    """过渡对随资产重派生([20] 变体按来牌选,同 p1_pair 语义);
    出 P1 清空(P2+ comp 唯一)。"""
    st = _state(bench=('三月七', '丹恒·饮月'),
                strategies=(_QUAL_STRATEGY,))
    ist = update_intention(st, IntentionState())
    assert ist.transition_pair == ('列车同行', '仙舟')   # _P1_PAIR_PREF 序
    # 希儿到手 → 重派生含希儿系
    st2 = _state(bench=('三月七', '丹恒·饮月', '希儿', '银狼', '杰帕德'),
                 round_num=2, strategies=(_QUAL_STRATEGY,))
    ist2 = update_intention(st2, ist)
    assert ist2.transition_pair == ('列车同行', '希儿系')
    assert '希儿' in locked_buy_scope(ist2), '希儿系展开并入 scope'
    # 出 P1 清空
    st3 = _state(bench=('三月七', '希儿'), plane=2,
                 strategies=(_QUAL_STRATEGY,))
    ist3 = update_intention(st3, ist2)
    assert ist3.transition_pair == ()
    assert '量子同频' not in (locked_faction_scope(ist3) or frozenset())


def test_qlock_revoke_clears_transition_pair() -> None:
    """撤销出口①(断供证据三条件合取,W423 起)→ weak:副方向随之
    退场(scope 契约=weak 不辖)。夹具:lv8 使 4 费核心刷新窗开
    (N_req=38),证据组 B=异线千冶减益终局件 5 张在手(厚度 ≥ A_min)。"""
    st = _state(bench=('三月七', '丹恒·饮月'),
                strategies=(_QUAL_STRATEGY,))
    ist = update_intention(st, IntentionState())
    assert ist.transition_pair
    # 推进 miss 计数到撤销(comp 核心恒不可得:窗口开但核心不在店/手;
    # 证据组 B 夹具与 test_cw_intention 同款)
    gone = _state(bench=EVIDENCE_BENCH, plane=1, level=8)
    need = max(cw_intention.CORE_MISS_N,
               cw_intention.core_miss_n_required(
                   '大黑塔', 8, DEFAULT_REGISTRY.revoke_miss_tolerance_eps))
    for _ in range(need):
        gone.round_num += 1
        ist = update_intention(gone, ist)
    assert ist.phase == 'weak' and ist.transition_pair == ()


# --- ② 买侧:对件免 demote/免 fence;comp 主序对副序 -------------------


def test_qlock_pair_member_exempt_third_class_demoted() -> None:
    """三级对照(①锁局帧):comp 件√ / 对件√(免 demote,原 off-scope
    处置消失)/ 两者皆非件×(仍 demote——约束未松到无方向)。"""
    sess = _qlock_session(('仙舟', '列车同行'))
    st = _state(plane=1, round_num=7, board={'群攻': 2})
    comp = get_comp(_COMP)
    pair_member = '三月七'          # 列车=对体系
    assert pair_member not in {c for c in _comp_chars(comp)}
    comp_member = intention_core(comp)
    third = _third_card(sess)
    assert _off_lock_demotion(_cand(comp_member, 'line_opportunistic'),
                              st, sess, DEFAULT_REGISTRY) == ''
    assert _off_lock_demotion(_cand(pair_member, 'line_opportunistic'),
                              st, sess, DEFAULT_REGISTRY) == ''
    assert _off_lock_demotion(_cand(third, 'line_opportunistic'),
                              st, sess, DEFAULT_REGISTRY) == 'demote'


def test_qlock_pair_member_exempt_final_fence() -> None:
    """位面末轮 boss 窗:对件免 final_fence([22]④ 有用先囤到末轮);
    三级外件照旧被围栏拒。"""
    sess = _qlock_session(('仙舟', '列车同行'))
    sess.node_type_current = 'boss'
    st = _state(plane=1, round_num=9)
    assert _off_lock_demotion(_cand('三月七', 'line_opportunistic'),
                              st, sess, DEFAULT_REGISTRY) == ''
    third = _third_card(sess)
    assert _off_lock_demotion(_cand(third, 'line_opportunistic'),
                              st, sess, DEFAULT_REGISTRY) == 'final_fence'


def test_qlock_hoard_primary_direction_unchanged() -> None:
    """comp 主序对副序:hoard 目标件集=comp 采购集逐位不变(mode
    'locked'),对件不进主目标集(不与 comp 件同轮顶分抢预算)。"""
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = _COMP
    ist.transition_pair = ('仙舟', '列车同行')
    ht = hoard_target_set(_state(), ist)
    assert ht.mode == 'locked'
    base = IntentionState()
    base.phase = 'locked'
    base.locked_comp = _COMP
    ht_base = hoard_target_set(_state(), base)
    assert ht.char_targets == ht_base.char_targets, '主方向目标件集不得变'
    assert '三月七' in _pair_members(ist.transition_pair)


def test_direction_factions_unlock_pair_systems() -> None:
    """pair 通道方向门:locked∧对非空 → allow=comp 档位键 ∪ 对体系键
    (对体系件不再被 comp 档位门拦);无对锁定帧照旧(回归)。"""
    sess = _qlock_session(('列车同行', '希儿系'))
    allow = _direction_factions(sess)
    assert '列车同行' in allow and '量子同频' in allow   # 对体系(希儿系展开)
    comp = get_comp(_COMP)
    assert set(comp.form_tiers) <= allow              # comp 主方向仍在
    sess_plain = _qlock_session(())
    allow_plain = _direction_factions(sess_plain)
    assert set(allow_plain) == set(comp.form_tiers) | set(comp.sub_tiers)


# --- ③ guard 基准扩辖(R2:对件引擎贡献受保护) -------------------------


def test_guard_protects_pair_engine_pieces_on_evolve() -> None:
    """①锁局 evolve 保护基准扩辖:对件(希儿系——非三羁绊成员,旧口径
    裸奔)进 _locked_protected_names。

    旧「无副方向帧希儿不辖」对照断言已随 W192/ADR-0375 过期:希儿本人
    唯一种子自此**恒入保护集**(guard_seele_scope_enabled,不依赖
    transition_pair 帧)——对照改 scope off(=W188 后行为)时希儿
    不辖,证扩辖来源。"""
    old_line = [_char_bc('希儿'), _char_bc('阿格莱雅')]
    sess = _qlock_session(('列车同行', '希儿系'))
    prot = _locked_protected_names(old_line, sess)
    assert '希儿' in prot, '对件引擎贡献(希儿系)须进保护集'
    sess_plain = _qlock_session(())
    assert '希儿' in _locked_protected_names(
        old_line, sess_plain), 'W192 起:希儿唯一种子恒辖(非 pair 帧独占)'
    assert '希儿' not in _locked_protected_names(
        old_line, sess_plain, seele_scope=False), 'scope off 对照'


def test_guard_faction_scope_not_offlock_for_pair_system() -> None:
    """对体系提案不再是 off-lock:locked_faction_scope ∪ 对体系键
    (evolve 提案/围栏消费的阵营口径基准)。"""
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = _COMP
    ist.transition_pair = ('仙舟', '希儿系')
    fs = locked_faction_scope(ist)
    assert {'仙舟', '量子同频', '贝洛伯格'} <= fs
    assert set(get_comp(_COMP).form_tiers) <= fs


# --- ④ 成型验收:①锁局 comp 三件套 ∧ 体系对引擎 -----------------------


def test_form_ok_qlock_requires_pair_engines() -> None:
    """①锁局 form_ok:comp 三件套(列车4+核心 2★)成立但引擎<2 →
    False(过渡引擎饿死面,W164);补 DOT2 → True。"""
    s = _form_state(extra=())
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    ist.transition_pair = ('列车同行', '持续伤害')
    assert not form_ok(s, SimpleNamespace(v3_intention=ist), DEFAULT_REGISTRY)
    s2 = _form_state(extra=('卡芙卡', '桑博'))
    assert form_ok(s2, SimpleNamespace(v3_intention=ist), DEFAULT_REGISTRY)


def test_form_ok_no_pair_frame_unchanged() -> None:
    """回归:①锁局无副方向(空资产帧)/P2 锁定/配方锁局 —— 旧口径
    comp 三件套即 True(P2+)或走兜底门(配方锁局),不辖。"""
    s = _form_state(extra=())
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = '列车同行'
    # ①锁局但 transition_pair 空(空资产派生不出对):comp 三件套即过
    assert form_ok(s, SimpleNamespace(v3_intention=ist), DEFAULT_REGISTRY)
    # P2:不辖(plane 门)
    ist_tp = IntentionState()
    ist_tp.phase = 'locked'
    ist_tp.locked_comp = '列车同行'
    ist_tp.transition_pair = ('列车同行', '持续伤害')
    s_p2 = _form_state(extra=())
    s_p2.plane = 2
    assert form_ok(s_p2, SimpleNamespace(v3_intention=ist_tp),
                   DEFAULT_REGISTRY)
    # 配方锁局(P1,unlocked+pair):走兜底门(W132),transition_pair
    # 恒空不辖——本帧 engines=1 < min_engines=2 → False(兜底门自洽)
    ist_r = IntentionState()
    ist_r.p1_pair = ('仙舟', '列车同行')
    assert not ist_r.transition_pair
    s_r = _form_state(extra=())
    assert form_ok(s_r, SimpleNamespace(v3_intention=ist_r),
                   DEFAULT_REGISTRY) is False


# --- ⑤ 回归:配方锁局零漂移 / 未锁局 / A-B 通道 -----------------------


def test_recipe_lock_frame_zero_drift() -> None:
    """配方锁局(p1_pair 帧)transition_pair 恒空:update 驱动后
    p1_pair 语义/hoard mode 逐位同 W145(scope 已有对成员,不因本批变)。"""
    st = _state(bench=('三月七', '丹恒·饮月'))   # 无资格策略 → 配方锁
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked'
    assert ist.p1_pair == ('列车同行', '仙舟')   # _P1_PAIR_PREF 序
    assert ist.transition_pair == ()
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p1_pair'
    scope = locked_buy_scope(ist)
    assert '三月七' in scope and intention_core(get_comp(_COMP)) not in scope


def test_unlocked_frames_unchanged() -> None:
    """未锁/weak/降格帧:transition_pair 恒空,scope 不辖(回归)。"""
    for ist in (IntentionState(),
                IntentionState(phase='weak', weak_comp=_COMP),
                IntentionState(demoted_endgame=True)):
        assert ist.transition_pair == ()
    # weak/降格帧:无锁定帧,买侧不辖(回归)
    assert locked_buy_scope(IntentionState(phase='weak', weak_comp=_COMP)) \
        is None
    assert locked_buy_scope(IntentionState(demoted_endgame=True)) is None


# (批 3 F5 清偿:原 test_ab_flag_off_restores_w164_behavior 随
# P1_LOCK_TRANSITION_PAIR 旗标退役删除,出处同蓝图 §6。)


def _comp_chars(comp) -> set[str]:
    from sr_od.application.currency_war.cw_intention import _line_hoard
    chars, _eq = _line_hoard(comp)
    return chars


def _third_card(sess: StrategySession) -> str:
    """既不在 comp 采购集也不在对成员集的注册表件(三级外件)。"""
    scope = locked_buy_scope(sess.v3_intention) or frozenset()
    for name in ('阿格莱雅', '知更鸟', '花火'):
        if name in CHARACTERS and name not in scope:
            return name
    raise AssertionError('找不到三级外件(测试数据错误)')


def _char_bc(name: str) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=ch.factions[0] if ch.factions else '?')


def _form_state(extra: tuple[str, ...]) -> GameState:
    """列车同行 comp 三件套成立态(form_tiers 列车4 + 核心 2★ 上场)。"""
    s = GameState()
    s.plane = 1
    s.round_num = 8
    s.level = 5
    dep = [BenchChar(slot=0, char_id='姬子·启行',
                     faction=(CHARACTERS['姬子·启行'].factions or ['?'])[0],
                     star=2)]
    for n in ('三月七', '丹恒·饮月', '开拓者·记忆', *extra):
        dep.append(BenchChar(slot=len(dep), char_id=n,
                             faction=(CHARACTERS[n].factions or ['?'])[0],
                             star=1))
    s.deployed = dep
    from sr_od.application.currency_war.cw_state import _recount_board
    s.board = _recount_board(dep)
    return s
