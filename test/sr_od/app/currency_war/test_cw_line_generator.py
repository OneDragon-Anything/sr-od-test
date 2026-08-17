"""cw_line_generator(25 号线生成器)v0 测试:J1 枚举覆盖率 + 先验语义 + 配额。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_line_generator import (  # noqa: E402
    RoleFacts,
    cost_gate_and_quota,
    enumerate_skeletons,
    strength_prior,
)


def _roles() -> list[RoleFacts]:
    return [
        RoleFacts('甲', 1, ('列车', '智识'), ('输出',), 'front'),
        RoleFacts('乙', 3, ('仙舟', '智识'), ('输出',)),
        RoleFacts('丙', 2, ('巡海', '仙舟'), ('辅助',)),
        RoleFacts('丁', 5, ('列车',), ('输出',)),
        RoleFacts('戊', 4, ('记忆',), ('治疗',)),
    ]


def test_j1_enumeration_coverage() -> None:
    """J1:枚举覆盖 427 组合空间的可达带(未知对被生成:已知线外的增量);
    去重生效;全高费 trait 被剪。"""
    known = {tuple(sorted(('列车', '仙舟')))}
    sks = enumerate_skeletons(_roles(), known_lines=known)
    pairs = {sk.core_traits for sk in sks}
    # 已知对不重复发射
    assert tuple(sorted(('列车', '仙舟'))) not in pairs
    # 未知对有增量(如 列车×智识、仙舟×巡海)
    assert tuple(sorted(('列车', '智识'))) in pairs
    # 「记忆」只有 4 费单角色——可作低费配对另一侧(≤4)不剪;carry=戊 时另一 trait
    # 须有低费单位 → 列车(甲 1 费)可配
    assert tuple(sorted(('记忆', '列车'))) in pairs
    # carry 不重复同 trait 对(t2 != t1)
    assert all(sk.core_traits[0] != sk.core_traits[1] for sk in sks)


def test_strength_prior_semantics() -> None:
    """先验语义:缺输出降权;阈值低(易激活)升权。"""
    roles = _roles()
    with_out = next(s for s in enumerate_skeletons(roles) if s.carry == '甲')
    no_out = next(s for s in enumerate_skeletons(roles) if s.carry == '戊')
    s_out = strength_prior(with_out, roles, {'列车': 2, '智识': 2})
    s_no = strength_prior(no_out, roles, {'记忆': 2, '列车': 2})
    assert s_out > s_no   # 戊 无输出 tag → ×0.5


def test_quota_topk_and_cost_gate() -> None:
    """配额:top-K 截断;成本门杀超预算骨架。"""
    roles = _roles()
    sks = enumerate_skeletons(roles)
    scores = {(sk.carry, sk.core_traits): strength_prior(sk, roles) for sk in sks}
    # 成本门:返回 None(不可行)或 >60 的杀
    gate = lambda sk: 999 if sk.carry == '戊' else 30
    out = cost_gate_and_quota(sks, scores, formation_cost_fn=gate, top_k=3)
    assert len(out) <= 3
    assert all(sk.carry != '戊' for sk in out)
    # 分数降序
    ranked = [scores[(sk.carry, sk.core_traits)] for sk in out]
    assert ranked == sorted(ranked, reverse=True)
