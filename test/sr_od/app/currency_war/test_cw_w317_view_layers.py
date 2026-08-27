"""W317(G4 读端欠账):hp/anomalies 视图显示 killed/boss_names/node_type/词缀。

W244 建 outcomes 的 killed/boss_names/enemy_affixes 字段后,视图读端
未跟上——断层归因(这轮输给谁/词缀是什么)要另开窗口直查 jsonl。
本文件用 tmp_path 直写 jsonl 样本行锁定输出格式(直写而非走
record_outcome:锁的是「视图对已落盘行的渲染契约」,与写端解耦)。
"""
import json
from pathlib import Path

from sr_od.application.currency_war import cw_telemetry as tel

RID = 'w317'


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows),
                    encoding='utf-8')


def _outcome(plane: int, round_num: int, **kw) -> dict:
    """最小 outcome 样本行(视图只读这些键;缺省键模拟旧数据)。"""
    row = {
        'schema_version': 2, 'ts': '2026-08-28T00:00:00', 'run_id': RID,
        'plane': plane, 'round_num': round_num,
        'node_type': kw.pop('node_type', '普通战斗'),
        'hp_after': kw.pop('hp_after', 50),
    }
    row.update(kw)
    return row


def test_hp_view_shows_killed_boss(tmp_path: Path):
    """hp 行尾:killed(1/0/?)/boss_names(非空才显示,None 元素滤除)。"""
    _write_jsonl(tmp_path / 'outcomes.jsonl', [
        # 击杀 + boss 非空(含 None 位面占位,应滤除)
        _outcome(1, 1, hp_after=80, killed=True,
                 node_type='战斗', boss_names=['巨像之械', None, '拟造星曜']),
        # 未杀:killed=False → 0
        _outcome(1, 2, hp_after=60, killed=False, node_type='战斗'),
        # 旧数据无 killed/boss_names 键 → killed=? 且无 boss 段
        _outcome(1, 3, hp_after=40, node_type='boss'),
    ])
    lines = tel.query_hp(tmp_path, RID)
    assert len(lines) == 3
    # 锁格式:node_type 保持列内 + killed/boss 追加在行尾(单行可读)
    assert 'killed=1' in lines[0] and 'boss=[巨像之械|拟造星曜]' in lines[0]
    assert 'killed=0' in lines[1] and 'boss=' not in lines[1]
    assert 'killed=?' in lines[2] and 'boss=' not in lines[2]
    # 胜负分层语义:Δ 与 node_type 仍在(既有判读字段不回归)
    assert 'Δ=' in lines[0] and 'boss' in lines[2]


def test_anomalies_drop_line_shows_node_and_affixes(tmp_path: Path):
    """断层条目:[node_type] 标签 + 词缀(非空才显示)。"""
    _write_jsonl(tmp_path / 'outcomes.jsonl', [
        _outcome(1, 4, hp_after=100, killed=True, node_type='战斗'),  # 基线 hp
        _outcome(1, 5, hp_after=70, killed=False, node_type='boss',
                 enemy_affixes=['冷冻冬眠', '净化身心']),
        _outcome(1, 6, hp_after=30, killed=False, node_type='战斗',
                 enemy_affixes=[]),  # 词缀空 → 不显示词缀段
    ])
    lines = tel.query_anomalies(tmp_path, RID)
    drop = [ln for ln in lines if '战力断层' in ln]
    assert len(drop) == 2
    assert 'p1r6 [战斗] 单轮掉血 70→30(战力断层)' in drop[1]
    assert 'p1r5 [boss] 单轮掉血' in drop[0]
    assert '词缀=冷冻冬眠 净化身心' in drop[0]
    assert '词缀=' not in drop[1]


def test_anomalies_gold_line_shows_node_type(tmp_path: Path):
    """钱变不成板条目:补所在轮 node_type(decisions.state 直读)。"""
    _write_jsonl(tmp_path / 'decisions.jsonl', [
        {'schema_version': 2, 'ts': '2026-08-28T00:00:00', 'run_id': RID,
         'plane': 1, 'round_num': 2, 'actions': [], 'gold': 50,
         'state': {'gold': 50, 'node_type': '普通战斗'},
         'eval_breakdown': {}},
        {'schema_version': 2, 'ts': '2026-08-28T00:01:00', 'run_id': RID,
         'plane': 1, 'round_num': 3, 'actions': [], 'gold': 0,
         'state': {'gold': 0, 'node_type': ''},   # node_type 缺 → 无标签
         'eval_breakdown': {'plan_error': 'boom'}},
    ])
    lines = tel.query_anomalies(tmp_path, RID)
    gold_ln = [ln for ln in lines if '钱变不成板' in ln]
    assert gold_ln == ['p1r2 [普通战斗] 金50 0买0升(钱变不成板)']
    plan_ln = [ln for ln in lines if 'plan_error' in ln]
    # 无 node_type:标签段整体省略(与 rounds 视图 [_tag] 风格一致)
    assert plan_ln == ['p1r3 plan_error(决策崩溃,见 log)']
