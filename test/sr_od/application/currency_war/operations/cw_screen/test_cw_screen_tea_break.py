"""幕后茶歇 op 剧本集(CwScreenTeaBreak;迭代 2026-11-20-cw-p0-chain
tasks 3.1,design §2.1):

- 剧本 1 = 分支态全链:标题词面态判别 → 选项一次读 + report 落
  ``tea_break_opts``/``tea_break_opts_xy``(同序等长)→ R1 零参读产 idx
  → 按 idx 点选项卡 → 确认钮出现 = 选中生效 → 点确认 until 奖励页标题
  → success 交回主循环;
- 剧本 2 = 首页双卡态前置段:首页态判别 → 首页 report → R1 卡按钮点击
  → 兜底边回观察重判 → 分支态接管 → 全链 success;
- 剧本 3 = 选中未生效脉冲:确认钮持续不在场 → 脉冲重入(重点同卡幂等)
  → CONFIRM_REJECT_MAX 耗尽 round_fail 交外环;
- 剧本 4 = 确认连等封顶:确认钮持续在场 ∧ 奖励页锚恒不出现(until
  round_wait 无界面)→ 连等计数 CONFIRM_WAIT_MAX 耗尽 round_fail 交外环;
- 纯函数 = pick_option_idx 固定规则(R1 回血优先 / R2 负面 HP 词面排除
  含「−N HP」「-N HP」实录形态 / R2b 返回类排除 / R3 取首 / 全排除
  None)。

帧资产 = 归档帧进仓(首页双卡 = 200426 / 分支选项 = 200509 / 分支确认 =
200546 / 奖励页 = 200623;坐标口径 = 1080p 建档帧),识别链跑真实 OCR
(conftest 内容哈希 memo);gs 桩 = session 命名空间(与 prep 剧本同款,
report 经 game_state_from_ctx 直达)。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.conftest import SrTestContext
from test.harness.cw_fixture_controller import CwFixtureController
from test.harness.fixture_controller import (
    enter_running_state,
    fast_sleep,
    reset_running_state,
)

from sr_od.application.currency_war.kernel.cw_game_state import game_state_of
from sr_od.application.currency_war.operations.cw_screen.cw_screen_tea_break import (
    CwScreenTeaBreak,
    pick_option_idx,
)

_TEA: str = '货币战争-幕后茶歇'
#: 分支态选项帧(两选项:美餐时间 R1 命中 / 返回 R2b 排除)。
_F_BRANCH: tuple[str, str] = (_TEA, '分支选项')
#: 分支态确认帧(点选后确认钮展开)。
_F_CONFIRM: tuple[str, str] = (_TEA, '分支确认')
#: 首页双卡帧(菇菇嘎嘎/聊一聊 + 享用茶歇·回复20小队生命值/摇一摇)。
_F_HOME: tuple[str, str] = (_TEA, '首页双卡')
#: 茶歇奖励页(判效锚帧)。
_F_REWARD: tuple[str, str] = ('货币战争-茶歇奖励', 'default')


def _require_frames(test_context: SrTestContext) -> None:
    """存档缺失 skip(采到后自动恢复),不 error。"""
    for screen_name, state in (_F_BRANCH, _F_CONFIRM, _F_REWARD):
        if not test_context.has_screen(screen_name, state):
            pytest.skip(f'存档截图缺失:screens/{screen_name}/{state}.webp')


def _attach_gs(test_context: SrTestContext,
               monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """挂流程态 Match 桩(session 命名空间;gs 经 game_state_from_ctx
    直达,report 写入可断言)。"""
    match = SimpleNamespace(session=SimpleNamespace(), gs=None)
    monkeypatch.setattr(test_context, 'cw_match', match)
    return match


def _run_op(test_context: SrTestContext, op: CwScreenTeaBreak):
    """fast_sleep 包裹执行 + 运行态前置复位(剧本测试惯例);看门狗混入
    防节点环失控(死循环 = fail 可见而非挂死测试进程)。"""
    enter_running_state(test_context)
    try:
        with fast_sleep(op):
            return op.execute()
    finally:
        reset_running_state(test_context, op)


def _opts_of(test_context: SrTestContext) -> tuple[list, list]:
    """读 game state 伴随域(report 写入结果断言面)。"""
    gs = game_state_of(test_context.cw_match.session)
    return (list(gs.tea_break_opts.value or []),
            list(gs.tea_break_opts_xy.value or []))


def test_branch_full_chain_reports_then_picks_r1_then_confirms(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 1 分支态全链:report 同序等长 → R1 产 idx 0 → 按坐标点卡 →
    确认钮展开 → 点确认 → until 奖励页 → success。"""
    _require_frames(test_context)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        # 分支选项帧:点选项卡(落读区内)推进到确认态帧
        {'frame': _F_BRANCH,
         'exit': ('on_click_in', _TEA, '读区-选项卡区')},
        # 分支确认帧:点确认钮推进到奖励页
        {'frame': _F_CONFIRM,
         'exit': ('on_click_in', _TEA, '按钮-确认')},
        {'frame': _F_REWARD},
    ])
    op = CwScreenTeaBreak(test_context)
    result = _run_op(test_context, op)

    assert result.success, f'分支态全链应 success,实际 {result.status!r}'
    # —— report 同序等长:选项文本 + 中心点(R1 选项在前)
    opts, pts = _opts_of(test_context)
    assert len(opts) == len(pts) == 2, \
        f'report 应写 2 选项同序等长,实际 opts={opts!r} pts={pts!r}'
    assert '回复' in opts[0] and '生命' in opts[0], \
        f'R1 选项(回复∧生命)应排首位,实际 {opts!r}'
    assert opts[1] == '返回', f'第二选项应为返回(R2b 排除对象),实际 {opts!r}'
    # —— 点击序列:点选项卡(在选项卡点击框内)→ 点确认(area rect 内)
    confirm_hit = ctrl.click_hit_area(_TEA, '按钮-确认')
    assert confirm_hit, f'应点击按钮-确认,实际点击 {ctrl.recorded_clicks}'
    in_strip = [p for p in ctrl.recorded_clicks
                if 1125 <= p.x <= 1860 and 385 <= p.y <= 865]
    assert len(in_strip) >= 1, \
        f'应先点选选项卡(读区内),实际点击 {ctrl.recorded_clicks}'
    # 首次点选落点 = gs 坐标伴随域 idx 0(零参读消费)
    ox, oy = pts[0]
    first = ctrl.recorded_clicks[0]
    assert (first.x, first.y) == (int(ox), int(oy)), \
        (f'点选落点应 = tea_break_opts_xy[0]({ox},{oy}),'
         f'实际 ({first.x},{first.y})')


