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

对齐批增量锁面(docs/develop/sr_od/application/cultivation/changes/
upgrade-align-2/design.md):
- 事务式记账:确认点击不动账,结果框在场才 settle 落账(判据位=已设未
  记账;确认未生效重入轮跳过设次数只重发确认);
- 开拓力守卫:「开拓力补充弹窗」链探测首位识别,点取消原路清场后
  POWER_CAPPED 可恢复判停(确认钮=星琼红线,画面档无该 area);
- 补料优先级(负责人裁定:通用材料补全 → 券刷 → 手动战斗):缺料可合成
  形态授权补全时优先补全、不刷取。

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
            # 逐查询序(④b 删除后:快升 miss 直接落 ⑤⑤b⑦;r1 全 miss=过渡态
            # 计 1 轮点空白,r2 满级锚命中→MAX_LEVEL):
            # 入口开关(分类①) → r1(弹窗/满级/开关→分类②/快速升级/补全/合成/
            # 可提升全miss→点空白) → r2(弹窗/满级→分类③→MAX_LEVEL) →
            # 收尾(开关→关面板/开关miss→落MAX_LEVEL)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(),
             set(), {(_TRACE, '文本-已达最大等级')},
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
            # 逐查询序:入口开关 → r1(弹窗/满级miss/开关→分类→快升miss→
            # 补全钮→未授权判停) → 收尾(开关→关面板/开关miss→落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
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
        """材料不足灰态(快速刷取入口消失,升下一级缺口超出刷取/补全/合成
        覆盖)→ 前置判停。分流依据 = 快速刷取入口在场性(版式级差异)而非
        按钮带文本——灰态禁用文本与白底态文本 lcs 0.75,文本锚连续两档
        阈值踩线,不可靠(实机两次)。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序:入口开关 → r1/r2/r3 各 7 查询(弹窗/满级miss/开关HIT
            # [灰态面板仍在]/快升/补全/合成/可提升全miss,第3轮 buttonless=3
            # 判停) → 收尾(开关→关面板/开关miss→落账)。farm_dungeon=False:
            # ⑥ 快速刷取查询被 and 短路
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(),
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(),
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(),
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋', '天赋'], level=3)

        result = _run_op(op)

        assert result.success and result.status == 'MATERIAL_CAPPED'
        assert op._end_level == 3
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-材料合成'), (
            '灰态判停不得空点禁用的合成钮'
        )
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-通用材料补全')
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-快速刷取')
        assert state['level_reads'] == 1

    def test_synthesis_form_stops_without_farm(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """材料合成形态(双形态实做项):fill_generic 未授权 → 判停,不点
        补全/合成钮、不走券刷(合成形态券刷无收益——光锥线同款裁定)。

        轮次walk:入口{开关} → r1{开关+合成钮}(判停) → 收尾{开关}→{无}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context)
        _install_script(
            monkeypatch, test_context,
            # 逐查询序:入口开关 → r1(弹窗/满级miss/开关→分类→快升miss→
            # 补全miss→合成钮→未授权判停) → 收尾(开关→关面板/开关miss→
            # 落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '按钮-材料合成')},
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
        _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
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

    def test_dual_auth_prefills_generic_over_farm(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """补料优先级翻转锁(负责人裁定:通用材料补全 → 券刷 → 手动战斗,
        见 docs/develop/sr_od/application/cultivation/changes/
        upgrade-align-2/design.md §4):缺料可合成形态(「使用通用材料补全」
        钮在场)双授权(fill_generic=True + farm_dungeon=True)时必须优先
        补全——不转券刷路由、不点面板「快速刷取」、_farm_rounds 恒零;
        该组合旧行为走券刷,是本项唯一行为变化点。

        轮次walk(fill_generic=True):入口{开关} → r1(弹窗/满级/开关→分类→
        快升miss→补全钮→点补全钮) → r2(弹窗→点确认) → r3 遮罩期(全miss→
        盲点空白) → r4(弹窗/满级/开关→分类→快速升级→升级) → r5(弹窗miss/
        满级→分类→MAX_LEVEL) → 收尾{开关→关面板}/{开关miss→落账}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, fill_generic=True,
                                  farm_dungeon=True)
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             {(_TRACE, '标题-材料补全弹窗')},
             set(), set(), set(),
             set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '按钮-快速升级')},
             set(), {(_TRACE, '文本-已达最大等级')},
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋', '天赋'], level=4)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'双授权应走补全链升满,status={result.status},'
            f'find_events={state["find_events"]}'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '按钮-通用材料补全'), (
            '双授权 ⑤ 形态必须优先点通用材料补全'
        )
        assert _has_click_in(clicks, test_context, _TRACE, '按钮-确认材料补全'), (
            '补全链应走通到确认弹窗'
        )
        assert not _has_click_in(clicks, test_context, _TRACE, '按钮-快速刷取'), (
            '授权补全时不得转券刷(不点面板「快速刷取」开窗)'
        )
        assert op._farm_rounds == 0, '授权补全时零券刷轮'

class TestFarmTicketChain:
    """券刷新链:路由→开窗→券按钮→连刷设置→确认→收口回面板→升级。"""

    def test_farm_round_routes_through_chain(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """缺料+farm_dungeon 预算内 → 券刷链全走(开窗/券按钮/连刷设置/
        确认/关结果框/关窗口)→ 回面板 → 继续升级至满级;结果框轮 settle
        恰一次(_farm_rounds=1)。

        轮次walk(farm_times_per_round=-1 → 拉满钮+桩读数5;链内每轮首格 =
        守卫探测「开拓力补充弹窗」miss):
        入口{开关} → r1{开关+补全钮}(NEED_FARM) → 链r1{开关+toast miss}
        (点面板钮开窗) → 链r2{窗口+行锚}(点券钮) → 链r3{弹窗+确认钮}
        (拉满+确认) → 链r4{弹窗}(连刷中) → 链r5{结果框}(settle+关) →
        链r6{窗口}(关窗) → 链r7{开关}(回面板) → r2{开关+快速升级}(升级)
        → r3{满级锚}(MAX_LEVEL) → 收尾{开关}→{无}。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        state = _install_script(
            monkeypatch, test_context,
            # 逐查询序(farm_times_per_round=-1 → 拉满钮+桩读数5;find_and_click
            # 各消耗一格;链内每轮首格 = 守卫探测 miss):
            # 入口开关 → r1(弹窗/满级/开关→分类→快速升级miss→补全钮→NEED_FARM)
            # → 链(守卫/弹窗/结果框/窗口miss/开关→toast miss→点面板钮)
            # → 链(守卫/弹窗/结果框miss/窗口+行锚→点券钮)
            # → 链(守卫miss/弹窗+确认钮→拉满+确认)
            # → 链(守卫miss/弹窗命中/确认钮miss→连刷中)
            # → 链(守卫/弹窗miss/结果框→settle+关,controller 点击)
            # → 链(守卫/弹窗/结果框miss/窗口→关窗)
            # → 链(守卫/弹窗/结果框/窗口miss/开关→回面板)
            # → r2(弹窗/满级/开关→分类→快速升级→升级) → r3(弹窗miss/满级→MAX_LEVEL)
            # → 收尾(开关→关面板/开关miss→落MAX_LEVEL)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             set(), set(), set(), {(_RESOURCE_WINDOW := '培养资源窗口', '标题-培养资源窗口')},
             {(_RESOURCE_WINDOW, '行锚-本周可领取奖励次数')},
             set(), {(_FAST := '快速刷取弹窗', '标题-快速刷取弹窗')},
             {(_FAST, '按钮-确认快速刷取')},
             set(), {(_FAST, '标题-快速刷取弹窗')}, set(),
             set(), set(), {(_RES := '快速刷取结果弹窗', '按钮-关闭刷取结果')},
             set(), set(), set(), {(_RESOURCE_WINDOW, '标题-培养资源窗口')},
             set(),
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
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
        assert op._farm_rounds == 1, '结果框轮 settle 恰一次,_farm_rounds=1'
        assert op._farm_times_set == 0, '结果框轮 settle 落账后判据位清零'
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
        toast 探测仅链入口轮查询一次(窗口出现后门控复位不再探)。

        轮次walk 同 routes_through_chain(链内每轮首格 = 守卫探测 miss)。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        _fast, _res, _win = '快速刷取弹窗', '快速刷取结果弹窗', '培养资源窗口'
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             # 链r1(守卫/弹窗/结果框/窗口miss/开关→toast miss→点面板钮):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             # 链r2(守卫/弹窗/结果框miss/窗口+行锚→点券钮):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '行锚-本周可领取奖励次数')},
             # 链r3(守卫miss/弹窗+确认钮→拉满+确认):
             set(), {(_fast, '标题-快速刷取弹窗')},
             {(_fast, '按钮-确认快速刷取')},
             # 链r4(守卫miss/弹窗命中/确认钮miss→连刷中):
             set(), {(_fast, '标题-快速刷取弹窗')}, set(),
             # 链r5(守卫/弹窗miss/结果框→关,controller 点击):
             set(), set(), {(_res, '按钮-关闭刷取结果')},
             # 链r6(守卫/弹窗/结果框miss/窗口→关窗):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '按钮-关闭资源窗口')},
             # 链r7(守卫/弹窗/结果框/窗口miss/开关→回面板):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             # r2(弹窗/满级/开关→分类→快速升级→升级):
             set(), set(), {(_TRACE, '开关-简略描述')},
             {(_TRACE, '按钮-快速升级')},
             # r3(弹窗miss/满级→MAX_LEVEL):
             set(), {(_TRACE, '文本-已达最大等级')},
             # 收尾(开关→关面板/开关miss→落MAX_LEVEL):
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
            # 链内每轮首格 = 守卫探测「开拓力补充弹窗」miss。
            # 入口开关 → r1(弹窗/满级miss/开关→分类→快升miss/补全钮→NEED_FARM)
            # → 链r1(守卫/弹窗/结果框/窗口miss/开关→toast miss→点面板钮)
            # → 链r2(守卫/弹窗/结果框/窗口miss/开关→toast 命中→判停)
            # → 收尾(开关→关面板/开关miss→落MATERIAL_CAPPED)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
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
        op._farm_window_wait_rounds = 2
        monkeypatch.setattr(UpgradeTraceOp, 'save_screenshot',
                            lambda self, prefix='': '')
        state = _install_script(
            monkeypatch, test_context,
            # 链内每轮首格 = 守卫探测「开拓力补充弹窗」miss。
            # 入口开关 → r1(→NEED_FARM) → 链r1/r2/r3(守卫miss/弹窗/结果框/
            # 窗口miss/开关命中→点面板钮;计数 2 起 toast 探测被门控抑制,
            # 第 3 轮计数 4 触发封顶判停) → 收尾(开关→关面板/开关miss→落账)
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
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

    def test_confirm_miss_rerun_skips_set_and_settles_once(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """事务式记账(设计 upgrade-align-2 §2,对齐 char/LC 口径):确认
        点击未生效的重入轮凭判据位(非零=已设未记账)跳过设次数只重发
        确认(拉满钮恰点 1 次不重复);连刷慢询轮零点击零记账;账只在结果
       框轮 settle 恰一次(_farm_rounds=1 不因重发虚增)。

        轮次walk:入口{开关} → r1(→NEED_FARM) → 链r1(点面板钮) → 链r2
        (点券钮) → 链r3(拉满+确认#1) → 链r4(确认未生效,判据位非零→跳过
        设次数重发确认#2) → 链r5(确认钮miss→慢询,零副作用) → 链r6(结果
        框→settle+关) → 链r7(关窗) → 链r8(回面板) → r2(满级→MAX_LEVEL)
        → 收尾。"""
        clicks = _record_controller_clicks(monkeypatch, test_context)
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        _fast, _res, _win = '快速刷取弹窗', '快速刷取结果弹窗', '培养资源窗口'
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             # 链r1(守卫/弹窗/结果框/窗口miss/开关→toast miss→点面板钮):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             # 链r2(守卫/弹窗/结果框miss/窗口+行锚→点券钮):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '行锚-本周可领取奖励次数')},
             # 链r3(守卫miss/弹窗+确认钮→拉满+确认#1,判据位=5):
             set(), {(_fast, '标题-快速刷取弹窗')},
             {(_fast, '按钮-确认快速刷取')},
             # 链r4(守卫miss/弹窗+确认钮→判据位非零跳过设次数,重发确认#2):
             set(), {(_fast, '标题-快速刷取弹窗')},
             {(_fast, '按钮-确认快速刷取')},
             # 链r5(守卫miss/弹窗命中/确认钮miss→慢询,零副作用):
             set(), {(_fast, '标题-快速刷取弹窗')}, set(),
             # 链r6(守卫/弹窗miss/结果框→settle 恰一次+关,controller 点击):
             set(), set(), {(_res, '按钮-关闭刷取结果')},
             # 链r7(守卫/弹窗/结果框miss/窗口→关窗):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '按钮-关闭资源窗口')},
             # 链r8(守卫/弹窗/结果框/窗口miss/开关→回面板):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             # r2(弹窗miss/满级→分类→MAX_LEVEL):
             set(), {(_TRACE, '文本-已达最大等级')},
             # 收尾:
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋', '天赋'], level=5, farm_times_read=5)

        result = _run_op(op)

        assert result.success and result.status == 'MAX_LEVEL', (
            f'重发确认后应走通全链,status={result.status},'
            f'find_events={state["find_events"]}'
        )
        assert op._farm_rounds == 1, (
            '重发确认+慢询轮不得虚增账,结果框轮 settle 恰一次'
        )
        assert op._farm_times_set == 0, 'settle 后判据位清零'
        max_clicks = [c for c in clicks
                      if _has_click_in([c], test_context, _fast,
                                       '按钮-刷取次数拉满')]
        assert len(max_clicks) == 1, (
            f'重发轮判据位非零必须跳过设次数(拉满钮恰点 1 次),clicks={clicks}'
        )
        confirm_clicks = [c for c in clicks
                          if _has_click_in([c], test_context, _fast,
                                           '按钮-确认快速刷取')]
        assert len(confirm_clicks) == 2, (
            f'首点+重发各确认一次,clicks={clicks}'
        )

    def test_power_replenish_guard_clears_to_power_capped(
            self, test_context: SrTestContext,
            monkeypatch: pytest.MonkeyPatch) -> None:
        """开拓力守卫(设计 upgrade-align-2 §3):确认刷取被「开拓力补充
        弹窗」拦截 → 链探测首位命中,点「取消」(星琼红线:确认钮无 area
        永不触碰)、判据位归零(本轮未成交未记账,历史账零回滚)、置
        POWER_CAPPED 可恢复判停 → 清场模式只关不发起(资源窗口关窗→面板
        态读收尾等级转 CLOSE_PANEL,不回升级循环)→ 收尾落账终态透出。

        轮次walk:入口{开关} → r1(→NEED_FARM) → 链r1(点面板钮) → 链r2
        (点券钮) → 链r3(拉满+确认,判据位=5) → 链r4(守卫命中→点取消)
        → 链r5(资源窗口→关窗) → 链r6(面板态→读等级→CLOSE_PANEL) →
        收尾{开关→关面板}/{开关miss→落POWER_CAPPED}。"""
        op = _WatchedUpgradeTrace(test_context, farm_dungeon=True,
                                  farm_rounds_max=1)
        op._init_watchdog()  # type: ignore[attr-defined]
        _power, _win = '开拓力补充弹窗', '培养资源窗口'
        state = _install_script(
            monkeypatch, test_context,
            [{(_TRACE, '开关-简略描述')},
             set(), set(), {(_TRACE, '开关-简略描述')},
             set(), {(_TRACE, '按钮-通用材料补全')},
             # 链r1(守卫/弹窗/结果框/窗口miss/开关→toast miss→点面板钮):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             set(),
             # 链r2(守卫/弹窗/结果框miss/窗口+行锚→点券钮):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '行锚-本周可领取奖励次数')},
             # 链r3(守卫miss/弹窗+确认钮→拉满+确认,判据位=5):
             set(), {(_FAST := '快速刷取弹窗', '标题-快速刷取弹窗')},
             {(_FAST, '按钮-确认快速刷取')},
             # 链r4(守卫命中→FINDCLICK 取消,判据位归零+置判停):
             {(_power, '标题-开拓力补充弹窗')}, set(),
             # 链r5(守卫/弹窗/结果框miss/窗口→清场关窗):
             set(), set(), set(), {(_win, '标题-培养资源窗口')},
             {(_win, '按钮-关闭资源窗口')},
             # 链r6(守卫/弹窗/结果框/窗口miss/开关→清场面板态读等级→CLOSE_PANEL):
             set(), set(), set(), set(), {(_TRACE, '开关-简略描述')},
             # 收尾(开关命中→点关面板/开关miss→落POWER_CAPPED):
             {(_TRACE, '开关-简略描述')}, set()],
            categories=['天赋', '天赋'], level=5, farm_times_read=5)

        result = _run_op(op)

        assert result.success and result.status == 'POWER_CAPPED', (
            f'守卫判停终态应为 POWER_CAPPED,status={result.status},'
            f'find_events={state["find_events"]}'
        )
        assert op._capped is True
        assert op._farm_rounds == 0, (
            '拦截轮未成交未记账,_farm_rounds 零虚增零回滚'
        )
        assert op._farm_times_set == 0, (
            '守卫仅清判据位作废本轮次数记录(确认轮设到的 5 归零)'
        )
        assert op._end_level == 5, '清场面板态应读收尾等级一次(桩值 5)'
        assert state['level_reads'] == 1, '判停等级应恰好读取一次'
        replenish_clicks = [e for e in state['find_clicks']
                            if e[0] == _power]
        assert replenish_clicks == [(_power, '按钮-取消')], (
            f'补充弹窗画面只允许点「取消」(星琼红线:确认钮永不触碰),'
            f'find_clicks={state["find_clicks"]}'
        )
