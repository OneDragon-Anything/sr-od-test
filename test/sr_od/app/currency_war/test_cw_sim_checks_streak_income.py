"""连胜金收入口径检查器自检锁(原 W133;ADR-0439 收入口径修正后重写)。

check_streak_combat_only_income 现辖三面断言(双向,少发/多发都报):
1. 补给轮 income.streak 恒 0(实发未钉死,零发放建模挂账);
2. 奖励轮照发 streak_gold(进轮连胜)(含 counter0=1,ADR-0351
   「不发金」半句被全量数据推翻);
3. 战斗轮 streak==0 且上一轮败 → LOSS_GOLD_BY_NODE[上一轮节点]
   (败轮金路径;否则按表)。
本文件锁:合成正例(违规必报/好样本必过)/缺键守卫(schema 演化
不静默绿)/去守卫变异推演(样本能杀死退化形态)。

分布数值不入锁(sr-od-test README 纪律);锁的是确定行为。
"""
from __future__ import annotations

from typing import Any

from sr_od.application.currency_war import cw_economy
from sr_od.application.currency_war import cw_sim_checks as chk


def _row(rn: int, node: str, streak: int, delta: int = 0,
         base: int = 5, interest: int = 0) -> dict:
    """最小合成账本行(生产形状子集:cw_sim 收入段必带 node/income)。"""
    return {'round_num': rn,
            'sim': {'node': node, 'delta': delta,
                    'income': {'base': base, 'interest': interest,
                               'streak': streak}}}


def _good_ledger() -> list[list[dict]]:
    """好样本:胜轮按表 + 败轮金路径 + 奖励轮照发 + 补给轮零,全链零违规。

    r1 胜(进轮 streak=0→表 1);r2 败(上一轮非败态,进轮 streak=1→表 1);
    r3 败(上一轮 r2 败→LOSS_GOLD battle=2);r4 奖励(照发,进轮
    streak=0→1);r5 补给(恒 0)。
    """
    return [[_row(1, 'battle', streak=1, delta=1),
             _row(2, 'battle', streak=1, delta=-5),
             _row(3, 'battle', streak=2, delta=-3),
             _row(4, 'reward', streak=1),
             _row(5, 'supply', streak=0, base=5, interest=2)]]


# --- 1. 合成正例(双向) -------------------------------------------------

def test_income_caliber_bidirectional() -> None:
    # 坏:奖励轮多发(表值 1 账本 3)/补给轮带 streak → 必报
    bad = [[_row(1, 'reward', streak=3)],
           [_row(1, 'supply', streak=1)]]
    r = chk.check_streak_combat_only_income(bad)
    assert r['violations'] == 2, '奖励/补给轮收入断言失明'
    assert r['missing_key_rows'] == 0
    # 坏:败轮金路径断(上一轮败应发 2,账本仍发表值 1)→ 必报
    bad_loss = [[_row(1, 'battle', streak=1, delta=-5),
                 _row(2, 'battle', streak=1, delta=-3)]]
    r_loss = chk.check_streak_combat_only_income(bad_loss)
    assert r_loss['violations'] == 1, '败轮金路径断言失明'
    # 坏:战斗轮少发(胜轮应发表值 1,账本 0)→ 必报(双向)
    bad_under = [[_row(1, 'battle', streak=0, delta=1)]]
    assert chk.check_streak_combat_only_income(
        bad_under)['violations'] == 1
    # 好:全链零违规,且账本口径与精确重算对拍 delta=0
    r2 = chk.check_streak_combat_only_income(_good_ledger())
    assert r2['violations'] == 0, f'好样本误报: {r2}'
    assert r2['missing_key_rows'] == 0
    assert r2['delta'] == 0
    assert r2['loss_gold_rows'] == 1   # r3 一轮命中败轮金路径
    assert r2['supply_rows'] == 1
    assert r2['supply_issued_extra'] == 7   # 补给多发残差披露(base+利息)
    assert r2['combat_only_streak_income'] == 5   # 1+1+2+1+0


# --- 2. 键名演化变异(缺键守卫) ---------------------------------------

