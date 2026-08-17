"""cw_knowledge_compiler(11 号知识编译层)v0 测试:DSL 校验 + 归并/冲突/分层。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.cw_knowledge_compiler import (  # noqa: E402
    Condition,
    Evidence,
    StrategyRule,
    Src,
    compile_rules,
    validate_condition,
)


def _rule(rid, field='hp', op='lt', value=20, pres=('posture', '息 floor 降 20'),
          ctx='', n=1, cred=1.0, src_kind='plaza', quote='血量低就不需要卡利息了,留20块就OK') -> StrategyRule:
    return StrategyRule(rid, 'economy', Condition(field, op, value, ctx), pres,
                        (Src(src_kind, f'ref-{rid}', quote),),
                        Evidence(n_support=n, credibility=cred))


def test_dsl_validation() -> None:
    """编译期校验:白名单字段过;非法字段/算子拒绝(引不到实体的条件不入库)。"""
    assert validate_condition(Condition('hp', 'lt', 20))
    assert not validate_condition(Condition('nonexistent_field', 'lt', 1))
    assert not validate_condition(Condition('hp', 'regex', 1))


def test_merge_evidence_across_posts() -> None:
    """归并:同条件同处方跨篇合并 → 证据计数累计,分层升 guide_high。"""
    rules = [_rule('r1', n=1, cred=1.5), _rule('r2', n=1, cred=2.0), _rule('r3', n=1, cred=1.0)]
    out = compile_rules(rules)
    assert len(out['rules']) == 1
    m = out['rules'][0]
    assert m.evidence.n_support == 3 and abs(m.evidence.credibility - 4.5) < 1e-9
    assert m.tier == 'guide_high'
    assert len(m.provenance) == 3


def test_conflict_not_averaged() -> None:
    """冲突:同条件反处方 → 不平均,进人审队列(上下文标签相同才算冲突)。"""
    a = _rule('a', pres=('posture', '息 floor 降 20'))
    b = _rule('b', pres=('posture', '息 floor 保 50'))   # 反处方
    c = _rule('c', pres=('posture', '息 floor 保 50'), ctx='shield_flow')  # 上下文分叉≠冲突
    out = compile_rules([a, b, c])
    assert out['n_conflicts'] == 1
    assert len(out['conflicts'][0]) == 2
    # 冲突双方各自保留(不平均、不丢弃)待人审;上下文分叉条目独立存活
    assert len(out['rules']) == 3


def test_user_tier_top_credibility() -> None:
    """user 源直入最高层(用户口述 > 任何篇数)。"""
    out = compile_rules([_rule('u', src_kind='user', quote='用户口述')])
    assert out['rules'][0].tier == 'user'


def test_single_post_stays_low() -> None:
    """单帖 guide_low(只候选不生效)。"""
    out = compile_rules([_rule('solo', n=1, cred=1.0)])
    assert out['rules'][0].tier == 'guide_low'
