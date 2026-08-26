"""r348/r350b(ADR-0220)→ ADR-0281 → W209/ADR-0385 重写:deploy cap 域检查锁——
①cap<level 才是真异常(不可能向,读错检测保留);②布局选档改 **cap 差公式**驱动
(口述「后台格数 = 6+(cap−level)」,run 26 lv8 无召唤物局按 8 格坐标拖不存在的
格子=崩坏根因①)后:cap 与 level **两读数共同**进选档,旧 lv6 待采留证
(note_pending_7slots)随 level 驱动模型作废,采集信号改 7 格档未建档留证
(back_7slots_pending,cw_back_layout.select_back_layout 内辖)。"""
from __future__ import annotations

import inspect

from sr_od.application.currency_war import prep_director
from sr_od.application.currency_war.cw_back_layout import (
    back_slots_from_cap_diff,
)


def test_cap_domain_check_inverted() -> None:
    """旧窄域(cap∈{level,level+1})跨 5 局假警报(宝钻叠加是合法
    常态);反转后:下界违例才留证,上界超出去 debug 记宝钻数。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'cap < st.level' in src, \
        '真异常方向 = cap<level(不可能向,读错检测保留,ADR-0220)'
    assert 'cap应在level..level+1' not in src, \
        '旧窄域 verdict 文案不得回流(假警报源)'


def test_lv6_pending_hook_retired() -> None:
    """W209/ADR-0385:旧 lv6 待采留证(note_pending_7slots)随 level 驱动模型
    作废删除——采集信号改 7 格档未建档(diff==1)留证,辖域在
    cw_back_layout(select_back_layout/note_7slots_pending),prep_director 不再挂。"""
    src = inspect.getsource(prep_director.PrepDirector._observe)
    assert 'note_pending_7slots(' not in src and 'note_7slots_pending(' not in src, \
        'lv6 待采留证已废(ADR-0385);7 格留证辖域在 cw_back_layout'
    assert 'deploy_cap_unverified_layout' not in src, \
        '旧「未实拍档留证」分支已作废(7/9/10/11 是幻影,ADR-0281)'
    assert '_UNVERIFIED_BACK_SLOTS' not in src, \
        '旧集合已删(勿回流)'


def test_cap_diff_formula_semantics() -> None:
    """W209/ADR-0385:口述公式「后台格数 = 6+(cap−level)」——
    diff0→6 / diff1→7(已建档,2026-08-26 佩佩局实锤)/ diff≥2→8。"""
    assert back_slots_from_cap_diff(0) == 6
    assert back_slots_from_cap_diff(2) == 8
    assert back_slots_from_cap_diff(1) == 7   # 7 格已建档 → 直读(佩佩局锚)


def test_cap_drives_selection_level_alone_does_not() -> None:
    """W209/ADR-0385 行为级锁(反转 ADR-0281 的「cap 不进选档」):
    同 level 不同 cap → 选档**随 cap 差变**(run 26 lv8 cap8=6 格 /
    钻石叠加 lv8 cap10=8 格);同 cap 差不同 level → 选档恒同
    (level 单独不再参与选档)。"""
    for lv in (3, 5, 7, 8):
        assert back_slots_from_cap_diff(0) == 6, \
            f'lv={lv} 无扩展:恒 6 格(run 26 反向锚)'
        assert back_slots_from_cap_diff(2) == 8, \
            f'lv={lv} diff2:恒 8 格(狸猫局锚)'
    # 同 diff 跨 level 恒同(公式只看差值)
    for d in (0, 1, 2):
        vals = {back_slots_from_cap_diff(d) for lv in (3, 4, 5, 6, 7, 8)}
        assert vals == {back_slots_from_cap_diff(d)}, \
            f'diff={d}:选档不得随 level 单独变(ADR-0385)'
