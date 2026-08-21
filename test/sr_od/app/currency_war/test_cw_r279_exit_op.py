# -*- coding: utf-8 -*-
"""r279 退局 op 分支③测试(战斗中→暂停→撤退)。

画面档:货币战争-战斗暂停(新,2026-08-23 实证)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.operations.entry.exit_currency_war_match import (
    ExitCurrencyWarMatch,
)


def test_op_exists_and_named() -> None:
    assert ExitCurrencyWarMatch.STATUS_AT_LOBBY == '已返回货币战争大厅'


def test_battle_pause_screen_onboarded() -> None:
    """战斗暂停画面档存在(分支③的识别地基)。"""
    import yaml

    p = 'assets/game_data/screen_info/currency_war_battle_pause.yml'
    d = yaml.safe_load(open(p, encoding='utf-8'))
    names = {a['area_name'] for a in d['area_list']}
    assert '标识-战斗暂停' in names
    assert '按钮-撤退' in names
    assert '按钮-继续战斗' in names


def test_retreat_branch_in_op() -> None:
    """op 源码含战斗暂停→撤退分支(r279 增补)。"""
    import inspect

    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    assert '货币战争-战斗暂停' in src
    assert '按钮-撤退' in src
    assert '(1843, 42)' in src   # 战斗中右上角 X 实证坐标


def test_no_round_retry_tail() -> None:
    """战斗中不再落入 retry 死循环(旧版尾分支)。"""
    import inspect

    src = inspect.getsource(ExitCurrencyWarMatch.exit_match)
    assert 'round_retry' not in src.split('战斗中(未暂停态)')[0].split(
        '标识-战斗暂停')[0] or True   # r279 后 retry 移除,战斗中走 X
    assert 'round_retry' not in src, 'r279: 全分支消化,无 retry 尾'
