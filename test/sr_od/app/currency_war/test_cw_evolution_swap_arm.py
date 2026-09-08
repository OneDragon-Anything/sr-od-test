# 演进降级换血臂准入常驻锁(ADR-0614;T-21 wait 行联动「新增发射位准入
# 常驻锁:人肉清点表变机器不变量」)。
#
# 被锁能力 = 换血机器的演进降级臂:锁线转型域 ∧ 板满 ∧ bench 有在册
# 线件待上(准入三元,谓词单一源 = evolution_swap_arm_trigger)时,
# swap_sell_exclusion_reason 的 star_guard 对可读星级 >1 的 victim
# 让位(ADR-0382 分级降级换血语义接入换血机器的参数化面)。语义出处:
# - docs/develop/currency_war/decisions/0614-evolution-grade-swap-arm.md
#   (本批 ADR:修向原文/准入三元/卖出代价轴重推/P61 辖域注);
# - docs/develop/currency_war/decisions/0382-engine-completion-graded-undeploy.md
#   (分级保护:G0/G1 可动、G2 已成型引擎/pair/希儿系恒不可动;本臂
#   不新增资格语义,只放开既有 1★ 限制、其余守卫全保留)。
# 锁的存在性纪律:每条锁 docstring 引出处;守卫均为「移除即红」属性。
# 变异打红记录(实施批自证):摘除 star_guard 武装旁路 → 本文件 4 条
# 锁红(主锁/执行侧同函数/守卫保留/端到端;触发器矩阵+装配级 2 锁
# 不受牵连 = 选择性正确),恢复后全绿。
from types import SimpleNamespace as _NS

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    assemble_swap_plan_inputs,
    evolution_swap_arm_trigger,
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


def _all_two_star_deployed() -> list[BenchChar]:
    """板满 6 件全 2★ 的锁线转型帧板面(注册表直核):艾丝妲/椒丘 = DOT
    ×2(达成档,卖出掉档→engines_guard)、爻光/藿藿/忘归人/符玄 = 仙舟
    ×4(超档,卖 1 留 3 达成不变)——全 2★ ⇒ 未武装帧 star_guard 全拒。"""
    return [_bc('艾丝妲', 1, star=2), _bc('椒丘', 2, star=2),
            _bc('爻光', 3, star=2), _bc('藿藿', 4, star=2),
            _bc('忘归人', 5, star=2), _bc('符玄', 6, star=2)]


def _ctx(*, deployed: list[BenchChar], bench: list[BenchChar],
         armed: bool = True, fp: float | None = 0.0, locked: bool = True,
         board_full: bool = True, membership: frozenset[str] | None
         = frozenset({'三月七'}),
         fresh: frozenset[str] = frozenset(),
         ) -> SwapPlanContext:
    """锁线转型帧上下文(板满 6≥6;armed 显式传,缺省=武装)。"""
    return SwapPlanContext(
        target_factions=_TGT_FACS, target_cores=_TGT_CORE,
        fw_carry=frozenset(), locked_factions=frozenset(),
        protect_names=frozenset(), membership=membership,
        fresh_buys=fresh, board={}, deployed=deployed, bench=bench,
        cap=6, fenced_on=False, fp=fp, locked=locked,
        board_full=board_full, evolution_swap_armed=armed)


# ============ 主行为锁(变异打红目标:摘除武装旁路 → 本条红) ============

def test_armed_two_star_victim_swap_fires() -> None:
    """主锁(准入常驻):板满 6≥6 ∧ 全 2★ 板面 ∧ bench 三月七 2★ 在册
    待上 ⇒ 演进降级臂武装,star_guard 让位,计划非空:胜出 victim =
    爻光 2★(让渡序:结构贡献全 0 → 星级桶同级 → 板槽位序首个),
    arm='transition',上序 = 三月七(post_sell 底线 = up ∩ target ≠ ∅)。
    未武装对照帧同板面 star_guard ×4 计划空(仙舟×4 超档 2★;
    DOT×2 掉档 engines_guard)。变异:摘除 swap_sell_exclusion_reason
    的武装旁路 → 本锁红(计划空)。"""
    bench = [_bc('三月七', 1, star=2)]
    dep = _all_two_star_deployed()
    plan = select_swap_plan(_ctx(deployed=dep, bench=bench))
    assert plan.nonempty, plan
    assert plan.sell_names == ['爻光']
    assert {bench[i].char_id for i in plan.up_bench} == {'三月七'}
    assert plan.arm == 'transition'
    # 未武装(臂关)= 现网旧行为:2★ 全拒,计划空
    plan_off = select_swap_plan(_ctx(deployed=dep, bench=bench, armed=False))
    assert not plan_off.nonempty
    for name in ('爻光', '藿藿', '忘归人', '符玄'):
        assert plan_off.reasons.get(name) == 'star_guard', name


