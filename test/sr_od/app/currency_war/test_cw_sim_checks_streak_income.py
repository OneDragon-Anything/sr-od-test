# -*- coding: utf-8 -*-
"""W133:check_streak_combat_only_income(ADR-0351 断言化)自检锁。

W129 把该检查器收紧为断言但零测试:若账本行键名演化(如
node→node_type),旧实现 `.get()` 静默读 None → violations 恒 0 →
断言永久失明、全量仍绿。本文件锁三面:
1. 合成正例(违规必报/好样本必过,双向);
2. 缺键守卫(schema 演化 → 计入违规,不静默绿);
3. 去守卫变异推演(monkeypatch/最小克隆,证明上述样本能杀死
   「去收入段守卫」「去计数守卫」两种退化形态)。

分布数值不入锁(README 纪律 6);锁的是确定行为。
"""
from __future__ import annotations

from typing import Any

from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war import cw_economy


def _row(rn: int, node: str, streak: int, delta: int = 0) -> dict:
    """最小合成账本行(生产形状子集:cw_sim L1570 起必带 node/income)。"""
    return {'round_num': rn,
            'sim': {'node': node, 'delta': delta,
                    'income': {'base': 5, 'streak': streak}}}


def _good_ledger() -> list[list[dict]]:
    """好样本:run15 r3 同构(counter0 照发 table[0]=1,ADR-0351)。"""
    # r1 战斗胜(delta>=0):进轮 streak=0 → 账本发 streak_gold(0)=1;
    # r2 奖励轮不发连胜金(streak=0);重算口径 r1 同样 streak_gold(0)=1。
    return [[_row(1, 'battle', streak=1, delta=0),
             _row(2, 'reward', streak=0)]]


# --- 1. 合成正例(双向) -------------------------------------------------

def test_reward_streak_income_bidirectional() -> None:
    # 坏:奖励轮账本带连胜金 → 必报(检查器能抓)
    bad = [[_row(1, 'reward', streak=1)]]
    r = chk.check_streak_combat_only_income(bad)
    assert r['violations'] == 1, '奖励轮 streak 收入未报=断言失明'
    assert r['missing_key_rows'] == 0
    # 好:counter0 照发 table[0]=1(战斗轮)×奖励轮 0 → 零违规,
    # 且账本口径与 combat-only 重算口径对拍 delta=0(W129 口径自洽)
    r2 = chk.check_streak_combat_only_income(_good_ledger())
    assert r2['violations'] == 0, '好样本误报'
    assert r2['missing_key_rows'] == 0
    assert r2['ledger_streak_income'] == 1
    assert r2['combat_only_streak_income'] == 1, \
        'counter0 照发 streak_gold(0)=1 未入 combat-only 重算'
    assert r2['delta'] == 0


# --- 2. 键名演化变异(缺键守卫) ---------------------------------------

def test_missing_node_key_counts_as_violation() -> None:
    """模拟未来 schema 演化(node→node_type):缺键必须涌现违规。

    旧实现此处 violations==0(静默失明)——正是 W133 要修的点。
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

def _mutant_no_income_guard(ledgers: list[list[dict]]) -> dict:
    """去收入段守卫克隆:删掉 reward/supply 断言分支的最小变异。

    仅推演用:证明本文件的正/负样本能杀死该退化形态。
    与生产实现的保真度由下方 good 样本对拍断言保证(漂移即红)。
    """
    from sr_od.application.currency_war.cw_economy import streak_gold
    violations = ledger_sum = combat_sum = 0
    for rows in ledgers:
        streaks = chk._combat_streak_by_round(rows)
        for row in rows:
            sim = row.get('sim') or {}
            inc_streak = (sim.get('income') or {}).get('streak', 0) or 0
            ledger_sum += inc_streak
            combat_sum += streak_gold(
                streaks.get(row.get('round_num') or 0, 0))
    return {'violations': violations, 'ledger_streak_income': ledger_sum,
            'combat_only_streak_income': combat_sum}


def test_mutation_no_income_guard_killed() -> None:
    """去收入段守卫(不再判 reward/supply)→ 违规样本必须涌现差异。"""
    bad = [[_row(1, 'reward', streak=1)]]
    real = chk.check_streak_combat_only_income(bad)
    mutant = _mutant_no_income_guard(bad)
    # 克隆保真:好样本上 violations 与生产一致(combat_only 必然
    # 不同——去守卫变异把奖励轮也计入重算,正是退化形态本身)
    good_real = chk.check_streak_combat_only_income(_good_ledger())
    good_mut = _mutant_no_income_guard(_good_ledger())
    assert good_mut['violations'] == good_real['violations'] == 0
    # 杀死条件:坏样本上生产报违规、变异体静默 → 若生产真退化成
    # 该形态,上方 test_reward_streak_income_bidirectional 必红
    assert real['violations'] == 1 and mutant['violations'] == 0, \
        '违规样本杀不死「去收入段守卫」变异=锁失效'


def test_mutation_no_count_guard_killed(monkeypatch: Any) -> None:
    """去计数守卫(combat-only 重算链断)→ 披露口径必须涌现差异。

    最小变异:monkeypatch cw_economy.streak_gold 恒 0(模拟重算
    依赖断裂)。检查器函数体内 `from cw_economy import streak_gold`
    每次调用现取 → monkeypatch 源模块即生效。
    """
    good = _good_ledger()
    real = chk.check_streak_combat_only_income(good)
    assert real['combat_only_streak_income'] == 1, \
        'counter0 照发 1 未入重算(生产侧先红)'
    monkeypatch.setattr(cw_economy, 'streak_gold', lambda streak: 0)
    mutated = chk.check_streak_combat_only_income(good)
    assert mutated['combat_only_streak_income'] == 0, \
        'monkeypatch 未生效,推演无效'
    assert mutated['combat_only_streak_income'] != real[
        'combat_only_streak_income'], \
        '好样本杀不死「去计数守卫」变异=重算披露锁失效'
