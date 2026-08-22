# -*- coding: utf-8 -*-
"""①② 账本+checks 契约锁(合成账本双向断言——检查器自身的回归网)。

锁防锁(防「永远绿」):每条检查器用坏/好合成账本双向锁——
坏必报(防静默失效)、好必过(防误报)。真实 sim 批次的分布级
行为不在此锁(锁分布数值 = change-detector 陷阱)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war import cw_sim_checks as chk
from sr_od.application.currency_war.cw_sim import write_batch_ledger


def _row(round_num: int = 1, gold: int = 10, gold_before: int = 5,
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
    bad = [_row(gold=99)]   # 5+6≠99
    assert chk.check_ledger_consistency(bad), '坏账本未报警=静默失效'
    good = [_row(gold=11)]  # 5+6=11
    assert not chk.check_ledger_consistency(good)
    # 卖回金计收入侧
    good2 = [_row(gold=13, spend={'buys': {'line': 2}, 'levelup': 0,
                                  'refresh': 0, 'sell_income': 4})]
    assert not chk.check_ledger_consistency(good2)   # 5+6-2+4=13
    # 缺 gold_before → 报(字段契约)
    miss = [_row()]
    del miss[0]['sim']['gold_before']
    assert chk.check_ledger_consistency(miss)


def test_coldstart_check_bidirectional() -> None:
    """局49 指纹:白名单外 reason 必报;方向件/已有方向不报。"""
    bad = [_row(actions=[{'__type__': 'BuyCard', 'name': '翡翠',
                          'cost': 1, 'reason': 'pair'}])]
    v = chk.check_coldstart_seed_squander(bad)
    assert v and '翡翠' in v[0]
    good = [_row(actions=[{'__type__': 'BuyCard', 'name': '丹恒·饮月',
                           'cost': 1, 'reason': 'bridge_seed'}])]
    assert not chk.check_coldstart_seed_squander(good)
    # 已有方向(r1 即锁线)非冷启动形态 → 不报
    directed = [_row(target_comp='v2:jizi_train',
                     actions=[{'__type__': 'BuyCard', 'name': '翡翠',
                               'cost': 1, 'reason': 'pair'}])]
    assert not chk.check_coldstart_seed_squander(directed)


def test_run_checks_report_shape() -> None:
    """批量检查报告形:violations 计数 + 局索引(供 seed 重放)。"""
    ledgers = [[_row(gold=11)], [_row(gold=99)], [_row(gold=11)]]
    rep = chk.run_checks_on_ledgers(ledgers)
    assert rep['ledger_consistency']['violations'] == 1
    assert rep['ledger_consistency']['games'] == [1]


def test_write_batch_ledger_guard() -> None:
    """写入器守卫:sim 账本禁写生产 replay 目录(自中毒防线)。"""
    with pytest.raises(RuntimeError):
        write_batch_ledger([], Path('.debug/temp/currency_war/replay'))


def test_checks_module_does_not_import_sim() -> None:
    """依赖方向:checks 不 import cw_sim(二轮#7;调用方传账本)。"""
    import inspect
    src = inspect.getsource(chk)
    assert 'import cw_sim' not in src and 'from sr_od' not in src
