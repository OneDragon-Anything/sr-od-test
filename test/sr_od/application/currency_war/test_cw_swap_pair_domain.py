"""双轨对锁期换入通道锁(行为出处 = 2026-09-18 sim 实证:配方对锁局
板满帧全 plan_empty,配方完成件压席无解形态)。

被锁行为(语义出处,非实现巧合):
- **转型域方向锁前提推广**:换血域「方向锁在效」= 终局线锁
  (``ist.locked_comp``)∨ P1 配方对锁(``ist.p1_pair``,ADR-0357 锁定
  产物;装配单一源 = ``assemble_swap_plan_inputs``)——配方对锁帧
  fenced 离线件经资格族(守恒门/star 守卫/素材守卫)可卖,此前恒
  ``fenced_arm_closed``,板满帧无合法 victim(探针实证:pair 局
  plan_empty 全帧);未对锁帧语义照旧。伴随收紧面(显式申报):对锁
  帧 off-target 非围栏板件由基座臂自由卖收窄为资格族(1★ 限卖等)。
  玩法口径 = user_playstyle [20]
  (配方驱动板面)/[13](凑齐优先)。
- **配方完成件让位通道**:双轨对锁期 fp<1 ∧ 板满 ∧ bench 存在
  「入板即成型」件(``_completion_swap_ins``,✗→✓ 严格优,折法单一源 =
  ``form_progress``)时,target 板件让位可卖——必需件臂只辖
  required_deployed 成员,桥池 pair required 恒空,完成件压席无解形态
  由本通道承接;卖后上序底线扩展为「真含 required ∪ 完成件」。
- **发射门轴①对锁期读法**:membership 空集帧(锁线采购集未锁帧缺省)
  压席成员轴退 target 视图(kernel ``target_view_char_is`` 单一源),
  转型域计划不再被发射门恒 defer(kernel 域开、门恒关的分轨态根除)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_deploy_logic import (
    SwapPlanContext,
    required_swap_arm_pending,
    select_swap_plan,
    swap_sell_exclusion_reason,
)
from sr_od.application.currency_war.kernel.cw_exec_state import BenchChar
from sr_od.application.currency_war.kernel.cw_intention import (
    pair_target_comp,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.deploy_plan import (
    select_deployments_reasoned,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    _redeploy_emission_allowed,
)

# 真实注册表角色(锁语义不锁巧合):卡芙卡/黑天鹅 = 持续伤害(flow) /
# 希儿 = 贝洛伯格+量子同频(required carry)/ 花火 = 量子同频 /
# 娜塔莎 = 贝洛伯格 / 三月七 = 列车同行+护盾(fenced,对视野外)/
# 万敌 = 夜之半神+燃血(视野外非围栏)。
_KAFKA = '卡芙卡'
_HEITIANQUE = '黑天鹅'
_XIER = '希儿'
_HUAHUO = '花火'
_NATASHA = '娜塔莎'
_SANYUEQI = '三月七'

# 持续伤害+希儿系 pair(真实 pair 键;判据 = DOT2 ∧ (量2∨贝2) ∧ 希儿在板;
# 单一源 = pair_target_comp)。
_PAIR = ('持续伤害', '希儿系')


def _bc(name: str, idx: int) -> BenchChar:
    """bench/板上件(slot = 1 基物理槽;idx 供唯一 slot)。"""
    return BenchChar(slot=idx, char_id=name, star=1)


def _ctx(*, board: list[str], bench: list[str], cap: int,
         fp: float, locked: bool, domain: bool,
         required: frozenset[str] = frozenset()) -> SwapPlanContext:
    """直构 SwapPlanContext(1★ 单元格;pair 真值键面;域快照随 locked
    一致传入——装配点两字段同点同值)。"""
    comp = pair_target_comp(_PAIR)
    return SwapPlanContext(
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
        locked_factions=frozenset(),
        protect_names=frozenset(),
        membership=frozenset(),
        fresh_buys=frozenset(),
        board={},
        deployed=[BenchChar(slot=i + 1, char_id=n, star=1,
                            position_pref='back')
                  for i, n in enumerate(board)],
        bench=[_bc(n, i + 1) for i, n in enumerate(bench)],
        cap=cap,
        front_slots=4,
        back_slots=6,
        fenced_on=False,
        fp=fp,
        locked=locked,
        board_full=len(board) >= cap,
        recipe_floor_lock_exempt=False,
        target_comp=comp,
        evolution_swap_armed=False,
        transition_domain=domain,
        required_names=frozenset(required) or frozenset(comp.required_deployed),
    )


def test_pair_locked_domain_releases_fenced_offline_victim() -> None:
    """配方对锁帧转型域开:fenced 离线件经资格族可卖;未对锁帧照旧拒。

    板 = 卡芙卡(DOT1)+希儿+花火(量2)+三月七(围栏件,对视野外):
    判据缺 DOT 腿(fp 0.833 <1)∧ 板满 → 对锁帧三月七经守恒门(列车/
    护盾 0 档不掉)放行;同板未对锁帧 = fenced_arm_closed(前提分野)。
    """
    board = [_KAFKA, _XIER, _HUAHUO, _SANYUEQI]
    ctx_open = _ctx(board=board, bench=[_HEITIANQUE], cap=4,
                    fp=0.833, locked=True, domain=True)
    assert swap_sell_exclusion_reason(_SANYUEQI, ctx_open) == ''
    ctx_closed = _ctx(board=board, bench=[_HEITIANQUE], cap=4,
                      fp=0.833, locked=False, domain=False)
    assert swap_sell_exclusion_reason(_SANYUEQI, ctx_closed) \
        == 'fenced_arm_closed'


def test_completion_member_yields_target_seat() -> None:
    """完成件滞留通道:希儿在板(required 臂关)∧ bench 有入板即成型件,
    多余腿 target 板件让位可卖;破腿件照旧 target_keep;计划真换入完成件。

    板 = 卡芙卡(DOT1)+希儿+花火(量2)+娜塔莎(贝1):判据缺 DOT 腿;
    黑天鹅入板 → DOT2 → fp=1.0(完成件)。花火/娜塔莎离场(量2 或贝2 有
    另一腿承住)+黑天鹅入板 → 判据满 → 让位;卡芙卡离场 → DOT 归零破腿
    → 照旧保。旧语义下必需件臂只辖 required(希儿在板 = 臂关),完成件
    压席无解形态(sim 实证主桶)。victim 序 = 让渡序(贡献并列 1
    → 扫描序,花火在前);卖后板面 = DOT2∧贝2∧希儿在板,成型。
    """
    ctx = _ctx(board=[_KAFKA, _XIER, _HUAHUO, _NATASHA],
               bench=[_HEITIANQUE], cap=4,
               fp=0.833, locked=True, domain=True)
    assert required_swap_arm_pending(ctx)   # 完成分支武装(希儿在板)
    assert swap_sell_exclusion_reason(_HUAHUO, ctx) == ''
    assert swap_sell_exclusion_reason(_NATASHA, ctx) == ''
    assert swap_sell_exclusion_reason(_KAFKA, ctx) == 'target_keep'
    plan = select_swap_plan(ctx, select_up=select_deployments_reasoned)
    assert plan.nonempty
    assert plan.sell_names == [_HUAHUO]
    assert {ctx.bench[i].char_id for i in plan.up_bench} == {_HEITIANQUE}


def test_completion_channel_gates() -> None:
    """完成通道三闭门:成型帧关 / bench 无完成件关 / 未对锁帧关。

    板面同 test_completion_member_yields_target_seat,仅翻转前提——
    fp≥1.0(已成型,无完成缺口)、bench 无完成件(黑天鹅换万敌)、
    locked=False(未对锁,方向锁前提不在)三者 pending 均 False。
    """
    board = [_KAFKA, _XIER, _HUAHUO, _NATASHA]
    assert not required_swap_arm_pending(_ctx(
        board=board, bench=[_HEITIANQUE], cap=4,
        fp=1.0, locked=True, domain=True))
    assert not required_swap_arm_pending(_ctx(
        board=board, bench=['万敌'], cap=4,
        fp=0.833, locked=True, domain=True))
    assert not required_swap_arm_pending(_ctx(
        board=board, bench=[_HEITIANQUE], cap=4,
        fp=0.833, locked=False, domain=False))


def test_redeploy_gate_pair_period_reads_target_view() -> None:
    """发射门轴①对锁期读法:membership 空集帧压席成员轴退 target 视图。

    bench = 花火(视图内,入板即成型)+万敌(视图外):空 membership 帧
    花火撑起轴①,轴②(入板推进成型度,严格上升)真 → 放行;bench 全
    视图外 → defer。轴①锁线分支(membership 非空)不辖本读法。
    """
    comp = pair_target_comp(_PAIR)
    gate_ctx = SimpleNamespace(
        membership=frozenset(),
        bench=[SimpleNamespace(char_id=_HUAHUO),
               SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    # 板 = DOT1 + 量1 + 希儿在板口径(fp 0.833):花火入板 → 量2 → OR 腿
    # 0.5→1.0 严格上升(轴②)。
    state = SimpleNamespace(board=SimpleNamespace(value={
        '持续伤害': 1, '量子同频': 1, '贝洛伯格': 1}))
    assert _redeploy_emission_allowed(session=None, state=state,
                                      ctx=gate_ctx)
    off_ctx = SimpleNamespace(
        membership=frozenset(),
        bench=[SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    assert not _redeploy_emission_allowed(session=None, state=state,
                                          ctx=off_ctx)


def test_redeploy_gate_membership_unread_fails_closed() -> None:
    """发射门 membership 缺读弃权:None = 缺读,不放行(fail-closed)。

    契约边界 = None 缺读 ≠ 空集缺省,禁坠对锁期回退放宽(出处 =
    ``_redeploy_emission_allowed`` None 分支注)。入面参照
    test_redeploy_gate_pair_period_reads_target_view 的放行构造——若
    None 分支被误删坠回空集缺省读法,本构造经 target 视读法会假放行,
    锁响。
    """
    comp = pair_target_comp(_PAIR)
    unread_ctx = SimpleNamespace(
        membership=None,
        bench=[SimpleNamespace(char_id=_HUAHUO),
               SimpleNamespace(char_id='万敌')],
        target_comp=comp,
        target_factions=frozenset(comp.all_factions),
        target_cores=frozenset(comp.core_chars),
        fw_carry=frozenset(),
    )
    # 板面同放行构造口径:花火入板 → 量2 → 轴②严格上升(None 分支
    # 被删时走空集读法会真放行,保证本锁判别力)。
    state = SimpleNamespace(board=SimpleNamespace(value={
        '持续伤害': 1, '量子同频': 1, '贝洛伯格': 1}))
    assert not _redeploy_emission_allowed(session=None, state=state,
                                          ctx=unread_ctx)
