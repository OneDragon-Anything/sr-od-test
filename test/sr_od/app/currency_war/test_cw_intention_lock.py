# -*- coding: utf-8 -*-
"""test_cw_intention_lock 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w155_evolve_lock_guard: test_cw_w155_evolve_lock_guard.py
- w166_lock_transition_pair: test_cw_w166_lock_transition_pair.py
- w192_seele_scope: test_cw_w192_seele_scope.py
- line_gate_relock: test_cw_line_gate_relock.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w155_evolve_lock_guard ====================

from types import SimpleNamespace

import sr_od.application.currency_war.kernel.cw_evolution as cw_evolution
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import select_deployments
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    UpgradeOption,
    UpgradeVerdict,
    execute_replacement,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    locked_faction_scope,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    simulate,
    _recount_board,
)


def _char(name: str, faction: str | None = None, row: str | None = None,
          star: int = 1) -> BenchChar:
    c = CHARACTERS[name]
    return BenchChar(slot=0, char_id=name,
                     faction=faction or (c.factions or ['?'])[0],
                     position_pref=row or c.position_pref(), star=star)


def _pair_session(*pair: str) -> SimpleNamespace:
    """p1_pair 锁定帧 session 桩(v3_intention 口径同生产)。"""
    ist = IntentionState()
    ist.p1_pair = tuple(pair)
    return SimpleNamespace(v3_intention=ist, target_comp=None)


def _comp_session(name: str) -> SimpleNamespace:
    ist = IntentionState()
    ist.phase = 'locked'
    ist.locked_comp = name
    return SimpleNamespace(v3_intention=ist, target_comp=None)


# ---------- 件1:提案层目标约束(锁定帧 off-lock 降级,优先级式) ----------

def test_locked_faction_scope_pair_and_comp():
    """锁定帧体系键派生:配方对(希儿系展开)/comp 主副档/空窗 None。"""
    assert locked_faction_scope(None) is None
    ist = IntentionState()
    assert locked_faction_scope(ist) is None   # 空窗:无锁定帧
    ist.p1_pair = ('仙舟', '持续伤害')
    assert locked_faction_scope(ist) == frozenset({'仙舟', '持续伤害'})
    ist2 = IntentionState()
    ist2.p1_pair = ('列车同行', '希儿系')
    assert locked_faction_scope(ist2) == frozenset(
        {'列车同行', '量子同频', '贝洛伯格'})   # 希儿系展开同 _pair_members
    cs = _comp_session('绯英欢愉')
    scope = locked_faction_scope(cs.v3_intention)
    assert scope == frozenset({'欢愉', '能量'})   # form_tiers 键


def test_best_option_offlock_demotion_priority_not_ban(monkeypatch):
    """锁定帧 off-lock 提案在选择序降级(penalty 让位,非禁换);
    未锁局 penalty 不生效(回归)。"""
    opts = [
        UpgradeOption('new_faction', '仙舟', 3, 6.0, True,
                      'xianzhou3', 'card'),
        UpgradeOption('tier_up', '持续伤害', 4, 4.0, True, '', 'board'),
    ]
    monkeypatch.setattr(cw_evolution, 'propose_upgrades',
                        lambda st, session=None: list(opts))
    monkeypatch.setattr(
        cw_evolution, 'evaluate_upgrade',
        lambda opt, st: UpgradeVerdict(opt, True, True, True, True, '齐'))
    st = GameState()
    sess = _pair_session('持续伤害', '列车同行')   # 仙舟 ∉ 锁定体系集
    # 基线(无 penalty):仙舟3 卡分高者胜
    assert cw_evolution._best_option(
        st, sess, None, 0.0).faction == '仙舟'
    # 降级(penalty 3.0):6-3 < 4 → 锁定线内提案胜
    assert cw_evolution._best_option(
        st, sess, None, 3.0).faction == '持续伤害'
    # 回归:未锁局(无锁定帧)同 penalty 不降级
    assert cw_evolution._best_option(
        st, None, None, 3.0).faction == '仙舟'
    # 回归:全部机会均 off-lock(无锁定线内可执行机会)→ 照选最优(非禁换)
    sess_xz = _pair_session('仙舟', '列车同行')
    only = [opts[0]]
    monkeypatch.setattr(cw_evolution, 'propose_upgrades',
                        lambda st, session=None: list(only))
    assert cw_evolution._best_option(
        st, sess_xz, None, 3.0).faction == '仙舟'


# ---------- 件3a:保留序保护(锁定目标件/引擎件不被划进卖出) ----------

def test_retained_protects_locked_target_and_engine_pieces():
    """old_line 溢出卖出:锁定目标件(scope)/引擎件(TT)保留序种子
    同级——先吃非保护件;无 session(未锁)时引擎件仍受保护、锁定目标
    件不受([23] 保护的是锁定目标件,空窗期无锁定帧)。"""
    # 新线 = 万敌单C(燃血);old_line = 绯英(欢愉,锁定 scope)/
    # 桑博(持续伤害,引擎件)/知更鸟(盛会之星,非保护,star2 cost4)
    def _state() -> GameState:
        st = GameState()
        st.gold = 20
        st.level = 6   # cap=6
        st.deployed = [_char('绯英', '欢愉'), _char('桑博', '持续伤害'),
                       _char('知更鸟', star=2)]
        st.board = _recount_board(st.deployed)
        # bench 8 占用(万敌 + 7 张花火填充),bench_new=万敌 → bench_free=2
        st.bench = ([_char('万敌')] + [_char('花火')] * 7)
        return st

    opt = UpgradeOption('new_faction', '燃血', 4, 5.0, True,
                        '万敌单C', 'comp')
    verdict = UpgradeVerdict(opt, True, True, True, True, '三条件齐备')

    # 锁定帧(绯英欢愉 comp):protected = {绯英(scope), 桑博(引擎)}
    # → retained=2 全给保护件,卖出=知更鸟(非保护件先吃)
    st = _state()
    tx = execute_replacement(verdict, st, None, _comp_session('绯英欢愉'))[0]
    sold = [st.deployed[i].char_id for i, d in tx.sell if d == 'deployed']
    assert sold == ['知更鸟'], \
        f'锁定帧:溢出卖出必须先吃非保护件,实卖 {sold}'
    assert simulate(st, tx).action_log[-1]['result'] == 'applied'

    # 未锁(无 session):引擎件(桑博)仍保护,锁定 scope 件(绯英)
    # 无锁定帧不辖 → 高星/高费保留 → 绯英被卖(对照组,证 scope 保护
    # 是锁定帧语义不是无条件)
    st2 = _state()
    tx2 = execute_replacement(verdict, st2, None, None)[0]
    sold2 = [st2.deployed[i].char_id for i, d in tx2.sell if d == 'deployed']
    assert sold2 == ['绯英'], f'未锁局:仅引擎件受保护,实卖 {sold2}'
    assert '桑博' not in sold2, '引擎件(TT)任何模式都是方向件([31])'


# ---------- 件4:deploy 围栏锁定帧体系键放行(ADR-0226 同型) ----------

def test_deploy_fence_locked_factions_unlocked_by_lock_frame():
    """锁定帧体系键并入围栏放行集:锁定 comp 的散阵营件(欢愉)配方
    饥饿期成对可上;未传锁定帧时照旧被摁 bench(r263b 纪律保持)。"""
    bench = [_char('藿藿'), _char('绯英'), _char('花火')]
    # 藿藿=target 件(tgt 非空 → ADR-0288 凑档例外不生效,围栏真拦截);
    # 绯英=星间旅人主阵营+欢愉流派(锁定 comp 阵营键是流派);
    # board 预置主阵营各 1 → 绯英/花火成对(must_up=2 > vacancy=1 → 非 roomy)
    board = {'星间旅人': 1, '盛会之星': 1}
    kwargs = dict(deployed_cids={'三月七'}, deployed_fac={}, board=board,
                  cap=10, front_total=1, back_total=1,
                  target_factions=frozenset({'仙舟'}))
    up0, held0 = select_deployments(list(bench), **kwargs)
    up0_names = {bench[i].char_id for i in up0}
    # 未锁:绯英(星间旅人主阵营,非围栏阵营;tgt 非空凑档例外不生效)
    # 被围栏摁 bench
    assert '绯英' not in up0_names, f'未锁局锁定阵营件须被围栏,实上 {up0_names}'
    up1, _held1 = select_deployments(
        list(bench), locked_factions=frozenset({'欢愉'}), **kwargs)
    up1_names = {bench[i].char_id for i in up1}
    assert '绯英' in up1_names, \
        f'锁定帧:欢愉键(锁定 comp 阵营,流派口径)按全羁绊放行,实上 {up1_names}'
    # 锁定帧只放行锁定体系:非锁定散阵营(花火=盛会之星)不因锁定帧
    # 获得额外放行(锁定臂仍被围栏)
    assert '花火' not in up1_names, '非锁定散阵营不得因锁定帧放行'
    assert '花火' not in up0_names, '未锁臂花火同样被围栏(两臂一致)'


# ---------- 件2:提案去重(生成侧守卫 + 被拒不发射/退避) ----------

def test_bench_newline_dedup_against_deployed_keep():
    """bench 新线候选与留场新线 deployed 同名 → 剔除(3合1 素材留
    bench);否则终态 deployed 同名重复 → duplicate_on_board 整事务拒
    (W143 s26 死循环根因形态)。"""
    st = GameState()
    st.gold = 20
    st.level = 6
    st.deployed = [_char('万敌', '燃血')]   # 万敌已在新线留场
    st.board = _recount_board(st.deployed)
    st.bench = [_char('万敌', '燃血', star=2), _char('刃', '燃血')]
    opt = UpgradeOption('new_faction', '燃血', 4, 5.0, True,
                        '万敌单C', 'comp')
    verdict = UpgradeVerdict(opt, True, True, True, True, '三条件齐备')
    tx = execute_replacement(verdict, st)[0]
    dep_names = [st.bench[i].char_id for i, _r in tx.deploy]
    assert '万敌' not in dep_names, \
        f'留场新线同名 bench 副本不得进部署名单:{dep_names}'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    assert [d.char_id for d in out.deployed
            if d is not None].count('万敌') == 1   # ADR-0392 滤 None
    bench_names = [b.char_id for b in out.bench if b is not None]
    assert bench_names.count('万敌') == 1, \
        '副本留 bench 当 3合1 素材(不卖)'


def test_rejected_tx_not_emitted_and_backoff(monkeypatch):
    """被 simulate 拒的事务不再发射(旧版拒了仍返回 tx → 每轮原样
    重提死循环)且登记退避:2 轮内同签名提案跳过,窗口过后恢复。"""
    st = GameState()
    st.gold = 20
    st.level = 8
    st.deployed = [_char(n, '持续伤害')
                   for n in ('桑博', '艾丝妲', '卡芙卡')]
    st.bench = [_char(n, '仙舟') for n in ('藿藿', '符玄', '彦卿')]
    st.board = _recount_board(st.deployed)

    rejected = GameState()
    rejected.action_log = [{'result': 'rejected',
                            'reason': 'duplicate_on_board:艾丝妲'}]
    calls = {'n': 0}

    def _fake_simulate(state, action):
        calls['n'] += 1
        return rejected

    monkeypatch.setattr(cw_evolution, 'simulate', _fake_simulate)
    mem = EvolutionState()
    assert evolution_step_reject_case(st, mem) == []
    assert calls['n'] >= 1, '被拒路径必须先 simulate 验证再决定发射'
    assert mem.reject_backoff, '被拒事务须登记退避签名'
    # 退避窗内:同提案不再进 _best_option(simulate 不再被调用)
    calls['n'] = 0
    assert evolution_step_reject_case(st, mem) == []
    assert calls['n'] == 0, '退避窗内同签名提案须被跳过'
    # 窗口过后(轮次 +3 > 退避窗 2 轮):恢复尝试(再 simulate,仍拒)
    st.round_num += 3
    assert evolution_step_reject_case(st, mem) == []
    assert calls['n'] >= 1, '退避窗过后须恢复重试'


def evolution_step_reject_case(st: GameState, mem: EvolutionState) -> list:
    """reject/backoff 测试的入口包装(隔离 monkeypatch 面)。"""
    return cw_evolution.evolution_step(st, None, mem)


# ==================== w166_lock_transition_pair ====================

from types import SimpleNamespace

import sr_od.application.currency_war.kernel.cw_intention as cw_intention
from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _pair_members,
    hoard_target_set,
    intention_core,
    locked_buy_scope,
    locked_faction_scope,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    BuyCard,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
from sr_od.application.currency_war.decision.decision_v2.scoring import _off_lock_demotion
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    _direction_factions,
)
from sr_od.application.currency_war.decision.decision_v2.phase import form_ok
from sr_od.application.currency_war.kernel.cw_evolution import _locked_protected_names

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
    from sr_od.application.currency_war.kernel.cw_intention import _line_hoard
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
    from sr_od.application.currency_war.kernel.cw_state import _recount_board
    s.board = _recount_board(dep)
    return s


# ==================== w192_seele_scope ====================

import dataclasses

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_evolution import (
    EvolutionState,
    _locked_protected_names,
    evolution_step,
)
from sr_od.application.currency_war.kernel.cw_intention import IntentionState

from sr_od.application.currency_war.kernel.cw_battle_calib import _board_factions_of
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    CompTransaction,
    GameState,
    _recount_board,
    simulate,
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

_REG = DEFAULT_REGISTRY
_REG_SCOPE_OFF = dataclasses.replace(_REG, guard_seele_scope_enabled=False)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v2_round_key = (1, 5)
    return s


def _w192_seele_scope_state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 60, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 80,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _bc(name: str, faction: str = '', slot: int = 0, star: int = 1,
        row: str = 'back') -> BenchChar:
    if not faction:
        faction = (CHARACTERS[name].factions or ['?'])[0]
    return BenchChar(slot=slot, char_id=name, faction=faction,
                     position_pref=row, star=star)


def _sell_cands(st: GameState, sess: StrategySession, reg=_REG):
    return [c for c in generate_candidates(st, sess, reg)
            if c.tag in ('off_target', 'for_gold', 'free_bench')]


# ===== ①-⑥ 卖侧守卫辖域 =====


def test_guard_blocks_seele_sole_core() -> None:
    """①希儿唯一种子:在手副本 1(单卡依赖体系的不可替核心)→ 三卖
    tag 候选全无 + 弱序键 None + 谓词真(W190 洞一)。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('希儿', '贝洛伯格')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True
    assert _sell_cands(st, sess) == []
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is None


