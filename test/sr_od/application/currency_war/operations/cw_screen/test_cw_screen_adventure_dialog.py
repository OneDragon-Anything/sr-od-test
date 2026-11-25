"""奇遇对话 op 剧本集(CwScreenAdventureDialog;迭代 2026-11-20-cw-p0-chain
tasks 3.3,design §2.2):

- 剧本 1 = 推进 → 分诊备战出口:点箭头推进(箭头消失 = 对话尽判效锚)
  → 分诊查备战标志命中 →「奇遇完成」交回主循环;partner_name 观察
  report 写入断言;
- 剧本 2 = 分诊茶歇出口:对话尽切茶歇分支帧(标题词面「享用茶歇」与
  建档锚 text=茶歇 共字命中)→「茶歇页交回主循环」(触发链 = 主循环
  下帧派茶歇 op,op 内不跳转);
- 剧本 3 = 两段式全链(mock 卡选项提供正面样本——真实帧三选一全负面
  为 R2/R2b 排除设计预期,全链走通用须 mock):点卡(report 补写 + idx
  零参读消费)→ 卡上确认钮出现 → 现读确认钮中心执行 → 生效判据
  (箭头复现)→ 交回主循环;卡选项 opts/xy 同序等长断言;
- 剧本 4 = 分诊全 miss 过渡帧自愈失败治理:连续全 miss → round_wait
  重跑 → TRIAGE_MISS_MAX 耗尽 fail;
- 剧本 5 = 两段式上限:卡恒不消失 → CARD_ATTEMPT_MAX 耗尽 fail。

帧资产 = 归档帧进仓(对话页 = 144711 / 选择卡 = 120053 / 选择卡确认 =
120117);备战帧 = 现役存档;茶歇分支帧 = 茶歇建档帧。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.cw_fixture_controller import CwFixtureController
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    game_state_of,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_adventure_dialog import (
    CwScreenAdventureDialog,
)

_ADV: str = '货币战争-奇遇对话'
#: 对话页(箭头在场;伙伴名牌「姬奇貓」在卡区读带)。
_F_DIALOG: tuple[str, str] = (_ADV, 'default')
#: 奇遇选择卡页(箭头消失,卡带三选一)。
_F_CARD: tuple[str, str] = (_ADV, '选择卡')
#: 选择卡确认态(选中卡展开,卡上确认钮在场)。
_F_CARD_CONFIRM: tuple[str, str] = (_ADV, '选择卡确认')
#: 备战帧(分诊备战出口)。
_F_PREP: tuple[str, str] = ('货币战争-备战', 'deployed_2star')
#: 茶歇分支帧(分诊茶歇出口;标题「享用茶歇」)。
_F_TEA: tuple[str, str] = ('货币战争-幕后茶歇', '分支选项')
#: 位面过渡帧(四出口全 miss 的过渡帧形态;现役存档 state 名)。
_F_TRANSITION: tuple[str, str] = ('货币战争-位面过渡', 'plane_1to2')

#: mock 卡选项(正面样本:R1 命中 + 返回排除;box 用选择卡帧实读卡位)。
_MOCK_UNITS: list[tuple[str, tuple[int, int, int, int]]] = [
    ('回复20小队生命值', (1146, 433, 1515, 534)),
    ('返回', (1145, 793, 1201, 823)),
]


def _require_frames(test_context: SrTestContext, *frames: tuple[str, str]) -> None:
    for screen_name, state in frames:
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _attach_gs(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    match = SimpleNamespace(session=SimpleNamespace(), gs=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


def _run_op(test_context: SrTestContext, op: CwScreenAdventureDialog):
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def test_dialog_advance_then_triage_prep_exit(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 1 推进 → 备战出口:partner_name report 写入 + 箭头推进 +
    备战标志命中交回。"""
    _require_frames(test_context, _F_DIALOG, _F_PREP)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_DIALOG,
         'exit': ('on_click_in', _ADV, '标识-对话箭头')},
        {'frame': _F_PREP},
    ])
    op = CwScreenAdventureDialog(test_context)
    result = _run_op(test_context, op)

    assert result.success, f'推进备战出口应 success,实际 {result.status!r}'
    assert '奇遇完成' in (result.status or ''), \
        f'出口 status 应为奇遇完成语义,实际 {result.status!r}'
    assert ctrl.click_hit_area(_ADV, '标识-对话箭头'), \
        f'应点击对话箭头推进,实际点击 {ctrl.recorded_clicks}'
    gs = game_state_of(test_context.cw_match.session)
    assert gs.adventure_partner_name.value == '姬奇貓', \
        (f'伙伴名应随观察 report 写入 game state,实际 '
         f'{gs.adventure_partner_name.value!r}')


