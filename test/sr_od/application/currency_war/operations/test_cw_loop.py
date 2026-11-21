"""CwLoop 分发包装与外环 fail 防线测试(loop 镜像锚)。

锁设计约定(契约单一源 = ``cw_loop.py::CwLoop._dispatch_screen_op`` docstring
防线出口契约段 + skill ``references/flow/guards.md`` §1):

- ``op_fail_redispatch_tick`` 四态:推进型 ok 归零 / 清理型 ok 保窗 /
  同键累加 / 异键归一(防线计数根语义,链形归组修复依赖这四态);
- 清理型成功不清零计数窗(活锁根治):fail ↔ 清理型 ok 交替形态的计数
  能累到 ``OP_FAIL_REDISPATCH_LIMIT`` 响亮出口(实证活锁形态 = 备战环
  情报采集 fail 与位面详情关闭 ok 交替,旧「任一 ok 即归零」下永无出口);
- 推进型成功清零照旧(主路径不回归):真失败 → 重派 → 成功 → 继续的
  正向面原样;
- 链形分支(投资环境链)粘滞 fail(app 主路径默认):两 dispatch 同
  ``chain_key`` 归组,每直调烧 2 次 fail 事件(链首+链尾),第 3 直调链首
  达限 → 防线交接 ``round_success``(status 以 ``STATUS_HANDOFF_PREFIX``
  开头,后缀 = 计数键)经链首双条件透传为分支出口(链尾不空跑);
- 委托清理模式(``cleanup_delegate=True``,route⑤ 专用):耗尽维持
  ``round_fail`` 现状语义(exit 节点重试承接),链尾同样不空跑;
- 链形分支 ok 归零:链尾 ok(备战就绪)= 画面证实推进 → 整窗归零,粘滞
  不跨情节带病累加(轮内次序 = 链首 fail 先 tick、链尾 ok 后归零);
- 单发分支计数键 = journal 名(``chain_key`` 缺省 None 逐位不变),与
  链形键隔离。

演法(粘滞形态无法实机复现,按剧本演):投资环境帧喂 OCR 假件「投资环境
标题」——标题在入口门区内命中(过观察门)、又在卡名过滤带外被剔除 →
act 节点「空候选 OCR 读缺」fail,与现役申报的 fail 点一致;链尾在投资
环境帧上「备战阶段」识别标志恒 miss → 假时钟跨过超时线 fail。
"""

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.matcher.ocr.ocr_match_result import OcrMatchResult
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war.currency_war_config import CurrencyWarConfig
from sr_od.application.currency_war.operations import cw_loop as cw_loop_module
from sr_od.application.currency_war.operations.cw_entry import cw_entry_exit
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    CwEntryExit,
)
from sr_od.application.currency_war.operations.cw_loop import (
    STATUS_HANDOFF_PREFIX,
    STATUS_LOBBY_DONE,
    CwLoop,
    op_fail_redispatch_tick,
)
from sr_od.application.currency_war.operations.cw_screen.cw_flow_const import (
    ONE_ONE_MAX_WAIT_S,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_battle_wait import (
    SettlementState,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_wait_one_one import (
    CwScreenWaitOneOne,
)

#: 投资环境归档帧(3 选 1 modal,无「备战阶段」文本锚——链尾粘滞 fail 的物理前提)。
_INVEST_FRAME: tuple[str, str] = ('货币战争-投资环境', 'default')
#: 备战归档帧(有「备战阶段」文本锚——链尾 ok 归零的物理前提)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_2star')

#: 链形分支的链级计数键(与生产接线同值,单一源 = cw_loop.py 投资环境分支)。
_CHAIN_KEY = '投资环境链'


class _StubOp:
    """dispatch 包装直驱假件:``execute`` 返回带 success/status 的轻结果
    (非 OperationRoundResult 型 → ok 判定走 OperationResult.success 面,
    与生产画面 op 收敛形态同构)。"""

    def __init__(self, ok: bool, status: str = 'stub') -> None:
        self._ok = ok
        self._status = status

    def execute(self):
        return SimpleNamespace(success=self._ok, status=self._status)


def _make_dispatch_shell(test_context: SrTestContext,
                         monkeypatch: pytest.MonkeyPatch, tmp_path,
                         cleanup_delegate: bool = False) -> CwLoop:
    """防线直驱最小壳(先例 = ``_make_shell`` 的 ``__new__`` 形;假件 op
    不走识别链,免 OCR 桩):留证桩 + 项目根重定向零落盘,
    ``last_screenshot=None`` 使防线 ``op_fail_cap`` 截图走框架 None 早退。"""
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_loop.'
        'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.decision_frame_hooks.'
        'get_project_root', lambda: tmp_path)
    shell = CwLoop.__new__(CwLoop)
    shell.ctx = test_context
    shell.last_screenshot = None
    shell._cleanup_delegate = cleanup_delegate
    return shell


def _require_screens(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_INVEST_FRAME, _PREP_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _area_center(test_context: SrTestContext,
                 screen_name: str, area_name: str) -> tuple[int, int]:
    """建档区域中心(假件文本锚定在识别区中心,天然落入 rect 过滤)。"""
    area = test_context.screen_loader.get_area(screen_name, area_name)
    assert area is not None, f'画面档区域缺失: {screen_name}.{area_name}'
    rect = area.pc_rect
    return (rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2


def _overlap_in_zone(hit_rect, zone) -> float:
    """假件矩形落入识别区的面积占比(复刻生产 ``get_ocr_result_list`` 的
    rect 过滤口径:文本矩形 ≥70% 在识别区内才返回)。"""
    ix1, iy1 = max(hit_rect.x1, zone.x1), max(hit_rect.y1, zone.y1)
    ix2, iy2 = min(hit_rect.x2, zone.x2), min(hit_rect.y2, zone.y2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    base = (hit_rect.x2 - hit_rect.x1) * (hit_rect.y2 - hit_rect.y1)
    return ((ix2 - ix1) * (iy2 - iy1)) / base


def _install_ocr_stub(monkeypatch: pytest.MonkeyPatch,
                      test_context: SrTestContext,
                      entries_by_frame: dict[int, list[tuple[str, int, int]]],
                      ) -> None:
    """按帧分流的 OCR 假件,挂 ``get_ocr_result_list`` 单点——入口门
    (``find_area``)与 ``_read_options``/刷新计数的共同底层汇点,桩一处
    两个消费面同源;缺省帧回空(识别恒 miss,失败形态干净)。"""
    def _stub(image, color_range=None, rect=None, crop_first=False,
              threshold=0, merge_line_distance=-1):
        out = []
        for text, cx, cy in entries_by_frame.get(id(image), []):
            hit = OcrMatchResult(c=1.0, x=cx - 60, y=cy - 15, w=120, h=30,
                                 data=text)
            if rect is None or _overlap_in_zone(hit.rect, rect) > 0.7:
                out.append(hit)
        return out

    monkeypatch.setattr(test_context.ocr_service, 'get_ocr_result_list', _stub)


def _make_shell(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
                tmp_path, cleanup_delegate: bool = False,
                ) -> tuple[FixtureController, CwLoop]:
    """最小壳 + 零落盘桩面组装(先例 = test_cw_start_battle_action 弹窗主
    路径):``CwLoop.__new__`` 直调分派层,``_op_fail_streak_*`` 靠 getattr
    缺省自起;``last_screenshot=None`` 使防线 ``op_fail_cap`` 截图走框架
    None 早退(零落盘)。``cleanup_delegate`` = 耗尽出口模式开关
    (__new__ 不走 ``__init__``,由本组装显式落位;缺省 False 与生产构造
    默认一致,True = route⑤ 委托清理模式用例)。"""
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # 让 controller 帧缓存持有两帧并取回对象引用,供 OCR 假件按 id(image) 分流
    #(帧缓存按 (画面, 子态) 键控返回同一数组,识别链拿到的就是桩登记的那份)。
    ctrl.set_phases([{'frame': _INVEST_FRAME}])
    frame_invest = ctrl.current_frame
    ctrl.set_phases([{'frame': _PREP_FRAME}])
    frame_prep = ctrl.current_frame
    invest_cx, invest_cy = _area_center(
        test_context, '货币战争-投资环境', '标识-投资环境')
    prep_cx, prep_cy = _area_center(test_context, '货币战争-备战', '标识-备战阶段')
    _install_ocr_stub(monkeypatch, test_context, {
        # 投资环境帧:标题文本——门区内命中(过观察门);y 在卡名过滤带
        # [NAME_CY_LO, NAME_CY_HI] 外且属剔除表 → ``_read_options`` 空候选
        # → act「空候选 OCR 读缺」fail(fail 点与现役申报一致)。
        id(frame_invest): [('投资环境', invest_cx, invest_cy)],
        # 备战帧:「备战阶段」——链尾文本锚命中 → 链尾 ok(归零场景的通路)。
        id(frame_prep): [('备战阶段', prep_cx, prep_cy)],
    })
    # 决策帧留存证据桩 + 项目根重定向(分派包装留证面零落盘;先例同款)。
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_loop.'
        'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.decision_frame_hooks.'
        'get_project_root', lambda: tmp_path)
    # 链尾超时留证 no-op:链尾 op 的 last_screenshot 是 fixture 帧(非
    # None),超时路径 ``wait_one_one_timeout`` 不桩会真实写盘;no-op 与
    # 「留证失败不阻塞停机」语义兼容。
    monkeypatch.setattr(CwScreenWaitOneOne, 'save_screenshot',
                        lambda self, *a, **k: '')
    shell = CwLoop.__new__(CwLoop)
    shell.ctx = test_context
    shell.last_screenshot = None
    shell._cleanup_delegate = cleanup_delegate
    return ctrl, shell


def _install_fake_monotonic(monkeypatch: pytest.MonkeyPatch,
                            calls: list[float]) -> None:
    """等待 1-1 轮询假时钟:第 k 次调用返回 ``k × ONE_ONE_MAX_WAIT_S``。
    每轮观察首调设基、次调跨过超时线 → 链尾每轮恰 1 次 fail;新 op 实例
    下一对同构,跨直调自然续走。阈值取常量单一源,不手抄 10。"""

    def _fake() -> float:
        v = len(calls) * ONE_ONE_MAX_WAIT_S
        calls.append(v)
        return v

    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_screen.'
        'cw_screen_wait_one_one._monotonic', _fake)


def test_op_fail_redispatch_tick_four_states() -> None:
    """防线计数纯函数四态基线:推进型 ok 归零 / 清理型 ok 保窗 /
    同键 fail 累加 / 异键 fail 归一。"""
    # 推进型 ok(缺省 ok_clears=True)= 画面证实推进 → 整窗归零(键清 None)
    assert op_fail_redispatch_tick('任意键', 3, 'X', True) == (None, 0)
    # 清理型 ok(ok_clears=False)= 画面恢复不解除粘滞根因 → 窗口原样保留
    assert op_fail_redispatch_tick('X', 2, 'Y', True, ok_clears=False) == ('X', 2)
    # 同键 fail 累加
    assert op_fail_redispatch_tick('X', 2, 'X', False) == ('X', 3)
    # 异键 fail = 粘滞对象已换,新情节从 1 起算
    assert op_fail_redispatch_tick('X', 4, 'Y', False) == ('Y', 1)


def test_cleanup_ok_bounded_livelock(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """活锁根治(实证形态回放):fail(备战)↔ok(位面详情,清理型)交替,
    旧「任一 ok 即归零」下计数恒 ≤1 永不到限(同一阻断反复重派无出口);
    修后清理型 ok 保留窗口,计数跨交替累加,第 5 次 fail 达
    ``OP_FAIL_REDISPATCH_LIMIT`` 响亮出口(app 主路径 = 交接前缀 success,
    后缀 = 计数键),交替循环终止。"""
    shell = _make_dispatch_shell(test_context, monkeypatch, tmp_path)
    enter_running_state(test_context)
    streak_track: list[int] = []
    res_limit = None
    try:
        with fast_sleep(shell):
            for _round in range(CwLoop.OP_FAIL_REDISPATCH_LIMIT):
                res_fail = shell._dispatch_screen_op(
                    _StubOp(False, status='情报采集失败'),
                    journal_name='备战', frame_tag=None, wait=0)
                streak_track.append(shell._op_fail_streak_n)
                if res_fail.result != OperationRoundResultEnum.WAIT:
                    res_limit = res_fail
                    break   # 防线出口:交替循环终止(不再无限)
                # 清理型 ok(位面详情关闭):窗口应原样保留
                shell._dispatch_screen_op(
                    _StubOp(True, status='弹窗已关'),
                    journal_name='位面详情', frame_tag=None, wait=0)
                streak_track.append(shell._op_fail_streak_n)
    finally:
        reset_running_state(test_context, shell)

    assert streak_track == [1, 1, 2, 2, 3, 3, 4, 4, 5], (
        f'fail 后计数跨清理型 ok 单调累加(清理 ok 不清零),实际 {streak_track}')
    assert res_limit is not None, (
        '交替形态应在前 5 次 fail 内达限,不得无限继续')
    assert res_limit.result == OperationRoundResultEnum.SUCCESS, (
        f'app 主路径达限出口 = 交接 success,实际 {res_limit.result}')
    assert res_limit.status == f'{STATUS_HANDOFF_PREFIX}备战', (
        f'交接后缀 = 触发计数键(单发分支 = journal 名): {res_limit.status}')


def test_advancing_ok_resets_streak(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """主路径不回归:fail(备战)→ ok(战斗等待,推进型)→ 整窗归零照旧
    (真失败→重派→成功→继续的正向面);其后同键 fail 从 1 重数,新情节
    不带病累加。"""
    shell = _make_dispatch_shell(test_context, monkeypatch, tmp_path)
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            shell._dispatch_screen_op(
                _StubOp(False, status='首轮失败'),
                journal_name='备战', frame_tag=None, wait=0)
            n_fail1, key_fail1 = (shell._op_fail_streak_n,
                                  shell._op_fail_streak_key)
            shell._dispatch_screen_op(
                _StubOp(True, status='重派成功'),
                journal_name='战斗等待', frame_tag=None, wait=0)
            n_ok, key_ok = (shell._op_fail_streak_n,
                            shell._op_fail_streak_key)
            shell._dispatch_screen_op(
                _StubOp(False, status='新情节失败'),
                journal_name='备战', frame_tag=None, wait=0)
            n_fail2, key_fail2 = (shell._op_fail_streak_n,
                                  shell._op_fail_streak_key)
    finally:
        reset_running_state(test_context, shell)

    assert (n_fail1, key_fail1) == (1, '备战'), \
        f'首轮 fail 计 1: {(n_fail1, key_fail1)}'
    assert (n_ok, key_ok) == (0, None), \
        f'推进型 ok 归零照旧: {(n_ok, key_ok)}'
    assert (n_fail2, key_fail2) == (1, '备战'), \
        f'归零后新情节从 1 重数(不带病累加): {(n_fail2, key_fail2)}'


def test_mixed_partial_advance_sequence(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """边界混合序列:①清理型自己 fail 也计数(异键归一照旧);
    ②清理 ok 后窗口键保持原粘滞对象(同键 fail 继续累加);
    ③推进型穿插(武装箱选择,选卡=资源变化)即真推进,清零生效,
    其后新情节从 1 重数。"""
    shell = _make_dispatch_shell(test_context, monkeypatch, tmp_path)
    enter_running_state(test_context)
    track: list[tuple[int, str | None]] = []
    try:
        with fast_sleep(shell):
            # ①清理型 fail:计数照常起窗
            shell._dispatch_screen_op(
                _StubOp(False), journal_name='位面详情',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
            # 异键 fail 归一照旧:粘滞对象换为备战
            shell._dispatch_screen_op(
                _StubOp(False), journal_name='备战',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
            # ②清理型 ok:窗口键/计数原样保留
            shell._dispatch_screen_op(
                _StubOp(True), journal_name='位面详情',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
            # 同键 fail 在保留窗口上继续累加
            shell._dispatch_screen_op(
                _StubOp(False), journal_name='备战',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
            # ③推进型穿插(选卡成功 = 资源变化)→ 清零生效
            shell._dispatch_screen_op(
                _StubOp(True), journal_name='武装箱选择',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
            # 清零后新情节从 1 重数
            shell._dispatch_screen_op(
                _StubOp(False), journal_name='备战',
                frame_tag=None, wait=0)
            track.append((shell._op_fail_streak_n,
                          shell._op_fail_streak_key))
    finally:
        reset_running_state(test_context, shell)

    assert track == [
        (1, '位面详情'),   # 清理型 fail 起窗
        (1, '备战'),       # 异键 fail 归一
        (1, '备战'),       # 清理 ok 保窗(键/计数不动)
        (2, '备战'),       # 同键 fail 在保留窗口上累加
        (0, None),         # 推进型穿插清零
        (1, '备战'),       # 新情节重数
    ], f'混合序列各步窗口态: {track}'


def test_chain_sticky_fail_reaches_redispatch_limit(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """链形分支粘滞 fail 回归(app 主路径默认):同键双计使计数能达限,
    防线交接 success 经链首前缀条件透传为分支出口。粘滞形态每直调烧
    2 次 fail 事件(链首+链尾同键累加),直调 1-2 出口 WAIT、直调 3 链首
    达限(n=5)出口交接 success(status = 前缀 + 计数键)。"""
    _require_screens(test_context)
    ctrl, shell = _make_shell(test_context, monkeypatch, tmp_path)
    monotonic_calls: list[float] = []
    _install_fake_monotonic(monkeypatch, monotonic_calls)
    ctrl.set_phases([{'frame': _INVEST_FRAME}])
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            res1 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            n1 = shell._op_fail_streak_n
            key1 = shell._op_fail_streak_key
            res2 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            n2 = shell._op_fail_streak_n
            polls_before_limit = len(monotonic_calls)
            res3 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            n3 = shell._op_fail_streak_n
            polls_after_limit = len(monotonic_calls)
    finally:
        reset_running_state(test_context, shell)

    assert res1.result == OperationRoundResultEnum.WAIT, (
        f'直调 1 未达限,链尾默认映射交回主循环,实际 {res1.result}')
    assert (n1, key1) == (2, _CHAIN_KEY), f'直调 1 应烧 2 次 fail: {n1}'
    assert res2.result == OperationRoundResultEnum.WAIT, (
        f'直调 2 未达限,实际 {res2.result}')
    assert n2 == 4, f'直调 2 累计 4 次 fail: {n2}'
    assert res3.result == OperationRoundResultEnum.SUCCESS, (
        f'直调 3 链首达限,防线交接 success 应透传为分支出口,实际 {res3.result}')
    assert (res3.status or '').startswith(STATUS_HANDOFF_PREFIX), (
        f'交接出口 status 应带交接前缀(消费契约 = startswith): {res3.status}')
    assert res3.status == f'{STATUS_HANDOFF_PREFIX}{_CHAIN_KEY}', (
        f'交接后缀 = 触发计数键(链形分支 = chain_key): {res3.status}')
    assert n3 == 5, f'达限时计数 = 上限值 5: {n3}'
    assert polls_after_limit == polls_before_limit, (
        '达限透传早退,链尾不应空跑(等待 1-1 轮询时钟不应再走)')
    assert ctrl.recorded_clicks == [], (
        f'粘滞形态零盲点,不应有对外点击: {ctrl.recorded_clicks}')


def test_chain_sticky_fail_delegate_mode_keeps_fail(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """委托清理模式(``cleanup_delegate=True``,route⑤ 专用)耗尽维持
    FAIL:委托实例失败计数从零重算,若出口也翻转成交接 success,exit
    会误判清理完成 → 残局遗留且账面成功(静默失败)。锁 fail 出口 +
    链尾不空跑(链首双条件 FAIL 分支的真实来源)。"""
    _require_screens(test_context)
    ctrl, shell = _make_shell(test_context, monkeypatch, tmp_path,
                              cleanup_delegate=True)
    monotonic_calls: list[float] = []
    _install_fake_monotonic(monkeypatch, monotonic_calls)
    ctrl.set_phases([{'frame': _INVEST_FRAME}])
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            for _ in range(2):   # 直调 1-2 未达限,烧 4 次 fail 事件
                shell._dispatch_identity_screen(
                    '货币战争-投资环境', ctrl.current_frame)
            polls_before_limit = len(monotonic_calls)
            res3 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            n3 = shell._op_fail_streak_n
            polls_after_limit = len(monotonic_calls)
    finally:
        reset_running_state(test_context, shell)

    assert res3.result == OperationRoundResultEnum.FAIL, (
        f'委托模式直调 3 链首达限,出口应维持 FAIL,实际 {res3.result}')
    assert '连续 fail 超上限' in (res3.status or ''), (
        f'委托模式防线 status 应维持现状文案: {res3.status}')
    assert n3 == 5, f'达限时计数 = 上限值 5: {n3}'
    assert polls_after_limit == polls_before_limit, (
        '达限透传早退,链尾不应空跑(委托模式双条件 FAIL 分支接住)')
    assert ctrl.recorded_clicks == [], (
        f'粘滞形态零盲点,不应有对外点击: {ctrl.recorded_clicks}')


def test_chain_ok_reset_breaks_streak(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """链形分支 ok 归零回归:链尾 ok(备战就绪)= 画面证实推进 → 整窗
    归零,粘滞不跨情节带病累加。轮内次序断言:切帧直调内链首 fail 先
    tick(n=3)、链尾 ok 后归 0;其后新情节从 1 重数,再粘滞 2 直调不达限。"""
    _require_screens(test_context)
    ctrl, shell = _make_shell(test_context, monkeypatch, tmp_path)
    monotonic_calls: list[float] = []
    _install_fake_monotonic(monkeypatch, monotonic_calls)
    ctrl.set_phases([{'frame': _INVEST_FRAME}])
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)   # 粘滞直调 → n=2
            n_before_switch = shell._op_fail_streak_n
            # 切备战帧直调:链首门 miss fail(tick)→ 链尾锚命中 ok(归零)。
            ctrl.set_phases([{'frame': _PREP_FRAME}])
            real_tail_cls = cw_loop_module.CwScreenWaitOneOne
            tail_seen: list[int] = []

            class _TailProbe(real_tail_cls):
                """链尾构造探针:构造时点 = 链首 fail 已 tick、链尾 ok 未归
                零的轮内切片,快照防线计数锁「先 tick 后归零」次序。"""

                def __init__(self, ctx):
                    super().__init__(ctx)
                    tail_seen.append(int(getattr(shell, '_op_fail_streak_n', 0)))

            cw_loop_module.CwScreenWaitOneOne = _TailProbe
            try:
                res_switch = shell._dispatch_identity_screen(
                    '货币战争-投资环境', ctrl.current_frame)
            finally:
                cw_loop_module.CwScreenWaitOneOne = real_tail_cls
            n_after_reset = shell._op_fail_streak_n
            key_after_reset = shell._op_fail_streak_key
            # 再粘滞 2 直调(投资环境帧):新情节从 1 重数,不达限。
            ctrl.set_phases([{'frame': _INVEST_FRAME}])
            res_post1 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            res_post2 = shell._dispatch_identity_screen(
                '货币战争-投资环境', ctrl.current_frame)
            n_final = shell._op_fail_streak_n
    finally:
        reset_running_state(test_context, shell)

    assert n_before_switch == 2, f'切帧前粘滞计数: {n_before_switch}'
    assert res_switch.result == OperationRoundResultEnum.WAIT, (
        f'链首 fail 被吸收映射(未达限),链尾应照跑交回,实际 {res_switch.result}')
    assert tail_seen == [3], (
        f'链尾构造时点应见链首 fail 已 tick 的瞬时计数 3: {tail_seen}')
    assert n_after_reset == 0 and key_after_reset is None, (
        f'链尾 ok 后整窗归零: n={n_after_reset} key={key_after_reset}')
    assert res_post1.result == OperationRoundResultEnum.WAIT, (
        f'新情节直调 1 未达限,实际 {res_post1.result}')
    assert res_post2.result == OperationRoundResultEnum.WAIT, (
        f'新情节直调 2 未达限,实际 {res_post2.result}')
    assert n_final == 4, f'归零后新情节重数至 4(未达限): {n_final}'


def test_single_dispatch_streak_key_uses_journal_name(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """单发分支计数键回归:``chain_key`` 缺省 None → 计数键 = journal 名,
    与链形键隔离(33 处单发调用点零行为变化的键面锚)。"""
    _require_screens(test_context)
    ctrl, shell = _make_shell(test_context, monkeypatch, tmp_path)
    ctrl.set_phases([{'frame': _INVEST_FRAME}])
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            res1 = shell._dispatch_identity_screen(
                '货币战争-商店刷新概率表', ctrl.current_frame)
            res2 = shell._dispatch_identity_screen(
                '货币战争-商店刷新概率表', ctrl.current_frame)
    finally:
        reset_running_state(test_context, shell)

    assert shell._op_fail_streak_key == '商店刷新概率表', (
        f'单发分支计数键应为该 op journal 名: {shell._op_fail_streak_key}')
    assert shell._op_fail_streak_key != _CHAIN_KEY, (
        '单发键与链形键必须隔离')
    assert shell._op_fail_streak_n == 2, (
        f'fail 2 轮同键累加: {shell._op_fail_streak_n}')
    assert res1.result == OperationRoundResultEnum.WAIT, (
        f'单发未达限走默认映射,实际 {res1.result}')
    assert res2.result == OperationRoundResultEnum.WAIT, (
        f'单发未达限走默认映射,实际 {res2.result}')
    assert ctrl.recorded_clicks == [], (
        f'入口门 miss 即失败,零对外点击: {ctrl.recorded_clicks}')


def test_delegate_loop_constructs_cleanup_delegate(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """route⑤ 委托构造冒烟:delegate_loop 构造 CwLoop 必带
    ``cleanup_delegate=True``(委托清理模式唯一传参点)。漏传 = 默认
    app 主路径,委托耗尽出口翻转成交接 success,exit 节点会误判清理
    完成(res.success → round_success 重入路由)。"""
    captured: dict[str, bool] = {}

    class _CapturingLoop:
        """CwLoop 构造参数捕获假件(不执行真实委托;execute 即返交还成功)。"""

        def __init__(self, ctx, max_rounds=None, stop_at_prep=False,
                     cleanup_delegate=False) -> None:
            captured['stop_at_prep'] = stop_at_prep
            captured['cleanup_delegate'] = cleanup_delegate

        def execute(self) -> OperationResult:
            return OperationResult(success=True, status='已到可交还备战态')

    monkeypatch.setattr(cw_entry_exit, 'CwLoop', _CapturingLoop)
    exit_op = CwEntryExit(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(exit_op):
            res = exit_op.delegate_loop()
    finally:
        reset_running_state(test_context, exit_op)

    assert captured == {'stop_at_prep': True, 'cleanup_delegate': True}, (
        f'route⑤ 委托构造参数漂移: {captured}')
    assert res.result == OperationRoundResultEnum.SUCCESS, (
        f'委托交还 success 应走重入路由出口,实际 {res.result}')


@pytest.mark.parametrize('is_debug', [True, False],
                         ids=['debug_halt_prep', 'non_debug_handoff'])
def test_exit_status_texts_stable(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path, is_debug: bool) -> None:
    """交接判定载体出口文本稳定性锚(防漂移破坏 app 交接判定,与 cw_loop
    出口常量面联动):大厅出口常量字面锚(判定 = 全等匹配);max_rounds 无
    常量,停点分模式(is_debug 读取点 = loop 停点段)触发真实停点出口,
    断言两分支——True 出口含「停备战」锚且不带交接前缀(落 app「其余」
    分支留局采样,本锚防形态误漏进交接);False 出口带 ``STATUS_HANDOFF_
    PREFIX`` 前缀且标「停点重开」语义(落 app 异常交接分支,弃局回大厅)。
    两分支 is_debug 各自显式锁定(替换 env_config 为单字段桩,monkeypatch
    自动还原,零配置落盘)——禁依赖 conftest 缺省值。max_rounds 停点走
    真实 ``loop()`` 备战分支,识别面全桩(身份解析桩为未命中、备战认领桩
    为命中),零真实识别零落盘。"""
    monkeypatch.setattr(test_context, 'env_config',
                        SimpleNamespace(is_debug=is_debug))
    assert STATUS_LOBBY_DONE == '对局结束,回大厅', (
        f'大厅出口常量漂移(app 交接判定载体,两端同源): {STATUS_LOBBY_DONE}')

    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': _PREP_FRAME}])
    # 决策帧留存证据桩 + 项目根重定向(与 _make_shell 同面,零落盘)。
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.cw_loop.'
        'save_decision_frame', lambda *a, **k: None)
    monkeypatch.setattr(
        'sr_od.application.currency_war.operations.decision_frame_hooks.'
        'get_project_root', lambda: tmp_path)
    # 阶段一身份解析桩为未命中:真实全扫描对本用例是纯识别成本,且
    # 备战帧本不在阶段一清单(清单不含备战,判定归属两识别标志同帧)。
    monkeypatch.setattr(CwLoop, '_resolve_frame_identity',
                        lambda self, screen: (None, []))
    # 备战认领判定桩为命中(本用例目标 = 停点出口文本,非认领判定本身;
    # 真实判定 = prep_anchors_hit,由 flow 层测试覆盖)。
    monkeypatch.setattr(cw_loop_module, 'prep_anchors_hit',
                        lambda op, screen: True)
    shell = CwLoop.__new__(CwLoop)
    shell.ctx = test_context
    shell.last_screenshot = ctrl.current_frame
    shell._cleanup_delegate = False
    shell._iter = 2   # 跳过 iter1 预检与首读;非 10 倍数跳过焦点防线
    shell._stop_at_prep = False
    shell._max_rounds = 1
    shell._settle = SettlementState(rounds_done=1)
    enter_running_state(test_context)
    try:
        with fast_sleep(shell):
            res = shell.loop()
    finally:
        reset_running_state(test_context, shell)

    assert res.result == OperationRoundResultEnum.SUCCESS, (
        f'max_rounds 达标停点应 success,实际 {res.result}')
    if is_debug:
        assert '停备战' in (res.status or ''), (
            f'debug 停点出口文本应含「停备战」锚(app「其余」分支判定输入): {res.status}')
        assert not (res.status or '').startswith(STATUS_HANDOFF_PREFIX), (
            f'debug 停点不得落交接形态(留局采样语义): {res.status}')
    else:
        assert (res.status or '').startswith(STATUS_HANDOFF_PREFIX), (
            f'非 debug 停点出口应带交接前缀(app 异常交接形态判定输入): {res.status}')
        assert '停点重开' in (res.status or ''), (
            f'非 debug 停点出口应标停点重开语义: {res.status}')


# ===== 每次运行重建判据 + 战斗帧恢复检测门(design §2.4/§2.6 迁移面)=====

def _establish_ctx_container(test_context: SrTestContext,
                             opened_via: str):
    """生产漏斗真跑:入口链/兜底同款 establish(断言走新建分支并返回容器)。"""
    from sr_od.application.currency_war.strategies.impl.cw_strategy_manager import (
        establish_new_match,
    )
    established = establish_new_match(
        test_context, CurrencyWarConfig(test_context.current_instance_idx),
        opened_via)
    assert established, 'ctx.cw_match=None 前提下 establish 应走新建分支'
    return test_context.cw_match


class TestHandleInitRebuild:
    """每次运行重建判据保留-重建矩阵(design §2.4 六场景;镜像锚 =
    cw_loop.py::CwLoop.handle_init,判据单一源 = 2026-11-19-resume-rebuild
    design §2.4)。演法 = 生产初始化序直驱:漏斗建容器(或裸构造)→ 真实
    ``CwLoop`` 构造(__init__ ensure 铸/认领 = handle_init 的「当前 run」
    基准)→ 直调 handle_init,断言容器保留/重建与 SettlementState 注入
    (is_new_match 值注入语义,等价映射 = 旧 True [兜底新建] ≙ takeover)。
    遥测 run 态簇 = 模块级单例,夹具前后 ``reset_run_state`` 复位。"""

    @staticmethod
    def _make_loop(test_context: SrTestContext,
                   monkeypatch: pytest.MonkeyPatch) -> CwLoop:
        """真实 CwLoop 构造(controller 桩供窗口就绪探针;零识别零落盘——
        构造后只直调 handle_init,不进 loop 节点)。"""
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', lambda *a, **k: None)
        return CwLoop(test_context)

    @pytest.fixture
    def cw_run_env(self, test_context: SrTestContext,
                   monkeypatch: pytest.MonkeyPatch) -> SrTestContext:
        """遥测 run 态簇复位夹具(模块级单例跨测防串染)+ ctx 挂拆还原。"""
        from sr_od.application.currency_war.telemetry import state as cw_state
        cw_state.reset_run_state()
        monkeypatch.setattr(test_context, 'cw_match', None, raising=False)
        monkeypatch.setattr(test_context, 'cw_selected_difficulty', None,
                            raising=False)
        yield test_context
        cw_state.reset_run_state()

    def test_fresh_entry_chain_container_kept(
            self, cw_run_env: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """场景 1 正常开局:入口链建(created_run_id == 当前 run)→ 保留
        同一容器;SettlementState 注入 False(new_game ≙ 旧 False)。"""
        from sr_od.application.currency_war.telemetry import state as cw_state
        container = _establish_ctx_container(cw_run_env, 'new_game')
        loop = self._make_loop(cw_run_env, monkeypatch)
        loop.handle_init()

        assert cw_run_env.cw_match is container, \
            '本 run 内建立的容器应保留(判据三连不成立:created_run_id==当前 run)'
        assert container.created_run_id == cw_state.current_run_id()
        assert loop._settle.is_new_match is False, \
            'new_game 容器的 SettlementState 注入应为 False'

    def test_fallback_builds_takeover_container(
            self, cw_run_env: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """场景 5 继续进度:容器缺席 → 兜底建 takeover;SettlementState
        注入 True(takeover ≙ 旧 True)。"""
        loop = self._make_loop(cw_run_env, monkeypatch)
        loop.handle_init()

        container = cw_run_env.cw_match
        assert container is not None, '容器缺席应走兜底建'
        assert container.opened_via == 'takeover', \
            (f'兜底建(未经新局链专属画面)应写 takeover,'
             f'实际 {container.opened_via!r}')
        from sr_od.application.currency_war.telemetry import state as cw_state
        assert container.created_run_id == cw_state.current_run_id(), \
            '兜底建容器应经漏斗记 created_run_id(重建判据载体)'
        assert loop._settle.is_new_match is True, \
            'takeover 容器的 SettlementState 注入应为 True'

    def test_stale_container_rebuilt_as_takeover(
            self, cw_run_env: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """场景 3/4 重跑直撞/停点重跑(同型):上 run 残留容器 → 弃旧重建
        takeover(discard 显式前置,establish 幂等直过不弃旧)。假钟前进
        = 模拟真实跨秒时序(run_id 秒级时间戳;生产里上一 run 收尾与下一
        run 铸造隔至少一次 app 运行、框架等待下限 >1s,必跨秒——测试
        压缩时序需显式造出跨秒前提,否则判据输入退化为同值字符串)。"""
        from sr_od.application.currency_war.telemetry import state as cw_state

        class _AdvancingDatetime:
            """``datetime.now`` 替身:每次调用前进 2 秒(真实时序压缩)。"""

            @staticmethod
            def now():
                _AdvancingDatetime._tick += 2
                from datetime import datetime as _real
                return _real(2026, 11, 19, 12, 0, _AdvancingDatetime._tick)

        _AdvancingDatetime._tick = 0
        monkeypatch.setattr(cw_state, 'datetime', _AdvancingDatetime)

        stale = _establish_ctx_container(cw_run_env, 'new_game')
        cw_state.close_run()   # 模拟上一运行收尾(_RUN_CLOSED 置位)
        # 容器残留(假局提前 return/入口链 fail 形态:收尾不清容器)
        assert cw_run_env.cw_match is stale

        loop = self._make_loop(cw_run_env, monkeypatch)   # __init__ ensure 铸新段
        loop.handle_init()

        container = cw_run_env.cw_match
        assert container is not stale, '跨 run 残留容器应弃旧重建'
        assert container.opened_via == 'takeover', \
            (f'重建容器应写 takeover(对局面无知,走接管面),'
             f'实际 {container.opened_via!r}')
        assert container.created_run_id == cw_state.current_run_id(), \
            '重建容器应记当前 run(下一次 handle_init 判保留的基准)'
        assert loop._settle.is_new_match is True, \
            '重建容器(takeover)的 SettlementState 注入应为 True'

    def test_two_games_in_process_each_gets_new_run(
            self, cw_run_env: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """场景 2 同进程连续两局:局终清容器 → 入口链新建 → 新容器经漏斗
        记当前 run(close_run 后重铸,「新段」由 ensure token 比对承载,
        run_id 秒级时间戳同秒合法同值不锁字符串),handle_init 判保留。"""
        from sr_od.application.currency_war.telemetry import state as cw_state
        _establish_ctx_container(cw_run_env, 'new_game')
        cw_state.close_run()
        monkeypatch.setattr(cw_run_env, 'cw_match', None)   # 局终清(3c 大厅收尾)

        second = _establish_ctx_container(cw_run_env, 'new_game')
        assert second.created_run_id == cw_state.current_run_id()
        loop = self._make_loop(cw_run_env, monkeypatch)
        loop.handle_init()

        assert cw_run_env.cw_match is second, '本 run 新建容器应保留'

    def test_sim_direct_construct_container_kept(
            self, cw_run_env: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """场景 6 sim 直构:裸构造容器(created_run_id=None)→ None 短路
        保留,不得被重建判据误弃(design §2.7 sim 零改动契约)。"""
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            StrategySession,
        )
        from sr_od.application.currency_war.strategies.impl.cw_strategy import (
            CurrencyWarMatch,
        )
        bare = CurrencyWarMatch(object(), StrategySession(), None)
        monkeypatch.setattr(cw_run_env, 'cw_match', bare, raising=False)

        loop = self._make_loop(cw_run_env, monkeypatch)
        loop.handle_init()

        assert cw_run_env.cw_match is bare, \
            'created_run_id=None(外部装配)应短路保留,不得弃旧重建'
        assert loop._settle.is_new_match is False, \
            '裸构造容器(opened_via 缺省 new_game)的注入应为 False'


class TestBattleFrameRecoveryGate:
    """战斗帧恢复检测门迁移等价(design §2.6:旧 is_new_match=True ≙
    opened_via=='takeover',方向禁反)。演法 = ``CwLoop.__new__`` 壳直驱
    ``loop()`` 单轮(先例 = 停点出口测试):首读桩给 round>1(上局残局
    读数形态),断言接管容器触发失效写、new_game 容器门关零写。"""

    @staticmethod
    def _drive_one_iter(test_context: SrTestContext,
                        monkeypatch: pytest.MonkeyPatch,
                        opened_via: str) -> None:
        """壳直驱一轮:识别面全桩为未命中(身份解析桩 None + prep_anchors_hit
        桩 False——本用例目标 = iter1 恢复检测门,非认领判定本体),首读桩
        给中局读数(round>1 = 上局残局读数形态)。"""
        from types import SimpleNamespace
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases([{'frame': _PREP_FRAME}])
        match = SimpleNamespace(opened_via=opened_via, gs=None,
                                session=SimpleNamespace())
        monkeypatch.setattr(test_context, 'cw_match', match, raising=False)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', lambda *a, **k: None)
        monkeypatch.setattr(CwLoop, '_resolve_frame_identity',
                            lambda self, screen: (None, []))
        monkeypatch.setattr(cw_loop_module, 'read_game_state',
                            lambda *a, **k: SimpleNamespace(round_num=9,
                                                            plane=1))
        monkeypatch.setattr(cw_loop_module, 'prep_anchors_hit',
                            lambda op, screen: False)
        shell = CwLoop.__new__(CwLoop)
        shell.ctx = test_context
        shell.last_screenshot = ctrl.current_frame
        shell._iter = 0   # loop() 顶部 +1 → 本轮 iter=1(恢复检测门的时点)
        shell._stop_at_prep = False
        shell._battle_wait_active = False
        shell._cleanup_delegate = False
        enter_running_state(test_context)
        try:
            shell.loop()
        finally:
            reset_running_state(test_context, shell)

    def test_takeover_container_gate_opens_invalidation_write(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """接管容器(iter1 ∧ takeover ∧ 中局读数)→ 门开:tracked 观察态
        失效写(logic / takeover_invalidation,写点 = CwLoop 战斗帧确认点)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        self._drive_one_iter(test_context, monkeypatch, 'takeover')
        gs = game_state_of(test_context.cw_match.session)
        _tracked = gs.tracked_account_observed
        assert _tracked.value is False, \
            (f'接管容器门开应失效写 False,实际 {_tracked.value!r}')
        assert _tracked.source == 'logic', \
            f'失效写应走 logic 通道,实际 {_tracked.source!r}'
        assert _tracked.evidence == 'takeover_invalidation', \
            f'失效写 evidence 应为 takeover_invalidation,实际 {_tracked.evidence!r}'

    def test_new_game_container_gate_stays_closed(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """new_game 容器(iter1)→ 门关:零失效写(旧 is_new_match=False
        的等价形态;中局读数不触发——新局容器对「残局读数」的旧语义 =
        恒不进检测)。"""
        from sr_od.application.currency_war.kernel.cw_game_state import (
            game_state_of,
        )
        self._drive_one_iter(test_context, monkeypatch, 'new_game')
        gs = game_state_of(test_context.cw_match.session)
        assert gs.tracked_account_observed.value is None, \
            (f'new_game 容器门关零写,'
             f'实际 {gs.tracked_account_observed.value!r}')


# ===== 分发画面预检(_dispatch_anchor_precheck;防建档/merged 漂移)=====

class TestDispatchAnchorPrecheck:
    """iter1 分发画面预检测试(design 2026-11-20-cw-p0-chain tasks 2.1):
    清单内画面缺档/缺 id_mark → log.error 逐条点名(不中止运行);真档
    全量在册 → 零点名。两向各锁一条——真档用例红 = 新登记画面档缺失或
    丢了 id_mark(新增画面「三处缺一不可」的建档腿);点名用例红 = 预检
    失声(漂移发生时判读面拿不到信号)。"""

    def test_current_assets_zero_problems(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """真档全量在册:预检零 error 点名(含 cw-p0chain 五新画面)。"""
        import logging
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', lambda *a, **k: None)
        loop = CwLoop(test_context)
        _one_dragon_logger = logging.getLogger('OneDragon')
        monkeypatch.setattr(_one_dragon_logger, 'propagate', True)
        with caplog.at_level(logging.ERROR, logger='OneDragon'):
            loop._dispatch_anchor_precheck()
        problems = [r for r in caplog.records
                    if r.levelno >= logging.ERROR
                    and '分发画面预检' in r.getMessage()]
        assert problems == [], \
            (f'分发清单画面应全部在册且有 id_mark,实际点名 '
             f'{[r.getMessage() for r in problems]}')

    def test_missing_id_mark_named_in_error(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """无 id_mark 形态:预检按画面名逐条点名(判读面信号 = 点名行)。

        注:画面档不存在形态的点名分支现役不可达(screen_loader.get_screen
        对缺档抛异常 → 被预检 except 吞成 debug,缺陷另行申报),本用例锁
        可达的 id_mark 半边。"""
        import logging
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', lambda *a, **k: None)
        _no_mark_screen = SimpleNamespace(area_list=[
            SimpleNamespace(id_mark=False),
        ])
        monkeypatch.setattr(CwLoop, 'CW_DISPATCH_SCREENS',
                            ('货币战争-预检测试无识别标志',))
        monkeypatch.setattr(test_context.screen_loader, 'get_screen',
                            lambda name, copy=False: _no_mark_screen)
        loop = CwLoop(test_context)
        _one_dragon_logger = logging.getLogger('OneDragon')
        monkeypatch.setattr(_one_dragon_logger, 'propagate', True)
        with caplog.at_level(logging.ERROR, logger='OneDragon'):
            loop._dispatch_anchor_precheck()
        problem_lines = [r.getMessage() for r in caplog.records
                         if r.levelno >= logging.ERROR
                         and '分发画面预检' in r.getMessage()]
        assert any('货币战争-预检测试无识别标志: 无 id_mark 识别标志' in m
                   for m in problem_lines), \
            (f'无识别标志画面应被逐条点名,实际 {problem_lines}')


class TestDispatchNewScreens:
    """cw-p0chain 分发分支接线测试(tasks 3.5;design §2.3-A/§2.5):
    四新画面分支的 journal 名 / frame_tag / 派发 op 类三元组断言 +
    主角锁定扩员分支的带参对断言(CwScreenPrepLockedReturn 参数化接口)。

    演法:派发 op ``execute`` 打桩(记录实例类名与带参字段,直调
    ``_dispatch_identity_screen`` 断言接线对——op 内部链路归各 op 剧本
    测试,本类只锁「屏名 → 处理器 + journal + tag」的接线面);
    ``_log_cw_op``/``save_decision_frame`` 换记录型桩。"""

    #: 四新画面 → (journal 名, frame_tag, op 类名) 接线对(与生产分支
    #: 逐字同源,生产侧改接线本表同步改——失配即红)。
    _EXPECT: list[tuple[str, str, str, str]] = [
        ('货币战争-幕后茶歇', '幕后茶歇', 'flow_tea_break', 'CwScreenTeaBreak'),
        ('货币战争-茶歇奖励', '茶歇奖励', 'flow_tea_break_reward',
         'CwScreenTeaBreakReward'),
        ('货币战争-奇遇对话', '奇遇对话', 'flow_adventure_dialog',
         'CwScreenAdventureDialog'),
        ('货币战争-主角光环选择', '主角光环', 'flow_aura_select',
         'CwScreenAuraSelect'),
    ]

    def _make(self, test_context: SrTestContext,
              monkeypatch: pytest.MonkeyPatch,
              dispatched: list, journals: list, tags: list):
        ctrl = FixtureController(
            ctx=test_context,
            standard_width=test_context.project_config.screen_standard_width,
            standard_height=test_context.project_config.screen_standard_height,
        )
        monkeypatch.setattr(test_context, 'controller', ctrl)
        ctrl.set_phases([{'frame': _PREP_FRAME}])

        def _rec_frame(loop, tag, shot) -> None:
            tags.append(tag)

        monkeypatch.setattr(
            'sr_od.application.currency_war.operations.cw_loop.'
            'save_decision_frame', _rec_frame)

        def _rec_log(op_name, pos, dur, outcome, reason='') -> None:
            journals.append((op_name, outcome))

        monkeypatch.setattr(cw_loop_module, '_log_cw_op', _rec_log)

        from sr_od.application.currency_war.operations.cw_screen.cw_screen_adventure_dialog import (
            CwScreenAdventureDialog,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_aura_select import (
            CwScreenAuraSelect,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep_locked_return import (
            CwScreenPrepLockedReturn,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_tea_break import (
            CwScreenTeaBreak,
        )
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_tea_break_reward import (
            CwScreenTeaBreakReward,
        )

        for cls in (CwScreenTeaBreak, CwScreenTeaBreakReward,
                    CwScreenAdventureDialog, CwScreenAuraSelect,
                    CwScreenPrepLockedReturn):
            def _fake_exec(self_op, _cls=cls):
                dispatched.append((
                    type(self_op).__name__,
                    getattr(self_op, '_screen_name', None),
                    getattr(self_op, '_entry_area', None)))
                return SimpleNamespace(success=True, status='stub')

            monkeypatch.setattr(cls, 'execute', _fake_exec)

        shell = CwLoop.__new__(CwLoop)
        shell.ctx = test_context
        shell.last_screenshot = None
        return shell, ctrl

    def test_four_new_branches_dispatch_contract(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """四新画面分支接线对:屏名 → op 类 + journal 名 + frame_tag
        逐项与生产接线一致。"""
        dispatched: list = []
        journals: list = []
        tags: list = []
        shell, ctrl = self._make(test_context, monkeypatch,
                                 dispatched, journals, tags)
        for screen_name, _journal, _tag, _cls in self._EXPECT:
            shell._dispatch_identity_screen(screen_name, ctrl.current_frame)

        assert [d[0] for d in dispatched] == [e[3] for e in self._EXPECT], \
            (f'派发 op 类应与接线对一致,实际 {dispatched!r}')
        assert [j[0] for j in journals] == [e[1] for e in self._EXPECT], \
            (f'journal 名应与接线对一致,实际 {journals!r}')
        assert all(j[1] == 'ok' for j in journals), \
            f'桩 execute 成功应映射 ok,实际 {journals!r}'
        assert tags == [e[2] for e in self._EXPECT], \
            (f'frame_tag 应与接线对一致,实际 {tags!r}')

    def test_protagonist_lock_expands_lock_branch_with_param_pair(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """主角锁定扩员:走既有锁定分支(三元组第三员),派发
        CwScreenPrepLockedReturn 带参对 = (画面档, 按钮-返回主角选择)
        ——参数化接口消费,零新 op(design §2.3-A)。"""
        dispatched: list = []
        journals: list = []
        tags: list = []
        shell, ctrl = self._make(test_context, monkeypatch,
                                 dispatched, journals, tags)
        shell._dispatch_identity_screen('货币战争-备战-主角锁定',
                                        ctrl.current_frame)

        assert dispatched == [('CwScreenPrepLockedReturn',
                               '货币战争-备战-主角锁定',
                               '按钮-返回主角选择')], \
            (f'主角锁定应派发带参对锁定 op,实际 {dispatched!r}')
        assert journals == [('备战暗色锁定', 'ok')], \
            (f'锁定分支 journal 名应维持现役共用名,实际 {journals!r}')