def test_guard_blocks_amp_below_formation_with_core() -> None:
    """②有核心·跌破成型门槛:希儿在手 + 唯一贝件娜塔莎(贝阵营 1≤2)
    → 卖拒(卖出使放大阵营跌破成型线 2,与 TT 系 owned≤tier 同构)。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('娜塔莎', '贝洛伯格', 1)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG) is True
    assert sell_priority_key(st.bench[1], st, sess, None, _REG) is None


def test_guard_not_govern_redundant_amp_with_core() -> None:
    """③有核心·成型线以上冗余:希儿 + 佩拉/娜塔莎/杰帕德(贝 3>2)
    → 佩拉照旧可卖(体系有余量时清仓不受辖)。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('佩拉', '贝洛伯格', 1),
                       _bc('娜塔莎', '贝洛伯格', 2),
                       _bc('杰帕德', '贝洛伯格', 3)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG) is False
    names = [c.breakdown_hint.get('name') for c in _sell_cands(st, sess)]
    assert '佩拉' in names, f'冗余放大件应可卖:{names}'


def test_guard_not_govern_amp_without_core() -> None:
    """④无核心不辖(域修正主锁):孤立花火(量子同频,无希儿在手)
    → off_target 照旧——无条件辖首版的回归形态(130/280/37 型:
    孤立放大件被禁卖堵 bench/被保护占 cap);transition_combos:
    没有希儿时量子/贝不能独立当过渡。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('花火', '盛会之星')])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is False
    cands = _sell_cands(st, sess)
    assert [c.breakdown_hint.get('name') for c in cands] == ['花火']
    assert cands[0].tag == 'off_target'
    assert sell_priority_key(st.bench[0], st, sess, None, _REG) is not None


def test_guard_core_sole_copy_caliber() -> None:
    """⑤核心种子口径:bench 希儿 + deployed 娜塔莎(贝)→ 希儿仍是
    唯一希儿副本 → 卖拒(放大件在体不解除核心唯一性;第二张希儿
    才构成冗余)。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('希儿', '贝洛伯格')],
                deployed=[_bc('娜塔莎', '贝洛伯格', slot=9)])
    assert sole_engine_sell_blocked(st.bench[0], st, _REG) is True


