"""商店买牌「未识别卡槽」感知竞态治本锁(W944)。

现场证据(局2,2026-08-31 06:32:50 停机留证帧 + .log/mcp_server.log 时序):
r7 刷新循环中游戏弹出模态弹窗「我来当策划/请选择一个骇入效果」压暗全屏
→ 商店牌行 SIFT miss(槽 1,2)→ 停机钩子 blind sleep(1.0s×2)防抖重读
无法自愈(弹窗是持续遮挡,不是瞬态帧)→ 停机留证。

修复语义(operations/prep/shop.py ``_wait_shop_row_stable``):
- 停机钩子防抖重读从 **blind sleep** 改 **判据化自愈**——每次重读前先等
  牌行区两帧指纹一致(与刷新分支 r325 同门同 rect),稳定即读,预算仍 2 次;
- 瞬态帧(刷新动画/settle)→ 门等到稳定后重读自愈,不停机;
- 模态弹窗压暗形态 → 画面本就稳定,门秒过,预算耗尽真停留证
  (弹窗处置归弹窗批域,shop_unk.flag 保留武装挂账)。

锁三条:
1. fixture 帧锁(单元级,合成帧走真实指纹基元):动画帧 → 稳定门 → 自愈;
2. op 级行为锁(w591 手法替身):钩子重读自愈 → 不停机;持续 unknown →
   预算耗尽真停 + flag 留证;
3. 守卫移除红检:摘掉稳定门(回退 blind sleep)→ 红。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

import pathlib
from typing import Any

import numpy as np
import pytest

from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_PREP = '货币战争-备战'
_ANCHOR = (_PREP, '备战标识-购买经验')

_NAMED = ['希儿', '景元', '布洛妮娅', '克拉拉', '杰帕德']


def _frame(changed: bool = False) -> Any:
    """合成 1080p 帧:基色 30;changed=True 时牌行区打亮块(指纹必异)。"""
    img: Any = np.full((1080, 1920, 3), 30, dtype=np.uint8)
    if changed:
        img[240:320, 320:1500] = 200
    return img


# ---------------------------------------------------------------------------
# 1. 稳定门单元锁(真实指纹基元 + 合成帧,无 fixture 文件依赖)
# ---------------------------------------------------------------------------

class _FakeOp:
    """最小 op 替身:仅暴露 _wait_shop_row_stable 用到的 screenshot()。"""

    def __init__(self, frames: list[Any]):
        self._frames = frames
        self._i = 0

    def screenshot(self) -> Any:
        f = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return f


def test_stable_gate_waits_animation_then_settles() -> None:
    """锁①a 动画帧序列:A→B(变)→B→B(连续同)→ 门判稳定放行。"""
    from sr_od.application.currency_war.operations.prep.shop import (
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(False), _frame(True), _frame(True), _frame(True),
                  _frame(True), _frame(True), _frame(True), _frame(True)])
    assert _wait_shop_row_stable(op) is True


def test_stable_gate_fast_path_minimum_observation() -> None:
    """锁①d(W952 P2-1)冻结帧 fast-path 最短观察 ≥1.0s。

    慢机冻结帧两次采样相同可短至 0.5s 即放行 → 非终帧误判稳定;
    修复后指纹相同仍须观察满 min_observe_s(对齐被替换 M35 单次 1.0s)
    才放行。实测放行耗时 ≥0.95s(0.25s 采样栅上的 1.0s 判据)。
    """
    import time as _t

    from sr_od.application.currency_war.operations.prep.shop import (
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(True)])   # 恒冻结帧:修复前 0.5s 即放行
    t0 = _t.monotonic()
    ok = _wait_shop_row_stable(op)
    elapsed = _t.monotonic() - t0
    assert ok is True
    assert elapsed >= 0.95, (
        f'冻结帧 fast-path 放行过快({elapsed:.2f}s < 0.95s):'
        'P2-1 回归(最短观察窗被摘)')


def test_stable_gate_timeout_has_compensation_wait() -> None:
    """锁①e(W952 P2-2)永变超时回退含补偿静置,不立读。

    调用方契约=「等稳后读」;超时(画面永变)若立即返回即「未稳即读」。
    修复后超时返回前静置 _SETTLE_TIMEOUT_COMPENSATE_S,实测 False 返回
    总耗时 ≥ max_wait_s + 补偿。
    """
    import time as _t

    from sr_od.application.currency_war.operations.prep.shop import (
        _SETTLE_TIMEOUT_COMPENSATE_S,
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(i % 2 == 0) for i in range(32)])
    t0 = _t.monotonic()
    ok = _wait_shop_row_stable(op, max_wait_s=0.4)
    elapsed = _t.monotonic() - t0
    assert ok is False
    assert elapsed >= 0.4 + _SETTLE_TIMEOUT_COMPENSATE_S - 0.05, (
        f'超时回退无补偿静置({elapsed:.2f}s):P2-2 回归(立读形态回流)')


def test_stable_gate_timeout_on_ever_changing_frames() -> None:
    """锁①b 永变帧序列 → 超时返回 False(调用方回退,不死等)。"""
    from sr_od.application.currency_war.operations.prep.shop import (
        _wait_shop_row_stable,
    )

    op = _FakeOp([_frame(i % 2 == 0) for i in range(32)])
    assert _wait_shop_row_stable(op, max_wait_s=0.4) is False


def test_stable_gate_screenshot_exception_offline_contract() -> None:
    """锁①c 离线契约:截图恒炸 → suppress 降级继续等,超时 False(不炸调用方)。"""
    from sr_od.application.currency_war.operations.prep.shop import (
        _wait_shop_row_stable,
    )

    class _BoomOp:
        def screenshot(self) -> Any:
            raise RuntimeError('offline')

    assert _wait_shop_row_stable(_BoomOp(), max_wait_s=0.3) is False


# ---------------------------------------------------------------------------
# 2. op 级行为锁(w591 替身手法:替身观测输入 + 替身计划源 + 台账隔离)
# ---------------------------------------------------------------------------

class _StubStrategy:
    """替身计划源:恒空 plan(波循环零动作 → 直接进钩子判定)。"""

    def __init__(self) -> None:
        self.calls = 0

    def update_target(self, state, session, config) -> None:
        pass

    def decide_prep(self, state, session, config) -> list[Any]:
        self.calls += 1
        return []


def _make_hook_op(test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  tmp_path: pathlib.Path,
                  wave_shop: list[str],
                  hook_rereads: list[list[str]],
                  writes: list[str]) -> tuple[Any, FixtureController, int]:
    """装配钩子路径被测 op。返回 (op, fixture_controller, 钩子重读次数容器)。

    ``wave_shop`` 是波循环顶 read_game_state 的商店名表(含 ''=未识别槽);
    ``hook_rereads`` 是停机钩子 read_shop_cards 的逐次返回(名表)。
    """
    from sr_od.application.currency_war.decision.cw_strategy import (
        CurrencyWarMatch,
        StrategySession,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState, ShopCard
    from sr_od.application.currency_war.obs import cw_observation as cwo
    from sr_od.application.currency_war.obs import cw_observation_gate as gate
    from sr_od.application.currency_war.operations.prep import shop as shop_mod
    from sr_od.application.currency_war.operations.prep.shop import BuyShopCards
    from sr_od.application.currency_war.telemetry import defects, recorder
    from sr_od.application.currency_war.telemetry import state as cw_telemetry

    class _Watched(WatchdogOperationMixin, BuyShopCards):
        pass

    # 台账隔离(不写真实 .debug;test_cw_w536 手法)
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True,
                                                   replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w944t')
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(defects, 'record_defect', lambda *a, **k: None)

    def _spy_write(self: pathlib.Path, data: Any, *args: Any, **kwargs: Any):
        writes.append(str(data))
        return len(data)

    monkeypatch.setattr(pathlib.Path, 'write_text', _spy_write)

    def _state() -> GameState:
        shop = [ShopCard(x=i, faction='?', name=n, cost=3, star=1)
                for i, n in enumerate(wave_shop)]
        return GameState(gold=10, plane=1, round_num=7, level=5, shop=shop)

    reads = {'n': 0}

    def _read_shop(*args: Any, **kwargs: Any):
        i = reads['n']
        reads['n'] += 1
        names = hook_rereads[min(i, len(hook_rereads) - 1)]
        return [ShopCard(x=j, faction='?', name=n, cost=3, star=1)
                for j, n in enumerate(names)]

    monkeypatch.setattr(shop_mod, 'read_game_state', lambda *a, **k: _state())
    monkeypatch.setattr(shop_mod, 'read_gold_opt', lambda *a, **k: 10)
    monkeypatch.setattr(shop_mod, 'read_gold', lambda *a, **k: 10)
    monkeypatch.setattr(shop_mod, 'read_shop_cards', _read_shop)
    monkeypatch.setattr(cwo, 'read_hp_opt', lambda *a, **k: None)
    monkeypatch.setattr(cwo, 'read_phase_round', lambda *a, **k: (1, 7))
    monkeypatch.setattr(gate, 'wait_stable_frame', lambda *a, **k: None)

    monkeypatch.setattr(test_context, 'cw_match',
                        CurrencyWarMatch(_StubStrategy(), StrategySession()))

    fc = FixtureController(test_context)
    fc.set_phases([{'frame': (_PREP, 'shop_closed')}])
    monkeypatch.setattr(test_context, 'controller', fc)

    op = _Watched(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda screen, screen_name, area_name, **k:
        op.round_success('') if (screen_name, area_name) == _ANCHOR
        else op.round_fail(''))
    monkeypatch.setattr(op, 'round_by_find_and_click_area',
                        lambda screen, screen_name, area_name, **k:
                        op.round_success(''))
    monkeypatch.setattr(op, 'round_by_ocr', lambda *a, **k: op.round_fail(''))
    monkeypatch.setattr(op, 'park_cursor', lambda *a, **k: None)
    monkeypatch.setattr(op, 'save_screenshot', lambda *a, **k: '<shot>')
    return op, fc, reads


def _execute(op) -> Any:
    enter_running_state(op.ctx)
    try:
        with fast_sleep():
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


@pytest.fixture()
def _require_fixture(test_context: SrTestContext) -> None:
    if not test_context.has_screen(_PREP, 'shop_closed'):
        pytest.skip(f'存档截图缺失:screens/{_PREP}/shop_closed.webp')


def test_hook_heals_after_settled_reread(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁②a 瞬态帧形态:波顶读含未识别槽 → 稳定门后重读全识别 → 不停机。

    修复前该形态靠 blind sleep 猜时长;修复后门等牌行区两帧一致再读
    (替身单帧恒同 → 门秒过),第 1 次重读全识别 → 正常收工,零 flag 零停。
    """
    writes: list[str] = []
    op, _fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=['', '景元', '', '克拉拉', '杰帕德'],
        hook_rereads=[_NAMED],
        writes=writes)

    result = _execute(op)

    assert result.success, f'自愈后应正常收工:status={result.status!r}'
    assert reads['n'] == 1, f'第 1 次重读即自愈,实际重读 {reads["n"]} 次'
    assert not any('HOOK-STOP' in w for w in writes), (
        f'自愈形态不得写停机 flag:{writes[:3]}')


