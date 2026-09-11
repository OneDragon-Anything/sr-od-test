# 转型臂(M1″ swap 谓词触发域扩展)单帧锁——锁线后 fp<1.00 板满帧的
# bench→板 换血通道:病灶回放/守恒门/合成素材守卫/1★ 守卫/卖后底线/
# 双臂互斥/胜出不提权/执行侧同函数/发射分键/守恒门辖域不变式。
# 语义出处:ADR-0534(docs/develop/currency_war/decisions/
# 0534-swap-transition-arm.md)。病灶帧 = 实机「锁 列车同行 →
# 三月七 2★ + 姬子·启行 bench 成型,deployed 恒 6 过渡件、3 备战轮未
# 上板)。锁的存在性纪律:每条锁 docstring 引出处;守卫均为「移除即红」
# 属性(删守卫代码 = 本文件对应锁必红)。
# CUT6 瘦身批(2026-09-09):回滚常量翻臂/胜出序让渡退化/成型臂与
# pending 透传分键变体/守恒门逐件参数化(病灶回放锁已断言同事实)砍除;
# 保留核清单 = reports/_cluster_CUT6.md。
# 收缩注记(CUT9 二次收缩:原 11 测试→6 测试;同分支变体砍,git 可复活):
# - 留:病灶帧回放主锁(engines_guard 守恒门×2 + 胜出序 + arm 标注
#   联合锚)/ fp 缺读弃权(fail-closed)/ 双臂 fp 单值互斥 / 合成素材
#   守卫(判定函数级+计划面双锁)/ 执行侧发射⇔执行同函数同判(未锁域
#   fenced_arm_closed 断言在彼)/ mandate 发射分键消费面;
# - 砍:未锁域 W209 对照(执行侧锁同断言面)/ 胜出序首位 victim 变体 /
#   1★ star_guard(守卫族第二件,守卫代表由 merge_material 承载)/
#   卖后上序底线 post_sell_offline / 守恒门辖域不变式(SWAP_GUARD_
#   SYSTEMS ⊇ DEPLOY_FENCE 注册表直核)。
from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    select_swap_plan,
    swap_sell_exclusion_reason,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_TGT_FACS = frozenset({'列车同行'})
_TGT_CORE = frozenset({'三月七'})


def _bc(name: str, slot: int = 1, star: int = 1) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name, star=star,
                     faction=(ch.factions[0] if ch.factions else '?'))


def _lesion_frame_deployed() -> list[BenchChar]:
    """病灶帧板面(注册表直核):艾丝妲/椒丘 = DOT flow(持续
    伤害 ×2);爻光/藿藿/忘归人/符玄 = 仙舟 ×4;全 1★、两两异名。"""
    return [_bc('艾丝妲', 1), _bc('椒丘', 2), _bc('爻光', 3),
            _bc('藿藿', 4), _bc('忘归人', 5), _bc('符玄', 6)]


def _locked_ctx(*, deployed: list[BenchChar], bench: list[BenchChar],
                fp: float | None = 0.0, locked: bool = True,
                fenced: bool = False, cap: int | None = 6,
                locked_factions: frozenset[str] = frozenset(),
                fresh: frozenset[str] = frozenset(),
                membership: frozenset[str] | None = frozenset(),
                ) -> SwapPlanContext:
    """锁线转型帧上下文(板满 6≥6;fp<1.00 = 转型期)。"""
    return SwapPlanContext(
        target_factions=_TGT_FACS, target_cores=_TGT_CORE,
        fw_carry=frozenset(), locked_factions=locked_factions,
        protect_names=frozenset(), membership=membership,
        fresh_buys=fresh, board={}, deployed=deployed, bench=bench,
        cap=cap, fenced_on=fenced, fp=fp, locked=locked, board_full=True)


# ============ 病灶帧回放:卖爻光(+1金)→ 上三月七 2★ ============

def test_lesion_frame_replay_transition_swap_fires() -> None:
    """病灶帧回放锁(ADR-0534 §背景):locked ∧ fp=0<1.00 ∧ 板满 6≥6;
    守恒门逐件:艾丝妲/椒丘 DOT 2→1 拒(engines_guard ×2)、
    爻光/藿藿/忘归人/符玄 仙舟 4→3 过(tier 3 卖后仍达成);皆 1★/
    非义务/非新鲜 ⇒ 胜出 = 现行序首个可成交者爻光,卖序 [爻光],
    上序 = 三月七 2★,arm='transition'。现网旧代码 = fenced_arm_closed
    ×6 计划空——本锁红 = 转型臂回归。"""
    bench = [_bc('三月七', 1, star=2)]
    plan = select_swap_plan(_locked_ctx(deployed=_lesion_frame_deployed(),
                                        bench=bench))
    assert plan.nonempty, plan
    assert plan.sell_names == ['爻光']
    assert {bench[i].char_id for i in plan.up_bench} == {'三月七'}
    assert plan.arm == 'transition'
    assert plan.reasons.get('艾丝妲') == 'engines_guard'
    assert plan.reasons.get('椒丘') == 'engines_guard'


