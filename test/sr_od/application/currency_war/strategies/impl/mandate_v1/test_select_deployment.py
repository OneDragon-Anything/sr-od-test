"""mandate.select_deployment 单帧测试(部署选人纯函数接口)。

被测 = ``strategies/impl/mandate_v1/mandate.py`` ``select_deployment`` /
``PrepContext`` / ``assemble_prep_context`` 与 ``entry._step5_deploy``
的消费接线(契约 = changes/2026-10-29-unified-priority/details/
acquisition-and-sell.md §1;部署判据正本 = strategy-docs/24 号稿,
结构抽取判据零改动):

- 三臂目标态:M5 开局(窗口冻结面生效)/ M1 空槽补位 / M1″ 板满
  换阵完成集(= (板 − 计划 sell) ∪ 计划 up,acquisition-and-sell
  §1 语义定案);
- 纯函数零遥测:目标态求取不写 counters/pending(虚拟重算副本零
  写入红线,总纲 §2.3);
- 生产路径消费接线:定型帧零动作 + pending 复位;diff 帧保持现行
  发射序(现行部署测试 = 行为守卫,本文件只补接线断言)。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_comps import Comp
from sr_od.application.currency_war.kernel.cw_exec_state import (
    bench_slot_unit,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    Unit,
    bench_entries_of,
    bench_view_slots_of,
    deployed_rows_of,
    max_units_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionDeployMoveParam,
    CwActionSellDeployedParam,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
    entry,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate import (
    MandateFrame,
    assemble_prep_context,
    select_deployment,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.mandate_state import (
    state_of,
)

_C_COMP = Comp(name='C组生长测', factions=[], core_chars=[
    '瓦尔特', '杰帕德', '停云', '希儿', '符玄'],
    form_tiers={}, strength='A', form_difficulty='easy',
    early_power='中', required_deployed=('瓦尔特', '杰帕德'))


def _frame(gs, *, round_num: int = 2) -> MandateFrame:
    """容器现读重建 MandateFrame(entry.emit 同款装配)。"""
    front, back = deployed_rows_of(gs)
    return MandateFrame(
        gold=30, level=5, bench=bench_entries_of(gs),
        deployed=[d for d in (*front, *back) if d is not None],
        deploy_cap=max_units_of(gs), node_type=None, stop_flag=False,
        k_members=(), round_num=round_num)


def _c_shape_session() -> tuple:
    """C 形态锁定 session 桩(直种 Comp + ist 分支① + seam 开闸;
    装配源 = test_emit_swap_bond_gate 同款锚帧形态)。"""
    session = cw4_session(_C_COMP)
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=_C_COMP.name)
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def test_m5_opening_target_and_window_freeze() -> None:
    """M5 开局目标态:板空帧部署定型 = 窗口过滤后的选人名集。

    窗口适用范围经 PrepContext 冻结集生效(现行谓词装配时取值):
    停云无窗口登记照常入选;椒丘所属线上线窗口未到(synergy 计数
    未达,现行 _deploy_window_blocked 判拦)不入目标态——与生产
    _emit_deploy_moves_scoped 的逐 move 过滤同判据同值。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=5, level=5, round_num=1,
                bench=[cw4_bc('停云'), cw4_bc('椒丘')])
    frame = _frame(gs, round_num=1)
    prep = assemble_prep_context(session, gs, frame)
    assert prep.window_blocked_names == {'椒丘'}, \
        f'窗口拦截集 = 现行谓词装配时冻结值,实得 {prep.window_blocked_names}'
    target = select_deployment(frame, prep)
    assert target == {'停云'}, f'M5 目标态 = 窗口过滤后选人,实得 {target}'


