"""零写动作族上报剧本测试(占席件「开件零写 + 选卡清槽」两拍契约的可执行
设计说明;被测单一源 = ``zero_writes.py``——登记簿槽号载体
``cw_overlay_register`` 与包级注入槽 ``cw_action_report.__init__`` 经本
剧本覆盖,不另立镜像测试)。

锁的设计约定:
- 瞬态窗主剧本(典籍链):开件上报零写(bench 留 observation 源,弹窗期
  重观察零失配)→ 登记携被点开槽 + 声明携槽 → 选卡上报消费登记 logic 清
  该槽(他槽不动)→ 全空实读零缺陷零 andon。真失配路由本体由
  ``kernel/cw_game_state/test_observe_rand_route.py`` 锁定,本文件不设反面锚
  (反面锚不运行本批新码 = 冗余锁);
- 选卡清槽出口:双件并存仅清被点开槽;登记缺位 / slot None / 登记槽 None
  (容量缩短·旧档回放形态)/ 槽 kind 不符 → 不清 + ``pick_open_slot_uncleared``
  披露行(evidence 后缀区分出口)零写;
- 溢出告警在场(观察驱动防线): (a) 实机口径(注入槽未装)——bench 零写、
  overflow 两字段零写、披露 ``overflow_in_play``;随后归位视图 / 不归位
  视图实读均零缺陷零 andon(obs 覆盖 obs 静默);(b) sim 口径(注入槽装
  empty)——被腾槽写 empty、bench 翻 logic、overflow 两字段不动、写行
  evidence ``pick_open_slot_clear``(produced_by 非可观测面,以写行证据
   代替);不归位视图实读零缺陷;
- OpenBox 同构(open_box 登记携槽 + decl slots + pick_box_card 清槽 + 溢出
  在场 (a)(b) 各一例);
- 注入槽装配/卸载口:未装 = None;装配/卸载随 (a)(b) 覆盖。

断言依据全部来自测试自造输入(合成 bench 视图);缺陷行缓冲与 andon 钩子槽
经 monkeypatch 装/卸,防跨测试污染。
"""