# (CUT9 收缩:原 test_transition_arm_keeps_w209_in_unlocked_domain 删
#  (2026-09-09)——未锁域 fenced_arm_closed 拒面由执行侧同函数锁的
#  ctx_unlocked 腿承载,同断言面。)


def test_fp_unreadable_abstains_transition_arm() -> None:
    """fp 缺读弃权锁(ADR-0534 §1:fp=None ⇒ fp_unreadable,两臂同
    fail-closed):fp 不可读的锁线板满帧,转型臂关且拒因显影
    fp_unreadable(不冒名 fenced_arm_closed)。"""
    bench = [_bc('三月七', 1, star=2)]
    plan = select_swap_plan(_locked_ctx(deployed=_lesion_frame_deployed(),
                                        bench=bench, fp=None))
    assert not plan.nonempty
    assert plan.reasons.get('爻光') == 'fp_unreadable'


# ============ 双臂 fp 单值互斥 + 同帧双资格胜出序(ADR-0534 §5) ============

def test_formed_arm_wins_when_fp_above_100() -> None:
    """双臂互斥锁(ADR-0534 §5):fp≥1.00 帧 fenced_on=True,
    fenced victim 经成型臂放行,arm='formed'(fp 单值互斥,同帧不可能
    'transition');成型臂无守恒门(守恒门是转型臂资格语义,ADR-0534 §2
    辖域绑定转型臂),现行序首位 fenced victim 直接可成交。"""
    bench = [_bc('三月七', 1, star=2)]
    plan = select_swap_plan(_locked_ctx(deployed=_lesion_frame_deployed(),
                                        bench=bench, fp=1.0, fenced=True))
    assert plan.nonempty
    assert plan.sell_names == ['艾丝妲']
    assert plan.arm == 'formed'


# (CUT9 收缩:原 test_base_victim_wins_over_transition_when_first 删
#  (2026-09-09)——现行序首位 victim 胜出、转型 victim 不提权的胜出序
#  面,病灶回放主锁已断言「胜出 = 现行序首个可成交者」,本测为序数据
#  变体,git 可复活。)


# ============ 逐件守卫(守卫移除即红) ============

def test_merge_material_guard_blocks_unfinished_pair() -> None:
    """合成素材守卫锁(ADR-0534 §2:触发态 = 含自身计数 2 未完态):victim 含
    自身全场域同名同星计数 = 2(2/3 未完态,合成恒律派生零自由参数)
    ⇒ 拒 merge_material_guard——卖 v 使合成进度 2/3 退 1/3。判定面锁
    在单一判定函数(守卫移除即红);计划面锁行为:爻光被拒后胜出者
    后移(藿藿,arm 仍 transition)。注:拒因按名键,板/备同名时
    post_sell_held 覆写是既知键面限制,故守卫语义锁在函数级。"""
    bench = [_bc('三月七', 1, star=2), _bc('爻光', 2)]
    ctx = _locked_ctx(deployed=_lesion_frame_deployed(), bench=bench)
    assert swap_sell_exclusion_reason('爻光', ctx) == 'merge_material_guard'
    # 对照:计数 = 1(无副本)不触发守卫(ADR-0534 §9:计数 <2 帧
    # 概率残差不在辖域,fail 向另计)
    plan = select_swap_plan(_locked_ctx(deployed=_lesion_frame_deployed(),
                                        bench=[_bc('三月七', 1, star=2)]))
    assert plan.sell_names == ['爻光']
    # 守卫帧:爻光不可成交,胜出后移
    plan2 = select_swap_plan(ctx)
    assert plan2.sell_names == ['藿藿']
    assert plan2.arm == 'transition'


# (CUT9 收缩:原 test_star_guard_blocks_2star_victim(1★ 限卖守卫)与
#  test_post_sell_offline_blocks_no_target_up(卖后上序底线)删
#  (2026-09-09)——守卫族代表行由 merge_material_guard 承载(判定函数
#  级 + 计划面双锁),star/post_sell 为守卫族另外两件的数据变体锁,
#  git 可复活。)


# ============ 执行侧逐件放行(ADR-0534 §3/§4:发射⇔执行同函数同判) ============

