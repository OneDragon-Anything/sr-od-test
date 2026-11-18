"""备战特殊流程段剧本集(CwScreenPrep 段1 四查 + 段3 三处置;六剧本全集,
迭代 2026-11-18-prep-special-flow design §2.8。剧本 4/6 首批(T-2),
剧本 1/2/3/5 补齐(T-3)):

- 剧本 1 = 常规帧:四查全否 → 前置段全量照旧(清场 → 收店探针 → heavy
  → 补采委派 → 审计,生产现行序取锚)→ serial 置位 → 策略器路径;
  零特殊流程处置调用(现行为零变化);
- 剧本 2 = 返回按钮帧:a 查 OCR 识别 → 跳前置段 → 段3a 点击(lcs 0.9)
  → 计数器分键 ``back_to_strategy_symptom`` 累加 → 交回;附两防线:
  strategy_state 缺席 None 守卫不炸 / 共享子串『请选择投资策略』
  (lcs 6/8=0.75 < 0.9)不触发 a 查;
- 剧本 3 = 探针非锁定:候选帧点商店 → 收起出现 → 失效写已发生 →
  候选撤回 → 收店 → 按序跑齐前置段 → 策略器路径;
- 剧本 4 = 探针锁定:候选帧点商店 → 收起不出现(锁定形态)→ 接管失效写 +
  配对写(locked_resume=True ∧ locked_sync_done=False)+ 候选撤回 →
  同步步(部署原子序)→ 出战发出 → 交回;
- 剧本 5 = 补给未确认:c 查识别 → 跳前置段 → 点「按钮-返回补给阶段」
  → 交回;补给已确认(chosen_supply 在场)→ 走常规路径(零分流点击);
- 剧本 6 = 锁定重派发帧:段3b retry 耗尽 → 访问 fail → 重派发新访问经
  第 0 查直达段3b,断言零前置段接触(防 heavy 观察在锁定帧执行——
  板面真值入状态容器会让同步步部署计划从空漂移为真,阻断面护栏)。

断言全部行为级(点击落点 / 写字段值 / 调用序 / 零前置段接触);harness =
fixture_controller(set_phases 帧序列 + click-hit 推进),``fast_sleep``
包裹;画面帧 = sr-od-test/screens 存档(货币战争-备战 /
货币战争-备战-开商店 / 货币战争-遭遇节点 现有建档帧,零新建档)。锁定
形态的构造 = 商店点击不推进帧序列(游戏侧按钮零响应的同构:点击发出、
画面不变);返回按钮帧的帧资产 = 夹具内 PIL 渲染文本构造(存档无此
形态帧,零落盘零真实副作用)。
"""

from __future__ import annotations

import types
from pathlib import Path