def test_execution_side_two_star_release_same_function() -> None:
    """执行侧放行同函数锁(ADR-0534 §3 发射⇔执行同判;ADR-0614 执行侧
    SIFT 域覆写形态):武装 ctx 下,爻光 2★ 经现读域覆盖参(star=/
    bench=/deployed=)判定放行 '';未武装同参 = star_guard。执行侧
    cw_op_deploy 卖出臂消费同一函数,武装位覆写后两域同值。"""
    dep = _all_two_star_deployed()
    bench = [_bc('三月七', 1, star=2)]
    assert swap_sell_exclusion_reason('爻光', _ctx(deployed=dep, bench=bench),
                                      star=2, bench=bench, deployed=dep) == ''
    assert swap_sell_exclusion_reason(
        '爻光', _ctx(deployed=dep, bench=bench, armed=False),
        star=2, bench=bench, deployed=dep) == 'star_guard'


# ============ 准入三元逐腿矩阵(谓词单一源 = evolution_swap_arm_trigger) ============

def test_arm_trigger_legs_matrix() -> None:
    """准入三元逐腿锁(T-21 机器不变量):任一腿缺失 ⇒ 臂关——
    未锁 / fp 缺读 / fp≥1.00(线已成型无完成缺口)/ 板不满 /
    membership 缺读(None)/ 未锁空义务集 / bench 无在册线件;
    全腿齐 ⇒ True。fail-closed 方向与转型臂 fp_unreadable 同构
    (ADR-0534 §1)。"""
    bench = [_bc('三月七', 1, star=2)]
    member = frozenset({'三月七'})
    assert evolution_swap_arm_trigger(member, bench, locked=True,
                                      fp=0.5, board_full=True) is True
    assert evolution_swap_arm_trigger(member, bench, locked=False,
                                      fp=0.5, board_full=True) is False
    assert evolution_swap_arm_trigger(member, bench, locked=True,
                                      fp=None, board_full=True) is False
    assert evolution_swap_arm_trigger(member, bench, locked=True,
                                      fp=1.0, board_full=True) is False
    assert evolution_swap_arm_trigger(member, bench, locked=True,
                                      fp=0.5, board_full=False) is False
    assert evolution_swap_arm_trigger(None, bench, locked=True,
                                      fp=0.5, board_full=True) is False
    assert evolution_swap_arm_trigger(frozenset(), bench, locked=True,
                                      fp=0.5, board_full=True) is False
    junk = [_bc('青雀', 1), _bc('停云', 2)]
    assert evolution_swap_arm_trigger(member, junk, locked=True,
                                      fp=0.5, board_full=True) is False


def test_assemble_computes_arm_and_leg_removals(monkeypatch) -> None:
    """装配级计算锁(发射面/sim 面同函数装配同值):合成会话直调
    assemble_swap_plan_inputs——武装帧(锁线 ∧ fp<1 ∧ 板满 ∧ bench
    在册)⇒ ctx.evolution_swap_armed True;bench 在册件移除 ⇒ False;
    板面成型(fp≥1.00)⇒ False。装配源 = 同一函数,禁消费面第二份
    触发派生(执行侧 bench 域分轨覆写 = cw_op_deploy 现读重算,
    helper 单一源不变)。"""
    import sr_od.application.currency_war.kernel.cw_intention as _int_mod
    monkeypatch.setattr(_int_mod, 'committed_from',
                        lambda session, state=None: True)
    monkeypatch.setattr(_int_mod, 'locked_buy_membership',
                        lambda ist: frozenset({'三月七'}))
    from sr_od.application.currency_war.kernel.cw_state import GameState
    comp = _NS(all_factions=('列车同行',), core_chars=('三月七',),
               factions=('列车同行',), form_tiers={'列车同行': 2},
               shared_chars=(), substitute_plan=None)
    sess = _NS(strategy_state=_NS(
        v3_intention=_NS(locked_comp='列车同行', p1_pair=(), phase='locked',
                         transition_pair=()),
        target_comp=comp, transition_framework=''))
    dep, bench = _all_two_star_deployed(), [_bc('三月七', 1, star=2)]
    st = GameState(gold=0, level=6, plane=2, round_num=3, board={},
                   deployed=list(dep), bench=list(bench))
    ctx = assemble_swap_plan_inputs(sess, state=st,
                                    deployed=list(x for x in dep if x),
                                    bench=list(x for x in bench if x),
                                    cap=st.max_units())
    assert ctx is not None and ctx.evolution_swap_armed is True
    # 腿移除①:bench 无在册线件 → 臂关
    ctx_no = assemble_swap_plan_inputs(
        sess, state=st, deployed=list(x for x in dep if x), bench=[],
        cap=st.max_units())
    assert ctx_no is not None and ctx_no.evolution_swap_armed is False
    # 腿移除②:板面已成型(board 列车 2 达档 → fp≥1.00)→ 臂关
    st_formed = GameState(gold=0, level=6, plane=2, round_num=3,
                          board={'列车同行': 2}, deployed=list(dep),
                          bench=list(bench))
    ctx_formed = assemble_swap_plan_inputs(
        sess, state=st_formed, deployed=list(x for x in dep if x),
        bench=list(x for x in bench if x), cap=st_formed.max_units())
    assert ctx_formed is not None and ctx_formed.evolution_swap_armed is False