def test_flag_off_restores_w188_behavior() -> None:
    """⑥guard_seele_scope_enabled=False 逐位回退:有核心的唯一放大
    件重新生成 off_target 卖候选 + 弱序键非 None(=W188 后行为;
    TT 三羁绊辖域由 sell_sole_engine_guard_enabled 独立辖,见 W184 ⑥)。"""
    sess = _sess()
    st = _w192_seele_scope_state(bench=[_bc('希儿', '贝洛伯格', 0),
                       _bc('娜塔莎', '贝洛伯格', 1)])
    assert sole_engine_sell_blocked(st.bench[1], st, _REG_SCOPE_OFF) is False
    cands = _sell_cands(st, sess, _REG_SCOPE_OFF)
    names = [c.breakdown_hint.get('name') for c in cands]
    assert '娜塔莎' in names and cands[names.index('娜塔莎')].tag \
        == 'off_target'
    assert sell_priority_key(st.bench[1], st, sess, None,
                             _REG_SCOPE_OFF) is not None


# ===== ⑦-⑧ 保护集/补完事务辖域 =====


def test_locked_protected_names_core_conditional() -> None:
    """⑦保护集单元:希儿恒入集(seele_scope 开);放大件佩拉仅
    core_in_hand=True 时入;非体系散件(银枝)不入;scope off 回
    旧辖域(仅 TT 三羁绊)。"""
    sess = _sess()
    line = [_bc('希儿', '贝洛伯格', 0), _bc('佩拉', '贝洛伯格', 1),
            _bc('银枝', '星间旅人', 2)]
    # 默认(core_in_hand=False):仅希儿恒入集(本函数只见 old_line,
    # 全池核心判定由调用方从 state 计算后传入)
    assert _locked_protected_names(line, sess) == {'希儿'}
    assert _locked_protected_names(line, sess,
                                   seele_core_in_hand=True) \
        == {'希儿', '佩拉'}
    assert _locked_protected_names(line, sess, seele_scope=False) == set()


