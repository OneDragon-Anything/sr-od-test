"""test_cw_sim_smoke 主题锁——sim 基建 smoke + 裁判 fail-closed 代表。

覆盖面(四类承重件):
- 入口 smoke:有限牌池守恒(sim.infra 基础不变量,draw 不减池/take-ret 互逆);
- 金钱不变量:账本守恒裁判(坏账本必报/好账本过/卖回金计收入侧/缺字段报);
- fail-closed 代表:裁判缺键守卫(schema 演化缺 node/income 键必须涌现违规,
  静默绿 = 断言永久失明)+ sim 账本写入器禁写生产 live 流目录(自中毒防线)。

来源指针(2026-09-09 目标形态重建批,断言零改动迁移):
- test_cw_sim_suite.py(sim 段/账本检查段/写入器守卫段)。
其余历史锁已退役(git 可复活);sim 每晚全链路(行为层安全网)不在 pytest 面。

出处:被测模块本体 sim/pool.py、sim/checks/(runtime/ledger)、sim/runner.py;
写入器守卫事故出处 = 2026-09-07 空批旧根截断事故(ADR-0586「单一源与守卫」节)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.data.cw_shop_odds import POOL_COPIES_PER_CARD
from sr_od.application.currency_war.sim.checks import ledger
from sr_od.application.currency_war.sim.checks import runtime as chk
from sr_od.application.currency_war.sim.pool import _Pool
from sr_od.application.currency_war.sim.runner import write_batch_ledger

# ==================== sim infra smoke(自 test_cw_sim_suite.py sim 段迁入) ====================

def test_pool_conservation() -> None:
    """有限牌池守恒:draw 不减池(买了才减),take/ret 互逆。"""
    import random
    rng = random.Random(7)
    p = _Pool(rng)
    total0 = sum(p.copies.values())
    p.draw_shop(5)                       # 抽店不减池(商店只是展示)
    assert sum(p.copies.values()) == total0
    name = next(iter(p.copies))
    p.take(name)
    assert sum(p.copies.values()) == total0 - 1
    p.ret(name)
    assert sum(p.copies.values()) == total0
    assert p.copies[name] <= POOL_COPIES_PER_CARD[CHARACTERS[name].cost]


# ==================== 裁判:键名演化变异缺键守卫(自 sim_checks_streak_income 段迁入) ====================

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


# ==================== 裁判:金守恒账本检查(自 sim_ledger_checks 段迁入) ====================

def _sim_ledger_checks_row(round_num: int = 1, gold: int = 10, gold_before: int = 5,
           income: dict | None = None, spend: dict | None = None,
           actions: list | None = None, target_comp: str = '') -> dict:
    return {
        'ts': round_num, 'round_num': round_num, 'gold': gold,
        'target_comp': target_comp, 'actions': actions or [],
        'sim': {
            'gold_before': gold_before,
            'income': income or {'base': 5, 'interest': 0,
                                 'streak': 1, 'event': 0},
            'spend': spend or {'buys': {}, 'levelup': 0,
                               'refresh': 0, 'sell_income': 0},
        },
    }


def test_consistency_check_bidirectional() -> None:
    """守恒检查:坏账本报(金不守恒)/好账本过。"""
    bad = [_sim_ledger_checks_row(gold=99)]   # 5+6≠99
    assert ledger.check_ledger_consistency(bad), '坏账本未报警=静默失效'
    good = [_sim_ledger_checks_row(gold=11)]  # 5+6=11
    assert not ledger.check_ledger_consistency(good)
    # 卖回金计收入侧
    good2 = [_sim_ledger_checks_row(gold=13, spend={'buys': {'line': 2}, 'levelup': 0,
                                  'refresh': 0, 'sell_income': 4})]
    assert not ledger.check_ledger_consistency(good2)   # 5+6-2+4=13
    # 缺 gold_before → 报(字段契约)
    miss = [_sim_ledger_checks_row()]
    del miss[0]['sim']['gold_before']
    assert ledger.check_ledger_consistency(miss)


# ==================== 写入器守卫:禁写生产流根(自 sim_ledger_checks 段迁入) ====================

def test_write_batch_ledger_guard() -> None:
    """写入器守卫:sim 账本禁写生产 live 流目录(自中毒防线)。

    禁写对象 = 生产流根(kernel/cw_observe.DEFAULT_REPLAY_DIR,单一源直调;
    曾硬抄旧路径字面量——根常量迁移即假绿,现随单一源走)。
    """
    from sr_od.application.currency_war.kernel.cw_observe import DEFAULT_REPLAY_DIR
    with pytest.raises(RuntimeError):
        write_batch_ledger([], DEFAULT_REPLAY_DIR)