def test_m1_vacancy_fill_target() -> None:
    """M1 空槽补位目标态:定型 = 现板 ∪ 补位选人(窗口面生效)。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=5, level=5,
                bench=[cw4_bc('停云')],
                front_row=[Unit(char_id='杰帕德', star=1)])
    frame = _frame(gs)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    assert target == {'杰帕德', '停云'}, \
        f'M1 目标态 = 现板 ∪ 补位件,实得 {target}'


def test_capfull_swap_completion_set_and_purity() -> None:
    """M1″ 板满换阵目标态 = 计划收敛完成集 + 纯函数零遥测。

    C 形态锚帧(cap=3 板满,bench 有 required 两件):目标态 =
    (板 − 计划 sell) ∪ 计划 up = {符玄, 瓦尔特, 杰帕德}——与现行
    发射面多帧逐对收敛的终板一致(test_emit_swap_bond_gate 全序断言
    的终板),本函数一次给出目标态。零遥测:red line = 虚拟重算执行
    前后 counters/pending 零写入(总纲 §2.3 副本零写入三通道)。"""
    session, st = _c_shape_session()
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[cw4_bc('瓦尔特'), cw4_bc('杰帕德')],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('停云', '希儿', '符玄')])
    frame = _frame(gs)
    counters_before = dict(st.cw4_counters)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    assert target == {'瓦尔特', '杰帕德', '符玄'}, \
        f'换阵完成集,实得 {target}'
    assert st.cw4_counters == counters_before, \
        f'纯函数零遥测(分键零写入),实得 {st.cw4_counters}'
    assert st.cw4_m1p_arm_pending is None \
        and st.cw4_m1p_plan_pending is None, 'pending 零写入'


def test_step5_settled_frame_zero_action_and_pending_reset() -> None:
    """生产接线·定型帧:目标态 == 现板 → 零动作,pending 同步复位
    (与现行发射器无发射分支的帧级复位语义一致,_step5_deploy
    docstring 行为申报)。"""
    session, st = _c_shape_session()
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('瓦尔特', '杰帕德', '符玄')])
    st.cw4_m1p_arm_pending = 'bond_gate'          # 上位帧残留载荷
    st.cw4_m1p_plan_pending = {'sell': ['停云']}
    out = entry._step5_deploy(session, gs, _frame(gs), [])
    assert out == [], '部署定型帧零动作'
    assert st.cw4_m1p_arm_pending is None \
        and st.cw4_m1p_plan_pending is None, '定型帧 pending 复位'


def test_step5_m1_diff_emits_deploy_move() -> None:
    """生产接线·M1 diff 帧:目标态 ⊋ 现板 → 现行发射器产补位 move,
    动作对象 = 目标态 diff 中的 bench 件(发射 tag/落位判据零改动)。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=5, level=5,
                bench=[cw4_bc('停云')],
                front_row=[Unit(char_id='杰帕德', star=1)])
    out = entry._step5_deploy(session, gs, _frame(gs), [])
    assert len(out) == 1 and out[0].reason == 'm1_deploy'
    act = out[0].action
    assert isinstance(act, CwActionDeployMoveParam)
    unit = bench_slot_unit(bench_view_slots_of(gs)[act.bench_idx])
    assert getattr(unit, 'char_id', '') == '停云', '动作 = 目标态 diff 件'


def test_step5_capfull_swap_first_pair_unchanged() -> None:
    """生产接线·板满换阵帧:目标态 diff 非空 → 现行 M1″ 发射器照旧
    逐对发射,首对 victim = 组贪心序首(发射行为与现行部署测试
    test_step5_pair_atomic_order_and_fresh_rederive 的全序守卫衔接,
    本断言只锁「消费 select_deployment 后首动作不变」)。"""
    session, st = _c_shape_session()
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[cw4_bc('瓦尔特'), cw4_bc('杰帕德')],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('停云', '希儿', '符玄')])
    out = entry._step5_deploy(session, gs, _frame(gs), [])
    assert out and isinstance(out[0].action, CwActionSellDeployedParam)
    front, _back = deployed_rows_of(gs)
    assert front[out[0].action.deployed_idx].char_id == '停云', \
        '首对 victim = 组贪心字典序首(现行发射序不变)'


def _locked_session(comp_name: str) -> tuple:
    """终局锁定 session 桩(target_comp 直种 + ist 分支① + seam 开闸;
    装配源 = test_emit_swap_bond_gate 同款)。"""
    from sr_od.application.currency_war.kernel.cw_comps import get_comp
    session = cw4_session(get_comp(comp_name))
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=comp_name)
    st.cw4_m1p_seam_verified = True
    st.cw4_counters = {}
    return session, st


def test_same_name_starup_pair_not_swallowed() -> None:
    """同名升星对不被名集目标态吞没(对抗审查实锤形态的回归锁)。

    板满帧换出换入同名不同星(吉尔伽美什 1★ 在板 ↔ 2★ 在 bench,
    kernel bond_gate star 分支一等设计通道):select_deployment 的
    名集目标态对该形状恒 == 现板(名集相等、星级不等)——_step5_deploy
    的定型判定不得据此早退,板满帧一律落现行 M1″ 发射器:首动作 =
    同名低星 victim 的 SellDeployed,2★ 由下帧 M1 空槽补位接管。"""
    session, st = _locked_session('双王圣杯')
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[cw4_bc('吉尔伽美什', star=2)],
                front_row=[Unit(char_id='吉尔伽美什', star=1),
                           Unit(char_id='Saber', star=2),
                           Unit(char_id='符玄', star=2)])
    frame = _frame(gs)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    current = {d.char_id for d in frame.deployed
               if d is not None and d.char_id}
    assert target == current, '名集目标态对同名升星对形状不敏感(契约口径)'
    out = entry._step5_deploy(session, gs, frame, [])
    assert out and isinstance(out[0].action, CwActionSellDeployedParam), \
        f'同名升星对照旧发射(不定型早退),实得 {out}'
    front, _back = deployed_rows_of(gs)
    victim = front[out[0].action.deployed_idx]
    assert victim.char_id == '吉尔伽美什' and (victim.star or 1) == 1, \
        'victim = 板上同名低星件(star 分支换血)'
