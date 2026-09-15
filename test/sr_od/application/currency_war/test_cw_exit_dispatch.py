"""退出链三分发结构行为锁(cw-exit-dispatch 落地 3.2,landing §3.2 ①-⑥)。

出处 = docs/develop/sr_od/application/currency_war/changes/2026-09-15-cw-exit-dispatch/
design.md §2.1(判定序表/默认委托/互踢推演)。真帧 fixture 驱动、真建档识别链,
FixtureController 记录点击。CwLoop 在委托锁①⑤中桩化(边界 op,内部行为不在
本锁范围);停机位行为由锁⑥直跑真 CwLoop 覆盖(免战帧 = 旧穿透双锚判否、
新名单判是的分歧点)。

- ① 列车同行事故帧(2026-09-15 卡死形态)→ 路由走默认委托,零「备战退局发起」;
- ② 免战帧 → 直接退局发起(屏名白名单,非锚判定);
- ③ 干净备战帧 → 直接退局发起;
- ④ 敌人信息浮层帧 → 点关闭回路由(⑤唯一特判,不走委托);
- ⑤ 认不出帧 → 数拍重试后按计数判战斗中(右上 X),全程无 CwLoop 委托
  (⑥链的「委托一次 CwLoop」步骤已删,设计 §2.1);
- ⑥ 委托后 A 类画面立即交还(停机位与路由③同源常量,无往返)。
"""
from __future__ import annotations

import pytest
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.operations.cw_entry import (
    cw_entry_exit as exit_mod,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    CwEntryExit,
)
from sr_od.application.currency_war.operations.cw_loop import CwLoop

_PARTNER_SCREEN = '货币战争-列车同行'
_PARTNER_FRAME = '伙伴遮罩-未选中'          # 2026-09-15 事故帧归档
_SKIP_SCREEN = '货币战争-备战-免战'
_SKIP_FRAME = '跳过态'
_PREP_SCREEN = '货币战争-备战'
_PREP_FRAME = 'deployed_2star'
_ENEMY_SCREEN = '货币战争-敌人信息浮层'
_ENEMY_FRAME = '详情页'
_DIALOG_SCREEN = '货币战争-中断挑战弹窗'
_LOBBY = ('货币战争-大厅', 'lobby')
_WORLD_FRAME = ('大世界', '普通')           # 非货币战争画面 = 全集识别恒 None


class _StubLoopResult:
    success = True
    status = '桩:已处理到可交还备战态'


class _StubCwLoop:
    """CwLoop 桩:记录委托调用;execute 时推进剧本(模拟 loop 处理到终点)。"""

    calls: int = 0

    def __init__(self, ctx, stop_at_prep: bool = False):
        self.stop_at_prep = stop_at_prep
        self.ctrl: FixtureController = ctx.controller

    def execute(self) -> _StubLoopResult:
        assert self.stop_at_prep, '退出链委托必须以 stop_at_prep=True 构造'
        _StubCwLoop.calls += 1
        self.ctrl._advance_phase()   # noqa: SLF001  桩内推进剧本到下一帧
        return _StubLoopResult()