def test_completion_undeploy_keeps_seele_engine() -> None:
    """⑧补完事务集成(W190 洞二构造):pair={仙舟,列车}(希儿系∉pair),
    deployed 希儿+佩拉(贝2,引擎已成型)+5 散件占满 cap,bench 列车×2
    → 补完 undeploy 只吃非希儿系散件(引擎数不减);scope off 时
    undeploy 吃希儿+佩拉(旧行为=洞的构造性复现)。

    注意:计数层面补完方新成的列车引擎可在总数上抵平——洞在「希儿系
    体系」被清空(键级:补完后希儿不在场),非计数差。
    """
    # 散件全 cost≥3(佩拉 cost2 = 唯一最弱,保证 scope off 差分确定)
    _SEELE = ('希儿', '佩拉')
    _FILL = ('镜流', '黄泉', 'Saber', '那刻夏', '布洛妮娅')
    st = GameState()
    st.plane = 1
    st.round_num = 4
    st.level = 7
    st.gold = 30
    st.bench = [_bc('姬子·启行'), _bc('三月七')]
    st.deployed = [
        (_bc(n, row='front') if i < 3 else _bc(n))
        for i, n in enumerate((*_SEELE, *_FILL))]
    st.board = _recount_board(st.deployed)
    sess = StrategySession()
    sess.v3_intention = IntentionState(p1_pair=('仙舟', '列车同行'))

    def _tx(seele_scope: bool) -> CompTransaction:
        txs = [a for a in evolution_step(st, sess, EvolutionState(),
                                         seele_scope=seele_scope)
               if isinstance(a, CompTransaction)
               and 'engine_complete' in (a.reason or '')]
        assert txs, '列车 owned2≥2∧上场0 缺口应发补完事务'
        return txs[0]

    # scope on:undeploy 不含希儿系贡献件;事务 applied;希儿系保住
    tx = _tx(True)
    downed = {st.deployed[i].char_id for i in (tx.undeploy or [])}
    assert downed <= set(_FILL), f'希儿系贡献件被下场:{downed}'
    out = simulate(st, tx)
    assert out.action_log[-1]['result'] == 'applied', out.action_log[-1]
    assert '希儿' in {d.char_id for d in out.deployed
                    if d is not None and d.char_id}   # ADR-0392 滤 None
    assert _board_factions_of(out.deployed).get('贝洛伯格', 0) >= 2

    # scope off:undeploy 吃希儿+佩拉(最弱两件,均无 TT 保护)= W190
    # 洞二旧行为的构造性复现——希儿系引擎体系 1→0
    tx_off = _tx(False)
    downed_off = {st.deployed[i].char_id
                  for i in (tx_off.undeploy or [])}
    assert downed_off == {'希儿', '佩拉'}, \
        f'scope off 应下希儿+佩拉(旧行为):{downed_off}'
    out_off = simulate(st, tx_off)
    assert out_off.action_log[-1]['result'] == 'applied'
    names_off = {d.char_id for d in out_off.deployed
                 if d is not None and d.char_id}   # ADR-0392 滤 None
    assert '希儿' not in names_off, 'scope off:希儿系单卡被下场(旧行为)'


# ==================== line_gate_relock ====================

import dataclasses
import math

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_intention import (
    CORE_MISS_N,
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_line_switch import (
    gate_counterfactual,
    p_bar_faction,
    survival_gate,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)

from sr_od.application.currency_war.sim.checks.decision_v2 import check_line_gate_decision_bits, check_line_gate_starvation_anchor, check_line_switch_midgame_bucket

_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)

#: P2 位面节点表(与 W379 夹具同款)
P2_TABLE = ['battle', 'battle', 'encounter', 'reward',
            'encounter', 'reward', 'boss']

#: 证据组 B 夹具(同 test_cw_w379_gate_v2_wire:异线「万敌单C」厚度证据)
_line_gate_relock_EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _line_gate_relock_state(plane: int = 2, **kw) -> GameState:
    s = GameState()
    s.plane = plane
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    s.hp = kw.get('hp', 20)          # 低血=投影存活轮数短(门收紧方向)
    s.gold = kw.get('gold', 30)
    s.active_env = kw.get('env', '')
    for name in kw.get('shop', []):
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel.cw_state import ShopCard
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions
                               else '?',
                               cost=ch.cost if ch else 3))
    for name in kw.get('bench', []):
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions
                                 else '?', star=1))
    return s


def _line_gate_relock_sess(plane: int = 2) -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(P2_TABLE)
    s.plane_node_table_plane = plane
    return s


