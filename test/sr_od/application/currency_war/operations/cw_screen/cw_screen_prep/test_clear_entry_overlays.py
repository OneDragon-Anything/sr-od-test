"""环入口清场段(``CwScreenPrep._clear_entry_overlays`` ×「货币战争-备战-奇遇介绍」浮层)。

锁定的故障形态:备战入口的全量观察(heavy)在奇遇介绍浮层帧上执行。浮层压在
备战界面上时,备战两识别标志(购买经验 / 出战)仍同帧命中,外循环照常派发
``CwScreenPrep``;浮层没被任何处理链接住时就原样留在画面上,后排布局的 CV
槽位签名通道被浮层自身内容点亮(左侧图形块 / 右侧说明文落进后排 y 带),
布局误判 9 格,下游占用计数、装备识别、身份行连环污染。

修法 = 浮层注册表(``kernel/cw_overlay_registry.py``)一条 display/closable
声明:清场派生集 ``cw_screen_prep.ENTRY_OVERLAY_CLOSE`` 自动收入该屏,环入口
在 heavy 观察之前点「按钮-空白继续」把浮层关掉。

断言面(行为级):
- 浮层帧上唯一点击 = 清场点击,落在「按钮-空白继续」;
- heavy 观察恰一次,且发生在浮层关闭后的干净备战帧上(剧本帧序已推进);
- 清场后前置段按生产现行序跑完(清场 → 收店探针 → heavy → 补采委派)。

帧 = sr-od-test/screens 存档(奇遇介绍浮层帧 + 干净备战帧,零新建档);
heavy 识别本体打桩(识别链有专测,本剧本断言面 = 编排序与帧归属);
harness = fixture_controller(点「按钮-空白继续」即推进到干净备战帧)。
"""

from __future__ import annotations

import types

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
from sr_od.application.currency_war.kernel.cw_vocab import CwActionObsParam
from sr_od.application.currency_war.obs.cw_observation import (
    reset_phase_round_cache,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
    CwScreenPrep,
)

#: 奇遇介绍浮层帧存档(备战界面 + 本局奇遇介绍浮层;画面身份锚「读区-奇遇标题」)。
_INTRO_FRAME: tuple[str, str] = ('货币战争-备战-奇遇介绍', '介绍浮层')
#: 浮层关闭后的干净备战帧存档(heavy 观察应在其上执行)。
_CLEAN_FRAME: tuple[str, str] = ('货币战争-备战', 'deployed_p1r9')

#: 前置段现行序(断言锚 = 生产 observe node 现行编排:清场 → 收店探针 →
#: heavy 观察 → 补采委派)。
_FRONT_SEGMENT_ORDER: list[str] = ['清场', '收店探针', 'heavy', '补采委派']

#: 夹具种子用的渠道签名(测试侧观察写只求通道合法,actor 沿备战写端)。
_TEST_OBS_SIG: ChannelSig = ChannelSig(family='obs', actor='CwScreenPrep',
                                       screen='货币战争-备战', mode='read')


class _PrepController(FixtureController):
    """假游戏控制器补 ``mouse_move``(备战观察链会触达;基类缺该方法 →
    AttributeError 被框架吞成异常重试的伪失败形态)。"""

    def mouse_move(self, pos) -> None:
        pass


class _StrategyStub:
    """策略器替身:恒发 ``CwActionObsParam(scope='outer_loop')``(返回主循环
    重新观察——决策环内零动作执行面,常规路径以此干净交回)。"""

    def decide_prep_screen(self) -> CwActionObsParam:
        return CwActionObsParam(scope='outer_loop')


@pytest.fixture
def prep_env(test_context: SrTestContext,
             monkeypatch: pytest.MonkeyPatch,
             ) -> tuple[SrTestContext, _PrepController]:
    """假控制器换装(monkeypatch 自动还原)。"""
    ctrl = _PrepController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    return test_context, ctrl


