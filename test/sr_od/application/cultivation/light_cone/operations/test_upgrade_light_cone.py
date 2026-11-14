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
- 晋阶横幅/材料返还页(全屏浮层):点空白关闭,先于界面重开判定处理
  (浮层盖住等级提升锚,后置会被过渡帧分支空转耗尽);
- farm_dungeon 券路线全链:资源窗口→副本→确认框(次数现读+点「+」补偿)
  →结果框→按浮层栈回退到等级提升,重入升级循环;
- 手动路线返回兼容:进入战斗卸载浮层栈,退出关卡后的副本「关闭X」直接回
  大世界——op 经 BACK_TO_WORLD 分支重走入口链(角色图标→重选角色→切TAB
  →强化),角色名取入口核对时读名区 OCR;重走入口链落在光锥 TAB 时须
  记名+读名一致才接管(防升错);
- 参数校验:farm_times_per_round 仅正数或 -1(拉满),farm_rounds_max >= 1。
"""

from __future__ import annotations

import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

import sr_od.application.cultivation.light_cone.operations.upgrade_light_cone as lc_module
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from sr_od.application.cultivation.light_cone.operations.upgrade_light_cone import (
    UpgradeLightConeOp,
)

_LC_TAB: str = '角色-光锥'
_LC_ASC: str = '光锥-等级提升'
_CHALLENGE: str = '挑战副本'
_FAST_FARM_DIALOG: str = '快速刷取弹窗'
_FAST_FARM_RESULT: str = '快速刷取结果弹窗'
_WORLD: str = '大世界-普通'
_DETAIL: str = '角色-详情'
_BATTLE: str = '战斗画面'
_LC_PROMO_BANNER: str = '光锥-等级提升-晋阶横幅'

# 测试内建档 rect 快照(来源 assets/game_data/screen_info 对应 yml 与实机
# analyze 命中;screen_info 漂移时本表测试红 → 同步)。测试环境的
# screen_loader 不加载画面数据(get_area 恒 None),点击落区断言只能用本表。
_TEST_RECTS: dict[tuple[str, str], tuple[int, int, int, int]] = {
    (_LC_TAB, '按钮-强化'): (1740, 962, 1910, 1022),
    (_LC_ASC, '按钮-快速刷取'): (1285, 965, 1450, 1015),
    (_LC_ASC, '按钮-通用材料补全'): (1527, 968, 1880, 1012),
    (_LC_ASC, '按钮-材料合成'): (1527, 968, 1880, 1012),
    (_LC_ASC, '按钮-快速升级'): (1527, 968, 1880, 1012),
    (_LC_ASC, '按钮-确认材料补全'): (990, 668, 1348, 825),
    (_LC_ASC, '按钮-取消材料补全'): (570, 668, 930, 825),
    (_LC_ASC, '按钮-关闭X'): (1826, 36, 1892, 92),
    (_CHALLENGE, '挑战按钮'): (1370, 958, 1858, 1014),
    ('培养资源窗口', '标题-培养资源窗口'): (490, 285, 740, 330),
    ('培养资源窗口', '按钮-进入副本'): (1290, 390, 1460, 440),
    ('培养资源窗口', '按钮-关闭资源窗口'): (1435, 285, 1480, 335),
    (_CHALLENGE, '按钮-快速刷取副本'): (1000, 955, 1155, 1010),
    (_FAST_FARM_DIALOG, '按钮-确认快速刷取'): (990, 740, 1348, 788),
    (_CHALLENGE, '按钮-关闭副本'): (1838, 38, 1888, 95),
    (_CHALLENGE, '按钮-开始编队挑战'): (1560, 955, 1740, 1005),
    (_FAST_FARM_RESULT, '按钮-关闭刷取结果'): (570, 788, 930, 842),
    (_FAST_FARM_DIALOG, '按钮-刷取次数加'): (1318, 570, 1374, 608),
    (_FAST_FARM_DIALOG, '按钮-取消'): (570, 740, 930, 792),
    ('开拓力补充弹窗', '按钮-取消'): (590, 707, 905, 759),
    (_BATTLE, '按钮-退出关卡'): (620, 945, 810, 1000),
    (_WORLD, '右上图标-角色详情'): (1800, 0, 1900, 100),
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
        # 查询侧画面态门卫(先于场景匹配——场景表是静态的,门卫管"画面在
        # 哪个态"):退出关卡仅存在于结算画面;编队钮已点过 = 战斗已开始,
        # 编队态查询 MISS 即画面已进结算态(点过退出关卡切 _CHALLENGE 后
        # 该钮不可见,防止静态场景表让 back_after_farm 结算分支死循环)
        if (s_name, a_name) == (_CHALLENGE, '队伍标题') \
                and state.get('squad_clicked'):
            state['screen_now'] = _BATTLE
            state['squad_clicked'] = False  # 画态翻转只发生一次(编队已散)
        if (s_name, a_name) == (_BATTLE, '按钮-退出关卡') \
                and state.get('screen_now') != _BATTLE:
            state['events'] = state.get('events', [])
            state['events'].append((state['round'], a_name, 'MISS'))
            return self.round_wait(status=f'未找到 {a_name}')
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is None:
            raise AssertionError(f'剧本耗尽:第 {state["round"]} 轮查询 {a_name}')
        if (s_name, a_name) in scene:
            state['events'] = state.get('events', [])
            state['events'].append((state['round'], a_name, 'HIT'))
            # 手动战斗编队态正锚命中 = 下一次编队钮点击是真实的「进入战斗」
            # 推进点(新 manual_fight 用 队伍标题/拟造花萼 双锚判编队态)
            if (s_name, a_name) == (_CHALLENGE, '队伍标题'):
                state['in_manual_fight'] = True
            # 结算锚命中 = 手动战斗已到结算画面(back_after_farm 据此判),
            # 画面态同步给点击门卫
            if (s_name, a_name) == (_BATTLE, '按钮-退出关卡'):
                state['screen_now'] = _BATTLE
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
        # 按真实契约(get_match_screen_name):命中集合内画面返回画面名,
        # 无匹配/整帧识别失败返回 None——桩不得返回集合首位等替身值,
        # 失真桩会让测试走与真机不同的分支
        now = state['screen_now']
        if screen_name_list is not None and now not in screen_name_list:
            return None
        return now

    def _fake_level(self, screen_name: str | None = None) -> int | None:
        state['level_reads'] += 1
        return level

    def _fake_farm_times(self) -> int | None:
        return state['farm_times_read']

    def _fake_char_name(self) -> str | None:
        state['char_name_reads'].append(1)
        return state.get('char_name_next', '测试角色')

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
    点「退出关卡」(战斗画面)恒检测 = 结算回重建副本画面(不直接切大世界);
    点副本「关闭副本」= 回大世界;点大世界「右上图标-角色详情」= 打开角色
    详情。⚠️ 三处切换都带画面态门卫(仅当 screen_now 与区域所属画面一致才
    推进):关副本/右上图标/关闭X 的 rect 在右上角几何重叠,无门卫会互相误
    触发;结算锚命中时 _fake_find_area 已把 screen_now 同步为 _BATTLE。
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
                state['squad_clicked'] = True
            if state.get('screen_now') == _BATTLE \
                    and _in_rect(x, y, _BATTLE, '按钮-退出关卡'):
                state['screen_now'] = _CHALLENGE
            if state.get('screen_now') == _CHALLENGE \
                    and _in_rect(x, y, _CHALLENGE, '按钮-关闭副本'):
                state['screen_now'] = _WORLD
            if state.get('screen_now') == _WORLD \
                    and _in_rect(x, y, _WORLD, '右上图标-角色详情'):
                state['screen_now'] = _DETAIL
            if _in_rect(x, y, _FAST_FARM_DIALOG, '按钮-刷取次数加'):
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
            {('光锥-等级提升-晋阶横幅', '标题-晋阶横幅')},
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
        assert state['level_reads'] == 2, (
            '入口起始等级与满级收尾各读一次'
        )
        assert op._ascend_banner_count == 1, (
            '晋阶横幅沿计数应恰为 1(=实际完成晋阶次数)'
        )

    def test_promo_banner_count_edge_gated(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """晋阶横幅沿计数:关闭点击未生效的 WAIT 重入轮(横幅仍在场)不得
        重复计数——横幅计数 = 实际完成晋阶次数,重计会虚高。"""
        state = _install_script(
            monkeypatch, test_context,
            [_DEAD_FRAME,
             {(_LC_PROMO_BANNER, '标题-晋阶横幅')},
             {(_LC_PROMO_BANNER, '标题-晋阶横幅')}],
            level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                op.upgrade_loop()
                op.upgrade_loop()  # 模拟关闭未生效的 WAIT 重入(横幅仍在场)
        finally:
            reset_running_state(op.ctx, op)
        assert op._ascend_banner_count == 1, (
            f'重入轮不得重复计数,实际 {op._ascend_banner_count}'
        )

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
        assert state['level_reads'] == 2, (
            '入口起始等级与判停收尾各读一次'
        )

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
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取'),
             (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
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
        assert _has_click_in(clicks, test_context, _FAST_FARM_DIALOG, '按钮-确认快速刷取'), (
            '确认框应点确认执行刷取'
        )
        assert _count_clicks_in(clicks, test_context,
                                _FAST_FARM_DIALOG, '按钮-刷取次数加') == 0, (
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
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取'),
             (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
            {(_LC_ASC, '标题-光锥详情')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        state['farm_times_read'] = 0  # 现读 0,目标 2 → 应点「+」2 次
        state['round'] = 1  # 直呼节点:场景定位到确认框在场轮(重入守卫需命中弹窗标题)
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
                                       _FAST_FARM_DIALOG, '按钮-刷取次数加')
        assert plus_clicks == 2, f'应恰好点「+」2 次,实际 {plus_clicks}'
        assert op._farm_rounds == 1

    def test_confirm_farm_wait_rerun_guard(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """券确认刷取的 WAIT 重入幂等守卫:带 until 的点击返回 WAIT 时引擎会
        原样重跑本节点——重入轮必须按画面态分流,不得重跑次数设置与确认点击。

        结果框在场 = 刷取已完成,直接 RESULT_OPEN 成功(零点击、计数不变);
        两弹窗都不在 = 刷取进行中,WAIT 慢询等待(同样零副作用)。"""
        # 用例1:结果框在场 → RESULT_OPEN 成功,无任何点击、不重复计数
        state = _install_script(
            monkeypatch, test_context,
            [{(_FAST_FARM_RESULT, '按钮-关闭刷取结果')}], level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.confirm_ticket_farm()
        finally:
            reset_running_state(op.ctx, op)
        assert result.is_success and result.status == 'RESULT_OPEN', (
            f'结果框在场应直接成功交返回分类,status={result.status}'
        )
        assert op._farm_rounds == 0, '重入守卫不得重复计数刷取轮次'
        assert not _has_click_in(clicks, test_context,
                                 _FAST_FARM_DIALOG, '按钮-刷取次数拉满'), (
            '重入守卫不得重跑拉满点击'
        )

        # 用例2:两弹窗都不在(确认已发出、刷取进行中) → WAIT 慢询等待
        state2 = _install_script(monkeypatch, test_context, [set()], level=40)
        clicks2 = _record_controller_clicks(monkeypatch, test_context, state2)
        op2 = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op2._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op2.ctx)
        try:
            with fast_sleep(op2):
                result2 = op2.confirm_ticket_farm()
        finally:
            reset_running_state(op2.ctx, op2)
        assert result2.result == OperationRoundResultEnum.WAIT, (
            f'刷取进行中应 WAIT 等待结果框,result={result2.result}'
        )
        assert op2._farm_rounds == 0, '刷取进行中重入不得重复计数'
        assert not clicks2, f'刷取进行中重入不得有任何点击,clicks={clicks2}'

        # 用例3:开拓力补充弹窗在场(确认被拦,结果框永不出现) → 置判停标志
        # 并以 POWER_BLOCKED 交返回分类原路清场(不再 round_fail 死在副本里)
        state3 = _install_script(
            monkeypatch, test_context,
            [{('开拓力补充弹窗', '标题-开拓力补充弹窗')}], level=40)
        clicks3 = _record_controller_clicks(monkeypatch, test_context, state3)
        op3 = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op3._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op3.ctx)
        try:
            with fast_sleep(op3):
                result3 = op3.confirm_ticket_farm()
        finally:
            reset_running_state(op3.ctx, op3)
        assert result3.is_success and result3.status == 'POWER_BLOCKED', (
            f'补充弹窗在场应以 POWER_BLOCKED 交返回分类清场,status={result3.status}'
        )
        assert op3._capped is True and op3._stop_status == 'POWER_CAPPED', (
            '守卫应置判停标志与 POWER_CAPPED 停因'
        )
        assert op3._farm_rounds == 0, '判停路径不得重复计数'
        assert not clicks3, f'判停路径不得有任何点击,clicks={clicks3}'

    def test_capped_exit_reports_stop_status(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """判停收尾按 _stop_status 出状态:POWER_CAPPED 场景(开拓力不足守卫
        置位)下 ③ 到光锥 TAB 即以 POWER_CAPPED 结束,与材料判停的
        LIGHT_CONE_CAPPED 可区分;并补读判停时未知的等级。"""
        state = _install_script(
            monkeypatch, test_context,
            [set(), {(_LC_TAB, '标题-角色光锥')}], level=70)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        op._capped = True
        op._stop_status = 'POWER_CAPPED'
        op._capped_level = None  # 券确认守卫判停时不在养成界面,等级未知
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.upgrade_loop()
        finally:
            reset_running_state(op.ctx, op)
        assert result.is_success and result.status == 'POWER_CAPPED', (
            f'POWER_CAPPED 停因应原样透出,status={result.status}'
        )
        assert op._capped_level == 70, f'收尾应补读判停等级,得到 {op._capped_level}'

    def test_back_after_farm_cancels_leftover_dialogs(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """刷取返回分类的残留弹窗清场:开拓力不足判停/中断现场会遗留开拓力
        补充弹窗与选次数确认框(盖住副本锚,整帧识别 None)——返回分类逐个
        点其「取消」清场重入分类,接管现场不再空转过渡帧兜底。"""
        # 用例1:开拓力补充弹窗在 → 点其取消,重入分类
        state = _install_script(
            monkeypatch, test_context,
            [{('开拓力补充弹窗', '标题-开拓力补充弹窗')}], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.back_after_farm()
        finally:
            reset_running_state(op.ctx, op)
        assert not result.is_success \
            and '开拓力补充弹窗已关' in str(result.status), (
            f'补充弹窗残留应点取消重入分类,status={result.status}'
        )
        assert ('开拓力补充弹窗', '按钮-取消') in state['find_clicks'], (
            f'应点击补充弹窗取消钮,find_clicks={state["find_clicks"]}'
        )

        # 用例2:选次数确认框在 → 点其取消,重入分类
        state2 = _install_script(
            monkeypatch, test_context,
            [{(_FAST_FARM_DIALOG, '标题-快速刷取弹窗')}], level=40)
        _record_controller_clicks(monkeypatch, test_context, state2)
        op2 = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op2._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op2.ctx)
        try:
            with fast_sleep(op2):
                result2 = op2.back_after_farm()
        finally:
            reset_running_state(op2.ctx, op2)
        assert not result2.is_success \
            and '选次数确认框已取消' in str(result2.status), (
            f'确认框残留应点取消重入分类,status={result2.status}'
        )
        assert (_FAST_FARM_DIALOG, '按钮-取消') in state2['find_clicks'], (
            f'应点击确认框取消钮,find_clicks={state2["find_clicks"]}'
        )

    def test_farm_in_dungeon_dialog_open_spin_bounded(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """确认框连续未打开的 WAIT 自旋必须有界:helper 的 WAIT 返回无重试
        上限,原样返回会无限自旋——连等 4 轮后显式失败(现场留证由
        save_screenshot 承担,测试内桩掉)。"""

        def _fake_wait_click(op_self, screen, s_name, a_name, *args, **kwargs):
            state['find_clicks'].append((s_name, a_name))
            return op_self.round_wait(status=a_name, wait=1.5)

        state = _install_script(monkeypatch, test_context, [set()], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_and_click_area',
                            _fake_wait_click)
        monkeypatch.setattr(UpgradeLightConeOp, 'save_screenshot',
                            lambda self, prefix='': '')
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                results = [op.farm_in_dungeon() for _ in range(4)]
        finally:
            reset_running_state(op.ctx, op)
        assert all(r.result == OperationRoundResultEnum.WAIT
                   for r in results[:3]), (
            f'前三轮应 WAIT 等待确认框,results={[(r.status, r.result) for r in results]}'
        )
        assert not results[3].is_success, (
            f'连等超限应显式失败,status={results[3].status}'
        )
        assert '连续未打开' in str(results[3].status)

    def test_farm_window_spin_bounded(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """快速刷取静默无反应(点击假成功但窗口不开)的有界自旋:helper 恒
        WAIT 不计重试,原样透传会无限自旋——连等 4 轮超限转 FARM_WINDOW_FAIL
        判停(现场留证由 save_screenshot 承担,测试内桩掉)。"""

        def _fake_wait_click(op_self, screen, s_name, a_name, *args, **kwargs):
            state['find_clicks'].append((s_name, a_name))
            return op_self.round_wait(status=a_name, wait=1.5)

        state = _install_script(monkeypatch, test_context, [set()], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_and_click_area',
                            _fake_wait_click)
        monkeypatch.setattr(UpgradeLightConeOp, 'save_screenshot',
                            lambda self, prefix='': '')
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                results = [op.open_farm_window() for _ in range(4)]
        finally:
            reset_running_state(op.ctx, op)
        assert all(r.result == OperationRoundResultEnum.WAIT
                   for r in results[:3]), (
            f'前三轮应 WAIT,results={[(r.status, r.result) for r in results]}'
        )
        assert results[3].is_success and results[3].status == 'FARM_WINDOW_FAIL', (
            f'连等超限应转 FARM_WINDOW_FAIL 判停,status={results[3].status}'
        )
        assert op._capped is True and op._stop_status == 'LIGHT_CONE_CAPPED', (
            '连等超限判停应置光锥停因'
        )

    def test_farm_window_toast_stops_immediately(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """无可刷缺口正判:场景含 toast 锚 → open_farm_window 首轮即
        FARM_WINDOW_FAIL 判停——find_clicks 空锁代码顺序(探测先于任何
        点击,先点后探的实现会让桩记到点击而本测试红);置位与既有判停
        路径一致,计数复位。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_LC_ASC, '提示-无可刷缺口')}], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeLightConeOp, 'save_screenshot',
                            lambda self, prefix='': '')
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.open_farm_window()
        finally:
            reset_running_state(op.ctx, op)
        assert result.is_success and result.status == 'FARM_WINDOW_FAIL', (
            f'toast 命中应即判停收口,status={result.status}'
        )
        assert op._capped is True and op._stop_status == 'LIGHT_CONE_CAPPED', (
            '正判应置判停标志与光锥停因'
        )
        assert op._farm_window_wait_rounds == 0, '判停路径应复位连等计数'
        assert state['find_clicks'] == [], (
            f'命中 toast 不得再点击(正判先于点击),find_clicks={state["find_clicks"]}'
        )

    def test_farm_window_toast_probe_gated_after_first_round(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """探测门:连等计数 ≥2 后抑制 toast 探测——慢开窗场景冗余二次点击
        被拒再弹的 toast 不得被误读为无可刷缺口(否则合法升级被提前误判
        停,停因还错)。计数置 2 + toast 锚在场仍走 helper(窗口已开)。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_LC_ASC, '提示-无可刷缺口')}], level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        op._farm_window_wait_rounds = 2
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.open_farm_window()
        finally:
            reset_running_state(op.ctx, op)
        assert result.is_success and result.status == '按钮-快速刷取', (
            f'计数 ≥2 应抑制探测走 helper(窗口开),status={result.status}'
        )
        assert op._capped is False, '抑制轮不得误判停'
        assert (_LC_ASC, '提示-无可刷缺口') not in state['find_events'], (
            '抑制轮不得发起 toast 探测查询'
        )
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-快速刷取'), (
            '抑制轮应照常走 helper 点击路径'
        )

    def test_back_after_farm_closes_team_screen(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """编队画面清场(手动路线开拓力被拦取消补充弹窗后/编队残留的落点):
        队伍标题在场时点右上 X(与副本关闭钮同槽位)回副本画面再逐层回退
        ——无此分支会落进「未识别画面」空转耗尽节点预算。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_CHALLENGE, '队伍标题')}], level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.back_after_farm()
        finally:
            reset_running_state(op.ctx, op)
        assert not result.is_success \
            and '编队画面已关' in str(result.status), (
            f'编队画面应点 X 回副本画面重入分类,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-关闭副本'), (
            f'应点击右上 X(与关闭副本同槽位),clicks={clicks}'
        )

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
             (_CHALLENGE, '按钮-开始编队挑战'), (_CHALLENGE, '队伍标题')},
            {(_BATTLE, '按钮-退出关卡')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-已提升至最高阶')},
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
            f'手动刷取回大世界后应经入口链继续升满判停,status={result.status},'
            f'round={state["round"]},in_fight={state.get("in_manual_fight")},'
            f'trace={state.get("events")},clicks={clicks}'
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
        assert not _has_click_in(clicks, test_context, _FAST_FARM_DIALOG, '按钮-确认快速刷取'), (
            '手动路线不得走券确认分支'
        )

    def test_unknown_dungeon_type_fails_bounded(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未识别副本类型有界失败(引擎级):挑战按钮在但「拟造花萼」标题
        持续读不到(未建档类型/OCR 持续失败)时,手动路线不得零消耗空转
        ——不计场的 BATTLE_DONE 会反复回环「关副本→大世界→重走入口→
        再开窗进本」形成无限循环;重试耗尽显式失败强制补档。"""
        scenes = [
            _DEAD_FRAME,  # 入口轮
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取'),
             (_CHALLENGE, '挑战按钮')},  # r1:缺料 → 刷取链 → 未识别副本画面
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert not result.success and '未识别' in (result.status or ''), (
            f'未识别副本类型应重试耗尽有界失败,status={result.status},'
            f'trace={state.get("events")}'
        )
        assert _count_clicks_in(clicks, test_context,
                                '培养资源窗口', '按钮-进入副本') == 1, (
            '未识别类型不得回环再开窗进本(零消耗空转无限循环防线)'
        )
        # 挑战按钮 rect 与等级提升「快速刷取」执行钮几何重叠,坐标断言
        # 会误伤合法点击,以 find_clicks(画面+区域对)断言
        assert (_CHALLENGE, '挑战按钮') not in state['find_clicks'], (
            f'未识别类型不得盲点挑战按钮,find_clicks={state["find_clicks"]}'
        )

    def test_manual_battle_wait_survives_long_fight(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """战斗期不烧重试预算(引擎级):手动路线整场战斗落返回分类的过渡
        帧分支——旧实现以 round_retry 计数,30 次预算耗尽即战斗中途 FAIL
        (战场残留游戏内继续自打,污染后续入口判定)。新语义 WAIT 慢询
        不计数,超时兜底交节点 timeout_seconds。战斗时长以「退出关卡
        探测次数」计轮,35 轮后结算画面出现(旧实现必挂)。"""
        scenes = [
            _DEAD_FRAME,  # 入口轮
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速刷取'),
             (_CHALLENGE, '队伍标题'), (_CHALLENGE, '按钮-开始编队挑战')},  # r1:缺料 → 编队态
            set(),  # r2:战斗期(全锚 MISS,战斗时钟到期后切结算)
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-快速升级')},  # r3:回界面材料齐
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-已提升至最高阶')},  # r4:满级态
            {(_LC_TAB, '标题-角色光锥')},  # r5:收尾回 TAB
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        _FakeSubOp.executed = []
        clicks = _record_controller_clicks(monkeypatch, test_context, state,
                                           advance_round_on_squad_click=True)
        # 战斗时钟:返回分类在战斗态每轮探测一次退出关卡,计满 35 轮后把
        # 剧本切到结算轮(模拟整场战斗 > 旧重试预算容忍上限)
        battle_clock = {'n': 0}
        installed_find = UpgradeLightConeOp.round_by_find_area

        def _battle_clock_find(self, screen, s_name, a_name, *args, **kwargs):
            if (s_name, a_name) == (_BATTLE, '按钮-退出关卡') \
                    and state.get('screen_now') == _BATTLE:
                battle_clock['n'] += 1
                if battle_clock['n'] >= 35:
                    scenes[2] = {(_BATTLE, '按钮-退出关卡')}
            return installed_find(self, screen, s_name, a_name, *args, **kwargs)

        monkeypatch.setattr(UpgradeLightConeOp, 'round_by_find_area',
                            _battle_clock_find)
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'长战斗(35 轮 > 旧 30 次重试预算)后应继续走完到判停收尾,'
            f'status={result.status},battle_rounds={battle_clock["n"]},'
            f'round={state["round"]},trace={state.get("events")},'
            f'clicks={clicks}'
        )
        assert op._manual_fights == 1 and op._farm_rounds == 1, (
            f'战斗期等待不得影响计场,fights={op._manual_fights},'
            f'rounds={op._farm_rounds}'
        )
        assert _has_click_in(clicks, test_context, _BATTLE, '按钮-退出关卡'), (
            '战斗结束应点退出关卡收口'
        )

    def test_reentry_tab_identity_gate(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """重走入口链落在光锥 TAB:有记名且读名一致才接管点强化(防升错)。

        名字一致 → 点强化 → FARMED;读名不一致 / 无记名 → fail 且绝不点
        强化——角色页记忆≠目标角色(实测记忆的是最近战斗编队首位)。"""
        state = _install_script(monkeypatch, test_context, [set()], level=79)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)

        # 用例1:记名 = 读名 → 接管点强化
        op = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._char_name = '测试角色'
        state['screen_now'] = _LC_TAB
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                result = op.reenter_from_world()
        finally:
            reset_running_state(op.ctx, op)
        assert result.is_success and result.status == 'FARMED', (
            f'记名与读名一致应接管点强化,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _LC_TAB, '按钮-强化')

        # 用例2:读名不一致 → fail,不点强化
        state['char_name_next'] = '别人'
        state['screen_now'] = _LC_TAB
        op2 = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                       use_fast_ticket=False)
        op2._char_name = '测试角色'
        enter_running_state(op2.ctx)
        try:
            with fast_sleep(op2):
                result2 = op2.reenter_from_world()
        finally:
            reset_running_state(op2.ctx, op2)
        assert not result2.is_success, '读名不一致应判停防升错'
        # clicks 是共享列表:用例1已有一条强化点击,此处以 find_clicks 增量判断
        assert state['find_clicks'].count((_LC_TAB, '按钮-强化')) == 1, (
            f'不一致时不得再点强化,find_clicks={state["find_clicks"]}'
        )

        # 用例3:无记名 → fail,不点强化
        state['screen_now'] = _LC_TAB
        op3 = _WatchedUpgradeLightCone(test_context, farm_dungeon=True,
                                       use_fast_ticket=False)
        op3._char_name = None
        enter_running_state(op3.ctx)
        try:
            with fast_sleep(op3):
                result3 = op3.reenter_from_world()
        finally:
            reset_running_state(op3.ctx, op3)
        assert not result3.is_success, '无记名应判停防升错'
        assert state['find_clicks'].count((_LC_TAB, '按钮-强化')) == 1, (
            f'无记名时不得点强化,find_clicks={state["find_clicks"]}'
        )

    def test_material_craft_button_crafts_and_finishes(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """「材料合成」执行钮形态(不需通用材料的合成:原始材料满足或通用
        不够):fill_generic 点它 → 同款「材料补全」确认框 → 确认 → 升满;
        fill_generic=False 时该形态直接判停不走刷取(此形态快速刷取静默
        无效,实机实证资源窗口打不开)。"""
        # 用例1:fill_generic=True 走合成升满
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-材料合成')},
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
            f'材料合成路线应确认补全后升满,status={result.status},'
            f'round={state["round"]},trace={state.get("events")}'
        )
        # 材料合成钮与快速升级/通用材料补全同 rect 同中心,场景表 r1 只有
        # 材料合成命中 = 分支唯一,直点断言以确认弹窗点击佐证
        assert _has_click_in(clicks, test_context, _LC_ASC, '按钮-确认材料补全'), (
            f'弹窗应点确认执行合成,clicks={clicks}'
        )
        assert not _has_click_in(clicks, test_context, _LC_ASC, '按钮-取消材料补全')

        # 用例2:fill_generic=False 直接判停,不点合成钮、不进刷取链
        scenes2 = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '按钮-材料合成')},
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state2 = _install_script(monkeypatch, test_context, scenes2, level=79)
        clicks2 = _record_controller_clicks(monkeypatch, test_context, state2)
        op2 = _WatchedUpgradeLightCone(test_context, fill_generic=False,
                                       farm_dungeon=True)
        op2._init_watchdog()  # type: ignore[attr-defined]

        result2 = _run_op(op2)

        assert result2.success and result2.status == 'LIGHT_CONE_CAPPED', (
            f'材料合成形态未授权应判停收尾,status={result2.status}'
        )
        # 强化钮点击坐标与材料合成 rect 巧合重叠,反向断言以确认钮(独立
        # rect)与 find_clicks 序列锁:直判停收尾,没点确认、没进刷取链
        assert not _has_click_in(clicks2, test_context, _LC_ASC, '按钮-确认材料补全'), (
            '未授权不得点确认执行合成'
        )
        assert state2['find_clicks'] == [
            (_LC_TAB, '按钮-强化'),
        ], f'应直接判停收尾不进刷取链(r2 场景已在光锥 TAB,无关闭X),find_clicks={state2["find_clicks"]}'

    def test_insufficient_gray_text_stops(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """「材料不足」灰字态(全缺)显式判停收尾——该文本与「材料合成」
        共享「材料」前缀,实机曾因默认相似度误命中走错分支(40 轮空转);
        修复后灰字走 ⑨ 判停,不点任何执行钮。"""
        scenes = [
            _DEAD_FRAME,
            {(_LC_ASC, '标题-光锥详情'), (_LC_ASC, '文本-材料不足')},
            {(_LC_TAB, '标题-角色光锥')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=70)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeLightCone(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'LIGHT_CONE_CAPPED', (
            f'灰字全缺态应判停收尾,status={result.status}'
        )
        # 唯一点击 = 入口开界面的强化钮;无确认/取消/合成类执行点击
        assert state['find_clicks'] == [(_LC_TAB, '按钮-强化')], (
            f'灰字态应零执行点击直接判停,find_clicks={state["find_clicks"]}'
        )

    def test_param_validation(
        self, test_context: SrTestContext,
    ) -> None:
        """参数校验:farm_times_per_round 仅正数或 -1;farm_rounds_max >= 1。
        默认策略锁:fill_generic 开、每轮拉满(-1)、预算 1 轮——通用材料
        最优先 + 刷取一轮拉满(材料共享库存,多余留他用)。"""
        op = UpgradeLightConeOp(test_context)
        assert op.fill_generic is True
        assert op.farm_times_per_round == -1
        assert op.farm_rounds_max == 1
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeLightConeOp(test_context, farm_times_per_round=0)
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeLightConeOp(test_context, farm_times_per_round=-2)
        with pytest.raises(ValueError, match='farm_rounds_max'):
            UpgradeLightConeOp(test_context, farm_rounds_max=0)
