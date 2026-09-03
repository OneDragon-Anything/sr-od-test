"""W971 P3a 开局序列与 overlay 族 op 行为锁(cw_flow 新包;P3b 接线前离线验证)。

覆盖面(每 op ≥1 条行为测试;离线桩手法 = test_cw_shop_refresh 同款:
FixtureController 假游戏 + 替身 handler + round_by_* 判定替身 + fast_sleep):
- BriefingOp:内联简报观察直写 session(P3b;P3a 委托壳已升级);非简报屏 fail。
- PlaneTransitionOp:提示命中 → 点「区域-空白点击」+ 验提示消失;提示未现 fail。
- WaitOneOneOp:锚命中即成功;假时钟验 ~10s 超时留证 fail。
- OpeningSequence:首帧分流纯函数 + 壳顺序执行/从中段续走。
- 七 overlay op(六委托 + CwScreenBookcard 直写):入口识别 + 委托执行 + 固定时长交回。

测试纪律:零真实副作用(save_screenshot/park_cursor 替身;台账不触)、
execute() 包 fast_sleep、运行态用 enter/reset_running_state。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from sr_od.application.currency_war.decision.cw_strategy import (
    CurrencyWarMatch,
    StrategySession,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_FRAME = ('货币战争-备战', 'shop_closed')


def _require_frame(test_context: SrTestContext) -> None:
    if not test_context.has_screen(*_FRAME):
        pytest.skip(f'存档截图缺失:screens/{_FRAME[0]}/{_FRAME[1]}.webp')


class _FakeSubOp:
    """替身子 op/handler:execute() 返回预置成功/失败(记录执行次数)。"""

    def __init__(self, ok: bool = True):
        self._ok = ok
        self.executed = 0

    def execute(self) -> Any:
        self.executed += 1
        return SimpleNamespace(success=self._ok,
                               status='stub-ok' if self._ok else 'stub-fail',
                               data=None)


class _StubStrategy:
    """替身策略:decide_star_tome 记录调用并返回预置下标。"""

    def __init__(self, idx: int = 0):
        self.idx = idx
        self.calls: list[list[str]] = []

    def decide_star_tome(self, names: list[str], state, session, config) -> int:
        self.calls.append(list(names))
        return self.idx


def _watched(op_cls: type) -> Any:
    return type('W', (WatchdogOperationMixin, op_cls), {})


def _make_op(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
             op_cls: type) -> tuple[Any, FixtureController]:
    """装配被测 op:假游戏控制器 + 框架副作用替身(存图/移光标)。"""
    _require_frame(test_context)
    fc = FixtureController(test_context)
    fc.set_phases([{'frame': _FRAME}])
    monkeypatch.setattr(test_context, 'controller', fc)
    op = _watched(op_cls)(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    # FixtureController 缺 mouse_move(bug#1 缓解点击的 op 前置动作会触达)
    monkeypatch.setattr(fc, 'mouse_move', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc


def _stub_find(op: Any, monkeypatch: pytest.MonkeyPatch,
               hits: list[tuple[str, str]], misses_after: int | None = None) -> list[int]:
    """round_by_find_area 替身:命中集内成功;``misses_after`` 次成功后全失败
    (模拟「入口锚在、出口锚消失」的真转移)。返回成功调用计数容器。"""
    counter = [0]

    def _find(screen, screen_name: str, area_name: str, **k: Any) -> Any:
        if misses_after is not None and counter[0] >= misses_after:
            return op.round_fail('')
        counter[0] += 1
        if (screen_name, area_name) in hits:
            return op.round_success('')
        return op.round_fail('')

    monkeypatch.setattr(op, 'round_by_find_area', _find)
    return counter


def _run(op: Any) -> Any:
    enter_running_state(op.ctx)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


# ==================== BriefingOp ====================

def test_briefing_op_reads_and_writes_session(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁①简报观察链(P3b 内联改写):入口锚命中 → 读词缀/boss/难度直写
    session(ctx 信箱退役,唯一写点)→ 点「下一步」→ 出口验真转移成功。"""
    from sr_od.application.currency_war.operations.cw_flow import (
        briefing_op as briefing_mod,
    )
    from sr_od.application.currency_war.operations.cw_flow.briefing_op import (
        BriefingOp,
    )
    op, _fc = _make_op(test_context, monkeypatch, BriefingOp)
    # 入口锚命中 1 次后全失败 = 出口「标识消失」真转移。
    _stub_find(op, monkeypatch, [('货币战争-简报', '标识-本场对局首领')],
               misses_after=1)
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda *a, **k: op.round_success(''))
    monkeypatch.setattr(briefing_mod, 'read_affixes_with_pos',
                        lambda ctx, screen: [('火弱点', None)])
    monkeypatch.setattr(briefing_mod, 'read_bosses',
                        lambda ctx, screen: ['碎星王虫'])
    monkeypatch.setattr(briefing_mod, 'clean_boss_names_by_lcs', lambda bs: bs)
    monkeypatch.setattr(briefing_mod, 'read_briefing_enemy_difficulty',
                        lambda ctx, screen: 5)
    monkeypatch.setattr(BriefingOp, '_collect_affix_effects',
                        lambda self, aff: {})   # 采集 best-effort,本锁不覆盖
    monkeypatch.setattr(briefing_mod, 'cw_telemetry', SimpleNamespace(
        record_exogenous=lambda *a, **k: None))   # 遥测替身(零真实台账)
    monkeypatch.setattr(op, 'screenshot', lambda *a, **k: op.last_screenshot)
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_StubStrategy(), StrategySession()),
                        raising=False)

    result = _run(op)

    assert result.success, f'简报步应成功:{result.status!r}'
    session = test_context.cw_match.session   # type: ignore[union-attr]
    assert session.briefing_affixes == ['火弱点']
    assert session.briefing_bosses == ['碎星王虫']
    assert session.enemy_difficulty == 5