def _weak_on_xianzhou(registry=None) -> tuple[IntentionState, StrategySession]:
    """走真实状态机抵达 weak(锁希儿量子 → 核心断供证据撤销;同 W379)。
    撤销出口①同时暂存 prev_lock_layer=3(v3 R-C)。"""
    from sr_od.application.currency_war.kernel.cw_intention import (
        core_miss_n_required,
    )
    reg = registry or DEFAULT_REGISTRY
    sess = _line_gate_relock_sess()
    ist = update_intention(_line_gate_relock_state(shop=['希儿']), IntentionState(),
                           sess, registry=registry)
    assert ist.locked_comp == '希儿量子', '夹具前提:③锁希儿量子'
    assert ist.lock_layer == 3, '夹具前提:③信号层=3'
    gone = _line_gate_relock_state(bench=_line_gate_relock_EVIDENCE_BENCH)
    need = max(CORE_MISS_N,
               core_miss_n_required('希儿', 5, reg.revoke_miss_tolerance_eps))
    for _ in range(need):
        update_intention(gone, ist, sess, registry=registry)
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子', \
        '夹具前提:撤销出口①降级弱意向'
    assert ist.prev_lock_layer == 3, '夹具前提:v3 R-C 原锁层已暂存'
    return ist, sess


# --- §6-6 轨迹锁(FM-9 原场景;v3 R-A 门感知滞回闩) ------------------------------


def test_line_gate_v3_latch_trajectory_no_cycle() -> None:
    """FM-9 原场景逐帧轨迹(DESIGN v3 §3-4):持续①层异线信号 + miss
    越阈 + P2 晚盘帧。
    t0:出口①降级 weak(prev_lock_layer=3 暂存);
    t1:best=B → 门拦 → 闩置位 + 一次性回锁原线(lock_layer 恢复 3);
    t2..T:locked 吸收态,出口①②被闩抑制 → 零转移(miss 照涨无消费)。
    同时钉死「永久 weak」与「周期-3 环」两个失败形态;relock 恰 1 次
    (G4 判据 1 的帧级对应)。"""
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    # t1:首次门拦截帧 = 闩置位 + 一次性回锁
    out1 = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert out1.phase == 'locked' and out1.locked_comp == '希儿量子'
    assert out1.last_event == 'gate_relock:希儿量子'
    assert out1.lock_layer == 3, 'FM-11:回锁恢复原锁层(非回锁信号层 1)'
    assert sess.v3_line_gate_latch is True
    assert sess.v3_line_gate_latch_plane == 2
    assert sess.line_switch_block_counts == {('希儿量子', '列车同行'): 1}
    assert sess.v3_line_gate_blocked is True
    assert sess.v3_line_gate_cf_blocked is True   # on 臂=门判定本身
    # t2..t4:闩存续期 → locked 吸收、零转移(出口①②抑制,miss 无消费)
    prev_event = out1.last_event
    for i in range(3):
        out = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20),
                               out1, sess, registry=_REG_GATE)
        assert out.phase == 'locked' and out.locked_comp == '希儿量子', \
            f'闩后第{i}帧:吸收态零转移'
        assert out.last_event == prev_event, '闩后无任何状态转移事件'
    assert sess.line_switch_block_counts == {('希儿量子', '列车同行'): 1}, \
        '闩后不再有拦截(去程已冻结)'


def test_line_gate_v3_infinite_original_line_weak_terminal() -> None:
    """对照帧①(DESIGN §6-6):原线 E=inf → 闩仍置位但状态停 weak
    (静态不可达原线的跨线骨架囤货/demoted/P3 兜底是合法终态,§3-4)。"""
    import sr_od.application.currency_war.kernel.cw_intention as ci
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    orig = ci.e_rounds

    def fake(comp, state, registry=None):
        if comp.name == '希儿量子':
            return math.inf   # 构造帧:原线静态不可达(p̄=0 同义)
        return orig(comp, state, registry)

    ci.e_rounds = fake
    try:
        out = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                               sess, registry=_REG_GATE)
    finally:
        ci.e_rounds = orig
    assert sess.v3_line_gate_latch is True, '闩照常置位(门拦过)'
    assert out.phase == 'weak' and out.locked_comp == '', '不回锁,停 weak'
    assert out.last_event.startswith('gate_hold:')


def test_line_gate_v3_inf_candidate_never_locks() -> None:
    """对照帧②(DESIGN §6-2⑤/R-E):E=inf 候选线信号帧 → 不落锁——
    survival_gate 对 inf 改拦 'alt_inf'(拦截归属唯一化;v2 的「上游
    已拦」假前提已勘误),闩置位帧回锁的是原线,候选线 B 全程不落锁。"""
    import sr_od.application.currency_war.kernel.cw_intention as ci
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    orig = ci.e_rounds

    def fake(comp, state, registry=None):
        if comp.name == '列车同行':
            return math.inf   # 构造帧:候选线 p̄=0 静态不可达
        return orig(comp, state, registry)

    ci.e_rounds = fake
    try:
        assert survival_gate(_line_gate_relock_state(hp=20), _line_gate_relock_sess(), math.inf,
                             _REG_GATE) == (False, 'alt_inf')
        out = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                               sess, registry=_REG_GATE)
    finally:
        ci.e_rounds = orig
    assert out.locked_comp == '希儿量子', '候选线 E=inf 不得落锁,回锁原线'
    assert out.last_event == 'gate_relock:希儿量子'


# --- W696 审计修正锁(D3/D4) ----------------------------------------------------


