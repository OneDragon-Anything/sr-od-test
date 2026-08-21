# -*- coding: utf-8 -*-
"""r348/r350b(ADR-0220+用户点题):deploy cap 域两段反转锁——
①cap<level 才是真异常;②cap 落入未实拍后排档(7/9/10/11)
必须 obs_conflict 留证采集(7/9 后台建档信号,不得降 debug)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director
from sr_od.application.currency_war.cw_back_layout import (
    _UNVERIFIED_BACK_SLOTS,
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


def test_unverified_layout_slot_collects_evidence() -> None:
    """r350b(用户点题):cap 落入未实拍后排档(7/9/10/11)必须
    obs_conflict 留证——7/9 后台只有格点推导坐标,只有 8 后台
    做过狸猫局实拍级建档;该 hook 是新档实拍采集信号,
    r348 曾误降 debug 静音(已修)。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert '_UNVERIFIED_BACK_SLOTS' in src, \
        'cap 检查必须接未实拍档集合(采集信号)'
    assert 'deploy_cap_unverified_layout' in src, \
        '未实拍档必须 obs_conflict 留证(独立冲突类型)'
    assert '处理:本局识别/拖拽逐位验证' in src, \
        'verdict 必须带可执行处理步骤(hook 三要素)'


def test_unverified_set_semantics() -> None:
    """未实拍档集合语义:7/9/10/11 在内(格点推导);6(多局基线)
    与 8(狸猫局实拍)不在。"""
    assert _UNVERIFIED_BACK_SLOTS == frozenset({7, 9, 10, 11})
    assert effective_back_slots(5) == 6   # cap≤6 钳制→已实拍基线
    assert effective_back_slots(7) == 7   # 未实拍档


def test_cap_domain_behavior_level(monkeypatch) -> None:
    """review-L4(r353b):行为级锁(源码字符串断言锁不住重构)——
    直接调用 _observe 的 cap 检查段不可行(重观测依赖),改锁
    分支纯函数面:effective_back_slots×_UNVERIFIED_BACK_SLOTS
    的组合枚举 = 域检查的全部决策输入。"""
    # (cap, level) → 是否应留证(落入未实拍档)
    cases = [
        (7, 6, True),    # cap7/lv6 单宝钻但档未实拍 → 留证(review C 问)
        (7, 7, True),    # 无宝钻 7 档 → 仍留证(档问题非宝钻问题)
        (6, 6, False),   # 常态无叠加已实拍 → 不留证
        (8, 6, False),   # 双宝钻但 8 档已实拍(狸猫局) → 不留证
        (5, 3, False),   # cap<level? 否(5>3)→6 槽已实拍 → 不留证
    ]
    for cap, level, should_flag in cases:
        slots = effective_back_slots(cap)
        flagged = slots in _UNVERIFIED_BACK_SLOTS
        assert flagged == should_flag, \
            f'cap={cap}/lv={level}: 留证={flagged},期望 {should_flag}'
