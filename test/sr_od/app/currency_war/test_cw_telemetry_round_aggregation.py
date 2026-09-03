"""遥测逐轮聚合与升级动作口径锁(复盘 g_20260903_232823 C2/C3/C5 观测面修复)。

锁面(结构/存在性,不锁分布数值):
- C2:同轮载体帧(ClickSpheres/OpenShop/StartBattle,strategy_id='')与决策帧
  同为单动作时,旧「并列取末帧」让载体帧代表该轮 → 视图 买/升/刷 全计 0
  (实证:p1r1 决策迹有 BuyCard,rounds/supply 记「买0」)。锁 = 动作计数
  吃同轮全帧合并流,代表帧(state/gold 展示)仍取 ts 最晚(r363 语义保留)。
- C3:升级动作生产序列化落具体类名 ``LevelUpShop``(W970 §4.1.3,is-a
  LevelUp),sim 账本/旧数据落 ``LevelUp``——读端两型同桶,单一源 =
  query._LEVELUP_TYPES(实证:p1r2 发 LevelUpShop,economy 记「花=0」)。
- C5:羁绊对账 ok 分支 debug 行在疑截断行名非空时附带行名(mismatch=0
  稳定态行名可考);空列表保持旧行形。
"""
from __future__ import annotations

import json
from pathlib import Path

from sr_od.application.currency_war.telemetry.query import (
    _load_decisions_rounds,
    plan_gold_flow,
    query_economy,
    query_rounds,
    query_supply,
)


def _write_decisions(tmp_path: Path, rows: list[dict]) -> None:
    with (tmp_path / 'decisions.jsonl').open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _frame(run_id: str, plane: int, round_num: int, ts: str,
           types: list[str], gold: int = 10,
           strategy_id: str = '') -> dict:
    return {
        'run_id': run_id, 'plane': plane, 'round_num': round_num,
        'ts': ts, 'strategy_id': strategy_id, 'gold': gold,
        'actions': [{'__type__': t} for t in types],
        'state': {'gold': gold},
    }


# ===== C2:同轮全帧动作合并(载体帧不再淹没决策帧的动作) =====


def test_round_actions_merge_across_carrier_frames(tmp_path: Path) -> None:
    """r1 形态重放:5 帧各 1 动作,末帧 = StartBattle 载体帧。

    锁 = 合并流含 BuyCard(旧实现只回代表帧 actions → 买0);
    代表帧仍取 ts 最晚帧(r363 轮末 state 展示语义不变)。
    """
    _write_decisions(tmp_path, [
        _frame('r1', 1, 1, '2026-09-03T23:28:28', ['ClickSpheres']),
        _frame('r1', 1, 1, '2026-09-03T23:28:39', ['RunDeploy']),
        _frame('r1', 1, 1, '2026-09-03T23:29:01', ['OpenShop']),
        _frame('r1', 1, 1, '2026-09-03T23:29:08', ['BuyCard'],
               strategy_id='mandate_v1'),
        _frame('r1', 1, 1, '2026-09-03T23:29:27', ['StartBattle'], gold=7),
    ])
    best = _load_decisions_rounds(tmp_path, 'r1')
    merged = best[(1, 1)]['actions']
    got = [a.get('__type__') for a in merged]
    assert 'BuyCard' in got, f'合并流应含决策帧动作: {got}'
    # 代表帧 = ts 最晚(轮末账面),不是首帧
    assert best[(1, 1)].get('gold') == 7


def test_supply_view_buys_not_zero_with_carrier_frames(tmp_path: Path) -> None:
    """supply 视图端到端:载体帧环绕下「买了」清单可见(旧形记 买0)。"""
    _write_decisions(tmp_path, [
        _frame('r1', 1, 1, '2026-09-03T23:29:01', ['OpenShop']),
        {'run_id': 'r1', 'plane': 1, 'round_num': 1,
         'ts': '2026-09-03T23:29:08', 'strategy_id': 'mandate_v1',
         'gold': 5, 'state': {'gold': 5},
         'actions': [{'__type__': 'BuyCard',
                      'card': {'name': '椒丘', 'cost': 2}}]},
        _frame('r1', 1, 1, '2026-09-03T23:29:27', ['StartBattle']),
    ])
    lines = query_supply(tmp_path, 'r1')
    assert any("'椒丘'" in ln for ln in lines), lines


