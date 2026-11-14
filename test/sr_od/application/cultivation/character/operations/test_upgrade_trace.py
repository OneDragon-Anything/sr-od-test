"""UpgradeTraceOp(行迹面板升级,面板态契约)流程测试。

测试层级声明:桩识别层的单元式流程测试——monkeypatch 掉
``round_by_find_area`` / ``round_by_find_and_click_area``(按剧本逐查询构造
round 结果)与面板读数辅助,驱动 op 跑完整 ``execute()`` 节点图,锁
「帧态 → 分支判定 → 动作 → 状态机流转」。不走真帧 + 真识别的理由:各分支
的画面证据全是**同屏面板态**(满级锚/补全与合成按钮/分类读区/灰字锚,见
assets/game_data/screen_info/character_traces.yml「角色-行迹」screen),
识别类输入禁止合成(sr-od-test/README.md「识别类测试的图片输入」);识别层
本身的正确性归画面建档流程与实机 run_operation 验证。

锁面 = 新契约(docs/develop/sr_od/application/cultivation/changes/
upgrade-ops-adaptation/details/trace-rework.md):
- 起跑闸:面板态双锚(简略描述开关 + 分类读区==target),两态细分;
- 升级循环:补全确认弹窗双形态 / 满级+分类校验(失配 fail 交 agent)/
  按钮三态 / 券刷路由(预算内) / 全缺判停;
- 券刷链:面板→资源窗口→券按钮(行锚+按钮双锚)→弹窗连刷设置→确认→
  关结果框→关窗口→回面板,状态机以 _farm_times_set 分流;链入口面板钮
  开窗(P0:无人点钮=NEED_FARM↔回面板乒乓)/无可刷缺口 toast 正判(前
  两轮门控探测)/连点封顶漏检兜底;
- 收尾关面板:一切出口必经,_final_status 携带终态,连等封顶。

判据同步声明(landing 3.3):旧契约剧本(树态起点/open_panel 节点/点击区-节点-*/
auto_farm 参数/「升满当前上限」独立出口)随面板态重构整体失配,本文件按新
契约全量改写;level_reads 语义 = 判停读取一次(收尾读数为新增的
独立一次,断言面见各用例)。
"""


import pytest
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from one_dragon.base.operation.operation_base import OperationResult
from sr_od.application.cultivation.character.operations.upgrade_trace import (
    UpgradeTraceOp,
)

_TRACE: str = '角色-行迹'

# 查询响应集类型别名:(screen, area) 命中表;空集 = 全 MISS
_SCENE = set[tuple[str, str]]


class _WatchedUpgradeTrace(WatchdogOperationMixin, UpgradeTraceOp):
    """带看门狗的被测 op(剧本耗尽时收拢为有界失败,防测试自身死循环)。"""

    watchdog_max_rounds: int = 60

    def __init__(self, ctx: SrTestContext, target: str = '天赋',
                 fill_generic: bool = False, farm_dungeon: bool = False,
                 farm_rounds_max: int = 1) -> None:
        """真实构造路径(含 target/farm 参数校验);测试无游戏窗口,
        关掉 execute 期的窗口前置链读取。"""
        UpgradeTraceOp.__init__(self, ctx, target=target,
                                fill_generic=fill_generic,
                                farm_dungeon=farm_dungeon,
                                farm_rounds_max=farm_rounds_max)
        self.need_check_game_win = False  # execute 期才读,实例属性即可关掉


