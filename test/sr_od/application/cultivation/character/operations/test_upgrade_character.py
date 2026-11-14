"""UpgradeCharacterOp(角色晋阶升级)流程测试。

测试层级声明:桩识别层的单元式流程测试(理由同 test_upgrade_trace.py
——「角色-等级提升」等面板态帧测试仓缺存档、识别类输入禁止合成),
monkeypatch 识别层构造 round 结果,驱动完整 ``execute()`` 节点图。

锁定的设计约定(出处 upgrade_character.py 模块 docstring 与各节点实现,
实机摸底:等级1角色全形态链路):
- 入口画面级判定 + 右下按钮三态分流:详情页右下「升级」(未满级)/
  「晋阶」(到上限)/无按钮(80 满)——未满级角色不得再被误判已满;
- 通用材料补全链(fill_generic 默认 True):缺料按钮 → 确认框确认 →
  材料齐后快速升级执行;确认框在场但未授权 = 取消+判停,绝不点确认;
- 刷取链(farm_dungeon):资源窗口 → 副本 → 券确认(次数现读+点「+」
  补偿,-1 拉满)/手动挑战双锚 → 返回分类逐层清场回养成界面;
- 刷取消耗记账以确认框实际设到的次数为准(_farm_draws),配置 -1 是
  拉满指令非次数;手动路线不耗券;
- 开拓力不足守卫:补充弹窗在场即 POWER_BLOCKED 交返回分类清场
  (POWER_CAPPED 收尾),绝不死在副本里;
- 手动路线返回兼容:退出关卡后副本关闭直接回大世界 → BACK_TO_WORLD
  → 重走入口链(角色图标→重选角色→切详情TAB),凭入口记名防升错;
- 快速刷取静默无反应(无可刷缺口)= FARM_WINDOW_FAIL 回循环判停,
  不许无界自旋。
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

import sr_od.application.cultivation.character.operations.upgrade_character as char_module
from one_dragon.base.geometry.point import Point
from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import OperationRoundResultEnum
from one_dragon.base.screen.screen_utils import FindAreaResultEnum
from sr_od.application.cultivation.character.operations.upgrade_character import (
    UpgradeCharacterOp,
)

_DETAIL: str = '角色-详情'
_ASCEND: str = '角色-等级提升'
_CHALLENGE: str = '挑战副本'
_FAST_FARM_DIALOG: str = '快速刷取弹窗'
_FAST_FARM_RESULT: str = '快速刷取结果弹窗'
_RESOURCE: str = '培养资源窗口'
_WORLD: str = '大世界-普通'
_BATTLE: str = '战斗画面'

# 升级循环每轮分类的必查锚(优先级①,每轮无条件查询),桩以它计轮推进
# 剧本;循环首轮另先查界面标题锚(起始等级),不作标记以免入口轮误推进
_ROUND_START: tuple[str, str] = (_ASCEND, '标题-材料补全弹窗')


class _WatchedUpgradeCharacter(WatchdogOperationMixin, UpgradeCharacterOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 80  # 手动刷取链含战斗/结算/大世界往返,预算需富余

    def __init__(self, ctx: SrTestContext, fill_generic: bool = True,
                 farm_dungeon: bool = True, use_fast_ticket: bool = True,
                 farm_times_per_round: int = 1, farm_rounds_max: int = 10) -> None:
        """真实构造路径;测试无游戏窗口,跳过窗口前置链。

        farm_dungeon 测试默认 True(与生产默认 False 相反):刷取链测试
        需要触发刷取路线;「不刷判停」语义由专门测试显式 farm_dungeon=False
        锁定,避免默认值掩盖。farm_rounds_max 替身默认 10(预算耗尽语义
        的既有测试依赖),生产默认 1 由生产构造直传。farm_times_per_round
        替身默认 1(生产默认 -1 拉满)——次数设置类断言用例显式传参。"""
        UpgradeCharacterOp.__init__(self, ctx, fill_generic=fill_generic,
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
    farm_times: int = 1,
) -> dict:
    """桩识别层并装记录器。

    state 键:round(剧本轮,弹窗锚查询推进)/level_reads/farm_times_read
    (确认框次数现读值,点「+」由点击记录器递增)/screen_now(可变画面名,
    check_and_update 返回;None 模拟模态弹窗盖住 id_mark 的整帧识别失败)/
    char_name_next(读名桩返回值)/in_manual_fight(编队态标志,编队钮点击
    推进用)/find_events/find_clicks。"""
    state: dict = {'round': 0, 'level_reads': 0, 'find_events': [],
                   'find_clicks': [], 'farm_times_read': farm_times,
                   'screen_now': _DETAIL, 'char_name_next': '测试角色',
                   'in_manual_fight': False}

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        if (s_name, a_name) == _ROUND_START:
            state['round'] += 1
        # 查询侧画面态门卫:退出关卡仅存在于结算画面;点击记录器把画面切走
        # 后(退出关卡已点),同场景表的后续查询 MISS,防止静态场景表让返回
        # 分类重复点退出关卡死循环
        if (s_name, a_name) == (_BATTLE, '按钮-退出关卡') \
                and state.get('screen_now') != _BATTLE:
            return self.round_wait(status=f'未找到 {a_name}')
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is None:
            raise AssertionError(f'剧本耗尽:第 {state["round"]} 轮查询 {a_name}')
        if (s_name, a_name) in scene:
            # 编队态正锚命中 = 随后的编队钮点击是真实「进入战斗」推进点
            if (s_name, a_name) == (_CHALLENGE, '队伍标题'):
                state['in_manual_fight'] = True
            return self.round_success(status=a_name)
        return self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
        state['find_clicks'].append((s_name, a_name))
        # 走 controller.click:让点击记录器与画面状态推进(退出关卡→副本、
        # 关闭副本→大世界等)与真实链路一致
        self.ctx.controller.click(_rect_center(ctx, s_name, a_name))
        return self.round_success(status=a_name)

    def _fake_check_screen(self, screen=None, screen_name_list=None,
                           crop_first=False):
        now = state['screen_now']
        # None(整帧识别失败)原样透传,走 op 的逐锚兜底分支
        if screen_name_list is not None and now is not None \
                and now not in screen_name_list:
            return screen_name_list[0]
        return now

    def _fake_static_find(ctx_arg, screen, s_name, a_name, *args, **kwargs):
        # 入口 None 兜底的逐锚探测(走 screen_utils.find_area):按场景表命中
        scene = scenes[state['round']] if state['round'] < len(scenes) else None
        if scene is not None and (s_name, a_name) in scene:
            return FindAreaResultEnum.TRUE
        return FindAreaResultEnum.FALSE

    def _fake_level(self) -> int | None:
        state['level_reads'] += 1
        return level

    def _fake_farm_times(self) -> int | None:
        return state['farm_times_read']

    def _fake_char_name(self) -> str | None:
        return state.get('char_name_next')

    monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeCharacterOp, 'check_and_update_current_screen',
                        _fake_check_screen)
    monkeypatch.setattr(UpgradeCharacterOp, '_read_ascend_level', _fake_level)
    monkeypatch.setattr(UpgradeCharacterOp, '_read_farm_times', _fake_farm_times)
    monkeypatch.setattr(UpgradeCharacterOp, '_read_character_name', _fake_char_name)
    monkeypatch.setattr(char_module, 'SelectCharacterOp', _FakeSubOp)
    monkeypatch.setattr(char_module, 'SwitchCharacterTabOp', _FakeSubOp)
    monkeypatch.setattr(char_module.screen_utils, 'find_area', _fake_static_find)
    return state


def _rect_center(ctx: SrTestContext, s_name: str, a_name: str) -> Point:
    """建档 rect 中心(点击桩用;区域未建档 = 测试写错,直接抛)。"""
    rect = ctx.screen_loader.get_area(s_name, a_name).pc_rect
    return Point((rect.x1 + rect.x2) / 2, (rect.y1 + rect.y2) / 2)


def _in_rect(x: int, y: int, ctx: SrTestContext,
             s_name: str, a_name: str) -> bool:
    rect = ctx.screen_loader.get_area(s_name, a_name).pc_rect
    return rect.x1 <= x <= rect.x2 and rect.y1 <= y <= rect.y2


def _record_controller_clicks(
    monkeypatch: pytest.MonkeyPatch, ctx: SrTestContext, state: dict,
    advance_round_on_squad_click: bool = False,
    advance_round_on_challenge_click: bool = False,
) -> list[tuple[int, int]]:
    """包装 controller.click 记录点击坐标,并按画面态推进剧本/画面状态。

    - 编队钮点击(in_manual_fight 置位时) = 进入战斗:round+1、画面切
      战斗态、清标志(advance_round_on_squad_click,仅手动路线测试启用)。
      ⚠️ 该钮 rect 与等级提升执行钮、挑战按钮坐标重叠,无标志门卫会误触发;
    - 挑战按钮点击(画面态=挑战副本) = 副本→编队画面切换:round+1
      (advance_round_on_challenge_click)。⚠️ 必须排在编队钮守卫之后:
      编队钮 rect 落在挑战按钮 rect 之内,先判挑战钮会双重推进;
    - 画面态切换链(if/elif 互斥):快速刷取(详情态)→资源窗口、进入副本
      (资源窗口态)→副本、退出关卡(战斗态)→重建副本(round+1)、关闭副本
      (副本态)→大世界(round+1)、右上角色图标(大世界态)→角色详情
      (round+1)。⚠️ 关闭副本/右上图标/关闭类控件的 rect 在右上角几何
      重叠,互斥链保证一次点击只归一个分支;
    - 确认框「+」= 次数现读值 +1(补偿式设置的演进)。"""
    clicks: list[tuple[int, int]] = []
    real_click = ctx.controller.click

    def _recording_click(pos=None, press_time: float = 0, pc_alt: bool = False,
                         gamepad_key: str | None = None) -> bool:
        if pos is not None:
            x, y = int(pos.x), int(pos.y)
            clicks.append((x, y))
            if advance_round_on_squad_click and state.get('in_manual_fight') \
                    and _in_rect(x, y, ctx, _CHALLENGE, '按钮-开始编队挑战'):
                state['round'] += 1
                state['in_manual_fight'] = False
                state['screen_now'] = _BATTLE
            if advance_round_on_challenge_click \
                    and state.get('screen_now') == _CHALLENGE \
                    and _in_rect(x, y, ctx, _CHALLENGE, '挑战按钮'):
                state['round'] += 1
            # 画面态切换链(互斥)
            now = state.get('screen_now')
            if now == _DETAIL and _in_rect(x, y, ctx, _ASCEND, '按钮-快速刷取'):
                state['screen_now'] = _RESOURCE
            elif now == _RESOURCE and _in_rect(x, y, ctx, _RESOURCE, '按钮-进入副本'):
                state['screen_now'] = _CHALLENGE
            elif now == _BATTLE and _in_rect(x, y, ctx, _BATTLE, '按钮-退出关卡'):
                state['screen_now'] = _CHALLENGE
                state['round'] += 1
            elif now == _CHALLENGE and _in_rect(x, y, ctx, _CHALLENGE, '按钮-关闭副本'):
                state['screen_now'] = _WORLD
                state['round'] += 1
            elif now == _WORLD and _in_rect(x, y, ctx, _WORLD, '右上图标-角色详情'):
                state['screen_now'] = _DETAIL
                state['round'] += 1
            if _in_rect(x, y, ctx, _FAST_FARM_DIALOG, '按钮-刷取次数加'):
                state['farm_times_read'] = state.get('farm_times_read', 0) + 1
        return real_click(pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctx.controller, 'click', _recording_click)
    return clicks


def _has_click_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> bool:
    """是否有点击落在建档区 pc_rect 内(坐标单一真相源 = screen_info)。"""
    return any(_in_rect(x, y, ctx, screen_name, area_name) for x, y in clicks)


def _count_clicks_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> int:
    return sum(1 for x, y in clicks if _in_rect(x, y, ctx, screen_name, area_name))


def _run_op(op: UpgradeCharacterOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


def _call_node(op: UpgradeCharacterOp, node_name: str):
    """运行态前置复位 + fast_sleep 直呼单节点(守卫/分支专项测试用)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return getattr(op, node_name)()
    finally:
        reset_running_state(op.ctx, op)


