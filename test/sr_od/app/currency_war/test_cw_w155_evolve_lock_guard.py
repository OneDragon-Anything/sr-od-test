# -*- coding: utf-8 -*-
"""W155/ADR-0360 evolve 换血事务锁定目标件保护单帧锁测试。

W147 归因(W143 执行半边):evolve 换血风暴的挤出 = 恶性被动挤出非
主动卖(目标件离场 60 笔中 59 被动)——①锁定后仍有 216 轮次 off-lock
evolve 提案(target_factions 不含锁定 faction → 锁定目标件被划进
old_line 整档解除);②strict 局挤出后 59% 不回场;③rejected 死循环
34 局(duplicate_on_board 同因重提零清障)。

四把锁(W155 三件套 + 顺手清障,全部优先级/围栏式非禁换):
1. 提案层目标约束:锁定帧 off-lock 提案在选择序中降级(off_lock_penalty);
2. 保留序:execute_replacement 溢出卖出先吃非保护件(锁定目标件/
   引擎件与 ADR-0339 种子窗同级);
3. deploy 围栏:锁定帧体系键并入围栏放行集(ADR-0226 同型扩位);
4. 提案去重:bench 新线候选与留场新线 deployed 同名剔除(生成侧守卫,
   duplicate_on_board 根因形态)+ 被拒事务不发射/退避 2 轮。

回归:未锁局(无锁定帧)evolve 行为不变(penalty 恒 0 语义)。
"""
from __future__ import annotations

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