import numpy as np
import pytest
from cv2.typing import MatLike
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    GameState,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    strategy_state_of,
)
from sr_od.application.currency_war.kernel.cw_vocab import (
    CwActionMoveUnitParam,
    CwActionObsParam,
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
#: 开商店帧存档(探针非锁定的收起出现形态;「按钮-收起」OCR 命中)。
_SHOP_OPEN_FRAME: tuple[str, str] = ('货币战争-备战-开商店', 'shop_open')
#: 补给节点备战帧存档(nodeseq current=supply 且「按钮-返回补给阶段」在场)。
_SUPPLY_FRAME: tuple[str, str] = ('货币战争-备战', '补给节点')

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
    伪失败形态);另支持 phase['frame'] 直接给 ndarray(夹具内构造帧,
    剧本 2 返回按钮帧用——存档无该形态帧)。"""

    def __init__(self, ctx: SrTestContext) -> None:
        FixtureController.__init__(self, ctx)
        self.recorded_mouse_moves: list[tuple[int, int]] = []
        self.recorded_drags: list[tuple[tuple[int, int] | None,
                                        tuple[int, int]]] = []

    @property
    def current_frame(self) -> MatLike:
        phase = self._phases[self._phase_idx]
        if isinstance(phase.get('frame'), np.ndarray):
            return phase['frame']
        return FixtureController.current_frame.fget(self)

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


def _require_frame(test_context: SrTestContext,
                   *frames: tuple[str, str]) -> None:
    """存档缺失 skip(采到后自动恢复),不 error;缺省 = 剧本 4/6 所需集。"""
    for screen_name, state in (frames or (_PREP_FRAME, _STALE_FRAME)):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


#: _attach_match 的策略器参数哨兵(默认 object() 非 None;None = 显式缺席门)。
_DEFAULT_STRATEGY: object = object()


def _attach_match(test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch,
                  *,
                  strategy: object = _DEFAULT_STRATEGY,
                  counters: dict | None = None,
                  **fields) -> types.SimpleNamespace:
    """挂流程态 Match 桩(monkeypatch 还原;session 每测新建 = GameState
    弱引用表新支,无跨测串染)。字段缺省 = 恢复候选帧前置(新局待探针)。
    ``strategy`` = 缺席门所需非 None(桩场景无策略器消费);传 None 显式
    制造缺席门命中(剧本 2 lcs 防线支),传策略器替身 = 常规路径剧本。
    ``counters`` 传入时挂策略状态替身(cw4_counters 读面 +
    cw4_segment_serial/cw4_frame_action_record 置位面;缺席 = None 守卫
    路径,剧本 2 附加支)。"""
    match = types.SimpleNamespace(
        session=types.SimpleNamespace(),
        strategy=object() if strategy is _DEFAULT_STRATEGY else strategy,
        is_new_match=fields.pop('is_new_match', True),
        resume_probe_pending=fields.pop('resume_probe_pending', True),
        locked_resume=fields.pop('locked_resume', False),
        locked_round=fields.pop('locked_round', 0),
        locked_sync_done=fields.pop('locked_sync_done', True),
        gs=None,
        **fields)
    if counters is not None:
        match.session.strategy_state = types.SimpleNamespace(
            cw4_counters=counters,
            cw4_segment_serial=0,
            cw4_frame_action_record=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


# ===== T-3 补齐(剧本 1/2/3/5)公共件 =====

#: 系统字体(PIL 渲染构造帧用;Windows 10+ 自带,缺失 = skip 同存档缺失语义)。
_FONT_PATH: str = 'C:/Windows/Fonts/msyh.ttc'

#: 前置段现行序(断言锚 = 生产 observe node 现行编排:四查全否 → 缺席门 →
#: 清场 → 收店探针 → heavy 观察 → 补采委派 → 审计族)。
_FRONT_SEGMENT_ORDER: list[str] = ['清场', '收店探针', 'heavy', '补采委派', '审计']

#: 夹具种子/断言共用的渠道签名(测试侧观察写只求通道合法,actor 沿备战写端)。
_TEST_OBS_SIG: ChannelSig = ChannelSig(family='obs', actor='CwScreenPrep',
                                       screen='货币战争-备战', mode='read')


class _StrategyStub:
    """策略器替身:恒发 ``CwActionObsParam(scope='outer_loop')``(返回主循环
    重新观察——决策环内零动作执行面,常规路径剧本以此干净交回)。"""

    def __init__(self) -> None:
        self.calls: int = 0

    def decide_prep_screen(self) -> CwActionObsParam:
        self.calls += 1
        return CwActionObsParam(scope='outer_loop')


def _seed_regular_gs(gs: GameState) -> None:
    """常规路径前置条件:补采委派门两支按否(位面 boss 真值在场 + 词缀
    非随机态)→ 前置段全量直通,不委派 CwEntryPlaneIntel(委派编排 =
    入口链专属测试域,不在本剧本断言面)。走 observe 通道:覆盖 logic_rand
    开局种子 = 预期内采新(logic_rand_outcome 台账行),source 翻 observation
    后「enemy_affixes ∈ logic_rand_fields」判定即否。"""
    gs.observe(gs.plane_bosses, ['boss-1', 'boss-2', 'boss-3'],
               evidence='test_seed', sig=_TEST_OBS_SIG)
    gs.observe(gs.enemy_affixes, [], evidence='test_seed', sig=_TEST_OBS_SIG)


def _spy_front_segments(monkeypatch: pytest.MonkeyPatch,
                        order: list[str]) -> None:
    """前置段序 spy(真方法透传,只记调用序;断言锚 = 生产现行编排)。
    打桩点 = CwScreenPrep 类绑定(act/observe 内 self 方法解析源)。"""
    real_clear = CwScreenPrep._clear_entry_overlays
    real_collapse = CwScreenPrep._try_collapse_open_shop
    real_observe = CwScreenPrep._observe
    real_delegate = CwScreenPrep._delegate_plane_intel_if_needed
    real_audit = CwScreenPrep._v2_post_frame_accounting

    def _clear(self) -> None:
        order.append('清场')
        return real_clear(self)

    def _collapse(self) -> bool:
        order.append('收店探针')
        return real_collapse(self)

    def _observe(self, heavy: bool, screen: MatLike | None = None):
        order.append('heavy' if heavy else '观察-轻')
        return real_observe(self, heavy, screen)

    def _delegate(self, session) -> object | None:
        order.append('补采委派')
        return real_delegate(self, session)

    def _audit(self, obs, session) -> None:
        order.append('审计')
        return real_audit(self, obs, session)

    monkeypatch.setattr(CwScreenPrep, '_clear_entry_overlays', _clear)
    monkeypatch.setattr(CwScreenPrep, '_try_collapse_open_shop', _collapse)
    monkeypatch.setattr(CwScreenPrep, '_observe', _observe)
    monkeypatch.setattr(CwScreenPrep, '_delegate_plane_intel_if_needed', _delegate)
    monkeypatch.setattr(CwScreenPrep, '_v2_post_frame_accounting', _audit)


def _stub_heavy_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    """heavy 识别核打桩(observe_full 回执 = {} → 各识别域按失读分支走)。

    断言面 = 观察 node 编排序与特殊流程分流,heavy 识别本体(身份/星级/
    装备 SIFT)有专测(test_cw_observe_full 同款打桩边界);打桩同时收窄
    识别链的截图落盘面(cw_shot 族重定向 no-op——识别 MISS/异常采集会写
    真实 .debug 目录,测试零真实副作用红线)。打桩点 = 调用时点解析源
    (cw_screen_prep 函数级 import + cw_observe 模块全局)。

    另:晶矿简易装备池按设计意图补非空(T-3 报告申报的生产缺陷:
    cw_ore_reward._SIMPLE_EQUIP_POOL 过滤 ``category == '简易'`` 而注册表
    落值「简易装备」→ 恒空池,采样到 equip 掉落即 IndexError 炸备战环;
    测试不改生产代码,常量补意图值让 report_spheres_observed 真实链
    可完成)。"""
    from sr_od.application.currency_war.kernel import cw_observe
    from sr_od.application.currency_war.kernel import cw_ore_reward
    from sr_od.application.currency_war.obs import cw_observe_full
    monkeypatch.setattr(cw_observe_full, 'observe_full',
                        lambda *a, **k: {})
    monkeypatch.setattr(cw_observe, 'cw_shot', lambda image, name: None)
    monkeypatch.setattr(cw_observe, 'cw_shot_unique',
                        lambda image, label: None)
    monkeypatch.setattr(cw_ore_reward, '_SIMPLE_EQUIP_POOL', ('蓝钻', '红钻'))


def _require_font() -> None:
    """系统字体缺失 skip(同存档缺失语义;PIL 构造帧依赖)。"""
    if not Path(_FONT_PATH).exists():
        pytest.skip(f'系统字体缺失:{_FONT_PATH}')


def _render_text_frame(text: str
                       ) -> tuple[MatLike, tuple[int, int, int, int]]:
    """内存构造帧:PIL 渲染单行文本于深色底(零落盘零真实副作用;OCR
    可检实证 = 剧本 2 断言)。返回 ``(帧, 文本包围盒 x1y1x2y2)``——
    包围盒 = OCR 点击落点的断言域(点击落 OCR 命中框中心 ≈ 文本盒)。"""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(_FONT_PATH, 22)
    img = Image.new('RGB', (1920, 1080), (24, 26, 30))
    draw = ImageDraw.Draw(img)
    draw.text((1600, 52), text, font=font, fill=(235, 235, 235))
    bbox = draw.textbbox((1600, 52), text, font=font)
    return (np.asarray(img),
            (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])))


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


def _spy_takeover_invalidation(monkeypatch: pytest.MonkeyPatch,
                               records: list[tuple]) -> None:
    """接管失效写 spy(真方法透传,前后值快照)。载体理由:常规路径后续
    heavy 对账锚定写(evidence=observation_anchor,值 True)会覆盖段2 的
    失效写终态——探针非锁定剧本(剧本 3)的「失效写已发生」断言必须取
    写入时点快照(锁定剧本 4 无前置段,终态断言即可,载体不同)。
    打桩点 = CwScreenPrep 类绑定(observe 内 self 方法解析源)。"""
    real = CwScreenPrep._invalidate_tracked_on_takeover

    def _spy(self) -> None:
        gs = game_state_of(self._match().session)
        before = gs.tracked_account_observed.value
        real(self)
        records.append((before, gs.tracked_account_observed.value,
                        gs.tracked_account_observed.evidence))

    monkeypatch.setattr(CwScreenPrep, '_invalidate_tracked_on_takeover', _spy)


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


# ===== T-3 补齐:剧本 1 / 2 / 3 / 5 =====

def test_regular_frame_runs_full_front_segments_in_order(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 1 常规帧零变化:四查全否 → 前置段全量照旧(现行序)→
    serial 置位 → 策略器路径进入;零特殊流程处置调用。"""
    test_context, ctrl = prep_env
    _require_frame(test_context)
    ctrl.set_phases([{'frame': _PREP_FRAME}])
    counters: dict = {}
    strategy = _StrategyStub()
    match = _attach_match(test_context, monkeypatch, strategy=strategy,
                          counters=counters,
                          is_new_match=False, resume_probe_pending=False,
                          locked_resume=False, locked_sync_done=True)
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)
    _stub_heavy_recognition(monkeypatch)
    _inv_records: list[tuple] = []
    _spy_takeover_invalidation(monkeypatch, _inv_records)
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

    # —— 常规访问 success(策略器发 Obs:outer_loop 交回)
    assert result.success, f'常规帧应访问 success,实际 {result.status!r}'
    # —— 前置段按生产现行序全量执行(清场 → 收店探针 → heavy → 补采 → 审计)
    assert order == _FRONT_SEGMENT_ORDER, \
        f'前置段应按现行序全量执行,实际 {order!r}'
    assert gs.frame_class_prep == 'full', \
        ('前置段哨兵:入口 heavy 后应标帧代次 full,'
         f'实际 {gs.frame_class_prep!r}')
    # —— serial 置位(备战期开始,访问入口 +1;Obs:outer_loop 拦截在
    #    决策环内,不写续段 token)
    _st = strategy_state_of(match.session)
    assert _st.cw4_segment_serial == 1, \
        f'访问入口应置位段序号 +1,实际 {_st.cw4_segment_serial!r}'
    assert _st.cw4_frame_action_record is None, \
        (f'Obs:outer_loop 拦截不写续段 token,'
         f'实际 {_st.cw4_frame_action_record!r}')
    # —— 策略器路径进入(决策读恰一次)
    assert strategy.calls == 1, \
        f'策略器 decide_prep_screen 应恰调用一次,实际 {strategy.calls}'
    # —— 零特殊流程处置调用:零段3b(锁定出战)、零计数分键(段3a)、
    #    零点击(段3a/3c/探针的载体都是点击)、零接管失效写(b 查未触发)
    assert calls == [], f'常规帧不应进入段3b,实际段3b 调用 {len(calls)} 次'
    assert counters == {}, \
        f'常规帧不应产生返回按钮计数,实际 {counters!r}'
    assert ctrl.recorded_clicks == [], \
        f'常规帧零处置点击,实际 {ctrl.recorded_clicks}'
    # 接管失效写零发生:最终写 = 前置段对账锚定写(观察态退出点,
    # evidence=observation_anchor);失效写若在锚定前发生,载体 =
    # _inv_records 零调用(候选过判是唯一调用面)。
    assert _inv_records == [], \
        f'常规帧无候选过判,不应发生接管失效写,实际 {_inv_records!r}'
    assert gs.tracked_account_observed.evidence == 'observation_anchor', \
        (f'常规路径最终写应为对账锚定写,'
         f'实际 {gs.tracked_account_observed.evidence!r}')
    # —— 四查输入未被改写(b 查按否跳过、锁定态保持)
    assert match.resume_probe_pending is False and match.locked_resume is False, \
        (f'常规帧不应改写流程态字段,实际 probe='
         f'{match.resume_probe_pending!r} locked={match.locked_resume!r}')


