"""cw_screen_report 包四新 obs 分侧自检(迭代 2026-11-20-cw-p0-chain
tasks 3.1-3.4;design §2.5 上报形态申报的分侧断言面):

- op1 茶歇 / op3 奇遇对话 / op4 光环选择 = **report 真实写**(函数在
  场;实载荷写字段断言 + 空载荷读缺跳写闸断言);
- op2 茶歇奖励 = **无 report 形态**(函数不在场——与
  test_cw_screen_tea_break_reward.py 的模块级断言互为补充,本文件从
  包完备视角再锁一次)。

obs 类 = 结构化结果 + ``screen`` 稳定帧引用契约(op-layer.md §2.1);
字段写入语义 = game state(同门同帧同序等长,读缺跳写)。
"""

from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_screen_report.adventure_dialog import (
    CwScreenAdventureDialogObs,
    report_screen_adventure_dialog_obs,
)
from sr_od.application.currency_war.kernel.cw_screen_report.aura_select import (
    CwScreenAuraSelectObs,
    report_screen_aura_select_obs,
)
from sr_od.application.currency_war.kernel.cw_screen_report.tea_break import (
    CwScreenTeaBreakObs,
    report_screen_tea_break_obs,
)
from sr_od.application.currency_war.kernel.cw_screen_report.tea_break_reward import (
    CwScreenTeaBreakRewardObs,
)

#: 测试用渠道签名(actor = 各自画面 op 类名,与生产同形)。
_SIG: ChannelSig = ChannelSig(family='logic_action', actor='test', mode='compute')


def _gs():
    return game_state_of(SimpleNamespace())


def test_tea_break_report_writes_opts_and_xy() -> None:
    """op1 report 真实写:选项文本/中心同门写入;空载荷读缺跳写。"""
    gs = _gs()
    obs = CwScreenTeaBreakObs(
        on_screen=True,
        options=[('美餐时间回复20小队生命值', (1148, 394, 1347, 492)),
                 ('返回', (1146, 589, 1200, 619))],
        screen=object())
    report_screen_tea_break_obs(gs, obs, sig=_SIG)
    assert list(gs.tea_break_opts.value) == \
        ['美餐时间回复20小队生命值', '返回']
    pts = list(gs.tea_break_opts_xy.value)
    assert pts == [(1247, 443), (1173, 604)], \
        f'中心应 = 点击框中心(同序等长),实际 {pts!r}'
    # 读缺跳写:新 gs 上空载荷 → 字段保持 None(「读到空」与「未读到」同判)
    gs2 = _gs()
    report_screen_tea_break_obs(gs2, CwScreenTeaBreakObs(on_screen=True),
                                sig=_SIG)
    assert gs2.tea_break_opts.value is None
    assert gs2.tea_break_opts_xy.value is None


def test_adventure_dialog_report_skips_absent_fields() -> None:
    """op3 report 真实写:名字与卡选项各自读缺跳写;实载荷双域写入。"""
    gs = _gs()
    obs = CwScreenAdventureDialogObs(
        on_screen=True, partner_name='姬奇貓', card_options=[], screen=object())
    report_screen_adventure_dialog_obs(gs, obs, sig=_SIG)
    assert gs.adventure_partner_name.value == '姬奇貓'
    assert gs.adventure_card_opts.value is None, \
        '卡未在场应跳写(读缺闸)'
    obs2 = CwScreenAdventureDialogObs(
        on_screen=True, partner_name=None,
        card_options=[('回复20小队生命值', (1146, 433, 1515, 534))],
        screen=object())
    report_screen_adventure_dialog_obs(gs, obs2, sig=_SIG)
    assert list(gs.adventure_card_opts.value) == ['回复20小队生命值']
    assert list(gs.adventure_card_opts_xy.value) == [(1330, 483)]
    # 名字读缺跳写保持旧值(整表覆盖只在读得时发生)
    assert gs.adventure_partner_name.value == '姬奇貓'


def test_aura_select_report_writes_names_centers_preview() -> None:
    """op4 report 真实写:标准化名二槽 + 中心同序等长 + 预览产点。"""
    gs = _gs()
    obs = CwScreenAuraSelectObs(
        on_screen=True, aura_left='富翁的梦泡', aura_right='闪耀蓝星',
        aura_centers=[(420, 485), (1500, 492)],
        preview_points=[(815, 620), (915, 620)], screen=object())
    report_screen_aura_select_obs(gs, obs, sig=_SIG)
    assert list(gs.aura_select_opts.value) == ['富翁的梦泡', '闪耀蓝星']
    assert list(gs.aura_select_opts_xy.value) == [(420, 485), (1500, 492)]
    assert list(gs.aura_select_preview_xy.value) == [(815, 620), (915, 620)]
    # 转换失败形态(任一槽空)= 不达写端(禁带病上报;op 侧早退语义的
    # report 侧兜底——二槽结构缺一即失败)
    gs2 = _gs()
    report_screen_aura_select_obs(
        gs2, CwScreenAuraSelectObs(on_screen=True, aura_left='富翁的梦泡',
                                   aura_right='', screen=object()), sig=_SIG)
    assert gs2.aura_select_opts.value is None


def test_tea_break_reward_no_report_form() -> None:
    """op2 无 report 形态:report 函数不在场(推进型,obs 构造即弃零
    保留);obs 类构造面在场(screen 稳定帧引用契约)。"""
    from sr_od.application.currency_war.kernel.cw_screen_report import (
        tea_break_reward as mod,
    )
    assert not hasattr(mod, 'report_screen_tea_break_reward_obs')
    obs = CwScreenTeaBreakRewardObs(on_screen=True, screen=object())
    assert obs.on_screen is True and obs.screen is not None
