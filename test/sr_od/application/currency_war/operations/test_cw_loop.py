"""CwLoop 分发包装与外环 fail 防线测试(loop 镜像锚)。

锁设计约定(契约单一源 = ``cw_loop.py::CwLoop._dispatch_screen_op`` docstring
防线出口契约段 + skill ``references/flow/guards.md`` §1):

- ``op_fail_redispatch_tick`` 三态:ok 归零 / 同键累加 / 异键归一(防线
  计数根语义,链形归组修复依赖这三态);
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


def test_op_fail_redispatch_tick_three_states() -> None:
    """防线计数纯函数三态基线:ok 归零 / 同键累加 / 异键归一。"""
    # 任一 op ok = 画面证实推进 → 整窗归零(键清 None)
    assert op_fail_redispatch_tick('任意键', 3, 'X', True) == (None, 0)
    # 同键 fail 累加
    assert op_fail_redispatch_tick('X', 2, 'X', False) == ('X', 3)
    # 异键 fail = 粘滞对象已换,新情节从 1 起算
    assert op_fail_redispatch_tick('X', 4, 'Y', False) == ('Y', 1)


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


def test_exit_status_texts_stable(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
        tmp_path) -> None:
    """交接判定载体出口文本稳定性锚(防漂移破坏 app 交接判定,与 T-1
    常量面联动):大厅出口常量字面锚(判定 = 全等匹配);max_rounds 无
    常量,触发真实停点出口断言含「停备战」锚(落 app「其余」分支,文本
    漂移行为安全,本锚防形态误漏进交接)。max_rounds 停点走真实
    ``loop()`` 备战分支,识别面全桩(身份解析桩为未命中、备战认领桩为
    命中),零真实识别零落盘。"""
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
        f'max_rounds 达标应停备战屏 success,实际 {res.result}')
    assert '停备战' in (res.status or ''), (
        f'停备战出口文本应含「停备战」锚(app「其余」分支判定输入): {res.status}')
