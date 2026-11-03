"""mandate.select_deployment 单帧测试(阶段 5/6 统一部署搜索内核)。

被测 = ``strategies/impl/mandate_v1/mandate.py`` ``select_deployment``
(统一部署搜索内核换接,设计单一源 = changes/2026-10-30-roster-
plane1-union/details/unified-deploy-order.md §1/§2 + 接口契约②:
target_board = 名 → (排, 星))与 ``entry._step5_deploy`` 的差分执行器
消费接线:

- 目标态 = 搜索定型板面(名+排+星;窗口谓词辖新上场、场上件恒满足
  §3.9);
- 同名升星对(场景走查「同名异星对」行):就位粒度含星 → diff 非空
  → 两步换星(低星直卖 + 高星上场,通道不停摆,D2-1);
- 纯函数零遥测:目标态求取不写 counters(虚拟重算副本零写入红线);
- 生产接线:定型收敛帧零动作;diff 帧产统一拖动/换星直卖序列。
"""
from __future__ import annotations

from test.sr_od.application.currency_war._cw_helpers import (
    cw4_bc,
    cw4_gs,
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_comps import Comp, get_comp
from sr_od.application.currency_war.kernel.cw_game_state import (
    Unit,
    bench_entries_of,
    deployed_rows_of,
    max_units_of,
)
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
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

_C_COMP = Comp(name='C组生长测', core_chars=[
    '瓦尔特', '杰帕德', '停云', '希儿', '符玄'],
    form_tiers={},
    required_deployed=('瓦尔特', '杰帕德'))


def _frame(gs, *, round_num: int = 2) -> MandateFrame:
    """容器现读重建 MandateFrame(entry.emit 同款装配)。"""
    front, back = deployed_rows_of(gs)
    return MandateFrame(
        gold=30, level=5, bench=bench_entries_of(gs),
        deployed=[d for d in (*front, *back) if d is not None],
        deploy_cap=max_units_of(gs), node_type=None, stop_flag=False,
        k_members=(), round_num=round_num)


def _c_shape_session() -> tuple:
    """C 形态锁定 session 桩(直种 Comp + ist 分支①;空羁绊线场景)。"""
    session = cw4_session(_C_COMP)
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp=_C_COMP.name)
    st.cw4_counters = {}
    return session, st


def test_locked_empty_bond_line_core_shared_completion() -> None:
    """空羁绊线(反甲流形态,form_tiers={} ∧ factions=[]):L1 由角色
    完成度单独承载(core∪shared 口径,D2-3)——required 两件(瓦尔特/
    杰帕德)与线成员符玄进目标态,非成员(停云/希儿)让位。"""
    session, st = _c_shape_session()
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[cw4_bc('瓦尔特'), cw4_bc('杰帕德')],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('停云', '希儿', '符玄')])
    frame = _frame(gs)
    counters_before = dict(st.cw4_counters)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    assert len(target) == 3, f'K 满编,实得 {sorted(target)}'
    assert {'瓦尔特', '杰帕德'} <= set(target), \
        f'required 两件进目标态(空羁绊线成员优先),实得 {sorted(target)}'
    assert set(target) <= {'瓦尔特', '杰帕德', '停云', '希儿', '符玄'}, \
        '目标态全部为线成员(core∪shared 口径)'
    assert st.cw4_counters == counters_before, \
        f'纯函数零遥测(分键零写入),实得 {st.cw4_counters}'


def test_step5_settled_frame_zero_action() -> None:
    """生产接线·定型收敛帧:目标态 == 现板(名+排+星全对)→ 差分空 →
    零动作(diff 空 = 显式零动作,§3.1;旧 m1p pending 复位断言随
    kernel swap 机器收编删除——载体字段已随部署统一批丁退役,unified-
    deploy-order §2.7/§4)。"""
    session, st = _c_shape_session()
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[],
                front_row=[Unit(char_id=n, star=1)
                           for n in ('瓦尔特', '杰帕德', '符玄')])
    out = entry._step5_deploy(session, gs, _frame(gs), [])
    assert out == [], '部署定型帧零动作'


