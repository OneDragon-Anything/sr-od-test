# 板满换阵补部署(M1″)基础设施锁——select_swap_plan 谓词 / 共享装配 /
# 卖出通道统一排除 / 消费方分键 / engine 意图面。
# 语义出处:ADR-0530(board-full swap redeploy)+ dd-037(留 bench
# 合法稳态,fail-closed 不对称口径)。锁的存在性纪律:每条锁 docstring
# 引出处;本批锁的是**基础设施语义**(谓词判定/装配契约/分键显影),
# 不锁发射行为——sim 探针实证靶场景频率 0(0/2700 帧;sim 部署代理
# 消解板满形态,效果判定挂实机),发射位由 m1p_input_seam_pending 门
# 维持关闭。
from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    assemble_swap_plan_inputs,
    fenced_swap_arm_of,
    fresh_buys_of,
    record_fresh_buy,
    select_swap_plan,
    swap_sell_exclusion_reason,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    MandateFrame,
    run_mandate,
)

_TF = frozenset({'仙舟', '列车同行'})
_CORES = frozenset({'三月七', '瓦尔特'})
_TARGET_BENCH = '丹恒·饮月'      # 主阵营仙舟,bonds∩TF 非空 = 线内待上位
_VICTIM = '黑塔'                  # 银河学者/群攻:非 fenced off-target(注册表事实)


def _bc(name: str, slot: int = 1, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch.factions else '?'))


