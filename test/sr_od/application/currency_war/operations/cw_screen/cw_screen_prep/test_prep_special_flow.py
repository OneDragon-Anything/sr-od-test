"""备战特殊流程段剧本集(CwScreenPrep 段1 四查 + 段3 三处置;首批 = 剧本 4/6,
迭代 2026-11-18-prep-special-flow design §2.8,剧本 1/2/3/5 留 T-3 补齐)。

- 剧本 4 = 探针锁定:候选帧点商店 → 收起不出现(锁定形态)→ 接管失效写 +
  配对写(locked_resume=True ∧ locked_sync_done=False)+ 候选撤回 →
  同步步(部署原子序)→ 出战发出 → 交回;
- 剧本 6 = 锁定重派发帧:段3b retry 耗尽 → 访问 fail → 重派发新访问经
  第 0 查直达段3b,断言零前置段接触(防 heavy 观察在锁定帧执行——
  板面真值入状态容器会让同步步部署计划从空漂移为真,阻断面护栏)。

断言全部行为级(点击落点 / 写字段值 / 零前置段接触);harness =
fixture_controller(set_phases 帧序列 + click-hit 推进),``fast_sleep``
包裹;画面帧 = sr-od-test/screens 存档(货币战争-备战 /
货币战争-遭遇节点 现有建档帧,零新建档)。锁定形态的构造 = 商店点击
不推进帧序列(游戏侧按钮零响应的同构:点击发出、画面不变)。
"""

from __future__ import annotations

import types

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
)
from sr_od.application.currency_war.obs.cw_observation import (
    reset_phase_round_cache,
)
from sr_od.application.currency_war.operations.cw_screen import cw_screen_prep
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

#: 备战帧存档(P1-r9:恢复候选判据 round>1 的读数形态)。
_PREP_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_p1r9')
#: 非备战帧存档(出战屏态复验 stale 形态;遭遇面板盖住槽区,两识别标志 miss)。
_STALE_FRAME: tuple[str, str] = ('货币战争-遭遇节点', 'default')

#: 发出链机械段会裸睡的模块(harness fast_sleep 只覆盖宿主 op MRO 内模块,
#: 不在其内的动作 op / 拖拽原语模块单独桩——先例 = test_prep_actions)。
_NOSLEEP_MODULES: tuple[str, ...] = (
    'sr_od.application.currency_war.operations.cw_op.cw_move_unit_action',
    'sr_od.application.currency_war.operations.cw_op.cw_start_battle_action',
    'sr_od.application.currency_war.operations.actions.drag_cw_char',
    'sr_od.application.currency_war.prep_actions',
)