def test_step5_vacancy_diff_emits_move_unit() -> None:
    """生产接线·空槽补位帧:目标态 ⊋ 现板 → 差分执行器产统一拖动
    (载体 = CwActionMoveUnitParam;落位判据 = 搜索排分配)。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=5, level=5,
                bench=[cw4_bc('停云')],
                front_row=[Unit(char_id='杰帕德', star=1)])
    out = entry._step5_deploy(session, gs, _frame(gs), [])
    assert out, '空槽补位帧应发拖动'
    assert all(isinstance(e.action, CwActionMoveUnitParam) for e in out)
    moves = [e.action for e in out
             if isinstance(e.action, CwActionMoveUnitParam)
             and e.action.src_domain == 'bench']
    assert any(True for _m in moves), 'bench 件上场拖动在序列内'


def test_same_name_star_up_pair_two_step_not_stalled() -> None:
    """同名升星对(场景走查「同名异星对」行,D2-1/D3-3):就位粒度
    名+排+星 → 板上 1★ vs 目标 2★ = diff 非空 → 两步换星:低星
    SellDeployed 直卖(不经 bench 中转)+ 高星统一拖动上场——通道
    不停摆(现行 bond_gate star 通道的统一承载)。"""
    session = cw4_session(get_comp('双王圣杯'))
    st = state_of(session)
    st.v3_intention = IntentionState(locked_comp='双王圣杯')
    st.cw4_counters = {}
    gs = cw4_gs(session, deploy_cap=3, level=3,
                bench=[cw4_bc('吉尔伽美什', star=2)],
                front_row=[Unit(char_id='吉尔伽美什', star=1),
                           Unit(char_id='Saber', star=2),
                           Unit(char_id='符玄', star=2)])
    frame = _frame(gs)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    assert target.get('吉尔伽美什', ('', 0))[1] == 2, \
        f'同键取最高星(落场后形态),实得 {target}'
    out = entry._step5_deploy(session, gs, frame, [])
    assert out, '同名升星 diff 帧应有动作(通道不停摆)'
    sells = [e.action for e in out
             if isinstance(e.action, CwActionSellDeployedParam)]
    assert sells, f'低星直卖在序列内(两步之一),实得 {[type(e.action).__name__ for e in out]}'
    front, _back = deployed_rows_of(gs)
    victim = None
    view = gs.deployed.value
    idx = sells[0].deployed_idx
    if idx < len(view.front_slots):
        victim = view.front_slots[idx]
    else:
        victim = view.back_slots[idx - len(view.front_slots)]
    assert victim is not None \
        and victim.char_id == '吉尔伽美什' \
        and (victim.star or 1) == 1, 'victim = 板上同名低星件'
    moves = [e.action for e in out
             if isinstance(e.action, CwActionMoveUnitParam)]
    assert any(m.src_domain == 'bench' for m in moves), \
        '高星上场拖动在序列内(两步之二)'


def test_target_board_payload_shape() -> None:
    """接口契约②载荷形态:target_board = 名 → (排, 星)——排 ∈
    {'front','back'}、星 = 落场后形态选定星。"""
    session = cw4_session()
    gs = cw4_gs(session, deploy_cap=5, level=5,
                bench=[cw4_bc('停云')],
                front_row=[Unit(char_id='杰帕德', star=1)])
    frame = _frame(gs)
    target = select_deployment(frame, assemble_prep_context(
        session, gs, frame))
    assert isinstance(target, dict)
    for name, (row, star, slot) in target.items():
        assert row in ('front', 'back'), f'{name} 排值 {row!r} 非法'
        assert star in (1, 2, 3), f'{name} 星值 {star!r} 非法'
        assert slot is None or slot >= 1, f'{name} 槽位值 {slot!r} 非法'
