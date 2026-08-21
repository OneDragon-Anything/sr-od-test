"""信号锁线+线库 v1 测试(Phase A Day 5-6)。"""

from sr_od.application.currency_war.cw_line_library_v1 import (
    LINE_LIBRARY_V1,
    line_of,
)
from sr_od.application.currency_war.cw_signal_lock import (
    check_core_signal,
)


def test_library_names_in_registry():
    """回归锁(同 B1 教训):线库核心字段的角色名在注册表。"""
    from sr_od.application.currency_war.cw_chars import CHARACTERS
    for line in LINE_LIBRARY_V1:
        assert line.carry in CHARACTERS, f'{line.line_id} carry 不在注册表'
        for c in line.core_cards:
            assert c in CHARACTERS, f'{line.line_id} core {c} 不在注册表'


def test_library_structure():
    """结构:三线/驱动型覆盖/降级链指向存在且无自环/兜底终点。"""
    assert [ln.line_id for ln in LINE_LIBRARY_V1] == \
        ['jizi_train', 'feiying_joy', 'dot_fallback']
    assert {ln.drive_type for ln in LINE_LIBRARY_V1} >= \
        {'burst', 'action', 'dot_fallback'}
    for line in LINE_LIBRARY_V1:
        if line.degrade_to is not None:
            target = line_of(line.degrade_to)
            assert target is not None, f'{line.line_id} 降级目标不存在'
            assert target.line_id != line.line_id  # 无自环
    assert line_of('dot_fallback').degrade_to is None   # 兜底=终点
    assert line_of('dot_fallback').core_cards == []     # 兜底不锁信号


def test_p2p3_forms_are_power_table_keys():
    """目标形态键必须存在于战力表数据(防编造键)。

    两档接受:①任人口/驱动型下查得 STRONG/COARSE;②键在
    POWER_ENTRIES 里真实存在但弱证据(如绯英 P3 3 篇——
    数据现实,查表 miss→战力模式是表的诚实回答,不是键错)。
    完全不存在=编造=失败。
    """
    from sr_od.application.currency_war.cw_power_table import check
    from sr_od.application.currency_war.cw_power_table_data import (
        POWER_ENTRIES,
    )
    for line in LINE_LIBRARY_V1:
        for ph, form in line.p2p3_forms.items():
            exists = any(b == form and phase == ph
                         for (b, _p, phase) in POWER_ENTRIES)
            assert exists, \
                f'{line.line_id} 的 {ph} 形态「{form}」不在战力表数据'
            drv = 'burst' if line.drive_type == 'dot_fallback' \
                else line.drive_type
            # N1:dot_fallback 按 burst 查——check() 只认三型+unknown,
            # burst(1.2)比 action(0.8)保守系数深,兜底从严
            hit = any(
                check(form, pop, ph, drv)[0] != 'miss'
                for pop in (5, 6, 7, 8, 9, 10))
            if not hit:
                # 弱证据键:存在但不过阈——合法,但至少要有篇数
                ns = [v for (b, _p, phase), v in POWER_ENTRIES.items()
                      if b == form and phase == ph]
                assert ns and max(ns) >= 2, \
                    f'{form}@{ph} 连 2 篇都没有——不是弱证据是噪声'


def test_signal_exact_match():
    """规范名精确匹配(识别层已归一,策略层不做模糊)。"""
    r = check_core_signal(['', '姬子·启行', '藿藿'])
    assert r.locked and r.line_id == 'jizi_train'
    assert r.matched_name == '姬子·启行'
    # set 输入同样支持
    assert check_core_signal({'绯英'}).line_id == 'feiying_joy'


def test_signal_unidentified_no_lock():
    """未识别(空名)不锁——漏锁可接受,误锁不可接受。"""
    assert not check_core_signal(['', '', '', '', '']).locked
    assert not check_core_signal([]).locked
    # 非规范名(识别层未归一的)不命中——策略层不做模糊
    assert not check_core_signal(['姬子启行']).locked


def test_signal_priority_library_order():
    """同层冲突:库序优先(姬子线在前)。"""
    r = check_core_signal(['姬子·启行', '绯英'])
    assert r.locked and r.line_id == 'jizi_train'


def test_signal_fallback_never_locks():
    """兜底线无核心卡信号(永远可选,不经信号锁)。"""
    assert not check_core_signal(['卡芙卡']).locked
    # r224 B1 回归:普通「姬子」(击破变体)不锁线——
    # 只有 姬子·启行 是锁线核心
    assert not check_core_signal(['姬子']).locked
    assert check_core_signal(['姬子·启行']).line_id == 'jizi_train'


def test_line_of_missing_returns_none():
    assert line_of('nonexistent') is None


def test_bench_windows_present_for_carry():
    """[21] 买而不上:CARRY 必须有上场窗口(姬子=7级/绯英=6级)。"""
    for line in LINE_LIBRARY_V1:
        if line.line_id == 'dot_fallback':
            continue  # 兜底 carry 早期就上场(前期=终局同体)
        assert line.carry in line.bench_windows, \
            f'{line.line_id} 的 carry 缺 bench_windows'
