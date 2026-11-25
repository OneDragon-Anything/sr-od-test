"""备战画面 op 的合成确认浮层优先分支(CwScreenPrep)。

合成确认浮层是备战画面的子态(不是独立画面):识别到就优先处置,其余备战流程一律
让位。本文件锁这条分支的两半——观察 node 顶部的识别分流、决策动作 node 顶部的处置
函数。样本 = ``sr-od-test/screens`` 下的实机浮层帧(最高档一张、带「选择主角」按钮的
中档两张)、干净备战帧、商店展开帧;没有实机样本的形态(只有一颗按钮、两对按钮、
商店加浮层同时在场)在内存里把按钮模板贴到样本帧上合成。

锁的设计约定:

- 浮层帧:观察 node 上报浮层读数后直接进决策动作 node(子态五查、清场、收店探针、
  接管补采委派、全量观察都不执行,段序号不动);策略器的浮层处置入口恰调用一次、坐标
  取自状态容器该字段;点击恰一次落在按钮上;访问经终结口交回。「选择主角」变体帧、
  接管局未探帧、锁定帧上的浮层同样优先——选择主角处置不被进入、探针不发、锁定保持。
- 读不准的帧(有按钮候选但配不成对 / 成对配对有歧义 / 识别入参缺失):观察 node 直接
  失败,不写该字段(留着上一帧的值),后续步骤都不执行。
- 干净帧:上报 ``'none'``(字段里留着上一帧的读数结构也不触发处置),原路径不变。
- 商店开着的帧(只有商店 / 商店加浮层同时在):不识别浮层、不写该字段、处置计数不清零、
  不走浮层分支,原路径照走(收店探针照常)。
- 连续未收起的出口:处置计数每处置一次加一,确认浮层不在场的帧清零,第四态的帧不清;
  三次处置后浮层仍在场 → 第四次失败、零点击。计数载体缺席 → 显式失败。
"""

from __future__ import annotations

import importlib
import types
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import pytest
from cv2.typing import MatLike
from test.conftest import SrTestContext
from test.harness.cw_fixture_controller import CwFixtureController
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen import screen_utils
from one_dragon.base.screen.template_info import TemplateInfo
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import strategy_state_of
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionObsParam,
    CwActionSynthesisCancelParam,
    CwActionSynthesisConfirmParam,
)
from sr_od.application.currency_war.obs import cw_synthesis_overlay_obs as overlay_mod
from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

_PREP: str = '货币战争-备战'
_OVERLAY_DIR: str = '货币战争-备战-合成确认'
_SHOP: str = '货币战争-备战-开商店'

#: 干净备战帧。
_CLEAN_FRAME: tuple[str, str] = (_PREP, 'deployed_2star')
#: 最高档实机浮层帧与 ✓ 按钮外框 [x1,y1,x2,y2](实机帧上的按钮位置)。
_TOP_OVERLAY_FRAME: tuple[str, str] = (_PREP, 'rail_badge_absent_r2')
_TOP_OK_BOX: tuple[int, int, int, int] = (1770, 298, 1875, 355)
#: 中档实机浮层帧(画面上有「选择主角」按钮的变体态)与 ✓ 按钮外框。
_MID_OVERLAY_FRAMES: list[tuple[str, str]] = [
    (_OVERLAY_DIR, '合成确认浮层'), (_OVERLAY_DIR, '合成确认浮层-残留')]
_MID_OK_BOX: tuple[int, int, int, int] = (1769, 375, 1874, 431)
#: ✕ 按钮在 ✓ 左侧的像素数(实机帧上两颗按钮的中心相距 114)。
_CANCEL_DX: int = 114
#: 商店面板展开帧。
_SHOP_FRAME: tuple[str, str] = (_SHOP, 'shop_open')

#: 处置计数的载体键(cw4_counters;对局终快照里的键名,按字面写)。
_CLICK_COUNT_KEY: str = 'synthesis_overlay_click'
#: 终结口给合成确认浮层两个动作的状态词。
_HANDLED_STATUS: str = '合成确认浮层已处理(交回外循环重观察)'

