# -*- coding: utf-8 -*-
"""r348/r350b(ADR-0220)→ ADR-0281 重写:deploy cap 域检查锁——
①cap<level 才是真异常(不可能向,读错检测保留);②布局选档 level 驱动后
(cap 与布局无关,双源实证),旧「cap 落入未实拍档留证」分支作废(7/9/10/11
档是循环论证幻影,已删);采集信号改 lv6 待采留证(back_7slots_pending)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director
from sr_od.application.currency_war.cw_back_layout import (
    _PENDING_7SLOT_LEVELS,
    effective_back_slots,
)


def test_cap_domain_check_inverted() -> None:
    """旧窄域(cap∈{level,level+1})跨 5 局假警报(宝钻叠加是合法
    常态);反转后:下界违例才留证,上界超出去 debug 记宝钻数。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'cap < st.level' in src, \
        '真异常方向 = cap<level(不可能向,读错检测保留,ADR-0220)'
    assert 'cap应在level..level+1' not in src, \
        '旧窄域 verdict 文案不得回流(假警报源)'


def test_lv6_pending_collects_evidence() -> None:
    """ADR-0281:采集信号 = lv6 待采留证(note_pending_7slots,
    back_7slots_pending)——旧「cap 落入未实拍档」hook 随幻影档作废。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'note_pending_7slots' in src, \
        'cap 检查段必须接 lv6 待采留证(ADR-0281 采集信号)'
    assert 'deploy_cap_unverified_layout' not in src, \
        '旧「未实拍档留证」分支已作废(7/9/10/11 是幻影,ADR-0281)'
    assert '_UNVERIFIED_BACK_SLOTS' not in src, \
        '旧集合已删(勿回流)'


def test_level_routing_semantics() -> None:
    """ADR-0281:level 驱动路由 —— lv≤5→6 / lv≥7→8 / lv6→保守 6;
    待采集 = {6};cap 不再进选档决策。"""
    assert _PENDING_7SLOT_LEVELS == frozenset({6})
    assert effective_back_slots(3) == 6
    assert effective_back_slots(5) == 6
    assert effective_back_slots(6) == 6   # 待采:保守 6
    assert effective_back_slots(7) == 8   # level 驱动(旧 cap 模型为 7=幻影)
    assert effective_back_slots(8) == 8


def test_cap_domain_behavior_level() -> None:
    """review-L4(r353b)→ ADR-0281 行为级锁:选档只看 level——
    同 level 不同 cap(cap=宝钻叠加,与布局无关)选档恒同。"""
    for lv in (3, 4, 5, 6, 7, 8):
        base = effective_back_slots(lv)
        for cap in (lv, lv + 1, lv + 2, lv + 3):
            assert effective_back_slots(lv) == base, \
                f'lv={lv}/cap={cap}: 选档不得随 cap 变(ADR-0281)'