def test_briefing_op_mark_miss_fails_without_read(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁②入口识别不中(非简报屏)→ fail 且不做观察/点击(编排壳按步分流)。"""
    from sr_od.application.currency_war.operations.cw_flow.briefing_op import (
        BriefingOp,
    )
    op, _fc = _make_op(test_context, monkeypatch, BriefingOp)
    _stub_find(op, monkeypatch, [])   # 锚恒不命中
    clicked: list[int] = []

    def _no_click(*a: Any, **k: Any) -> Any:
        clicked.append(1)
        return op.round_success('')

    monkeypatch.setattr(op, 'round_by_find_and_click_area', _no_click)

    result = _run(op)

    assert not result.success and not clicked


# ==================== PlaneTransitionOp ====================

def test_plane_transition_clicks_blank_and_verifies(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁③位面过渡:提示命中 → 点「区域-空白点击」→ 提示消失 = 成功。"""
    from sr_od.application.currency_war.operations.cw_flow.plane_transition_op import (
        PlaneTransitionOp,
    )
    op, fc = _make_op(test_context, monkeypatch, PlaneTransitionOp)
    # 第 1 次判定(入口)= 提示在;第 2 次(出口验证)= 提示已消失
    _stub_find(op, monkeypatch,
               [('货币战争-位面过渡', '提示-点击空白继续')], misses_after=1)

    result = _run(op)

    assert result.success, f'过渡应成功:{result.status!r}'
    assert fc.click_hit_area('货币战争-位面过渡', '区域-空白点击'), (
        f'点击未落空白点击区:{[str(p) for p in fc.recorded_clicks]}')


def test_plane_transition_prompt_missing_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁④提示未现 = 该步不适用 → fail 交编排壳,不盲点。"""
    from sr_od.application.currency_war.operations.cw_flow.plane_transition_op import (
        PlaneTransitionOp,
    )
    op, fc = _make_op(test_context, monkeypatch, PlaneTransitionOp)
    _stub_find(op, monkeypatch, [])

    result = _run(op)

    assert not result.success
    assert fc.recorded_clicks == []


# ==================== WaitOneOneOp ====================

def test_wait_one_one_anchor_hit(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁⑤主判据:「备战阶段」锚命中即成功(不等固定 10s)。"""
    from sr_od.application.currency_war.operations.cw_flow.wait_one_one_op import (
        WaitOneOneOp,
    )
    op, _fc = _make_op(test_context, monkeypatch, WaitOneOneOp)
    _stub_find(op, monkeypatch, [('货币战争-备战', '标识-备战阶段')])

    result = _run(op)

    assert result.success and result.status == '1-1 备战就绪'


def test_wait_one_one_timeout_leaves_evidence(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁⑥超时兜底:锚一直不现 → ~10s 后 fail 留证(假时钟,不真等)。"""
    from sr_od.application.currency_war.operations.cw_flow import (
        wait_one_one_op as mod,
    )
    from sr_od.application.currency_war.operations.cw_flow.wait_one_one_op import (
        WaitOneOneOp,
    )
    op, _fc = _make_op(test_context, monkeypatch, WaitOneOneOp)
    _stub_find(op, monkeypatch, [])
    clock = {'now': 0.0}

    def _fake_clock() -> float:
        clock['now'] += 2.0   # 每轮 +2s(>轮询间隔 1s,快进)
        return clock['now']

    monkeypatch.setattr(mod, '_monotonic', _fake_clock)

    result = _run(op)

    assert not result.success and '超时' in (result.status or ''), result.status
    assert clock['now'] >= 2.0 * 5   # 轮询至上界才退出,非首轮放弃


# ==================== 七 overlay 族 ====================

@pytest.mark.parametrize('op_cls,screen_name,mark_area', [
    # (RunNode 退役批:CwScreenMegastar 已内联,不再是委托形态——行为等价锁
    #  见 test_cw_runnode_retire.py,不入本委托 parametrize。)
    ('CwScreenPartner', '货币战争-列车同行', '标识-选择伙伴'),
    ('CwScreenWishTrial', '货币战争-祈愿试炼', '标识-祈愿试炼'),
    ('CwScreenPlanner', '货币战争-骇入策划', '标识-我来当策划'),
    ('CwScreenFortune', '货币战争-命运卜者强化', '标识-命运卜者'),
])
def test_overlay_op_delegates_and_settles(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    op_cls: str, screen_name: str, mark_area: str,
) -> None:
    """锁⑩委托 overlay:入口 id_mark 命中 → 委托现役 handler 一次 → 成功交回。"""
    import sr_od.application.currency_war.operations.cw_screen.cw_screen_overlay as overlay_mod
    cls: type = getattr(overlay_mod, op_cls)
    op, _fc = _make_op(test_context, monkeypatch, cls)
    _stub_find(op, monkeypatch, [(screen_name, mark_area)])
    fake = _FakeSubOp(ok=True)
    op.HANDLER_FACTORY = lambda ctx: fake   # type: ignore[method-assign]

    result = _run(op)

    assert result.success, f'{op_cls} 应成功:{result.status!r}'
    assert fake.executed == 1


def test_overlay_op_mark_miss_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁⑪入口识别不中 → fail 不委托(交上层重新分流,不在错屏盲跑)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_overlay import (
        CwScreenPartner,
    )
    op, _fc = _make_op(test_context, monkeypatch, CwScreenPartner)
    _stub_find(op, monkeypatch, [])
    fake = _FakeSubOp()
    op.HANDLER_FACTORY = lambda ctx: fake   # type: ignore[method-assign]

    result = _run(op)

    assert not result.success and fake.executed == 0


def test_bookcard_op_reads_and_picks_by_strategy(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁⑫星徽秘典(直写):OCR 卡名 → decide_star_tome → 点近邻星徽卡 area → 弹窗关。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_overlay import (
        CwScreenBookcard,
    )
    op, fc = _make_op(test_context, monkeypatch, CwScreenBookcard)
    _stub_find(op, monkeypatch,
               [('货币战争-星徽秘典弹窗', '标识-星徽秘典')], misses_after=1)
    strategy = _StubStrategy(idx=1)   # 选第 2 张(列车同行)

    def _fake_ocr(image, crop_first: bool = False, **k: Any) -> list[Any]:
        return [SimpleNamespace(data='仙舟星徽', x=600, w=120),
                SimpleNamespace(data='列车同行星徽', x=920, w=160)]

    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', _fake_ocr)
    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(strategy, StrategySession()),
                        raising=False)

    result = _run(op)

    assert result.success, f'秘典选卡应成功:{result.status!r}'
    assert strategy.calls and strategy.calls[0] == ['仙舟', '列车同行']
    assert fc.click_hit_area('货币战争-星徽秘典弹窗', '星徽卡-2'), (
        f'点击未落星徽卡-2:{[str(p) for p in fc.recorded_clicks]}')


def test_bookcard_op_mark_miss_fails(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """锁⑬秘典入口识别不中 → fail(交循环重新分流)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_overlay import (
        CwScreenBookcard,
    )
    op, fc = _make_op(test_context, monkeypatch, CwScreenBookcard)
    _stub_find(op, monkeypatch, [])

    result = _run(op)

    assert not result.success and fc.recorded_clicks == []


# ==================== 结构守卫 ====================

def test_overlay_ops_registry_covers_six() -> None:
    """锁⑭全集注册:OVERLAY_OPS = 06-overlays §4 表序六 op(武装箱选卡不经本族,主循环 0f 直派 HandleArmoryBoxDialog)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_overlay import (
        OVERLAY_OPS,
    )
    names = [c.__name__ for c in OVERLAY_OPS]
    assert names == ['CwScreenMegastar', 'CwScreenPartner', 'CwScreenWishTrial',
                     'CwScreenPlanner', 'CwScreenFortune', 'CwScreenBookcard']


def test_cw_flow_const_settle_values() -> None:
    """锁⑮完成承诺常量:DD-011 形态①固定 1.0s 两处 + 1-1 超时 10s(W971 口述值)。"""
    from sr_od.application.currency_war.operations.cw_flow import cw_flow_const
    assert cw_flow_const.BRIEFING_SETTLE_S == 1.0
    assert cw_flow_const.CW_OVERLAY_SETTLE_S == 1.0
    assert cw_flow_const.ONE_ONE_MAX_WAIT_S == 10.0