def _attach_match(test_context: SrTestContext,
                  monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """挂流程态 Match 桩:新局常规路径前置(非接管、未锁定、策略器替身、
    策略状态计数器在场)。session 每测新建 = GameState 弱引用表新支,
    无跨测串染。"""
    match = types.SimpleNamespace(
        session=types.SimpleNamespace(),
        strategy=_StrategyStub(),
        opened_via='new_game',
        probed=False,
        locked_resume=False,
        locked_round=0,
        locked_sync_done=True,
        gs=None)
    match.session.strategy_state = types.SimpleNamespace(
        cw4_counters={}, cw4_segment_serial=0, cw4_frame_action_record=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


def _seed_regular_gs(gs: GameState) -> None:
    """常规路径前置条件:补采委派门两支按否(位面 boss 真值在场 + 词缀非
    随机态)→ 前置段直通,不委派 CwEntryPlaneIntel(委派编排 = 入口链专属
    测试域,不在本剧本断言面)。"""
    gs.observe(gs.plane_bosses, ['boss-1', 'boss-2', 'boss-3'],
               evidence='test_seed', sig=_TEST_OBS_SIG)
    gs.observe(gs.enemy_affixes, [], evidence='test_seed', sig=_TEST_OBS_SIG)


def _stub_heavy_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    """heavy 识别核打桩(observe_full 回执 = {} → 各识别域按失读分支走);
    识别 MISS 采集口径一并 no-op(识别链有专测,本剧本只断言编排序与帧归属)。"""
    from sr_od.application.currency_war.kernel import cw_observe
    from sr_od.application.currency_war.obs import cw_observe_full
    monkeypatch.setattr(cw_observe_full, 'observe_full',
                        lambda *a, **k: {})
    monkeypatch.setattr(cw_observe, 'cw_shot', lambda image, name: None)
    monkeypatch.setattr(cw_observe, 'cw_shot_unique',
                        lambda image, label: None)


def test_adventure_intro_overlay_closed_before_heavy_observe(
        prep_env: tuple[SrTestContext, _PrepController],
        monkeypatch: pytest.MonkeyPatch) -> None:
    """奇遇介绍浮层帧进备战入口:清场段点「按钮-空白继续」关浮层 → heavy
    观察在关闭后的干净备战帧上执行(浮层帧零 heavy 观察)。"""
    test_context, ctrl = prep_env
    for screen_name, state in (_INTRO_FRAME, _CLEAN_FRAME):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')
    reset_phase_round_cache()   # 清位面轮次模块缓存(单调守卫跨测防串染)
    # 剧本:浮层帧(点「按钮-空白继续」推进)→ 干净备战帧。
    ctrl.set_phases([
        {'frame': _INTRO_FRAME,
         'exit': ('on_click_in', '货币战争-备战-奇遇介绍', '按钮-空白继续')},
        {'frame': _CLEAN_FRAME},
    ])
    match = _attach_match(test_context, monkeypatch)
    _seed_regular_gs(game_state_of(match.session))
    _stub_heavy_recognition(monkeypatch)

    # 前置段序 spy(真方法透传,只记调用序与 heavy 观察时的剧本帧序)。
    real_clear = CwScreenPrep._clear_entry_overlays
    real_collapse = CwScreenPrep._try_collapse_open_shop
    real_observe = CwScreenPrep._observe
    real_delegate = CwScreenPrep._delegate_plane_intel_if_needed
    order: list[str] = []
    heavy_on_phase: list[int] = []

    def _clear(self) -> None:
        order.append('清场')
        return real_clear(self)

    def _collapse(self) -> bool:
        order.append('收店探针')
        return real_collapse(self)

    def _observe(self, heavy: bool, screen: MatLike | None = None):
        if heavy:
            order.append('heavy')
            heavy_on_phase.append(ctrl.phase_idx)
        return real_observe(self, heavy, screen)

    def _delegate(self, session) -> object | None:
        order.append('补采委派')
        return real_delegate(self, session)

    monkeypatch.setattr(CwScreenPrep, '_clear_entry_overlays', _clear)
    monkeypatch.setattr(CwScreenPrep, '_try_collapse_open_shop', _collapse)
    monkeypatch.setattr(CwScreenPrep, '_observe', _observe)
    monkeypatch.setattr(CwScreenPrep, '_delegate_plane_intel_if_needed', _delegate)

    op = CwScreenPrep(test_context)
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    # —— 常规访问 success(清场后走常规路径,策略器发 Obs:outer_loop 交回)
    assert result.success, f'浮层帧清场后应走常规路径 success,实际 {result.status!r}'
    # —— 读数前关闭:浮层帧上唯一点击 = 清场点击,落在「按钮-空白继续」
    assert len(ctrl.recorded_clicks) == 1, \
        f'浮层帧上应恰有一次清场点击,实际 {ctrl.recorded_clicks}'
    assert ctrl.click_hit_area('货币战争-备战-奇遇介绍', '按钮-空白继续'), \
        f'清场点击应落在按钮-空白继续,实际 {ctrl.recorded_clicks}'
    # —— heavy 观察恰一次,且在浮层关闭后的干净备战帧上(剧本帧序 1)
    assert heavy_on_phase == [1], \
        (f'heavy 观察应恰一次且落在浮层关闭后的帧(剧本帧序 1),'
         f'实际 {heavy_on_phase!r}')
    # —— 清场后前置段按现行序跑完
    assert order == _FRONT_SEGMENT_ORDER, \
        f'清场后前置段应按现行序跑完,实际 {order!r}'
    assert ctrl.phase_idx == 1, \
        f'剧本应停在干净备战帧,实际帧序 {ctrl.phase_idx}'