def _make_watched_exit(test_context) -> CwEntryExit:
    class _WatchedExit(WatchdogOperationMixin, CwEntryExit):
        watchdog_max_rounds = 80

    op = _WatchedExit(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    return op


def _run_execute(test_context, op) -> object:
    enter_running_state(test_context)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _require_screens(test_context, *frames: tuple[str, str]) -> None:
    for screen, state in frames:
        if not test_context.has_screen(screen, state):
            pytest.skip(f'存档截图缺失:screens/{screen}/{state}.webp')


@pytest.fixture()
def fixture_controller(
    test_context,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    monkeypatch.setattr(ctrl, 'mouse_move', lambda pos: None, raising=False)
    # 委托边界桩:默认替换 CwEntryExit 模块内的 CwLoop 引用(锁⑥用真类时
    # 由该测试自行撤销本桩)。
    monkeypatch.setattr(exit_mod, 'CwLoop', _StubCwLoop)
    _StubCwLoop.calls = 0
    return ctrl


def test_lock1_partner_frame_delegates_without_prep_exit(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """锁①:列车同行事故帧 → 路由走默认委托,零「备战退局发起」触发。

    事故反形:旧穿透双锚穿透选伙伴弹窗误判干净备战 → 备战退局发起空转
    966 次;本锁红 = 表外画面判定回退(识别结果被丢弃)。
    """
    _require_screens(test_context, (_PARTNER_SCREEN, _PARTNER_FRAME), _LOBBY)
    fixture_controller.set_phases([
        {'frame': (_PARTNER_SCREEN, _PARTNER_FRAME)},
        {'frame': _LOBBY},   # 桩委托处理后画面直达大厅(终点)
    ])
    op = _make_watched_exit(test_context)

    result = _run_execute(test_context, op)

    assert result.success, (
        f'事故帧委托链未走通:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx}')
    assert _StubCwLoop.calls == 1, '列车同行帧必须恰好委托对局循环一次'
    assert not fixture_controller.click_hit_area(_PREP_SCREEN, '按钮-退出对局'), (
        '事故帧不得触发备战退局发起(穿透误判回退)')


def _full_exit_chain(first_frame: tuple[str, str]) -> list[dict]:
    """完整退局链剧本:首帧点门形图标 → 弹窗放弃 → 挑战失败 → 详情 →
    战报 → 大厅(所有退出过程画面建档 fixture)。"""
    return [
        {'frame': first_frame,
         'exit': ('on_click_in', _PREP_SCREEN, '按钮-退出对局')},
        {'frame': (_DIALOG_SCREEN, 'open'),
         'exit': ('on_click_in', _DIALOG_SCREEN, '按钮-放弃并结算')},
        {'frame': ('货币战争-挑战失败', 'failed'),
         'exit': ('on_click_in', '货币战争-挑战失败', '按钮-下一步')},
        {'frame': ('货币战争-结算-对局详情', 'default'),
         'exit': ('on_click_in', '货币战争-结算-对局详情', '按钮-下一页')},
        {'frame': ('货币战争-结算-战报', 'default'),
         'exit': ('on_click_in', '货币战争-结算-战报', '按钮-返回货币战争')},
        {'frame': _LOBBY},
    ]


def test_lock2_skip_state_frame_exits_directly(
    test_context, fixture_controller: FixtureController,
) -> None:
    """锁②:免战帧 → 直接退局发起(A 类名单,非锚判定),完整退局链走通。

    免战画面「出战」锚被「跳过」替换:旧备战档锚判定对免战恒 False,本锁
    红 = 免战被误判为需委托/认不出(名单判定回退)。
    """
    _require_screens(test_context, (_SKIP_SCREEN, _SKIP_FRAME),
                     (_DIALOG_SCREEN, 'open'),
                     ('货币战争-挑战失败', 'failed'),
                     ('货币战争-结算-对局详情', 'default'),
                     ('货币战争-结算-战报', 'default'), _LOBBY)
    fixture_controller.set_phases(
        _full_exit_chain((_SKIP_SCREEN, _SKIP_FRAME)))
    op = _make_watched_exit(test_context)

    result = _run_execute(test_context, op)

    assert result.success, (
        f'免战退局链未走通:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area(_PREP_SCREEN, '按钮-退出对局'), (
        '免战帧必须直接发起退局(点门形图标)')
    assert _StubCwLoop.calls == 0, 'A 类画面不得走委托'


def test_lock3_clean_prep_frame_exits_directly(
    test_context, fixture_controller: FixtureController,
) -> None:
    """锁③:干净备战帧 → 直接退局发起(不委托),完整退局链走通。"""
    _require_screens(test_context, (_PREP_SCREEN, _PREP_FRAME),
                     (_DIALOG_SCREEN, 'open'),
                     ('货币战争-挑战失败', 'failed'),
                     ('货币战争-结算-对局详情', 'default'),
                     ('货币战争-结算-战报', 'default'), _LOBBY)
    fixture_controller.set_phases(
        _full_exit_chain((_PREP_SCREEN, _PREP_FRAME)))
    op = _make_watched_exit(test_context)

    result = _run_execute(test_context, op)

    assert result.success, f'备战帧退局未走通:{result.status!r}'
    assert fixture_controller.click_hit_area(_PREP_SCREEN, '按钮-退出对局'), (
        '干净备战帧必须直接发起退局')
    assert _StubCwLoop.calls == 0, 'A 类画面不得走委托'


def test_lock4_enemy_info_frame_closed_inline(
    test_context, fixture_controller: FixtureController,
) -> None:
    """锁④:敌人信息浮层帧 → 点建档「按钮-关闭」回路由(⑤唯一特判)。"""
    _require_screens(test_context, (_ENEMY_SCREEN, _ENEMY_FRAME), _LOBBY)
    fixture_controller.set_phases([
        {'frame': (_ENEMY_SCREEN, _ENEMY_FRAME),
         'exit': ('on_click_in', _ENEMY_SCREEN, '按钮-关闭')},
        {'frame': _LOBBY},   # 关闭后画面回大厅(完成门 = 标识消失)
    ])
    op = _make_watched_exit(test_context)

    result = _run_execute(test_context, op)

    assert result.success, (
        f'敌人信息关闭链未走通:status={result.status!r} '
        f'phase_idx={fixture_controller.phase_idx}')
    assert fixture_controller.click_hit_area(_ENEMY_SCREEN, '按钮-关闭'), (
        '敌人信息浮层必须点建档关闭按钮(内联关闭)')
    assert _StubCwLoop.calls == 0, '敌人信息浮层是特判,不走默认委托'


def test_lock5_unknown_frame_battle_fallback_without_delegation(
    test_context, fixture_controller: FixtureController,
) -> None:
    """锁⑤:认不出帧 → 数拍重试后按计数判战斗中(右上 X 兜底),全程零委托。

    设计 §2.1 ⑥:miss 链的「委托一次 CwLoop」步骤已删——已建档画面在⑤
    全部有去处,认不出的未建档画面委托对局循环同样无力。本锁红 = 委托
    步骤复活或战斗兜底计数回退。
    """
    _require_screens(test_context, _WORLD_FRAME)
    fixture_controller.set_phases([
        {'frame': _WORLD_FRAME},   # 帧恒不变:数拍重试 → 判战斗中 → 右上 X
    ])
    op = _make_watched_exit(test_context)

    result = _run_execute(test_context, op)

    # 战斗暂停标识在认不出帧上永不出现 → 节点预算耗尽有界失败,属预期;
    # 锁的是路由行为而非链路终点。
    assert not result.success, '认不出帧不应假成功'
    assert _StubCwLoop.calls == 0, '认不出帧不得委托 CwLoop(冗余步骤须保持删除)'
    assert fixture_controller.click_hit_area('货币战争-战斗', '按钮-右上X'), (
        '连续认不出必须按计数判战斗中进右上 X 兜底')


def test_lock6_stop_at_prep_returns_immediately_on_class_a(
    test_context, monkeypatch: pytest.MonkeyPatch,
    fixture_controller: FixtureController,
) -> None:
    """锁⑥:委托后对局循环在 A 类画面(免战帧)立即交还,零分发动作。

    停机位与退出路由③共用同一常量(cw_screen_state.PREP_DIRECT_EXIT_SCREENS)
    → 两侧对「是否已到可交还态」结论恒一致,无互踢往返。免战帧 = 新旧判据
    分歧点:旧穿透双锚对免战恒 False(不停机即误入分发),新名单判是。
    """
    _require_screens(test_context, (_SKIP_SCREEN, _SKIP_FRAME))
    monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
    fixture_controller.set_phases([
        {'frame': (_SKIP_SCREEN, _SKIP_FRAME)},
    ])

    class _WatchedLoop(WatchdogOperationMixin, CwLoop):
        watchdog_max_rounds = 20

    op = _WatchedLoop(test_context, stop_at_prep=True)
    op._init_watchdog()  # type: ignore[attr-defined]

    result = _run_execute(test_context, op)

    assert result.success, (
        f'A 类画面必须立即交还:status={result.status!r}')
    assert op._iter == 1, (
        f'停机位必须在首轮命中(A 类画面零分发动作):iter={op._iter}')
    assert not fixture_controller.recorded_clicks, (
        '停机位命中前不得有任何分发点击'
        f':{fixture_controller.recorded_clicks}')


def test_route_table_has_no_battle_pause_dead_entry() -> None:
    """分发契约:ROUTE_BY_SCREEN 无「战斗暂停」死项。

    该屏无 id_mark,建档精准匹配结构性不可达,入表即死项;实际入口 =
    「战斗中点右上X」节点的直边(until 单锚命中「标识-战斗暂停」)。
    本断言锁公共分发表契约(运行时对象,非源码扫描)。"""
    assert '货币战争-战斗暂停' not in CwEntryExit.ROUTE_BY_SCREEN
    assert '货币战争-敌人信息浮层' not in CwEntryExit.ROUTE_BY_SCREEN, \
        '敌人信息浮层走⑤特判内联关闭,不经分发表'