def test_hook_persistent_unknown_stops_with_evidence(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁②b 模态弹窗压暗形态:预算 2 次重读仍 unknown → 真停 + flag 留证。

    弹窗遮挡不是瞬态帧,重读不会自愈——判据化门秒过(画面稳定)后预算
    耗尽照旧停机留证(用户 2026-08-24 裁决:未识别不能降级带病跑)。
    """
    writes: list[str] = []
    unk = ['', '景元', '', '克拉拉', '杰帕德']
    op, _fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=unk,
        hook_rereads=[unk, unk],
        writes=writes)

    result = _execute(op)

    assert not result.success, f'持续 unknown 应真停:{result.status!r}'
    assert '未识别卡槽' in (result.status or ''), result.status
    assert reads['n'] == 2, f'预算应恰 2 次重读,实际 {reads["n"]} 次'
    assert any('HOOK-STOP' in w and 'shop' in w for w in writes), (
        f'真停必须留证 flag:{writes[:3]}')


# ---------------------------------------------------------------------------
# 2c. match2 复盘候选形态锁(replay/matches/reviews/g_20260831_053546):
#     读空帧 → 标记跳过该槽(不点空槽)→ 不误停;持续读空才停机(锁②b)
# ---------------------------------------------------------------------------

def test_hook_unknown_slot_skipped_not_stopped(
    test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path, _require_fixture,
) -> None:
    """锁②c 同波含未识别槽:执行只买有身份牌(不点读空槽),重读自愈不停机。

    复盘候选形态「unknown 标记跳过该槽 + 持续读空才停机」的执行半部:
    plan 不发读空槽的 BuyCard → 执行侧零空槽点击;稳定门重读自愈 →
    op 正常收工。「持续读空才停机」半部由锁②b 承载(预算耗尽真停)。
    """
    from sr_od.application.currency_war.kernel.cw_obs_core import (
        shop_card_click_points,
    )
    from sr_od.application.currency_war.kernel.cw_state import (
        BuyCard,
        ShopCard,
    )

    writes: list[str] = []
    op, fc, reads = _make_hook_op(
        test_context, monkeypatch, tmp_path,
        wave_shop=['', '景元', '布洛妮娅', '克拉拉', '杰帕德'],
        hook_rereads=[_NAMED],
        writes=writes)
    # 给替身策略注入「只买有身份牌(x≈1300 → 槽5)」的 plan
    test_context.cw_match.strategy.decide_prep = (
        lambda state, session, config: [
            BuyCard(card=ShopCard(x=1300, faction='?', name='杰帕德',
                                  cost=3, star=1))])

    result = _execute(op)

    assert result.success, f'跳过读空槽后应正常收工:{result.status!r}'
    assert reads['n'] == 1, f'重读自愈,实际重读 {reads["n"]} 次'
    assert not any('HOOK-STOP' in w for w in writes), (
        f'自愈形态不得写停机 flag:{writes[:3]}')
    expected = min(shop_card_click_points(test_context),
                   key=lambda p: abs(p.x - 1300))
    buys = [c for c in fc.recorded_clicks
            if abs(c.x - expected.x) <= 5 and c.y == expected.y]
    assert len(buys) == 1, (
        f'应恰好 1 次有身份牌点击@~({expected.x},{expected.y}),'
        f'recorded={[str(p) for p in fc.recorded_clicks]}')
    assert all(abs(c.x - expected.x) <= 5 for c in fc.recorded_clicks), (
        f'不得点击读空槽(槽1 rect x≈250 区):{[str(p) for p in fc.recorded_clicks]}')


# ---------------------------------------------------------------------------
# 3. 守卫移除红检(源码锁,手法同 test_cw_w515):摘掉稳定门 → 红
# ---------------------------------------------------------------------------

def test_guard_hook_uses_settle_gate_not_blind_sleep() -> None:
    """锁③ 钩子防抖必须走判据化稳定门;blind sleep 回流 = 红。

    W944 治本点:读卡失败的防抖重读在「帧稳定」判据下进行,不是猜时长
    的固定 sleep。摘掉 _wait_shop_row_stable 调用(或回退 sleep 等待)时,
    本锁红,防感知自愈被静默移除。
    """
    src = pathlib.Path(
        'src/sr_od/application/currency_war/operations/prep/shop.py'
    ).read_text(encoding='utf-8')
    # 稳定门存在且被钩子调用(调用形态:门 → 重读,紧邻)
    assert 'def _wait_shop_row_stable(' in src, '稳定门 helper 缺失'
    assert '_wait_shop_row_stable(self)' in src, '钩子未调用稳定门'
    # W952 P2-1:fast-path 最短观察窗在位(指纹相同仍须观察满 min_observe_s)
    assert 'min_observe_s' in src, 'P2-1 回归:fast-path 最短观察窗被摘'
    # W952 P2-2:超时回退补偿静置在位(超时返回前 sleep,不立读)
    assert 'time.sleep(_SETTLE_TIMEOUT_COMPENSATE_S)' in src, (
        'P2-2 回归:超时回退补偿静置被摘(立读形态回流)')
    # 钩子段不得回流 blind sleep(门到位前旧码形态:先 sleep 再重读)
    assert 'time.sleep(1.0)\n                _reshop' not in src, (
        '钩子防抖回流 blind sleep(摘门回归形态)')