class _PrepTestController(FixtureController):
    """补机械动作触达面:mouse_move 记录(出战单击 / 拖拽 settle)+ drag_to
    双端记录(基类缺 mouse_move → AttributeError 会被框架吞成异常重试,
    伪失败形态)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_drags: list[tuple[tuple[int, int] | None,
                                        tuple[int, int]]] = []

    def mouse_move(self, pos) -> None:
        self.recorded_mouse_moves.append((int(pos.x), int(pos.y)))

    def drag_to(self, end, start=None, duration: float = 0.5,
                hold_time: float = 0.0) -> None:
        start_pt = ((int(start.x), int(start.y)) if start is not None
                    else None)
        self.recorded_drags.append((start_pt, (int(end.x), int(end.y))))


class _NoSleepTime:
    """模块级 ``time`` 替身:sleep 记录 no-op、其余属性透传真模块。"""

    def __init__(self, real_module: types.ModuleType) -> None:
        self._real = real_module
        self.skipped: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.skipped.append(seconds)

    def __getattr__(self, name: str):
        return getattr(self._real, name)


@pytest.fixture
def prep_env(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch,
             ) -> tuple[SrTestContext, _PrepTestController]:
    """特殊流程剧本夹具:假控制器换装(monkeypatch 自动还原)+ 动作 op
    模块裸睡桩(名单是超集,模块无裸 time 引用则跳过)。"""
    ctrl = _PrepTestController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    for mod_name in _NOSLEEP_MODULES:
        import importlib
        mod = importlib.import_module(mod_name)
        if hasattr(mod, 'time'):
            monkeypatch.setattr(mod, 'time', _NoSleepTime(mod.time))
    return test_context, ctrl


def _require_frame(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_PREP_FRAME, _STALE_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _attach_match(test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  **fields) -> types.SimpleNamespace:
    """挂流程态 Match 桩(monkeypatch 还原;session 每测新建 = GameState
    弱引用表新支,无跨测串染)。字段缺省 = 恢复候选帧前置(新局待探针)。"""
    match = types.SimpleNamespace(
        session=types.SimpleNamespace(),
        strategy=object(),        # 缺席门所需非 None(桩场景无策略器消费)
        is_new_match=fields.pop('is_new_match', True),
        resume_probe_pending=fields.pop('resume_probe_pending', True),
        locked_resume=fields.pop('locked_resume', False),
        locked_round=fields.pop('locked_round', 0),
        locked_sync_done=fields.pop('locked_sync_done', True),
        gs=None,
        **fields)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


def _spy_sync_battle(monkeypatch: pytest.MonkeyPatch,
                     calls: list[int],
                     snapshots: list[dict]) -> None:
    """段3b 入口 spy(计数 + Match 流程态快照;真函数透传)。快照时点 =
    段3b 进入 = 观察段配对写之后、同步步发出之前,即配对写/候选撤回的
    断言窗口。打桩点 = cw_screen_prep 模块绑定(act 内名字解析源)。"""
    real = cw_screen_prep.locked_resume_sync_and_battle

    def _spy(op, ctx):
        calls.append(1)
        snapshots.append({
            'locked_resume': ctx.cw_match.locked_resume,
            'locked_sync_done': ctx.cw_match.locked_sync_done,
            'resume_probe_pending': ctx.cw_match.resume_probe_pending,
        })
        return real(op, ctx)

    monkeypatch.setattr(cw_screen_prep, 'locked_resume_sync_and_battle', _spy)


def _patch_deploy_plan(monkeypatch: pytest.MonkeyPatch,
                       moves: list[CwActionMoveUnitParam],
                       ) -> list[int]:
    """部署计划单一源打桩(计划函数 = prep_actions 函数级 import 的源符号;
    返回调用计数容器供断言「同步步恰一次」)。"""
    calls: list[int] = []

    def _fake(session) -> list:
        calls.append(1)
        return list(moves)

    from sr_od.application.currency_war.strategies.impl.mandate_v1 import (
        deploy_plan,
    )
    monkeypatch.setattr(deploy_plan, 'battle_chain_deploy_params', _fake)
    return calls


def _click_count_in_area(ctrl: _PrepTestController, screen_name: str,
                         area_name: str) -> int:
    """落在指定 area rect 内的点击计数(探针与收起按钮是同一物理按钮的
    前后形态,rect 几乎全重叠——「有没有额外的收店点击」用计数判,
    裸 hit 布尔区分不了)。"""
    area = ctrl.ctx.screen_loader.get_area(screen_name, area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: {screen_name}/{area_name}'
    rect = area.pc_rect
    return sum(1 for p in ctrl.recorded_clicks
               if rect.x1 <= p.x <= rect.x2 and rect.y1 <= p.y <= rect.y2)


def _expected_center(ctx: SrTestContext, area_name: str
                     ) -> tuple[int, int]:
    """期望点击从同源 screen_info 档案现算(rect 中心)。"""
    area = ctx.screen_loader.get_area('货币战争-备战', area_name)
    assert area is not None and area.pc_rect is not None, \
        f'真建档缺 area: 货币战争-备战/{area_name}'
    rect = area.pc_rect
    return ((rect.x1 + rect.x2) // 2, (rect.y1 + rect.y2) // 2)


def test_probe_locked_pair_write_then_sync_battle(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 4 探针锁定:候选帧点商店 → 收起不出现 → 失效写 + 配对写 +
    候选撤回 → 同步步 → 出战发出 → 交回。"""
    test_context, ctrl = prep_env
    _require_frame(test_context)
    reset_phase_round_cache()   # 清位面轮次模块缓存(单调守卫跨测防串染)
    ctrl.set_phases([{'frame': _PREP_FRAME}])   # 无 exit:锁定形态,点击不推进
    match = _attach_match(test_context, monkeypatch,
                          is_new_match=True, resume_probe_pending=True,
                          locked_resume=False, locked_sync_done=True)
    moves = [CwActionMoveUnitParam(src_domain='bench', src_slot=0,
                                   dst_domain='front', dst_slot=1)]
    plan_calls = _patch_deploy_plan(monkeypatch, moves)
    calls: list[int] = []
    snapshots: list[dict] = []
    _spy_sync_battle(monkeypatch, calls, snapshots)

    op = CwScreenPrep(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    # —— 交回:访问 success(段3b 出战成功锁解除 → 交回外循环战斗分支)
    assert result.success, f'锁定出战成功应交回 success,实际 {result.status!r}'
    assert len(calls) == 1, f'段3b 应恰执行一次,实际 {len(calls)} 次'

    # —— 探针点击落点:点「按钮-商店」试探(锁定形态 = 点击后画面不变,
    # 「按钮-收起」不出现 → 判锁定)。商店/收起两 area 是同一物理按钮的
    # 前后形态(rect 几乎全重叠),「非锁定收店点击」用计数判:命中该
    # 区域的点击应恰 1 次(= 探针本身),不得有第二次收店点击。
    assert ctrl.click_hit_area('货币战争-备战', '按钮-商店'), \
        f'探针应点击按钮-商店,实际点击 {ctrl.recorded_clicks}'
    assert _click_count_in_area(ctrl, '货币战争-备战-开商店', '按钮-收起') == 1, \
        ('锁定形态不得有收店点击(区域命中应恰探针 1 次),'
         f'实际 {ctrl.recorded_clicks}')

    # —— 接管失效写(候选过判即写):tracked_account_observed 写 False,
    # source=logic、evidence=takeover_invalidation(备战帧确认点 =
    # CwScreenPrep,与战斗帧确认点两确认点分流)
    gs = game_state_of(match.session)
    _inv = gs.tracked_account_observed
    assert _inv.value is False, \
        f'接管失效写应置 False,实际 {_inv.value!r}'
    assert _inv.source == 'logic', f'失效写应走 logic 通道,实际 {_inv.source!r}'
    assert _inv.evidence == 'takeover_invalidation', \
        f'失效写 evidence 应为 takeover_invalidation,实际 {_inv.evidence!r}'

    # —— 配对写 + 候选撤回(段3b 进入时点快照 = 段2 写后、同步步前):
    # locked_resume=True ∧ locked_sync_done=False 同帧配对;
    # resume_probe_pending 无条件撤回。
    assert snapshots == [{
        'locked_resume': True,
        'locked_sync_done': False,
        'resume_probe_pending': False,
    }], f'段3b 进入时配对写/候选撤回不符,实际 {snapshots!r}'
    assert match.locked_round == 9, \
        f'锁定确认应写轮次读数(1-9 帧),实际 {match.locked_round!r}'

    # —— 同步步:部署计划恰一次、原子序发出(拖拽 ×1),发出即写证据位
    assert plan_calls == [1], f'同步步应恰执行一次部署计划,实际 {plan_calls}'
    assert len(ctrl.recorded_drags) == 1, \
        f'同步步应发出部署原子 ×1,实际 {ctrl.recorded_drags}'
    assert match.locked_sync_done is True, \
        '同步步发出后应置证据位 locked_sync_done'

    # —— 出战发出:单击命中「按钮-出战」,时序 = 拖拽 settle 在前
    assert ctrl.click_hit_area('货币战争-备战', '按钮-出战'), \
        f'出战应点击按钮-出战,实际点击 {ctrl.recorded_clicks}'
    exp_b0 = _expected_center(test_context, '备战栏-1')
    exp_btn = _expected_center(test_context, '按钮-出战')
    assert ctrl.recorded_mouse_moves == [exp_b0, exp_btn], \
        (f'机械时序应为 拖拽settle → 出战按钮(mouse_move 序),'
         f'实际 {ctrl.recorded_mouse_moves}')

    # —— 锁解除(出战成功 → locked_after_start_battle 写回 False)
    assert match.locked_resume is False, '出战成功后应解除锁定'


def test_locked_redispatch_hits_check0_zero_pre_segment(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 6 锁定重派发帧:段3b retry 耗尽 → 访问 fail → 重派发新访问
    经第 0 查直达段3b,断言零前置段接触(heavy 观察未在锁定帧执行)。"""
    test_context, ctrl = prep_env
    _require_frame(test_context)
    ctrl.set_phases([{'frame': _STALE_FRAME}])   # 无 exit:出战屏态复验恒 stale
    match = _attach_match(test_context, monkeypatch,
                          resume_probe_pending=False,   # 候选已清(重派发形态)
                          locked_resume=True,           # 锁定确认态
                          locked_sync_done=False)       # 同步步待执行
    plan_calls = _patch_deploy_plan(monkeypatch, [])
    calls: list[int] = []
    snapshots: list[dict] = []
    _spy_sync_battle(monkeypatch, calls, snapshots)
    gs = game_state_of(match.session)

    enter_running_state(test_context)
    op1 = CwScreenPrep(test_context)
    op2: CwScreenPrep | None = None
    try:
        # —— 第一次访问:段3b retry 耗尽 → 访问 fail(stale 帧 → 出战未执行
        # → round_retry;框架节点预算 3 耗尽 = 首跑 + 3 retry = 4 次)
        with fast_sleep(op1):
            result1 = op1.execute()
        assert not result1.success, \
            f'段3b retry 耗尽应访问 fail,实际 {result1.status!r}'
        assert len(calls) == 4, \
            (f'段3b 应按框架预算执行 1 首跑 + 3 retry,实际 {len(calls)} 次;'
             f'status={result1.status!r}')
        assert match.locked_resume is True, 'retry 保锁:锁定态不得解除'
        assert plan_calls == [], \
            f'stale 帧(屏态复验失败)不应执行部署计划,实际 {plan_calls}'

        # —— 重派发(主循环 fail 后重派新访问 = 新 op 实例):经第 0 查
        # 直达段3b;零前置段接触 = heavy 观察未执行(frame_class_prep 未标、
        # 板面真值未入状态容器)且无探针点击
        calls.clear()
        op2 = CwScreenPrep(test_context)
        with fast_sleep(op2):
            result2 = op2.execute()
        assert not result2.success, \
            f'重派发访问同样 stale → 应再 fail,实际 {result2.status!r}'
        assert len(calls) == 4, \
            f'重派发访问应直达段3b 并再耗尽预算,实际 {len(calls)} 次'
        assert all(s['locked_resume'] is True for s in snapshots), \
            '重派发访问应经第 0 查直达段3b(段3b spy 全程锁定态)'
    finally:
        reset_running_state(test_context, op1)
        if op2 is not None:
            reset_running_state(test_context, op2)

    # —— 零前置段接触(两访问合计):
    # ① 无探针/收店/返回补给类点击(唯一合法触达面 = 出战发出链,而 stale
    #    帧连出战点击都没有 → 全程零点击);
    assert ctrl.recorded_clicks == [], \
        f'锁定帧零前置段接触:不应有任何点击,实际 {ctrl.recorded_clicks}'
    # ② heavy 观察未执行:帧代次未标 full(常规路径在入口 heavy 后无条件
    #    标写,此字段即「前置段跑没跑」的哨兵;非 Field 簿记,缺省 'none');
    assert gs.frame_class_prep == 'none', \
        (f'零前置段接触:frame_class_prep 应保持 none,'
         f'实际 {gs.frame_class_prep!r}')
    # ③ 板面真值未入状态容器(heavy 观察 → bench 观察写,source 翻
    #    observation;未接触 = 保持开局种子 logic_rand 形态);
    assert gs.bench.source == 'logic_rand', \
        (f'零前置段接触:bench 未被观察写,实际 source='
         f'{gs.bench.source!r}')
    # ④ 接管失效写不在重派发帧发生(b 查被跳过,失效写只挂候选过判)
    assert gs.tracked_account_observed.value is None, \
        ('重派发帧无候选过判,不应发生接管失效写,'
         f'实际 {gs.tracked_account_observed.value!r}')
