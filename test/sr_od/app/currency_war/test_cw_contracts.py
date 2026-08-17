"""cw_contracts(13 号行为合约 v0)测试:J1 bug 重现对拍(ADR-0162)。"""
from sr_od.application.currency_war.cw_contracts import (
    DEFAULT_CONTRACTS,
    audit_replay,
    check_contracts,
)


def _row(ts, plane, rnd, gold, level, bench_n, hp=80, tgt='', fp=None):
    return {'ts': ts, 'state': {'plane': plane, 'round_num': rnd, 'gold': gold,
                                'level': level, 'bench': [{}] * bench_n, 'hp': hp},
            'target_comp': tgt, 'fp': fp}


def test_j1_m19_hp_default_poison():
    """M19 重现:p2 r2+ 连续 8 决策点 hp=100(默认值)→ 违约。"""
    traj = [_row(f't{i:02d}', 2, 2, 20 + i, 6, 3, hp=100) for i in range(10)]
    vs = check_contracts(traj)
    assert any(v.contract == 'hp_default_poison' for v in vs)
    # 正常 hp 波动 → 不触发
    ok = [_row(f't{i:02d}', 2, 2, 20 + i, 6, 3, hp=100 - i) for i in range(10)]
    assert not any(v.contract == 'hp_default_poison' for v in check_contracts(ok))


def test_j1_m17b_gold_no_progress():
    """M17b/M24 重现:同回合连续 12 决策点(金,级,bench)零变化 → 活性违约。"""
    traj = [_row(f't{i:02d}', 1, 5, 30, 6, 9) for i in range(15)]
    vs = check_contracts(traj)
    assert any(v.contract == 'gold_no_progress' for v in vs)
    # 正常推进 → 不触发
    ok = [_row(f't{i:02d}', 1, 5, 30 - i, 6, 9) for i in range(15)]
    assert not any(v.contract == 'gold_no_progress' for v in check_contracts(ok))


def test_j1_m34_target_no_pivot():
    """M34 重现:target 钉死 18+ 决策点且 fp 均值 <0.4 → 转型活性违约。"""
    traj = [_row(f't{i:02d}', 1, i % 9 + 1, 30, 6, 3, tgt='列车同行', fp=0.25) for i in range(20)]
    vs = check_contracts(traj)
    assert any(v.contract == 'target_no_pivot' for v in check_contracts(traj))
    # fp 健康爬升 → 不触发
    ok = [_row(f't{i:02d}', 1, i % 9 + 1, 30, 6, 3, tgt='列车同行', fp=0.2 + i * 0.04) for i in range(20)]
    assert not any(v.contract == 'target_no_pivot' for v in check_contracts(ok))


def test_j1_m25_fp_diverge():
    """M25 重现:fp 连续 6 点下降(target 期己方买入走散)→ 自洽违约。"""
    traj = [_row(f't{i:02d}', 2, 3, 40 - i, 7, 3, tgt='希儿量子', fp=0.6 - i * 0.05) for i in range(8)]
    vs = check_contracts(traj)
    assert any(v.contract == 'fp_diverge_on_buy' for v in vs)


def test_contracts_discipline():
    """铁律 1 形式检查:合约描述不得含策略评分词(胜率/强度/最优)。"""
    for c in DEFAULT_CONTRACTS:
        for w in ('胜率', '强度', '最优', '评分'):
            assert w not in c.description, f'{c.name} 描述含策略词「{w}」(铁律1)'


def test_audit_replay_file_roundtrip(tmp_path):
    p = tmp_path / 'decisions.jsonl'
    p.write_text('\n'.join(
        __import__('json').dumps(_row(f't{i:02d}', 2, 2, 20, 6, 3, hp=100)) for i in range(10)
    ), encoding='utf-8')
    rep = audit_replay(p)
    assert rep['rows'] == 10
    assert rep['by_contract'].get('hp_default_poison', 0) >= 1
