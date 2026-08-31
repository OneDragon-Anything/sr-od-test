# -*- coding: utf-8 -*-
"""①② 账本+checks 契约锁(合成账本双向断言——检查器自身的回归网)。

锁防锁(防「永远绿」):每条检查器用坏/好合成账本双向锁——
坏必报(防静默失效)、好必过(防误报)。真实 sim 批次的分布级
行为不在此锁(锁分布数值 = change-detector 陷阱)。


出处:被其他测试文件引用(防断链保留,需后续人工归并)(2026-08-31 测试瘦身批考证补记)。"""
from __future__ import annotations

from pathlib import Path

import pytest

from sr_od.application.currency_war.sim.checks import ledger, runner
from sr_od.application.currency_war.sim.runner import write_batch_ledger


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
    assert ledger.check_ledger_consistency(bad), '坏账本未报警=静默失效'
    good = [_row(gold=11)]  # 5+6=11
    assert not ledger.check_ledger_consistency(good)
    # 卖回金计收入侧
    good2 = [_row(gold=13, spend={'buys': {'line': 2}, 'levelup': 0,
                                  'refresh': 0, 'sell_income': 4})]
    assert not ledger.check_ledger_consistency(good2)   # 5+6-2+4=13
    # 缺 gold_before → 报(字段契约)
    miss = [_row()]
    del miss[0]['sim']['gold_before']
    assert ledger.check_ledger_consistency(miss)


def test_coldstart_check_bidirectional() -> None:
    """局49 指纹(r371b 语义):开局轮 reason∈{pair,off} 必报;
    方向件/其它通道/非开局轮不报。

    ⚠ reason 空间=self-attack 修正:_want_label 的 pair 谓词分支
    返回 classify_buy **身份**——门失效的线外件 reason='pair'
    (同阵营)或 'off'(异阵营=局49 原始形态,翡翠/大丽花对空板
    A5 门)。只查 'pair' 会漏掉局49 原始形态。
    """
    # 坏:异阵营线外(reason=off)——局49 原始形态
    bad = [{'plane': 1, 'round_num': 1, 'target_comp': '',
            'actions': [{'__type__': 'BuyCard',
                         'card': {'name': '翡翠', 'cost': 1},
                         'reason': 'off', 'channel': 'off'}]}]
    v = ledger.check_coldstart_seed_squander(bad)
    assert v and '翡翠' in v[0]
    # 坏:局53 形态(系统 bench 带卡,同阵营线外)
    bad2 = [{'plane': 1, 'round_num': 2, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '阿格莱雅', 'cost': 1},
                          'reason': 'pair', 'channel': 'pair'}]}]
    assert ledger.check_coldstart_seed_squander(bad2)
    # 好:pair 谓词放行的方向件(reason=身份=bridge_seed)
    good = [{'plane': 1, 'round_num': 1, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '丹恒·饮月', 'cost': 1},
                          'reason': 'bridge_seed',
                          'channel': 'bridge_seed'}]}]
    assert not ledger.check_coldstart_seed_squander(good)
    # 好:其它通道(line/emergency)不辖于门
    other = [{'plane': 1, 'round_num': 1, 'target_comp': '',
              'actions': [{'__type__': 'BuyCard',
                           'card': {'name': '翡翠', 'cost': 1},
                           'reason': 'emergency', 'channel': 'off'}]}]
    assert not ledger.check_coldstart_seed_squander(other)
    # 好:非开局轮(r3+)pair 凑对恢复旧语义(r371b 回归点)
    late = [{'plane': 1, 'round_num': 3, 'target_comp': '',
             'actions': [{'__type__': 'BuyCard',
                          'card': {'name': '翡翠', 'cost': 1},
                          'reason': 'pair', 'channel': 'pair'}]}]
    assert not ledger.check_coldstart_seed_squander(late)
    # decision_v2 栈:reason 带 d2_ 前缀(+'_merge' 尾,arbiter
    # _materialize)——归一化后同指纹必报(防对新栈无声失效,
    # 2026-08-24 leader 核实观察局首验)
    d2bad = [{'plane': 1, 'round_num': 1, 'target_comp': '',
              'actions': [{'__type__': 'BuyCard',
                           'card': {'name': '翡翠', 'cost': 1},
                           'reason': 'd2_off', 'channel': 'off'}]}]
    v2 = ledger.check_coldstart_seed_squander(d2bad)
    assert v2 and '翡翠' in v2[0]
    d2bad2 = [{'plane': 1, 'round_num': 2, 'target_comp': '',
               'actions': [{'__type__': 'BuyCard',
                            'card': {'name': '阿格莱雅', 'cost': 1},
                            'reason': 'd2_pair_merge',
                            'channel': 'pair'}]}]
    assert ledger.check_coldstart_seed_squander(d2bad2)
    d2good = [{'plane': 1, 'round_num': 1, 'target_comp': '',
               'actions': [{'__type__': 'BuyCard',
                            'card': {'name': '丹恒·饮月', 'cost': 1},
                            'reason': 'd2_engine_seed',
                            'channel': 'engine_seed'}]}]
    assert not ledger.check_coldstart_seed_squander(d2good)


def test_coldstart_check_in_batch_set() -> None:
    """r371b 后局49 检查进批量集(sim 批次自动扫)。"""
    assert 'coldstart_direction' in runner._BATCH_CHECKS


def test_run_checks_report_shape() -> None:
    """批量检查报告形:violations 计数 + 局索引(供 seed 重放)。"""
    ledgers = [[_row(gold=11)], [_row(gold=99)], [_row(gold=11)]]
    rep = runner.run_checks_on_ledgers(ledgers)
    assert rep['ledger_consistency']['violations'] == 1
    assert rep['ledger_consistency']['games'] == [1]


def test_write_batch_ledger_guard() -> None:
    """写入器守卫:sim 账本禁写生产 replay 目录(自中毒防线)。"""
    with pytest.raises(RuntimeError):
        write_batch_ledger([], Path('.debug/temp/currency_war/replay'))


def test_checks_module_does_not_import_sim() -> None:
    """依赖方向:checks 不 import cw_sim(二轮#7;调用方传账本)。

    r405 修订:原断言 `'from sr_od' not in src` 过宽——新检查
    (no_component_equipped_p1)合法 lazy-import cw_synthesis.
    RESERVED_COMPONENTS(叶子模块,单一源纪律;压测经济批规格),
    非循环依赖。锁收窄到本意:不 import cw_sim(AST 级判,免疫
    docstring 字样)。
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(runner))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            continue
        for n in names:
            assert 'cw_sim' not in n, f'checks 不得 import cw_sim: {n}'