class TestUpgradeCharacterEntryStates:

    def test_unmaxed_level_entry_not_mistaken_as_max(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口「升级」按钮(未满级角色)分流:不得误判已满。

        实机摸底:等级未到上限的角色右下按钮是「升级」而非「晋阶」,
        旧版只认「晋阶」会把这类角色误判 ALREADY_MAX 直接退出——本测试
        锁定「升级」入口正常打开界面并走升级循环。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮1:执行升级
            {(_ASCEND, '标题-升级结果')},                            # 轮2:升级横幅
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:详情页判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=80)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'未满级入口应正常升级到满,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _DETAIL, '按钮-升级'), (
            '未满级入口应点击「升级」按钮打开界面'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-快速升级'), (
            '材料足轮次应执行升级点击'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-升级'),
            (_ASCEND, '点击区-关闭横幅'),
        ], f'find+click 序列(开界面/关升级横幅)漂移:{state["find_clicks"]}'
        assert state['level_reads'] == 1, (
            '起始等级读数(首入晋阶界面即读,此路径原不读等级)'
        )
        assert op._banner_upgrade_count == 1, (
            '升级横幅沿计数应恰为 1(=实际完成升级次数)'
        )

    def test_already_max_entry_stays_zero_click(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口无按钮(80/80):零点击直接 MAX_LEVEL(已满判据保持)。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'无按钮起点应直接 MAX_LEVEL,status={result.status}'
        )
        assert clicks == [], f'已满级起点不应有任何画面点击:{clicks}'


