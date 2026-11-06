"""CW 屏 op 行为测试面(战斗等待败局标志键门 + 选择伙伴选选流序)。

两节归并自原两个主题文件(测试函数名全量保留,原文件已删):

1. 战斗等待 op 败局标志键门(原 test_cw_battle_wait_defeat_latch.py;
   判据面 = 迭代 2026-10-12-abolish-node-ordinal landing §3.3 + 设计
   §2.11 测试 7):键门 (位面, 轮) >= (2,5) 与旧 9 制序数门 (p-1)*9+r >= 14
   在边界值上逐值同判(含修饰局 (1,10) 形态),另两臂语义保持(负分量
   缺席不置一次性标志位 / 状态容器节点读口未观察 fail-closed 不置一次性标志位);
2. 选择伙伴选选流序(原 test_cw_partner_select_confirm_flow.py;事故
   机制单一源 = docs/game/screens/currency_war_choose_partner.md:旧
   「选中态 gate」全屏 OCR「已选择」恒误命中 → op 每轮只点置灰确认钮 →
   实机 P1-r1 十八连 fail ~12 分钟零推进):选选流序(先点候选后确认)
   + 确认被拒有界重试(脉冲恰跑满 CONFIRM_REJECT_MAX → 显式 fail)。
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.application.currency_war._cw_helpers import (
    cw4_session,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    NodeKey,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import CwActionPickPartnerParam
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    CwScreenBattleWait,
    SettlementState,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_partner import (
    CwScreenPartner,
)

# ============================================================
# 1. 战斗等待 op 败局标志键门
# ============================================================

_SIG_OBS = ChannelSig(family='obs', actor='TestDefeatLatch', mode='read')

#: 面板负分量形态(damage_base < 0 = 次级证据负分量在)。
_NEG_PNL = {'damage_base': -1, 'damage_unfinished_progress': None}


def _make_op(test_context, monkeypatch) -> CwScreenBattleWait:
    """battle_wait 裸实例(先例 = test_env_grants._make_op;
    ctx.cw_match 无 gs 属性 → 状态容器走 session 旁表兜底,与生产同取口
    gs_of_ctx)。"""
    session = cw4_session()
    st = SettlementState(battle_ts=1234.0, run_start_ts=time.monotonic(),
                         is_new_match=False)
    monkeypatch.setattr(test_context, 'cw_match',
                        SimpleNamespace(session=session), raising=False)
    op = CwScreenBattleWait.__new__(CwScreenBattleWait)
    op.ctx = test_context
    op._st = st
    return op


@pytest.mark.parametrize('pos', [(1, 10), (2, 1), (2, 4), (2, 5)])
def test_lock7_defeat_latch_gate_matches_old_t_gate(
        test_context, monkeypatch, pos) -> None:
    """败局标志键门与旧 t 门逐值对拍(设计 §2.11 测试 7):旧门
    (p-1)*9+r >= 14 在边界值上的判定 = 新键门 (p,r) >= (2,5) 的实际
    置一次性标志位行为,逐值不分叉。"""
    old_t = (pos[0] - 1) * 9 + pos[1]
    expected = old_t >= 14
    op = _make_op(test_context, monkeypatch)
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.node, NodeKey(plane=pos[0], round_num=pos[1], kind='battle'),
               evidence='t', sig=_SIG_OBS)

    op._defeat_latch_by_secondary(dict(_NEG_PNL))

    assert op._st.saw_defeat_settlement is expected, \
        f'{pos}: 新键门与旧 t 门(t={old_t})判定分叉'


def test_lock7_latch_requires_neg_and_node(test_context, monkeypatch) -> None:
    """门另两臂语义保持:面板负分量缺席不置一次性标志位(序位过门也不置);
    节点未观察(状态容器 node 读口 None)fail-closed 不置一次性标志位。"""
    op = _make_op(test_context, monkeypatch)
    gs = game_state_of(test_context.cw_match.session)
    gs.observe(gs.node, NodeKey(plane=2, round_num=5, kind='battle'),
               evidence='t', sig=_SIG_OBS)
    op._defeat_latch_by_secondary({'damage_base': 3})   # 非负分量
    assert op._st.saw_defeat_settlement is False

    op = _make_op(test_context, monkeypatch)            # 节点未观察
    op._defeat_latch_by_secondary(dict(_NEG_PNL))
    assert op._st.saw_defeat_settlement is False


# ============================================================
# 2. 选择伙伴选选流序
# ============================================================

_PARTNER_SCREEN = '货币战争-列车同行'
_OVERLAY_FIXTURE = '伙伴遮罩-未选中'
_BOARD_FRAME = ('货币战争-备战', 'deployed_2star')


class _NoSleep:
    """模块内 ``time`` 替身:点击后等待记录不真睡(fast_sleep 只盖
    op 框架的轮间等待,盖不到模块自己的 ``time.sleep``)。"""

    def __init__(self) -> None:
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)


def _make_watched_op(test_context, monkeypatch) -> CwScreenPartner:
    """真类 + 桩面装配:cw_match 桩(decide_partner 恒 idx=0;决策质量不在
    测试范围,守卫面测试 = test_screen_two_node_family 伙伴臂)、SIFT 立绘
    识别回落 label 名(跳过模板库加载)、模块内 time 不真睡。桩无 ``gs``
    属性 → chosen 写端经 ``getattr(match, 'gs', None)`` 跳过(两个测试零状态容器
    断言不受影响)。"""

    class _WatchedPartner(WatchdogOperationMixin, CwScreenPartner):
        pass

    monkeypatch.setattr(
        test_context, 'cw_match',
        SimpleNamespace(strategy=SimpleNamespace(
            decide_partner=lambda: CwActionPickPartnerParam(idx=0,
                                                            reason='stub'))),
        raising=False)
    op = _WatchedPartner(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        op, '_identify_portraits',
        lambda screen, cands: [n for n, _cx, _cy in cands])
    # 统一动作工厂批4:「点选候选 → 确认」脉冲链体迁 pick op 模块——
    # 模块内 time 替身随体迁移(替身跟随被迁体,测试的「不真睡」意图不变;
    # partner 模块本体已无直接 sleep)。本测试桩化的伙伴脉冲确认收尾
    # (partner reset 根因链)不读屏,桩面= 记录点击。
    import sr_od.application.currency_war.operations.cw_op.cw_pick_partner_action as pick_mod
    monkeypatch.setattr(pick_mod, 'time', _NoSleep())
    return op


def _run_execute(test_context, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _in_rect(point, rect) -> bool:
    return rect.x1 <= point.x <= rect.x2 and rect.y1 <= point.y <= rect.y2


def _rect_of(test_context, area_name: str):
    area = test_context.screen_loader.get_area(_PARTNER_SCREEN, area_name)
    assert area is not None and area.pc_rect is not None, (
        f'建档缺失:{_PARTNER_SCREEN}/{area_name}(测试依赖 screen_info area)')
    return area.pc_rect


@pytest.fixture()
def fixture_controller(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    """注入 FixtureController(monkeypatch 自动还原,防污染 session 级 ctx)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # partner op 点击链 = mouse_move + click(harness 未备 mouse_move 桩,
    # 本地补 no-op;点击记录只看 click)。
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    return ctrl


