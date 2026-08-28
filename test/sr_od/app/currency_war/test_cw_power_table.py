# -*- coding: utf-8 -*-
"""战力表判断层+桥线池测试(Phase A Day 1-4;评审 S7/B1 后重写)。"""
from sr_od.application.currency_war.cw_bridge_pool import (
    BRIDGE_POOL, BRIDGE_POOL_P2, pick_bridge, score_bridge,
)
from sr_od.application.currency_war.cw_chars import CHARACTERS
from sr_od.application.currency_war.cw_power_table import (
    COARSE, MISS, STRONG, POWER_EXACT_MIN, bonds_key, check,
)
from sr_od.application.currency_war.cw_power_table_data import (
    POWER_ENTRIES,
)


# ===== 战力表 =====

def test_bonds_key_canonical_order():
    assert bonds_key({'仙舟': 3, '持续伤害': 2}) == '仙舟3+持续伤害2'
    assert bonds_key({'护盾': 2, '列车同行': 2}) == '列车同行2+护盾2'


def test_check_exact_hit():
    lvl, n, pop = check('仙舟3+持续伤害2', 5, 'P1', 'burst')
    assert lvl == STRONG and n >= 80 and pop == 5


def test_check_pop_fallback_coarse_with_pop():
    """降人口维返回命中人口(消费方判距离用)。"""
    lvl, _, mp = check('仙舟3+持续伤害2', 99, 'P1', 'burst')
    assert lvl == COARSE and mp == 5  # 最强证据在人口5


def test_check_miss_pop_neg1():
    lvl, _, mp = check('量子同频9+击破9', 10, 'P1', 'burst')
    assert lvl == MISS and mp == -1


def test_conservative_factor_layered_real_entry():
    """S7:用真实条目验证分层——找篇数落在 action 阈与 reactive
    阈之间的条目,断言 action 过而 reactive 不过。"""
    lo = POWER_EXACT_MIN * 0.8   # action 因子
    hi = POWER_EXACT_MIN * 2.0   # reactive 因子
    found = None
    for (b, p, ph), v in POWER_ENTRIES.items():
        if lo <= v < hi:
            found = (b, p, ph, v)
            break
    assert found, '数据里找不到区间条目(生成器版本变化?)'
    b, p, ph, v = found
    assert check(b, p, ph, 'action')[0] == STRONG
    # reactive 需 >= 5*2=10;区间条目 <10 时精确层不过,
    # 但降维层可能命中更高篇数——所以只断言「精确层差异」
    lvl_r = check(b, p, ph, 'reactive')[0]
    if v < hi:
        # v < 10:reactive 精确层必不过;整体可能 COARSE(降维)
        assert lvl_r in (COARSE, MISS)


def test_unknown_drive_uses_reactive_factor():
    """unknown 驱动型取 reactive 系数(最保守)。"""
    # 用一个 8 篇的条目:burst(×1.2→阈6)过,unknown(×2.0→阈10)不过
    lo, hi = POWER_EXACT_MIN * 1.2, POWER_EXACT_MIN * 2.0
    found = None
    for (b, p, ph), v in POWER_ENTRIES.items():
        if lo <= v < hi:
            found = (b, p, ph, v)
            break
    if found:
        b, p, ph, _ = found
        assert check(b, p, ph, 'burst')[0] != MISS
        # unknown 与 reactive 同系数——精确层同样卡
        assert check(b, p, ph, 'unknown')[0] == \
            check(b, p, ph, 'reactive')[0]


# ===== 桥线池(评审 S7 最小集) =====

def test_bridge_names_all_in_registry():
    """B1 回归锁:池内所有名字必须在注册表里(防静默失配)。"""
    for pool in (BRIDGE_POOL, BRIDGE_POOL_P2):
        for c in pool:
            for name in c.fixed + c.core + c.flex:
                assert name in CHARACTERS, \
                    f'{c.bridge_id} 的 {name} 不在注册表'


def test_bridge_fixed_missing_zero_score():
    """fixed 缺一=0(判据级)。"""
    xd = next(c for c in BRIDGE_POOL if c.bridge_id == 'xianzhou_dot')
    # 有 core 无 fixed
    assert score_bridge(xd, {'藿藿', '丹恒·饮月', '艾丝妲'}) == 0.0
    # fixed 齐
    assert score_bridge(xd, {'爻光'}) > 0.0


def test_pick_bridge_highest_score():
    """选最高分桥(仙舟件齐→仙舟DOT,列车件齐→列车)。"""
    xd = pick_bridge({'爻光', '藿藿', '丹恒·饮月', '艾丝妲', '椒丘'})
    assert xd is not None and xd.bridge_id == 'xianzhou_dot'
    # 列车+DOT 件齐(fixed 饮月在两池都有)
    td = pick_bridge({'丹恒·饮月', '三月七', '椒丘', '艾丝妲'})
    assert td is not None


def test_pick_bridge_empty_or_all_missing():
    assert pick_bridge(set(), 'P1') is None
    assert pick_bridge({'姬子·启行'}, 'P1') is None  # 无桥 fixed 齐


def test_pick_bridge_phase_routing():
    """phase 显式映射:错拼抛 KeyError(防静默落错池)。"""
    try:
        pick_bridge(set(), 'P9')
        raise AssertionError('应抛 KeyError')
    except KeyError:
        pass
    assert pick_bridge({'姬子·启行', '三月七'}, 'P2') is not None
