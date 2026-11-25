"""SimBackend ``_on_open_tome`` 分支单测(占席件「开件零写 + 选卡清槽」两拍契约的
sim 伴随面;被测单一源 = ``cw_sim_backend.SimBackend._on_open_tome`` + advance
分派接线 + ``install_backend``/``uninstall_backend`` 的溢出在场选卡清槽解析槽
装配)。

锁的设计约定(sim 无星徽弹窗呈现面、选卡拍不存在——典籍离席为后端开件拍代清,
sim-design.md §6.3 ``open_tome`` 准入例外):
- advance 分派接线:``trigger='open_tome'`` 在键集内(集外 = ValueError 响亮)
  且 ``decl.slots`` 原样送达 handler;
- 清席步:仅被点开槽(``slots`` 首元 = 备战栏物理槽 1 基)清为 empty,他槽
  (含另一枚典籍、角色)不动;star_tome 登记被消费(无呈现面路径 = 消费 +
  披露);时点分歧 / 范围口径 / 溢出归位模型三披露键在场;
- 溢出在场(``overflow_warning`` 真 ∧ ``overflow_card`` 非空):被清槽 = empty、
  overflow 两字段不动(sim 溢出模型 as-built 仅卖出腾槽归位)、零台账行;
- ``slots`` 空 / 越界 / kind 不符帧:不清 + ``open_tome_clear_skipped`` 披露
  (值 = 原因串),溢出在场时 overflow 两字段亦不动;指向合法空槽 = 幂等零写
  (bench 字段帧对象不变);
- 装配生命周期:``install_backend`` 后 ``overflow_pick_resolver(gs)`` 返回 empty
  槽件(sim 口径),``uninstall_backend`` 后返回 None(实机口径)。

直构 SimBackend(开局序列纯内存);断言依据全部来自测试自造 bench 视图。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_action_report import (
    overflow_pick_resolver,
)
from sr_od.application.currency_war.kernel.cw_action_report.zero_writes import (
    report_action_open_tome_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    Unit,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionOpenTomeParam
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_backend
from sr_od.application.currency_war.sim.cw_sim_backend import (
    ADVANCE_TRIGGER_KINDS,
    OPEN_TOME_CLEAR_SKIPPED,
    OPEN_TOME_OVERFLOW_MODEL,
    OPEN_TOME_SCOPE_NOTE,
    OPEN_TOME_TIMING_DIVERGENCE,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_base import obs_sig
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_SIG_OBS = obs_sig(group_id='test')
_SIG_LOGIC = ChannelSig(family='logic_action', actor='test')

#: 开局 HP 查表唯一实证档(RunConfig 字段注释;sim 构造期校验按档查表)。
_CFG = RunConfig(selected_difficulty='A8', enemy_difficulty=108)

#: 被点开典籍槽(0 基下标 2 = 物理槽 3)。
_K = 2
_OVERFLOW_CARD = '刃心'
_TOME_DISCLOSURE = f'{cw_sim_backend.OVERLAY_PARAM_PENDING}:star_tome'


def _make_backend() -> cw_sim_backend.SimBackend:
    return cw_sim_backend.SimBackend(seed=0, cfg=_CFG)


def _bench_view(tome_at: tuple[int, ...] = (), *,
                empty_at: int | None = None) -> BenchView:
    """9 槽席位视图:角色填充,指定下标放典籍 / 空槽。"""
    slots = [BenchSlot(kind='unit', unit=Unit(char_id=f'c{i}', star=1))
             for i in range(9)]
    for i in tome_at:
        slots[i] = BenchSlot(kind='tome')
    if empty_at is not None:
        slots[empty_at] = BenchSlot(kind='empty')
    return BenchView(slots=slots, capacity=9)


def _seed_overflow(backend: cw_sim_backend.SimBackend) -> None:
    """溢出在场前置(obs 渠道写;开局种子该两字段为 logic_rand 态,首写落
    ``logic_rand_outcome`` 预期内行——取走清空,使后续「零台账行」断言只对
    被测清席步生效)。"""
    backend.gs.observe(backend.gs.overflow_warning, True, sig=_SIG_OBS)
    backend.gs.observe(backend.gs.overflow_card, _OVERFLOW_CARD, sig=_SIG_OBS)
    consume_defect_sink()


@pytest.fixture(autouse=True)
def _clean_defect_board() -> None:
    """缺陷行缓冲进程级共享:用前取走残留、用后清空,防跨测试串染。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


def test_advance_dispatches_open_tome_with_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """分派接线:'open_tome' 在键集内且 decl.slots 原样送达 handler(集外
    trigger 的 ValueError 响亮面由现役 advance 契约承载,不另设反面锚)。"""
    assert 'open_tome' in ADVANCE_TRIGGER_KINDS
    backend = _make_backend()
    seen: list[tuple[int, ...]] = []
    monkeypatch.setattr(backend, '_on_open_tome', lambda slots: seen.append(tuple(slots)))
    backend.advance(WorldDecl(
        next_screen=backend._screen, trigger='open_tome', slots=(_K + 1,)))
    assert seen == [(_K + 1,)]