def test_missing_node_key_counts_as_violation() -> None:
    """模拟未来 schema 演化(node→node_type):缺键必须涌现违规。

    旧实现此处 violations==0(静默失明)——正是本锁要修的点。
    """
    evolved = [{'round_num': 1,
                'sim': {'node_type': 'reward', 'delta': 0,
                        'income': {'base': 5, 'streak': 3}}}]
    r = chk.check_streak_combat_only_income([evolved])
    assert r['violations'] >= 1, '缺 node 键静默绿=断言永久失明'
    assert r['missing_key_rows'] == 1
    # income 整段缺失同理
    no_income = [{'round_num': 1, 'sim': {'node': 'reward', 'delta': 0}}]
    r2 = chk.check_streak_combat_only_income([no_income])
    assert r2['violations'] >= 1 and r2['missing_key_rows'] == 1
    # income 在但 streak 键缺失(streak→streak_count 演化)同理
    renamed = [{'round_num': 1,
                'sim': {'node': 'reward', 'delta': 0,
                        'income': {'base': 5, 'streak_count': 3}}}]
    r3 = chk.check_streak_combat_only_income([renamed])
    assert r3['violations'] >= 1 and r3['missing_key_rows'] == 1


# --- 3. 去守卫变异推演(不必真改生产代码) -----------------------------

def _mutant_flat_table(ledgers: list[list[dict]]) -> dict:
    """退化变异:所有行一律按 streak_gold(进轮连胜)重算——
    丢掉「补给轮恒 0」与「败轮金路径」两个特殊分支。
    """
    from sr_od.application.currency_war.cw_economy import streak_gold
    violations = ledger_sum = recompute = 0
    for rows in ledgers:
        streaks = chk._combat_streak_by_round(rows)
        for row in rows:
            sim = row.get('sim') or {}
            inc_streak = (sim.get('income') or {}).get('streak', 0) or 0
            ledger_sum += inc_streak
            expect = streak_gold(streaks.get(row.get('round_num') or 0, 0))
            recompute += expect
            if inc_streak != expect:
                violations += 1
    return {'violations': violations, 'ledger_streak_income': ledger_sum,
            'combat_only_streak_income': recompute}


def test_mutation_flat_table_killed() -> None:
    """扁平表变异(丢补给零/丢败轮金)必须被本文件样本杀死。"""
    good = _good_ledger()
    real = chk.check_streak_combat_only_income(good)
    assert real['violations'] == 0
    mutant = _mutant_flat_table(good)
    # 杀死面①:补给轮——生产恒 0,扁平表按表算 1 → 变异误报
    # (r5 补给进轮 streak=0,表值 1 ≠ 账本 0)
    assert mutant['violations'] >= 1, '补给零断言杀不死扁平表变异'
    # 杀死面②:败轮金——生产发 LOSS_GOLD 2,扁平表按表算 1 → 变异误报
    bad_loss = [[_row(1, 'battle', streak=1, delta=-5),
                 _row(2, 'battle', streak=2, delta=-3)]]
    assert chk.check_streak_combat_only_income(bad_loss)['violations'] == 0
    assert _mutant_flat_table(bad_loss)['violations'] >= 1, \
        '败轮金路径杀不死扁平表变异'


def test_mutation_no_count_guard_killed(monkeypatch: Any) -> None:
    """重算链断(monkeypatch streak_gold 恒 0)→ 披露口径必须涌现差异。

    检查器函数体内 `from cw_economy import streak_gold` 每次调用现取
    → monkeypatch 源模块即生效。
    """
    good = _good_ledger()
    real = chk.check_streak_combat_only_income(good)
    assert real['combat_only_streak_income'] == 5, \
        '重算基线漂移(生产侧先红)'
    monkeypatch.setattr(cw_economy, 'streak_gold', lambda streak: 0)
    mutated = chk.check_streak_combat_only_income(good)
    assert mutated['combat_only_streak_income'] == 2, \
        'monkeypatch 未生效(只剩败轮金 2),推演无效'
    assert mutated['combat_only_streak_income'] != real[
        'combat_only_streak_income'], \
        '好样本杀不死「重算链断」变异=披露锁失效'
