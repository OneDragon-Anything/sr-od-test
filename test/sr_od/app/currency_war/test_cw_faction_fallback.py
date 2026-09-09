"""r137 阵营兜底测试(用户质询「列车件池 5 人?」→ 实 8 人的口径修正)。

出处:被测模块本体——现行基建锁(阵营兜底;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import sys

sys.path.insert(0, 'src')

from sr_od.application.currency_war.kernel.cw_transition import transition_score


def test_dual_faction_char_counts_for_framework():
    """饮月(仙舟+列车双阵营):列车框架下虽是仙舟在册件,应有阵营兜底分。"""
    s = transition_score('丹恒·饮月', '仙舟', '列车')
    assert s > 0.5, f'饮月对列车框架应有兜底分(羁绊计数有贡献),实得 {s}'


def test_nonroster_faction_char_partial_score():
    """星期日(盛会+列车,完全不在册):列车框架下 partial 级。"""
    s = transition_score('星期日', '盛会之星', '列车')
    assert s >= 0.6, f'星期日阵营命中列车应有 partial 级分,实得 {s}'


def test_roster_carry_still_highest():
    """在册 carry(三月七)同框架仍最高(策展档位不被兜底反超)。"""
    s_roster = transition_score('三月七', '列车同行', '列车')
    s_fallback = transition_score('星期日', '盛会之星', '列车')
    assert s_roster > s_fallback, '在册 carry 应高于阵营兜底件'