def test_home_gate_clicks_r1_button_then_branch_takeover(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 2 首页前置段:首页态判别 → R1 卡(享用茶歇·回复20生命值)按钮
    点击 → 回观察重判 → 分支态接管全链 success。"""
    _require_frames(test_context)
    if not test_context.has_screen(*_F_HOME):
        pytest.skip(f'存档截图缺失:screens/{_F_HOME[0]}/{_F_HOME[1]}.webp')
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([
        # 首页双卡帧:点 R1 卡按钮(落首页选项带内)推进到分支态
        {'frame': _F_HOME,
         'exit': ('on_click_in', _TEA, '读区-首页选项卡带')},
        {'frame': _F_BRANCH,
         'exit': ('on_click_in', _TEA, '读区-选项卡区')},
        {'frame': _F_CONFIRM,
         'exit': ('on_click_in', _TEA, '按钮-确认')},
        {'frame': _F_REWARD},
    ])
    op = CwScreenTeaBreak(test_context)
    result = _run_op(test_context, op)

    assert result.success, f'首页前置段全链应 success,实际 {result.status!r}'
    # 首页 report:双卡选项(按钮框为点击框)入 game state
    opts, pts = _opts_of(test_context)
    assert len(opts) == 2, f'首页应报 2 卡,实际 {opts!r}'
    # 首次点击 = R1 卡按钮(落首页选项带内)
    assert ctrl.click_hit_area(_TEA, '读区-首页选项卡带'), \
        f'应点击 R1 卡按钮(摇一摇),实际点击 {ctrl.recorded_clicks}'


def test_confirm_pulse_retry_exhausts_to_fail(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 3 选中未生效:确认钮持续不在场 → 脉冲重入(每轮重点同卡,
    gs 未变 idx 恒定)→ 超限 round_fail 交外环(有界,禁无界循环)。"""
    _require_frames(test_context)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': _F_BRANCH}])   # 无 exit:确认钮恒不出现
    op = CwScreenTeaBreak(test_context)
    result = _run_op(test_context, op)

    assert not result.success, \
        f'确认钮恒不在场应 fail 交外环,实际 {result.status!r}'
    # 脉冲计数 = 首点 + 重试 ≤ CONFIRM_REJECT_MAX(常量单一源,不手抄)
    max_clicks = 1 + CwScreenTeaBreak.CONFIRM_REJECT_MAX
    assert len(ctrl.recorded_clicks) <= max_clicks, \
        (f'选卡点击应有界(≤{max_clicks} 次),'
         f'实际 {len(ctrl.recorded_clicks)} 次')


def test_confirm_wait_until_unsatisfied_capped_to_fail(
        test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
    """剧本 4 确认连等封顶:确认钮持续在场 ∧ 奖励页锚恒不出现——until
    点击恒成功锚恒不出现 = 框架 round_wait 无界(operation.py
    round_by_find_and_click_area「等待的失败出口」申报),节点自设连等
    封顶 CONFIRM_WAIT_MAX 耗尽 round_fail 交外环(有界,禁死循环)。"""
    _require_frames(test_context)
    _attach_gs(test_context, monkeypatch)
    ctrl = CwFixtureController(test_context)
    monkeypatch.setattr(test_context, 'controller', ctrl)
    ctrl.set_phases([{'frame': _F_CONFIRM}])   # 无 exit:确认钮恒在场,奖励页锚恒不出现
    op = CwScreenTeaBreak(test_context)
    result = _run_op(test_context, op)

    assert not result.success, \
        f'奖励页锚恒不出现应连等封顶 fail 交外环,实际 {result.status!r}'
    # 走的是确认连等路径(确认钮被点击),非选中未生效脉冲路径
    assert ctrl.click_hit_area(_TEA, '按钮-确认'), \
        f'应有点确认动作(连等路径),实际点击 {ctrl.recorded_clicks}'
    # 连等有界:每轮 = 点卡 1 + 点确认 1,总轮 ≤ 1 + CONFIRM_WAIT_MAX
    max_rounds = 1 + CwScreenTeaBreak.CONFIRM_WAIT_MAX
    assert len(ctrl.recorded_clicks) <= max_rounds * 2, \
        (f'确认连等应有界(≤{max_rounds} 轮×2 次),'
         f'实际 {len(ctrl.recorded_clicks)} 次')


def test_pick_option_idx_fixed_rules() -> None:
    """纯函数:R1 回血优先 / R2 负面词面排除(实录词形两向) /
    R2b 返回排除 / R3 取首 / 全排除 None / 空 None。"""
    # R1:含「回复」∧「生命」优先
    assert pick_option_idx(['美餐时间', '回复20小队生命值', '智慧果咖啡']) == 1
    # R2:负面 HP 词面排除(「失去」实录 /「降低」/「−N HP」「-N HP」形)
    assert pick_option_idx(['失去4生命值', '返回']) is None
    assert pick_option_idx(['智慧果咖啡+20经验−10HP', '回复20生命']) == 1
    assert pick_option_idx(['智慧果咖啡+20经验-10HP', '回复20生命']) == 1
    assert pick_option_idx(['HP降低10', '回复20生命']) == 1
    # R2b:返回类排除(点它 = 放弃交互)
    assert pick_option_idx(['返回']) is None
    # R3:其余取第一个未排除项
    assert pick_option_idx(['菇菇嘎嘎', '返回']) == 0
    # 全排除 / 空
    assert pick_option_idx(['返回', '失去4生命值']) is None
    assert pick_option_idx([]) is None

