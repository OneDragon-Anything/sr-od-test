"""W628 · 重构迁移批 2(方向层接管+效果层归位+开关清偿)锁面。

依据 = 蓝图 v-final.1 §7 批 2 行 + §4.3-R1/R5 + W622 预验尸 P1-P9 +
W620 BATCH2_APPENDIX 三危险供给点(D1/D2/D3):

1. D1:hoard 可信位——投影失败帧 ``hoard_readable=False``,消费域走保守域,
   变异探针(投影抛错)下买侧行为 ≠ 空集放行;
2. D2:committed 缺供给帧 = 保守侧 False(拔供给探针),禁缺省激进侧;
3. D3:息线单一源 = ``registry.interest_floor()`` 派生(interest_cap×10),
   全仓属性读点 = 0(grep 锁)+ ALL IN override 通道;
4. P7:意向状态机驱动点契约——每 game-round 恰一次(键守卫幂等),
   registry 注入分歧探针(P6:注入臂与缺省臂必须出现受控分歧);
5. P4:ist 跨局零残留(每局新建 StrategySession 构造性保证的行为锁);
6. 哨兵锁:局23 型帧(100 金+备战空+interest 姿态)新栈产出 release 帧
   (W611 锁沿用,经 assemble 预算投影复合验证);
7. committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁(P1 段
   小帧集,分歧仅允许出现在方向层接管区并逐帧定性)。
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    committed_authority,
    drive_intention,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY as _REG,
)
from sr_od.application.currency_war.kernel.cw_state import GameState
from sr_od.application.currency_war.kernel.cw_transition import CommitSignals
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession
from sr_od.application.currency_war.strategies.impl.mandate_v1.assembly import (
    assemble,
    hoard_consumer_domain,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.contracts import (
    Snapshot,
    SubstateClassification,
)

_SRC = (Path(__file__).parents[5] / 'src' / 'sr_od' / 'application'
        / 'currency_war')


def _snapshot(plane: int = 1, round_num: int = 2) -> Snapshot:
    return Snapshot(
        classification=SubstateClassification(
            name='prep_shop', evidence=('test',), confident=True),
        plane=plane, round_num=round_num, level=3, gold=40, gold_trusted=True,
        free_bench_slots=3, deploy_vacancy=1, shop_open=False,
    )


def _state(plane: int = 1, round_num: int = 2, gold: int = 40) -> GameState:
    st = GameState()
    st.plane = plane
    st.round_num = round_num
    st.gold = gold
    st.level = 3
    return st


# ----------------------------------------------------- D1 hoard 可信位

def test_d1_hoard_readable_normal_frame():
    """正常帧:ist 未锁 → hoard = ⑤兜底域(fallback),可信位为真。

    「空集双义」分离的关键:正常帧 readable 恒 True(含 fallback 非空域
    与真空集),失败帧才 False——消费侧语义不因实现细节抖动。
    """
    sess = StrategySession()
    sess.v3_intention = IntentionState()
    turn = assemble(_snapshot(), sess)
    assert turn.direction.hoard_readable is True
    assert isinstance(turn.direction.hoard, frozenset)


def test_d1_mutation_probe_projection_failure_conservative_domain():
    """变异探针(D1 验收判据):hoard_target_set 抛错 → 消费域 = 保守域。

    静默退空集 = 锁线局囤货方向消失一帧、买侧按无方向放行——本锁钉住
    「投影失败」与「真无目标」表示分离(hoard_readable 位)。
    """
    import sr_od.application.currency_war.kernel.cw_intention as cw_intention_mod

    sess = StrategySession()
    sess.v3_intention = IntentionState()
    orig = cw_intention_mod.hoard_target_set

    def _boom(_state, _ist):
        raise RuntimeError('注入:投影失败')

    try:
        cw_intention_mod.hoard_target_set = _boom
        turn = assemble(_snapshot(), sess)
    finally:
        cw_intention_mod.hoard_target_set = orig
    d = turn.direction
    assert d.hoard_readable is False          # 失败帧显式暴露
    full = frozenset({'任意件A', '任意件B'})
    assert hoard_consumer_domain(d, full) == full     # 保守域,非空集放行
    ok = replace(d, hoard_readable=True)
    assert hoard_consumer_domain(ok, full) == ok.hoard  # 正常帧走目标集


# ----------------------------------------------------- D2 缺供给保守侧
# (原 test_d2_missing_supply_falls_conservative 已并入
#  test_cw_w620_migration_b1::test_committed_from_semantics——缺供给
#  保守侧为其分支 1,committed_authority 直调两形态已随迁。重复构成
#  删并理由(README 纪律 8)。)


# ----------------------------------------------------- W629-R2 镜像雷锁


def test_d3_grep_lock_no_interest_floor_attribute_reads():
    """grep 锁(D3):``registry/reg.interest_floor`` 属性读点全仓 = 0。

    豁免:registry.py 定义处(方法本体/override 字段/注释);调用形态
    ``.interest_floor()`` 不匹配(带括号),裸属性读(无括号)即违规。
    """
    pat = re.compile(r'\b(?:registry|reg)\.interest_floor\b(?!\()')
    offenders = {}
    for path in _SRC.rglob('*.py'):
        hits = len(pat.findall(path.read_text(encoding='utf-8')))
        if hits:
            offenders[path.name] = hits
    assert set(offenders) <= {'registry.py'}, offenders


# ----------------------------------------------------- P7 驱动点契约 + P6 注入

def test_p7_drive_intention_idempotent_per_round():
    """P7:同 (plane, round) 重入驱动 = 幂等(键守卫),跨轮才推进。"""
    sess = StrategySession()
    st = _state(plane=1, round_num=2)
    drive_intention(st, sess)
    assert sess.v3_intention_key == (1, 2)
    ev1 = sess.v3_intention.last_event
    drive_intention(st, sess)                     # 同轮重入:不重复驱动
    assert sess.v3_intention_key == (1, 2)
    assert sess.v3_intention.last_event == ev1
    drive_intention(_state(plane=1, round_num=3), sess)   # 跨轮:推进
    assert sess.v3_intention_key == (1, 3)


def test_p6_registry_injection_reaches_state_machine():
    """P6 注入分歧探针:注入臂与缺省臂必须出现受控分歧,无分歧 = 注入链断。

    旋钮 = line_env_lock_min_round(环境判据观察期):调大 = 判据本轮不辖
    → 对抗环境帧缺省臂缓锁、注入臂落锁——两臂 ist 分歧即注入链可达证。
    【夹具演进(经济冻结批)】原 plane=2 unlocked 帧:旧形态缺省臂保持
    unlocked;现 P2 unlocked 帧被强制 assignment 移交锁接管(目标不空窗
    语义,test_cw_economic_freeze.py ①组),与旋钮无关 → 不再承载分歧。
    改用 weak 帧(撤销机器在册态,移交不辖,「直至新信号」语义保留)。
    """
    from sr_od.application.currency_war.kernel.cw_intention import update_intention
    st = _state(plane=2, round_num=1)   # P2:comp 锁定通道(P1 配方锁区不锁 comp)
    st.enemy_affixes = ['净化身心']            # 对抗词缀(万敌强环境不命中)
    st.shop = [SimpleNamespace(name='万敌')]   # ③核心卡信号可见
    reg_def = _REG
    reg_inj = replace(_REG, line_env_lock_min_round=99)
    ist_def = update_intention(st, IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_def)
    ist_inj = update_intention(st, IntentionState(phase='weak', weak_comp='万敌单C'),
                               None, registry=reg_inj)
    assert ist_def.locked_comp == ''            # 缺省臂:环境判据缓锁(weak 保持)
    assert ist_inj.locked_comp != ''            # 注入臂:判据不辖 → 落锁


def test_p4_ist_zero_residue_across_matches():
    """P4:跨局 ist 零残留——每局新建 StrategySession,ist/驱动键从零开始。"""
    sess = StrategySession()
    drive_intention(_state(), sess)
    assert sess.v3_intention is not None and sess.v3_intention.evicted == set()
    fresh = StrategySession()   # 新局(构造性重置)
    assert fresh.v3_intention is None
    assert fresh.v3_intention_key is None


# ----------------------------------------------------- 哨兵锁:局23 型帧
# (原 test_sentinel_ju23_frame_releases_on_new_stack 已并入
#  test_cw_w633_migration_b3::test_jue23_sentinel_obligation_chain_alive
#  ——同一哨兵 w633 版义务链+release 族更全;budget.interest_floor==50
#  供给面由 w611 恒等式(全局)+ w633 注入一致性锁(BudgetView 透传)共辖。
#  重复构成删并理由(README 纪律 8)。)


# ------------------------------------------- committed 谓词逐帧对拍(P1 附)

def _old_committed(state: GameState, session: StrategySession) -> bool:
    """旧语义复刻(update_target L125-132 判定式;对拍基准,非生产路径)。

    committed = plane≥2 ∨ (signals.ready ∧ (可切换 ∨ target==领先线))。
    """
    from sr_od.application.currency_war.kernel.cw_transition import t_of
    if state.plane >= 2:
        return True
    sig = getattr(session, 'commit_signals', None)
    if sig is None:
        return False
    ready = sig.ready(t_of(state.plane, state.round_num))
    lead = sig.leader() if ready else None
    return bool(ready and lead is not None)


def test_committed_predicate_frame_by_frame_vs_old():
    """committed 翻真谓词 vs 旧 CommitSignals 判定:逐帧对拍锁。

    帧集(判前锁):分歧仅允许出现在「方向层接管区」= 新谓词尚保守
    (ist 未锁)而旧信号已 ready 的窗口;反向分歧(新 True 旧 False)
    仅允许 plane≥2 帧。任何出区分歧 = 谓词漂移,门红。
    """
    frames = []
    # 帧1-2:P1 前段,信号空、ist 未锁 → 双 False
    for rnd in (1, 3):
        frames.append((_state(plane=1, round_num=rnd), StrategySession(),
                       'both_false'))
    # 帧3:P1 信号 ready(分超阈+过轮门)但 ist 未锁 → 预期分歧(接管区,
    # 新谓词保守)
    s3 = StrategySession()
    s3.commit_signals = CommitSignals()
    s3.commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_state(plane=1, round_num=8), s3, 'takeover_zone_only_old'))
    # 帧4:ist 已锁 → 双 True
    s4 = StrategySession()
    s4.v3_intention = IntentionState(phase='locked', locked_comp='万敌燃血')
    s4.commit_signals = CommitSignals()
    s4.commit_signals.scores = {'万敌燃血': 99.0}
    frames.append((_state(plane=1, round_num=8), s4, 'both_true'))
    # 帧5:P2 → 双 True(语义边界保留)
    frames.append((_state(plane=2, round_num=1), StrategySession(),
                   'both_true_p2'))
    for st, sess, expect in frames:
        new_v = committed_authority(st, sess)
        old_v = _old_committed(st, sess)
        if expect == 'both_false':
            assert not new_v and not old_v
        elif expect == 'both_true' or expect == 'both_true_p2':
            assert new_v and old_v
        else:   # takeover_zone_only_old:旧翻新未翻 = 接管区唯一合法分歧形
            assert old_v and not new_v, (st.plane, st.round_num, new_v, old_v)
