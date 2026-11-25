"""BackToNormalWorldPlus.check_screen 真帧输入锁:归档截图 + 真识别照跑,不桩画面识别。

与同目录 test_check_screen.py(mock 分发锁)按输入形态分文件;本文件红了先查建档 / 识别漂移
(识别标志失配、模板漂移、误吸别分支),mock 文件红先查路由逻辑。
"""

from __future__ import annotations

import numpy as np
import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)
from test.sr_od.operations.back_to_normal_world_plus.harness import _WatchedBackToNormal

import sr_od.operations.back_to_normal_world_plus as btnw_module
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_round_result import OperationRoundResult
from sr_od.operations.back_to_normal_world_plus import BackToNormalWorldPlus


def _run_real_frame_check_screen(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
    screen_name: str,
    state: str,
    in_match_screen_name: str | None = None,
    exit_match_cls: type | None = None,
    use_real_cw_match: bool = False,
) -> tuple[OperationRoundResult, list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]], list[tuple[Point | None, bool]]]:
    """真帧驱动单轮 check_screen,返回 (结果, find记录, find+click记录, 裸click记录, controller点击记录)。

    - ``op.last_screenshot`` 直接注入归档真帧(不经截图链路);
    - 三类 round_by_* 均为**包装真实方法**(识别照跑,只加记录);
    - controller.click 同样包装记录 ``(pos, pc_alt)``(锁光标恢复态加固后,
      大厅/兜底分支直点 controller,须在此验证 pc_alt 语义);
    - 模拟宇宙状态 / 列车补给 / 对话守卫恒无(与本测试无关,防噪音);
    - CW 对局中画面判定默认恒 None;``in_match_screen_name`` 非 None 时改为
      恒返回该屏名(真帧 + 判定桩:对局画面匹配层已由 cw 侧测试单独锁定,
      本仓真帧测试只锁 check_screen 的分支路由);
    - ``use_real_cw_match=True`` 时判定桩整体不装,走真实 ``cw_screen_state``
      判定(真帧 + 真画面匹配的端到端路由锁,如结算屏委托);
    - ``exit_match_cls`` 非 None 时替换为该假类(不触真实退出对局 op)。
    """
    img = test_context.load_screen(screen_name, state)
    finds: list[tuple[str, str]] = []
    find_clicks: list[tuple[str, str]] = []
    bare_clicks: list[tuple[str, str]] = []
    controller_clicks: list[tuple[Point | None, bool]] = []

    real_find = BackToNormalWorldPlus.round_by_find_area
    real_find_click = BackToNormalWorldPlus.round_by_find_and_click_area
    real_click = BackToNormalWorldPlus.round_by_click_area

    def _spy_find(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            finds.append((s_name, a_name))
        return r

    def _spy_find_click(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find_click(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            find_clicks.append((s_name, a_name))
        return r

    def _spy_click(self, s_name: str, a_name: str, *a, **k):
        r = real_click(self, s_name, a_name, *a, **k)
        bare_clicks.append((s_name, a_name))
        return r

    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _spy_find)
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'round_by_find_and_click_area', _spy_find_click,
    )
    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _spy_click)
    monkeypatch.setattr(
        btnw_module.sim_uni_screen_state,
        'get_sim_uni_screen_state',
        lambda *args, **kw: None,
    )
    monkeypatch.setattr(
        btnw_module.common_screen_state,
        'is_express_supply',
        lambda *args, **kw: False,
    )
    # CW 对局中画面判定恒 None(真实实现走真 OCR 画面匹配,与被测分支无关;
    # None=判定失败退既有行为)。真帧场景需命中时由调用方显式覆盖;
    # use_real_cw_match=True 时整段不桩,判定单一源照真跑(端到端路由锁)。
    if not use_real_cw_match:
        monkeypatch.setattr(
            btnw_module.cw_screen_state,
            'get_in_match_screen_name',
            lambda *args, **kw: None,
        )
        # CW 挂起入口两屏屏级点名恒 None(真帧测试锁各自分支路由,挂起
        # 分支的画面匹配层由 test_id_mark 与 cw 侧测试单独锁定)。
        monkeypatch.setattr(
            btnw_module,
            'get_match_screen_name',
            lambda *args, **kw: None,
        )
        if in_match_screen_name is not None:
            monkeypatch.setattr(
                btnw_module.cw_screen_state,
                'get_in_match_screen_name',
                lambda *args, **kw: in_match_screen_name,
            )
    if exit_match_cls is not None:
        monkeypatch.setattr(btnw_module, 'CwEntryExit', exit_match_cls)
    monkeypatch.setattr(BackToNormalWorldPlus, 'check_npc_dialog', lambda self, s: None)

    op = _WatchedBackToNormal(test_context)
    op.last_screenshot = img  # 真帧注入:check_screen 每轮读它做识别
    monkeypatch.setattr(op, 'screenshot', lambda: img)

    real_ctrl_click = op.ctx.controller.click

    def _spy_ctrl_click(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
        r = real_ctrl_click(pos, press_time=press_time, pc_alt=pc_alt,
                            gamepad_key=gamepad_key)
        controller_clicks.append((pos, bool(pc_alt)))
        return r

    monkeypatch.setattr(op.ctx.controller, 'click', _spy_ctrl_click, raising=False)

    enter_running_state(test_context)
    try:
        result = op.check_screen()
    finally:
        reset_running_state(test_context, op)
    return result, finds, find_clicks, bare_clicks, controller_clicks


class TestCwLobbyResidualBranch:
    """CW 大厅残留态分支真帧输入锁:上局结束「回大厅」的死按钮残留态。

    背景(2026-08-27 run49 首跑 147s 失败根因,编排者 live 实证):上局结束
    「回大厅」后的大厅 UI 层是残留态——开始按钮不响应任何点击(app 重试循环
    与手动双击均无效),右上角「按钮-关闭」才是真退出(关 X 露出世界场景后
    世界入口接管一切正常)。该残留态与开局前大厅共用同一 screen_info 档
    (货币战争-大厅,玩法名 id_mark 识别标志「标识-玩法名」+ 按钮-关闭
    template),由既有
    大厅分支接管:标识命中 → find+click「按钮-关闭」→ round_retry
    逐帧重识别露世界 → 「角色图标」分支 SUCCESS。

    真帧锁:fixture = run49 真实失败帧(死按钮大厅态,含玩法名标题+开始钮+
    右上关闭钮,测试仓归档 ``大厅-残留态-run49.webp``)。不 mock 画面识别,
    锁「真帧 → 分支路由 + 点击 area」全链:识别标志失配 / 模板漂移 / 误吸
    别分支(尤其对话守卫与兜底)会在此红。
    """

    SCREEN = '货币战争-大厅'
    STATE = '大厅-残留态-run49'

    def test_residual_lobby_closes(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """run49 残留态真帧:命中大厅分支,直点「按钮-关闭」area 中心(pc_alt=True)。"""
        result, finds, find_clicks, bare_clicks, ctrl_clicks = (
            _run_real_frame_check_screen(
                test_context, monkeypatch, self.SCREEN, self.STATE,
            )
        )

        # 分支路由:round_retry 等下一轮逐帧重识别露世界(非 success / 兜底)
        assert not result.is_success, f'残留态应 round_retry,status={result.status}'
        assert result.status == self.SCREEN
        # 识别事实(真 OCR):玩法名 id_mark 识别标志命中(分支入口判据)。
        assert (self.SCREEN, '标识-玩法名') in finds, f'识别命中:{finds}'
        # 动作(锁光标恢复态加固锁,2026-09-02 事故根修):命中后直点
        # 「按钮-关闭」area 中心,且必须带 pc_alt=True(锁光标下不带 Alt 的
        # 点击全部落空);不再走 find_and_click,也不落兜底。
        close_area = test_context.screen_loader.get_area(self.SCREEN, '按钮-关闭')
        assert close_area is not None, '货币战争-大厅/按钮-关闭 area 未建档'
        assert find_clicks == [], f'大厅分支不应再走 find_and_click:{find_clicks}'
        assert bare_clicks == [], f'不应有兜底/翻页类裸点击:{bare_clicks}'
        # Point 无 __eq__,按坐标比较
        assert len(ctrl_clicks) == 1, f'关闭点击应恰一次:{ctrl_clicks}'
        pos, alt = ctrl_clicks[0]
        assert (int(pos.x), int(pos.y)) == (int(close_area.center.x), int(close_area.center.y)) and alt, (
            f'关闭点击应为 area 中心 + pc_alt=True:{ctrl_clicks}'
        )


class TestBattleFailScreenBranch:
    """大世界-战斗失败分支真帧输入锁:app 异常退出遗留的战败结算屏。

    背景(2026-08-30 实证,开拓力 FAIL 遗留现场):战败结算屏无右上角返回按钮,
    唯一交互是「点击空白区域继续」;起手兜底只会反复点右上角死循环至 FAIL,
    卡死下一个应用。分支 = id_mark「标题-战斗失败」正面识别 → find+click
    「点击空白区域继续」→ round_retry 逐帧重识别(点空白落到各副本战前画面,
    由既有分支/兜底继续)。

    真帧锁:fixture = 饰品提取战败真帧(标题-战斗失败 + 点击空白区域继续,
    conf 0.995+,见 docs/game/screens/大世界-战斗失败.md)。不 mock 画面识别,
    真 OCR/模板识别照跑——识别漂移时测试红,直接暴露建档漂移。
    """

    SCREEN = '大世界-战斗失败'
    STATE = '战斗失败'

    def test_battle_fail_clicks_blank(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """战败屏真帧:命中战败分支,find+click「点击空白区域继续」,round_retry。"""
        result, finds, find_clicks, bare_clicks, _ctrl = _run_real_frame_check_screen(
            test_context, monkeypatch, self.SCREEN, self.STATE,
        )

        # 分支路由:round_retry 等下一轮逐帧重识别(点空白落到战前画面)
        assert not result.is_success, f'战败屏应 round_retry,status={result.status}'
        assert result.status == self.SCREEN
        # 识别事实(真 OCR):标题 id_mark 识别标志命中(分支入口判据)
        assert (self.SCREEN, '标题-战斗失败') in finds, f'识别命中:{finds}'
        # 动作:只 find+click 点空白继续;不落兜底裸点击
        assert find_clicks == [(self.SCREEN, '点击空白区域继续')], (
            f'点击漂移:{find_clicks}'
        )
        assert bare_clicks == [], f'不应有兜底裸点击:{bare_clicks}'


# --------------------------------------------------------------------------- #
# 货币战争图鉴族返回链
# --------------------------------------------------------------------------- #

#: 图鉴族返回链参数表:起点屏 → (归档帧子态, 自起点逐级点「按钮-返回」经过的屏序)。
#: 屏序 = 画面档各图鉴档「按钮-返回」area 的 goto_list 返回边(子页 → 数据银行),
#: 数据银行 → 大厅由「货币战争-大厅」分支点关闭 X 接管;去向依据 = 玩家 skill
#: 画面卡「按钮-返回」行(skills/sr-od-currency-war/references/screens/
#: 货币战争-数据银行.md 及同族各卡)。
CODEX_CHAINS: dict[str, tuple[str, list[str]]] = {
    '货币战争-竞争对手图鉴详情': (
        '技能-火线动力机甲',
        ['货币战争-竞争对手图鉴详情', '货币战争-竞争对手图鉴列表', '货币战争-数据银行'],
    ),
    '货币战争-竞争对手图鉴列表': (
        '列表', ['货币战争-竞争对手图鉴列表', '货币战争-数据银行'],
    ),
    '货币战争-装备图鉴': ('default', ['货币战争-装备图鉴', '货币战争-数据银行']),
    '货币战争-主角光环图鉴': ('蚁群效应选中', ['货币战争-主角光环图鉴', '货币战争-数据银行']),
    '货币战争-数据银行': ('主页', ['货币战争-数据银行']),
}
_CODEX_START_IDS: list[str] = ['rival-detail', 'rival-list', 'equip', 'aura', 'data-bank']


def _expected_hops(chain: list[str]) -> list[tuple[str, str, str]]:
    """返回链的跳转三元组 (出发屏, 点的 area, 到达屏);末跳落大厅。"""
    return [
        (src, '按钮-返回', dst)
        for src, dst in zip(chain, chain[1:] + ['货币战争-大厅'], strict=True)
    ]


def _codex_chain_harness(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_WatchedBackToNormal, dict[str, list], dict[str, object]]:
    """真帧链驱动装置:识别照真跑,只加记录;返回 (op, 记录表, 当前帧槽)。

    - ``btnw_module.get_match_screen_name`` **不桩**——图鉴族分支靠它按屏名清单
      精确识别当前页,是本链的被测判定;
    - 对局中判定 / 模拟宇宙状态 / 列车补给恒无(链不经过这些画面,真匹配只会
      让每帧多跑全量无关 id_mark);
    - 对话守卫被触达即断言失败:链上每帧都有专属分支(图鉴页 → 图鉴族分支、
      大厅 → 大厅分支、大世界 → 角色图标分支),落守卫 = 路由漂移;
    - 记录表键:finds(识别命中)/ find_clicks / bare_clicks / ctrl_clicks(pos, pc_alt)。
    """
    rec: dict[str, list] = {'finds': [], 'find_clicks': [], 'bare_clicks': [], 'ctrl_clicks': []}
    real_find = BackToNormalWorldPlus.round_by_find_area
    real_find_click = BackToNormalWorldPlus.round_by_find_and_click_area
    real_click = BackToNormalWorldPlus.round_by_click_area

    def _spy_find(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            rec['finds'].append((s_name, a_name))
        return r

    def _spy_find_click(self, screen, s_name: str, a_name: str, *a, **k):
        r = real_find_click(self, screen, s_name, a_name, *a, **k)
        if r.is_success:
            rec['find_clicks'].append((s_name, a_name))
        return r

    def _spy_click(self, s_name: str, a_name: str, *a, **k):
        r = real_click(self, s_name, a_name, *a, **k)
        rec['bare_clicks'].append((s_name, a_name))
        return r

    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _spy_find)
    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_and_click_area', _spy_find_click)
    monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_click_area', _spy_click)
    monkeypatch.setattr(
        btnw_module.sim_uni_screen_state, 'get_sim_uni_screen_state',
        lambda *args, **kw: None,
    )
    monkeypatch.setattr(
        btnw_module.common_screen_state, 'is_express_supply', lambda *args, **kw: False,
    )
    monkeypatch.setattr(
        btnw_module.cw_screen_state, 'get_in_match_screen_name', lambda *args, **kw: None,
    )
    monkeypatch.setattr(
        BackToNormalWorldPlus, 'check_npc_dialog',
        lambda self, screen: (_ for _ in ()).throw(
            AssertionError('返回链各帧都有专属分支,不应进入对话态守卫')),
    )

    op = _WatchedBackToNormal(test_context)
    slot: dict[str, object] = {'img': None}
    monkeypatch.setattr(op, 'screenshot', lambda: slot['img'])

    real_ctrl_click = op.ctx.controller.click

    def _spy_ctrl_click(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
        r = real_ctrl_click(pos, press_time=press_time, pc_alt=pc_alt,
                            gamepad_key=gamepad_key)
        rec['ctrl_clicks'].append((pos, bool(pc_alt)))
        return r

    monkeypatch.setattr(op.ctx.controller, 'click', _spy_ctrl_click, raising=False)
    return op, rec, slot


def _drive_round(
    op: _WatchedBackToNormal,
    rec: dict[str, list],
    slot: dict[str, object],
    test_context: SrTestContext,
    screen: str,
    state: str,
) -> tuple[OperationRoundResult, dict[str, int]]:
    """注入一张归档真帧,直调一轮 check_screen;返回 (结果, 本轮前各记录长度)。"""
    slot['img'] = test_context.load_screen(screen, state)
    op.last_screenshot = slot['img']
    before = {k: len(v) for k, v in rec.items()}
    result = op.check_screen()
    return result, before


def _assert_single_center_click(
    rec: dict[str, list],
    before: dict[str, int],
    test_context: SrTestContext,
    screen: str,
    area_name: str,
) -> None:
    """本轮恰一次直点且落点 = 该 area 中心 + pc_alt=True,零 find+click / 裸点击。"""
    area = test_context.screen_loader.get_area(screen, area_name)
    assert area is not None, f'{screen}/{area_name} area 未建档'
    assert rec['find_clicks'][before['find_clicks']:] == [], f'不应走 find_and_click:{rec["find_clicks"]}'
    assert rec['bare_clicks'][before['bare_clicks']:] == [], f'不应有裸点击:{rec["bare_clicks"]}'
    clicks = rec['ctrl_clicks'][before['ctrl_clicks']:]
    assert len(clicks) == 1, f'应恰一次直点:{clicks}'
    pos, alt = clicks[0]
    assert (int(pos.x), int(pos.y)) == (int(area.center.x), int(area.center.y)) and alt, (
        f'直点应为 {screen}/{area_name} 中心 + pc_alt=True:{clicks}'
    )


class TestCwCodexBranch:
    """货币战争图鉴族 → 点右上返回箭头逐级退回分支锁。

    期望表现(cw_screen_state.CODEX_STATE_SCREENS 注释 + 各图鉴档「按钮-返回」
    goto 边):停在任一图鉴页时,check_screen 按屏名清单认出该页,验返回箭头模板
    可见后直点其 area 中心(pc_alt=True)并 round_retry;逐帧重识别下每轮退一级
    (子页 → 数据银行 → 大厅 → 大世界),终点「角色图标」分支 SUCCESS。
    无此分支时图鉴页落兜底(点「菜单-右上角返回」),返回链未建模。
    """

    @pytest.mark.parametrize('start', list(CODEX_CHAINS), ids=_CODEX_START_IDS)
    def test_route_to_lobby(self, start: str, test_context: SrTestContext) -> None:
        """画面路由图:任一图鉴页经「按钮-返回」逐级可达大厅,跳转序列 = 返回链。"""
        route = test_context.screen_loader.get_screen_route(start, '货币战争-大厅')
        assert route is not None and route.can_go, f'{start} 无到达大厅的路由(返回边缺)'
        hops = [(n.from_screen, n.from_area, n.to_screen) for n in route.node_list]
        assert hops == _expected_hops(CODEX_CHAINS[start][1]), f'{start} 路由跳漂移:{hops}'

    @pytest.mark.parametrize('start', list(CODEX_CHAINS), ids=_CODEX_START_IDS)
    def test_back_chain_reaches_world(
        self,
        start: str,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """真帧逐级:每页认出该屏 + 返回箭头模板命中 + 直点其中心 → 大厅 → 大世界。"""
        _, chain = CODEX_CHAINS[start]
        op, rec, slot = _codex_chain_harness(test_context, monkeypatch)

        enter_running_state(test_context)
        try:
            with fast_sleep(op):
                for screen in chain:
                    result, before = _drive_round(
                        op, rec, slot, test_context, screen, CODEX_CHAINS[screen][0],
                    )
                    assert not result.is_success and result.status == screen, (
                        f'{screen} 帧应命中图鉴族分支并 round_retry,status={result.status}'
                    )
                    # 识别事实(真模板):返回箭头可见才点;前序分支零命中。
                    assert rec['finds'][before['finds']:] == [(screen, '按钮-返回')], (
                        f'{screen} 帧识别命中应仅返回箭头:{rec["finds"]}'
                    )
                    _assert_single_center_click(rec, before, test_context, screen, '按钮-返回')

                result, before = _drive_round(op, rec, slot, test_context, '货币战争-大厅', 'lobby')
                assert not result.is_success and result.status == '货币战争-大厅', (
                    f'数据银行返回后应由大厅分支接管,status={result.status}'
                )
                _assert_single_center_click(rec, before, test_context, '货币战争-大厅', '按钮-关闭')

                result, before = _drive_round(op, rec, slot, test_context, '大世界', '普通')
                assert result.is_success, f'链终点应落大世界 SUCCESS,status={result.status}'
                assert len(rec['ctrl_clicks']) == before['ctrl_clicks'], '大世界帧不应再点击'
        finally:
            reset_running_state(test_context, op)

    def test_back_arrow_hidden_no_blind_click(
        self,
        test_context: SrTestContext,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """清单命中数据银行但返回箭头模板未命中(被浮层盖住):不接管、不盲点,落兜底。"""
        ctrl_clicks: list[tuple[Point | None, bool]] = []

        def _fake_find_area(self, screen, s_name, a_name, *a, **kw):
            return self.round_wait(status=f'未找到 {a_name}')

        monkeypatch.setattr(BackToNormalWorldPlus, 'round_by_find_area', _fake_find_area)
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_find_and_click_area', _fake_find_area,
        )
        monkeypatch.setattr(
            BackToNormalWorldPlus, 'round_by_click_area', _fake_find_area,
        )
        monkeypatch.setattr(
            btnw_module.sim_uni_screen_state, 'get_sim_uni_screen_state',
            lambda *args, **kw: None,
        )
        monkeypatch.setattr(
            btnw_module.common_screen_state, 'is_express_supply', lambda *args, **kw: False,
        )
        monkeypatch.setattr(
            btnw_module.cw_screen_state, 'get_in_match_screen_name', lambda *args, **kw: None,
        )
        # 屏名清单匹配桩:只对含数据银行的清单命中(图鉴族分支送审的清单),其余 None。
        monkeypatch.setattr(
            btnw_module, 'get_match_screen_name',
            lambda ctx, screen, screen_name_list=None: (
                '货币战争-数据银行'
                if screen_name_list and '货币战争-数据银行' in screen_name_list
                else None
            ),
        )
        monkeypatch.setattr(BackToNormalWorldPlus, 'check_npc_dialog', lambda self, s: None)

        op = _WatchedBackToNormal(test_context)
        op.last_screenshot = np.zeros((1080, 1920, 3), dtype=np.uint8)

        def _record_click(pos=None, press_time=0, pc_alt=False, gamepad_key=None):
            ctrl_clicks.append((pos, bool(pc_alt)))
            return True

        monkeypatch.setattr(op.ctx.controller, 'click', _record_click, raising=False)

        enter_running_state(test_context)
        try:
            with fast_sleep(op):
                result = op.check_screen()
        finally:
            reset_running_state(test_context, op)

        assert not result.is_success and result.status == '右上角返回', (
            f'箭头不可见应落兜底,status={result.status}'
        )
        fallback = test_context.screen_loader.get_area('菜单', '右上角返回')
        back = test_context.screen_loader.get_area('货币战争-数据银行', '按钮-返回')
        assert fallback is not None and back is not None
        assert len(ctrl_clicks) == 1, f'应只有兜底一次直点:{ctrl_clicks}'
        pos, alt = ctrl_clicks[0]
        assert (int(pos.x), int(pos.y)) == (int(fallback.center.x), int(fallback.center.y)), (
            f'直点应是兜底位,不是返回箭头位 {back.center}:{ctrl_clicks}'
        )
        assert alt is True
