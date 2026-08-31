# -*- coding: utf-8 -*-
"""test_cw_intention_switch 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w119_switch_authority: test_cw_w119_switch_authority.py
- w126_switch_dispatch: test_cw_w126_switch_dispatch.py
- intention: test_cw_intention.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w119_switch_authority ====================

from dataclasses import replace
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    intention_core,
)
from sr_od.application.currency_war.kernel.cw_state import (
    Action,
    BenchChar,
    BuyCard,
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import (
    _active_floor,
    arbitrate,
)
from sr_od.application.currency_war.decision.decision_v2.candidates import Candidate
from sr_od.application.currency_war.decision.decision_v2.discipline import (
    _streak_floor,
    assess_discipline,
    boss_window_active,
)
from sr_od.application.currency_war.decision.decision_v2.ev import (
    REWARD_BATTLE_ENVS,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    formed_stop_active,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
)

_REG = DEFAULT_REGISTRY


def _card(name: str, faction: str = '仙舟罗浮',
          cost: int = 2) -> ShopCard:
    return ShopCard(name=name, faction=faction, cost=cost, x=0, star=1)


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 5, 'gold': 50, 'level': 5,
            'hp': 70, 'board': {}, 'bench': [], 'shop': [],
            'node_type': 'battle'}
    base.update(kw)
    return GameState(**base)


def _sess_locked(comp: str = 'DOT队') -> StrategySession:
    sess = StrategySession()
    sess.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    sess.v3_mode = 'economy'
    return sess


def _formed_frame(comp_name: str, **kw) -> GameState:
    """锁定线成型帧:form_tiers 全满(board)+ 核心上场 2★。"""
    comp = get_comp(comp_name)
    core = intention_core(comp)
    base = {
        'plane': 1, 'round_num': 7, 'gold': 55, 'level': 5, 'hp': 60,
        'board': {f: t for f, t in comp.form_tiers.items()},
        'deployed': [BenchChar(slot=0, char_id=core,
                               faction=next(iter(comp.form_tiers)),
                               star=2)],
        'bench': [], 'shop': [], 'node_type': 'battle',
    }
    base.update(kw)
    return GameState(**base)


# --- ① FORM 段 EV 正破息买放行 ----------------------------------------------


def test_form_ev_positive_break_buy_allowed() -> None:
    """①FORM 相位金 51:跨档买(51→47,破 1 档)按 EV 授权裁决——
    EV=V−C>0 放行(log 带 ev_auth 授权依据 trace);EV≤0 拒(拒绝因
    「EV≤0 破息拒」)。V=层3分剥离息分量(bd['int_emb']),本锁直接
    注入 (val, bd) 锁**门语义**(EV 阈值/方向/trace);int_emb 与评分
    的单一源契约另锁(见 test_int_emb_contract)。"""
    sess = StrategySession()   # unlocked 空 board → FORM
    sess.v3_mode = 'economy'
    st = _state(round_num=5, gold=51, node_type='battle')
    cand = Candidate(action=BuyCard(_card('引擎件', cost=4), reason=''),
                     tag='engine_seed', source='shop')
    # EV 正:V = 30 −(−25) = 55,C = 1 档×min(R,3)=3(买侧回档
    # 折中口径)→ EV≈52 > 0 → 放行
    res_pos = arbitrate([(cand, 30.0, {'int_emb': -25.0})], st, sess,
                        _REG)
    row = next(r for r in res_pos.log if r['tag'] == 'engine_seed')
    assert row['accepted'] is True, row
    assert row['ev_auth']['ev_auth'] > 0, row   # 授权依据 trace 在场
    assert any(isinstance(a, BuyCard) for a in res_pos.actions)
    # EV 负:V = 1 − 0 = 1 < C(3)→ 拒(前 C=1×R≈23,标定后买侧
    # C=回档折中口径——低价值买仍拒,门语义保留)
    sess2 = StrategySession()
    sess2.v3_mode = 'economy'
    res_neg = arbitrate([(cand, 1.0, {'int_emb': 0.0})], st, sess2,
                        _REG)
    row2 = next(r for r in res_neg.log if r['tag'] == 'engine_seed')
    assert row2['accepted'] is False, row2
    assert 'EV≤0 破息拒' in (row2['reject'] or ''), row2


def test_int_emb_contract() -> None:
    """int_emb 单一源契约:score_candidate 的 breakdown 内嵌息分量=
    息差(after−base);无息差通道(refresh/无 after)恒 0。仲裁层
    interest_rule 的 V 剥离消费它,禁双源。"""
    from sr_od.application.currency_war.decision.decision_v2.scoring import (
        score_candidate as _sc,
    )
    # 常规买候选(bench 件,息差 0——金不变):int_emb=Δinterest
    st = _state(round_num=3, gold=30, node_type='battle',
                bench=[BenchChar(slot=0, char_id='桑博',
                                 faction='仙舟罗浮', star=1)],
                shop=[])
    from sr_od.application.currency_war.kernel.cw_state import SellBench
    sell = Candidate(action=SellBench(bench_idx=0, income=1),
                     tag='off_target', source='bench',
                     breakdown_hint={'name': '桑博'})
    _val, bd = _sc(sell, st, StrategySession(), _REG)
    assert bd['int_emb'] == (bd['after']['interest']
                             - bd['base']['interest'])
    # refresh 候选:int_emb=0
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    rf = Candidate(action=RefreshShop(cost=2), tag='refresh',
                   source='shop')
    _v2, bd2 = _sc(rf, st, StrategySession(), _REG)
    assert bd2['int_emb'] == 0.0


# --- ② EV≤0 升级被拒(seed6 形态帧)------------------------------------------


def test_levelup_rejected_seed6_frame() -> None:
    """②seed6 形态帧:P1 金 49/lv6/从未满息/无人口位(deployed=cap,
    bench 无目标件)→ LevelUp 被 EV 总账拒(平台延迟账),拒绝因可见
    「息引擎总账拒」。"""
    sess = StrategySession()   # unlocked → FORM;last_streak 无
    sess.v3_mode = 'economy'
    st = _state(round_num=6, gold=49, level=6,
                deployed=[BenchChar(slot=i, char_id=f'杂件{i}',
                                    faction='公司', star=1)
                          for i in range(6)],
                bench=[BenchChar(slot=0, char_id='散件甲',
                                 faction='公司', star=1)],
                shop=[])
    assert st.max_units() >= 6 and len(st.deployed) >= st.max_units(), \
        '前置:deployed=cap(无人口位)'
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, sess, _REG)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert row['accepted'] is False, row
    assert '息引擎总账拒' in (row['reject'] or ''), row
    assert not any(isinstance(a, LevelUp) for a in res.actions)


# --- ③ formed_stop 辖轮 comp 派生 -------------------------------------------


def test_formed_stop_round_comp_derived() -> None:
    """③辖轮 = max(comp.typical_form_round, formed_stop_min_round):
    早成型 DOT队(typical 4→辖 7):r6 不停/r7 停;晚成型 昼神阿雅
    (typical 8→辖 8):r7 不停/r8 停。
    (语义演进史,ADR-0400 → ADR-0411:本锁曾用
    handoff_gate_enabled=False 隔离末窗承接维——该布尔字段已随
    ADR-0411 flag 家族清理删除,承接门无条件启用。现改用同款隔离
    效果的合法手段:handoff_gate_min_round 提到 9(量级常量仍在
    registry),本锁全部构造轮(r≤8)落到承接门外,gap 恒 0——隔离
    「comp 派生辖轮」语义;承接维行为由 test_cw_w227_handoff_gate 锁。)"""
    _reg_no_gate_window = replace(_REG, handoff_gate_min_round=9)
    for comp_name, stop_r, nostop_r in (('DOT队', 7, 6),
                                        ('昼神阿雅', 8, 7)):
        comp = get_comp(comp_name)
        assert comp.typical_form_round in (4, 8)   # 前置:早晚档锚
        for r, expect in ((nostop_r, False), (stop_r, True)):
            sess = _sess_locked(comp_name)
            st = _formed_frame(comp_name, round_num=r)
            assert formed_stop_active(st, sess,
                                      _reg_no_gate_window) is expect, (
                f'{comp_name} r{r}:期望 {expect}')


# --- ④ boss 窗判定合一(节点图为主)-----------------------------------------


def test_boss_window_unified_node_graph() -> None:
    """④同帧同判:node_type='battle' P1 r7(旧 discipline r≥5 会入
    boss_breaker)→ 两口径都**不**入 boss 窗(coverage=mode/economy,
    地板=相位地板);node_type='boss' 同轮 → 两口径都入(boss_breaker,
    地板=boss_floor);node_type 缺读 P1 r9 → 兜底入窗。"""
    sess = StrategySession()
    sess.v3_mode = 'economy'
    # battle 节点 + P1 r7:不入窗
    st = _state(round_num=7, node_type='battle')
    assert boss_window_active(st, sess, _REG) is False
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage != 'boss_breaker', disc
    assert _active_floor(st, sess, _REG) == _REG.form_floor   # FORM 相位
    # boss 节点同轮:入窗(两口径同判)
    st_boss = _state(round_num=7, node_type='boss')
    assert boss_window_active(st_boss, sess, _REG) is True
    disc_b = assess_discipline(st_boss, sess, _REG)
    assert disc_b.coverage == 'boss_breaker'
    assert _active_floor(st_boss, sess, _REG) == _REG.boss_floor
    # node_type 缺读 + P1 r9:兜底(全仓唯一轮数口径)
    st_n = _state(round_num=9, node_type='')
    assert boss_window_active(st_n, sess, _REG) is True


# --- ⑤ 排程接线:升级授权消费确定性排程核(批 3 预算收权重推)--------------


def test_dp_posture_consumed_by_arbiter(monkeypatch) -> None:
    """⑤升级授权随排程核翻转(接线证明,非注释非遥测):无人口位
    (deployed=cap)隔离 ① 路径;金 60(花后 52≥50 平台未破)帧锁
    排程臂放行,金 49(花后 45<50)帧锁平台越界拒。
    批 3 重推:注入对象从 ev.dp_posture(DP 退役)改为排程单一址
    cw_economy.schedule_upgrade(kernel,期 0b 下沉);producer 规则锁在 test_cw_w633_migration_b3。
    契约时代迁移(ADR-0504 无条件生效,除开关批):bench 垫一件非目标
    杂件使升级前提 pop_slot 成立(bench 有件∨cap 有空位)——否则执行侧
    前提防线在排程臂之前拒付(13-2 形态);杂件不构成人口位(①臂要求
    bench 件 ∈ 目标集),排程臂隔离意图不变。"""
    from sr_od.application.currency_war.kernel import cw_economy

    st = _state(round_num=6, gold=51, level=6,
                deployed=[BenchChar(slot=i, char_id=f'杂件{i}',
                                    faction='公司', star=1)
                          for i in range(6)],
                bench=[BenchChar(slot=0, char_id='垫件甲',
                                 faction='公司', star=1)],
                shop=[])
    assert len(st.deployed) >= st.max_units(), '前置:无人口位'
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    st60 = _state(round_num=6, gold=60, level=6,
                  deployed=list(st.deployed),
                  bench=[BenchChar(slot=0, char_id='垫件甲',
                                   faction='公司', star=1)],
                  shop=[])
    sess = StrategySession()
    sess.v3_mode = 'economy'
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda s, ss, rg=None: True)
    res_up = arbitrate([(cand, 1.0, {})], st60, sess, _REG)
    assert any(isinstance(a, LevelUp) for a in res_up.actions), \
        '排程说升且平台未破(60-4=52≥50)→ 必须放行'
    monkeypatch.setattr(cw_economy, 'schedule_upgrade',
                        lambda s, ss, rg=None: False)
    sess2 = StrategySession()
    sess2.v3_mode = 'economy'
    res_save = arbitrate([(Candidate(action=LevelUp(cost=4),
                                     tag='levelup', source='xp'),
                           1.0, {})],
                         _state(round_num=6, gold=49, level=6,
                                deployed=list(st.deployed),
                                bench=[BenchChar(slot=0, char_id='垫件甲',
                                                 faction='公司', star=1)],
                                shop=[]), sess2, _REG)
    row = next(r for r in res_save.log if r['tag'] == 'levelup')
    assert row['accepted'] is False and '息引擎总账拒' in row['reject'], row


# --- ⑥ 扑满守卫(ADR-0348;口述定谒 2026-08-26=低危战斗)---------------------


def test_overheat_reward_node_treated_as_battle() -> None:
    """⑥「经济过热」类环境 reward 节点=**奖励型战斗**(口述定谒 [16]
    +P8;F-01:扑满不掉血,真损失=打不过没奖励——轻投入凑
    羁绊刷伤害拿奖励,**禁深花保血**):
    - 战斗向刷新理由开放:r>refresh_max_round 的刷新在过热局 reward
      节点转正分——但受 **P8 上限**辖(单节点 s≤2金 → 限 1 次/节点,
      超出按无证拒回常规门恒负分);
    - 地板不降:连胜 EV 地板**不**因扑满节点降 5(_hard_node 不辖;
      boss/遭遇窗的下探授权对扑满全部不适用);
    - 环境名单从 cw_invest_data 效果文本派生(单一源断言)。"""
    from sr_od.application.currency_war.data.cw_invest_data import PLAZA_PORTALS
    # 名单派生:效果文本含「奖励节点替换」
    expect = {p.name for p in PLAZA_PORTALS
              if '奖励节点替换' in (p.effect or '')}
    assert expect == {'经济过热', '经济严重过热'}
    assert REWARD_BATTLE_ENVS == frozenset(expect)
    sess = StrategySession()
    sess.v3_mode = 'economy'
    # 地板不降:过热局 reward 节点连胜在手 → 地板原值(不掉血,
    # 深花保血没有对象)
    sess.last_streak = 2
    st_hot = _state(round_num=4, node_type='reward',
                    active_env='经济过热', gold=40)
    assert _streak_floor(st_hot, sess, _REG, 30) == 30
    # 战斗向刷新开放×P8 上限:r7(>refresh_max_round=6)reward 节点 +
    # 过热 → 首刷正分(轮计数 0<cap);同轮已刷 1 次(计数≥cap)→
    # 豁免失效回常规门恒负分;无环境对照恒负分(轮界门照辖)
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    from sr_od.application.currency_war.decision.decision_v2.scoring import (
        score_candidate as _sc,
    )
    for used, env, expect_pos in ((0, '经济过热', True),
                                  (_REG.piggy_refresh_round_cap,
                                   '经济过热', False),
                                  (0, '', False)):
        s = StrategySession()
        s.v3_mode = 'economy'
        s.v2_round_refreshes = used
        st_r = _state(round_num=7, node_type='reward',
                      active_env=env, gold=40)
        rf = Candidate(action=RefreshShop(cost=2), tag='refresh',
                       source='shop')
        v, _bd = _sc(rf, st_r, s, _REG)
        if expect_pos:
            assert v > 0, f'过热局扑满轮首刷应开放(实际 {v})'
        else:
            assert v < 0, f'豁免超限/无环境应恒负分(实际 {v})'


# --- 附2:证明批检验点锁(P5 边界/P6 无特判)-----------------------------


def test_w120_p5_c_interest_boundary() -> None:
    """P5 定理退化输出(ADR-0347 C_interest 公式的边界断言):
    金 50/51 时 D 候选被 EV 拒(跨 50 档,C_interest≥R);金 ≥52+刷价
    放行(C_interest=0,由常分决定)——「花完仍≥50」是公式的自然输出
    而非外加约束。注入 (val=0.5, int_emb=0) 锁门语义(常分口径。"""
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    cand = Candidate(action=RefreshShop(cost=2), tag='refresh',
                     source='shop')
    for gold, expect in ((50, False), (51, False), (52, True), (53, True)):
        sess = StrategySession()
        sess.v3_mode = 'economy'
        st = _state(round_num=5, gold=gold, node_type='battle')
        res = arbitrate([(cand, 0.5, {'int_emb': 0.0})], st, sess, _REG)
        row = next(r for r in res.log if r['tag'] == 'refresh')
        assert row['accepted'] is expect, (gold, row)
        if not expect:
            assert 'EV' in (row['reject'] or ''), row


def test_w120_p6_no_per_round_special_case() -> None:
    """P6:前两轮无 per-round 特判——统一 EV 路径自动给出「买」
    (零息损+全额退免费期权)。断言 r1/r2 无决策分支读 round_num 做
    买/刷的特殊放行(scoring/arbiter 源码静态检查;唯一轮界门
    refresh_max_round/bond_fallback_min_round/form_refresh_max_round 是
    ADR-0293/0340 既有门,非 r1/r2 特判)。"""
    import inspect
    from sr_od.application.currency_war.decision.decision_v2 import arbiter as _arb
    from sr_od.application.currency_war.decision.decision_v2 import scoring as _sc
    src = inspect.getsource(_arb) + inspect.getsource(_sc)
    for pat in ('round_num <= 1', 'round_num <= 2', 'round_num < 1',
                'round_num < 2', 'round_num == 1', 'round_num == 2',
                'round_num >= 1', 'round_num >= 2'):
        assert pat not in src, f'r1/r2 特判模式出现: {pat}'


def test_w120_p9_hp1_dead_end_marker() -> None:
    """P9:HP=1 死局/早停候选标记(披露非违规)——check 恒空
    (violations=0),数据面 hp1_dead_end_rounds 给出轮号供早停判读。"""

    from sr_od.application.currency_war.sim.checks.ledger import check_hp1_dead_end_candidate, hp1_dead_end_rounds
    rows = [{'round_num': 6, 'hp': 3}, {'round_num': 7, 'hp': 1},
            {'round_num': 8, 'hp': 1}, {'round_num': 9, 'hp': 0}]
    assert check_hp1_dead_end_candidate(rows) == []   # 恒不违规
    assert hp1_dead_end_rounds(rows) == [7, 8, 9]     # 数据面含 hp=0


# --- 附3:G1 人口位判据方向锁 -------------------------------------------


def test_w121_g1_population_slot_trigger_direction() -> None:
    """G1(高严重度):人口位升级触发 = **cap 满 ∧ bench 有等待上场
    的目标/框架件**——§3.3 通道 2 原文「deployed<cap 且 bench 有
    成型可上件」把判据写反(deployed<cap=有余量=该件直接上场即可,
    [32](b) 判定此时再升纯浪费)。

    双态断言(金 45/lv6/bench 引擎件希儿,裸 session=targets 含引擎件):
    - A:deployed=cap(位满)→ 总账放行(① 人口位,花后 41≥form_floor);
    - B:deployed=cap−1(有空位)→ ① 不触发,DP 臂平台未破不过、静态账
      平台延迟损拒 →「息引擎总账拒」。"""
    from sr_od.application.currency_war.decision.decision_v2.candidates import (
        _target_names,
    )
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        engine_char_names,
    )
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        levelup_ev_authorized,
    )
    targets = _target_names(None, None)
    assert '希儿' in engine_char_names() and '希儿' in targets
    dep_full = [BenchChar(slot=i, char_id=f'杂件{i}', faction='公司',
                          star=1) for i in range(6)]
    dep_gap = dep_full[:5]
    for deployed, expect in ((dep_full, True), (dep_gap, False)):
        sess = StrategySession()
        sess.v3_mode = 'economy'
        st = _state(round_num=7, gold=45, level=6, deployed=deployed,
                    bench=[BenchChar(slot=0, char_id='希儿',
                                     faction='公司', star=1)],
                    node_type='battle')
        got = levelup_ev_authorized(
            st, sess, _REG, 45, 4, targets, val=1.0, int_emb=0.0)
        assert got is expect, (len(deployed), expect, got)


# --- 附:旁路护栏 + HOARD 相位域 ---------------------------------------------


def test_bypass_emergency_floor_unchanged() -> None:
    """旁路护栏:应急帧(hp≤25)地板=rebirth_floor、interest_rule
    让位(语义逐位不变——验证门 1 专项)。"""
    sess = StrategySession()
    sess.v3_mode = 'economy'
    st = _state(hp=20, gold=55, node_type='battle')
    assert _active_floor(st, sess, _REG) == _REG.rebirth_floor
    disc = assess_discipline(st, sess, _REG)
    assert disc.coverage == 'emergency'
    # interest_rule 在应急态不辖(交 gold_floor)
    from sr_od.application.currency_war.decision.decision_v2.arbiter import (
        _check_constraint,
    )
    cand = Candidate(action=BuyCard(_card('测试件', cost=4), reason=''),
                     tag='engine_seed', source='shop')
    r = _check_constraint('interest_rule', cand, st, st, sess, _REG)
    assert r is None, '应急态 interest_rule 必须让位'


def test_hoard_phase_domain() -> None:
    """HOARD 相位域(form_ok+金<50):[11] 同档/1费放行;跨档攒息拒
    (拒绝原因可见 HOARD 攒息)。"""
    sess = _sess_locked('DOT队')
    st = _formed_frame('DOT队', gold=45, round_num=7)
    from sr_od.application.currency_war.decision.decision_v2.phase import (
        derive_phase,
    )
    assert derive_phase(st, sess, _REG).value == 'HOARD'
    from sr_od.application.currency_war.decision.decision_v2.arbiter import (
        _check_constraint,
    )
    # 同档买(45→43,档 4 内):放行
    c_same = Candidate(action=BuyCard(_card('同档件', cost=2), reason=''),
                       tag='engine_seed', source='shop')
    assert _check_constraint('gold_floor', c_same, st, st, sess,
                             _REG) is None
    # 跨档买(45→39,破档 4):拒(HOARD 攒息)
    c_cross = Candidate(action=BuyCard(_card('跨档件', cost=6), reason=''),
                        tag='engine_seed', source='shop')
    r = _check_constraint('gold_floor', c_cross, st, st, sess, _REG)
    assert r is not None and 'HOARD 攒息' in r.describe, r


# ==================== w126_switch_dispatch ====================

from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import IntentionState
from sr_od.application.currency_war.data.cw_shop_odds import (
    expected_refreshes_for_card,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    LevelUp,
    RefreshShop,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.arbiter import arbitrate
from sr_od.application.currency_war.decision.decision_v2.candidates import (
    Candidate,
    _target_names,
    generate_candidates,
)
from sr_od.application.currency_war.decision.decision_v2.ev import (
    levelup_ev_authorized,
    levelup_refresh_saving,
)
from sr_od.application.currency_war.decision.decision_v2.filters import (
    filter_candidates,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision.decision_v2.scoring import (
    score_candidate,
    vd_refresh_score,
)

_w126_switch_dispatch_REG = DEFAULT_REGISTRY


def _locked_sess(comp: str) -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState(phase='locked', locked_comp=comp)
    s.target_comp = get_comp(comp)
    s.v3_mode = 'economy'
    return s


def _w126_switch_dispatch_state(level: int, copies: list[str], gold: int, r: int, *,
           comp: str = 'DOT队', deployed: int = 4,
           node: str = 'battle') -> tuple[GameState, StrategySession]:
    s = _locked_sess(comp)
    st = GameState(
        plane=1, round_num=r, gold=gold, level=level, hp=60,
        deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                            faction='公司', star=1)
                  for i in range(deployed)],
        bench=[BenchChar(slot=i, char_id=n, faction='公司', star=1)
               for i, n in enumerate(copies)],
        shop=[], node_type=node)
    return st, s


# --- ① V_D 批口径正分帧(W119 锁④ 升级版)------------------------------------


def test_vd_batch_caliber_positive_frame() -> None:
    """①金 100/r8/c5 概率窗(Archer,命运圣杯红A L10 roll)核心未齐
    (j=2,k=1):refresh 候选正分。断言三件:
    - 评分>0(V_D 生效,非恒 0/负);
    - 分值=vd_refresh_score(批口径金账,含 E×刷价成本项——
      val < 收益侧毛值,证明批成本在分内);
    - 离窗对照(L8:概率窗未到)为负(批成本放大,不硬 D)。"""
    st, s = _w126_switch_dispatch_state(10, ['Archer', 'Archer'], 100, 8,
                   comp='命运圣杯红A')
    vd = vd_refresh_score(st, s, _w126_switch_dispatch_REG)
    assert vd is not None and vd > 0, vd
    cand = [c for c in generate_candidates(st, s, _w126_switch_dispatch_REG)
            if c.tag == 'refresh'][0]
    val, _bd = score_candidate(cand, st, s, _w126_switch_dispatch_REG)
    assert val == vd, (val, vd)
    # 批成本项在分内:收益毛值(R 项+战斗项,ADR-0425 标定口径)> val
    # (净)=毛值−E×刷价
    from sr_od.application.currency_war.decision.decision_v2.ev import (
        cross_plane_remaining_nodes,
    )
    from sr_od.application.currency_war.decision.decision_v2.scoring import (
        p1_battle_loss_est,
    )
    win_term = (( _w126_switch_dispatch_REG.h3_win_rate[2] - _w126_switch_dispatch_REG.h3_win_rate[1])
                * p1_battle_loss_est(st, _w126_switch_dispatch_REG, rung=2)
                * _w126_switch_dispatch_REG.hp_to_gold * _w126_switch_dispatch_REG.battles_left_est)
    gross = 1.6 * cross_plane_remaining_nodes(st) + win_term
    assert val < gross, '批口径成本项(E×刷价)必须在分内(禁单次边际)'
    # 离窗对照:L8(c5 概率 p=0.03)→ 批成本爆炸 → 负分
    st8, s8 = _w126_switch_dispatch_state(8, ['Archer', 'Archer'], 100, 8,
                     comp='命运圣杯红A')
    vd8 = vd_refresh_score(st8, s8, _w126_switch_dispatch_REG)
    assert vd8 is not None and vd8 < 0, vd8


def test_vd_requires_opened_core() -> None:
    """V_D 目标语境=核心已开张(≥1 张):0 张时 D 关闭(攒自然刷新+
    买入压库;[1] r1/r2 不 D 的保守侧落法,ADR-0349 记档)。
    L4=DOT队 plan roll 窗内(排除窗二分干扰)。"""
    st, s = _w126_switch_dispatch_state(4, [], 60, 4)
    assert vd_refresh_score(st, s, _w126_switch_dispatch_REG) is None
    st2, s2 = _w126_switch_dispatch_state(4, ['卡芙卡'], 60, 4)
    assert vd_refresh_score(st2, s2, _w126_switch_dispatch_REG) is not None


# --- ⑦ V_level 省刷金项:k 放大 + 峰值以上为 0(P5 检验点②)-------------------


def test_levelup_saving_k_amplification() -> None:
    """⑦省刷金随 k(剩余张数)放大:c2@L4,k=2(j=1)的省刷金 >
    k=1(j=2)——升级收益侧必须过 k 放大总账(P5 边界 a 的判据本体);
    峰值以上(L6→L7,c2 峰值在 L6)ΔE≤0 → saving=0(P5 边界 b:
    峰值级/峰值以上停留最优,不设独立峰值惩罚)。"""
    st_k2, s_k2 = _w126_switch_dispatch_state(4, ['卡芙卡'], 50, 4)      # j=1 → k=2
    st_k1, s_k1 = _w126_switch_dispatch_state(4, ['卡芙卡', '卡芙卡'], 50, 4)   # j=2 → k=1
    sv2 = levelup_refresh_saving(st_k2, s_k2, _w126_switch_dispatch_REG)
    sv1 = levelup_refresh_saving(st_k1, s_k1, _w126_switch_dispatch_REG)
    assert sv2 > sv1 > 0, (sv2, sv1)
    # 表值对拍:sv1 = 刷价×(E(L4,j2)−E(L5,j2))
    e = (expected_refreshes_for_card(4, 2, 2, owned=2)
         - expected_refreshes_for_card(5, 2, 2, owned=2))
    assert abs(sv1 - e * 2) < 1e-6
    # 峰值以上:L6(c2 峰值)→L7 概率降 → 0
    st6, s6 = _w126_switch_dispatch_state(6, ['卡芙卡', '卡芙卡'], 50, 6)
    assert levelup_refresh_saving(st6, s6, _w126_switch_dispatch_REG) == 0.0


# --- ⑧ 概率窗二分([3]/通道表冲突消解)----------------------------------------


def test_roll_window_dichotomy() -> None:
    """⑧升 vs D 的概率窗二分(判据=level_plan roll 窗单一源):
    DOT队 L5(plan 说 level_up)→ vd 返回 None(D 让位给升,
    「没到就少刷新、多买经验」);L8(plan 说 roll 卡芙卡 2★)
    → V_D 生效且该帧正分。"""
    st5, s5 = _w126_switch_dispatch_state(5, ['卡芙卡', '卡芙卡'], 60, 5)
    assert vd_refresh_score(st5, s5, _w126_switch_dispatch_REG) is None, '窗外 D 必须让位'
    st8, s8 = _w126_switch_dispatch_state(8, ['卡芙卡', '卡芙卡'], 60, 8)
    vd8 = vd_refresh_score(st8, s8, _w126_switch_dispatch_REG)
    assert vd8 is not None and vd8 > 0, vd8


# --- ③ c=2@L4 型格子(k=1)升级判负(P5 边界 a)-------------------------------


def test_c2_l4_k1_levelup_negative() -> None:
    """③P5 边界 a:c2@L4 找 1 张(k=1),金 51 的升级(单击 4)
    被平台总账拒——省刷金(k 放大后 6.25 金)仍远小于平台延迟损
    (花后 47<50:满息缺口 1×R=24)。「概率提高」本身不构成升级理由。"""
    st, s = _w126_switch_dispatch_state(4, ['卡芙卡', '卡芙卡'], 51, 4)
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, s, _w126_switch_dispatch_REG)
    row = next(r for r in res.log if r['tag'] == 'levelup')
    assert row['accepted'] is False, row
    assert '息引擎总账拒' in (row['reject'] or ''), row
    assert not any(isinstance(a, LevelUp) for a in res.actions)


# --- ④ 34 帧误拒形态复现 → 修复后放行 ----------------------------------------


def test_pop_slot_affordable_below_form_floor_allowed() -> None:
    """④W123 34 帧误拒形态:cap 满+bench 目标件+整组升级花费花后
    <form_floor(金 23,5 击×4=20,花后 3)——W126 修复前被 arm① 的
    form_floor 保险丝拦;修复后放行(人口位价值=当轮战力兑现,
    保险丝=可负担性)。对照:金不足(15<20)仍拒(可负担性入口门)。"""
    st, s = _w126_switch_dispatch_state(5, ['希儿'], 23, 5, deployed=5)
    assert st.deployed_count() >= st.max_units(), '前置:cap 满(ADR-0392 占用数)'
    targets = _target_names(st, s)
    assert '希儿' in targets, '前置:bench 目标件'
    assert levelup_ev_authorized(st, s, _w126_switch_dispatch_REG, 23, 20, targets,
                                 val=1.0, int_emb=0.0) is True
    # 金不足对照:整组总价超本金 → 拒(可负担性入口门,W126)
    assert levelup_ev_authorized(st, s, _w126_switch_dispatch_REG, 15, 20, targets,
                                 val=1.0, int_emb=0.0) is False
    # 无人口位对照:deployed<cap 同帧 → arm① 不辖
    st2, s2 = _w126_switch_dispatch_state(5, ['希儿'], 23, 5, deployed=4)
    assert st2.deployed_count() < st2.max_units()   # ADR-0392 占用数
    assert levelup_ev_authorized(st2, s2, _w126_switch_dispatch_REG, 23, 20,
                                 _target_names(st2, s2),
                                 val=1.0, int_emb=0.0) is False
    # 单击路径端到端:gold_floor 让位后由 ev 单一裁决(同帧单击 4 也放行)
    cand = Candidate(action=LevelUp(cost=4), tag='levelup', source='xp')
    res = arbitrate([(cand, 1.0, {})], st, s, _w126_switch_dispatch_REG)
    assert any(isinstance(a, LevelUp) for a in res.actions), \
        'cap 满+bench 目标件的可负担单击升级应放行(34 帧修复)'


# --- ⑤ 追赶态退场静态断言 -----------------------------------------------------


def test_catchup_retired_static() -> None:
    """⑤追赶态(F6)退场:registry 无追赶字段、过滤链无 catchup 层、
    filters/discipline 无 is_catchup、覆盖序不产 'catchup'
    (人口落后由通道 2/4+EV 涌现承接,ADR-0349)。"""
    for field in ('catchup_tags', 'catchup_forbidden_tags',
                  'catchup_min_level', 'pop_baseline'):
        assert not hasattr(_w126_switch_dispatch_REG, field), field
    assert 'catchup' not in _w126_switch_dispatch_REG.filter_chain_order
    assert 'catchup' not in _w126_switch_dispatch_REG.audit_round_state_dims
    from sr_od.application.currency_war.decision.decision_v2 import (
        filters as _f,
        discipline as _d,
        arbiter as _a,
    )
    for mod in (_f, _d, _a):
        assert not hasattr(mod, 'is_catchup'), mod.__name__
    # 行为面:旧追赶触发帧(等级≥6+人口<基线-1,r232 形态)不再产
    # catchup 覆盖——回落 mode(经济),refresh 候选不被追赶禁
    s = _locked_sess('DOT队')
    s.v3_mode = 'economy'
    st = GameState(plane=2, round_num=3, gold=40, level=6, hp=70,
                   deployed=[BenchChar(slot=9 + i, char_id=f'杂件{i}',
                                       faction='公司', star=1)
                             for i in range(2)],
                   bench=[], shop=[], node_type='battle')
    disc = _d.assess_discipline(st, s, _w126_switch_dispatch_REG)
    assert disc.coverage == 'mode', disc
    cands = generate_candidates(st, s, _w126_switch_dispatch_REG)
    kept, _flog = filter_candidates(cands, st, s, _w126_switch_dispatch_REG)
    assert any(c.tag == 'refresh' for c in kept), \
        '旧追赶帧 refresh 不再被禁(追赶态退场)'


# --- ⑥ war 模式帧 refresh 候选在场 --------------------------------------------


def test_war_mode_refresh_candidate_present() -> None:
    """⑥war 滤 refresh 废除:war 模式帧(报警升级/boss_breaker 覆盖)
    refresh 候选层2 在场(war_tags 含 refresh)——D 是一等花钱通道,
    授权由 V_D+interest_rule 辖,不再按模式整体消失(run10 病症的
    通道层根治)。"""
    assert 'refresh' in _w126_switch_dispatch_REG.war_tags
    s = _locked_sess('DOT队')
    s.v3_mode = 'war'
    st, _s = _w126_switch_dispatch_state(8, ['卡芙卡', '卡芙卡'], 60, 8)
    cands = generate_candidates(st, s, _w126_switch_dispatch_REG)
    kept, flog = filter_candidates(cands, st, s, _w126_switch_dispatch_REG)
    assert any(c.tag == 'refresh' for c in kept), \
        'war 模式帧 refresh 候选必须在场'
    # 评分不受 war 模式影响(V_D 同账;授权由层4 辖)
    rc = next(c for c in cands if c.tag == 'refresh')
    val, _bd = score_candidate(rc, st, s, _w126_switch_dispatch_REG)
    assert val > 0, f'概率窗内 V_D 应正分(实际 {val})'
    # 端到端:war 帧 refresh 被采纳
    res = arbitrate([(rc, val, _bd)], st, s, _w126_switch_dispatch_REG)
    assert any(isinstance(a, RefreshShop) for a in res.actions)


# --- ⑩ 伴随修复:CompTransaction shop fill 索引漂移(B 批 sim 涌现)--------


def test_comp_tx_shop_fill_index_drift_fixed() -> None:
    """⑩W126 sim ledger_consistency 2→12/100 涌现的根:CompTransaction
    多笔 shop fill 的 apply 循环内 ``s.shop.remove`` 左移列表,后续
    f.idx 失效——买错卡(错档部署)+记错账(实扣 6 记 4)。修复=按
    校验期解析的卡对象(``plan['shop_fill_cards']``)按身份消费。
    锁:两笔 shop fill([1]=2费,[2]=2费)后金恰扣 4、上场的是提案的
    两张(非移位后的遐蝶 4费)、店内只剩未提案的。"""
    from sr_od.application.currency_war.kernel.cw_state import (
        CompTransaction,
        FillSpec,
        ShopCard,
        simulate,
    )
    st = GameState(plane=1, round_num=5, gold=30, level=4, hp=60,
                   shop=[ShopCard(name='卡零', faction='公司', cost=1, x=0),
                         ShopCard(name='砂金', faction='公司', cost=2, x=1),
                         ShopCard(name='佩拉', faction='贝洛伯格', cost=2, x=2),
                         ShopCard(name='遐蝶', faction='夜之半神', cost=4, x=3)],
                   bench=[], deployed=[], node_type='battle')
    tx = CompTransaction(deploy=[], undeploy=[], sell=[],
                         fill=[FillSpec(source='shop', idx=1, row='back'),
                               FillSpec(source='shop', idx=2, row='back')],
                         reason='test:drift')
    out = simulate(st, tx)
    log = out.action_log[-1]
    assert log['result'] == 'applied', log
    assert log['fill_cost'] == 4, log
    assert st.gold - out.gold == 4, (st.gold, out.gold)
    dep_names = {d.char_id for d in out.deployed if d is not None}
    assert dep_names == {'砂金', '佩拉'}, dep_names   # ADR-0392 滤 None
    shop_names = [c.name for c in out.shop]
    assert shop_names == ['卡零', '遐蝶'], shop_names


# ==================== intention ====================

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    CORE_MISS_N,
    CROSS_LINE_SKELETON,
    FALLBACK_COMP_NAME,
    IntentionState,
    detect_signals,
    encounter_window_rounds,
    hoard_target_set,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState, ShopCard


def _intention_state(**kw) -> GameState:
    s = GameState()
    s.plane = kw.get('plane', 1)
    s.round_num = kw.get('round_num', 1)
    s.level = kw.get('level', 5)
    s.active_env = kw.get('active_env', '')
    s.active_strategies = list(kw.get('strategies', []))
    for name in kw.get('bench', []):
        ch = CHARACTERS.get(name)
        s.bench.append(BenchChar(slot=len(s.bench), char_id=name,
                                 faction=ch.factions[0] if ch and ch.factions else '?',
                                 star=kw.get('bench_star', 1)))
    for name in kw.get('shop', []):
        ch = CHARACTERS.get(name)
        s.shop.append(ShopCard(x=len(s.shop), name=name,
                               faction=ch.factions[0] if ch and ch.factions else '?',
                               cost=ch.cost if ch else 3))
    for fac, n in kw.get('board', {}).items():
        s.board[fac] = n
    return s


def _layers(sigs: list) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for s in sigs:
        out.setdefault(s.layer, set()).add(s.comp_name)
    return out


# ===== 信号五层触发例 =====

def test_layer1_env_signal() -> None:
    """①策略驱动-环境:列车同行概念股 → 列车同行;且锁线。"""
    st = _intention_state(active_env='列车同行概念股')
    sigs = detect_signals(st)
    l1 = [s for s in sigs if s.layer == 1]
    assert any(s.comp_name == '列车同行' and s.kind == 'env' for s in l1)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    assert ist.lock_layer == 1 and not ist.forced


def test_layer1_strategy_signal() -> None:
    """①策略驱动-投资策略:黑塔纪元(augment)→ 大黑塔银河学者。"""
    st = _intention_state(strategies=['黑塔纪元'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '大黑塔银河学者' and s.kind == 'strategy'
               for s in sigs if s.layer == 1)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '大黑塔银河学者'


def test_layer2_family_bond_signal() -> None:
    """②类专属羁绊(ADR-0338 资格门):羁绊副产品计数不是直通资格——
    持续伤害×2 无资格不发②;持有资格(env 特邀专家:桑博 → 专家桑博DOT)
    才发;量子×2 恒不触发(希儿量子无②——量子/贝是放大器)。"""
    st = _intention_state(board={'持续伤害': 2})
    lay = _layers(detect_signals(st))
    assert lay.get(2, set()) == set(), '无资格时②羁绊信号不得发射(锁直通=旧病)'
    st2 = _intention_state(board={'持续伤害': 2}, active_env='特邀专家:桑博')
    lay2 = _layers(detect_signals(st2))
    assert '专家桑博DOT' in lay2.get(2, set())
    st3 = _intention_state(board={'量子同频': 2})
    lay3 = _layers(detect_signals(st3))
    assert '希儿量子' not in lay3.get(2, set())


# ===== ADR-0338:直通终局线资格门(W85 五局同型根因修复)=====


def test_bond_lock_requires_qualification() -> None:
    """银河学者×2(经济凑数位)无资格 → 不锁大黑塔银河学者;P1 方向落
    配方过渡方向(p1_transition,ADR-0357——绯英兜底不辖 P1);
    持黑塔纪元(资格策略)→ 放行锁直通。"""
    st = _intention_state(board={'银河学者': 2})          # 学者2 = 买 DOT 的副产品
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert hoard_target_set(st, ist).mode == 'p1_transition'
    st_q = _intention_state(board={'银河学者': 2}, strategies=['黑塔纪元'])
    ist_q = update_intention(st_q, IntentionState())
    assert ist_q.phase == 'locked' and ist_q.locked_comp == '大黑塔银河学者'
    # env 侧资格同放行(银河学者概念股)
    st_e = _intention_state(board={'银河学者': 2}, active_env='银河学者概念股')
    ist_e = update_intention(st_e, IntentionState())
    assert ist_e.locked_comp == '大黑塔银河学者'


def test_bond_lock_wan_di_rejected_core_card_still_legal() -> None:
    """夜之半神×2(燃血副产品)不锁万敌单C(003757 r6 病);
    贯穿件万敌到手:③锁线在 P2/P3 照旧([23] 合法路径),但 P1 被
    ADR-0341 资格门拦下(终局专属线 P1 锁向=板面饥饿,W97:hp 差 9-11)。"""
    st = _intention_state(board={'夜之半神': 2})
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    # P1:贯穿件在手但无①类资格 → ③证据被门拦下,意向落配方过渡方向
    ist_p1 = update_intention(_intention_state(bench=['万敌']), IntentionState())
    assert ist_p1.phase == 'unlocked' and ist_p1.locked_comp == ''
    assert hoard_target_set(_intention_state(), ist_p1).mode == 'p1_transition'
    # P2:门不辖([21] 上场窗口/换血点都在 P1 后),③照旧
    ist2 = update_intention(_intention_state(plane=2, bench=['万敌']), IntentionState())
    assert ist2.phase == 'locked' and ist2.locked_comp == '万敌单C'
    assert ist2.lock_layer == 3


def test_bond_lock_train_requires_strategy() -> None:
    """列车同行×2 不锁列车同行 comp(终局形态需列车4+姬子,024503 r7 病);
    持「本姑娘就是罗刹」(资格策略)→ 放行。"""
    st = _intention_state(board={'列车同行': 2})
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    st_q = _intention_state(board={'列车同行': 2}, strategies=['本姑娘就是罗刹'])
    ist_q = update_intention(st_q, IntentionState())
    assert ist_q.locked_comp == '列车同行'


def test_layer3_core_card_signal() -> None:
    """③核心卡:具名意向核心在店 → 对应线;P2 锁线(回归)。

    P1(W145/ADR-0357):③不再锁终局 comp(锁定产物=过渡配方体系对);
    希儿仅在店可见≠到手([23] 锁定由贯穿件=到手)→ 不构成配方证据,
    p1_pair 空、方向落四体系全集(p1_transition)。"""
    st = _intention_state(plane=2, shop=['希儿'])
    sigs = detect_signals(st)
    assert any(s.comp_name == '希儿量子' and s.kind == 'core_card'
               for s in sigs if s.layer == 3)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.locked_comp == '希儿量子'
    # P1:③证据不再锁 comp
    st1 = _intention_state(shop=['希儿'])
    ist1 = update_intention(st1, IntentionState())
    assert ist1.phase == 'unlocked' and ist1.locked_comp == ''
    assert ist1.p1_pair == ()
    assert hoard_target_set(st1, ist1).mode == 'p1_transition'


def test_layer4_resource_signal() -> None:
    """④资源:升费链角色(银狼LV.999)到手 → 狼尊欢愉资源信号;
    P1 被 ADR-0341 资格门拦下(④与③同为「卡/资源到手」证据类)。"""
    st = _intention_state(bench=['银狼LV.999'])
    sigs = detect_signals(st)
    assert not any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
                   for s in sigs if s.layer == 4), 'P1 终局专属线④证据应被门拦下'
    st2 = _intention_state(plane=2, bench=['银狼LV.999'])
    sigs2 = detect_signals(st2)
    assert any(s.comp_name == '狼尊欢愉' and s.kind == 'resource'
               for s in sigs2 if s.layer == 4)


def test_layer5_fallback_no_signal() -> None:
    """⑤无信号兜底:无任何信号 → 不锁线;P2+ 囤货方向落绯英档
    (P1 配方方向见 W145 配方锁测试;绯英兜底不辖 P1,ADR-0357)。"""
    st = _intention_state(plane=2)
    assert detect_signals(st) == []
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'fallback'
    assert '绯英' in ht.char_targets
    assert get_comp(FALLBACK_COMP_NAME) is not None


def test_layer_priority_order() -> None:
    """①>②>③>④:同轮多层并存取最高层(①)。"""
    st = _intention_state(active_env='列车同行概念股', board={'持续伤害': 3},
                shop=['希儿'], bench=['银狼LV.999'])
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '列车同行' and ist.lock_layer == 1


# ===== 撤销两出口 =====

#: 证据组 B 夹具:异线「万敌单C」(v2 家族)终局件 5 张在手(核心万敌
#: 可达;厚度=5×1★ + 骨架重叠×0.5=6.5 ≥ A_min=5,W423 测量值)。
EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _default_n_req(core: str, level: int = 5) -> int:
    from sr_od.application.currency_war.kernel.cw_intention import (
        core_miss_n_required,
    )
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    return core_miss_n_required(
        core, level, DEFAULT_REGISTRY.revoke_miss_tolerance_eps)


def test_revoke_exit1_requires_n_req_and_alt_asset_evidence() -> None:
    """撤销出口①三条件合取(设计=`.debug/temp/currency_war/
    w396_r2r3_design/DESIGN.md` R3.1,治 W386 BP1 门放行噪声换线):
    - 仅 miss 达拍死计数 CORE_MISS_N 而无异线资产证据 → 不开窗,
      计数继续累计(「核心短时缺货」的正常噪声不再进撤销);
    - miss 达 max(CORE_MISS_N, N_req) 且存在异线(核心可达+厚度
      ≥ A_min)→ 开窗降弱意向,事件行与证据字段携带 n_req/q/alt/thk
      (实机判读锚:无证据字段的开窗=守卫失效)。"""
    st = _intention_state(plane=2, shop=['希儿'])   # 锁希儿量子(3费,lv5 开窗)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    gone = _intention_state(plane=2)                # 窗口开、核心缺、无异线资产
    for _ in range(CORE_MISS_N + 5):
        update_intention(gone, ist)
        assert ist.phase == 'locked', '无证据组 B 时拍死计数不得开窗'
    assert ist.tracks['希儿量子'].miss_count == CORE_MISS_N + 5
    # 补证据组 B → 推进到 N_req 轮开窗
    gone_ev = _intention_state(plane=2, bench=EVIDENCE_BENCH)
    total = max(CORE_MISS_N, _default_n_req('希儿'))
    for _ in range(total - (CORE_MISS_N + 5) - 1):
        update_intention(gone_ev, ist)
        assert ist.phase == 'locked'
    update_intention(gone_ev, ist)   # 第 N_req 轮:三条件齐 → 开窗
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子'
    assert ist.last_event.startswith('revoke:miss')
    assert 'alt=万敌单C' in ist.last_event
    ev = ist.revoke_evidence
    assert ev['alt_comp'] == '万敌单C'
    assert ev['asset_thickness'] >= ev['a_min'] >= 5.0
    assert ev['n_req'] == total and ev['q'] > 0 and ev['miss_count'] == total
    ht = hoard_target_set(gone_ev, ist)
    assert ht.mode == 'weak'
    assert set(ht.char_targets) == set(CROSS_LINE_SKELETON)


def test_revoke_exit2_higher_signal_with_reachability() -> None:
    """撤销出口②:更高层信号 + 可达性对照 → 撤;下轮新信号锁新线;不可达则不撤。
    (锁线场景设 P2:W145 起 P1 ③不锁 comp——希儿量子 P1 落配方方向。)"""
    st = _intention_state(plane=2, shop=['希儿'])  # ③锁希儿量子(layer3)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    # 可达:plane2 剩余节点 > 姬子再遇窗 → 撤,降弱意向
    st2 = _intention_state(plane=2, active_env='列车同行概念股', shop=['希儿'],
                 round_num=2)
    update_intention(st2, ist)
    assert ist.phase == 'weak' and ist.weak_comp == '希儿量子'
    assert 'higher' in ist.last_event
    update_intention(st2, ist)             # 直至新信号:env 再锁列车线
    assert ist.phase == 'locked' and ist.locked_comp == '列车同行'
    # 不可达:P3 末轮只剩少量节点,新信号核心再遇窗远超 → 层级高≠必换,不撤
    st3 = _intention_state(shop=['希儿'], active_env='列车同行概念股',
                 plane=3, round_num=9)
    ist2 = update_intention(_intention_state(plane=3, shop=['希儿']), IntentionState())
    assert ist2.locked_comp == '希儿量子'
    update_intention(st3, ist2)
    assert ist2.phase == 'locked' and ist2.locked_comp == '希儿量子'


def test_revoke_exit1_resets_on_core_visible() -> None:
    """核心再现 → miss 计数清零(不冤枉撤销)。(锁线场景设 P2,W145。)"""
    st = _intention_state(plane=2, shop=['希儿'])
    ist = update_intention(st, IntentionState())
    gone = _intention_state(plane=2)
    for _ in range(3):
        update_intention(gone, ist)
    assert ist.tracks['希儿量子'].miss_count == 3
    update_intention(_intention_state(plane=2, shop=['希儿']), ist)
    assert ist.tracks['希儿量子'].miss_count == 0
    assert ist.phase == 'locked'


# ===== 窗口冻结语义 =====

def test_freeze_counter_and_eviction() -> None:
    """窗口未开不计 miss;冻结超位面剩余节点 → 移出候选集、回⑤、该轮不触发③。
    (锁线场景设 P2:W145 起 P1 ③不锁 comp;冻结语义本身位面无关。)"""
    st = _intention_state(plane=2, shop=['希儿'])  # lv5 锁希儿量子(3费)
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '希儿量子'
    frozen = _intention_state(plane=2, level=3, shop=['希儿'])   # lv3 不出 3费 → 窗口关
    # 轮 2-5:frozen 1..4,均未超位面剩余(轮5 剩 5)→ 仍锁;miss 恒 0(未开窗不计)
    for r in range(2, 6):
        frozen.round_num = r
        update_intention(frozen, ist)
        assert ist.phase == 'locked'
        assert ist.tracks['希儿量子'].miss_count == 0
    # 轮 6:frozen=5 > 位面剩余 4 → 逐出;店里有希儿但③被排除 → 回⑤兜底
    frozen.round_num = 6
    update_intention(frozen, ist)
    assert ist.phase == 'unlocked' and '希儿量子' in ist.evicted
    assert ist.last_event.startswith('evict:frozen')
    assert hoard_target_set(frozen, ist).mode == 'fallback'
    # 之后希儿再出现,③信号也被 evicted 过滤(等同信号未发生)
    update_intention(_intention_state(plane=2, shop=['希儿']), ist)
    assert ist.phase == 'unlocked' and ist.locked_comp == ''


# ===== 强制锁线与降格终局 =====

def test_forced_lock_p3_thickest() -> None:
    """P3 入口无意向:可达候选中资产最厚方向强制锁线(非 carry 件堆出的厚度)。"""
    st = _intention_state(plane=3, level=4, bench=['千冶·刃', '缇宝'])   # 万敌线终局件×2,无③信号
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked' and ist.forced
    assert ist.locked_comp == '万敌单C'   # 厚度 2+0.5 > DOT 系 1.5
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'forced' and '万敌' in ht.char_targets


def test_forced_lock_demote_endgame() -> None:
    """全候选不可达(P3 末轮+低等级+无资产)→ 降格终局标记;absorbing,新信号不解锁。"""
    st = _intention_state(plane=3, round_num=9, level=3)
    ist = update_intention(st, IntentionState())
    assert ist.demoted_endgame and ist.last_event == 'demote:endgame'
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'demoted_endgame'
    assert set(ht.char_targets) == set(CROSS_LINE_SKELETON)
    # absorbing:此后任何信号不再改意向(承认下限,「赢不了就少输」)
    update_intention(_intention_state(active_env='列车同行概念股'), ist)
    assert ist.demoted_endgame and ist.locked_comp == ''


# ===== 锁后效果(只改囤货方向) =====

def test_lock_effect_hoard_target_set() -> None:
    """锁定 → 囤货集合切到意向线(角色件含核心/羁绊成员;装备件=到人配方−禁忌)。
    (万敌单C P1 ③被 ADR-0341 门拦,锁线场景设 P2。)"""
    st = _intention_state(plane=2, bench=['万敌'])
    ist = update_intention(st, IntentionState())
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'locked'
    for c in get_comp('万敌单C').core_chars:
        assert c in ht.char_targets
    assert '高周波电锯' in ht.equip_targets
    assert '以牙还牙甲' not in ht.equip_targets   # equip_taboos(盾装连带禁)
    # 希儿线装备配方也在锁定时切过去(锁线场景设 P2:W145 起 P1 ③不锁)
    ist2 = update_intention(_intention_state(plane=2, shop=['希儿']), IntentionState())
    ht2 = hoard_target_set(_intention_state(plane=2), ist2)
    assert '火力风暴潮·特权' in ht2.equip_targets


def test_line_hoard_flows_members_in_target_set() -> None:
    """W65/ADR-0323:锁定万敌线 → 燃血(flows 流派)成员 刃/镜流/布洛妮娅
    进囤货目标集——旧版 _line_hoard 只查 c.factions,flows 成员被排除
    (W64 Ring1:燃血 8 成员 3/8 采购面缺失)。泛化修正:档位键与
    factions ∪ flows 全集交集,非万敌特判。(锁线场景设 P2:万敌单C
    的 P1 ③证据被 ADR-0341 资格门拦。)"""
    st = _intention_state(plane=2, bench=['万敌'])
    ist = update_intention(st, IntentionState())
    assert ist.locked_comp == '万敌单C'
    ht = hoard_target_set(st, ist)
    for name in ('刃', '镜流', '布洛妮娅'):
        assert name in ht.char_targets, \
            f'燃血(flows)成员 {name} 应在锁定线目标集内'


def test_encounter_window_monotonic() -> None:
    """再遇窗近似:窗口未开=inf;低费窗更近(静态近似 sanity)。"""
    assert encounter_window_rounds('希儿', 3) == float('inf')
    assert encounter_window_rounds('万敌', 5) < encounter_window_rounds('希儿', 5)


def test_cross_line_skeleton_source() -> None:
    """跨线骨架名单 = W16 八张 + 双身份两张(点0 弱意向囤货集单一源)。"""
    assert set(CROSS_LINE_SKELETON) == {
        '瓦尔特', '千冶·刃', '符玄', '星期日', '开拓者·记忆',
        '花火', '缇宝', '刻律德菈', '三月七', '藿藿',
    }


# ===== P1 过渡配方锁(W145/ADR-0357)=====


def test_p1_pair_lock_from_dot_assets() -> None:
    """P1 锁定产物=体系对:DOT 2 件在手(DOT 支持度 1.0)→ 锁
    (持续伤害, 列车同行)(第二体系按激活占比序);囤货=对成员集,
    mode=p1_pair;不锁任何终局 comp。"""
    st = _intention_state(bench=['桑博', '卡芙卡'])
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'unlocked' and ist.locked_comp == ''
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p1_pair'
    assert '桑博' in ht.char_targets          # DOT 成员
    assert '三月七' in ht.char_targets        # 列车成员(第二体系=目标件)
    assert not ht.equip_targets               # 过渡装备随意([20])


def test_p1_pair_shifts_with_assets() -> None:
    """体系对随资产重派生([20] 变体按来牌选):仙舟三人组到手(1.0)
    → 对切 (列车同行, 仙舟)——饮月双阵营(仙舟+列车)各系并计,
    列车以平手占比序挤掉 DOT(对内序=激活占比序)。"""
    ist = update_intention(_intention_state(bench=['桑博']), IntentionState())
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ist = update_intention(
        _intention_state(bench=['桑博', '藿藿', '丹恒·饮月', '爻光']), ist)
    assert ist.p1_pair == ('列车同行', '仙舟')
    assert ist.last_event.startswith('p1_pair:')


def test_p1_pair_seele_owned_not_shop() -> None:
    """希儿系=到手才计支持度([23] 锁定由贯穿件=到手):店里可见不锁希儿系,
    bench 到手 → 希儿系进对。"""
    ist = update_intention(_intention_state(shop=['希儿']), IntentionState())
    assert '希儿系' not in ist.p1_pair
    ist2 = update_intention(_intention_state(bench=['希儿']), IntentionState())
    assert '希儿系' in ist2.p1_pair
    ht = hoard_target_set(_intention_state(bench=['希儿']), ist2)
    assert '希儿' in ht.char_targets and '缇宝' in ht.char_targets


def test_p1_pair_boundary_empty_fallback() -> None:
    """边界:无任何过渡体系件(空窗期,[31]①)→ 不锁对;方向=四体系
    引擎件全集(p1_transition),不落绯英兜底(零引擎覆盖,W143)。"""
    st = _intention_state(bench=['万敌'])   # 终局专属件,不构成体系支持
    ist = update_intention(st, IntentionState())
    assert ist.p1_pair == ()
    ht = hoard_target_set(st, ist)
    assert ht.mode == 'p1_transition'
    for name in ('三月七', '桑博', '丹恒·饮月'):   # 三体系代表件
        assert name in ht.char_targets


def test_p1_pair_exits_at_p2() -> None:
    """进 P2:配方锁退场(p1_pair 清空),comp 锁定通道照旧
    (P2 锁定产物=终局 comp,回归)。"""
    ist = update_intention(_intention_state(bench=['桑博']), IntentionState())
    assert ist.p1_pair == ('列车同行', '持续伤害')
    ist = update_intention(_intention_state(plane=2), ist)
    assert ist.p1_pair == () and ist.last_event == 'p1_pair:exit_p1'
    assert hoard_target_set(_intention_state(plane=2), ist).mode == 'fallback'


# (批 3 F5 清偿:原 test_p1_recipe_lock_off_restores_baseline 随模块级 flag
# P1_RECIPE_LOCK 退役删除——flag=False 基线臂改由 git 冻结快照构造
# (蓝图 §6;开臂前置因冻结令消失=第 4 态清理)。)
    """锁定目标数据形态显式可读(ADR-0357 约束基准契约):p1_pair 落
    ``serialize_intention`` 输出(decisions 行可读,后续「通道约束批」
    按此字段约束 opportunistic/bond_fallback——不隐式)。"""
    from sr_od.application.currency_war.kernel.cw_intention import serialize_intention
    ist = update_intention(_intention_state(bench=['桑博']), IntentionState())
    d = serialize_intention(ist)
    assert d is not None and list(d['p1_pair']) == ['列车同行', '持续伤害']
    d2 = serialize_intention(update_intention(_intention_state(), IntentionState()))
    assert d2 is not None and list(d2['p1_pair']) == []
