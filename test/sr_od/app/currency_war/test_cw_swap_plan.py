# 板满换阵补部署(M1″)基础设施锁——select_swap_plan 谓词 / 共享装配 /
# 卖出通道统一排除 / 消费方分键 / engine 意图面 / engine 执行面。
# 语义出处:ADR-0530(board-full swap redeploy)+ dd-037(留 bench
# 合法稳态,fail-closed 不对称口径)。锁的存在性纪律:每条锁 docstring
# 引出处;本批锁的是**基础设施语义**(谓词判定/装配契约/分键显影/
# 执行转录),不锁 sim 帧分布上的发射频率(行为分布归批判读,频次
# 探针=批统计)。执行面(T-169,总图设计 R2 §2 sim 边界行)接入后
# 换血行为 sim 可见:计划非空帧卖 victim(cw_state.simulate 单一源)
# + 轮末残余补部署补上——执行转录锁由 test_m1p_execution_face_*
# 承载;发射门已开闸(ADR-0530 开闸批:M1P_SEAM_VERIFIED 缺省 True),
# seam 门两态与 m1p_fired 发射面由
# test_m1p_consumer_seam_gate_keeps_emission_closed 承载。
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
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
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


# 谓词锁⑤之一:cap 缺读弃权(membership 缺读弃权由下方装配级缺读锁
# 一并承载:装配产物 membership=None 经同一谓词分支弃权,同文件超集)

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
    r271 批同型复发)。fp 门真值单行在本锁自持;占用数口径真值表由
    test_fenced_arm_revives_on_occupancy_full_frame 自持(cap 全域扫;
    原 test_cw_deploy_ops 同型真值表已删,其头部注记回指本文件)。"""
    from sr_od.application.currency_war.kernel import cw_deploy_logic as dl
    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy
    assert cw_op_deploy.fenced_swap_arm_of is dl.fenced_swap_arm_of
    assert cw_op_deploy.swap_arm_deployed_count is dl.swap_arm_deployed_count
    assert fenced_swap_arm_of(0.42, 7, 7) is False   # fp 门:未成型臂关


# ==================== 成型臂复活锁(占用数口径收口) ====================

def test_fenced_arm_revives_on_occupancy_full_frame() -> None:
    """成型臂复活锁(fenced成型臂物理槽位门语义 bug 修复:占用数口径
    统一,REVISION_R2 同根双源收口):线成型 fp≥1.00 ∧ 占用数 = cap 帧
    ⇒ fenced 臂可开。旧代码板满门 = deployed_n ≥ 前后排物理槽位总数
    (4+6=10),而 XP_TO_NEXT_LEVEL 键域 3..9 ⇒ level≤9 ⇒ level 驱动
    cap 全域 <10 ⇒ 旧门全域不可达、成型臂恒死——本帧旧代码恒关,
    本锁红即回归护栏。"""
    # 纯函数面:level 驱动可达 cap 域(3..9,XP_TO_NEXT_LEVEL 键域)
    # 内「占用数 = cap」帧全开;cap 缺读/非法 = 臂关(fail-closed)。
    from sr_od.application.currency_war.kernel.cw_state import (
        XP_TO_NEXT_LEVEL,
    )
    caps = sorted(set(XP_TO_NEXT_LEVEL) | {max(XP_TO_NEXT_LEVEL) + 1})
    for cap in caps:
        assert fenced_swap_arm_of(1.0, cap, cap) is True, cap
        assert fenced_swap_arm_of(1.0, cap - 1, cap) is False, cap
    assert fenced_swap_arm_of(1.0, 9, None) is False
    assert fenced_swap_arm_of(1.0, 9, 0) is False
    # 装配面:fp=1.00 ∧ 9 占用/9 cap(state.max_units() 现算链)⇒
    # ctx.fenced_on=True(旧物理门形态此帧恒 False)。
    comp = _NS(all_factions=('仙舟',), core_chars=('三月七',),
               factions=('仙舟',), form_tiers={'仙舟': 2},
               shared_chars=(), substitute_plan=None)
    sess = _NS()
    state_of(sess).target_comp = comp
    state_of(sess).transition_framework = ''
    dep = [BenchChar(slot=i, char_id=f'p{i}', star=1)
           for i in range(1, 10)]   # 9 占用(喂入只计占用数,名不查注册表)
    st = GameState(gold=0, level=9, deploy_cap=9, plane=1, round_num=2,
                   board={'仙舟': 2}, deployed=list(dep), bench=[])
    ctx = assemble_swap_plan_inputs(sess, state=st, deployed=dep,
                                    bench=[], cap=9)
    assert ctx is not None and ctx.fenced_on is True, '复活锁:占用数满帧臂开'
    # 未成型对照:同板面 fp<1.00 ⇒ 臂关(熔断保护原语义零变化)。
    st_half = GameState(gold=0, level=9, deploy_cap=9, plane=1,
                        round_num=2, board={'仙舟': 1},
                        deployed=list(dep), bench=[])
    ctx_half = assemble_swap_plan_inputs(sess, state=st_half,
                                         deployed=dep, bench=[], cap=9)
    assert ctx_half is not None and ctx_half.fenced_on is False


# ==================== engine M1″ 意图面:双向断言 ====================

def _m1p_state(*, deployed: list[BenchChar], bench: list[BenchChar],
               cap: int = 6) -> GameState:
    return GameState(gold=0, level=6, deploy_cap=cap, plane=1, round_num=2,
                     board={}, deployed=list(deployed), bench=list(bench))


def test_m1p_intent_face_bidirectional() -> None:
    """M1″ 意图面双向断言锁(ADR-0530 决策6:sim 只建模发射意图,不建模
    执行语义)。F1 用例预期更新(T-167,ADR-0534 修订节):无方向帧
    (target 视图空 = 事故形态)从「计划非空」变「弃权 no_direction +
    计划空」——sim 镜像经 select_swap_plan 自动继承谓词,零第二份;
    定向帧(有 comp ∧ bench 线内件 ∧ 板满)保持计划非空 + 卖序双向可红。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_realizable,
    )
    from sr_od.application.currency_war.sim.engine_p1 import (
        m1p_intent_record,
    )
    sess = _NS()
    state_of(sess).target_comp = None
    state_of(sess).v3_intention = _NS(locked_comp='', p1_pair=(), phase='',
                                      transition_pair=())
    state_of(sess).transition_framework = ''
    # 无方向帧(事故同态:板满 + bench 有件 + target 视图空)→ 弃权
    rec_nd = m1p_intent_record(_m1p_state(
        deployed=_base_deployed(), bench=[_bc(_TARGET_BENCH)]), sess)
    assert rec_nd['nonempty'] is False
    assert rec_nd['abstain'] == 'no_direction'
    assert swap_realizable(assemble_swap_plan_inputs(
        sess, state=_m1p_state(deployed=_base_deployed(),
                               bench=[_bc(_TARGET_BENCH)]),
        deployed=_base_deployed(),
        bench=[_bc(_TARGET_BENCH)],
        cap=6)) == (False, 'no_direction'), 'sim 镜像与生产谓词同源同值'
    # 定向帧:计划非空(卖序非空 + up 非空)
    sess_d = _NS()
    state_of(sess_d).target_comp = _DIRECTED_COMP
    state_of(sess_d).v3_intention = _NS(locked_comp='', p1_pair=(), phase='',
                                        transition_pair=())
    state_of(sess_d).transition_framework = ''
    rec = m1p_intent_record(_m1p_state(deployed=_base_deployed(),
                                       bench=[_bc(_TARGET_BENCH)]), sess_d)
    assert rec['nonempty'] is True and rec['sell'] == [_VICTIM]
    assert rec['up'] >= 1 and rec['abstain'] == ''
    # 空帧:cap 不满(3 占用)⇒ 板满门关 ⇒ 无意图
    rec0 = m1p_intent_record(_m1p_state(
        deployed=_base_deployed()[:3],
        bench=[_bc(_TARGET_BENCH)]), sess_d)
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