class TestUpgradeCharacterEntryTakeover:
    """入口残留现场接管:画面级判定未命中(None)时逐锚探测分流。"""

    def test_leftover_probes_route_by_anchor(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """None 兜底逐锚探测:残留弹窗(选次数/结果/开拓力补充)、战斗结算
        退出钮、副本挑战锚各按 LEFTOVER 接管;等级提升标题按 ALREADY_ASCEND
        直入升级循环——中断现场不再快速失败。"""
        cases = [
            ((_FAST_FARM_DIALOG, '标题-快速刷取弹窗'), 'LEFTOVER'),
            ((_FAST_FARM_RESULT, '标题-快速刷取弹窗'), 'LEFTOVER'),
            (('开拓力补充弹窗', '标题-开拓力补充弹窗'), 'LEFTOVER'),
            ((_BATTLE, '按钮-退出关卡'), 'LEFTOVER'),
            ((_CHALLENGE, '挑战按钮'), 'LEFTOVER'),
            ((_ASCEND, '标题-等级提升'), 'ALREADY_ASCEND'),
            ((_ASCEND, '标题-材料补全弹窗'), 'ALREADY_ASCEND'),
        ]
        for anchor, expected in cases:
            state = _install_script(
                monkeypatch, test_context, [{anchor}], level=0)
            state['screen_now'] = None  # 模态盖住画面 id_mark,整帧识别失败
            _record_controller_clicks(monkeypatch, test_context, state)
            op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
            op._init_watchdog()  # type: ignore[attr-defined]

            result = _call_node(op, 'check_entry')

            assert result.is_success and result.status == expected, (
                f'{anchor} 残留应接管为 {expected},status={result.status}'
            )

    def test_entry_world_routes_reenter(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """入口落在大世界(手动链中断落点):BACK_TO_WORLD 交重走入口链。"""
        state = _install_script(monkeypatch, test_context, [set()], level=0)
        state['screen_now'] = _WORLD
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _call_node(op, 'check_entry')

        assert result.is_success and result.status == 'BACK_TO_WORLD', (
            f'大世界落点应交重走入口链,status={result.status}'
        )

    def test_manual_route_fails_fast_without_name(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """手动链读名失败 = 消耗前判停:返回链需凭记名重选角色,读不到
        就在开战前拦住(等打完一场再失败会白烧开拓力)。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')}], level=0)
        state['char_name_next'] = None
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _call_node(op, 'check_entry')

        assert not result.is_success and '读名' in str(result.status), (
            f'手动链读名失败应在消耗前判停,status={result.status}'
        )


class TestUpgradeCharacterFillGeneric:

    def test_generic_fill_then_upgrade_chain(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """通用材料补全全链(fill_generic 默认 True):缺料按钮 → 确认框
        确认 → 材料齐 → 快速升级执行 → 横幅关闭 → 详情判满。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-通用材料补全')},  # 轮1:缺料
            {(_ASCEND, '标题-材料补全弹窗')},                       # 轮2:确认框
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮3:材料齐
            {(_ASCEND, '标题-晋阶结果')},                           # 轮4:晋阶横幅(双锚之一)
            {(_DETAIL, '按钮-属性详情')},                           # 轮5:详情页判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context)  # fill_generic 默认 True
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'通用材料补全链应以满级结束,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-通用材料补全'), (
            '缺料轮应点击「使用通用材料补全」'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-确认材料补全'), (
            '确认框轮应点击确认(fill_generic 默认授权)'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-升级'),
            (_ASCEND, '点击区-关闭横幅'),
        ], f'find+click 序列漂移:{state["find_clicks"]}'
        assert state['find_events'].count(_ROUND_START) == 5, (
            '循环应恰好分类 5 轮,轮数漂移 = 循环结构变化'
        )
        assert op._banner_promotion_count == 1, (
            '晋阶横幅沿计数应恰为 1(=实际完成晋阶次数)'
        )

    def test_fill_generic_false_stops_on_lacking(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """fill_generic=False:缺料判停 MATERIAL_CAPPED,不碰通用材料补全。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-晋阶')},   # 入口轮:到上限态
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-通用材料补全')},  # 轮1:缺料判停
            {(_ASCEND, '标题-等级提升')},                           # 轮2:收尾途中
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:回到详情
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=20)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, fill_generic=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'未授权通用材料应判停收尾,status={result.status}'
        )
        # 负向断言走 find_clicks(精确):详情页入口按钮 rect 与养成界面
        # 右下执行钮 rect 几何重叠,入口点击会落进执行钮矩形,rect 断言误报
        assert (_ASCEND, '按钮-通用材料补全') not in state['find_clicks'], (
            'fill_generic=False 不应点击通用材料补全按钮'
        )
        assert (_ASCEND, '按钮-确认材料补全') not in state['find_clicks'], (
            'fill_generic=False 不应确认材料补全弹窗'
        )
        assert state['find_clicks'][-1] == (_ASCEND, '按钮-返回箭头'), (
            '判停后应经返回箭头收尾'
        )
        assert state['level_reads'] == 2, (
            '起始等级与判停等级各读一次'
        )

    def test_popup_cancelled_without_authorization_capped(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """确认框在场但 fill_generic 未授权:防御路径点「取消」+ 判停。

        残留确认框态下未授权 = 绝不点确认(确认即真实消耗通用材料);
        取消判停后经返回箭头收尾,MATERIAL_CAPPED 结束。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-晋阶')},   # 入口轮
            {(_ASCEND, '标题-材料补全弹窗')},                       # 轮1:确认框在场
            {(_ASCEND, '标题-等级提升')},                           # 轮2:收尾途中
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:回到详情
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=70)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, fill_generic=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'未授权确认框应取消判停收尾,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _ASCEND, '按钮-取消材料补全'), (
            '未授权防御路径应点取消'
        )
        assert not _has_click_in(clicks, test_context, _ASCEND, '按钮-确认材料补全'), (
            f'未授权绝不允许点确认,clicks={clicks}'
        )
        assert state['find_clicks'][-1] == (_ASCEND, '按钮-返回箭头'), (
            f'取消判停后应经返回箭头收尾,find_clicks={state["find_clicks"]}'
        )
        assert state['level_reads'] == 2, (
            '起始等级与判停等级各读一次'
        )


class TestUpgradeCharacterFarmRoute:

    def test_gray_lacking_triggers_ticket_farm_then_upgrade(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """右下全灰(材料不足)触发券刷取链:

        灰底 → 打开「培养还需获取资源」窗口 → 点「进入」直达副本 → 副本
        左下「快速刷取」(券) → 确认框确认(免战斗领奖) → 关副本回养成界面
        → 材料齐 → 快速升级执行 → 横幅关 → 详情判满。消耗按确认框实际
        设到的次数记账。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},  # 轮1:全灰 → NEED_FARM
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮2:材料齐
            {(_ASCEND, '标题-升级结果')},                          # 轮3:升级横幅
            {(_DETAIL, '按钮-属性详情')},                          # 轮4:详情判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=0)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context)  # use_fast_ticket 默认 True
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'券刷取链应走通到满级,status={result.status}'
        )
        assert state['find_clicks'] == [
            (_DETAIL, '按钮-升级'),
            (_ASCEND, '按钮-快速刷取'),
            (_RESOURCE, '按钮-进入副本'),
            (_CHALLENGE, '按钮-快速刷取副本'),
            (_FAST_FARM_DIALOG, '按钮-确认快速刷取'),
            (_ASCEND, '点击区-关闭横幅'),
        ], f'刷取链 find+click 序列漂移:{state["find_clicks"]}'
        assert op._farm_rounds == 1, f'应恰好刷取 1 轮,实际 {op._farm_rounds}'
        assert op._farm_draws == 1, (
            f'消耗记账应按确认框实际读数,draws={op._farm_draws}'
        )
        assert state['level_reads'] == 1, (
            '起始等级读数(首入晋阶界面即读,此路径原不读等级)'
        )

    def test_farm_times_max_uses_fill_button(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """farm_times_per_round=-1:确认框内点「^」拉满按钮(滑条上限),
        OCR 复核后确认——锁定拉满语义的交互路径与实数记账。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},  # 轮1:灰底 → 刷取链
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮2:材料齐
            {(_ASCEND, '标题-升级结果')},                          # 轮3:横幅
            {(_DETAIL, '按钮-属性详情')},                          # 轮4:判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_times_per_round=-1)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'拉满刷取链应走通,status={result.status}'
        )
        assert _has_click_in(
            clicks, test_context, _FAST_FARM_DIALOG, '按钮-刷取次数拉满'), (
            '拉满模式应点击「^」按钮而非「+」'
        )
        assert state['farm_times_read'] >= 1, '拉满后应 OCR 复核次数'
        assert op._farm_rounds == 1, f'应恰好刷取 1 轮,实际 {op._farm_rounds}'
        assert op._farm_draws == 1, (
            f'拉满消耗记账应按读数(而非配置 -1),draws={op._farm_draws}'
        )

    def test_farm_times_plus_compensation(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """确认框次数现读低于目标:点「+」补差值到目标,恰好点差额次数
        (OCR 现读 + 补偿式设置;非零起点区分「点差额」与「盲点目标次」)。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
            {(_ASCEND, '标题-等级提升')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        state['farm_times_read'] = 1  # 现读 1,目标 3 → 应点「+」恰 2 次
        state['round'] = 1  # 直呼节点:场景定位到确认框在场轮(重入守卫需命中弹窗标题)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      farm_times_per_round=3)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _call_node(op, 'confirm_ticket_farm')

        assert result.is_success, f'补偿设置后应成功点确认,status={result.status}'
        plus_clicks = _count_clicks_in(clicks, test_context,
                                       _FAST_FARM_DIALOG, '按钮-刷取次数加')
        assert plus_clicks == 2, f'应恰好点「+」2 次,实际 {plus_clicks}'
        assert op._farm_draws == 3, (
            f'实数记账应为目标值,draws={op._farm_draws}'
        )
        assert op._farm_rounds == 1

    def test_confirm_farm_wait_rerun_guard(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """券确认刷取的 WAIT 重入幂等守卫:带 until 的点击返回 WAIT 时引擎会
        原样重跑本节点——重入轮必须按画面态分流,不得重跑次数设置与确认点击。

        结果框在场 = 刷取已完成(RESULT_OPEN,零点击);两弹窗都不在 = 刷取
        进行中(WAIT 慢询,零副作用);补充弹窗在场 = 券被拦(POWER_BLOCKED,
        回滚确认前计数)。"""
        # 用例1:结果框在场 → RESULT_OPEN 成功,无任何点击、不重复计数
        state = _install_script(
            monkeypatch, test_context,
            [{(_FAST_FARM_RESULT, '按钮-关闭刷取结果')}], level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        result = _call_node(op, 'confirm_ticket_farm')
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
        op2 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op2._init_watchdog()  # type: ignore[attr-defined]
        result2 = _call_node(op2, 'confirm_ticket_farm')
        assert result2.result == OperationRoundResultEnum.WAIT, (
            f'刷取进行中应 WAIT 等待结果框,result={result2.result}'
        )
        assert op2._farm_rounds == 0, '刷取进行中重入不得重复计数'
        assert not clicks2, f'刷取进行中重入不得有任何点击,clicks={clicks2}'

        # 用例3:开拓力补充弹窗在场(确认被拦,结果框永不出现) → 置判停标志、
        # 作废本轮次数记录(本轮未成交未记账,不动历史账),以 POWER_BLOCKED
        # 交返回分类原路清场
        state3 = _install_script(
            monkeypatch, test_context,
            [{('开拓力补充弹窗', '标题-开拓力补充弹窗')}], level=40)
        clicks3 = _record_controller_clicks(monkeypatch, test_context, state3)
        op3 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op3._init_watchdog()  # type: ignore[attr-defined]
        op3._farm_draws = 3      # 前轮已成交的历史账
        op3._farm_times_set = 3  # 本轮确认已设未成交
        result3 = _call_node(op3, 'confirm_ticket_farm')
        assert result3.is_success and result3.status == 'POWER_BLOCKED', (
            f'补充弹窗在场应以 POWER_BLOCKED 交返回分类清场,status={result3.status}'
        )
        assert op3._capped is True and op3._stop_status == 'POWER_CAPPED', (
            '守卫应置判停标志与 POWER_CAPPED 停因'
        )
        assert op3._farm_rounds == 0, '判停路径不得重复计数'
        assert op3._farm_draws == 3, (
            f'未成交不动历史账(3 保持 3,既不抹账也不出负数),实际 {op3._farm_draws}'
        )
        assert op3._farm_times_set == 0, '本轮次数记录应作废归零'
        assert not clicks3, f'判停路径不得有任何点击,clicks={clicks3}'

    def test_confirm_count_on_effective_click(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """券确认记账在确认点击生效后才发生:确认点击未生效的 WAIT 重入轮
        只重发确认(不重复设次数、不重复记账)——确认框在场重入若重复记账
        会虚报消耗,重跑次数设置会多点「+」。"""
        set_calls = {'n': 0}
        real_set = UpgradeCharacterOp._set_farm_times

        def _counting_set(op_self, target):
            set_calls['n'] += 1
            return real_set(op_self, target)

        def _fake_click_with_miss(op_self, screen, s_name, a_name, *args, **kwargs):
            state['find_clicks'].append((s_name, a_name))
            if (s_name, a_name) == (_FAST_FARM_DIALOG, '按钮-确认快速刷取') \
                    and len([c for c in state['find_clicks']
                             if c == (_FAST_FARM_DIALOG, '按钮-确认快速刷取')]) == 1:
                return op_self.round_wait(status=a_name, wait=2)  # 首点未生效
            test_context.controller.click(_rect_center(test_context, s_name, a_name))
            return op_self.round_success(status=a_name)

        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        state['round'] = 1  # 直呼节点:确认框在场轮
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      farm_times_per_round=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _fake_click_with_miss)
        monkeypatch.setattr(UpgradeCharacterOp, '_set_farm_times', _counting_set)
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                first = op.confirm_ticket_farm()
                second = op.confirm_ticket_farm()  # 模拟确认未生效的 WAIT 重入
        finally:
            reset_running_state(op.ctx, op)
        assert first.result == OperationRoundResultEnum.WAIT, (
            f'首点未生效应 WAIT,result={first.result}'
        )
        assert second.is_success, f'重发确认应生效,status={second.status}'
        assert op._farm_rounds == 1, (
            f'重入轮不得重复记账,rounds={op._farm_rounds}'
        )
        assert op._farm_draws == 1, f'重入轮不得重复记账,draws={op._farm_draws}'
        # 次数设置幂等:重入轮(_farm_times_set 非零)不得重跑 _set_farm_times
        assert set_calls['n'] == 1, (
            f'重入轮不得重复设次数,set 调用 {set_calls["n"]} 次'
        )

    def test_confirm_accounting_on_result_reentry(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """真时序记账回归:带 until 的 helper 一次调用只点击一次、until 验证
        在下一次调用开头——重入轮结果框探测先于 helper 命中,记账必须挂在
        RESULT_OPEN(结果框=领奖完成)而非仅 helper success,否则生产时序下
        记账分支不可达(预算失效+统计恒 0)。桩按真实 helper 时序仿真:
        确认点击恒返回 WAIT(until 未满足),重入轮由结果框守卫接管记账。"""

        def _timing_faithful_click(op_self, screen, s_name, a_name, *args, **kwargs):
            state['find_clicks'].append((s_name, a_name))
            if (s_name, a_name) == (_FAST_FARM_DIALOG, '按钮-确认快速刷取'):
                # 真实 helper 时序:点击发出,until(结果框)下轮开头才验证
                return op_self.round_wait(status=a_name, wait=2)
            test_context.controller.click(_rect_center(test_context, s_name, a_name))
            return op_self.round_success(status=a_name)

        scenes = [
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')},
            {(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗'),
             (_FAST_FARM_RESULT, '按钮-关闭刷取结果')},  # 重入轮:结果框已出现
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        state['round'] = 0  # 直呼节点:确认框在场轮(结果框未出现)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      farm_times_per_round=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _timing_faithful_click)
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                first = op.confirm_ticket_farm()
                state['round'] = 1  # 直呼节点手工推进场景轮(结果框本轮出现)
                second = op.confirm_ticket_farm()
        finally:
            reset_running_state(op.ctx, op)
        assert first.result == OperationRoundResultEnum.WAIT, (
            f'首调点击后 until 未满足应 WAIT,result={first.result}'
        )
        assert second.is_success and second.status == 'RESULT_OPEN', (
            f'重入轮结果框在场应 RESULT_OPEN,status={second.status}'
        )
        assert op._farm_rounds == 1 and op._farm_draws == 1, (
            f'结果框重入轮必须记账(否则预算失效+统计恒 0),'
            f'rounds={op._farm_rounds},draws={op._farm_draws}'
        )

    def test_capped_exit_reports_stop_status(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """判停收尾按 _stop_status 出状态:POWER_CAPPED 场景(开拓力不足守卫
        置位)下 ③ 回到详情页即以 POWER_CAPPED 结束,与材料判停的
        MATERIAL_CAPPED 可区分;并补读判停时未知的等级。"""
        state = _install_script(
            monkeypatch, test_context,
            [set(), {(_DETAIL, '按钮-属性详情')}], level=70)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        op._capped = True
        op._stop_status = 'POWER_CAPPED'
        op._capped_level = None  # 券确认守卫判停时不在养成界面,等级未知
        result = _call_node(op, 'upgrade_loop')
        assert result.is_success and result.status == 'POWER_CAPPED', (
            f'POWER_CAPPED 停因应原样透出,status={result.status}'
        )
        assert op._capped_level == 70, f'收尾应补读判停等级,得到 {op._capped_level}'

    def test_banner_count_edge_gated(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """横幅沿计数:关闭点击未生效的 WAIT 重入轮(横幅仍在场)不得重复
        计数——横幅计数 = 实际完成升级次数,重计会虚高。"""
        state = _install_script(
            monkeypatch, test_context,
            [set(), {(_ASCEND, '标题-升级结果')}, {(_ASCEND, '标题-升级结果')}],
            level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                op.upgrade_loop()
                op.upgrade_loop()  # 模拟关闭未生效的 WAIT 重入(横幅仍在场)
        finally:
            reset_running_state(op.ctx, op)
        assert op._banner_upgrade_count == 1, (
            f'重入轮不得重复计数,实际 {op._banner_upgrade_count}'
        )

    def test_banner_count_resets_after_disappear(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """横幅沿计数归位:横幅消失后再次出现按新横幅重新计数——沿计数门
        只在横幅持续在场的重入轮生效,不吞并新的执行(删掉归位行本测试红)。"""
        scenes = [
            set(),
            {(_ASCEND, '标题-升级结果')},
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 横幅消失,材料足再执行
            {(_ASCEND, '标题-升级结果')},                              # 新横幅再现
            {(_DETAIL, '按钮-属性详情')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                for _ in range(4):
                    op.upgrade_loop()
        finally:
            reset_running_state(op.ctx, op)
        assert op._banner_upgrade_count == 2, (
            f'消失后再现应重新计数,实际 {op._banner_upgrade_count}'
        )

    def test_farm_route_budget_exhausted_stops(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """刷取预算耗尽:灰底反复触发刷取,预算(10 次)耗尽判停 MATERIAL_CAPPED,
        且 _farm_rounds 恰好等于预算。"""
        # 场景 0=入口,1..10=每轮刷取循环,11=预算耗尽轮(返回箭头),12=详情收尾
        scenes: list[set[tuple[str, str]]] = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},
        ]
        scenes += [{(_ASCEND, '标题-等级提升'), (_FAST_FARM_DIALOG, '标题-快速刷取弹窗')}
                   for _ in range(10)]  # 轮1-10:持续缺料
        scenes.append({(_ASCEND, '标题-等级提升')})  # 轮11:预算耗尽判停
        scenes.append({(_DETAIL, '按钮-属性详情')})  # 轮12:详情收尾
        _install_script(monkeypatch, test_context, scenes, level=40)
        # 预算耗尽语义锁:显式传 10 轮(生产默认 1 轮拉满,见 docstring)
        op = _WatchedUpgradeCharacter(test_context, farm_rounds_max=10)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'刷取预算耗尽应判停收尾,status={result.status}'
        )
        assert op._farm_rounds == 10, f'刷取次数应恰为预算 10,实际 {op._farm_rounds}'

    def test_farm_dungeon_false_stops_without_farming(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """farm_dungeon=False(生产默认):灰底缺料不进刷取链,直接判停——
        「要不要刷副本」独立开关为零消耗默认路径的守卫。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},   # 入口轮
            {(_ASCEND, '标题-等级提升')},                           # 轮1:灰底判停
            {(_ASCEND, '标题-等级提升')},                           # 轮2:收尾途中
            {(_DETAIL, '按钮-属性详情')},                           # 轮3:回到详情
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'未授权刷副本应判停收尾,status={result.status}'
        )
        assert op._farm_rounds == 0, 'farm_dungeon=False 不应执行任何刷取'
        assert not any(a == _CHALLENGE for _, a in state['find_clicks']), (
            '未授权刷副本不应触碰挑战副本画面'
        )

    def test_farm_window_fail_stops_instead_of_spinning(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """快速刷取静默无反应(无可刷缺口,按钮白底可 OCR 但点击无效):
        helper 重试预算耗尽(is_fail)转 FARM_WINDOW_FAIL 回升级循环判停
        收尾——原样透传 WAIT 会无界自旋挂死一条龙。"""

        def _fake_fail_click(op_self, screen, s_name, a_name, *args, **kwargs):
            return op_self.round_fail(f'未找到 {a_name}')

        state = _install_script(monkeypatch, test_context, [set()], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _fake_fail_click)

        result = _call_node(op, 'open_farm_window')

        assert result.is_success and result.status == 'FARM_WINDOW_FAIL', (
            f'资源窗口打不开应以 FARM_WINDOW_FAIL 回循环判停,status={result.status}'
        )
        assert op._capped is True and op._stop_status == 'MATERIAL_CAPPED', (
            'FARM_WINDOW_FAIL 应置判停标志与材料停因'
        )

    def test_farm_window_spin_bounded(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """快速刷取静默无反应(点击假成功但窗口不开)的有界自旋:按钮白底
        常在可 OCR,helper 恒 WAIT 不计重试,原样透传会无限自旋挂死一条龙
        ——连等 4 轮超限转 FARM_WINDOW_FAIL 判停(现场留证由 save_screenshot
        承担,测试内桩掉)。"""

        def _fake_wait_click(op_self, screen, s_name, a_name, *args, **kwargs):
            state['find_clicks'].append((s_name, a_name))
            return op_self.round_wait(status=a_name, wait=1.5)

        state = _install_script(monkeypatch, test_context, [set()], level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _fake_wait_click)
        monkeypatch.setattr(UpgradeCharacterOp, 'save_screenshot',
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
        assert op._capped is True and op._stop_status == 'MATERIAL_CAPPED', (
            '连等超限判停应置材料停因'
        )

    def test_farm_window_fail_routes_back_to_loop(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """引擎级边路由回归:FARM_WINDOW_FAIL 必须经升级循环判停收尾。

        该状态的 @node_from 曾挂错源节点(返回养成界面)——无精确边时引擎
        兜底路由进「进入副本」,在养成画面无限盲点「进入」坐标挂死;节点级
        直呼测试测不出边挂错,必须走完整 execute 验证路由。"""

        def _fake_fail_farm_click(op_self, screen, s_name, a_name, *args, **kwargs):
            # 仅快速刷取钮点击失败(模拟静默无反应的重试耗尽),其余点击成功
            if (s_name, a_name) == (_ASCEND, '按钮-快速刷取'):
                return op_self.round_fail(f'未找到 {a_name}')
            test_context.controller.click(_rect_center(test_context, s_name, a_name))
            return op_self.round_success(status=a_name)

        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},  # 入口
            {(_ASCEND, '标题-等级提升')},                          # 轮1:灰底 → NEED_FARM → 打开资源窗口失败
            {(_DETAIL, '按钮-属性详情')},                          # 轮2:判停收尾(回详情页)
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _fake_fail_farm_click)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'FARM_WINDOW_FAIL 应回升级循环判停收尾,status={result.status},'
            f'round={state["round"]},trace={state.get("find_events")}'
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
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_and_click_area',
                            _fake_wait_click)
        monkeypatch.setattr(UpgradeCharacterOp, 'save_screenshot',
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

    def test_power_blocked_guards_stop_before_consuming(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """开拓力不足守卫:券确认/手动挑战两节点识别「开拓力补充弹窗」即置
        判停标志,以 POWER_BLOCKED 交返回分类原路清场(清场链与 POWER_CAPPED
        收尾由 back_to_ascend 取消用例与判停收尾用例覆盖)——守卫路径本身
        零点击、不重复计数。"""
        for node_name in ('confirm_ticket_farm', 'manual_fight'):
            state = _install_script(
                monkeypatch, test_context,
                [{('开拓力补充弹窗', '标题-开拓力补充弹窗')}], level=0)
            clicks = _record_controller_clicks(monkeypatch, test_context, state)
            op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
            op._init_watchdog()  # type: ignore[attr-defined]
            result = _call_node(op, node_name)
            assert result.is_success and result.status == 'POWER_BLOCKED', (
                f'{node_name} 补充弹窗在场应以 POWER_BLOCKED 清场,'
                f'status={result.status}'
            )
            assert op._capped is True and op._stop_status == 'POWER_CAPPED', (
                f'{node_name} 守卫应置判停标志与 POWER_CAPPED 停因'
            )
            assert op._farm_rounds == 0, f'{node_name} 判停路径不得重复计数'
            assert not clicks, f'{node_name} 守卫路径不得有任何点击,clicks={clicks}'

    def test_back_to_ascend_cancels_leftover_popups(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """返回养成界面清场:开拓力补充弹窗/选次数确认框残留 → 各点其取消
        重入分类(补充弹窗「确认」是星琼购开拓力,永不触碰)。"""
        # 用例1:开拓力补充弹窗在 → 点其取消,重入分类
        state = _install_script(
            monkeypatch, test_context,
            [{('开拓力补充弹窗', '标题-开拓力补充弹窗')}], level=0)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        result = _call_node(op, 'back_to_ascend')
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
            [{(_FAST_FARM_DIALOG, '标题-快速刷取弹窗')}], level=0)
        _record_controller_clicks(monkeypatch, test_context, state2)
        op2 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op2._init_watchdog()  # type: ignore[attr-defined]
        result2 = _call_node(op2, 'back_to_ascend')
        assert not result2.is_success \
            and '选次数确认框已取消' in str(result2.status), (
            f'确认框残留应点取消重入分类,status={result2.status}'
        )
        assert (_FAST_FARM_DIALOG, '按钮-取消') in state2['find_clicks'], (
            f'应点击确认框取消钮,find_clicks={state2["find_clicks"]}'
        )

    def test_back_to_ascend_closes_team_screen(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """编队画面清场(手动路线开拓力被拦取消补充弹窗后/编队残留的落点):
        队伍标题在场时点右上 X(与副本关闭钮同槽位)回副本画面再逐层回退
        ——无此分支会落进「未识别画面」空转耗尽节点预算。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_CHALLENGE, '队伍标题')}], level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _call_node(op, 'back_to_ascend')

        assert not result.is_success \
            and '编队画面已关' in str(result.status), (
            f'编队画面应点 X 回副本画面重入分类,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-关闭副本'), (
            f'应点击右上 X(与关闭副本同槽位),clicks={clicks}'
        )

    def test_ticket_route_stack_walk_layered(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """券路线返回栈逐层回退:结果框 → 资源窗口 → 副本 → 养成界面,每层
        点对应关闭控件,直至养成锚命中 FARMED——层级序漂移会在错误画面点
        关闭控件。"""
        scenes = [
            {(_FAST_FARM_RESULT, '按钮-关闭刷取结果')},
            {(_RESOURCE, '标题-培养资源窗口')},
            {(_CHALLENGE, '挑战按钮')},
            {(_ASCEND, '标题-等级提升')},
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True)
        op._init_watchdog()  # type: ignore[attr-defined]
        enter_running_state(op.ctx)
        try:
            with fast_sleep(op):
                r1 = op.back_to_ascend()
                state['round'] = 1  # 直呼节点手工推进场景轮(本节点无计轮锚)
                r2 = op.back_to_ascend()
                state['round'] = 2
                r3 = op.back_to_ascend()
                state['round'] = 3
                r4 = op.back_to_ascend()
        finally:
            reset_running_state(op.ctx, op)
        assert not r1.is_success and '刷取结果框已关' in str(r1.status)
        assert not r2.is_success and '资源窗口已关' in str(r2.status)
        assert not r3.is_success and '副本画面已关' in str(r3.status)
        assert r4.is_success and r4.status == 'FARMED', (
            f'逐层回退后应回养成界面,status={r4.status}'
        )
        assert state['find_clicks'] == [
            (_FAST_FARM_RESULT, '按钮-关闭刷取结果'),
            (_RESOURCE, '按钮-关闭资源窗口'),
            (_CHALLENGE, '按钮-关闭副本'),
        ], f'逐层关闭序列漂移:{state["find_clicks"]}'


class TestUpgradeCharacterManualRoute:
    """手动挑战路线:副本态前置、编队双锚、大世界返回与重走入口链。"""

    def test_manual_full_chain_returns_via_world_and_reenters(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """手动路线全链:灰底 → 资源窗口 → 副本(凝滞虚影态) → 挑战 →
        编队(双锚确认) → 战斗 → 结算退出 → 重建副本关闭 → 大世界 →
        BACK_TO_WORLD → 重走入口链(角色图标→重选角色→切详情TAB) →
        FARMED 重入升级循环升满判停。

        此路径若误按券路线的栈回退处理,流程会在大世界卡死。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},     # 入口
            {(_ASCEND, '标题-等级提升'), (_CHALLENGE, '标题-凝滞虚影')},  # 轮1:灰底;副本态=凝滞虚影
            {(_CHALLENGE, '队伍标题')},                              # 轮2:编队态(点挑战后)
            {(_BATTLE, '按钮-退出关卡')},                            # 轮3:战斗结算
            {(_CHALLENGE, '挑战按钮')},                              # 轮4:重建副本画面
            set(),                                                   # 轮5:大世界(返回分类判定)
            set(),                                                   # 轮6:角色详情(重走入口链重选/切页)
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},  # 轮7:回界面材料齐 → 执行
            {(_ASCEND, '标题-升级结果')},                            # 轮8:横幅
            {(_DETAIL, '按钮-属性详情')},                            # 轮9:判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        _FakeSubOp.executed = []
        clicks = _record_controller_clicks(
            monkeypatch, test_context, state,
            advance_round_on_squad_click=True,
            advance_round_on_challenge_click=True)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'手动刷取回大世界后应经入口链继续升满判停,status={result.status},'
            f'round={state["round"]},trace={state.get("find_events")},clicks={clicks}'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '挑战按钮'), (
            '副本态应点挑战按钮进编队'
        )
        assert _has_click_in(clicks, test_context, _CHALLENGE, '按钮-开始编队挑战'), (
            '编队态应点开始编队挑战'
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
        assert any(k.get('tab_name') == '详情' for k in _FakeSubOp.executed), (
            f'入口链应切回「详情」页签,executed={_FakeSubOp.executed}'
        )
        assert not _has_click_in(clicks, test_context,
                                 _FAST_FARM_DIALOG, '按钮-确认快速刷取'), (
            '手动路线不得走券确认分支'
        )
        assert op._farm_rounds == 1 and op._manual_fights == 1, (
            f'手动刷取应计 1 轮 1 场,rounds={op._farm_rounds},'
            f'fights={op._manual_fights}'
        )
        assert op._farm_draws == 0, (
            f'手动路线不耗券,draws 应为 0,实际 {op._farm_draws}'
        )

    def test_manual_fight_dual_anchor_blocks_dungeon_state(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """编队态双锚防线:挑战按钮 area 与编队「开始挑战」文本 LCS 互恰,
        副本态(副本类型标题在场)下即使队伍锚误命中也不得点开始编队挑战
        (连环误开战防线,光锥线同位实测事故)。"""
        state = _install_script(
            monkeypatch, test_context,
            [{(_CHALLENGE, '队伍标题'), (_CHALLENGE, '标题-凝滞虚影')}], level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _call_node(op, 'manual_fight')

        assert result.is_success and result.status == 'BATTLE_DONE', (
            f'副本态(标题在场)应交返回分类而非开战,status={result.status}'
        )
        assert not _has_click_in(clicks, test_context,
                                 _CHALLENGE, '按钮-开始编队挑战'), (
            f'副本态不得点开始编队挑战,clicks={clicks}'
        )

    def test_farm_in_dungeon_requires_dungeon_state(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """副本态前置三分:挑战按钮 area 与编队「开始挑战」文本 LCS 互恰,
        无副本类型标题时按画面态分流,任何形态都不得盲点挑战按钮——

        - 编队态(队伍标题在):交手动战斗节点点开始挑战;
        - 战斗/结算态(全锚不在):交手动战斗节点分类;
        - 未识别副本类型(挑战按钮在但副本标题读不到):计重试等重判
          (瞬时 OCR 失败可自愈;交手动分类会零消耗空转无限回环)。"""
        # 用例1:编队态 → 交手动分类
        state = _install_script(
            monkeypatch, test_context,
            [{(_CHALLENGE, '队伍标题')}], level=0)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]
        result = _call_node(op, 'farm_in_dungeon')
        assert result.is_success and result.status == 'MANUAL_FIGHT', (
            f'编队态应交手动分类点开始挑战,status={result.status}'
        )
        assert not _has_click_in(clicks, test_context, _CHALLENGE, '挑战按钮'), (
            f'编队态不得点挑战按钮,clicks={clicks}'
        )

        # 用例2:战斗/结算态(全锚不在) → 交手动分类
        _install_script(monkeypatch, test_context, [set()], level=0)
        op2 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                       use_fast_ticket=False)
        op2._init_watchdog()  # type: ignore[attr-defined]
        result2 = _call_node(op2, 'farm_in_dungeon')
        assert result2.is_success and result2.status == 'MANUAL_FIGHT', (
            f'战斗/结算态应交手动分类,status={result2.status}'
        )

        # 用例3:未识别副本类型(挑战按钮在、副本标题读不到) → 重试等重判
        state3 = _install_script(
            monkeypatch, test_context,
            [{(_CHALLENGE, '挑战按钮')}], level=0)
        clicks3 = _record_controller_clicks(monkeypatch, test_context, state3)
        op3 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                       use_fast_ticket=False)
        op3._init_watchdog()  # type: ignore[attr-defined]
        result3 = _call_node(op3, 'farm_in_dungeon')
        assert result3.result == OperationRoundResultEnum.RETRY, (
            f'未识别副本类型应重试等重判(瞬时 OCR 失败自愈),'
            f'result={result3.result},status={result3.status}'
        )
        assert not _has_click_in(clicks3, test_context, _CHALLENGE, '挑战按钮'), (
            f'未识别类型不得盲点挑战按钮,clicks={clicks3}'
        )

    def test_unknown_dungeon_type_fails_bounded(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未识别副本类型有界失败(引擎级):挑战按钮在但副本类型标题持续
        读不到(未建档类型/OCR 持续失败)时,手动路线不得零消耗空转——
        不计场的 BATTLE_DONE 会反复回环「关副本→大世界→重走入口→再开窗
        进本」形成无限循环;重试耗尽显式失败强制补档。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},      # 入口轮
            {(_ASCEND, '标题-等级提升'), (_CHALLENGE, '挑战按钮')},     # 轮1:灰底 → 刷取链 → 未识别副本画面
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=40)
        clicks = _record_controller_clicks(monkeypatch, test_context, state)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert not result.success and '未识别' in (result.status or ''), (
            f'未识别副本类型应重试耗尽有界失败,status={result.status}'
        )
        assert _count_clicks_in(clicks, test_context,
                                _RESOURCE, '按钮-进入副本') == 1, (
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
        帧分支——旧实现以 round_retry 计数,30 次预算约 90s 耗尽即战斗
        中途 FAIL(战场残留游戏内继续自打,污染后续入口判定)。新语义
        WAIT 慢询不计数,超时兜底交节点 timeout_seconds。战斗时长以
        「挑战按钮探测次数」计轮,40 轮后结算画面出现(旧实现必挂)。"""
        scenes = [
            {(_DETAIL, '按钮-属性详情'), (_DETAIL, '按钮-升级')},      # 入口轮
            {(_ASCEND, '标题-等级提升'), (_CHALLENGE, '标题-凝滞虚影')},  # 轮1:灰底;副本态=凝滞虚影
            {(_CHALLENGE, '队伍标题')},                                # 轮2:编队态(点挑战后)
            set(),                                                     # 轮3:战斗期(全锚 MISS,战斗时钟推进用)
            {(_BATTLE, '按钮-退出关卡')},                              # 轮4:战斗结算(战斗时钟到期后切换)
            {(_CHALLENGE, '挑战按钮')},                                # 轮5:重建副本画面
            set(),                                                     # 轮6:大世界
            set(),                                                     # 轮7:角色详情(重走入口链)
            {(_ASCEND, '标题-等级提升'), (_ASCEND, '按钮-快速升级')},   # 轮8:回界面材料齐 → 执行
            {(_ASCEND, '标题-升级结果')},                              # 轮9:横幅
            {(_DETAIL, '按钮-属性详情')},                              # 轮10:判满
        ]
        state = _install_script(monkeypatch, test_context, scenes, level=79)
        _FakeSubOp.executed = []
        clicks = _record_controller_clicks(
            monkeypatch, test_context, state,
            advance_round_on_squad_click=True,
            advance_round_on_challenge_click=True)
        # 战斗时钟:返回分类在战斗态每轮探测一次挑战按钮,计满 40 轮后把
        # 剧本切到结算轮(模拟整场战斗约 2 分钟 > 旧重试预算容忍上限)
        battle_clock = {'n': 0}
        installed_find = UpgradeCharacterOp.round_by_find_area

        def _battle_clock_find(self, screen, s_name, a_name, *args, **kwargs):
            if (s_name, a_name) == (_CHALLENGE, '挑战按钮') \
                    and state.get('screen_now') == _BATTLE:
                battle_clock['n'] += 1
                if battle_clock['n'] >= 40:
                    state['round'] = 4  # 切结算轮(退出关卡在 scene[4])
            return installed_find(self, screen, s_name, a_name, *args, **kwargs)

        monkeypatch.setattr(UpgradeCharacterOp, 'round_by_find_area',
                            _battle_clock_find)
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._init_watchdog()  # type: ignore[attr-defined]

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'长战斗(40 轮 > 旧 30 次重试预算)后应继续走完到满级,'
            f'status={result.status},battle_rounds={battle_clock["n"]},'
            f'round={state["round"]}'
        )
        assert op._manual_fights == 1 and op._farm_rounds == 1, (
            f'战斗期等待不得影响计场,fights={op._manual_fights},'
            f'rounds={op._farm_rounds}'
        )
        assert _has_click_in(clicks, test_context, _BATTLE, '按钮-退出关卡'), (
            '战斗结束应点退出关卡收口'
        )

    def test_reentry_identity_gate_requires_name(
        self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """重走入口链防升错:落在角色详情时有入口记名才重选(凭记名,
        不信页面显示——角色详情不记忆上次角色);无记名显式失败且不调用
        重选子 op。"""
        state = _install_script(monkeypatch, test_context, [set()], level=79)
        _FakeSubOp.executed = []
        _record_controller_clicks(monkeypatch, test_context, state)

        # 用例1:有记名 → 重选 + 切页 → FARMED
        op = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                      use_fast_ticket=False)
        op._char_name = '测试角色'
        state['screen_now'] = _DETAIL
        result = _call_node(op, 'reenter_from_world')
        assert result.is_success and result.status == 'FARMED', (
            f'有记名应重选角色接管,status={result.status}'
        )
        assert any(k.get('cn_name') == '测试角色' for k in _FakeSubOp.executed), (
            f'应凭入口记名重选,executed={_FakeSubOp.executed}'
        )

        # 用例2:无记名 → fail,不调用重选子 op
        _FakeSubOp.executed = []
        op2 = _WatchedUpgradeCharacter(test_context, farm_dungeon=True,
                                       use_fast_ticket=False)
        op2._char_name = None
        state['screen_now'] = _DETAIL
        result2 = _call_node(op2, 'reenter_from_world')
        assert not result2.is_success, '无记名应判停防升错'
        assert not _FakeSubOp.executed, (
            f'无记名不得调用重选子 op,executed={_FakeSubOp.executed}'
        )


class TestUpgradeCharacterParamValidation:

    def test_param_validation(self, test_context: SrTestContext) -> None:
        """参数校验:farm_times_per_round 仅正数或 -1;farm_rounds_max >= 1。
        默认策略锁:fill_generic 开、每轮拉满(-1)、预算 1 轮、券路线——
        通用材料最优先 + 刷取一轮拉满(材料共享库存,多余留他用)。"""
        op = UpgradeCharacterOp(test_context)
        assert op.fill_generic is True
        assert op.farm_dungeon is False
        assert op.use_fast_ticket is True
        assert op.farm_times_per_round == -1
        assert op.farm_rounds_max == 1
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeCharacterOp(test_context, farm_times_per_round=0)
        with pytest.raises(ValueError, match='farm_times_per_round'):
            UpgradeCharacterOp(test_context, farm_times_per_round=-2)
        with pytest.raises(ValueError, match='farm_rounds_max'):
            UpgradeCharacterOp(test_context, farm_rounds_max=0)