def _install_script(
    monkeypatch: pytest.MonkeyPatch,
    ctx: SrTestContext,
    scenes: list[_SCENE],
    categories: list[str],
    level: int,
    farm_times_read: int = 1,
) -> dict:
    """桩识别层并装记录器(逐查询出剧本,队列耗尽即抛错防静默转绿)。

    - ``scenes``:按 find_area 查询次序逐个弹出命中集((screen, area) 表),
      不在命中集的查询一律视为未命中;耗尽抛 AssertionError 让测试变红。
    - ``categories``:``_read_panel_category`` 按调用次序弹出(分类校验桩)。
    - ``level``:``_read_panel_level`` 桩返回值;读取次数记入返回值供断言。
    - ``farm_times_read``:``_read_farm_times`` 桩返回值(券刷连刷次数设置)。
    返回 ``{'find_events', 'find_clicks', 'level_reads'}``。"""
    state: dict = {'level_reads': 0, 'find_events': [], 'find_clicks': []}
    queue = list(scenes)

    def _fake_find_area(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        if not queue:
            raise AssertionError(f'剧本耗尽:查询 ({s_name}, {a_name})')
        scene = queue.pop(0)
        hit = (s_name, a_name) in scene
        print(f'[POP#{len(state["find_events"])} ({a_name}) '
              f'-> {"HIT" if hit else "MISS"}]')
        return self.round_success(status=a_name) if hit \
            else self.round_wait(status=f'未找到 {a_name}')

    def _fake_find_and_click(self, screen, s_name, a_name, *args, **kwargs):
        state['find_events'].append((s_name, a_name))
        state['find_clicks'].append((s_name, a_name))
        if not queue:
            raise AssertionError(f'剧本耗尽:find_and_click ({s_name}, {a_name})')
        queue.pop(0)
        return self.round_success(status=a_name)

    def _fake_category(self) -> str | None:
        return categories.pop(0) if categories else None

    def _fake_level(self) -> int | None:
        state['level_reads'] += 1
        return level

    def _fake_farm_times(self) -> int | None:
        return farm_times_read

    monkeypatch.setattr(UpgradeTraceOp, 'round_by_find_area', _fake_find_area)
    monkeypatch.setattr(UpgradeTraceOp, 'round_by_find_and_click_area',
                        _fake_find_and_click)
    monkeypatch.setattr(UpgradeTraceOp, '_read_panel_category', _fake_category)
    monkeypatch.setattr(UpgradeTraceOp, '_read_panel_level', _fake_level)
    monkeypatch.setattr(UpgradeTraceOp, '_read_farm_times', _fake_farm_times)
    return state


def _record_controller_clicks(
    monkeypatch: pytest.MonkeyPatch, ctx: SrTestContext,
) -> list[tuple[int, int]]:
    """包装 controller.click 记录点击坐标(op 直点全部经 controller)。"""
    clicks: list[tuple[int, int]] = []
    real_click = ctx.controller.click

    def _recording_click(pos=None, press_time: float = 0, pc_alt: bool = False,
                         gamepad_key: str | None = None) -> bool:
        if pos is not None:
            clicks.append((int(pos.x), int(pos.y)))
        return real_click(pos, press_time=press_time, pc_alt=pc_alt,
                          gamepad_key=gamepad_key)

    monkeypatch.setattr(ctx.controller, 'click', _recording_click)
    return clicks


def _has_click_in(
    clicks: list[tuple[int, int]], ctx: SrTestContext,
    screen_name: str, area_name: str,
) -> bool:
    """是否有点击落在建档区 pc_rect 内(坐标单一真相源 = screen_info)。"""
    area = ctx.screen_loader.get_area(screen_name, area_name)
    rect = area.pc_rect
    return any(
        rect.x1 <= x <= rect.x2 and rect.y1 <= y <= rect.y2 for x, y in clicks
    )


def _run_op(op: UpgradeTraceOp) -> OperationResult:
    """运行态前置复位 + fast_sleep 跑完整 execute(跳过真机等待)。"""
    enter_running_state(op.ctx)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(op.ctx, op)


class TestConstructorValidation:
    """构造校验:target 非空等值语义、farm 参数边界(新契约)。"""

    def test_empty_target_rejected(self, test_context: SrTestContext) -> None:
        with pytest.raises(ValueError):
            UpgradeTraceOp(test_context, target='  ')

    def test_farm_params_boundary(self, test_context: SrTestContext) -> None:
        with pytest.raises(ValueError):
            UpgradeTraceOp(test_context, target='天赋', farm_times_per_round=0)
        with pytest.raises(ValueError):
            UpgradeTraceOp(test_context, target='天赋', farm_rounds_max=0)


class TestEntryGate:
    """起跑闸:面板态双锚两态细分(零消耗)。"""

    def test_not_panel_fails_direct(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """开关不在场(真无面板/未知态)→ 直落 fail,不经收尾、零点击。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(monkeypatch, test_context, [set()],
                                categories=[], level=0)

        result = _run_op(op)

        assert not result.success
        assert '不在面板态' in (result.status or '')
        assert clicks == [], '未知态直落不得点击'
        assert state['level_reads'] == 0

    def test_category_mismatch_closes_panel_then_fails(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """开关在场但分类不符(面板开着别的技能)→ 经收尾关面板回树态后
        fail(树态契约保持,不留面板态破口)。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')}, {(_TRACE, '开关-简略描述')}, set()],
            categories=['战技'], level=0)

        result = _run_op(op)

        assert result.success
        assert result.status == '不在目标技能面板'
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-关面板空白'), (
            f'分类不符应经收尾关面板回树态,clicks={clicks}'
        )