# ==================== engine M1″ 执行面:卖出转录(T-169) ====================

def _m1p_directed_session() -> _NS:
    """定向帧 session(与意图面双向锁的 sess_d 同构装配)。"""
    sess = _NS()
    state_of(sess).target_comp = _DIRECTED_COMP
    state_of(sess).v3_intention = _NS(locked_comp='', p1_pair=(), phase='',
                                      transition_pair=())
    state_of(sess).transition_framework = ''
    return sess


class _RetPool:
    """有限牌池 ret 探针(只记回池名;执行面只消费 ret 一面)。"""

    def __init__(self) -> None:
        self.retired: list[str] = []

    def ret(self, name: str) -> None:
        self.retired.append(name)


def test_m1p_execution_face_sells_victim_with_ledger_row() -> None:
    """执行面锁(T-169 最小执行面;总图设计 R2 §2 sim 边界行,修订
    ADR-0530「sim 不建模执行侧」申报):定向板满帧计划非空 ⇒ 逐件卖
    victim 经 cw_state.simulate 单一源——victim 下场(槽位置 None)、
    金回充(卖出回金)、牌池回填、账本转录行(name+reason=
    m1_swap_redeploy,换血可见性判读锚;既有显式动作行无名,本行加键
    不破消费)。补上(腾位后残余补部署)在引擎轮末部署块,集成面归
    重锚批判读,不在本单测辖域。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
        m1p_swap_execute,
    )
    st = _m1p_state(deployed=_base_deployed(),
                    bench=[_bc(_TARGET_BENCH)])
    plan, rec, _ctx = _m1p_plan_and_record(st, _m1p_directed_session())
    assert plan.nonempty and rec['sell'] == [_VICTIM]
    acts: list[dict] = []
    spend: dict = {'buys': {}, 'levelup': 0, 'refresh': 0, 'sell_income': 0}
    pool = _RetPool()
    st2, sold = m1p_swap_execute(st, plan, acts=acts, spend=spend,
                                 pool=pool)
    assert sold is True
    # victim 下场(卖出槽位 None 不移位;其余件不动)
    assert all(d is None or d.char_id != _VICTIM for d in st2.deployed)
    assert sum(d is not None for d in st2.deployed) == len(_base_deployed()) - 1
    # 金回充(单一源卖出回金)+ 账本转录行 + 池守恒
    assert st2.gold > st.gold
    assert len(acts) == 1
    row = acts[0]
    assert row['__type__'] == 'SellDeployed' and row['result'] == 'applied'
    assert row['name'] == _VICTIM
    assert row['reason'] == 'm1_swap_redeploy'
    assert row['income'] == spend['sell_income'] > 0
    assert pool.retired == [_VICTIM]


def test_m1p_execution_face_noop_when_plan_empty() -> None:
    """执行面零行为锁:计划空帧(板不满)⇒ 零卖出/零转录/零金流动
    (「计划空帧纯读」语义,引擎注释申报面的锁面)。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
        m1p_swap_execute,
    )
    st = _m1p_state(deployed=_base_deployed()[:3],
                    bench=[_bc(_TARGET_BENCH)])
    plan, rec, _ctx = _m1p_plan_and_record(st, _m1p_directed_session())
    assert not plan.nonempty and rec['sell'] == []
    acts: list[dict] = []
    spend: dict = {'buys': {}, 'levelup': 0, 'refresh': 0, 'sell_income': 0}
    st2, sold = m1p_swap_execute(st, plan, acts=acts, spend=spend,
                                 pool=_RetPool())
    assert sold is False and st2.gold == st.gold and acts == []
    assert spend['sell_income'] == 0


