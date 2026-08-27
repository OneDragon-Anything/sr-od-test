# 检查器判据重定义批(W131/ADR-0353):levelup_interest_engine_gate
# 改读授权依据(旧「金<50 且未曾满息」判据把 [33] 人口位合法 <50 升级
# 全数计违规——W123 §5.3.3 实测 378 违规绝大多数为合法面,W126 后 206)。
#
# 锁面(双向,检查器非安慰剂):
# 1. 合法授权升级(pop_slot/dp)0 违规——重定义的放行面;
# 2. 无依据升级('')/static_ev 估值账放行的 <50 升级涌现违规——去门
#    变异必须被杀(授权依据缺失时检查器不失明);
# 3. 旧判据面保留:lv<5 不报、时点金 ≥50 不报;
# 4. 账本接线:sim 账本 LevelUp 行带 auth 键(观测字段端到端落地),
#    真实批 rows 过检查器 0 违规(合法面;static_ev 残量见 sim 冒测)。
from __future__ import annotations

import json
from pathlib import Path

from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war.cw_sim import simulate_p1_batch


def _row(round_num: int, gold0: int, level: int, auths: list[str]) -> dict:
    """构造单轮账本行(shop_waves 首波金=时点金;actions=LevelUp 组)。"""
    return {
        'plane': 1,
        'round_num': round_num,
        'gold': max(0, gold0 - 4 * len(auths)),
        'actions': [{'__type__': 'LevelUp', 'cost': 4, 'auth': a}
                    for a in auths],
        'sim': {'shop_waves': [{'gold': gold0}]},
        'state': {'level': level},
    }


def test_authorized_levelup_zero_violation() -> None:
    """合法授权升级 0 违规:pop_slot([33] 人口位)与 dp(DP 花费授权)
    的 lv≥5 时点金<50 升级是重定义后的放行面(旧判据误计违规的主体)。"""
    rows = [
        _row(4, 30, 5, ['pop_slot', 'pop_slot']),   # 多击整组
        _row(6, 12, 6, ['dp']),
        _row(7, 45, 7, ['pop_slot']),
    ]
    assert chk.check_levelup_interest_engine_gate(rows) == []


def test_unauthorized_levelup_emerges_violation() -> None:
    """无授权依据的 <50 升级必须涌现违规(去门变异可杀)。

    - auth=''(default 栈旧调用/未过账路径)→ 违规且消息标「无授权依据」;
    - W255/ADR-0410 起 static_ev 并入合法面(旧断言「static_ev 计违规」
      随语义过期——boss 升级禁令删除后该臂是末窗升级主授权臂,W123
      「帧量级 0-1 保守计违规」的校准前提已失效);无授权依据检测面
      (auth 空/缺失)保留,检查器对授权观测缺失不失明。"""
    # prev_level 语义:检查器用上一轮账本 level 判追级段(首轮 prev=3)
    # ——先放一行 lv5 铺底,违规落在第二行。
    _pre = _row(4, 60, 5, [])
    rows_no_basis = [_pre, _row(5, 30, 6, [''])]
    v1 = chk.check_levelup_interest_engine_gate(rows_no_basis)
    assert len(v1) == 1 and '无授权依据' in v1[0], v1

    # 旧 auth 键整体缺失(旧账本形态)等同无依据
    row = _row(5, 30, 6, ['pop_slot'])
    del row['actions'][0]['auth']
    v3 = chk.check_levelup_interest_engine_gate([_pre, row])
    assert len(v3) == 1, 'auth 键缺失必须计违规(授权不可默认成立)'


def test_old_criterion_surface_kept() -> None:
    """旧判据的非违规面保留:lv<5(r263 过渡宽松段)与时点金≥50 不报。"""
    assert chk.check_levelup_interest_engine_gate(
        [_row(3, 20, 4, [''])]) == []          # lv<5(首轮 prev=3)
    assert chk.check_levelup_interest_engine_gate(
        [_row(6, 55, 6, [''])]) == []          # 时点金 ≥50(息平台在场)
    # P1 外位面不辖
    row = _row(5, 30, 6, [''])
    row['plane'] = 2
    assert chk.check_levelup_interest_engine_gate([row]) == []


def test_ledger_auth_key_wired(tmp_path: Path) -> None:
    """账本接线锁:sim 账本 LevelUp 行带 auth 键(观测字段端到端落地),
    真实批 rows 过新判据检查器——授权升级不误报。"""
    rep = simulate_p1_batch(5, pool='fallback', seed_base=0,
                            ledger=tmp_path / 'auth')
    d = Path(rep['ledger_dir'])
    n_lv = 0
    arms: set[str] = set()
    for name in ('decisions.jsonl', 'outcomes.jsonl'):
        f = d / name
        if not f.exists():
            continue
        for ln in f.read_text(encoding='utf-8').splitlines():
            row = json.loads(ln)
            for a in row.get('actions') or []:
                if a.get('__type__') == 'LevelUp':
                    assert 'auth' in a, \
                        f'LevelUp 账本行缺 auth 键(观测字段断链):{a}'
                    assert a['auth'] in ('', 'pop_slot', 'dp',
                                         'static_ev'), a
                    n_lv += 1
                    arms.add(a['auth'])
    assert n_lv > 0, '5 局零 LevelUp:接线锁样本不足(换 seed_base)'
    # 真实批 rows(检查器消费的行流)过新判据:合法授权面(pop_slot/dp/
    # static_ev,W255 起)不误报。
    rows = [json.loads(ln) for ln in
            (d / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
    v = chk.check_levelup_interest_engine_gate(rows)
    for line in v:
        assert '无授权依据' not in line, \
            f'真实批涌现无授权依据升级(接线断裂或真违规):{line}'
