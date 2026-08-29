"""换线存活门 P2/P3 修复单帧锁(W665 DESIGN **v3** 落码批;v3 终版含
W683 六必改)。设计=唯一规格:`.debug/temp/currency_war/w665_p2p3_linegate/
DESIGN.md` v3;锁面清单=该文 §6。本文件承载:

- §6-6 轨迹锁(FM-9 原场景,v3 R-A 门感知滞回闩):t0 降级(暂存原锁
  层)→ t1 闩置位+一次性回锁(锁层恢复)→ t2 起 locked 吸收、零转移
  ——同时钉死「永久 weak」与「周期-3 环」两个失败形态;
- §6-6 对照帧:原线 E=inf → 闩置位但停 weak(合法终态);E=inf 候选
  线信号帧 → 不落锁(v3 R-E,'alt_inf');
- §6-7 FM-11 撤销面锁:回锁恢复原锁层;位面切换清闩后②层优线可经出
  口②撤销;prev_lock_layer 位面切换清零断言;
- §6-3 FM-10 瞬态对拍锁(门稳定性主承载面,v3 R-H 升格);
- §6-4 一致性检查器锁(两违规构造反例;禁复算判据式);
- §5.1-G4 三判据锚锁(v3 R-B:relock ≤1/局 / 局末 weak 占比 on≤off /
  闩后转移=0);
- §5.1-G2/R-D 中盘分桶锁(r≤4 双侧不劣 CI 参考带 / r5-r9 纯披露);
- off 臂反事实记账锁(R3):门关帧照记 P(f) 位,零漂移落锁不变。
"""
from __future__ import annotations

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
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_line_gate_decision_bits,
    check_line_gate_starvation_anchor,
    check_line_switch_midgame_bucket,
)

_REG_GATE = dataclasses.replace(DEFAULT_REGISTRY,
                                line_switch_survival_gate_enabled=True)

#: P2 位面节点表(与 W379 夹具同款)
P2_TABLE = ['battle', 'battle', 'encounter', 'reward',
            'encounter', 'reward', 'boss']

#: 证据组 B 夹具(同 test_cw_w379_gate_v2_wire:异线「万敌单C」厚度证据)
EVIDENCE_BENCH = ['万敌', '千冶·刃', '长夜月', '刻律德菈', '缇宝']


def _state(plane: int = 2, **kw) -> GameState:
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


def _sess(plane: int = 2) -> StrategySession:
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
    sess = _sess()
    ist = update_intention(_state(shop=['希儿']), IntentionState(),
                           sess, registry=registry)
    assert ist.locked_comp == '希儿量子', '夹具前提:③锁希儿量子'
    assert ist.lock_layer == 3, '夹具前提:③信号层=3'
    gone = _state(bench=EVIDENCE_BENCH)
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
    out1 = update_intention(_state(env='列车同行概念股', hp=20), ist,
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
        out = update_intention(_state(env='列车同行概念股', hp=20),
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
        out = update_intention(_state(env='列车同行概念股', hp=20), ist,
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
        assert survival_gate(_state(hp=20), _sess(), math.inf,
                             _REG_GATE) == (False, 'alt_inf')
        out = update_intention(_state(env='列车同行概念股', hp=20), ist,
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
    out1 = update_intention(_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert out1.phase == 'locked' and sess.v3_line_gate_latch is True, \
        '夹具前提:闩已置位'
    # 窗口关闭帧(level=3 刷不出 5 费核心)连驱 9 帧 > 位面剩余节点 7
    # ——修复前第 8 帧即 evict:frozen 落 unlocked
    prev = out1
    for i in range(9):
        prev = update_intention(_state(level=3, hp=20, round_num=1),
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
    out1 = update_intention(_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert sess.v3_line_gate_latch is True, '夹具前提:闩置位'
    assert out1.prev_lock_layer == 3, '夹具前提:暂存=原锁层'
    pre_miss = out1.tracks['希儿量子'].miss_count
    assert pre_miss >= 1, '夹具前提:miss 计数非零(闩内持续累计)'
    # 位面切换 P2→P3(无信号帧:不触发出口,清零链可孤立观察)
    out2 = update_intention(_state(plane=3, round_num=1, hp=20),
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
    sess = _sess()
    st_p1 = _state(plane=1, hp=20)
    st_p3 = _state(plane=3, hp=20)
    assert survival_gate(st_p1, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    assert survival_gate(st_p3, sess, 99.0, _REG_GATE) == (True, 'gate_off')
    assert survival_gate(_state(hp=20), sess, 3.0,
                         DEFAULT_REGISTRY) == (True, 'gate_off')


# --- §6-7 FM-11 撤销面锁(v3 R-C) ----------------------------------------------


def test_line_gate_v3_relock_preserves_revoke_face() -> None:
    """FM-11 消解锁(DESIGN v3 §6-7/R-C):闩回锁恢复原锁层(3)而非
    回锁信号层(1)→ ①层优线仍可经出口②撤销(撤销面未被收窄)。
    位面切换清闩断言含在本锁前半;出口②对照用干净 session 构造帧
    (P3 帧的强制锁会同一帧消费 weak 态,属 P3 既有语义,不混入本锁)。"""
    ist, sess = _weak_on_xianzhou(_REG_GATE)
    out1 = update_intention(_state(env='列车同行概念股', hp=20), ist,
                            sess, registry=_REG_GATE)
    assert out1.phase == 'locked' and out1.lock_layer == 3, '夹具前提:闩回锁恢复层3'
    assert sess.v3_line_gate_latch is True
    # 位面切换 P2→P3:闩清零(phase!=locked → P3 强制锁随后接管,既有语义)
    out2 = update_intention(_state(plane=3, round_num=1, hp=20),
                            out1, sess, registry=_REG_GATE)
    assert sess.v3_line_gate_latch is False
    assert sess.v3_line_gate_latch_plane is None
    # FM-11 实质(干净 session 构造帧,排除闩/强制锁干扰):
    # 回锁态 lock_layer=3 → ①层优线可经出口②撤销;
    # 反事实对照:若回锁残留 layer=1(未恢复),同一帧撤销不可达。
    frame = _state(env='列车同行概念股', shop=['姬子·启行'], hp=100)
    base3 = IntentionState(phase='locked', locked_comp='希儿量子',
                           lock_layer=3)
    out3 = update_intention(frame, base3, _sess())
    assert out3.phase == 'weak' and out3.weak_comp == '希儿量子'
    assert out3.last_event.startswith('revoke:higher:列车同行')
    assert out3.prev_lock_layer == 3, '撤销暂存原锁层(闩回锁恢复的消费面)'
    base1 = IntentionState(phase='locked', locked_comp='希儿量子',
                           lock_layer=1)
    out4 = update_intention(frame, base1, _sess())
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
    full = _state(hp=50, gold=60)
    full.bench = [BenchChar(slot=i, char_id='万敌', faction='?', star=1)
                  for i in range(8)]
    free = _state(hp=50, gold=60)
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
    sess = _sess()
    out = update_intention(_state(env='列车同行概念股', hp=20), ist, sess)
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