# ==================== T-279 R1/R2:计划单一源补部署 ====================
# 语义出处:ADR-0640(C-A2 双源缺口修复;装配单一源契约 ADR-0530/0534
# 延伸至部署补上段)。锁面:①记录 up_names(R2);②R1-a 直投等价锁
# (条件式【推】:前提面 = victim 名一致 + 占用序稳定,断言对象 = 名字
# 集——对抗审 F3);③R1-b 防御锁(前提破帧缺口仍补);④mandate 计划
# 载荷透传锁。

def test_m1p_record_carries_up_names() -> None:
    """m1p 记录 up_names 锁(T-279 R2):记录 dict 追加上序名单(名字级,
    `swap_plan_up_names` 单一换算——up_bench 是 ctx.bench 下标非名字,
    对抗审 F3),与 up 计数一致;义务件处置四态直读的判读锚。"""
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
    )
    st = _m1p_state(deployed=_base_deployed(),
                    bench=[_bc(_TARGET_BENCH)])
    plan, rec, ctx = _m1p_plan_and_record(st, _m1p_directed_session())
    assert plan.nonempty
    assert rec['up'] == len(rec['up_names']) == 1
    assert rec['up_names'] == [_TARGET_BENCH]
    # 换算单一源:记录名单与 kernel helper 直调逐位同
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_plan_up_names,
    )
    assert rec['up_names'] == swap_plan_up_names(plan, ctx)


def test_m1p_plan_fill_deploys_plan_up_names() -> None:
    """R1-a 直投等价锁(T-279 R1;ADR-0640):卖出成功帧(m1p_swap_execute
    卖的就是计划 victim,卖出后板面 ≡ 计划假想态)⇒ 补部署逐位等于计划
    up 名单。条件式【推】的前提面显式断言(对抗审 F3):victim 名一致
    (rec['sell'] == 实际转录名)+ 占用序稳定(卖出后占用数 = 计划时点
    −1)+ up 名单在 bench;断言对象 = 名字集(up_names == 实际补上名)。
    本帧形态与局 18/局 58 缺口帧同构(板满 + 计划非空 + up=1)。"""
    from sr_od.application.currency_war.kernel.cw_state import (
        iter_occupied_deployed,
    )
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
        _m1p_plan_fill_deploy,
        m1p_swap_execute,
    )
    sess = _m1p_directed_session()
    st = _m1p_state(deployed=_base_deployed(),
                    bench=[_bc(_TARGET_BENCH)])
    plan, rec, ctx = _m1p_plan_and_record(st, sess)
    acts: list[dict] = []
    spend: dict = {'buys': {}, 'levelup': 0, 'refresh': 0, 'sell_income': 0}
    st2, sold = m1p_swap_execute(st, plan, acts=acts, spend=spend,
                                 pool=_RetPool())
    assert sold is True
    # —— 等价性前提面(条件式【推】的前提,显式断言)——
    assert rec['sell'] == [_VICTIM]                    # ① victim 名一致
    assert [a.get('name') for a in acts if a.get('__type__') == 'SellDeployed'] \
        == [_VICTIM]                                   # ① 实际卖出 = 计划 victim
    occ_after_sell = sum(1 for _ in iter_occupied_deployed(st2.deployed))
    assert occ_after_sell == len(_base_deployed()) - 1  # ③ 占用 = 计划时点 −1
    # —— R1-a 直投:补上名单 == 计划 up 名单(名字集断言)——
    res_up, res_held, lag = _m1p_plan_fill_deploy(st2, plan, ctx, sess)
    dep_names = {d.char_id for d in iter_occupied_deployed(st2.deployed)
                 if d.char_id}
    assert res_up == 1 and res_held == 0 and lag == 0
    assert set(rec['up_names']) <= dep_names, '计划 up 件必须真上板'
    assert dep_names == ({d.char_id for d in _base_deployed()}
                         - {_VICTIM}) | set(rec['up_names'])
    assert sum(1 for _ in iter_occupied_deployed(st2.deployed)) \
        == len(_base_deployed()), '单空槽补满 = 计划假想终态'


