"""CW 入口/退局流测试:入口 smoke + ESC-4 落地审条件 F1 发射锁 + 防伪绿路径。

覆盖面(四类承重件在本文件的对位):
- 入口 smoke:传送已落地场景入口分流到大厅(enter 修复回归,18:29 事故);
- 防伪绿:F 分支必须真按交互键(修复前 AttributeError 被吞成 retry 也能假绿);
- F1 发射锁①:cw_entry_exit.py 源级零 ESC 发射墓碑(红 = ESC 回潮);
- overlay 分支出口语义:retry 化(验证废除批 K1,预算归节点,无自带上界);
- 建档锚:门形「按钮-退出对局」中心 (61,63)±2 + goto 转场边(防建档漂移)。

来源:本文件 = test_cw_enter_flow.py(git mv)+ test_cw_entry_exit_esc_free.py
三锁并入(2026-09-09 套件重建批 A,#1)。其余历史锁已退役(git 可复活)。
出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览
docs/develop/currency_war/strategy/README.md)。
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from one_dragon.base.operation.operation_base import OperationResult
from one_dragon.base.operation.operation_round_result import (
    OperationRoundResultEnum,
)
from sr_od.application.currency_war import cw_screen_state
from sr_od.application.currency_war.operations.cw_entry import cw_entry_enter
from sr_od.application.currency_war.operations.cw_entry.cw_entry_enter import (
    CwEntryEnter,
)
from sr_od.application.currency_war.operations.cw_entry.cw_entry_exit import (
    CwEntryExit,
)
from test.conftest import SrTestContext
from test.harness.fixture_controller import (
    FixtureController,
    WatchdogOperationMixin,
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

# 主仓根(src/ 所在):yml/源码扫描锚定,不依赖 pytest 运行 CWD
_MAIN_REPO = Path(__file__).resolve().parents[5]


class _WatchedCwEntryEnter(WatchdogOperationMixin, CwEntryEnter):
    """带看门狗的 CwEntryEnter(防 WAIT 段死循环)。"""


class _FakeGuideStepOp:
    """打开指南 / 选择 TAB 的替身:直接成功(本测试聚焦「前往参与」节点分流)。"""

    def __init__(self, *args, **kwargs) -> None:  # 与真 op 构造签名解耦(ctx / ctx+tab)
        pass

    def execute(self) -> OperationResult:
        return OperationResult(success=True, status='mock-成功')


@pytest.fixture()
def fixture_controller(
    test_context: SrTestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FixtureController:
    ctrl = FixtureController(
        ctx=test_context,
        standard_width=test_context.project_config.screen_standard_width,
        standard_height=test_context.project_config.screen_standard_height,
    )
    monkeypatch.setattr(test_context, 'controller', ctrl)
    # 指南两步替身(真实 GuideOpen/GuideChooseTab 需要大世界导航链 fixture,超出本测试焦点)
    monkeypatch.setattr(cw_entry_enter, 'GuideOpen', _FakeGuideStepOp)
    monkeypatch.setattr(cw_entry_enter, 'GuideChooseTab', _FakeGuideStepOp)
    return ctrl


def test_enter_recovers_when_transport_already_done(
    test_context: SrTestContext,
    fixture_controller: FixtureController,
) -> None:
    """传送已落地场景:「前往参与」按钮不在 → 不判死,分流到 wait_lobby 按F进大厅。"""
    phases = [
        {  # 大世界普通:打开指南/选TAB(替身成功)两轮后推进
            'frame': ('大世界', '普通'),
            'exit': ('on_polls', 2),
        },
        {  # 朝露公馆入口(已传送):无「前往参与」→ 修复点:交 wait_lobby → F 分支按 F
            'frame': ('大世界', '朝露公馆入口'),
            'exit': ('on_polls', 4),
        },
        {  # 大厅:terminal(wait_lobby 命中「标识-创业指南」→ op 成功)
            'frame': ('货币战争-大厅', 'lobby'),
        },
    ]
    for screen_name, state in (p['frame'] for p in phases):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')

    fixture_controller.set_phases(phases)
    op = _WatchedCwEntryEnter(test_context)
    op._init_watchdog()  # type: ignore[attr-defined]

    enter_running_state(test_context)
    try:
        with fast_sleep():
            result = op.execute()
    finally:
        reset_running_state(test_context, op)

    assert result.success, (
        f'传送已落地场景应恢复到达大厅而非判死「找不到 前往参与」:'
        f'status={result.status};phase_idx={fixture_controller.phase_idx}'
    )
    assert fixture_controller.phase_idx == len(phases) - 1, (
        f'剧本应推进到末 phase(大厅):phase_idx={fixture_controller.phase_idx}'
    )
    # F 分支真按了 F(防伪绿:修复前 controller.btn_tap 缺失 → AttributeError 被
    # 框架吞成 round_retry,靠异常重试的 poll 副作用推进剧本也能 PASS,F 从未被按)
    assert test_context.game_config.key_interact in fixture_controller.recorded_btn_taps, (
        '朝露公馆入口应按交互键 F 进大厅,但 recorded_btn_taps 里没有:'
        f'{fixture_controller.recorded_btn_taps}'
    )


# ==================== ESC-4 落地审条件 F1 三锁(自 test_cw_entry_exit_esc_free.py 并入) ====================

# ESC 发射形态(全文扫描,含大小写变体):
# - 引号包住的 esc 字面量:btn_tap('esc') / key_tap("ESC") / 键名映射 'esc'
# - .esc 属性/枚举访问(controller.esc(...) / Key.esc)
# 注释与文案里的裸「ESC」叙述(如「零 ESC」「ESC 已禁用」)不是发射,不入模式;
# 全文扫描不剔注释 = 墓碑从宽(引用旧 ESC 写法的注释也该被看见再删)。
_ESC_TOMBSTONE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"['\"]esc['\"]", re.IGNORECASE),
    re.compile(r'\.esc\b', re.IGNORECASE),
)


def test_entry_exit_source_has_zero_esc_emission() -> None:
    """源级墓碑锁:cw_entry_exit.py 全文零 ESC 发射形态,红 = ESC 回潮。

    出处:ESC 清零批(2026-09-08)把备战/overlay 两处 ESC 换建档点击
    (替代依据见该文件头与各分支注释;ESC 禁令 = runtime-ops「运行坑」:
    ESC 语义随画面漂移,无面板时落备战误弹中断挑战弹窗)。缺失场景 =
    有人回退实现补回 btn_tap('esc'),既有行为测试全绿也必须在此红。
    """
    src_file = Path(inspect.getsourcefile(CwEntryExit))
    assert src_file is not None and src_file.exists(), 'CwEntryExit 源文件定位失败'
    src = src_file.read_text(encoding='utf-8')
    for pattern in _ESC_TOMBSTONE_PATTERNS:
        hit = pattern.search(src)
        assert hit is None, (
            f'cw_entry_exit.py 出现 ESC 发射形态 {pattern.pattern!r}'
            f'(命中 {hit.group(0)!r})——该通道已随 ESC 清零批退役,'
            f'回潮 = 违反 runtime-ops ESC 绝对禁令,须改建档点击'
        )


def test_overlay_branch_retry_budget_semantics(
    test_context: SrTestContext,
) -> None:
    """锁(L1-12 改写,验证废除批 + K1):overlay 分支 retry 化——动作已发
    返回 round_retry(计节点 retry 预算),不再自带上界计数。

    重推依据(锁的存在性纪律):原 OVERLAY_ACTION_MAX=5 自带上界因
    「round_wait 不消耗预算」而生;验证废除批(用户裁定 2026-09-10:动作
    op 禁「未生效」检出)拆计数上界,分支改 round_retry 后每轮重命中 =
    每轮耗 1 次节点预算(exit_match node_max_retry_times=30),耗尽框架
    原生 FAIL 交外层重新导航——有界终止单由预算机制原生承载,空壳计数
    删除(禁保留空壳,批0c L1-12 判语)。本锁改锁新语义:①动作已发恒
    retry(轮次流转语义,非成败回执);②area 缺失(动作没发出)仍
    fail 如实交回;③同分支重命中不产生任何自带上界 fail(预算归节点)。
    """
    op = CwEntryExit(test_context)
    act_calls: list[str] = []

    def _act() -> bool:
        act_calls.append('click')
        return True   # 点击已发(浮层关没关由重入观察重判,不在动作层)

    with fast_sleep():   # round_retry(wait=2) 的轮间等待在测试环境纯属空转
        results = [op._overlay_branch('补给阶段', _act).result
                   for _ in range(8)]
    assert results == [OperationRoundResultEnum.RETRY] * 8, (
        f'动作已发应恒 retry(计节点预算,无自带上界),实际={results}')
    assert len(act_calls) == 8, (
        f'每次调用应恰发 1 次动作,实际 {len(act_calls)} 次')

    # area 缺失臂:动作没发出(职责未完成)→ fail 如实交回(ESC 已禁用)
    def _act_missing() -> bool:
        return False

    r_fail = op._overlay_branch('补给阶段', _act_missing)
    assert r_fail.result == OperationRoundResultEnum.FAIL, (
        f'area 缺失应 fail 交外层,实际={r_fail.result}')


def test_exit_door_area_center_and_goto_edge_onboarded() -> None:
    """建档中心锁:门形「按钮-退出对局」中心 =(61,63)±2,goto 边含中断挑战弹窗。

    出处:ESC 清零批退局发起 = 点备战左上门形图标替代旧 ESC(两入口实测 =
    docs/game/screens/currency_war_interrupt_dialog.md,手动链点左上
    ~(100,70) 落本 area 热区右缘)。中心是退局链的唯一点击落点——建档
    rect 漂移会让点击落空(门分支每轮重命中烧梯子预算至 fail)或误触相邻
    「按钮-敌人难度」(rect x≥95 与本 area 有重叠条带史,点它弹敌方信息
    浮层)。goto 边 = 「点门 → 弹窗」转场语义的建档声明半边,漂移 = 转场
    语义失真。锚值 (61,63) 独立于 yml(外部门形图标实测读数),非自证。
    """
    import yaml

    from one_dragon.base.geometry.rectangle import Rect

    p = (_MAIN_REPO / 'assets' / 'game_data' / 'screen_info'
         / 'currency_war_battle_prep.yml')
    with open(p, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    areas = {a['area_name']: a for a in d['area_list']}
    assert '按钮-退出对局' in areas, (
        '货币战争-备战应有「按钮-退出对局」area(退局发起唯一落点,'
        '删除 = 退局链 fail-closed 常态红)')
    rect = Rect(*areas['按钮-退出对局']['pc_rect'])
    c = rect.center
    assert abs(c.x - 61) <= 2 and abs(c.y - 63) <= 2, (
        f'门形图标中心应 =(61,63)±2,实际 ({c.x:.0f},{c.y:.0f})——'
        f'漂移先对相邻「按钮-敌人难度」rect(左缘 95,重叠条带史)'
    )
    goto = areas['按钮-退出对局'].get('goto_list') or []
    assert '货币战争-中断挑战弹窗' in goto, (
        f'goto_list 应含「货币战争-中断挑战弹窗」(点门 → 弹窗转场边),'
        f'实际={goto}')


# ==================== 结算屏清场语义批(T-57)判定层真帧锁 ====================


def test_settlement_real_frame_in_match_judgment(
    test_context: SrTestContext,
) -> None:
    """结算屏真帧(win/ended 双标题变体)→ 判定单一源命中「货币战争-结算」。

    T-57 定谳锚:.debug/temp/TODO.md 2026-08-24 债登记「BackToNormalWorldPlus
    不认识 CW P1 结算屏(挑战结束+继续挑战挂着时清场失败)」的识别面——
    判定单一源 ``cw_screen_state``(货币战争- 前缀 − 大厅白名单)按前缀
    自动收录结算屏(不在白名单),无需任何 per-screen 代码分支。真帧 + 真
    画面匹配照跑(id_mark = 按钮-继续挑战 OCR 锚):命中失败 = 建档漂移
    (锚失配)或白名单误收(结构性回潮),两层任一失效本锁红。

    ended.webp = 挑战结束 + 1-9 首领 + 继续挑战(P1 位面末首领存活挂机态,
    即债登记的目标画面;判读见 docs/game/screens/currency_war_settlement.md
    「子态」),win.webp = 挑战成功变体(同布局同 id_mark)。
    """
    # 结构半边:结算屏不许进大厅态白名单(误收 = 判定单一源漏接,委托分支失明)
    assert '货币战争-结算' not in cw_screen_state.LOBBY_STATE_SCREENS, (
        '结算屏是大厅白名单成员 = 对局中判定漏接(清场链失明回潮)')
    for state in ('win', 'ended'):
        if not test_context.has_screen('货币战争-结算', state):
            pytest.skip(f'存档截图缺失:screens/货币战争-结算/{state}.webp')
        img = test_context.load_screen('货币战争-结算', state)
        matched = cw_screen_state.get_in_match_screen_name(test_context, img)
        assert matched == '货币战争-结算', (
            f'结算屏 {state} 变体应对局中判定命中「货币战争-结算」,实际={matched}'
            f'(id_mark 漂移或白名单误收)')
