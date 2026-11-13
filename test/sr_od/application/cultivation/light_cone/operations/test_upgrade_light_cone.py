"""UpgradeLightConeOp(光锥晋阶升级·新版快速刷取)节点流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_trace.py
模块 docstring——面板态帧测试仓缺存档、识别类输入禁止合成),monkeypatch
识别层构造 round 结果,驱动完整 ``execute()`` 节点图。

同构精简说明:与 trace/character 同构的部分(flat loop 分类/缺料判停/
入口判满/升级按钮执行)已分别在 test_upgrade_trace.py /
test_upgrade_character.py 锁定,本文件只测 light cone 特有分支——出处
src/sr_od/application/cultivation/light_cone/operations/upgrade_light_cone.py
模块 docstring 与各节点实现:
- 「材料补全」确认弹窗:fill_generic 授权点「确认」继续;未授权防御性点
  「取消」判停——通用材料是稀缺消耗品,授权边界 = 确认/取消二选一;
- farm_dungeon 券路线全链:资源窗口→副本→确认框(次数现读+点「+」补偿)
  →结果框→按浮层栈回退到等级提升,重入升级循环;
- 手动路线返回兼容:进入战斗卸载浮层栈,退出关卡后的副本「关闭X」直接回
  大世界——op 经 BACK_TO_WORLD 分支重走入口链(角色图标→重选角色→切TAB
  →强化),角色名取入口核对时读名区 OCR;
- 参数校验:farm_times_per_round 仅正数或 -1(拉满),farm_rounds_max >= 1。
"""

from __future__ import annotations

import pytest