def test_execution_side_per_piece_release_via_same_function() -> None:
    """执行侧放行验点锁(ADR-0534 §背景/§8 对齐增行 17 断言):
    爻光经单一判定函数——fenced_on=False 但转型臂资格 True ⇒ 返回 ''
    (放行卖出);同函数同参下发射侧判合格 ⇒ 执行侧必同判(禁标量
    fenced_on 退化喂入)。执行侧现读域经 star/bench/deployed 参数喂入。"""
    deployed = _lesion_frame_deployed()
    ctx = _locked_ctx(deployed=deployed, bench=[_bc('三月七', 1, star=2)])
    assert swap_sell_exclusion_reason('爻光', ctx) == ''
    # 现读域覆盖喂入(执行侧 SIFT 形态):同判
    assert swap_sell_exclusion_reason('爻光', ctx, star=1,
                                      bench=[], deployed=deployed) == ''
    # 未锁帧同函数 = fenced_arm_closed(W209 保持)
    ctx_unlocked = _locked_ctx(deployed=deployed,
                               bench=[_bc('三月七', 1, star=2)],
                               locked=False)
    assert swap_sell_exclusion_reason('爻光', ctx_unlocked) \
        == 'fenced_arm_closed'
    # 合成素材守卫在现读域覆盖下同样生效(bench 域含同名同星副本)
    assert swap_sell_exclusion_reason('爻光', ctx, star=1,
                                      bench=[_bc('爻光', 2)],
                                      deployed=deployed) \
        == 'merge_material_guard'


# ============ mandate 消费面分键(plan.arm → 触发键) ============

def _m1p_frame(deployed: list[BenchChar], bench: list[BenchChar]):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        MandateFrame,
    )
    return MandateFrame(gold=0, level=6, bench=bench, deployed=deployed,
                        deploy_cap=6, node_type=None, stop_flag=False,
                        k_members=(), round_num=2)


def test_mandate_counts_transition_trigger_and_reject_keys(
        monkeypatch) -> None:
    """发射分键锁(ADR-0534 §7 键集):转型帧发射 ⇒ m1p_fired +
    swap_arm_transition_trigger(plan.arm 消费面分键);守恒拒帧 ⇒
    engines_guard 分键显影。装配侧意向供给(monkeypatch 桩化,零真实
    派生依赖):committed=True + 义务集 = {'三月七'}——T-127 执行条件
    发射门(ADR-0590 决策4)要求压席锁线成员存在,bench 三月七经义务
    桩入压席面(面板 board={} 列车 0<2,部署推进 form = 档关键件,
    保守形态放行);deployed 六件非成员,victim 资格面不受桩影响。"""
    import sr_od.application.currency_war.kernel.cw_intention as _int_mod
    import sr_od.application.currency_war.strategies.impl.mandate_v1.mandate as _mandate_mod
    from sr_od.application.currency_war.kernel.cw_state import GameState
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        run_mandate,
    )
    monkeypatch.setattr(_mandate_mod, 'M1P_SEAM_VERIFIED', True)
    monkeypatch.setattr(_int_mod, 'committed_from',
                        lambda session, state=None: True)
    monkeypatch.setattr(_int_mod, 'locked_buy_membership',
                        lambda ist, cap_hold=None: frozenset({'三月七'}))
    comp = _NS(all_factions=('列车同行',), core_chars=('三月七',),
               factions=('列车同行',), form_tiers={'列车同行': 2},
               shared_chars=(), substitute_plan=None)
    # 策略器字段经 state_of 载体(session 职责分离迁移后生产唯一读面);
    # last_owned_equips 是观察数据字段,仍在 session 上。
    sess = _NS(last_owned_equips=None)
    _st = state_of(sess)
    _st.cw4_counters = {}
    _st.v3_intention = _NS(locked_comp='列车同行', p1_pair=(),
                           phase='locked', transition_pair=())
    _st.target_comp = comp
    _st.transition_framework = ''
    dep, bench = _lesion_frame_deployed(), [_bc('三月七', 1, star=2)]
    st = GameState(gold=0, level=6, plane=1, round_num=2, board={},
                   deployed=list(dep), bench=list(bench))
    out = run_mandate(_m1p_frame(dep, bench), sess, state=st)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert state_of(sess).cw4_counters.get('m1p_fired') == 1
    assert state_of(sess).cw4_counters.get('swap_arm_transition_trigger') == 1
    assert 'swap_arm_formed_trigger' not in state_of(sess).cw4_counters
    assert state_of(sess).cw4_counters.get('engines_guard') == 1   # 帧级显影
    # 执行侧透传(39 跳登记:执行侧卖出 m1p 驱动不可辨):发射帧 pending
    # = plan.arm,消费点 = CwOpDeploy.deploy 卖出臂读后即清
    assert state_of(sess).cw4_m1p_arm_pending == 'transition'


# (CUT9 收缩:原 test_guard_set_covers_deploy_fence 删(2026-09-09)
#  ——SWAP_GUARD_SYSTEMS ⊇ DEPLOY_FENCE 注册表直核不变式,守卫族行为
#  面已由上方锁承载,注册表内容回归窗口放宽,git 可复活。)