def test_back_button_frame_clicks_return_then_hands_back(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 返回按钮帧:a 查 OCR 识别(夹具内构造帧)→ 跳前置段 →
    段3a 点击「返回投资策略选择」(落点 = 构造文本框内)→ 计数器分键
    ``back_to_strategy_symptom`` 累加 → 交回。"""
    test_context, ctrl = prep_env
    _require_font()
    frame, bbox = _render_text_frame('返回投资策略选择')
    ctrl.set_phases([{'frame': frame}])
    counters: dict = {}
    match = _attach_match(test_context, monkeypatch, counters=counters,
                          is_new_match=False, resume_probe_pending=False,
                          locked_resume=False, locked_sync_done=True)
    gs = game_state_of(match.session)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)
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

    # —— a 查识别 → 段3a 点击 → 交回 success
    assert result.success, f'返回按钮帧应交回 success,实际 {result.status!r}'
    # —— 跳前置段:零前置段方法调用 + 帧代次保持 none(哨兵同剧本 6)
    assert order == [], f'返回按钮帧应跳全部前置段,实际 {order!r}'
    assert gs.frame_class_prep == 'none', \
        (f'跳前置段:帧代次应保持 none,实际 {gs.frame_class_prep!r}')
    # —— 点击落点:唯一点击 = 段3a 返回点击,落在构造文本包围盒内
    assert len(ctrl.recorded_clicks) == 1, \
        (f'返回按钮帧唯一点击 = 段3a 返回点击,'
         f'实际 {ctrl.recorded_clicks}')
    cx, cy = ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y
    assert bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3], \
        (f'返回点击应落在 OCR 命中文本(包围盒 {bbox})内,'
         f'实际 ({cx}, {cy})')
    # —— 计数器分键累加(遥测单一载体;寿命 per-match 每局归零)
    assert counters == {'back_to_strategy_symptom': 1}, \
        f'返回按钮症状计数应累加 1,实际 {counters!r}'
    # —— 零段3b、流程态字段未被改写
    assert calls == [], f'返回按钮帧不应进入段3b,实际段3b 调用 {len(calls)} 次'
    assert match.resume_probe_pending is False and match.locked_resume is False, \
        '返回按钮帧不应改写锁定/候选流程态字段'


def test_back_button_frame_none_state_guard_skips_counter(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 附加(None 守卫):strategy_state 缺席 → 计数分键守卫跳过
    不炸,处置点击与交回照常。"""
    test_context, ctrl = prep_env
    _require_font()
    frame, bbox = _render_text_frame('返回投资策略选择')
    ctrl.set_phases([{'frame': frame}])
    match = _attach_match(test_context, monkeypatch,   # session 无 strategy_state
                          is_new_match=False, resume_probe_pending=False)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)

    op = CwScreenPrep(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, \
        f'None 守卫路径应仍交回 success,实际 {result.status!r}'
    assert strategy_state_of(match.session) is None
    assert len(ctrl.recorded_clicks) == 1, \
        f'处置点击应照常发出,实际 {ctrl.recorded_clicks}'
    cx, cy = ctrl.recorded_clicks[0].x, ctrl.recorded_clicks[0].y
    assert bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3], \
        (f'返回点击应落在构造文本包围盒 {bbox} 内,实际 ({cx}, {cy})')
    assert order == [], f'应跳全部前置段,实际 {order!r}'