def test_triage_tea_break_exit_hands_back(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 分诊茶歇出口:对话尽切茶歇分支帧 → 茶歇标题命中 → 交回
    主循环(下帧派茶歇 op;op 内零跳转代码)。"""
    _require_frames(test_context, _F_DIALOG, _F_TEA)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_DIALOG,
         'exit': ('on_click_in', _ADV, '标识-对话箭头')},
        {'frame': _F_TEA},
    ])
    op = CwScreenAdventureDialog(test_context)
    result = _run_op(test_context, op)

    assert result.success, f'茶歇出口应 success,实际 {result.status!r}'
    assert '茶歇' in (result.status or ''), \
        f'出口 status 应为茶歇交回语义,实际 {result.status!r}'


def test_card_phase_full_chain_reports_and_consumes_idx(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 3 两段式全链:分诊卡出口(report 补写)→ R1 idx 零参读点卡
    → 卡上确认钮出现 → 现读中心执行 → 生效判据(箭头复现)交回。"""
    _require_frames(test_context, _F_DIALOG, _F_CARD, _F_CARD_CONFIRM)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_DIALOG,
         'exit': ('on_click_in', _ADV, '标识-对话箭头')},
        # 选择卡帧:点卡(落 mock 点击框内)推进到确认态帧
        {'frame': _F_CARD,
         'exit': ('on_click_in', _ADV, '读区-奇遇卡按钮区')},
        # 确认态帧:点卡上确认钮推进回对话页(生效形态 = 箭头复现)
        {'frame': _F_CARD_CONFIRM,
         'exit': ('on_click_in', _ADV, '按钮-卡上确认')},
        {'frame': _F_DIALOG},
    ])
    op = CwScreenAdventureDialog(test_context)
    # mock 卡选项读带(正面样本;实读三选一全负面为 R2/R2b 设计预期,
    # 全链走通用须正面样本——读带 mock 单点,report/决策/点击全真链)
    monkeypatch.setattr(op, '_read_card_units',
                        lambda screen: list(_MOCK_UNITS))
    result = _run_op(test_context, op)

    assert result.success, f'两段式全链应 success,实际 {result.status!r}'
    gs = game_state_of(test_context.cw_match.session)
    opts = list(gs.adventure_card_opts.value or [])
    pts = list(gs.adventure_card_opts_xy.value or [])
    assert opts == ['回复20小队生命值', '返回'], \
        f'卡选项 report 应整表覆盖写入,实际 {opts!r}'
    assert len(pts) == len(opts), \
        f'坐标伴随域应同序等长,实际 pts={pts!r} opts={opts!r}'
    # 点卡落点 = opts_xy[0](R1 命中 idx 0 零参读消费)
    first = ctrl.recorded_clicks[-2]   # 倒序:点卡 → 点确认钮
    ox, oy = pts[0]
    assert (first.x, first.y) == (int(ox), int(oy)), \
        (f'点卡落点应 = adventure_card_opts_xy[0]({ox},{oy}),'
         f'实际 ({first.x},{first.y})')
    assert ctrl.click_hit_area(_ADV, '按钮-卡上确认'), \
        f'应点卡上确认钮,实际点击 {ctrl.recorded_clicks}'


def test_triage_all_miss_exhausts_to_fail(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 4 分诊全 miss:过渡帧不收敛 → round_wait 重跑 → 超限 fail
    (失败治理出口,有界)。"""
    _require_frames(test_context, _F_DIALOG, _F_TRANSITION)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_DIALOG,
         'exit': ('on_click_in', _ADV, '标识-对话箭头')},
        {'frame': _F_TRANSITION},
    ])
    op = CwScreenAdventureDialog(test_context)
    result = _run_op(test_context, op)

    assert not result.success, \
        f'分诊全 miss 不收敛应 fail 交外环,实际 {result.status!r}'


def test_card_phase_attempt_cap_fails(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 5 两段式上限:卡恒不消失(mock 恒非空 + 帧恒选择卡)→ 进入
    计数超 CARD_ATTEMPT_MAX → fail(有界,禁无界重走)。"""
    _require_frames(test_context, _F_DIALOG, _F_CARD)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        {'frame': _F_DIALOG,
         'exit': ('on_click_in', _ADV, '标识-对话箭头')},
        {'frame': _F_CARD},
    ])
    op = CwScreenAdventureDialog(test_context)
    monkeypatch.setattr(op, '_read_card_units',
                        lambda screen: list(_MOCK_UNITS))
    result = _run_op(test_context, op)

    assert not result.success, \
        f'两段式超限应 fail 交外环,实际 {result.status!r}'
    card_max = CwScreenAdventureDialog.CARD_ATTEMPT_MAX
    max_clicks = 1 + card_max
    assert len(ctrl.recorded_clicks) <= max_clicks, \
        (f'点击应有界(箭头推进 1 + 点卡 ≤{card_max} 次),'
         f'实际 {len(ctrl.recorded_clicks)} 次')