def test_line_gate_v3_latch_suspends_frozen_eviction() -> None:
    """D3 修正锁(W696 审计):闩存续期冻结驱逐挂起——驱逐会产生设计外
    转移 locked→unlocked→同帧可无门落新线,破坏「转移冻结」吸收态
    (DESIGN v3 §3-3)。闩下窗口关闭超限帧不再驱逐,状态恒 locked、零
    转移事件;frozen_rounds 照常累计(位面切换清闩后恢复既有驱逐路径)。"""
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    out1 = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert out1.phase == 'locked' and sess.v3_line_gate_latch is True, \
        '夹具前提:闩已置位'
    # 窗口关闭帧(level=3 刷不出 5 费核心)连驱 9 帧 > 位面剩余节点 7
    # ——修复前第 8 帧即 evict:frozen 落 unlocked
    prev = out1
    for i in range(9):
        prev = update_intention(_line_gate_relock_state(level=3, hp=20, round_num=1),
                                prev, sess, registry=_REG_GATE)
        assert prev.phase == 'locked' and prev.locked_comp == '希儿量子', \
            f'闩存续期第{i + 1}关闭帧:驱逐必须挂起(吸收态零转移)'
        assert not prev.last_event.startswith('evict:frozen')
        assert '希儿量子' not in prev.evicted


def test_line_gate_v3_plane_switch_clears_latch_chain() -> None:
    """D4 修正锁(W696 审计,DESIGN §6-7 清零链):位面切换清零四字段
    逐一断言——①闩位 False ②闩位面 None ③prev_lock_layer 0
    ④tracks miss_count 归零(帧内再自增前, prior 阈值级大值不复现)。"""
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    out1 = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert sess.v3_line_gate_latch is True, '夹具前提:闩置位'
    assert out1.prev_lock_layer == 3, '夹具前提:暂存=原锁层'
    pre_miss = out1.tracks['希儿量子'].miss_count
    assert pre_miss >= 1, '夹具前提:miss 计数非零(闩内持续累计)'
    # 位面切换 P2→P3(无信号帧:不触发出口,清零链可孤立观察)
    out2 = update_intention(_line_gate_relock_state(plane=3, round_num=1, hp=20),
                            out1, sess, registry=_REG_GATE)
    assert sess.v3_line_gate_latch is False, '清零①:闩位'
    assert sess.v3_line_gate_latch_plane is None, '清零②:闩位面'
    assert out2.prev_lock_layer == 0, '清零③:暂存锁层'
    assert out2.tracks['希儿量子'].miss_count < pre_miss, \
        '清零④:陈旧 miss 不复现(本帧自增后=1,未清则 ≥ 阈值)'