import sr_od.application.cultivation.light_cone.operations.upgrade_light_cone as lc_module
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from sr_od.application.cultivation.light_cone.operations.upgrade_light_cone import (
    UpgradeLightConeOp,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

_LC_TAB: str = '角色-光锥'
_LC_ASC: str = '光锥-等级提升'
_CHALLENGE: str = '挑战副本'
_WORLD: str = '大世界-普通'
_DETAIL: str = '角色-详情'
_BATTLE: str = '战斗画面'

# 测试内建档 rect 快照(来源 assets/game_data/screen_info 对应 yml 与实机
# analyze 命中;screen_info 漂移时本表测试红 → 同步)。测试环境的
# screen_loader 不加载画面数据(get_area 恒 None),点击落区断言只能用本表。
_TEST_RECTS: dict[tuple[str, str], tuple[int, int, int, int]] = {
    (_LC_TAB, '按钮-强化'): (1740, 962, 1910, 1022),
    (_LC_ASC, '按钮-快速刷取'): (1285, 965, 1450, 1015),
    (_LC_ASC, '按钮-通用材料补全'): (1527, 968, 1880, 1012),
    (_LC_ASC, '按钮-快速升级'): (1527, 968, 1880, 1012),
    (_LC_ASC, '按钮-确认材料补全'): (990, 680, 1340, 730),
    (_LC_ASC, '按钮-取消材料补全'): (570, 680, 930, 730),
    (_LC_ASC, '按钮-关闭X'): (1826, 36, 1892, 92),
    (_CHALLENGE, '挑战按钮'): (1370, 958, 1858, 1014),
    ('培养资源窗口', '标题-培养资源窗口'): (490, 285, 740, 330),
    ('培养资源窗口', '按钮-进入副本'): (1290, 390, 1460, 440),
    ('培养资源窗口', '按钮-关闭资源窗口'): (1435, 285, 1480, 335),
    (_CHALLENGE, '按钮-快速刷取副本'): (1000, 955, 1155, 1010),
    (_CHALLENGE, '按钮-确认快速刷取'): (990, 740, 1348, 788),
    (_CHALLENGE, '按钮-关闭副本'): (1838, 38, 1888, 95),
    (_CHALLENGE, '按钮-开始编队挑战'): (1560, 955, 1740, 1005),
    (_CHALLENGE, '按钮-关闭刷取结果'): (570, 788, 930, 842),
    (_CHALLENGE, '按钮-刷取次数加'): (1318, 570, 1374, 608),
    (_BATTLE, '按钮-退出关卡'): (663, 957, 765, 989),
    (_WORLD, '右上图标-角色详情'): (1814, 14, 1879, 79),
}


def _rect_center(s_name: str, a_name: str) -> Point:
    """快照 rect 中心(点击桩用;表外区域 = 测试写错,直接抛)。"""
    rect = _TEST_RECTS[(s_name, a_name)]
    return Point((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)


def _in_rect(x: int, y: int, s_name: str, a_name: str) -> bool:
    rect = _TEST_RECTS[(s_name, a_name)]
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]

# 升级循环每轮分类的第一个识别查询 = 材料补全弹窗锚(优先级①在判停检查
# 之前,判停收尾轮同样先查它),桩以它计轮推进剧本。
_ROUND_START: tuple[str, str] = (_LC_ASC, '标题-材料补全弹窗')

_DEAD_FRAME: set[tuple[str, str]] = set()


class _WatchedUpgradeLightCone(WatchdogOperationMixin, UpgradeLightConeOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: SrTestContext, fill_generic: bool = False,
                 farm_dungeon: bool = False, use_fast_ticket: bool = True,
                 farm_times_per_round: int = 1, farm_rounds_max: int = 10) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。"""
        UpgradeLightConeOp.__init__(self, ctx, fill_generic=fill_generic,
                                    farm_dungeon=farm_dungeon,
                                    use_fast_ticket=use_fast_ticket,
                                    farm_times_per_round=farm_times_per_round,
                                    farm_rounds_max=farm_rounds_max)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


class _FakeSubOp:
    """子 op 替身(记录构造参数,execute 恒成功)——重走入口链的重选/切页。"""

    executed: list[dict] = []

    def __init__(self, ctx: SrTestContext, **kwargs) -> None:
        self.kwargs = kwargs

    def execute(self) -> OperationResult:
        _FakeSubOp.executed.append(dict(self.kwargs))
        return OperationResult(success=True, status='FAKE_OK')


def _install_script(
    monkeypatch: pytest.MonkeyPatch,
    ctx: SrTestContext,
    scenes: list[set[tuple[str, str]]],
    level: int,
) -> dict:
    """桩识别层并装记录器。

    state 键:round(剧本轮,弹窗锚查询推进)/farm_times_read(确认框次数
    现读值)/screen_now(可变画面名,check_and_update 返回)/find_clicks。
    """
    state: dict = {'round': 0, 'level_reads': 0, 'find_events': [],
                   'find_clicks': [], 'farm_times_read': 1,
                   'screen_now': _LC_TAB, 'char_name_reads': []}

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        if (s_name, a_name) == _ROUND_START:
            state['round'] += 1
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is None:
            raise AssertionError(f'剧本耗尽:第 {state["round"]} 轮查询 {a_name}')
        if (s_name, a_name) in scene:
            state['events'] = state.get('events', [])
            state['events'].append((state['round'], a_name, 'HIT'))
            # 手动战斗场景命中 = 下一次编队钮点击是真实的「进入战斗」推进点
            if (s_name, a_name) == (_CHALLENGE, '按钮-开始编队挑战'):
                state['in_manual_fight'] = True
            return self.round_success(status=a_name)
        state['events'] = state.get('events', [])
        state['events'].append((state['round'], a_name, 'MISS'))
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
        state['find_clicks'].append((s_name, a_name))
        # 走 controller.click:让点击记录器与画面状态推进(退出关卡→大世界等)
        # 与真实链路一致
        self.ctx.controller.click(_rect_center(s_name, a_name))
        return self.round_success(status=a_name)

    def _fake_check_screen(self, screen=None, screen_name_list=None,
                           crop_first=False):
        now = state['screen_now']
        if screen_name_list is not None and now not in screen_name_list:
            return screen_name_list[0]
        return now

    def _fake_level(self, screen_name: str | None = None) -> int | None:
        state['level_reads'] += 1
        return level

    def _fake_farm_times(self) -> int | None:
        return state['farm_times_read']

    def _fake_char_name(self) -> str | None:
        state['char_name_reads'].append(1)
        return '测试角色'

    monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeLightConeOp, 'check_and_update_current_screen',
                        _fake_check_screen)
    monkeypatch.setattr(UpgradeLightConeOp, '_read_lc_level', _fake_level)
    monkeypatch.setattr(UpgradeLightConeOp, '_read_farm_times', _fake_farm_times)
    monkeypatch.setattr(UpgradeLightConeOp, '_read_character_name', _fake_char_name)
    monkeypatch.setattr(lc_module, 'SelectCharacterOp', _FakeSubOp)
    monkeypatch.setattr(lc_module, 'SwitchCharacterTabOp', _FakeSubOp)
    monkeypatch.setattr(lc_module.screen_utils, 'find_area',
                        lambda *args, **kwargs: FindAreaResultEnum.TRUE)
    return state


def _record_controller_clicks(
    monkeypatch: pytest.MonkeyPatch, ctx: SrTestContext, state: dict,
    advance_round_on_squad_click: bool = False,
) -> list[tuple[int, int]]:
    """包装 controller.click 记录点击坐标。

    advance_round_on_squad_click=True(仅手动路线测试)时:场景查询命中编队钮
    置位 in_manual_fight → 随后的编队钮点击 = 进入战斗,round+1 并清位。
    ⚠️ 标志门卫不可省:该钮 rect 与光锥-等级提升「快速升级/通用材料补全」
    执行钮坐标巧合重叠,无门卫则券链/补全链的执行钮点击会误触发推进。
    点「退出关卡」(战斗画面)恒检测 = 结算回大世界(screen_now 切大世界)。
    点大世界「右上图标-角色详情」= 打开角色详情。
    点确认框「+」= 确认框次数递增(补偿测试的现读桩随点击演进)。"""
    clicks: list[tuple[int, int]] = []
    real_click = ctx.controller.click

    def _recording_click(pos=None, press_time: float = 0, pc_alt: bool = False,
                         gamepad_key: str | None = None) -> bool:
        if pos is not None:
            x, y = int(pos.x), int(pos.y)
            clicks.append((x, y))
            if advance_round_on_squad_click and state.get('in_manual_fight') \
                    and _in_rect(x, y, _CHALLENGE, '按钮-开始编队挑战'):
                state['round'] += 1
                state['in_manual_fight'] = False
            if _in_rect(x, y, _BATTLE, '按钮-退出关卡'):
                state['screen_now'] = _WORLD
            if _in_rect(x, y, _WORLD, '右上图标-角色详情'):
                state['screen_now'] = _DETAIL
            if _in_rect(x, y, _CHALLENGE, '按钮-刷取次数加'):
                state['farm_times_read'] = state.get('farm_times_read', 0) + 1
        return real_click(pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctx.controller, 'click', _recording_click)
    return clicks


def _has_click_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> bool:
    return any(_in_rect(x, y, screen_name, area_name) for x, y in clicks)


def _count_clicks_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> int:
    return sum(1 for x, y in clicks if _in_rect(x, y, screen_name, area_name))


def _run_op(op: UpgradeLightConeOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


class TestUpgradeLightConeBranches:

    def test_fill_generic_confirms_popup(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """fill_generic 授权:通用材料补全按钮 → 确认弹窗 → 点「确认」继续升满。

        弹窗分支只许点确认、绝不点取消(取消+判停是未授权防御路径);
        材料补上后按钮转「快速升级」执行,升满进满级态判停收尾
        (LIGHT_CONE_CAPPED)。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-通用材料补全')},
            {(_LC_ASC, '标题-材料补全弹窗')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-已提升至最高阶')},
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=80)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, fill_generic=True)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'确认补全后应继续升满(满级态收尾),status={result.status},'
            f'round={state["round"]},trace={state.get("events")},'
            f'clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-通用材料补全'), (
            '缺料轮应先点通用材料补全按钮唤出弹窗'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-确认材料补全'), (
            f'授权后弹窗应点确认,clicks={clicks},round={state["round"]},'
            f'trace={state.get("events")}'
        )
        assert not _has_click_in(clicks, test_context, _LC_ASC, '按钮-取消材料补全'), (
            f'授权流不得触发取消路径,clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-快速升级')
        assert state['level_reads'] == 1, '满级态收尾应恰好读取一次等级'

    def test_popup_cancelled_without_authorization_capped(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """弹窗在场但 fill_generic 未授权:防御路径点「取消」+ 判停。

        残留弹窗态下未授权 = 绝不点确认(确认即真实消耗稀缺通用材料);
        取消判停后经「关闭X」回光锥 TAB,LIGHT_CONE_CAPPED 结束。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-材料补全弹窗')},
            set(),
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, fill_generic=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'未授权弹窗应取消判停收尾,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-取消材料补全'), (
            '未授权防御路径应点取消'
        )
        assert not _has_click_in(clicks, test_context, _LC_ASC, '按钮-确认材料补全'), (
            f'未授权绝不允许点确认(稀缺消耗),clicks={clicks}'
        )
        assert state['find_clicks'] == [
            (_LC_TAB, '按钮-强化'),
            (_LC_ASC, '按钮-关闭X'),
        ], f'find+click 序列(开晋阶/关X收尾)漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'

    def test_ticket_farm_full_chain_returns_to_loop(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """farm_dungeon 券路线全链:缺料 NEED_FARM → 资源窗口 → 副本 →
        确认框(现读次数达标,零补偿点击)→ 确认 → 结果框 → 按浮层栈回退
        到等级提升(FARMED)→ 重入升级循环升满判停。

        券路线返回语义 = 副本关闭按栈回退(back_after_farm 命中详情锚),
        不触发大世界入口链。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-已提升至最高阶')},
            {(_LC_TAB, '标题-角色光锥')},
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=True, farm_times_per_round=1)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'券刷补料后应继续升满判停,status={result.status},'
            f'round={state["round"]},trace={state.get("events")},'
            f'clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-快速刷取'), (
            '缺料轮应点快速刷取唤出资源窗口'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-确认快速刷取'), (
            '确认框应点确认执行刷取'
        )
        assert _count_clicks_in(clicks, test_context,
                                _CHALLENGE, '按钮-刷取次数加') == 0, (
            '现读次数已达目标(1>=1)不应有点「+」补偿'
        )
        assert op._farm_rounds == 1, '应恰好执行一轮券刷取'
        assert state['screen_now'] == _LC_TAB, (
            '券路线按栈回退,不应落到大世界'
        )

    def test_ticket_farm_plus_compensation(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """确认框次数现读低于目标:点「+」补差值到目标(OCR 现读+补偿式设置)。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取')},
            {(_LC_ASC, '标题-光锥详情')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        state['farm_times_read'] = 0  # 现读 0,目标 2 → 应点「+」2 次
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      farm_times_per_round=2)
        op._init_watchdog()  # type: ignore[attr-defined]

        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.confirm_ticket_farm()
        finally:
            reset_running_state(op.ctx, op)

        assert result.is_success, f'补偿设置后应成功点确认,status={result.status}'
        plus_clicks = _count_clicks_in(clicks, test_context,
                                       _CHALLENGE, '按钮-刷取次数加')
        assert plus_clicks == 2, f'应恰好点「+」2 次,实际 {plus_clicks}'
        assert op._farm_rounds == 1

    def test_manual_fight_returns_to_world_and_reenters(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """手动路线返回兼容:进入战斗卸载浮层栈 → 退出关卡后副本「关闭X」
        直接回大世界 → BACK_TO_WORLD → 重走入口链(角色图标→重选角色→
        切TAB→强化)→ FARMED 重入升级循环。

        素裳实机对照:此路径若误按券路线的栈回退处理,流程会在错误画面卡死。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取'),
             (_CHALLENGE, '按钮-开始编队挑战')},
            set(),
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-已提升至最高阶')},
            {(_LC_TAB, '标题-角色光锥')},
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context, state,
                                           advance_round_on_squad_click=True)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'手动刷取回大世界后应经入口链继续升满判停,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-开始编队挑战'), (
            '手动路线应点编队开始挑战'
        )
        assert _has_click_in(clicks, test_context, _BATTLE, '按钮-退出关卡'), (
            '战斗结算应点退出关卡'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-关闭副本'), (
            '回大世界前应先关副本画面'
        )
        assert _has_click_in(clicks, test_context, _WORLD, '右上图标-角色详情'), (
            '大世界应点右上角色详情图标重走入口链'
        )
        assert _FakeSubOp.executed, '入口链应调用重选/切页子 op'
        assert any(k.get('cn_name') == '测试角色' for k in _FakeSubOp.executed), (
            f'重选角色应使用入口记下的名字,executed={_FakeSubOp.executed}'
        )
        assert not _has_click_in(clicks, test_context, _CHALLENGE, '按钮-确认快速刷取'), (
            '手动路线不得走券确认分支'
        )

    def test_param_validation(
        self, test_context: SrTestContext,
    ) -> None:
        """参数校验:farm_times_per_round 仅正数或 -1;farm_rounds_max >= 1。"""
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeLightConeOp(test_context, farm_times_per_round=0)
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeLightConeOp(test_context, farm_times_per_round=-2)
        with pytest.raises(ValueError, match='farm_rounds_max'):
            UpgradeLightConeOp(test_context, farm_rounds_max=0)