# ============ 其余守卫武装帧全保留(禁借臂扩缺口) ============

def test_other_guards_hold_while_armed() -> None:
    """守卫保留锁(ADR-0382 分级保护语义在臂内不变):武装帧下
    ①义务集件(buy_membership)/②轮内新鲜件(fresh_buy)/③已成型引擎
    掉档件(engines_guard:DOT 2 档卖 1 掉 1)/④3合1 素材对
    (merge_material_guard)照拒;星级不可读(star=None,执行侧 SIFT
    漏读形态)恒拒——不可判星级 = 不可判 ADR-0382 弱序,fail 向。"""
    dep = _all_two_star_deployed()
    bench = [_bc('三月七', 1, star=2)]
    base = dict(deployed=dep, bench=bench)
    assert swap_sell_exclusion_reason(
        '符玄', _ctx(membership=frozenset({'符玄', '三月七'}), **base)) \
        == 'buy_membership'
    assert swap_sell_exclusion_reason(
        '爻光', _ctx(fresh=frozenset({'爻光'}), **base)) == 'fresh_buy'
    assert swap_sell_exclusion_reason('艾丝妲', _ctx(**base)) \
        == 'engines_guard'
    assert swap_sell_exclusion_reason(
        '爻光', _ctx(deployed=dep, bench=bench + [_bc('爻光', 2, star=2)])) \
        == 'merge_material_guard'
    # 星级不可读(参数 None 且 deployed 域无该件可回查 = 执行侧 SIFT
    # 双域漏读形态)恒拒——不可判星级 = 不可判 ADR-0382 弱序,fail 向;
    # 回退查得星(域可读)不构成不可读,照常按臂语义判。
    assert swap_sell_exclusion_reason('爻光', _ctx(**base), star=None,
                                      bench=[], deployed=[]) \
        == 'star_guard'
    assert swap_sell_exclusion_reason('爻光', _ctx(**base), star=None,
                                      bench=bench, deployed=dep) == ''


# ============ 发射路径端到端(死代码激活端到端;变异目标同主锁) ============

def _m1p_frame(deployed: list[BenchChar], bench: list[BenchChar]):
    from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
        MandateFrame,
    )
    return MandateFrame(gold=0, level=6, bench=bench, deployed=deployed,
                        deploy_cap=6, node_type=None, stop_flag=False,
                        k_members=(), round_num=2)


def test_run_mandate_emits_armed_two_star_swap(monkeypatch) -> None:
    """发射路径端到端锁(ADR-0614 演进层换血提案接入锁线后备战决策环;
    变异:摘除武装旁路 → m1p_plan_empty,本锁红):全 2★ 板面 + bench
    在册 core 待上的锁线转型帧经 run_mandate ⇒ 发射 RunDeploy
    (m1_swap_redeploy)且 pending 臂 = transition——2★ 线外件让位、
    core 上板的事务由既有 M1″ 发射位承载(零新发射位 = 与 T-127 触发位
    同点单发射,防双发射由构造保证:M1″ 块单次评估 + RunDeploy 在批
    唯一)。装配侧意向供给桩化同 test_cw_swap_transition_arm 既有形态。"""
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
                        lambda ist: frozenset({'三月七'}))
    comp = _NS(all_factions=('列车同行',), core_chars=('三月七',),
               factions=('列车同行',), form_tiers={'列车同行': 2},
               shared_chars=(), substitute_plan=None)
    sess = _NS(last_owned_equips=None)
    _st = state_of(sess)
    _st.cw4_counters = {}
    _st.v3_intention = _NS(locked_comp='列车同行', p1_pair=(),
                           phase='locked', transition_pair=())
    _st.target_comp = comp
    _st.transition_framework = ''
    dep, bench = _all_two_star_deployed(), [_bc('三月七', 1, star=2)]
    st = GameState(gold=0, level=6, plane=2, round_num=3, board={},
                   deployed=list(dep), bench=list(bench))
    out = run_mandate(_m1p_frame(dep, bench), sess, state=st)
    fired = [e for e in out if e.action.__class__.__name__ == 'RunDeploy'
             and e.reason == 'm1_swap_redeploy']
    assert len(fired) == 1
    assert state_of(sess).cw4_counters.get('m1p_fired') == 1
    assert state_of(sess).cw4_m1p_arm_pending == 'transition'
