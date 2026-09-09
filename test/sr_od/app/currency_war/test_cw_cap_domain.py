# -*- coding: utf-8 -*-
"""test_cw_cap_domain 主题锁。

2026-09-03 拆分归档批:自混合文件 test_cw_legacy_audit.py 按 member 拆回独立文件(纯移动,断言零改动;原合并文件消亡)。"""
from __future__ import annotations



import inspect as _r348_cap_domain_inspect

from sr_od.application.currency_war.operations.cw_screen import (
    cw_screen_prep as _r348_cap_domain_prep,
)


def test_cap_domain_check_inverted() -> None:
    """旧窄域(cap∈{level,level+1})跨 5 局假警报(宝钻叠加是合法
    常态);反转后:下界违例才留证,上界超出去 debug 记宝钻数。"""
    src = _r348_cap_domain_inspect.getsource(_r348_cap_domain_prep.CwScreenPrep._observe)
    assert 'cap < st.level' in src, \
        '真异常方向 = cap<level(不可能向,读错检测保留,ADR-0220)'
    assert 'cap应在level..level+1' not in src, \
        '旧窄域 verdict 文案不得回流(假警报源)'


def test_lv6_pending_hook_retired() -> None:
    """W209/ADR-0385:旧 lv6 待采留证(note_pending_7slots)随 level 驱动模型
    作废删除——采集信号改 7 格档未建档(diff==1)留证,辖域在
    cw_back_layout(select_back_layout/note_7slots_pending),cw_screen_prep 不再挂。"""
    src = _r348_cap_domain_inspect.getsource(_r348_cap_domain_prep.CwScreenPrep._observe)
    assert 'note_pending_7slots(' not in src and 'note_7slots_pending(' not in src, \
        'lv6 待采留证已废(ADR-0385);7 格留证辖域在 cw_back_layout'
    assert 'deploy_cap_unverified_layout' not in src, \
        '旧「未实拍档留证」分支已作废(7/9/10/11 是幻影,ADR-0281)'
    assert '_UNVERIFIED_BACK_SLOTS' not in src, \
        '旧集合已删(勿回流)'


# (2026-09-03 瘦身批:cap_diff 两测删除——值面与「level 单独不参与」由
#  test_cw_data_registry.py::test_cap_diff_routing 严格超集辖定(三档值+
#  域外/读错边界+幻影负例,纪律 7);墓碑两条保留。)