def test_m1p_plan_fill_falls_back_to_rederive_when_premise_broken() -> None:
    """R1-b 防御锁(T-279 R1;对抗审 F2/F4):直投前提破(计划 up 件不在
    bench——模拟板面漂移帧)⇒ 走装配单一源对卖出后现读重 derive,缺口
    仍被补(板满恢复),补上件来自重 derive 判定而非计划名单(已离席的
    计划 pick 禁虚报)。陪衬件 = 景元(注册表事实:仙舟主阵营,板上
    仙舟 ≥2 成对 ⇒ 围栏认可可补)。非 m1p 显式动作轮不归本函数辖
    (F4 辖域钉 m1_swap_redeploy 轮,由引擎分支结构承载)。"""
    from sr_od.application.currency_war.kernel.cw_state import (
        iter_occupied_deployed,
    )
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
        _m1p_plan_fill_deploy,
        m1p_swap_execute,
    )
    sess = _m1p_directed_session()
    st = _m1p_state(deployed=_base_deployed(),
                    bench=[_bc(_TARGET_BENCH), _bc('景元', 2)])
    plan, rec, ctx = _m1p_plan_and_record(st, sess)
    assert plan.nonempty
    assert rec['up_names'] == [_TARGET_BENCH], '锁前提:扫描序首件为计划 pick'
    acts: list[dict] = []
    spend: dict = {'buys': {}, 'levelup': 0, 'refresh': 0, 'sell_income': 0}
    st2, sold = m1p_swap_execute(st, plan, acts=acts, spend=spend,
                                 pool=_RetPool())
    assert sold is True
    # 前提破坏:计划 up 件从 bench 消失(漂移帧)
    st2.bench = [b for b in st2.bench
                 if b is None or b.char_id != _TARGET_BENCH]
    res_up, _held, _lag = _m1p_plan_fill_deploy(st2, plan, ctx, sess)
    dep_names = {d.char_id for d in iter_occupied_deployed(st2.deployed)
                 if d.char_id}
    assert res_up >= 1, '前提破帧缺口仍必须被补(R1-b 重 derive)'
    assert _TARGET_BENCH not in dep_names, '已离席的计划 pick 禁虚报'
    assert '景元' in dep_names, '补上件 = 重 derive 判定(注册表目标视图件)'
    assert sum(1 for _ in iter_occupied_deployed(st2.deployed)) \
        == len(_base_deployed()), '板满恢复'


def test_m1p_plan_fill_equivalence_locked_transition_domain() -> None:
    """等价锁·锁线转型域帧(T-279 验收设计锚;局 18 P2r4 形态固化,
    ADR-0640):锁线转型域(locked ∧ fp<1.00 ∧ 板满)+ 义务件黄泉带已
    达成弹性键(减益 2 档)⇒ 计划面(装配收窄键集)up pick = 黄泉,
    R1-a 直投后 m1p.up_names == 实际补部署名单(名字集断言,前提面 =
    victim 名一致 + 占用序稳定)。帧数据 = 局 18 卖出后账本形态的注册表
    真名重建(收窄键集 {减益,列车同行,星间旅人} 与账本 m1p 逐键一致;
    判据源 = T-279-交付报告 §二 + probe2/3 对照重放)。守卫移除红证:
    拔 R1-a 直投 + 拔 transition_domain 钉定(退域谓词现算 = 卖出后
    board_full 翻假 → 全量 8 键)⇒ 补上件变丹恒·腾荒 ≠ 计划 pick,本锁
    必红——分叉已亲证(no-pin up=[丹恒·腾荒] / pin up=[黄泉])。"""
    from types import SimpleNamespace as _NS2

    from sr_od.application.currency_war.data.cw_chars import CHARACTERS as _CH
    from sr_od.application.currency_war.kernel.cw_comps import get_comp as _get_comp
    from sr_od.application.currency_war.kernel.cw_state import (
        iter_occupied_deployed,
    )
    from sr_od.application.currency_war.sim.engine_p1 import (
        _m1p_plan_and_record,
        _m1p_plan_fill_deploy,
        m1p_swap_execute,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
        state_of as _state_of,
    )

    def _g18_bc(name: str, slot: int) -> BenchChar:
        ch = _CH[name]
        return BenchChar(slot=slot, char_id=name, star=1,
                         faction=(ch.factions[0] if ch.factions else '?'))

    # 局 18 P2r4:计划时点板 = 末态板 + victim(藿藿),cap 9 板满;
    # bench = 末态 bench(黄泉 = 本轮新购义务件,减益已达成 2 档)。
    kept = ['三月七', '椒丘', '海瑟音', '桑博', '姬子·启行', '千冶·刃',
            '飞霄', '艾丝妲']
    pre_board = kept + ['藿藿']
    bench_names = ['貊泽', '丹恒·腾荒', '黄泉', '银狼LV.999', '希儿',
                   '瓦尔特', '彦卿', '貊泽']
    board: dict[str, int] = {}
    for _n in pre_board:
        _c = _CH[_n]
        for _f in tuple(_c.factions or ()) + tuple(_c.flows or ()):
            board[_f] = board.get(_f, 0) + 1
    sess = _NS2()
    _st = _state_of(sess)
    _st.target_comp = _get_comp('列车同行')
    _st.transition_framework = ''
    _st.v3_intention = _NS2(locked_comp='列车同行', p1_pair=(),
                            phase='locked', transition_pair=())
    gs = GameState(gold=0, level=9, deploy_cap=9, plane=2, round_num=4,
                   board=board,
                   deployed=[_g18_bc(n, i + 1)
                             for i, n in enumerate(pre_board)],
                   bench=[_g18_bc(n, i + 1)
                          for i, n in enumerate(bench_names)])
    plan, rec, ctx = _m1p_plan_and_record(gs, sess)
    assert ctx is not None and ctx.transition_domain is True, (
        '锁前提:锁线转型域帧装配域事实 = True')
    assert ctx.target_factions == frozenset(
        {'减益', '列车同行', '星间旅人'}), (
        f'收窄键集与局 18 账本 m1p 逐键一致,实得 {sorted(ctx.target_factions)}')
    assert rec['up_names'] == ['黄泉'], (
        f'义务件(达成弹性键承载者)= 计划 pick,实得 {rec["up_names"]}')
    acts: list[dict] = []
    spend: dict = {'buys': {}, 'levelup': 0, 'refresh': 0, 'sell_income': 0}
    gs2, sold = m1p_swap_execute(gs, plan, acts=acts, spend=spend,
                                 pool=_RetPool())
    assert sold is True and plan.sell_names == ['飞霄']
    res_up, _held, _lag = _m1p_plan_fill_deploy(gs2, plan, ctx, sess)
    dep_names = {d.char_id for d in iter_occupied_deployed(gs2.deployed)
                 if d.char_id}
    assert res_up == 1 and '黄泉' in dep_names, '计划 pick 真上板'
    assert set(rec['up_names']) <= dep_names, (
        'm1p.up_names == 实际补部署名单(执行=计划等价,名字集断言)')
    assert sum(1 for _ in iter_occupied_deployed(gs2.deployed)) == 9, (
        '板满恢复 = 计划假想终态')