def _pick_fenced_offtarget(exclude: set[str]) -> str:
    """注册表直调取第二个 fenced off-target 名(锁前提自证,不拍名)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        DEPLOY_FENCE,
    )
    for name, ch in CHARACTERS.items():
        if name in exclude:
            continue
        bonds = set(ch.factions) | set(ch.flows)
        if bonds & DEPLOY_FENCE and not bonds & _TF:
            return name
    raise AssertionError('注册表缺 fenced off-target 样本,锁前提不成立')


def _base_ctx(*, deployed: list[BenchChar], bench: list[BenchChar],
              cap: int | None = 6, fenced: bool = False,
              membership: frozenset[str] | None = frozenset(),
              fresh: frozenset[str] = frozenset()) -> SwapPlanContext:
    return SwapPlanContext(
        target_factions=_TF, target_cores=_CORES, fw_carry=frozenset(),
        locked_factions=frozenset(), protect_names=frozenset(),
        membership=membership, fresh_buys=fresh, board={},
        deployed=deployed, bench=bench, cap=cap, fenced_on=fenced)


def _base_deployed() -> list[BenchChar]:
    """4 target 件(仙舟主阵营)+ 2 off-target victim(黑塔在先)。"""
    return [_bc('黑塔', 1), _bc('青雀', 2), _bc('停云', 3), _bc('藿藿', 4),
            _bc('爻光', 5), _bc('艾丝妲', 6)]


# ==================== 谓词锁①:基形(卖序+上序非空) ====================

def test_swap_plan_base_shape_sell_and_up() -> None:
    """基形锁(ADR-0530 决策1 组合语义):cap 满 ∧ bench 线内件 ∧ 非
    fenced off-target victim → 卖序非空 ∧ 上序 = 卖出后假想状态复用
    select_deployments 判非空(同一留置规则裁判,零新启发式)。up_bench
    为 bench 占用序下标,直查指向线内待上位件。"""
    bench = [_bc(_TARGET_BENCH)]
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=bench))
    assert plan.nonempty, plan
    assert plan.sell_names == [_VICTIM]
    assert {bench[i].char_id for i in plan.up_bench} == {_TARGET_BENCH}


# ==================== 谓词锁②:fenced 臂关闭全拒 ====================

def test_swap_plan_all_fenced_victims_refused_when_arm_closed() -> None:
    """fenced_arm_closed 锁(ADR-0522 W209 熔断口径):victim 全为
    fenced off-target ∧ 臂关(fp<1.00)→ 计划空 + 逐件拒因
    fenced_arm_closed——W209 熔断语义经 offtarget_sell_allowed 单一源
    传导,谓词不另写第二套 victim 语义。"""
    second = _pick_fenced_offtarget({_VICTIM, '艾丝妲'})
    deployed = [_bc('艾丝妲', 1), _bc(second, 2),
                _bc('青雀', 3), _bc('停云', 4), _bc('藿藿', 5), _bc('爻光', 6)]
    plan = select_swap_plan(_base_ctx(deployed=deployed,
                                      bench=[_bc(_TARGET_BENCH)],
                                      fenced=False))
    assert not plan.nonempty
    assert plan.reasons.get('艾丝妲') == 'fenced_arm_closed'
    assert plan.reasons.get(second) == 'fenced_arm_closed'


# ==================== 谓词锁③:victim 义务集排除 ====================

def test_swap_plan_membership_victim_excluded() -> None:
    """buy_membership 锁(ADR-0530 决策1/3 卖出通道统一义务集排除):victim ∈
    买面义务集 → 计划空 + 拒因 buy_membership(与 M4 燃料集同参同源,
    防 P60 换手循环在 swap 通道重演)。"""
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=[_bc(_TARGET_BENCH)],
                                      membership=frozenset({_VICTIM})))
    assert not plan.nonempty
    assert plan.reasons.get(_VICTIM) == 'buy_membership'


# ==================== 谓词锁④:轮内新鲜度排除(防抖+显影) ====================

def test_swap_plan_fresh_buy_victim_excluded() -> None:
    """fresh_buy 锁(ADR-0530 决策5:降格为防抖+显影辅助,单调性
    由义务集排除独立承载):victim ∈ 轮内买入名集 → 计划空 + 拒因
    fresh_buy。"""
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=[_bc(_TARGET_BENCH)],
                                      fresh=frozenset({_VICTIM})))
    assert not plan.nonempty
    assert plan.reasons.get(_VICTIM) == 'fresh_buy'


def test_fresh_buys_record_per_name_and_expire_by_round() -> None:
    """多买入意图逐名入集锁(ADR-0530 决策5)+ 轮内窗失效锁:同一
    发射批多个买入逐名登记(漏记 = 防抖失效静默);位面/轮次推进 = 集
    自动失效(M7 闩键式同构)。"""
    sess = _NS()
    st = GameState(plane=1, round_num=2)
    record_fresh_buy(sess, st, '甲')
    record_fresh_buy(sess, st, '乙')
    assert fresh_buys_of(sess, st) == frozenset({'甲', '乙'})
    st2 = GameState(plane=1, round_num=3)
    assert fresh_buys_of(sess, st2) == frozenset()   # 轮次推进自动失效
    st3 = GameState(plane=2, round_num=2)
    assert fresh_buys_of(sess, st3) == frozenset()   # 位面推进同辖


# ==================== 谓词锁⑤:双弃权键(fail-closed) ====================

def test_swap_plan_cap_unreadable_abstain() -> None:
    """cap_unreadable 锁(dd-037 维持 fail-closed;ADR-0530 决策1
    双弃权键 同构语义):cap 缺读 ⇒ 谓词弃权、计划空,与 M1/M1′ vacancy=0
    门同向(dd-037 留 bench 合法稳态比误判发射便宜)。"""
    reasons: dict[str, str] = {}
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=[_bc(_TARGET_BENCH)],
                                      cap=None), reasons_out=reasons)
    assert plan.abstain == 'cap_unreadable'
    assert not plan.nonempty
    assert reasons.get('(plan)') == 'cap_unreadable'


def test_swap_plan_membership_unreadable_abstain() -> None:
    """membership_unreadable 锁(ADR-0530 决策1 钉死:缺读 = 谓词
    弃权、计划空,消除「排除集空=放行」与拒因并存的语义自相矛盾)。"""
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=[_bc(_TARGET_BENCH)],
                                      membership=None))
    assert plan.abstain == 'membership_unreadable'
    assert not plan.nonempty


def test_assembly_abstains_membership_when_intention_missing() -> None:
    """装配级缺读锁:session 无 v3_intention ⇒ 装配产物 membership=None
    ⇒ 谓词弃权(发射面与执行面经同一装配函数吃同一 fail-closed 行为,
    禁消费面自写第二份缺读语义)。"""
    sess = _NS(v3_intention=None, target_comp=None,
               transition_framework='')
    st = GameState(plane=1, round_num=2, board={})
    ctx = assemble_swap_plan_inputs(sess, state=st,
                                    deployed=_base_deployed(),
                                    bench=[_bc(_TARGET_BENCH)], cap=6)
    assert ctx is not None and ctx.membership is None
    assert select_swap_plan(ctx).abstain == 'membership_unreadable'


# ==================== 谓词锁⑥:板满门占用数口径 ====================

def test_swap_plan_board_full_counts_unrecognized_occupants() -> None:
    """占用数口径锁(ADR-0530 决策1):板满门 = len(deployed)(占用
    件数)≥ cap,**含 SIFT 未识别 char_id='' 占位件**——禁
    len(deployed_cids) 衍生集口径(未识别件漏计 → 板实满判未满),与
    执行侧 cap 门「禁用衍生计数」(cw_op_deploy.swap_arm_deployed_count
    docstring)同向。本锁:6 占用中 1 件未识别,占用数口径判满并开计划。"""
    deployed = [_bc(_VICTIM, 1), _bc('青雀', 2), _bc('停云', 3),
                _bc('藿藿', 4), _bc('爻光', 5),
                BenchChar(slot=6, char_id='')]   # SIFT 未识别占位件
    assert sum(1 for d in deployed if d.char_id) == 5   # 衍生集口径会漏计
    plan = select_swap_plan(_base_ctx(deployed=deployed,
                                      bench=[_bc(_TARGET_BENCH)]))
    assert plan.nonempty, plan   # 占用数 6 ≥ cap 6:门开


# ==================== 谓词锁⑦:底线留置件不作上序候选 ====================

def test_swap_plan_recipe_floor_bench_piece_not_up_candidate() -> None:
    """post_sell_held 锁(ADR-0530 决策1 底线留置件不作上序候选):
    配方底线规则(列车≥2 档 ∧ 仙舟<3)在卖出后假想状态留 bench 的列车
    件**不作上序候选**——上序裁判 = select_deployments 同一套留置规则,
    「白卖一件板面变弱」形态在谓词内不可达。板面构造:2 列车同行主阵营
    在场 + 0 仙舟档。"""
    train_a, train_b = '三月七', '瓦尔特'   # 主阵营列车同行(注册表事实)
    deployed = [_bc(_VICTIM, 1), _bc(train_a, 2), _bc(train_b, 3),
                _bc('阿格莱雅', 4), _bc('飞霄', 5), _bc('乱破', 6)]
    bench = [_bc('姬子·启行')]   # 列车同行主阵营候选(会被底线留置)
    plan = select_swap_plan(_base_ctx(deployed=deployed, bench=bench))
    assert not plan.nonempty
    assert plan.reasons.get('姬子·启行') == 'post_sell_held'
    assert '姬子·启行' not in {bench[i].char_id for i in plan.up_bench}


# ==================== fenced 臂判据迁移:单一源同一性 ====================

def test_fenced_arm_single_source_identity() -> None:
    """re-export 同一性锁(ADR-0530 决策2:fenced 臂判据迁
    kernel,执行侧 re-export 兼容——operations 桶副本必须归零,双源 =
    r271 批同型复发)。"""
    from sr_od.application.currency_war.kernel import cw_deploy_logic as dl
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy
    assert cw_op_deploy.fenced_swap_arm_of is dl.fenced_swap_arm_of
    assert cw_op_deploy.swap_arm_deployed_count is dl.swap_arm_deployed_count
    # 判据语义不变(真值表同 test_cw_deploy_ops 锁,防迁移改行为)
    assert fenced_swap_arm_of(1.0, 7, 2, 5) is True
    assert fenced_swap_arm_of(0.42, 7, 2, 5) is False
    assert fenced_swap_arm_of(1.0, 6, 2, 5) is False


# ==================== engine M1″ 意图面:双向断言 ====================

def _m1p_state(*, deployed: list[BenchChar], bench: list[BenchChar],
               cap: int = 6) -> GameState:
    return GameState(gold=0, level=6, deploy_cap=cap, plane=1, round_num=2,
                     board={}, deployed=list(deployed), bench=list(bench))


def test_m1p_intent_face_bidirectional() -> None:
    """M1″ 意图面双向断言锁(ADR-0530 决策6:sim 只建模发射意图,不建模
    执行语义):计划非空 ⇒ 意图记录 nonempty=True 且带卖序;计划空 ⇒
    nonempty=False 无卖序——两向都可红,谓词在 sim 帧分布上的正确性
    覆盖不依赖执行建模。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        m1p_intent_record,
    )
    sess = _NS(target_comp=None,
               v3_intention=_NS(locked_comp='', p1_pair=(), phase='',
                                transition_pair=()),
               transition_framework='')
    # 非空帧:板满(cap=6,6 占用)+ bench 线内件 + 非 fenced victim
    rec = m1p_intent_record(_m1p_state(deployed=_base_deployed(),
                                       bench=[_bc(_TARGET_BENCH)]), sess)
    assert rec['nonempty'] is True and rec['sell'] == [_VICTIM]
    assert rec['up'] >= 1 and rec['abstain'] == ''
    # 空帧:cap 不满(3 占用)⇒ 板满门关 ⇒ 无意图
    rec0 = m1p_intent_record(_m1p_state(
        deployed=_base_deployed()[:3],
        bench=[_bc(_TARGET_BENCH)]), sess)
    assert rec0['nonempty'] is False and rec0['sell'] == []
    assert rec0['abstain'] == ''


