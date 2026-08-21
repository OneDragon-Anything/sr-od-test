# -*- coding: utf-8 -*-
"""r348(ADR-0220):deploy cap 域检查反转锁——宝钻可叠加,
cap<level 才是真异常;cap>level+1 是宝钻数信息不得占 [cw!]。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director


def test_cap_domain_check_inverted() -> None:
    """旧窄域(cap∈{level,level+1})跨 5 局假警报(宝钻叠加是合法
    常态);反转后:下界违例才留证,上界超出去 debug 记宝钻数。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'cap < st.level' in src, \
        '真异常方向 = cap<level(不可能向,读错检测保留,ADR-0220)'
    assert '宝钻×%d 叠加' in src or '宝钻×' in src, \
        'cap>level+1 必须降级 debug 记宝钻数(合法信息非警报)'
    assert 'cap应在level..level+1' not in src, \
        '旧窄域 verdict 文案不得回流(假警报源)'