def test_mandate_carries_m1p_plan_payload() -> None:
    """mandate 计划载荷透传锁(T-279 R1;ADR-0640):m1p 发射帧置
    cw4_m1p_plan_pending = {sell, up, trans_domain, occ}(载荷仅作部署段
    核对,不改卖出仲裁权);非 m1p 帧恒 None(帧级同宿复位)。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    sess = _m1p_session(None, directed=True)
    out = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess, state=st)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1, '锁前提:m1p 发射帧'
    payload = state_of(sess).cw4_m1p_plan_pending
    assert payload == {'sell': [_VICTIM], 'up': [_TARGET_BENCH],
                       'trans_domain': False, 'occ': len(dep)}, payload
    # 非 m1p 帧(无方向 → 计划弃权 → 无发射):载荷恒 None
    sess_nd = _m1p_session(None, directed=False)
    out_nd = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess_nd,
                         state=st)
    assert not any(e.action.__class__.__name__ == 'RunDeploy' for e in out_nd)
    assert state_of(sess_nd).cw4_m1p_plan_pending is None


# ==================== mandate M1″ 消费方:seam 门关闭态 ====================

def _m1p_frame(*, deployed: list[BenchChar], bench: list[BenchChar],
               cap: int | None = 6) -> MandateFrame:
    return MandateFrame(gold=0, level=6, bench=bench, deployed=deployed,
                        deploy_cap=cap, node_type=None, stop_flag=False,
                        k_members=(), round_num=2)


#: 有向 comp(T-167 F1 夹具升级):无方向帧自 F1 起在 select_swap_plan
#: 弃权 no_direction,原「计划非空」夹具(target 视图空)须升级为定向
#: 才能测 seam 门/计划空分键的原辖面(ADR-0534 修订节用例预期更新)。
_DIRECTED_COMP = _NS(all_factions=('仙舟',), core_chars=('三月七',),
                     factions=('仙舟',), form_tiers={'仙舟': 2},
                     shared_chars=(), substitute_plan=None)


def _m1p_session(seam: bool | None, *, directed: bool = False) -> _NS:
    # 策略器字段经 state_of 载体(session 职责分离迁移后生产唯一读面);
    # last_owned_equips 是观察数据字段,仍在 session 上。
    s = _NS(last_owned_equips=None)
    st = state_of(s)
    st.cw4_counters = {}
    st.v3_intention = _NS(locked_comp='', p1_pair=(), phase='',
                          transition_pair=())
    st.target_comp = _DIRECTED_COMP if directed else None
    st.transition_framework = ''
    if seam is not None:
        st.cw4_m1p_seam_verified = seam
    return s


def test_m1p_consumer_seam_gate_keeps_emission_closed(
        monkeypatch) -> None:
    """seam 门两态锁(ADR-0530 决策4;开闸批修订:置位已兑付——两侧输入
    对齐证据 + fresh 生产写点接线两项前置义务完成后,run_mandate 入口
    唯一写点恒置 True)。回滚态(写点改 False)= 计划非空帧不发
    RunDeploy、仅计 m1p_input_seam_pending(fail-closed 显影);置位态
    (现役缺省)= 同帧形态发射(RunDeploy reason=m1_swap_redeploy +
    m1p_fired)。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    # 回滚态(唯一写点值源 M1P_SEAM_VERIFIED 写回 False = fail-closed
    # 显影态;monkeypatch 模拟回滚编辑,不碰生产模块)
    import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as _mandate_mod
    monkeypatch.setattr(_mandate_mod, 'M1P_SEAM_VERIFIED', False)
    sess = _m1p_session(None, directed=True)
    out = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess, state=st)
    assert state_of(sess).cw4_m1p_seam_verified is False
    assert not any(e.action.__class__.__name__ == 'RunDeploy' for e in out)
    assert state_of(sess).cw4_counters.get('m1p_input_seam_pending') == 1
    assert 'm1p_fired' not in state_of(sess).cw4_counters
    # 置位态(现役缺省:入口写点自置 True,无需外部注入)
    monkeypatch.setattr(_mandate_mod, 'M1P_SEAM_VERIFIED', True)
    sess2 = _m1p_session(None, directed=True)
    out2 = run_mandate(_m1p_frame(deployed=dep, bench=bench), sess2,
                       state=st)
    assert state_of(sess2).cw4_m1p_seam_verified is True   # 入口唯一写点自置位
    fired = [e for e in out2 if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert state_of(sess2).cw4_counters.get('m1p_fired') == 1
    assert 'm1p_input_seam_pending' not in state_of(sess2).cw4_counters


def test_m1p_consumer_counts_plan_empty_and_cap_unreadable() -> None:
    """消费方分键锁:计划空帧 → m1p_plan_empty;cap 缺读帧 →
    m1p_cap_unreadable(零静默,判读可归因)。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    sess = _m1p_session(None, directed=True)
    # cap 满帧但上序空(bench 候选与在场件同名,M1/M1′ 因 vacancy=0 不发,
    # M1″ 计划空分键显影)
    dep_dup = [_bc(_VICTIM, 1), _bc('青雀', 2), _bc('停云', 3),
               _bc('藿藿', 4), _bc('爻光', 5), _bc(_TARGET_BENCH, 6)]
    st_dup = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                       deployed=list(dep_dup), bench=list(bench))
    run_mandate(_m1p_frame(deployed=dep_dup, bench=bench), sess,
                state=st_dup)
    assert state_of(sess).cw4_counters.get('m1p_plan_empty') == 1
    # cap 缺读帧:frame.deploy_cap=None → 弃权键
    sess2 = _m1p_session(None, directed=True)
    run_mandate(_m1p_frame(deployed=dep, bench=bench, cap=None), sess2,
                state=st)
    assert state_of(sess2).cw4_counters.get('m1p_cap_unreadable') == 1


def test_m1p_consumer_input_missing_not_mixed_into_plan_empty() -> None:
    """m1p_input_missing 分键锁(落地审低④:供给缺失 ≠ 真计划空,禁混桶
    ——「不冒名拒因」纪律,can_deploy_single 的 unannotated 先例同型):
    装配不可得(state 与 cap 双缺 ⇒ 装配函数返回 None)帧计入
    m1p_input_missing,m1p_plan_empty 不计数。"""
    dep, bench = _base_deployed(), [_bc(_TARGET_BENCH)]
    sess = _m1p_session(None)
    run_mandate(_m1p_frame(deployed=dep, bench=bench, cap=None), sess,
                state=None)
    assert state_of(sess).cw4_counters.get('m1p_input_missing') == 1
    assert 'm1p_plan_empty' not in state_of(sess).cw4_counters
    assert 'm1p_cap_unreadable' not in state_of(sess).cw4_counters


# ==================== 执行侧卖出臂:义务集∪新鲜度排除接线 ====================

def test_swap_sell_exclusion_single_source_verdict() -> None:
    """执行侧单一判定锁(落地审阻断 #1 修复;ADR-0530 决策3):
    `swap_sell_exclusion_reason` = 发射面谓词与执行侧卖出臂共用的唯一
    逐件判定——买面义务集成员 → buy_membership;轮内新鲜买入件 →
    fresh_buy;义务集缺读 → membership_unreadable(执行面 fail-closed =
    全候选禁卖);target 成员 → target_keep;非 target 非 fenced 普通件
    → ''。执行侧 `_sell_offtarget_deployed` 逐候选消费本判定(禁第二份
    实现),P60 卖义务件↔买回环在执行路径同受保护。
    旧语义勘误(转型臂批):本函数已由「仅义务集∪新鲜度排除」扩展为
    per-piece 完整资格判定(ADR-0534 §3 同位
    扩展,offtarget_sell_allowed 经本函数参数化接入)——「青雀(target
    成员)返 ''」的旧断言随扩展失效,target_keep 拒因取代;'' 样本改用
    注册表直调的非 target 非 fenced 件(花火)。"""
    ctx = _base_ctx(deployed=[], bench=[],
                    membership=frozenset({'艾丝妲'}), fresh=frozenset({_VICTIM}))
    assert swap_sell_exclusion_reason('艾丝妲', ctx) == 'buy_membership'
    assert swap_sell_exclusion_reason(_VICTIM, ctx) == 'fresh_buy'
    assert swap_sell_exclusion_reason('青雀', ctx) == 'target_keep'
    assert swap_sell_exclusion_reason('花火', ctx) == ''
    ctx_unread = _base_ctx(deployed=[], bench=[], membership=None)
    assert swap_sell_exclusion_reason(_VICTIM, ctx_unread) \
        == 'membership_unreadable'
    assert swap_sell_exclusion_reason(_VICTIM, None) == ''
    assert swap_sell_exclusion_reason('', ctx) == ''


# ==================== F1 换阵可兑现谓词锁(T-167)====================

def test_swap_plan_no_direction_frame_abstains() -> None:
    """三合取①锁(事故同态帧):target 视图空(target_comp=None 链)
    → 弃权 no_direction + plan 级拒因显影——M1″ 幻影部署的发射面根除位
    (run_20260908_210431:无方向态发射 53 次执行 0 次的接缝断裂本体)。"""
    reasons: dict[str, str] = {}
    plan = select_swap_plan(_base_ctx(deployed=_base_deployed(),
                                      bench=[_bc(_TARGET_BENCH)]),
                            reasons_out=reasons)
    # _base_ctx 目标视图 = _TF 非空,须显式造无方向帧
    ctx_nd = SwapPlanContext(
        target_factions=frozenset(), target_cores=frozenset(),
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=frozenset(),
        fresh_buys=frozenset(), board={}, deployed=_base_deployed(),
        bench=[_bc(_TARGET_BENCH)], cap=6)
    plan = select_swap_plan(ctx_nd, reasons_out=reasons)
    assert plan.abstain == 'no_direction' and not plan.nonempty
    assert reasons.get('(plan)') == 'no_direction'
    # 弃权键闭集登记(kernel SWAP_REALIZABLE_WHY 单一源)
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        SWAP_REALIZABLE_WHY,
    )
    assert 'no_direction' in SWAP_REALIZABLE_WHY


def test_swap_plan_no_bench_target_frame_abstains() -> None:
    """三合取②锁(F-1① 幻影形态根除):有向帧但 bench 无目标视图件
    (旧 base/formed 臂「非目标件填空上序」= 执行面必然空转)→ 弃权
    no_bench_target——「发射→执行 no-op」变「弃权→空批出战」(F-2
    如实申报的行为变化,ADR-0534 修订节)。"""
    ctx_nbt = SwapPlanContext(
        target_factions=_TF, target_cores=_CORES, fw_carry=frozenset(),
        locked_factions=frozenset(), protect_names=frozenset(),
        membership=frozenset(), fresh_buys=frozenset(), board={},
        deployed=_base_deployed(),   # 板满 + 黑塔可卖 victim 在场
        bench=[_bc(_VICTIM)],        # bench 无目标视图件(唯一候选即 victim)
        cap=6)
    plan = select_swap_plan(ctx_nbt)
    assert plan.abstain == 'no_bench_target' and not plan.nonempty


def test_swap_plan_no_sellable_victim_keeps_per_piece_reasons() -> None:
    """三合取③ = victim 扫描自然承载锁(ADR-0534「修订(T-167)」节的显影保留面):
    有向帧 ∧ bench 有目标件 ∧ 板上无可卖 off-target(全 fenced 且臂关)
    → 计划空但逐件拒因 fenced_arm_closed 保留显影——合取③不预判成
    plan 级单键,拒因显影不丢失。"""
    second = _pick_fenced_offtarget({_VICTIM, '艾丝妲'})
    deployed = [_bc('艾丝妲', 1), _bc(second, 2),
                _bc('青雀', 3), _bc('停云', 4), _bc('藿藿', 5), _bc('爻光', 6)]
    plan = select_swap_plan(_base_ctx(deployed=deployed,
                                      bench=[_bc(_TARGET_BENCH)],
                                      fenced=False))
    assert not plan.nonempty
    assert plan.reasons.get('艾丝妲') == 'fenced_arm_closed'
    assert plan.reasons.get(second) == 'fenced_arm_closed'


def test_swap_realizable_why_closed_set() -> None:
    """swap_realizable 拒因闭集锁(F-8:plan 级弃权键闭集,发射面分键
    消费同一闭集):三合取各假帧的 why 值一一对应;真帧返 ''。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        swap_realizable,
    )
    ok_ctx = _base_ctx(deployed=_base_deployed(),
                       bench=[_bc(_TARGET_BENCH)])
    assert swap_realizable(ok_ctx) == (True, '')
    assert swap_realizable(None)[0] is False, 'ctx None fail-closed'
    nbt_ctx = _base_ctx(deployed=_base_deployed(), bench=[_bc(_VICTIM)])
    assert swap_realizable(nbt_ctx) == (False, 'no_bench_target')
    # 无可卖 off-target 帧构造 = 全 fenced 臂关帧(注册表直调取 fenced
    # off-target 样本,与其余 target 件组成板面;构造同 fenced_arm_closed 锁)
    second = _pick_fenced_offtarget({_VICTIM, '艾丝妲'})
    nso_ctx = _base_ctx(
        deployed=[_bc('艾丝妲', 1), _bc(second, 2),
                  _bc('青雀', 3), _bc('停云', 4), _bc('藿藿', 5), _bc('爻光', 6)],
        bench=[_bc(_TARGET_BENCH)], fenced=False)
    assert swap_realizable(nso_ctx)[1] == 'no_sellable_offtarget'


def test_target_view_char_single_source_includes_fw_carry() -> None:
    """fw_carry 口径收口锁(F-1③,择 kernel 含):单件判定单一源 =
    target_view_char_is(fw_carry 命中即目标视图件),发射面 _bench_is_
    target 与 kernel bench_target_count 同吃;执行面旧局部 _is_tgt_char
    (不含 fw_carry)拆除(源级断言)。"""
    from sr_od.application.currency_war.kernel.cw_deploy_logic import (
        bench_target_count,
        target_view_char_is,
    )
    ctx = _base_ctx(deployed=[], bench=[])
    assert target_view_char_is(ctx, _TARGET_BENCH), (
        '阵营交集件 = 目标视图件(基本腿)')
    assert target_view_char_is(ctx, '三月七'), 'core 件 = 目标视图件'
    ctx_fw = SwapPlanContext(
        target_factions=_TF, target_cores=_CORES,
        fw_carry=frozenset({'花火'}),   # 花火 bonds∉TF 的 fw_carry 样本
        locked_factions=frozenset(), protect_names=frozenset(),
        membership=frozenset(), fresh_buys=frozenset(), board={},
        deployed=[], bench=[], cap=6)
    ch = CHARACTERS['花火']
    assert not (set(ch.factions) | set(ch.flows)) & _TF, '锁前提:样本∉视图'
    assert target_view_char_is(ctx_fw, '花火'), 'fw_carry 命中即目标视图件'
    assert bench_target_count(ctx_fw, bench=[_bc('花火')]) == 1, (
        'bench_target_count 计 fw_carry 件(执行面 max_sell 同吃)')
    import inspect

    from sr_od.application.currency_war.operations.cw_op import cw_op_deploy
    src = inspect.getsource(cw_op_deploy)
    assert 'def _is_tgt_char' not in src, (
        '执行面局部第二份口径必须拆除(fw_carry 收口后禁双实现)')
    assert 'bench_target_count(' in src and 'swap_realizable(' in src, (
        '执行面两门必须消费 kernel 合取支(F1 单一源)')


def test_m1p_no_direction_incident_frame_no_emission(monkeypatch) -> None:
    """F1 核心单帧锁(诊断验收1修订):事故同态帧(P2r6、target 视图空、
    板满 8/8、bench 有件、gold=31)闩闭帧 → 发射序列空(entry ⑥ StartBattle
    的前件,空批出战出口恢复可达)∧ m1p_no_direction plan 级弃权键显影
    (F-8)∧ 无 RunDeploy。"""
    sess = _m1p_session(None)
    # 板满 8/8:注册表真名(无方向帧在门①即弃权,件名羁绊不入判定)
    _full = [_bc('艾丝妲', 1), _bc('黑塔', 2), _bc('椒丘', 3), _bc('青雀', 4),
             _bc('停云', 5), _bc('藿藿', 6), _bc('爻光', 7), _bc('花火', 8)]
    st = GameState(gold=31, level=8, plane=2, round_num=6, board={},
                   deployed=_full,
                   bench=[_bc(_VICTIM, 1), _bc('花火', 2)])
    st2 = state_of(sess)
    st2.cw4_shopped_phase = (2, 6)   # 闩闭(事故的部署帧相位)
    out = run_mandate(
        MandateFrame(gold=31, level=8, bench=[b for b in st.bench if b],
                     deployed=[d for d in st.deployed if d], deploy_cap=8,
                     node_type='battle', stop_flag=False, k_members=(),
                     round_num=6),
        sess, state=st)
    assert not any(e.action.__class__.__name__ == 'RunDeploy' for e in out), (
        f'闩闭帧不得再发射幻影 RunDeploy:{[e.reason for e in out]}')
    assert out == [], f'闩闭帧序列空(entry ⑥ 出战可达),实得 {[e.reason for e in out]}'
    assert st2.cw4_counters.get('m1p_no_direction') == 1, (
        'no_direction plan 级弃权键必须显影(F-8 层位)')


# ==================== 开闸批:fresh 生产写点接线 ====================

def test_shop_buy_emission_writes_fresh_buys() -> None:
    """fresh 生产写点接线锁(ADR-0530 开闸批;开闸核对批需接线清单①):
    shop 买入发射位(_emit_buy,全部 BuyCard 返回位单一收口)在买入动作
    被采纳(单动作契约:return 即被决策循环无条件执行)时,逐名写入
    kernel ExecState.cw4_swap_fresh_buys 单一载体——发射位写入 → fresh_buys_of
    同帧可读;执行侧卖出臂经 swap_sell_exclusion_reason 消费同一载体,
    生产 fresh_buy 排除自此全量生效(P60 防抖在执行路径复活)。"""
    from sr_od.application.currency_war.kernel.cw_comps import (
        COMP_LIBRARY,
        get_comp,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        BuyCard,
        ShopCard,
    )
    from sr_od.application.currency_war.kernel.cw_strategy_session import (
        StrategySession,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        proof as _proof,
    )
    from sr_od.application.currency_war.strategies.impl.mandate_v1.shop import (
        decide_shop_action,
    )
    comp = get_comp(next(c.name for c in COMP_LIBRARY
                         if getattr(c, 'core_chars', None)))
    m = list(comp.core_chars)[0]
    st = GameState(gold=30, level=3, round_num=2, plane=1)
    st.shop = [ShopCard(x=100, name=m, cost=3, star=1)]
    sess = StrategySession()
    state_of(sess).cw4_counters = {}
    state_of(sess).target_comp = comp
    state_of(sess).cw4_line_state = _proof.LineState()
    act = decide_shop_action(st, sess, _NS(ev_arm='full'))
    assert isinstance(act, BuyCard) and act.reason == 'm2_line_member'
    assert fresh_buys_of(sess, st) == frozenset({m})