from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel import cw_mismatch_policy
from sr_od.application.currency_war.kernel.cw_action_report import (
    overflow_pick_resolver,
    set_overflow_pick_resolver,
)
from sr_od.application.currency_war.kernel.cw_action_report.zero_writes import (
    PICK_OPEN_SLOT_UNCLEARED,
    report_action_open_box_param,
    report_action_open_tome_param,
    report_action_pick_box_card_param,
    report_action_pick_star_tome_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    GAME_STATE_SCHEMA_VERSION,
    BenchSlot,
    BenchView,
    ChannelSig,
    GameState,
    Unit,
    consume_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_overlay_register import (
    KIND_SCREEN_NAMES,
    consume_screen_change,
    register_screen_change,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionOpenBoxParam,
    CwActionOpenTomeParam,
    CwActionPickBoxCardParam,
    CwActionPickStarTomeParam,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl

_SIG_LOGIC = ChannelSig(family='logic_action', actor='test')
_SIG_OBS = ChannelSig(family='obs', actor='test', screen='货币战争-备战',
                      mode='read')

#: 溢出在场剧本的被腾槽(0 基下标 2 = 物理槽 3)。
_K = 2
_OVERFLOW_CARD = '刃心'


def _gs() -> GameState:
    return GameState(schema_version=GAME_STATE_SCHEMA_VERSION)


def _unit(char_id: str = '那刻夏') -> BenchSlot:
    return BenchSlot(kind='unit', unit=Unit(char_id=char_id, star=1))


def _empty_view(capacity: int = 9) -> BenchView:
    return BenchView(slots=[BenchSlot(kind='empty')] * capacity,
                     capacity=capacity)


def _full_view_tome_at(k: int) -> BenchView:
    """9/9 满、槽 k(0 基)= 典籍的席位视图。"""
    slots = [_unit(f'c{i}') for i in range(9)]
    slots[k] = BenchSlot(kind='tome')
    return BenchView(slots=slots, capacity=9)


@pytest.fixture(autouse=True)
def _clean_defect_board() -> None:
    """缺陷行缓冲进程级共享:用前取走残留、用后清空,防跨测试串染。"""
    consume_defect_sink()
    yield
    consume_defect_sink()


@pytest.fixture
def andon_rows(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """andon 钩子槽装/卸(monkeypatch 自动还原缺省关)。"""
    rows: list[dict] = []
    monkeypatch.setattr(cw_mismatch_policy, '_ANDON_HOOK', rows.append)
    return rows


def test_tome_transient_window_zero_andon_chain(andon_rows: list[dict]) -> None:
    """瞬态窗主剧本(典籍为备战栏唯一非空槽 = 全空形态走通的阻断形态):
    开件零写 → 弹窗期重观察零失配 → 选卡清槽 → 全空实读零缺陷零 andon
    (「弹窗识别 miss 使备战环踩中瞬态窗 → 实读 tome 对 logic empty 真失配
    andon」这条停机链在新语义下不成立的复现锁)。"""
    gs = _gs()
    before = BenchView(slots=[BenchSlot(kind='empty')] * 2
                       + [BenchSlot(kind='tome')]
                       + [BenchSlot(kind='empty')] * 6, capacity=9)
    gs.observe(gs.bench, before, sig=_SIG_OBS)

    outcome = report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=3), _SIG_LOGIC)
    assert outcome.applied is True
    # 开件零写:bench 留 observation 源、典籍留席
    assert gs.bench.source == 'observation'
    assert gs.bench.value.slots[2].kind == 'tome'
    # 登记携被点开槽(物理槽 1 基)+ 声明携槽
    assert [(p.kind, p.slot) for p in gs.screen_changes.pending] == [('star_tome', 3)]
    assert isinstance(outcome.world_decl, WorldDecl)
    assert outcome.world_decl.trigger == 'open_tome'
    assert outcome.world_decl.slots == (3,)

    # 弹窗期重观察(识别 miss 使备战环踩中瞬态窗):同视图实读 → 零缺陷
    gs.observe(gs.bench, before, sig=_SIG_OBS)
    assert consume_defect_sink() == []
    assert andon_rows == []

    pick = report_action_pick_star_tome_param(
        gs, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    assert pick.applied is True
    assert gs.screen_changes.pending == []                       # 登记被消费
    assert gs.bench.value.slots[2].kind == 'empty'               # 被点开槽清
    assert gs.bench.source == 'logic'
    assert gs.bench.evidence == 'pick_open_slot_clear'

    # 选完离席的全空备战栏实读(logic empty 对 obs empty = 静默;修前
    # 直写缺失时该形态走观察写端 carry 保旧 → 滞留重发)
    gs.observe(gs.bench, _empty_view(), sig=_SIG_OBS)
    assert consume_defect_sink() == []
    assert andon_rows == []
    assert gs.bench.source == 'observation'
    assert gs.bench.value.slots[2].kind == 'empty'


def test_clear_only_opened_slot_dual_tome() -> None:
    """双典籍并存(「终身学习」跨位面累积形态)+ 他槽角色:仅清被点开槽,
    另一枚典籍与角色槽不动。"""
    gs = _gs()
    slots = [BenchSlot(kind='tome'), BenchSlot(kind='empty'),
             BenchSlot(kind='tome')] + [BenchSlot(kind='empty')] * 5 + [_unit()]
    gs.observe(gs.bench, BenchView(slots=slots, capacity=9), sig=_SIG_OBS)
    report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=3), _SIG_LOGIC)
    report_action_pick_star_tome_param(
        gs, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    assert gs.bench.value.slots[0].kind == 'tome'      # 未点开的一枚留席
    assert gs.bench.value.slots[2].kind == 'empty'
    assert gs.bench.value.slots[8] == _unit()          # 角色槽不动
    assert consume_defect_sink() == []


@pytest.mark.parametrize(
    ('case', 'suffix'),
    [('no_entry', 'no_entry'), ('slot_none', 'no_entry'),
     ('slot_out_of_range', 'slot_kind_mismatch'),
     ('slot_is_none', 'slot_kind_mismatch'),
     ('kind_mismatch', 'slot_kind_mismatch')],
)
def test_uncleared_exits_disclose_without_write(case: str, suffix: str) -> None:
    """四个不清槽出口(登记缺位 / 槽 None / 越界·该槽 None / kind 不符)
    → 不清 + 披露行(evidence 后缀区分)、零写(字段帧对象不变)。"""
    gs = _gs()
    if case != 'no_entry':
        register_screen_change(gs, 'star_tome', KIND_SCREEN_NAMES['star_tome'],
                               source='test',
                               slot={'slot_none': None,
                                     'slot_out_of_range': 9,
                                     'slot_is_none': 3,
                                     'kind_mismatch': 3}[case])
    if case in ('slot_out_of_range', 'slot_is_none'):
        # 容量缩短 / 旧档回放形态:槽表长度 3,下标 2 为 None
        gs.observe(gs.bench, BenchView(slots=[BenchSlot(kind='empty'),
                                              BenchSlot(kind='empty'), None],
                                       capacity=3), sig=_SIG_OBS)
    else:
        cur = (BenchSlot(kind='bookcard') if case == 'kind_mismatch'
               else BenchSlot(kind='tome'))
        gs.observe(gs.bench, BenchView(slots=[cur] + [BenchSlot(kind='empty')] * 8,
                                       capacity=9), sig=_SIG_OBS)
    before = gs.bench
    value_before = gs.bench.value

    outcome = report_action_pick_star_tome_param(
        gs, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    assert outcome.applied is True                        # 语义申报非拒绝
    assert gs.bench is before and gs.bench.value == value_before   # 零写
    rows = consume_defect_sink()
    assert [r['kind'] for r in rows] == [PICK_OPEN_SLOT_UNCLEARED]
    assert rows[0]['observed_evidence'] == f'{PICK_OPEN_SLOT_UNCLEARED}:{suffix}'


def test_overflow_in_play_live_no_write_then_reads_absorb(
        andon_rows: list[dict]) -> None:
    """溢出告警在场·实机口径(注入槽未装):选卡拍 bench 零写、overflow
    两字段零写、披露 overflow_in_play;随后归位视图 / 不归位视图实读均
    零缺陷零 andon——「点开 → 溢出件归位」未实证机制下不写让实读承接。"""
    gs = _gs()
    full = _full_view_tome_at(_K)
    gs.observe(gs.bench, full, sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    gs.observe(gs.overflow_card, _OVERFLOW_CARD, sig=_SIG_OBS)
    assert overflow_pick_resolver(gs) is None            # 未装 = 实机口径

    report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=_K + 1), _SIG_LOGIC)
    outcome = report_action_pick_star_tome_param(
        gs, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    assert outcome.applied is True
    assert gs.bench.source == 'observation'              # 零写留原源
    assert gs.bench.value.slots[_K].kind == 'tome'       # 典籍仍留席
    assert gs.overflow_warning.value is True
    assert gs.overflow_warning.source == 'observation'
    assert gs.overflow_card.value == _OVERFLOW_CARD
    rows = consume_defect_sink()
    assert [(r['kind'], r['observed_evidence']) for r in rows] == [
        (PICK_OPEN_SLOT_UNCLEARED, f'{PICK_OPEN_SLOT_UNCLEARED}:overflow_in_play')]

    # 归位视图:被腾槽 = 溢出件、告警解除 → obs 覆盖 obs 静默
    placed = list(full.slots)
    placed[_K] = _unit(_OVERFLOW_CARD)
    gs.observe(gs.bench, BenchView(slots=placed, capacity=9), sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, False, sig=_SIG_OBS)
    gs.observe(gs.overflow_card, '', sig=_SIG_OBS)
    assert consume_defect_sink() == [] and andon_rows == []

    # 不归位视图(另起一局同前置):被腾槽 = empty、告警仍在 → 同样静默
    gs2 = _gs()
    gs2.observe(gs2.bench, full, sig=_SIG_OBS)
    gs2.observe(gs2.overflow_warning, True, sig=_SIG_OBS)
    gs2.observe(gs2.overflow_card, _OVERFLOW_CARD, sig=_SIG_OBS)
    report_action_open_tome_param(gs2, CwActionOpenTomeParam(slot=_K + 1), _SIG_LOGIC)
    report_action_pick_star_tome_param(
        gs2, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    consume_defect_sink()
    kept = list(full.slots)
    kept[_K] = BenchSlot(kind='empty')
    gs2.observe(gs2.bench, BenchView(slots=kept, capacity=9), sig=_SIG_OBS)
    assert consume_defect_sink() == [] and andon_rows == []


def test_overflow_in_play_sim_writes_empty(andon_rows: list[dict]) -> None:
    """溢出告警在场·sim 口径(注入槽装 empty 槽件):被腾槽写 empty、bench
    翻 logic、overflow 两字段不动(as-built 不归位模型,零披露行);随后
    不归位视图实读零缺陷。装配/卸载口各一断言。"""
    gs = _gs()
    gs.observe(gs.bench, _full_view_tome_at(_K), sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    gs.observe(gs.overflow_card, _OVERFLOW_CARD, sig=_SIG_OBS)
    assert overflow_pick_resolver(gs) is None
    set_overflow_pick_resolver(lambda _gs: BenchSlot(kind='empty'))
    try:
        assert overflow_pick_resolver(gs) == BenchSlot(kind='empty')
        report_action_open_tome_param(gs, CwActionOpenTomeParam(slot=_K + 1), _SIG_LOGIC)
        report_action_pick_star_tome_param(
            gs, CwActionPickStarTomeParam(idx=0), _SIG_LOGIC)
    finally:
        set_overflow_pick_resolver(None)
    assert overflow_pick_resolver(gs) is None            # 卸载 = 实机口径

    assert gs.bench.value.slots[_K].kind == 'empty'
    assert gs.bench.source == 'logic'
    assert gs.bench.evidence == 'pick_open_slot_clear'
    assert gs.overflow_warning.value is True and gs.overflow_warning.source == 'observation'
    assert gs.overflow_card.value == _OVERFLOW_CARD and gs.overflow_card.source == 'observation'
    assert consume_defect_sink() == []                          # 写行即留痕,零披露

    kept = list(gs.bench.value.slots)
    gs.observe(gs.bench, BenchView(slots=kept, capacity=9), sig=_SIG_OBS)
    assert consume_defect_sink() == [] and andon_rows == []


def test_open_box_isomorphic_chain(andon_rows: list[dict]) -> None:
    """OpenBox 同构:开箱登记携被点开槽 + 声明携槽(trigger='open_box')+
    选卡清槽(kind 'supply_box');全空实读零缺陷零 andon。"""
    gs = _gs()
    before = BenchView(slots=[BenchSlot(kind='empty'), BenchSlot(kind='supply_box')]
                       + [BenchSlot(kind='empty')] * 7, capacity=9)
    gs.observe(gs.bench, before, sig=_SIG_OBS)
    outcome = report_action_open_box_param(gs, CwActionOpenBoxParam(slot=2), _SIG_LOGIC)
    assert outcome.applied is True
    assert gs.bench.source == 'observation'
    assert gs.bench.value.slots[1].kind == 'supply_box'   # 箱仍留席(零写)
    assert [(p.kind, p.slot) for p in gs.screen_changes.pending] == [('box_card', 2)]
    assert isinstance(outcome.world_decl, WorldDecl)
    assert outcome.world_decl.trigger == 'open_box'
    assert outcome.world_decl.slots == (2,)

    pick = report_action_pick_box_card_param(
        gs, CwActionPickBoxCardParam(idx=0), _SIG_LOGIC)
    assert pick.applied is True
    assert gs.screen_changes.pending == []
    assert gs.bench.value.slots[1].kind == 'empty'
    assert gs.bench.source == 'logic'
    assert gs.bench.evidence == 'pick_open_slot_clear'

    gs.observe(gs.bench, _empty_view(), sig=_SIG_OBS)
    assert consume_defect_sink() == [] and andon_rows == []


@pytest.mark.parametrize('sim_shape', [False, True])
def test_open_box_overflow_in_play(sim_shape: bool,
                                   andon_rows: list[dict]) -> None:
    """OpenBox 溢出在场 (a) 实机口径零写+披露 / (b) sim 口径写 empty、
    overflow 两字段不动——与典籍链同形。"""
    gs = _gs()
    slots = [_unit(f'c{i}') for i in range(9)]
    slots[_K] = BenchSlot(kind='supply_box')
    full = BenchView(slots=slots, capacity=9)
    gs.observe(gs.bench, full, sig=_SIG_OBS)
    gs.observe(gs.overflow_warning, True, sig=_SIG_OBS)
    gs.observe(gs.overflow_card, _OVERFLOW_CARD, sig=_SIG_OBS)
    report_action_open_box_param(gs, CwActionOpenBoxParam(slot=_K + 1), _SIG_LOGIC)
    if sim_shape:
        set_overflow_pick_resolver(lambda _gs: BenchSlot(kind='empty'))
    try:
        report_action_pick_box_card_param(
            gs, CwActionPickBoxCardParam(idx=0), _SIG_LOGIC)
    finally:
        if sim_shape:
            set_overflow_pick_resolver(None)
    if sim_shape:
        assert gs.bench.value.slots[_K].kind == 'empty'
        assert gs.bench.source == 'logic'
        assert consume_defect_sink() == []
    else:
        assert gs.bench.source == 'observation'
        assert gs.bench.value.slots[_K].kind == 'supply_box'   # 箱仍留席(零写)
        assert [r['observed_evidence'] for r in consume_defect_sink()] == [
            f'{PICK_OPEN_SLOT_UNCLEARED}:overflow_in_play']
    assert gs.overflow_warning.value is True
    assert gs.overflow_card.value == _OVERFLOW_CARD
    assert andon_rows == []


def test_overlay_register_slot_roundtrip_and_dedupe() -> None:
    """登记簿槽号载体:slot 透传 1 基不换算、回传被消费条目、未登记 =
    None、同 kind 去重命中丢弃后来条目。"""
    gs = _gs()
    register_screen_change(gs, 'star_tome', KIND_SCREEN_NAMES['star_tome'],
                           source='a', slot=4)
    register_screen_change(gs, 'star_tome', KIND_SCREEN_NAMES['star_tome'],
                           source='b', slot=7)           # 去重:后来条目丢弃
    entry = consume_screen_change(gs, 'star_tome')
    assert entry is not None and entry.slot == 4 and entry.source == 'a'
    assert consume_screen_change(gs, 'star_tome') is None
    register_screen_change(gs, 'fortune', KIND_SCREEN_NAMES['fortune'], source='c')
    assert consume_screen_change(gs, 'fortune').slot is None   # 非占席件恒 None
