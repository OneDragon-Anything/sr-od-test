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
    # form_tiers 键(修复项2,2026-08-31:绯英主羁绊=欢愉+星间旅人,能量降 flex 挂件)
    assert scope == frozenset({'欢愉', '星间旅人'})


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


# ==================== (line_gate_relock 已随 C4 开关族删除) ====================
# (换线存活门轨迹锁/门闩/反事实位/检查器锁段已随 line_switch_survival_
#  gate_enabled 开关族删除——旧方案清退批,清查报告 OLD_MIX_AUDIT §1.3;
#  cw_intention 门闩分支、cw_line_switch.survival_gate/gate_counterfactual/
#  register_gate_block、sim.checks 三检查器与 v3_line_gate_* 决策位同批删。)
