"""report_action_move_unit_param 统一拖动推演矩阵测试(镜像 src =
kernel/cw_action_report/move_unit.py;部署统一批 unified-deploy-order
§4 动作词表行:源域 × 目标域 × 目标槽占用态全分支)。

锁定的期望表现 = 详设 changes/2026-10-30-roster-plane1-union/details/
unified-deploy-order.md §4「动作词表」行与 §2 段 0(唯一性键/银狼
落场后形态/未知件禁挤)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_move_unit_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    GameState,
    Unit,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
)

_SIG_OBS = ChannelSig(family='obs', actor='CwScreenPrep')
_SIG_ACT = ChannelSig(family='logic_action', actor='CwScreenPrep')


def _gs(bench: list[Unit | None], front: list[Unit | None],
        back: list[Unit | None] | None = None,
        locks: tuple = (),
        node_pos: tuple[int, int] = (1, 1)) -> GameState:
    """观察面组装:bench/前排/后排按位直写(空位 = None → empty);
    生效序位观察锚定(锁守卫比对基准,fail-open 缺省须显式播种)。"""
    gs = GameState(schema_version=GAME_STATE_SCHEMA_VERSION)
    slots: list[BenchSlot | None] = [
        BenchSlot(kind='unit', unit=u) if u is not None
        else BenchSlot(kind='empty') for u in bench]
    while len(slots) < 9:
        slots.append(BenchSlot(kind='empty'))
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.deployed, DeployedView(
        front_slots=list(front) + [None] * (4 - len(front)),
        back_slots=(list(back) if back is not None else [None] * 6)),
        sig=_SIG_OBS)
    gs.observe(gs.node_pos, node_pos, sig=_SIG_OBS)
    if locks:
        gs.write_logic(gs.env_grant_deploy_locks, locks,
                       produced_by='test-seed',
                       sig=ChannelSig(family='logic_action', actor='t',
                                      mode='compute'))
    return gs


def _unit(name: str, star: int = 1, uid: int | None = None) -> Unit:
    return Unit(char_id=name, star=star, uid=uid)


def test_bench_to_field_empty_slot_direct_drop() -> None:
    """bench→场上空槽 = 直落:落位 + bench 源槽清空。"""
    gs = _gs([_unit('三月七'), None], [None, None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 1), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.front_slots[0].char_id == '三月七'
    assert gs.bench.value.slots[0].kind == 'empty'


def test_bench_to_occupied_field_swap_back_to_src() -> None:
    """bench→场上被占槽 = 交换:被占者回 bench 源槽(占用不变)。"""
    gs = _gs([_unit('花火'), None], [_unit('三月七'), None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 1), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.front_slots[0].char_id == '花火'
    assert gs.bench.value.slots[0].unit.char_id == '三月七'


def test_field_to_field_pure_swap_no_lock_no_transform() -> None:
    """场上→场上 = 纯换位(目标被占 = 场上互换;无锁无变换)。"""
    gs = _gs([_unit('流萤', 1, uid=1), None],
             [_unit('刃', star=3), _unit('三月七'), None, None],
             locks=(('流萤', 1, (9, 9)),))
    # 流萤被锁但只做场上挪位(非新上场)→ 无锁校验,放行。
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('front', 2, 'front', 1), _SIG_ACT)
    assert out.applied is True
    front = gs.deployed.value.front_slots
    assert front[0].char_id == '三月七'
    assert front[1].char_id == '刃'


def test_field_to_bench_empty_slot_disembark() -> None:
    """场上→bench 空槽 = 下场(保守归一 = 原样保留形态名)。"""
    gs = _gs([None, None], [_unit('刃'), None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('front', 1, 'bench', 3), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.front_slots[0] is None
    assert gs.bench.value.slots[3].unit.char_id == '刃'


def test_field_to_occupied_bench_swap_lock_guards_bench_unit() -> None:
    """场上→bench 被占槽 = 交换:被挤出 bench 件上 field,锁校验辖此。"""
    gs = _gs([_unit('流萤', 1, uid=1), None],
             [_unit('刃'), None, None, None],
             locks=(('流萤', 1, (9, 9)),))
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('front', 1, 'bench', 0), _SIG_ACT)
    # 流萤(uid=1)被锁 → 新单位入场形态被锁校验拒(fail-closed 零写)。
    assert out.applied is False
    assert out.reason.startswith('deploy_locked:')
    assert gs.deployed.value.front_slots[0].char_id == '刃'


def test_field_to_occupied_bench_swap_success() -> None:
    """场上→bench 被占槽 = 交换(无锁/同名冲突时):bench 件上场、
    场上件进 bench 目标槽。"""
    gs = _gs([_unit('花火'), None], [_unit('刃'), None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('front', 1, 'bench', 0), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.front_slots[0].char_id == '花火'
    assert gs.bench.value.slots[0].unit.char_id == '刃'


def test_bench_to_bench_reposition() -> None:
    """bench→bench = 席内挪位(空槽移动 + 互换两形态)。"""
    gs = _gs([_unit('三月七'), _unit('花火'), None], [None] * 4)
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'bench', 2), _SIG_ACT)
    assert out.applied is True
    assert gs.bench.value.slots[0].kind == 'empty'
    assert gs.bench.value.slots[2].unit.char_id == '三月七'
    out2 = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 1, 'bench', 2), _SIG_ACT)
    assert out2.applied is True
    assert gs.bench.value.slots[1].unit.char_id == '三月七'
    assert gs.bench.value.slots[2].unit.char_id == '花火'


def test_locked_bench_unit_to_field_refused() -> None:
    """上场锁(bench→场上直落形态):锁期内拒零写(T-30 实例粒度)。"""
    gs = _gs([_unit('流萤', 1, uid=7), None], [None] * 4,
             locks=(('流萤', 7, (9, 9)),))
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'back', 1), _SIG_ACT)
    assert out.applied is False
    assert out.reason.startswith('deploy_locked:')


def test_duplicate_on_board_refused() -> None:
    """唯一性键(上场者与场上现存无同名):开拓者双形态归一互斥。"""
    from sr_od.application.currency_war.data.cw_chars import is_trailblazer
    assert is_trailblazer('开拓者•欢愉') or is_trailblazer('开拓者•记忆')
    gs = _gs([_unit('开拓者•欢愉'), None], [_unit('开拓者•记忆'),
                                        None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 2), _SIG_ACT)
    assert out.applied is False
    assert out.reason.startswith('duplicate_on_board:')


def test_unknown_field_unit_slot_refuses_bench_entry() -> None:
    """禁挤未知件(详设 §2 段 0 D3-13):场上未知身份件占槽,bench 件
    拖入该槽 = 移动未知件 → fail-closed 拒。"""
    gs = _gs([_unit('花火'), None], [Unit(char_id='', star=1),
                                None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 1), _SIG_ACT)
    assert out.applied is False
    assert out.reason.startswith('dst_unknown_unit:')


def test_silverwolf_transform_on_bench_to_field() -> None:
    """银狼变换窗只 bench→上场触发:3★ 落场写 1★ + 档行 +1(银狼
    落场后形态评分 ≡ 执行后板面,场景走查「银狼 3★ 上场」行)。
    档行 = 当前档 +1:未观察档(None)归约 3(开局档默认),首变 → 4。"""
    gs = _gs([_unit('银狼LV.999', star=3), None], [None] * 4)
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 1), _SIG_ACT)
    assert out.applied is True
    moved = gs.deployed.value.front_slots[0]
    assert moved.char_id == '银狼LV.999'
    assert moved.star == 1
    assert gs.lv999_cost_tier.value == 4


def test_silverwolf_field_to_bench_no_transform() -> None:
    """下场不触发变换窗(变换窗只 bench→上场;3★ 场上件下场保持 3★)。"""
    gs = _gs([None, None], [_unit('银狼LV.999', star=3), None, None, None])
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('front', 1, 'bench', 0), _SIG_ACT)
    assert out.applied is True
    assert gs.bench.value.slots[0].unit.star == 3


def test_invalid_domain_and_slot_refused() -> None:
    """越界/域外 fail-closed:front 槽 0(基 1)/bench 槽 9/域枚举外全拒。"""
    gs = _gs([_unit('三月七'), None], [_unit('刃'), None, None, None])
    for p in (CwActionMoveUnitParam('front', 0, 'bench', 0),
              CwActionMoveUnitParam('bench', 0, 'bench', 9),
              CwActionMoveUnitParam('side', 1, 'bench', 0),
              CwActionMoveUnitParam('bench', 0, 'shop', 1)):
        out = report_action_move_unit_param(gs, p, _SIG_ACT)
        assert out.applied is False, p
        assert out.reason.startswith('move_slot_invalid:'), p


def test_same_slot_idempotent_no_write() -> None:
    """同槽直拖 = 幂等零写成功(执行层噪声形态)。"""
    gs = _gs([_unit('三月七'), None], [None] * 4)
    before = (gs.bench.value, gs.deployed.value)
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'bench', 0), _SIG_ACT)
    assert out.applied is True
    assert (gs.bench.value, gs.deployed.value) == before


def test_trailblazer_form_by_target_row() -> None:
    """开拓者按目标排定形态:bench 欢愉形态 → 前排 = 记忆形态。"""
    from sr_od.application.currency_war.kernel.cw_exec_state import (
        trailblazer_row_identity,
    )
    front_id, _ = trailblazer_row_identity('开拓者•欢愉', 'front')
    gs = _gs([_unit('开拓者•欢愉'), None], [None] * 4)
    out = report_action_move_unit_param(
        gs, CwActionMoveUnitParam('bench', 0, 'front', 1), _SIG_ACT)
    assert out.applied is True
    assert gs.deployed.value.front_slots[0].char_id == front_id