def test_back_button_lcs_guard_ignores_select_screen_text(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 防线(lcs 0.9 语义):共享子串的『请选择投资策略』
    (lcs 6/8=0.75 < 0.9)不得触发 a 查——误匹配会吞投资策略屏致死循环
    (防线理由随迁注释);a 查未命中 → 四查全否 → 落 match 缺席门。"""
    test_context, ctrl = prep_env
    _require_font()
    frame, bbox = _render_text_frame('请选择投资策略')
    ctrl.set_phases([{'frame': frame}])
    _attach_match(test_context, monkeypatch, strategy=None,
                  is_new_match=False, resume_probe_pending=False)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)

    op = CwScreenPrep(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    # —— a 查未触发:访问落缺席门 fail(若误触发,a 查路径会 success 交回)
    assert not result.success, \
        f'共享子串文本不得触发 a 查(应落缺席门 fail),实际 {result.status!r}'
    assert '无 cw_match' in (result.status or ''), \
        f'四查全否应落 match 缺席门,实际 {result.status!r}'
    # —— 零点击(未把选择屏文本当返回按钮点掉)
    assert ctrl.recorded_clicks == [], \
        f'lcs 防线:不应有点击发出,实际 {ctrl.recorded_clicks}'
    assert order == [], f'零前置段接触,实际 {order!r}'


def test_probe_not_locked_collapses_then_runs_regular_path(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 3 探针非锁定:候选帧点商店 → 收起出现 → 失效写已发生 →
    候选撤回 → 收店 → 按序跑齐前置段 → 策略器路径。"""
    test_context, ctrl = prep_env
    _require_frame(test_context, _PREP_FRAME, _SHOP_OPEN_FRAME)
    reset_phase_round_cache()
    # 探针两形态帧序列:备战(点商店推进)→ 开商店(收起出现;点收起推进)
    # → 备战(收店后常规路径全量)。
    ctrl.set_phases([
        {'frame': _PREP_FRAME,
         'exit': ('on_click_in', '货币战争-备战', '按钮-商店')},
        {'frame': _SHOP_OPEN_FRAME,
         'exit': ('on_click_in', '货币战争-备战-开商店', '按钮-收起')},
        {'frame': _PREP_FRAME},
    ])
    counters: dict = {}
    strategy = _StrategyStub()
    match = _attach_match(test_context, monkeypatch, strategy=strategy,
                          counters=counters,
                          is_new_match=True, resume_probe_pending=True,
                          locked_resume=False, locked_sync_done=True)
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)
    _stub_heavy_recognition(monkeypatch)
    _inv_records: list[tuple] = []
    _spy_takeover_invalidation(monkeypatch, _inv_records)
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

    # —— 访问 success(非锁定 → 常规路径 → 策略器交回)
    assert result.success, f'探针非锁定应走常规路径 success,实际 {result.status!r}'
    # —— 探针点击:点「按钮-商店」试探;收店点击发生在探针之后
    #    (商店/收起是同一物理按钮的前后形态,区域命中计数判:探针 1 +
    #    收店 1 = 2;锁定形态 = 1,见剧本 4 对照)
    assert ctrl.click_hit_area('货币战争-备战', '按钮-商店'), \
        f'探针应点击按钮-商店,实际点击 {ctrl.recorded_clicks}'
    assert _click_count_in_area(ctrl, '货币战争-备战-开商店', '按钮-收起') == 2, \
        ('非锁定应有收店点击(区域命中 = 探针 1 + 收店 1),'
         f'实际 {ctrl.recorded_clicks}')
    # —— 接管失效写已发生(候选过判即写,先于探针点击;备战帧确认点 =
    #    CwScreenPrep,与战斗帧确认点两确认点分流)。写入时点快照:
    #    None → False / evidence=takeover_invalidation;后续 heavy 对账
    #    锚定写(True)会覆盖终态,终态载体见下方锚定断言。
    assert _inv_records == [(None, False, 'takeover_invalidation')], \
        (f'候选过判应发生接管失效写(None→False/takeover_invalidation),'
         f'实际 {_inv_records!r}')
    # —— 候选撤回(无条件,防同 run 重探针)+ 锁定配对写零发生
    assert match.resume_probe_pending is False, '候选应无条件撤回'
    assert match.locked_resume is False and match.locked_sync_done is True \
        and match.locked_round == 0, \
        (f'非锁定不得写锁定配对字段,实际 locked={match.locked_resume!r} '
         f'sync={match.locked_sync_done!r} round={match.locked_round!r}')
    assert calls == [], f'非锁定不进段3b,实际段3b 调用 {len(calls)} 次'
    # —— 收店后按序跑齐全部前置段(= fresh visit 全序列)+ 策略器路径
    assert order == _FRONT_SEGMENT_ORDER, \
        f'收店后应按现行序跑齐前置段,实际 {order!r}'
    assert gs.frame_class_prep == 'full', \
        (f'前置段哨兵:帧代次应标 full,实际 {gs.frame_class_prep!r}')
    assert strategy.calls == 1, \
        f'策略器 decide_prep_screen 应恰调用一次,实际 {strategy.calls}'
    assert strategy_state_of(match.session).cw4_segment_serial == 1, \
        ('常规路径访问入口应置位段序号 +1,实际 '
         f'{strategy_state_of(match.session).cw4_segment_serial!r}')