#: 上一帧留下的浮层读数结构:只用来表示「字段里留着一组旧坐标」,不是哪张样本帧的读数。
_STALE_READING: dict = {
    'ok_xy': (1821, 327), 'cancel_xy': (1707, 327), 'panel_rect': [1597, 222, 1872, 359],
    'inputs': [{'name': '轮滑鞋', 'conf': 0.91, 'cx': 1632, 'cy': 251},
               {'name': '光能电池', 'conf': 0.88, 'cx': 1731, 'cy': 251}],
    'product': {'name': None, 'conf': 0.30, 'cx': 1838, 'cy': 248},
}

#: 夹具种子写入用的渠道签名(观察通道)。
_TEST_OBS_SIG: ChannelSig = ChannelSig(family='obs', actor='CwScreenPrep',
                                       screen='货币战争-备战', mode='read')

#: 合成确认浮层两个动作 op 的模块:点击后等浮层收起的 op 内等待是真机时长,测试里
#: 画面瞬间切换,模块级 ``time`` 单独桩掉(宿主 op 的 fast_sleep 够不着它们)。
_ACTION_OP_MODULES: tuple[str, ...] = (
    'sr_od.application.currency_war.operations.cw_op.cw_synthesis_confirm_action',
    'sr_od.application.currency_war.operations.cw_op.cw_synthesis_cancel_action',
)

#: 原路径的前置段现行序(清场 → 收店探针 → heavy 观察 → 补采委派)。
_FRONT_SEGMENT_ORDER: list[str] = ['清场', '收店探针', 'heavy', '补采委派']


class _NoSleepTime:
    """模块级 ``time`` 替身:sleep 不睡,其余属性透传真模块。"""

    def __init__(self, real_module: types.ModuleType) -> None:
        self._real = real_module

    def sleep(self, seconds: float) -> None:
        pass

    def __getattr__(self, name: str):
        return getattr(self._real, name)


class _FrameController(CwFixtureController):
    """剧本控制器:另支持 phase['frame'] 直接给 ndarray(内存里合成的帧)。"""

    @property
    def current_frame(self) -> MatLike:
        phase = self._phases[self._phase_idx]
        if isinstance(phase.get('frame'), np.ndarray):
            return phase['frame']
        return CwFixtureController.current_frame.fget(self)


class _OverlayStrategy:
    """策略器替身:两个入口各记调用次数;浮层处置入口按状态容器该字段的坐标返回
    指定的一种动作(与现役策略同一个取数方式——坐标取字段,不自算)。"""

    def __init__(self, gs: GameState, kind: str = 'confirm') -> None:
        self.gs = gs
        self.kind = kind
        self.overlay_calls: int = 0
        self.prep_calls: int = 0

    def decide_synthesis_overlay(self):
        self.overlay_calls += 1
        value = self.gs.synthesis_overlay.value
        assert isinstance(value, dict), f'处置入口被调用时字段应是读数结构,实际 {value!r}'
        cx, cy = value['ok_xy'] if self.kind == 'confirm' else value['cancel_xy']
        if self.kind == 'confirm':
            return CwActionSynthesisConfirmParam(cx, cy)
        return CwActionSynthesisCancelParam(cx, cy)

    def decide_prep_screen(self) -> CwActionObsParam:
        self.prep_calls += 1
        return CwActionObsParam(scope='outer_loop')


@pytest.fixture
def prep_env(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch,
             ) -> tuple[SrTestContext, _FrameController]:
    """浮层分支剧本夹具:假控制器换装 + 两个动作 op 模块的裸睡桩 + 重识别核打桩
    (heavy 观察本体有专测;打桩同时收窄识别链的截图落盘面,测试零真实副作用)。"""
    ctrl = _FrameController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    for mod_name in _ACTION_OP_MODULES:
        mod = importlib.import_module(mod_name)
        monkeypatch.setattr(mod, 'time', _NoSleepTime(mod.time))
    _stub_heavy_recognition(monkeypatch)
    return test_context, ctrl


@contextmanager
def _running(test_context: SrTestContext) -> Iterator[list[CwScreenPrep]]:
    """进入运行态;退出时复位本次测试建的全部 op(事件监听与运行态一并清)。"""
    ops: list[CwScreenPrep] = []
    enter_running_state(test_context)
    try:
        yield ops
    finally:
        for op in ops:
            reset_running_state(test_context, op)