def test_m1p_intent_face_records_abstain() -> None:
    """意图面弃权显影锁:意向供给缺失帧(savestate v3_intention=None)
    ⇒ membership 缺读弃权在意图记录中可见(零静默,判读可归因)。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        m1p_intent_record,
    )
    sess = _NS(target_comp=None, v3_intention=None,
               transition_framework='')
    rec = m1p_intent_record(_m1p_state(deployed=_base_deployed(),
                                       bench=[_bc(_TARGET_BENCH)]), sess)
    assert rec['nonempty'] is False
    assert rec['abstain'] == 'membership_unreadable'


# ==================== mandate M1″ 消费方:seam 门关闭态 ====================

def _m1p_frame(*, deployed: list[BenchChar], bench: list[BenchChar],
               cap: int | None = 6) -> MandateFrame:
    return MandateFrame(gold=0, level=6, bench=bench, deployed=deployed,
                        deploy_cap=cap, node_type=None, stop_flag=False,
                        k_members=(), round_num=2)


def _m1p_session(seam: bool | None) -> _NS:
    s = _NS(cw4_counters={},
            v3_intention=_NS(locked_comp='', p1_pair=(), phase='',
                             transition_pair=()),
            target_comp=None, transition_framework='',
            last_owned_equips=None)
    if seam is not None:
        s.cw4_m1p_seam_verified = seam
    return s


def test_m1p_consumer_seam_gate_keeps_emission_closed() -> None:
    """m1p_input_seam_pending 关闭态锁(ADR-0530 决策4:装配两侧输入
    核对通过前发射位关闭,分键显影,缺省关 = fail-closed):计划非空帧
    不发 RunDeploy,仅计 m1p_input_seam_pending;置 seam 位后同帧形态
    才发射(RunDeploy reason=m1_swap_redeploy + m1p_fired)。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    # 关闭态(缺省,无 seam 位)
    sess = _m1p_session(None)
    out = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess, state=st)
    assert not any(e.action.__class__.__name__ == 'RunDeploy' for e in out)
    assert sess.cw4_counters.get('m1p_input_seam_pending') == 1
    assert 'm1p_fired' not in sess.cw4_counters
    # 显式置位(seam 核对通过后的唯一合法开闸态)
    sess2 = _m1p_session(True)
    out2 = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess2,
                       state=st)
    fired = [e for e in out2 if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert sess2.cw4_counters.get('m1p_fired') == 1
    assert 'm1p_input_seam_pending' not in sess2.cw4_counters


def test_m1p_consumer_counts_plan_empty_and_cap_unreadable() -> None:
    """消费方分键锁:计划空帧 → m1p_plan_empty;cap 缺读帧 →
    m1p_cap_unreadable(零静默,判读可归因)。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    sess = _m1p_session(None)
    # cap 满帧但上序空(bench 候选与在场件同名,M1/M1′ 因 vacancy=0 不发,
    # M1″ 计划空分键显影)
    dep_dup = [_bc(_VICTIM, 1), _bc('青雀', 2), _bc('停云', 3),
               _bc('藿藿', 4), _bc('爻光', 5), _bc(_TARGET_BENCH, 6)]
    st_dup = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                       deployed=list(dep_dup), bench=list(bench))
    run_mandate(_m1p_frame(deployed=dep_dup, bench=bench), sess,
                state=st_dup)
    assert sess.cw4_counters.get('m1p_plan_empty') == 1
    # cap 缺读帧:frame.deploy_cap=None → 弃权键
    sess2 = _m1p_session(None)
    run_mandate(_m1p_frame(deployed=dep, bench=bench, cap=None), sess2,
                state=st)
    assert sess2.cw4_counters.get('m1p_cap_unreadable') == 1


def test_m1p_consumer_input_missing_not_mixed_into_plan_empty() -> None:
    """m1p_input_missing 分键锁(落地审低④:供给缺失 ≠ 真计划空,禁混桶
    ——「不冒名拒因」纪律,can_deploy_single 的 unannotated 先例同型):
    装配不可得(state 与 cap 双缺 ⇒ 装配函数返回 None)帧计入
    m1p_input_missing,m1p_plan_empty 不计数。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    sess = _m1p_session(None)
    run_mandate(_m1p_frame(deployed=dep, bench=bench, cap=None), sess,
                state=None)
    assert sess.cw4_counters.get('m1p_input_missing') == 1
    assert 'm1p_plan_empty' not in sess.cw4_counters
    assert 'm1p_cap_unreadable' not in sess.cw4_counters


# ==================== 执行侧卖出臂:义务集∪新鲜度排除接线 ====================

def test_swap_sell_exclusion_single_source_verdict() -> None:
    """执行侧排除单一判定锁(落地审阻断 #1 修复;ADR-0530 决策3):
    `swap_sell_exclusion_reason` = 发射面谓词与执行侧卖出臂共用的唯一
    义务集∪新鲜度判定——买面义务集成员 → buy_membership;轮内新鲜
    买入件 → fresh_buy;义务集缺读 → membership_unreadable(执行面
    fail-closed = 全候选禁卖);普通件 → ''。执行侧 `_sell_offtarget_
    deployed` 逐候选消费本判定(禁第二份实现),P60 卖义务件↔买回环
    在执行路径同受保护。"""
    ctx = _base_ctx(deployed=[], bench=[],
                    membership=frozenset({'艾丝妲'}), fresh=frozenset({_VICTIM}))
    assert swap_sell_exclusion_reason('艾丝妲', ctx) == 'buy_membership'
    assert swap_sell_exclusion_reason(_VICTIM, ctx) == 'fresh_buy'
    assert swap_sell_exclusion_reason('青雀', ctx) == ''
    ctx_unread = _base_ctx(deployed=[], bench=[], membership=None)
    assert swap_sell_exclusion_reason(_VICTIM, ctx_unread) \
        == 'membership_unreadable'
    assert swap_sell_exclusion_reason(_VICTIM, None) == ''
    assert swap_sell_exclusion_reason('', ctx) == ''