# ===== C3:升级动作 LevelUpShop/LevelUp 读端同桶 =====


def test_economy_spend_counts_levelupshop(tmp_path: Path) -> None:
    """r4 形态:单帧 4×LevelUpShop(生产序列化类名)→ 花=16(4×luc4)。

    旧实现只认 'LevelUp' → 生产局升级支出恒不计(花=0 假滞留)。
    """
    _write_decisions(tmp_path, [
        _frame('r4', 1, 4, '2026-09-03T23:36:19', ['OpenShop'], gold=22),
        {'run_id': 'r4', 'plane': 1, 'round_num': 4,
         'ts': '2026-09-03T23:36:26', 'strategy_id': 'mandate_v1',
         'gold': 22, 'state': {'level_up_cost': 4},
         'actions': [{'__type__': 'LevelUpShop', 'cost': 4}] * 4},
    ])
    lines = query_economy(tmp_path, 'r4')
    assert any('花=16' in ln for ln in lines), lines


def test_economy_spend_still_counts_legacy_levelup(tmp_path: Path) -> None:
    """sim 账本/旧数据基类名 'LevelUp' 同桶(small 回归:不因改读端丢旧口径)。"""
    _write_decisions(tmp_path, [
        {'run_id': 'lg', 'plane': 1, 'round_num': 2,
         'ts': '2026-09-03T23:30:55', 'strategy_id': 'mandate_v1',
         'gold': 7, 'state': {'level_up_cost': 4},
         'actions': [{'__type__': 'LevelUp', 'cost': 4}]},
    ])
    lines = query_economy(tmp_path, 'lg')
    assert any('花=4' in ln for ln in lines), lines


def test_rounds_view_counts_levelupshop(tmp_path: Path) -> None:
    """rounds 视图升级计数吃 LevelUpShop(升4 形;旧形恒 升0)。"""
    _write_decisions(tmp_path, [
        {'run_id': 'r4', 'plane': 1, 'round_num': 4,
         'ts': '2026-09-03T23:36:26', 'strategy_id': 'mandate_v1',
         'gold': 22, 'state': {'gold': 22},
         'actions': [{'__type__': 'LevelUpShop', 'cost': 4}] * 4},
    ])
    lines = query_rounds(tmp_path, 'r4')
    assert any('升4' in ln for ln in lines), lines


def test_plan_gold_flow_accepts_levelupshop() -> None:
    """逐项金流纯函数同桶:LevelUpShop 计支出(spend_ledger 分类器输入)。"""
    flow = plan_gold_flow([{'__type__': 'LevelUpShop', 'cost': 4}])
    assert flow['planned_spend'] == 4
    assert flow['items'][0]['target'] == 'level_up'


# ===== C5:ok 分支 debug 行附疑截断行名 =====


def test_faction_ok_line_appends_suspect_names() -> None:
    """疑截断行名非空 → 行内附带行名(mismatch=0 稳定态可溯源)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        faction_display_ok_debug_line,
    )
    line = faction_display_ok_debug_line(
        7, 1, ['持续伤害', '仙舟', '狼狩', '银河学者'], 0)
    assert 'trunc_suspect=4' in line
    assert '(持续伤害,仙舟,狼狩,银河学者)' in line


def test_faction_ok_line_empty_suspects_keeps_legacy_shape() -> None:
    """空疑截断列表 → 不附括号段(旧行形,判读 grep 兼容)。"""
    from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
        faction_display_ok_debug_line,
    )
    line = faction_display_ok_debug_line(6, 0, [], 0)
    assert 'trunc_suspect=0 computed_missing=0' in line
    assert 'trunc_suspect=0(' not in line
