"""cw_entry_policy 单元锁:难度确认屏「恒选最高」缺省判据两分支。

锁面依据 = 难度选择判据单一源设计(判据居 kernel/cw_entry_policy,
入口链 cw_entry_start 只观察+机械点击;行为保持契约 = 同输入同动作)。"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_entry_policy import (
    DifficultyEntryIntent,
    difficulty_entry_intent,
)


def test_go_highest_btn_present_switches_to_highest() -> None:
    """在场分支:「返回最高职级」在场 = 未在最高 → 恒切最高。

    切最高先于开始对局(原入口链分支序):同帧双在场仍切最高;职级读数
    不参与缺省策略分支(恒选最高与当前是 A5 还是 A8 无关)。"""
    assert difficulty_entry_intent(
        True, False, 'A5') is DifficultyEntryIntent.SWITCH_TO_HIGHEST, \
        '切最高按钮在场 → 切最高'
    assert difficulty_entry_intent(
        True, True, 'A8') is DifficultyEntryIntent.SWITCH_TO_HIGHEST, \
        '双按钮同帧在场 → 仍先切最高(行为保持)'


def test_go_highest_btn_absent_starts_or_keeps_observing() -> None:
    """不在场分支:切最高按钮不在场(已在最高)→ 按开始对局在场性分流。

    「开始对局」在场 → 开始对局;两按钮皆缺(转场帧)→ 不动作落回其余
    推进分支,入口链不得凭空点击。"""
    assert difficulty_entry_intent(
        False, True, 'A8') is DifficultyEntryIntent.START_MATCH, \
        '已在最高且开始对局在场 → 开始对局'
    assert difficulty_entry_intent(
        False, False, None) is DifficultyEntryIntent.KEEP_OBSERVING, \
        '两按钮皆缺 → 保持观察(零动作)'
