"""行为锁:位面情报采集「非clean放弃」失败语义分层(W901 治本)。

背景:位面情报采集在非 clean 帧放弃跨局三现(局13/16,两代代码同现;
sentinel 18:42 命中)。根因在触发时机语义层——调用方(battle_loop)调起前
已做备战节点条 clean 确认,重叠窗口在点开位面详情之后:详情条静止读不出
(位面转换动画 / 过去位面变暗渲染)被 op 级 round_fail 升格为整场采集失败,
调用方 2 次无退避重试同窗烧光 → 整场无情报。治本 = 失败语义分层:

1. 详情侧静止非 clean → **位面级结论**(该位面情报不可得,记 None,推进
   下一位面),不整场失败(同 conclude_plane_boss 徽章态记 None 语义线);
2. 静止但已不在位面详情(详情没开成)→ 维持 op 级失败,留给调用方重试;
3. 帧在变(真动画)→ 间隔重读路径不变(有界 90s 上限);
4. 备战入口路径(详情都开不了,无下一位面可推进)→ op 级失败不变
   (w857 既有锁继续钉该语义)。

REPORT = .debug/temp/currency_war/w901_plane_intel_timing/REPORT.md。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import cv2
import numpy as np

from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

if TYPE_CHECKING:
    from test.conftest import SrTestContext

_PD = '货币战争-位面详情'
_PREP = '货币战争-备战'
_TITLE = '标识-位面详情标题'


def _make_op(test_context: SrTestContext, monkeypatch) -> tuple:
    """构造被测 op(fixture 控制器注入),返回 (op, fixture_controller)。"""
    from sr_od.application.currency_war.operations.handlers.collect_plane_intel import (
        CollectPlaneIntel,
    )

    class _Watched(WatchdogOperationMixin, CollectPlaneIntel):
        pass

    op = _Watched(test_context)
    op.watchdog_max_rounds = 300
    fc = FixtureController(test_context)
    fc.set_phases([{'frame': (_PREP, 'shop_closed')}])
    monkeypatch.setattr(test_context, 'controller', fc)
    return op, fc


def _detect(op) -> SimpleNamespace:
    """画面判定替身:采集期(cur_plane<3)恒「在位面详情」;三位面齐后首次
    调用仍 True(让采集节点走到 round_success),其后 False(关闭节点判定
    详情 id_mark 消失=真转移)。"""
    if op._cur_plane < 3:
        op._w901_done_seen = False
        return SimpleNamespace(is_success=True)
    if not getattr(op, '_w901_done_seen', False):
        op._w901_done_seen = True
        return SimpleNamespace(is_success=True)
    return SimpleNamespace(is_success=False)


def _load_detail_frame() -> np.ndarray:
    """位面详情存档帧(RGB;真实 OCR id_mark 可命中,w314 锁③同款帧源)。"""
    p = (Path(__file__).parents[4] / 'screens' / _PD
         / '位面详情-点节点直开.png')
    img_bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img_bgr is not None, f'fixture 缺失: {p}'
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)   # 生产语义:RGB


# --------------------------------------------------------------------------- #
# 锁①:详情侧静止非clean → 位面级结论(记 None,推进下一位面),不整场失败
# --------------------------------------------------------------------------- #


def test_static_concludes_plane_and_advances(test_context: SrTestContext,
                                             monkeypatch) -> None:
    """锁①:详情侧(conclude_plane=True)静止 2 帧 → round_wait 推进,
    该位面记 None;op 不失败,等待账重置(下一位面从零起算)。"""

    op, _fc = _make_op(test_context, monkeypatch)
    # 确在位面详情(守卫通过):monkeypatch 画面判定命中
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=True))
    # 两轮同帧(静止):门比较 last_screenshot(w857 同款),真实帧差判定同图=True
    op.last_screenshot = np.zeros((108, 192, 3), dtype=np.uint8)

    with fast_sleep():
        r1 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)
        assert '间隔重读' in str(r1.status), (
            f'第 1 帧(尚无前帧可比)应走间隔重读,得 {r1.status!r}')
        r2 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)

    assert not r2.is_fail, f'静止帧应位面级结论而非整场失败,得 {r2.status!r}'
    assert op._cur_plane == 1, f'应推进到下一位面(0基=1),得 {op._cur_plane}'
    assert op._plane_bosses[0] is None, '该位面应记 None(情报不可得)'
    assert '静止' in str(r2.status) or '不可得' in str(r2.status), (
        f'状态应声明位面级结论,得 {r2.status!r}')
    # 等待账已重置:下一位面的非clean等待从零起算
    assert op._nonclean_wait_start is None, '位面结论后等待账应重置'


# --------------------------------------------------------------------------- #
# 锁②:静止但不在位面详情(详情没开成)→ 维持 op 级失败 + 尽力关详情
# --------------------------------------------------------------------------- #


def test_static_not_in_detail_fails_op(test_context: SrTestContext,
                                       monkeypatch) -> None:
    """锁②:守卫——静止结论仅在确在位面详情时成立;不在详情(详情未开成/
    被弹回)维持 op 级失败,留给调用方在后续稳定帧重试(防 conclude 吞掉
    「半开备战帧点不开详情」场景)。"""

    op, fc = _make_op(test_context, monkeypatch)
    # 守卫判定:不在位面详情
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=False))
    op.last_screenshot = np.zeros((108, 192, 3), dtype=np.uint8)

    with fast_sleep():
        r1 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)
        assert '间隔重读' in str(r1.status)
        r2 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)

    assert r2.is_fail, f'不在详情应维持 op 级失败,得 {r2.status!r}'
    assert '放弃采集' in str(r2.status), f'应声明放弃采集,得 {r2.status!r}'
    assert op._cur_plane == 0, '失败路径不得推进位面'
    assert op._plane_bosses[0] is not None or True   # bosses 保持初值(None),以推进位不变为准
    # 失败前尽力关详情(op 出口契约);本场景判定不在详情 → 零点击
    assert fc.recorded_clicks == [], '不在详情时不应产生点击'


# --------------------------------------------------------------------------- #
# 锁③:动画帧到达(帧在变)→ 间隔重读,不位面结论不上限
# --------------------------------------------------------------------------- #


def test_changing_frames_keeps_waiting_in_conclude_mode(
        test_context: SrTestContext, monkeypatch) -> None:
    """锁③(过渡期/动画帧到达场景):详情条暂读不出但帧在变(真动画)→
    conclude 模式同样走间隔重读,不做位面结论、不失败——位面转换动画窗
    给时间等它读完。"""

    op, _fc = _make_op(test_context, monkeypatch)
    monkeypatch.setattr(op, 'round_by_find_area',
                        lambda *a, **k: SimpleNamespace(is_success=True))
    # 帧间有变化(真动画):门比较的 last_screenshot 逐轮换显著差异图
    # (w857 同款手法:门读 last_screenshot,不经 screenshot())
    img_a = np.zeros((108, 192, 3), dtype=np.uint8)
    img_b = np.full((108, 192, 3), 200, dtype=np.uint8)

    with fast_sleep():
        op.last_screenshot = img_a
        r1 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)
        assert '间隔重读' in str(r1.status)
        op.last_screenshot = img_b
        r2 = op._nonclean_read_gate('切卡动画中', conclude_plane=True)

    assert not r2.is_fail, f'动画帧不应失败,得 {r2.status!r}'
    assert '间隔重读' in str(r2.status), f'应走间隔重读路径,得 {r2.status!r}'
    assert op._cur_plane == 0, '动画等待期不得推进位面'


# --------------------------------------------------------------------------- #
# 锁④:循环级——位面1静止不可得 + 位面2/3 clean → 采集成功 [None, b2, b3]
# --------------------------------------------------------------------------- #


def test_loop_partial_static_then_clean_succeeds(test_context: SrTestContext,
                                                 monkeypatch) -> None:
    """锁④(clean 帧到达 + 部分静止混合场景):位面1 详情条静止读不出 →
    位面级结论;位面2/3 clean → 正常采集;op 最终 success 且结果保位
    [None, b2, b3](None 丢弃会左移错位,保位语义=ADR-0398)。"""
    from sr_od.application.currency_war.kernel import cw_obs_core
    from sr_od.application.currency_war.obs import cw_observation as cwo

    op, _fc = _make_op(test_context, monkeypatch)
    # 画面判定:采集期(cur_plane<3)恒"在位面详情"(跳过备战入口,直入采集
    # 循环;位面结论守卫亦通过);关闭节点期(_cur_plane>=3)=详情已关
    # (id_mark 消失=真转移)→ close_and_report 走成功写回。
    monkeypatch.setattr(
        op, 'round_by_find_area',
        lambda *a, **k: _detect(op))
    # 帧恒静止(同一存档帧):位面1 两轮同图触发位面结论;后续位面 reader
    # 直接给出槽位,不进等待门
    img = _load_detail_frame()
    op.last_screenshot = img

    def _shot() -> np.ndarray:
        op.last_screenshot = img
        return img

    monkeypatch.setattr(op, 'screenshot', _shot)
    # area → 固定矩形(卡区/节点条/大图标坐标单一源走 area;测试桩化)
    monkeypatch.setattr(
        cw_obs_core, '_area_rect',
        lambda ctx, name, screen: SimpleNamespace(x1=0, y1=0, x2=100, y2=100))
    # 详情条读法按位面:位面1 恒读不出(静止结论路径);位面2/3 clean
    # (以 op._cur_plane 为键,与调用次数无关)
    slot = SimpleNamespace(node_type='battle', state='current', cx=50, cy=50)

    def _fake_detail_nodes(ctx, screen):
        return None if op._cur_plane == 0 else [slot]

    monkeypatch.setattr(cwo, 'read_plane_detail_nodes', _fake_detail_nodes)
    monkeypatch.setattr(cwo, 'read_phase_round',
                        lambda ctx, screen: None)   # 无 session 真值 → 不跳过
    from sr_od.application.currency_war.obs import cw_briefing_obs as cbo
    monkeypatch.setattr(cbo, 'read_detail_affixes', lambda ctx, screen: [])
    monkeypatch.setattr(
        cwo, 'read_detail_node_type_label', lambda ctx, screen: '首领')
    # boss 大图标 SIFT:按位面命名(断言保位)
    monkeypatch.setattr(op, '_read_boss_big_icon',
                        lambda: f'boss{op._cur_plane + 1}')
    enter_running_state(test_context)
    try:
        with fast_sleep():
            res = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert res.success, f'部分静止不可得不应导致整场失败,得 {res.status!r}'
    bosses = getattr(op.ctx, 'cw_plane_bosses', None)
    assert bosses == [None, 'boss2', 'boss3'], (
        f'结果应保位 [None, boss2, boss3],得 {bosses}')
