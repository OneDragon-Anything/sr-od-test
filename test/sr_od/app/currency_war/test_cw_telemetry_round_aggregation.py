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


# ===== 备战批量升级费括号(复盘 g_20260904_010335 专项②定谳)=====
# 根因不在读端乘法(合并流/逐实例计数均在),而在发射流:备战通道
# mandate M3 只发 1 个裸 LevelUp,执行器 prep_actions._level_up
# 「循环点至 level+1」批量展开,动作流 1:N 欠表达 → 旧码只入账单击
# luc(实证 1-2 差 4 金 / 1-3 差 16 金 / 1-9 差 24 金,三处同构)。
# 修 = 裸 LevelUp 载体帧(sid='' 单动作帧)按「载体帧 gold − 同轮下一帧
# gold」金差括号计实点击批费;商店通道 LevelUpShop 实例保持逐击计费。


def test_economy_prep_batch_bracket_gold_diff(tmp_path: Path) -> None:
    """1-9 形态重放:裸 LevelUp 载体帧 gold=49,批后帧 gold=21 → 花=28(7 击)。

    旧码只记 luc×1=4(差 24);括号金差 = 执行实况,与 gold 49→21 对拍一致。
    """
    _write_decisions(tmp_path, [
        _frame('g9', 1, 9, '2026-09-04T01:27:07', ['ClickSpheres'], gold=49),
        _frame('g9', 1, 9, '2026-09-04T01:27:22', ['LevelUp'], gold=49),
        _frame('g9', 1, 9, '2026-09-04T01:27:44', ['RunDeploy'], gold=21),
    ])
    lines = query_economy(tmp_path, 'g9')
    assert any('花=28' in ln for ln in lines), lines
    assert not any('花=28?' in ln for ln in lines), lines   # 括号有效,无兜底标记


def test_economy_prep_batch_plus_shop_channel_same_round(tmp_path: Path) -> None:
    """1-2 形态重放:同轮商店通道 LevelUpShop×1(4)+ 备战批括号(8→0=8)
    + BuyCard(1)→ 花=13(两通道各计各的,不互扰)。"""
    _write_decisions(tmp_path, [
        {'run_id': 'g2', 'plane': 1, 'round_num': 2,
         'ts': '2026-09-04T01:05:42', 'strategy_id': 'mandate_v1',
         'gold': 12, 'state': {'level_up_cost': 4},
         'actions': [{'__type__': 'BuyCard', 'card': {'name': '三月七', 'cost': 1}},
                     {'__type__': 'LevelUpShop', 'cost': 4}]},
        _frame('g2', 1, 2, '2026-09-04T01:06:35', ['LevelUp'], gold=8),
        _frame('g2', 1, 2, '2026-09-04T01:06:50', ['RunDeploy'], gold=0),
        _frame('g2', 1, 2, '2026-09-04T01:07:42', ['StartBattle'], gold=2),
    ])
    lines = query_economy(tmp_path, 'g2')
    assert any('花=13' in ln for ln in lines), lines


def test_economy_consecutive_bare_carriers_grouped_as_one_batch(tmp_path: Path) -> None:
    """连发裸载体帧并作一批(后帧也是载体 → 括号顺延),不重叠双计。"""
    _write_decisions(tmp_path, [
        _frame('gc', 1, 3, '2026-09-04T01:08:59', ['LevelUp'], gold=20),
        _frame('gc', 1, 3, '2026-09-04T01:09:05', ['LevelUp'], gold=20),
        _frame('gc', 1, 3, '2026-09-04T01:09:19', ['RunDeploy'], gold=4),
    ])
    lines = query_economy(tmp_path, 'gc')
    assert any('花=16' in ln for ln in lines), lines


def test_economy_bracket_invalid_falls_back_single_click_with_mark(tmp_path: Path) -> None:
    """括号无效(载体帧后无帧/金差 < 单击价)→ 回退单击 luc 并标 `?`(可辨)。"""
    _write_decisions(tmp_path, [
        _frame('gf', 1, 3, '2026-09-04T01:08:59', ['LevelUp'], gold=20),
    ])
    lines = query_economy(tmp_path, 'gf')
    assert any('花=4?' in ln for ln in lines), lines


def test_economy_plan_bare_deduped_when_carrier_present(tmp_path: Path) -> None:
    """计划帧裸 LevelUp 与载体帧同轮并存 → 撤计划口径(执行已被括号计费,防双计)。"""
    _write_decisions(tmp_path, [
        {'run_id': 'gd', 'plane': 1, 'round_num': 3,
         'ts': '2026-09-04T01:08:50', 'strategy_id': 'mandate_v1',
         'gold': 22, 'state': {'level_up_cost': 4},
         'actions': [{'__type__': 'LevelUp', 'cost': 4}]},
        _frame('gd', 1, 3, '2026-09-04T01:08:59', ['LevelUp'], gold=22),
        _frame('gd', 1, 3, '2026-09-04T01:09:19', ['RunDeploy'], gold=6),
    ])
    lines = query_economy(tmp_path, 'gd')
    assert any('花=16' in ln for ln in lines), lines   # 只括号 22→6,无 +4 双计


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