def test_partner_selects_candidate_before_confirm(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """选选流序测试:未选中帧上先点候选卡后点确认;确认后 overlay 关 → success。

    事故反形:旧 gate 误命中时首个(且唯一)click 落在置灰确认钮上、候选
    零点击 —— 本测试红 = 流序回退(未选先确认)或完成门失效。
    """
    if not test_context.has_screen(_PARTNER_SCREEN, _OVERLAY_FIXTURE):
        pytest.skip(f'存档截图缺失:screens/{_PARTNER_SCREEN}/{_OVERLAY_FIXTURE}.webp')
    if not test_context.has_screen(*_BOARD_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_BOARD_FRAME[0]}/{_BOARD_FRAME[1]}.webp')

    fixture_controller.set_phases([
        {
            # 确认 click 落在确认钮内 → 游戏接受,overlay 关(推进备战帧)。
            'frame': (_PARTNER_SCREEN, _OVERLAY_FIXTURE),
            'exit': ('on_click_in', _PARTNER_SCREEN, '按钮-确认选择'),
        },
        {'frame': _BOARD_FRAME},   # terminal:overlay 已关,完成门应判 success。
    ])
    op = _make_watched_op(test_context, monkeypatch)

    result = _run_execute(test_context, op)

    assert result.success, (
        f'选择伙伴未成功完成:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx} '
        f'clicks={fixture_controller.recorded_clicks}')

    strip = _rect_of(test_context, '候选-卡区')
    confirm = _rect_of(test_context, '按钮-确认选择')
    clicks = fixture_controller.recorded_clicks
    assert clicks, f'零点击记录:{clicks}'
    first = clicks[0]
    assert _in_rect(first, strip) and not _in_rect(first, confirm), (
        f'首个 click 必须是候选卡点选(非确认钮):{first} '
        f'clicks={clicks}')
    assert any(_in_rect(p, confirm) for p in clicks[1:]), (
        f'确认钮 click 缺失(先选后确认流序断裂):{clicks}')
    assert fixture_controller.phase_idx == 1, (
        f'确认后应推进到备战帧:phase_idx={fixture_controller.phase_idx}')
    assert op._watchdog_round_count <= 4, (
        f'成功路径轮次应 ≤4(点选→确认→完成门):{op._watchdog_round_count}')


def test_partner_confirm_rejected_bounded_retry(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """确认被拒有界重试测试:overlay 恒在(置灰确认被游戏拒)→ 脉冲恰
    CONFIRM_REJECT_MAX 次 → 显式 fail,点击有界、先于节点预算、看门狗零触发。

    事故反形:旧实现每执行烧满 10 轮(20 click)且 fail 原因无形态区分,
    外环无限重派 —— 本测试红 = 有界防线回退或失败语义丢失。
    """
    if not test_context.has_screen(_PARTNER_SCREEN, _OVERLAY_FIXTURE):
        pytest.skip(f'存档截图缺失:screens/{_PARTNER_SCREEN}/{_OVERLAY_FIXTURE}.webp')

    # 无 exit 的单 phase = 帧恒不变(确认被拒、overlay 不关的实机形态)。
    fixture_controller.set_phases([
        {'frame': (_PARTNER_SCREEN, _OVERLAY_FIXTURE)},
    ])
    op = _make_watched_op(test_context, monkeypatch)

    result = _run_execute(test_context, op)

    assert not result.success, (
        f'确认被拒形态不得假成功:{result!r}')
    assert '确认被拒' in (result.status or ''), (
        f'失败状态须含「确认被拒」(形态可判读):{result.status!r}')

    strip = _rect_of(test_context, '候选-卡区')
    confirm = _rect_of(test_context, '按钮-确认选择')
    clicks = fixture_controller.recorded_clicks
    card_clicks = [p for p in clicks if _in_rect(p, strip) and not _in_rect(p, confirm)]
    confirm_clicks = [p for p in clicks if _in_rect(p, confirm)]
    assert len(confirm_clicks) == CwScreenPartner.CONFIRM_REJECT_MAX, (
        f'确认脉冲应恰跑满上限 {CwScreenPartner.CONFIRM_REJECT_MAX} 次:'
        f'{len(confirm_clicks)} clicks={clicks}')
    assert len(card_clicks) == CwScreenPartner.CONFIRM_REJECT_MAX, (
        f'未选中实证下每脉冲都应重点选候选:{len(card_clicks)} clicks={clicks}')
    assert len(set(map(str, card_clicks))) == 1, (
        f'重入轮点位应稳定(决策一次,防跨轮换候选):{card_clicks}')
    # 轮次上限算术(两 node 形态,):
    # 检测游戏窗口 1 + 观察 1 + 脉冲 4 + 守卫 fail 1 = MAX + 3(原单 node
    # 形态无观察段 = MAX + 2)。测试的语义 = 显式退出先于节点预算耗尽,
    # 非轮次精确值。
    assert op._watchdog_round_count <= CwScreenPartner.CONFIRM_REJECT_MAX + 3, (
        f'应在节点预算(10)耗尽前显式退出:{op._watchdog_round_count}')