def _visit(test_context: SrTestContext, ops: list[CwScreenPrep]
           ) -> tuple[CwScreenPrep, OperationResult]:
    """跑一次备战画面 op 访问(每次派发新建 op 实例,同生产形态)。"""
    op = CwScreenPrep(test_context)
    ops.append(op)
    with fast_sleep(op):
        result = op.execute()
    return op, result


def _attach_match(test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
                  *, kind: str = 'confirm', counters: dict | None = None,
                  with_state: bool = True, **fields) -> types.SimpleNamespace:
    """挂流程态 Match 桩(monkeypatch 还原;session 每测新建 = 状态容器新支,无跨测
    串染)。策略器替身持该 session 的状态容器。``counters`` 传入时挂策略状态替身
    (处置计数的载体 + 段序号);``with_state=False`` 制造「计数载体缺席」。"""
    session = types.SimpleNamespace()
    match = types.SimpleNamespace(
        session=session, strategy=None, gs=None,
        opened_via=fields.pop('opened_via', 'new_game'),
        probed=fields.pop('probed', False),
        locked_resume=fields.pop('locked_resume', False),
        locked_round=fields.pop('locked_round', 0),
        locked_sync_done=fields.pop('locked_sync_done', True),
        **fields)
    if counters is not None:
        counters.setdefault(_CLICK_COUNT_KEY, 0)
    if with_state:
        session.strategy_state = types.SimpleNamespace(
            cw4_counters=counters if counters is not None else {},
            cw4_segment_serial=0, cw4_frame_action_record=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    match.strategy = _OverlayStrategy(game_state_of(session), kind)
    return match


def _seed_regular_gs(gs: GameState) -> None:
    """原路径的前置条件:补采委派门两支按否(位面 boss 真值在场 + 词缀非随机态),
    常规帧与收店后的帧不委派接管补采(委派编排有专属测试域)。"""
    gs.observe(gs.plane_bosses, ['boss-1', 'boss-2', 'boss-3'],
               evidence='test_seed', sig=_TEST_OBS_SIG)
    gs.observe(gs.enemy_affixes, [], evidence='test_seed', sig=_TEST_OBS_SIG)


def _seed_stale_reading(gs: GameState) -> None:
    """让状态容器的浮层字段留着一组上一帧的读数结构。"""
    gs.observe(gs.synthesis_overlay, dict(_STALE_READING),
               evidence='test_seed', sig=_TEST_OBS_SIG)


def _stub_heavy_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    """heavy 识别核打桩(observe_full 回执 = {}),并把识别链的截图落盘面收成 no-op
    (识别 MISS / 异常采集会写真实 .debug 目录)。"""
    from sr_od.application.currency_war.kernel import cw_observe
    from sr_od.application.currency_war.obs import cw_observe_full
    monkeypatch.setattr(cw_observe_full, 'observe_full', lambda *a, **k: {})
    monkeypatch.setattr(cw_observe, 'cw_shot', lambda image, name: None)
    monkeypatch.setattr(cw_observe, 'cw_shot_unique', lambda image, label: None)


def _spy_later_steps(monkeypatch: pytest.MonkeyPatch
                     ) -> tuple[list[str], list[int], list[int]]:
    """观察 node 后续步骤的探针:返回 ``(前置段调用序, c 查节点条读的调用数,
    锁定出战的调用数)``。前置段四个方法真方法透传、只记调用序;c 查是子态五查的
    末查,锁定出战是段 3 的首个处置——它们的调用数就是「后面的步骤跑没跑」的哨兵。"""
    order: list[str] = []
    node_seq_calls: list[int] = []
    lock_battle_calls: list[int] = []
    real = {name: getattr(CwScreenPrep, name) for name in (
        '_clear_entry_overlays', '_try_collapse_open_shop', '_observe',
        '_delegate_plane_intel_if_needed')}
    labels = {'_clear_entry_overlays': '清场', '_try_collapse_open_shop': '收店探针',
              '_delegate_plane_intel_if_needed': '补采委派'}

    def _wrap(method_name: str):
        label = labels.get(method_name)

        def _spy(self, *args, **kwargs):
            if label is not None:
                order.append(label)
            else:
                heavy = kwargs.get('heavy', args[1] if len(args) > 1 else False)
                order.append('heavy' if heavy else '观察-轻')
            return real[method_name](self, *args, **kwargs)
        return _spy

    for method_name in real:
        monkeypatch.setattr(CwScreenPrep, method_name, _wrap(method_name))
    real_node_seq = cw_screen_prep.read_node_sequence

    def _node_seq_spy(*args, **kwargs):
        node_seq_calls.append(1)
        return real_node_seq(*args, **kwargs)

    monkeypatch.setattr(cw_screen_prep, 'read_node_sequence', _node_seq_spy)

    def _lock_battle_spy(op, ctx):
        lock_battle_calls.append(1)
        return False, '本测试不应走到锁定出战'

    monkeypatch.setattr(cw_screen_prep, 'locked_resume_sync_and_battle', _lock_battle_spy)
    return order, node_seq_calls, lock_battle_calls


def _paste_buttons(frame: MatLike, ok_xy: tuple[int, int],
                   cancel_xy: tuple[int, int] | None = None) -> MatLike:
    """在内存里把按钮模板贴到帧上的指定左上角(只贴掩码内的像素),返回新帧。"""
    out = frame.copy()
    jobs = [(TemplateInfo(overlay_mod.OK_TEMPLATE_DIR, overlay_mod.OK_TEMPLATE_DIR), ok_xy)]
    if cancel_xy is not None:
        jobs.append((TemplateInfo(overlay_mod.CANCEL_TEMPLATE_DIR,
                                  overlay_mod.CANCEL_TEMPLATE_DIR), cancel_xy))
    for template, (x, y) in jobs:
        keep = template.mask > 0
        region = out[y:y + template.raw.shape[0], x:x + template.raw.shape[1]]
        region[keep] = template.raw[keep]
    return out


def _clicks_in_box(ctrl: CwFixtureController,
                   box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    """落在矩形内的点击坐标。"""
    x1, y1, x2, y2 = box
    return [(p.x, p.y) for p in ctrl.recorded_clicks
            if x1 <= p.x <= x2 and y1 <= p.y <= y2]


def _assert_overlay_branch(op: CwScreenPrep, result: OperationResult,
                           ctrl: _FrameController, match: types.SimpleNamespace,
                           button_box: tuple[int, int, int, int],
                           order: list[str], node_seq_calls: list[int]) -> None:
    """浮层分支走通的公共断言(各浮层帧剧本共用)。"""
    strategy = match.strategy
    assert result.success, f'浮层帧应经终结口成功交回,实际 {result.status!r}'
    assert result.status == _HANDLED_STATUS, \
        f'访问应经终结口结束(不出现「非终结动作进入终结出口」),实际 {result.status!r}'
    assert (strategy.overlay_calls, strategy.prep_calls) == (1, 0), \
        (f'浮层处置入口应恰调用一次、备战常规入口不调用,'
         f'实际 浮层入口 {strategy.overlay_calls} 次 / 常规入口 {strategy.prep_calls} 次')
    assert len(_clicks_in_box(ctrl, button_box)) == 1 and len(ctrl.recorded_clicks) == 1, \
        f'点击应恰一次且落在浮层按钮上,实际 {[(p.x, p.y) for p in ctrl.recorded_clicks]}'
    assert op._executor is not None, '浮层帧上执行器应已构建(常规构建点在被跳过的路径上)'
    assert order == [], f'浮层帧上前置段与全量观察都不执行,实际调用了 {order!r}'
    assert node_seq_calls == [], '浮层帧上子态五查不执行(c 查的节点条读被调用即走到了五查)'
    assert strategy_state_of(match.session).cw4_segment_serial == 0, \
        '浮层处置不是备战期动作,段序号不应置位'


@pytest.mark.parametrize(('kind', 'button_box'),
                         [('confirm', _TOP_OK_BOX),
                          ('cancel', (_TOP_OK_BOX[0] - _CANCEL_DX, _TOP_OK_BOX[1],
                                      _TOP_OK_BOX[2] - _CANCEL_DX, _TOP_OK_BOX[3]))],
                         ids=['确认', '取消'])
def test_overlay_frame_is_handled_before_any_prep_step(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch, kind: str,
        button_box: tuple[int, int, int, int]) -> None:
    """浮层帧:观察 node 上报读数后直达决策动作 node → 处置入口按字段坐标返回动作 →
    点击落在按钮上 → 终结口交回。确认、取消两个动作各一条(终结口认得这两个动作)。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    match = _attach_match(test_context, monkeypatch, kind=kind, counters={})
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    order, node_seq_calls, lock_battle_calls = _spy_later_steps(monkeypatch)

    with _running(test_context) as ops:
        op, result = _visit(test_context, ops)

    _assert_overlay_branch(op, result, ctrl, match, button_box, order, node_seq_calls)
    assert lock_battle_calls == []
    # 信息上传:字段里是读数结构,✓ 中心落在实机帧的 ✓ 按钮上(动作坐标取自它)
    assert isinstance(gs.synthesis_overlay.value, dict), \
        f'浮层帧应把读数结构写进状态容器,实际 {gs.synthesis_overlay.value!r}'
    ok_x, _ok_y = gs.synthesis_overlay.value['ok_xy']
    assert _TOP_OK_BOX[0] <= ok_x <= _TOP_OK_BOX[2], \
        f'字段里的 ✓ 中心应落在 ✓ 按钮上,实际 {gs.synthesis_overlay.value["ok_xy"]!r}'


@pytest.mark.parametrize('frame', _MID_OVERLAY_FRAMES, ids=[f[1] for f in _MID_OVERLAY_FRAMES])
def test_select_hero_variant_with_overlay_skips_select_hero_handler(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch, frame: tuple[str, str]) -> None:
    """「选择主角」变体帧上的浮层:浮层分支优先,选择主角处置 node 不被进入
    (在浮层下点「选择主角」会被吞、等不到光环屏标题,连等超限后整局停)。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': frame}])
    match = _attach_match(test_context, monkeypatch, counters={})
    _seed_regular_gs(game_state_of(match.session))
    order, node_seq_calls, _ = _spy_later_steps(monkeypatch)
    assert screen_utils.is_target_screen(
        test_context, test_context.load_screen(*frame),
        screen_name='货币战争-备战-选择主角'), '样本应是带「选择主角」按钮的变体帧'

    with _running(test_context) as ops:
        op, result = _visit(test_context, ops)

    _assert_overlay_branch(op, result, ctrl, match, _MID_OK_BOX, order, node_seq_calls)
    assert op._prep_substate is None and op._select_hero_retries == 0, \
        (f'浮层帧不应进入选择主角处置 node,'
         f'实际 子态载体 {op._prep_substate!r} / 处置计数 {op._select_hero_retries}')


def test_takeover_unprobed_overlay_frame_skips_probe(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """接管局未探的浮层帧:探针不发(浮层下点商店会被吞、被判成「锁定」并一次性写入
    locked_resume,之后整个备战期被当成锁定局直出战),浮层分支照常执行。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    match = _attach_match(test_context, monkeypatch, counters={},
                          opened_via='takeover', probed=False)
    _seed_regular_gs(game_state_of(match.session))
    order, node_seq_calls, _ = _spy_later_steps(monkeypatch)

    with _running(test_context) as ops:
        op, result = _visit(test_context, ops)

    _assert_overlay_branch(op, result, ctrl, match, _TOP_OK_BOX, order, node_seq_calls)
    assert match.probed is False and match.locked_resume is False, \
        (f'浮层帧上探针不应发,流程态字段不得改写,'
         f'实际 probed={match.probed!r} locked={match.locked_resume!r}')
    assert not ctrl.click_hit_area('货币战争-备战', '按钮-商店'), \
        f'浮层帧上不应有探针点击,实际 {[(p.x, p.y) for p in ctrl.recorded_clicks]}'


def test_locked_match_overlay_frame_keeps_lock(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """锁定帧上的浮层:浮层分支执行;锁定处置本次不执行、锁定字段不动(浮层收起后的
    下一访问照常走锁定出战);执行器在锁定帧上同样构建。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    match = _attach_match(test_context, monkeypatch, counters={},
                          locked_resume=True, locked_sync_done=False)
    _seed_regular_gs(game_state_of(match.session))
    order, node_seq_calls, lock_battle_calls = _spy_later_steps(monkeypatch)

    with _running(test_context) as ops:
        op, result = _visit(test_context, ops)

    _assert_overlay_branch(op, result, ctrl, match, _TOP_OK_BOX, order, node_seq_calls)
    assert lock_battle_calls == [], '浮层帧上锁定出战处置不应执行'
    assert match.locked_resume is True and match.locked_sync_done is False, \
        (f'浮层处置不动锁定字段,'
         f'实际 locked={match.locked_resume!r} sync={match.locked_sync_done!r}')
    assert not ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'浮层帧上不应有出战点击,实际 {[(p.x, p.y) for p in ctrl.recorded_clicks]}'


@pytest.mark.parametrize('form', ['unpaired', 'ambiguous', 'input_missing'],
                         ids=['配不成对', '有歧义', '入参缺失'])
def test_unreadable_overlay_frame_fails_before_any_prep_step(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch, form: str) -> None:
    """读不准的帧:观察 node 直接失败(不按「不在场」继续)——这种帧上后续步骤照跑的话,
    探针点击会被吞、全量观察会把失真的装备栏读数写进状态容器。失败文案区分三种
    形态;该字段不写(留着上一帧的读数结构),处置计数不动,零点击。"""
    test_context, ctrl = prep_env
    counters: dict = {_CLICK_COUNT_KEY: 2}
    match = _attach_match(test_context, monkeypatch, counters=counters)
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    _seed_stale_reading(gs)
    stale = gs.synthesis_overlay.value
    order, node_seq_calls, _ = _spy_later_steps(monkeypatch)
    keyword = {'unpaired': '配不成对', 'ambiguous': '有歧义',
               'input_missing': '入参缺失'}[form]
    if form == 'input_missing':
        def _missing(ctx, screen):
            raise overlay_mod.SynthesisOverlayInputError('按钮模板缺失(✓)')

        monkeypatch.setattr(cw_screen_prep, 'read_synthesis_overlay_of', _missing,
                            raising=False)
        ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    else:
        clean = test_context.load_screen(*_CLEAN_FRAME)
        frame = (_paste_buttons(clean, (1772, 374)) if form == 'unpaired'
                 else _paste_buttons(_paste_buttons(clean, (1772, 297), (1657, 297)),
                                      (1772, 374), (1657, 374)))
        ctrl.set_phases([{'frame': frame}])

    with _running(test_context) as ops:
        _op, result = _visit(test_context, ops)

    assert not result.success, f'读不准的浮层帧应观察节点直接失败,实际 {result.status!r}'
    assert keyword in (result.status or ''), \
        f'失败文案应带「{keyword}」,实际 {result.status!r}'
    assert gs.synthesis_overlay.value is stale, \
        f'读不准的帧不写该字段,实际 {gs.synthesis_overlay.value!r}'
    assert counters[_CLICK_COUNT_KEY] == 2, f'读不准的帧不动处置计数,实际 {counters!r}'
    assert ctrl.recorded_clicks == [], f'读不准的帧零点击,实际 {ctrl.recorded_clicks!r}'
    assert order == [] and node_seq_calls == [], \
        f'子态五查与全量观察都不执行,实际 前置段 {order!r} / c 查 {len(node_seq_calls)} 次'
    assert (match.strategy.overlay_calls, match.strategy.prep_calls) == (0, 0), \
        '读不准的帧不进决策动作 node'


def test_counter_carrier_absent_fails_loudly(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数载体缺席(策略器私有状态里没有 cw4_counters):处置函数显式失败——照「缺席
    即跳过」写的话计数永远不涨,连续未收起的有界出口就不存在。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    match = _attach_match(test_context, monkeypatch, with_state=False)
    _seed_regular_gs(game_state_of(match.session))

    with _running(test_context) as ops:
        _op, result = _visit(test_context, ops)

    assert not result.success, f'计数载体缺席应显式失败,实际 {result.status!r}'
    assert '合成确认浮层处置计数载体缺席' in (result.status or ''), \
        f'失败文案应说明计数载体缺席,实际 {result.status!r}'
    assert ctrl.recorded_clicks == [], f'载体缺席不点击,实际 {ctrl.recorded_clicks!r}'
    assert match.strategy.overlay_calls == 0, '载体缺席时不该调处置入口'


def test_clean_frame_reports_none_and_takes_regular_path(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """干净帧(字段里留着上一帧的读数结构):上报 'none'、处置入口不调、零点击,原路径
    不变(前置段全量照旧、段序号置位、常规决策入口进入)。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _CLEAN_FRAME}])
    match = _attach_match(test_context, monkeypatch, counters={})
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    _seed_stale_reading(gs)
    order, node_seq_calls, _ = _spy_later_steps(monkeypatch)

    with _running(test_context) as ops:
        _op, result = _visit(test_context, ops)

    assert result.success, f'干净帧应走原路径成功交回,实际 {result.status!r}'
    assert gs.synthesis_overlay.value == 'none', \
        f'干净帧应把字段上报为 none,实际 {gs.synthesis_overlay.value!r}'
    assert (match.strategy.overlay_calls, match.strategy.prep_calls) == (0, 1), \
        '干净帧不调处置入口,照常进常规决策入口'
    assert ctrl.recorded_clicks == [], \
        f'字段留着旧读数结构也不得按旧坐标点击,实际 {ctrl.recorded_clicks!r}'
    assert order == _FRONT_SEGMENT_ORDER, f'原路径前置段应照现行序全量执行,实际 {order!r}'
    assert node_seq_calls, '干净帧上子态五查照常执行到 c 查'
    assert strategy_state_of(match.session).cw4_segment_serial == 1, \
        '原路径访问入口应置位段序号'


@pytest.mark.parametrize('with_overlay', [False, True], ids=['只有商店', '商店加浮层'])
def test_shop_open_frame_skips_overlay_branch(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch, with_overlay: bool) -> None:
    """商店开着的帧(画面上只有商店 / 商店加浮层同时在):商店开着时不读右侧装备、
    不操作合成——不识别浮层、不写该字段(留着一组旧坐标也不按它点)、处置计数不清零、
    不走浮层分支;原路径照走,收店探针照常把商店收起。"""
    test_context, ctrl = prep_env
    counters: dict = {_CLICK_COUNT_KEY: 2}
    match = _attach_match(test_context, monkeypatch, counters=counters)
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    _seed_stale_reading(gs)
    stale = gs.synthesis_overlay.value
    shop_frame = test_context.load_screen(*_SHOP_FRAME)
    real_read = overlay_mod.read_synthesis_overlay_of
    if with_overlay:
        shop_frame = _paste_buttons(shop_frame, (1772, 374), (1657, 374))
        assert real_read(test_context, shop_frame).state == overlay_mod.STATE_PRESENT, \
            '合成帧上浮层应确实在场(否则本用例验不到「商店开着时不识别」)'
    reads: list[int] = []

    def _counting_read(ctx, screen):
        reads.append(1)
        return real_read(ctx, screen)

    monkeypatch.setattr(cw_screen_prep, 'read_synthesis_overlay_of', _counting_read,
                        raising=False)
    # 点「收起」后画面回到干净的备战帧,原路径在同一访问里接着跑完
    ctrl.set_phases([
        {'frame': shop_frame,
         'exit': ('on_click_in', _SHOP, '按钮-收起')},
        {'frame': _CLEAN_FRAME},
    ])
    order, _, _ = _spy_later_steps(monkeypatch)

    with _running(test_context) as ops:
        _op, result = _visit(test_context, ops)

    assert result.success, f'商店开着的帧应走原路径成功交回,实际 {result.status!r}'
    assert reads == [], f'商店开着的帧不识别浮层,实际识别了 {len(reads)} 次'
    assert gs.synthesis_overlay.value is stale, \
        f'商店开着的帧不写该字段,实际 {gs.synthesis_overlay.value!r}'
    assert counters[_CLICK_COUNT_KEY] == 2, \
        f'商店开着的帧不清处置计数(没有确认浮层不在场),实际 {counters!r}'
    assert (match.strategy.overlay_calls, match.strategy.prep_calls) == (0, 1), \
        '商店开着的帧不走浮层分支,常规入口照常进入'
    assert order == _FRONT_SEGMENT_ORDER, f'原路径应照现行序全量执行,实际 {order!r}'
    assert ctrl.click_hit_area(_SHOP, '按钮-收起') and len(ctrl.recorded_clicks) == 1, \
        f'唯一点击应是收店探针的「收起」,实际 {[(p.x, p.y) for p in ctrl.recorded_clicks]}'


def test_overlay_still_present_after_three_clicks_fails(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数剧本:三次处置后浮层仍在场 → 第四次访问失败、零点击(点击发出但游戏不收
    时循环有界,交外循环失败连击链)。"""
    test_context, ctrl = prep_env
    ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
    counters: dict = {}
    match = _attach_match(test_context, monkeypatch, counters=counters)
    _seed_regular_gs(game_state_of(match.session))

    with _running(test_context) as ops:
        for _ in range(3):
            ctrl.recorded_clicks.clear()
            _op, result = _visit(test_context, ops)
            assert result.success, f'前三次处置应各自成功交回,实际 {result.status!r}'
            assert len(_clicks_in_box(ctrl, _TOP_OK_BOX)) == 1, '每次处置点击 ✓ 恰一次'
        assert counters[_CLICK_COUNT_KEY] == 3, f'每次处置计数加一,实际 {counters!r}'
        ctrl.recorded_clicks.clear()
        _op, result = _visit(test_context, ops)

    assert not result.success, f'三次处置后浮层仍在场,第四次应失败,实际 {result.status!r}'
    assert '合成确认浮层连续 3 次处置后仍在场' in (result.status or ''), \
        f'失败文案应说明连续处置后仍在场,实际 {result.status!r}'
    assert ctrl.recorded_clicks == [], f'第四次访问零点击,实际 {ctrl.recorded_clicks!r}'


def test_clean_frame_clears_click_count(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数剧本:确认浮层不在场的帧把处置计数清零——之后新出现的浮层重新从一数起。"""
    test_context, ctrl = prep_env
    counters: dict = {}
    match = _attach_match(test_context, monkeypatch, counters=counters)
    _seed_regular_gs(game_state_of(match.session))

    with _running(test_context) as ops:
        ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
        _op, result = _visit(test_context, ops)
        assert result.success, f'浮层帧处置应成功交回,实际 {result.status!r}'
        assert counters[_CLICK_COUNT_KEY] == 1

        ctrl.set_phases([{'frame': _CLEAN_FRAME}])
        _op, result = _visit(test_context, ops)
        assert result.success, f'干净帧应走原路径成功交回,实际 {result.status!r}'
        assert counters[_CLICK_COUNT_KEY] == 0, \
            f'确认浮层不在场的帧应把处置计数清零,实际 {counters!r}'

        ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
        ctrl.recorded_clicks.clear()
        _op, result = _visit(test_context, ops)
    assert result.success, f'计数清零后新出现的浮层应照常处置,实际 {result.status!r}'
    assert counters[_CLICK_COUNT_KEY] == 1, f'处置计数应重新从一数起,实际 {counters!r}'
    assert len(_clicks_in_box(ctrl, _TOP_OK_BOX)) == 1


def test_unpaired_frames_do_not_clear_click_count(
        prep_env: tuple[SrTestContext, _FrameController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """计数剧本:浮层在场与「配不成对」交替出现——读不准的帧不清处置计数,第三次处置后
    浮层仍在场即失败(一颗按钮的分数在阈值附近抖动时同样有界)。"""
    test_context, ctrl = prep_env
    unpaired_frame = _paste_buttons(
        test_context.load_screen(*_CLEAN_FRAME), (1772, 374))
    counters: dict = {}
    match = _attach_match(test_context, monkeypatch, counters=counters)
    _seed_regular_gs(game_state_of(match.session))

    with _running(test_context) as ops:
        for _ in range(3):
            ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
            _op, result = _visit(test_context, ops)
            assert result.success, f'浮层在场帧处置应成功交回,实际 {result.status!r}'
            ctrl.set_phases([{'frame': unpaired_frame}])
            _op, result = _visit(test_context, ops)
            assert not result.success and '配不成对' in (result.status or ''), \
                f'配不成对的帧应观察节点直接失败,实际 {result.status!r}'
        assert counters[_CLICK_COUNT_KEY] == 3, \
            f'读不准的帧不清计数,三次处置后应为 3,实际 {counters!r}'
        ctrl.set_phases([{'frame': _TOP_OVERLAY_FRAME}])
        ctrl.recorded_clicks.clear()
        _op, result = _visit(test_context, ops)

    assert not result.success, f'第三次处置后浮层仍在场应失败,实际 {result.status!r}'
    assert '合成确认浮层连续 3 次处置后仍在场' in (result.status or ''), \
        f'失败文案应说明连续处置后仍在场,实际 {result.status!r}'
    assert ctrl.recorded_clicks == [], f'该次访问零点击,实际 {ctrl.recorded_clicks!r}'