class TestUpgradeLoop:
    """升级循环分支(满级/判停两形态/合成形态)。"""

    def test_max_level_closes_panel_and_succeeds(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """满级锚+分类相符 → MAX_LEVEL 经收尾关面板;判停等级零读取。

        轮次walk:入口{开关} → r1{开关}(全miss→点空白) → r2{满级锚}
        → 收尾{开关}→{无}(面板关)。categories 弹序 = 入口/r1③/r2①。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序(farm_dungeon=False:⑥ 券刷钮查询被 and 短路,不入剧本):
            # 入口开关(分类①) → r1(弹窗/满级/开关→分类②/快速升级/补全/合成/
            # 可提升全miss→点空白) → r2(弹窗/满级→分类③→MAX_LEVEL) →
            # 收尾(开关→关面板/开关miss→落MAX_LEVEL)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(),
             set(), set(), {(_TRACE, '文本-已达最大等级')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋'], level=0)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL'
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-关面板空白')
        assert state['level_reads'] == 0, '满级路径不应触发判停等级读取'

    def test_material_capped_without_authorization(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """缺料且 farm_dungeon/fill_generic 均未授权 → MATERIAL_CAPPED 判停
        经收尾关面板;不点升级钮;判停等级恰好读取一次。

        轮次walk:入口{开关} → r1{开关+补全钮}(判停) → 收尾{开关}→{无}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序:入口开关 → r1(弹窗/满级miss/开关→分类→补全钮→判停)
            # → 收尾(开关→关面板/开关miss→落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=6)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED'
        assert op._end_level == 6, '判停应捕获面板等级供报告(桩值 6)'
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-快速升级')
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-关面板空白')
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'

    def test_insufficient_material_gray_stops_immediately(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """材料不足灰态(按钮带禁用文本,升下一级缺口超出补全/合成覆盖)→
        前置判停,不误入合成分支空点禁用钮(其四字文本与「材料合成」lcs
        恰好 0.5 踩线,识别阈值已收紧,此处锁前置判停行为)。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序:入口开关 → r1(弹窗/满级miss/开关→分类→快升miss→
            # 材料不足→判停) → 收尾(开关→关面板/开关miss→落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '文本-材料不足')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=3)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED'
        assert op._end_level == 3
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-材料合成'), (
            '灰态判停不得空点禁用的合成钮'
        )
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-通用材料补全')
        assert state['level_reads'] == 1

    def test_synthesis_form_stops_without_farm(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """材料合成形态(双形态实做项):fill_generic 未授权 → 判停,不点
        补全/合成钮、不走券刷(合成形态券刷无收益——光锥线同款裁定)。

        轮次walk:入口{开关} → r1{开关+合成钮}(判停) → 收尾{开关}→{无}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序:入口开关 → r1(弹窗/满级miss/开关→分类→合成钮→判停)
            # → 收尾(开关→关面板/开关miss→落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), {(_TRACE, '按钮-材料合成')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=7)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED'
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-材料合成')
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-通用材料补全')
    def test_feedback_banner_recovered_then_max_level(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """升级反馈遮罩期实机场景:补全确认后游戏弹全屏横幅/特效(遮罩期
        OCR 全盲,遮罩版式随技能描述长度浮动不可建档)——盲点安全域空白
        直到面板锚回归,继续升满;不误判失配;收尾盲点收敛落账。

        轮次walk(fill_generic=True):入口{开关} → r1(弹窗/满级/开关→分类→
        快升miss→补全钮→点补全钮) → r2(弹窗→点确认) → r3 遮罩期(弹窗/满级/
        开关miss→盲点空白) → r4(弹窗/满级/开关→分类→快速升级→升级) →
        r5(弹窗/满级→分类→MAX_LEVEL) → 收尾{开关→关面板}/{开关miss→盲点}
        /{开关miss→落账}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, fill_generic=True)
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             {(_TRACE, '标题-材料补全弹窗')},
             set(), set(), set(),
             set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '按钮-快速升级')},
             set(), {(_TRACE, '文本-已达最大等级')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋', '天赋'], level=4)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL'
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-关面板空白'), (
            '反馈期与收尾应经安全域空白关遮罩/关面板'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '按钮-确认材料补全')

    def test_feedback_persistent_miss_fails_as_mismatch(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """面板锚连续 6 轮 miss 且盲点无效(真画面异动,非遮罩期)→ 盲点封顶
        判「不在目标技能面板」经收尾落账,不无限点击。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 入口{开关} → r1-r6 连续六轮(弹窗/满级/开关)全 miss(每轮盲点
            # 空白,第 6 轮 feedback=6 触发封顶) → 收尾(开关miss→落账)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), set(),
             set(), set(), set(),
             set(), set(), set(),
             set(), set(), set(),
             set(), set(), set(),
             set(), set(), set(),
             set()],
            categories=['天赋'], level=5)

        result = _run_op(op)

        assert result.success and result.status == '不在目标技能面板', (
            f'events={state["find_events"]}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '点击区-关面板空白'), (
            '遮罩期与收尾按负责人方案盲点安全域空白'
        )

class TestFarmTicketChain:
    """券刷新链:路由→开窗→券按钮→连刷设置→确认→收口回面板→升级。"""

    def test_farm_round_routes_through_chain(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """缺料+farm_dungeon 预算内 → 券刷链全走(开窗/券按钮/连刷设置/
        确认/关结果框/关窗口)→ 回面板 → 继续升级至满级;_farm_rounds=1。

        轮次walk(farm_times_per_round=-1 → 拉满钮+桩读数5):
        入口{开关} → r1{开关+补全钮}(NEED_FARM) → 链r1{窗口+行锚}(点券钮)
        → 链r2{弹窗+确认钮}(拉满+确认) → 链r3{弹窗}(连刷中) → 链r4{结果框}
        → 链r5{窗口}(关窗) → 链r6{开关}(回面板) → r2{开关+快速升级}(升级)
        → r3{满级锚}(MAX_LEVEL) → 收尾{开关}→{无}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序(farm_times_per_round=-1 → 拉满钮+桩读数5;find_and_click
            # 各消耗一格):
            # 入口开关 → r1(弹窗/满级/开关→分类→快速升级miss→补全钮→NEED_FARM)
            # → 链(弹窗miss/结果框miss/窗口+行锚→点券钮) → 链(弹窗+确认钮→拉满+确认)
            # → 链(弹窗+确认钮miss→连刷中) → 链(弹窗miss/结果框→关,controller 点击)
            # → 链(弹窗/结果框miss/窗口→关窗) → 链(弹窗/结果框/窗口miss/开关→回面板)
            # → r2(弹窗/满级/开关→分类→快速升级→升级) → r3(弹窗/满级→MAX_LEVEL)
            # → 收尾(开关→关面板/开关miss→落MAX_LEVEL)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(),
             {(_RESOURCE_WINDOW := '培养资源窗口', '标题-培养资源窗口')},
             {(_RESOURCE_WINDOW, '行锚-本周可领取奖励次数')},
             {(_FAST := '快速刷取弹窗', '标题-快速刷取弹窗')},
             {(_FAST, '按钮-确认快速刷取')},
             {(_FAST, '标题-快速刷取弹窗')}, set(),
             set(), {('快速刷取结果弹窗', '按钮-关闭刷取结果')},
             set(), set(), {(_RESOURCE_WINDOW, '标题-培养资源窗口')},
             set(),
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '按钮-快速升级')},
             set(), {(_TRACE, '文本-已达最大等级')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋', '天赋'], level=5,
            farm_times_read=5)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'券刷链回面板后应继续升满,status={result.status}'
        )
        assert op._farm_rounds == 1, '券刷确认一轮后 _farm_rounds=1'
        assert op._farm_times_set == 0, '确认后记账值消费清零(实际值在确认轮日志)'
        assert _has_click_in(clicks, test_context, _RESOURCE_WINDOW,
                             '按钮-花萼行券按钮'), '资源窗口应点花萼行券按钮'
        assert not _has_click_in(clicks, test_context, _RESOURCE_WINDOW,
                                 '按钮-进入副本'), '禁止误点「进入」副本(设计外链路)'
        assert _has_click_in(clicks, test_context, '快速刷取结果弹窗',
                             '按钮-关闭刷取结果'), '结果框应经 controller 点击关闭'
        assert ('培养资源窗口', '按钮-关闭资源窗口') in state['find_clicks']

    def test_farm_chain_clicks_panel_button_and_farm_completes(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """P0 回归锁(面板钮开窗):券刷链入口窗未开时必须由链内点击面板
        「快速刷取」开窗——旧实现面板态只回交升级循环,无人点钮,NEED_FARM
        ↔ 回面板无限乒乓(双方 SUCCESS 重试计数永不累积)。全链走通到满级,
        toast 探测仅链入口轮查询一次(窗口出现后门控复位不再探)。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        _fast, _res, _win = '快速刷取弹窗', '快速刷取结果弹窗', '培养资源窗口'
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '行锚-本周可领取奖励次数')},
             {(_fast, '标题-快速刷取弹窗')},
             {(_fast, '按钮-确认快速刷取')},
             {(_fast, '标题-快速刷取弹窗')}, set(),
             set(), {(_res, '按钮-关闭刷取结果')},
             set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '按钮-关闭资源窗口')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '按钮-快速升级')},
             set(), {(_TRACE, '文本-已达最大等级')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋', '天赋'], level=5, farm_times_read=5)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'链内点面板钮开窗后应走通全链,status={result.status}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '按钮-快速刷取'), (
            '券刷链入口必须点击面板「快速刷取」开窗(P0:无人点钮=乒乓挂死)'
        )
        assert op._farm_rounds == 1
        toast_queries = [e for e in state['find_events']
                         if e == (_TRACE, '提示-无可刷缺口')]
        assert len(toast_queries) == 1, (
            f'toast 探测应仅链入口轮一次,find_events={state["find_events"]}'
        )

    def test_farm_chain_toast_stops_immediately(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """无可刷缺口 toast 正判:链入口点击被拒 → 重入轮(计数 1,帧落
        toast 窗口)探测命中 → MATERIAL_CAPPED 判停收口,面板钮恰点一次
        (命中后不再连点);判停等级恰好读取一次。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        monkeypatch.setattr(UpgradeTraceOp, 'save_screenshot',
                            lambda self, prefix='': '')
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '提示-无可刷缺口')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=5)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'toast 命中应即判停收口,status={result.status},'
            f'find_events={state["find_events"]},clicks={clicks}'
        )
        assert op._end_level == 5
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'
        panel_clicks = [c for c in clicks
                        if _has_click_in([c], test_context, _TRACE,
                                         '按钮-快速刷取')]
        assert len(panel_clicks) == 1, (
            f'命中 toast 后不得再连点,clicks={clicks}'
        )
        toast_queries = [e for e in state['find_events']
                         if e == (_TRACE, '提示-无可刷缺口')]
        assert len(toast_queries) == 2, (
            f'漏检轮+重入轮各探一次,find_events={state["find_events"]}'
        )

    def test_farm_chain_toast_probe_gated_and_click_capped(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """探测门(计数 ≥2 抑制)+连点封顶:计数置 2 起 toast 查询不发起
        (慢开窗场景冗余点击被拒的 toast 不得误读);连点 4 次窗仍未开 =
        漏检兜底封顶判停,不再无限连点。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        op._panel_farm_click_rounds = 2
        monkeypatch.setattr(UpgradeTraceOp, 'save_screenshot',
                            lambda self, prefix='': '')
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=5)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED', (
            f'连点封顶应判停收口,status={result.status}'
        )
        assert (_TRACE, '提示-无可刷缺口') not in state['find_events'], (
            '计数 ≥2 后不得发起 toast 探测查询'
        )
        panel_clicks = [c for c in clicks
                        if _has_click_in([c], test_context, _TRACE,
                                         '按钮-快速刷取')]
        assert len(panel_clicks) == 2, (
            f'计数 2 起应再点 2 次到封顶,实际 {len(panel_clicks)},clicks={clicks}'
        )
        assert op._end_level == 5