def test_clears_only_opened_slot_and_consumes_registration() -> None:
    """双典籍并存:仅被点开槽清为 empty,另一枚典籍与角色槽不动;star_tome
    登记被消费(无呈现面披露);三披露键在场。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.bench, _bench_view(tome_at=(0, _K)), sig=_SIG_OBS)
    outcome = report_action_open_tome_param(
        backend.gs, CwActionOpenTomeParam(slot=_K + 1), _SIG_LOGIC)
    assert outcome.world_decl is not None and outcome.world_decl.slots == (_K + 1,)

    backend._on_open_tome(outcome.world_decl.slots)

    slots = backend.gs.bench.value.slots
    assert slots[_K].kind == 'empty'
    assert slots[0].kind == 'tome'                       # 另一枚典籍留席
    assert slots[1].unit.char_id == 'c1'                 # 角色槽不动
    assert backend.gs.bench.source == 'observation'      # 引擎真值 obs 渠道
    assert backend.gs.screen_changes.pending == []       # 登记被消费
    assert backend.disclosures[_TOME_DISCLOSURE] == 'star_tome_options_unmodeled'
    assert backend.disclosures[OPEN_TOME_TIMING_DIVERGENCE] == \
        'sim_clear_at_open/live_clear_at_pick'
    assert OPEN_TOME_SCOPE_NOTE in backend.disclosures
    assert OPEN_TOME_OVERFLOW_MODEL in backend.disclosures
    assert OPEN_TOME_CLEAR_SKIPPED not in backend.disclosures


def test_overflow_in_play_clears_empty_leaves_overflow_fields() -> None:
    """溢出在场:被清槽 = empty、overflow 两字段不动(as-built 不归位模型)、
    零台账行。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.bench, _bench_view(tome_at=(_K,)), sig=_SIG_OBS)
    _seed_overflow(backend)

    backend._on_open_tome((_K + 1,))

    assert backend.gs.bench.value.slots[_K].kind == 'empty'
    assert backend.gs.overflow_warning.value is True
    assert backend.gs.overflow_warning.source == 'observation'
    assert backend.gs.overflow_card.value == _OVERFLOW_CARD
    assert consume_defect_sink() == []
    assert OPEN_TOME_CLEAR_SKIPPED not in backend.disclosures


@pytest.mark.parametrize(
    ('slots_payload', 'cur_kind', 'reason'),
    [
        ((), 'tome', 'slots_empty'),
        ((10,), 'tome', 'slot_out_of_range'),       # 越上界(9 槽)
        ((_K + 1,), 'supply_box', 'slot_kind_mismatch'),
        ((_K + 1,), None, 'slot_out_of_range'),      # 该槽 None(容量缩短/旧档形态)
    ],
)
def test_skips_clear_and_discloses(slots_payload: tuple[int, ...],
                                   cur_kind: str | None, reason: str) -> None:
    """slots 空 / 越界 / 该槽 None / kind 不符帧:不清 + 披露(值 = 原因串);
    溢出在场时 overflow 两字段亦不动。"""
    backend = _make_backend()
    view = _bench_view(tome_at=())
    slots = list(view.slots)
    slots[_K] = None if cur_kind is None else BenchSlot(kind=cur_kind)
    view = BenchView(slots=slots, capacity=9)
    backend.gs.observe(backend.gs.bench, view, sig=_SIG_OBS)
    _seed_overflow(backend)
    before = backend.gs.bench

    backend._on_open_tome(slots_payload)

    assert backend.gs.bench is before                 # 不清 = 字段帧不变
    assert backend.gs.bench.value is view
    assert backend.disclosures[OPEN_TOME_CLEAR_SKIPPED] == reason
    assert backend.gs.overflow_warning.value is True
    assert backend.gs.overflow_card.value == _OVERFLOW_CARD


def test_legal_empty_slot_is_idempotent() -> None:
    """指向合法空槽 = 幂等零写(bench 字段帧对象不变,无清席跳过披露)。"""
    backend = _make_backend()
    backend.gs.observe(backend.gs.bench, _bench_view(tome_at=(0,), empty_at=_K),
                       sig=_SIG_OBS)
    before = backend.gs.bench

    backend._on_open_tome((_K + 1,))

    assert backend.gs.bench is before
    assert OPEN_TOME_CLEAR_SKIPPED not in backend.disclosures


def test_install_backend_wires_overflow_pick_resolver() -> None:
    """装配生命周期锁:install_backend 后解析槽返 empty 槽件(sim 口径),
    uninstall_backend 后返 None(实机口径);与 rng 提供槽同生命周期。"""
    backend = _make_backend()
    assert overflow_pick_resolver(backend.gs) is None
    install_backend(backend)
    try:
        assert overflow_pick_resolver(backend.gs) == BenchSlot(kind='empty')
    finally:
        uninstall_backend()
    assert overflow_pick_resolver(backend.gs) is None