def test_line_gate_v3_plane_scope_narrowed() -> None:
    """辖域断言锁(DESIGN §6-2③④):plane=1 与 plane=3 帧门恒放行
    (v3 R-G 收窄 plane==2:P2 损血表不辖 P3,FM-12);开关关恒放行
    (零漂移)。"""
    sess = _line_gate_relock_sess()
    st_p1 = _line_gate_relock_state(plane=1, hp=20)
    st_p3 = _line_gate_relock_state(plane=3, hp=20)
    assert survival_gate(st_p1, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    assert survival_gate(st_p3, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    assert survival_gate(_line_gate_relock_state(hp=20), sess, 3.0,
                         DEFAULT_REGISTRY) == (True, 'gate_off')


# --- §6-7 FM-11 撤销面锁(v3 R-C) ----------------------------------------------


def test_line_gate_v3_relock_preserves_revoke_face() -> None:
    """FM-11 消解锁(DESIGN v3 §6-7/R-C):闩回锁恢复原锁层(3)而非
    回锁信号层(1)→ ①层优线仍可经出口②撤销(撤销面未被收窄)。
    位面切换清闩断言含在本锁前半;出口②对照用干净 session 构造帧
    (P3 帧的强制锁会同一帧消费 weak 态,属 P3 既有语义,不混入本锁)。"""
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    out1 = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert out1.phase == 'locked' and out1.lock_layer == 3, '夹具前提:闩回锁恢复层3'
    assert sess.v3_line_gate_latch is True
    # 位面切换 P2→P3:闩清零(phase!=locked → P3 强制锁随后接管,既有语义)
    out2 = update_intention(_line_gate_relock_state(plane=3, round_num=1, hp=20),
                            out1, sess, registry=_REG_GATE)
    assert sess.v3_line_gate_latch is False
    assert sess.v3_line_gate_latch_plane is None
    # FM-11 实质(干净 session 构造帧,排除闩/强制锁干扰):
    # 回锁态 lock_layer=3 → ①层优线可经出口②撤销;
    # 反事实对照:若回锁残留 layer=1(未恢复),同一帧撤销不可达。
    frame = _line_gate_relock_state(env='列车同行概念股', shop=['姬子·启行'], hp=100)
    base3 = IntentionState(phase='locked', locked_comp='希儿量子',
                           lock_layer=3)
    out3 = update_intention(frame, base3, _line_gate_relock_sess())
    assert out3.phase == 'weak' and out3.weak_comp == '希儿量子'
    assert out3.last_event.startswith('revoke:higher:列车同行')
    assert out3.prev_lock_layer == 3, '撤销暂存原锁层(闩回锁恢复的消费面)'
    base1 = IntentionState(phase='locked', locked_comp='希儿量子',
                           lock_layer=1)
    out4 = update_intention(frame, base1, _line_gate_relock_sess())
    assert out4.phase == 'locked' and out4.locked_comp == '希儿量子', \
        '反事实对照:layer=1 回锁态下①层信号不可撤(FM-11 病灶形状)'


# --- §6-3 瞬态敏感对拍锁(FM-10;v3 R-H 门稳定性主承载面) ------------------------


def _synth_comp(tag: str, need: int) -> Comp:
    """构造线:单一标签档位(form_tiers 只喂 e_rounds 的 distance/p̄)。"""
    return Comp(name='FM10构造线', factions=['追击'], core_chars=['希儿'],
                form_tiers={tag: need}, strength='A',
                form_difficulty='easy', early_power='高')


def _tabled_sess() -> StrategySession:
    s = StrategySession()
    s.plane_node_table = list(P2_TABLE)
    s.plane_node_table_plane = 2
    s.round_num = 1
    return s


def e_rounds_of(comp: Comp, state: GameState, reg) -> float:
    from sr_od.application.currency_war.kernel.cw_line_switch import e_rounds
    return e_rounds(comp, state, reg)


def test_line_gate_fm10_transient_gold_bench_pair() -> None:
    """FM-10 对拍锁:同一局面仅改 bench_free(板满帧 vs 空板高金帧,
    gold 两帧同值=affordable 不构成差分)→ 门结论翻转。钉「门对当帧
    经济瞬态的敏感带」入 L1:e_rounds 的 per_round=(1+min(affordable,
    bench_free))·p̄ 随当帧 bench 波动(v3 R-H:该通道 E 可翻 3-4 倍,
    比参数网格变幅大一个量级=门稳定性一阶源)。"""
    reg = _REG_GATE
    p = p_bar_faction('追击', 5)
    # 夹具前提带(查表值漂移=夹具失效信号,先红于此行,禁静默改数)
    assert 0.25 < p < 0.60, f'追击 p̄(lv5)={p:.3f} 超夹具前提带,需重锚'
    sess = _tabled_sess()
    comp = _synth_comp('追击', 3)
    full = _line_gate_relock_state(hp=50, gold=60)
    full.bench = [BenchChar(slot=i, char_id='万敌', faction='?', star=1)
                  for i in range(8)]
    free = _line_gate_relock_state(hp=50, gold=60)
    ok_full, _ = survival_gate(full, sess, e_rounds_of(comp, full, reg), reg)
    ok_free, _ = survival_gate(free, sess, e_rounds_of(comp, free, reg), reg)
    assert ok_full is False and ok_free is True, \
        'FM-10:板满帧 vs 空板帧门结论必须翻转(敏感带钉死)'
    # 反事实位同式同源(门关两帧的 P(f) 记账差分同向)
    assert gate_counterfactual(full, sess, e_rounds_of(comp, full, reg),
                               DEFAULT_REGISTRY) is True
    assert gate_counterfactual(free, sess, e_rounds_of(comp, free, reg),
                               DEFAULT_REGISTRY) is False


# --- off 臂反事实记账锁(R3;零漂移) --------------------------------------------


def test_line_gate_off_arm_records_counterfactual_bit_zero_drift() -> None:
    """门关(缺省 registry)同帧:行为零漂移(照旧落锁列车同行),但
    反事实判定位照记 P(f)=True(晚盘低血帧门判据式成立)——off 臂
    A/B 批器的拦截精度记账数据面(v3 R-F 规格补全见 gate_counterfactual
    docstring);拦截位恒 False(门关无「拦」语义)。"""
    ist, _ = _weak_on_xianzhou(None)
    sess = _line_gate_relock_sess()
    out = update_intention(_line_gate_relock_state(env='列车同行概念股', hp=20), ist, sess)
    assert out.phase == 'locked' and out.locked_comp == '列车同行'
    assert sess.v3_line_gate_blocked is False
    assert sess.v3_line_gate_cf_blocked is True


# --- §6-4 一致性检查器锁(两违规各一;禁复算) ------------------------------------


def test_check_line_gate_decision_bits_two_violations() -> None:
    """检查器两条违规的构造反例(DESIGN §6-4):①gate_hold 行为但拦截
    位 False=账本漏记;②拦截位 True 但反事实位 False=位间矛盾。干净行
    不报。检查器只读位,不调判据式(禁复算纪律,函数体内无
    survival_gate/rounds_alive 引用=结构性保证)。"""
    rows = [
        {'ts': 1, 'line_gate_blocked': True, 'line_gate_cf_blocked': True,
         'v3_intention': {'last_event': 'gate_hold:A->B'}},
        {'ts': 2, 'line_gate_blocked': False, 'line_gate_cf_blocked': True,
         'v3_intention': {'last_event': 'gate_hold:A->B'}},
        {'ts': 3, 'line_gate_blocked': True, 'line_gate_cf_blocked': False,
         'v3_intention': {'last_event': 'lock:B'}},
    ]
    v = check_line_gate_decision_bits(rows)
    assert len(v) == 2, v
    assert '行1' in v[0] and '账本漏记' in v[0]
    assert '行2' in v[1] and '位间矛盾' in v[1]
    assert check_line_gate_decision_bits(rows[:1]) == []


# --- G4 三判据锚锁(v3 R-B) + 中盘分桶锁(v3 R-D) --------------------------------


def test_check_line_gate_starvation_anchor_v3() -> None:
    """G4 三判据(DESIGN v3 §5.1-G4):①relock ≤1/局(>1=结构违规);
    ②局末 weak∧非降格占比 on ≤ off;③闩置位局闩后转移局占比=0
    (环病灶直接可见)。"""
    good = [
        {'ts': 1, 'line_gate_blocked': True, 'target_comp': '',
         'v3_intention': {'last_event': 'gate_hold:A->B', 'phase': 'weak'}},
        {'ts': 2, 'line_gate_blocked': True, 'target_comp': 'A',
         'v3_intention': {'last_event': 'gate_relock:A', 'phase': 'locked'}},
        {'ts': 3, 'line_gate_blocked': False, 'target_comp': 'A',
         'v3_intention': {'last_event': 'gate_relock:A', 'phase': 'locked'}},
    ]
    cycle = good + [
        {'ts': 4, 'line_gate_blocked': False, 'target_comp': 'B',
         'v3_intention': {'last_event': 'revoke:miss6', 'phase': 'weak'}},
    ]
    off = [{'ts': 1, 'target_comp': 'A',
            'v3_intention': {'last_event': 'lock:A', 'phase': 'locked'}}]
    rep = check_line_gate_starvation_anchor([good, cycle], [off, off])
    assert rep['on']['relock_gt1_runs'] == 0
    assert rep['on']['latch_then_transfer_runs'] == 1, '环局必须被判据 3 捕获'
    assert any('闩置位后出现转移' in v for v in rep['violations'])
    assert rep['off']['end_weak_rate'] == 0.0
    # relock >1 结构违规(闩被实现成计数回锁;第二次 relock 须经一次
    # 转移离开 locked 再回来,事件转移口径才计第二次)
    twice = good + [
        {'ts': 4, 'line_gate_blocked': False, 'target_comp': '',
         'v3_intention': {'last_event': 'revoke:miss6', 'phase': 'weak'}},
        {'ts': 5, 'line_gate_blocked': True, 'target_comp': 'A',
         'v3_intention': {'last_event': 'gate_relock:A', 'phase': 'locked'}},
    ]
    rep2 = check_line_gate_starvation_anchor([twice])
    assert rep2['on']['relock_gt1_runs'] == 1
    assert any('relock 2 次' in v for v in rep2['violations'])
    # 判据 2:on 末帧 weak 占比 > off → 违规
    weakend = [{'ts': 1, 'line_gate_blocked': True, 'target_comp': '',
                'v3_intention': {'last_event': 'gate_hold:A->B',
                                 'phase': 'weak'}}]
    rep3 = check_line_gate_starvation_anchor([weakend], [off])
    assert rep3['on']['end_weak_rate'] == 1.0
    assert any('on 1.0 > off 0.0' in v for v in rep3['violations'])


def test_check_line_gate_anchor_d1_d2_predicate_fixes() -> None:
    """D1/D2 修正锁(W696 审计):
    D1——原线 E=inf 停 weak 是合法终态,逐帧 gate_hold 复现行不入转移
    谓词(修复前误判违规);
    D2——判据 3 窗口收窄闩位面段(plane==2),P2→P3 后的合法转移
    (P3 强制锁接管等)不计;对照:P2 段内转移仍违规。"""
    holds = [{'ts': t, 'plane': 2, 'line_gate_blocked': True,
              'target_comp': '',
              'v3_intention': {'last_event': 'gate_hold:A->B',
                               'phase': 'weak'}}
             for t in (1, 2, 3)]
    # D1:纯 gate_hold 复现(E=inf 停 weak 轨迹)→ 零违规
    rep = check_line_gate_starvation_anchor([holds])
    assert rep['violations'] == [], 'D1:合法终态 gate_hold 不得计违规'
    # D2:闩后 P2 段零转移,P3 段 revoke → 不违规(窗口已收窄)
    cross = holds + [{'ts': 4, 'plane': 3, 'line_gate_blocked': False,
                      'target_comp': '',
                      'v3_intention': {'last_event': 'revoke:miss6',
                                       'phase': 'weak'}}]
    rep2 = check_line_gate_starvation_anchor([cross])
    assert rep2['violations'] == [], 'D2:出闩位面的合法转移不计'
    # 对照:P2 段内转移仍被抓
    inplane = holds[:2] + [{'ts': 3, 'plane': 2, 'line_gate_blocked': False,
                            'target_comp': '',
                            'v3_intention': {'last_event': 'revoke:miss6',
                                             'phase': 'weak'}}]
    rep3 = check_line_gate_starvation_anchor([inplane])
    assert len(rep3['violations']) == 1 and '闩置位后出现转移' in rep3['violations'][0]


def test_check_line_switch_midgame_bucket_v3() -> None:
    """中盘分桶(DESIGN v3 R-D):r≤4 = 双侧不劣守卫(off ±95% Wilson
    参考带,带外违规);r5-r9 = 纯披露(期望方向下降,无判定)。"""
    off = [[{'ts': 1, 'round_num': 2, 'target_comp': 'A'},
            {'ts': 2, 'round_num': 3, 'target_comp': 'A'},   # 中盘 0/10
            {'ts': 3, 'round_num': 6, 'target_comp': 'A'},
            {'ts': 4, 'round_num': 7, 'target_comp': 'A'},
            {'ts': 5, 'round_num': 6, 'target_comp': 'B'},
            {'ts': 6, 'round_num': 7, 'target_comp': 'C'},
            {'ts': 7, 'round_num': 6, 'target_comp': 'A'},
            {'ts': 8, 'round_num': 7, 'target_comp': 'B'},
            {'ts': 9, 'round_num': 6, 'target_comp': 'C'},
            {'ts': 10, 'round_num': 7, 'target_comp': 'A'}]]
    on_in = [[{'ts': 1, 'round_num': 2, 'target_comp': 'A'},
              {'ts': 2, 'round_num': 3, 'target_comp': 'A'},   # 中盘 0/10,带内
              {'ts': 3, 'round_num': 6, 'target_comp': 'A'},
              {'ts': 4, 'round_num': 7, 'target_comp': 'A'}]]
    rep = check_line_switch_midgame_bucket(off, on_in)
    assert rep['violations'] == [], '带内不违规'
    assert rep['r_le4_band']['lo'] >= 0.0 and rep['r_le4_band']['hi'] <= 1.0
    # on 中盘率飙高(9/10)→ 带外违规;末窗披露照报(期望方向下降)
    on_out = [[{'ts': 1, 'round_num': 2, 'target_comp': 'A'},
               {'ts': 2, 'round_num': 3, 'target_comp': 'B'},
               {'ts': 3, 'round_num': 2, 'target_comp': 'C'},
               {'ts': 4, 'round_num': 3, 'target_comp': 'A'},
               {'ts': 5, 'round_num': 2, 'target_comp': 'B'},
               {'ts': 6, 'round_num': 3, 'target_comp': 'C'},
               {'ts': 7, 'round_num': 2, 'target_comp': 'A'},
               {'ts': 8, 'round_num': 3, 'target_comp': 'B'},
               {'ts': 9, 'round_num': 2, 'target_comp': 'C'},
               {'ts': 10, 'round_num': 3, 'target_comp': 'A'}]]
    rep2 = check_line_switch_midgame_bucket(off, on_out)
    assert len(rep2['violations']) == 1 and 'r≤4' in rep2['violations'][0]
    assert 'rate' in rep2['on']['r5_r9']   # 纯披露字段在,无 r5_r9 判定