def test_supply_unconfirmed_diverts_to_supply_screen(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 5 补给未确认:c 查识别(nodeseq current=supply ∧ chosen_supply
    未确认)→ 跳前置段 → 点「按钮-返回补给阶段」→ 交回。"""
    test_context, ctrl = prep_env
    _require_frame(test_context, _SUPPLY_FRAME)
    ctrl.set_phases([{'frame': _SUPPLY_FRAME}])
    match = _attach_match(test_context, monkeypatch,
                          is_new_match=False, resume_probe_pending=False,
                          locked_resume=False, locked_sync_done=True)
    gs = game_state_of(match.session)
    assert gs.chosen_supply.value is None   # 未确认前置 = 状态容器缺省
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)
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

    # —— c 查识别 → 段3c 点击 → 交回 success
    assert result.success, f'补给未确认帧应交回 success,实际 {result.status!r}'
    assert ctrl.click_hit_area('货币战争-备战', '按钮-返回补给阶段'), \
        (f'应点击按钮-返回补给阶段,实际点击 {ctrl.recorded_clicks}')
    assert len(ctrl.recorded_clicks) == 1, \
        (f'补给未确认帧唯一点击 = 返回补给阶段,实际 {ctrl.recorded_clicks}')
    # —— 跳前置段(帧代次哨兵 + 零前置段方法调用)
    assert order == [], f'补给未确认帧应跳全部前置段,实际 {order!r}'
    assert gs.frame_class_prep == 'none', \
        (f'跳前置段:帧代次应保持 none,实际 {gs.frame_class_prep!r}')
    # —— 零段3b、零探针点击(商店按钮)、分流字段零改写
    assert calls == [], f'补给未确认帧不应进入段3b,实际段3b 调用 {len(calls)} 次'
    assert _click_count_in_area(ctrl, '货币战争-备战', '按钮-商店') == 0, \
        (f'补给分流不得触发探针点击,实际 {ctrl.recorded_clicks}')
    assert gs.chosen_supply.value is None, '分流处置不改写补给确认字段'


def test_supply_confirmed_takes_regular_path(
        prep_env: tuple[SrTestContext, _PrepTestController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 5 补给已确认:chosen_supply 在场 → 零分流点击,走常规路径
    (前置段全量 + 策略器路径)。"""
    test_context, ctrl = prep_env
    _require_frame(test_context, _SUPPLY_FRAME)
    ctrl.set_phases([{'frame': _SUPPLY_FRAME}])
    counters: dict = {}
    strategy = _StrategyStub()
    match = _attach_match(test_context, monkeypatch, strategy=strategy,
                          counters=counters,
                          is_new_match=False, resume_probe_pending=False,
                          locked_resume=False, locked_sync_done=True)
    gs = game_state_of(match.session)
    _seed_regular_gs(gs)
    gs.observe(gs.chosen_supply, ('角色·测试', ('装备甲', '装备乙')),
               evidence='test_seed', sig=_TEST_OBS_SIG)
    order: list[str] = []
    _spy_front_segments(monkeypatch, order)
    _stub_heavy_recognition(monkeypatch)
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

    # —— 已确认 → 常规路径访问 success
    assert result.success, f'补给已确认应走常规路径 success,实际 {result.status!r}'
    # —— 零分流点击(不得再回补给屏:死循环面)
    assert ctrl.recorded_clicks == [], \
        (f'补给已确认零分流点击,实际 {ctrl.recorded_clicks}')
    # —— 前置段按现行序全量 + 策略器路径
    assert order == _FRONT_SEGMENT_ORDER, \
        f'已确认应按现行序跑齐前置段,实际 {order!r}'
    assert gs.frame_class_prep == 'full', \
        (f'前置段哨兵:帧代次应标 full,实际 {gs.frame_class_prep!r}')
    assert strategy.calls == 1, \
        f'策略器 decide_prep_screen 应恰调用一次,实际 {strategy.calls}'
    assert strategy_state_of(match.session).cw4_segment_serial == 1, \
        ('常规路径访问入口应置位段序号 +1,实际 '
         f'{strategy_state_of(match.session).cw4_segment_serial!r}')
    assert calls == [], f'已确认帧不应进入段3b,实际段3b 调用 {len(calls)} 次'
