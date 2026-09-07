"""invest 归属重算脚本行为锁(tools/cw/repair_invest_attribution.py,ADR-0588)。

被测工具 = 主仓 ``tools/cw/repair_invest_attribution.py``,经 importlib 按路径
装载(先例:test_cw_replay_to_md.py 装载 replay_to_md.py)。fixture 全
tmp_path(测试零真实 .debug/ 副作用;工具的 journal 落点模块常量随批
monkeypatch 指向 tmp)。

锁面(ADR-0588 方案 §4.2):
- 迷你库 dry-run:重算计划正确(重归属/窗内合法/活局尾部/人工审分型)+
  零落盘 + 恒等自检通过;
- recovered 收口(ADR-0273 回填,ts=名义窗尾)与无收口两种失真形态的行
  入「疑似串门-人工审」且 --apply 零改动(修3 补洞锁);
- --apply:V1 行数与分 kind 计数不变 / 污染行换戳 / 备份存在且只建一次 /
  真主档案补行重建(chosen_env 与最早 decisions active_env 对齐);
- 幂等:二次 --apply = 0 行待改,备份不被二次覆盖。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOOL_PATH = _REPO_ROOT / 'tools' / 'cw' / 'repair_invest_attribution.py'
_MODULE_NAME = 'cw_repair_invest_attribution_tool'

# 迷你库时间线(ISO 秒级;字典序 = 时间序)。run_id 用真实格式
# (run_YYYYMMDD_HHMMSS):game_id 由 run_id 派生,归档断言依赖真实形态。
_RUN_A = 'run_20260907_084010'
_RUN_B = 'run_20260907_084830'
_RUN_REC = 'run_20260907_090400'
_RUN_D = 'run_20260907_091200'
_GID_A = 'g_20260907_084010'
_GID_B = 'g_20260907_084830'
_TS_A = '2026-09-07T08:42:10'
_TS_B = '2026-09-07T08:54:32'
_TS_REC = '2026-09-07T09:20:00'

_TOOL: Any = None


def _load_tool() -> Any:
    """按路径装载被测工具(模块级缓存,跨用例只 exec 一次)。"""
    global _TOOL
    if _TOOL is None:
        spec = importlib.util.spec_from_file_location(_MODULE_NAME,
                                                      _TOOL_PATH)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(_MODULE_NAME, mod)
        spec.loader.exec_module(mod)
        _TOOL = mod
    return _TOOL


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """按写端 append_jsonl 同参数写迷你流行(ensure_ascii=False,默认分隔符)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _read_lines(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding='utf-8').splitlines()
            if ln.strip()]


def _invest_row(ts: str, run_id: str, kind: str, name: str) -> dict[str, Any]:
    return {'schema_version': 1, 'ts': ts, 'run_id': run_id, 'kind': kind,
            'idx': 0, 'name': name, 'x': 300, 'effect_text': 'e',
            'chosen': True}


@pytest.fixture()
def mini_lib(tmp_path: Path) -> Path:
    """迷你库:两正常收口 + 一 recovered 回填收口 + 一无收口崩局 + 5 行
    invest(覆盖重算全部判定支);decisions/outcomes 足以分出两个 game。"""
    _write_jsonl(tmp_path / 'runs.jsonl', [
        {'ts': _TS_A, 'run_id': _RUN_A, 'difficulty': 'A8', 'result': 'win',
         'plane_reached': 1, 'rounds_survived': 2, 'final_hp': 30},
        {'ts': _TS_B, 'run_id': _RUN_B, 'difficulty': 'A8', 'result': 'loss',
         'plane_reached': 1, 'rounds_survived': 3, 'final_hp': 0},
        {'ts': _TS_REC, 'run_id': _RUN_REC, 'difficulty': 'A8',
         'result': 'abandoned', 'plane_reached': 1, 'rounds_survived': 2,
         'final_hp': 40, 'source': 'recovered'},
    ])
    _write_jsonl(tmp_path / 'decisions.jsonl', [
        {'ts': '2026-09-07T08:40:00', 'run_id': _RUN_A, 'plane': 1,
         'round_num': 1, 'state': {'active_env': ''}, 'target_comp': '',
         'actions': []},
        {'ts': '2026-09-07T08:50:02', 'run_id': _RUN_B, 'plane': 1,
         'round_num': 1, 'state': {'active_env': '甲'}, 'target_comp': '',
         'actions': []},
    ])
    _write_jsonl(tmp_path / 'outcomes.jsonl', [
        {'ts': '2026-09-07T08:42:09', 'run_id': _RUN_A, 'plane': 1,
         'round_num': 1},
        {'ts': '2026-09-07T08:54:31', 'run_id': _RUN_B, 'plane': 1,
         'round_num': 1},
    ])
    _write_jsonl(tmp_path / 'invest_cards.jsonl', [
        _invest_row('2026-09-07T08:44:12', _RUN_A, 'env', '甲'),    # 污染行:盖上局 → 重归属 _RUN_B
        _invest_row('2026-09-07T08:50:00', _RUN_B, 'strategy', 'S1'),  # 窗内合法
        _invest_row('2026-09-07T09:05:00', _RUN_REC, 'env', '丙'),  # recovered 收口 → 人工审
        _invest_row('2026-09-07T09:10:00', _RUN_D, 'env', '丁'),    # 无收口崩局 → 人工审
        _invest_row('2026-09-07T09:55:00', _RUN_REC, 'env', '戊'),  # 活局尾部
    ])
    # 预建两局档案(修复前状态:run_a 局档案错收污染行)
    from sr_od.application.currency_war.telemetry.match_archive import (
        assemble_game,
    )
    assert assemble_game(tmp_path, _GID_A) is not None, '迷你库须能装配 run_a 局'
    assert assemble_game(tmp_path, _GID_B) is not None, '迷你库须能装配 run_b 局'
    return tmp_path


def _plan_of(replay_dir: Path) -> Any:
    tool = _load_tool()
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    rows = read_jsonl(replay_dir / 'invest_cards.jsonl')
    closes = tool._load_closes(read_jsonl(replay_dir / 'runs.jsonl'))
    return tool.plan_repair(rows, closes,
                            tool._latest_ts_by_run(replay_dir))


def test_dry_run_plan_classifies_all_branches(mini_lib: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """计划分型正确 + 恒等自检零失败 + dry-run 零落盘(行字节/档案不变)。"""
    tool = _load_tool()
    before = _read_lines(mini_lib / 'invest_cards.jsonl')
    archives_before = sorted(p.name for p in
                             (mini_lib / 'matches').glob('match_*.json'))
    rc = tool.main(['--replay-dir', str(mini_lib)])
    assert rc == 0
    plan = _plan_of(mini_lib)
    by_action: dict[str, list[Any]] = {}
    for v in plan.verdicts:
        by_action.setdefault(v.action, []).append(v)
    re_rows = by_action.get('reattribute', [])
    assert [(v.line_no, v.old_run_id, v.new_run_id) for v in re_rows] \
        == [(1, _RUN_A, _RUN_B)], '污染行(盖上局)重归属本局收口'
    assert [v.line_no for v in by_action.get('keep_window', [])] == [2]
    assert [v.line_no for v in by_action.get('keep_live_tail', [])] == [5]
    # 修3 补洞:两种收口失真形态都入人工审,且判定先于 owner 规则
    manual = {ln: why for ln, _, _, _, why in plan.manual_review}
    assert set(manual) == {3, 4}
    assert plan.roundtrip_mismatch == []
    out = capsys.readouterr().out
    assert '疑似串门-人工审(2 行' in out
    assert 'dry-run(零落盘)' in out
    assert _read_lines(mini_lib / 'invest_cards.jsonl') == before
    assert sorted(p.name for p in
                  (mini_lib / 'matches').glob('match_*.json')) \
        == archives_before, 'dry-run 不得触发档案重建'


def test_apply_rewrites_rows_and_rebuilds_true_owner_archive(
        mini_lib: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """--apply:V1 行数/分 kind 计数不变;污染行换戳;人工审与活局尾行
    保持原样;备份单次;真主档案(run_b 局)补行且 chosen_env 对齐最早
    decisions active_env;journal 落 monkeypatch 指定的 tmp 目录。"""
    tool = _load_tool()
    monkeypatch.setattr(tool, '_JOURNAL_DIR', mini_lib / 'journals')
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    rc = tool.main(['--replay-dir', str(mini_lib), '--apply'])
    assert rc == 0
    rows = read_jsonl(mini_lib / 'invest_cards.jsonl')
    assert len(rows) == 5   # V1:行数不变
    assert {r['kind'] for r in rows} == {'env', 'strategy'}
    assert rows[0]['run_id'] == _RUN_B, '污染行重归属本局'
    assert rows[1]['run_id'] == _RUN_B and rows[1]['kind'] == 'strategy'
    assert rows[2]['run_id'] == _RUN_REC, '人工审行不自动改'
    assert rows[3]['run_id'] == _RUN_D, '无收口形态不自动改'
    assert rows[4]['run_id'] == _RUN_REC, '活局尾行保持'
    # 备份:存在、内容 = 原始 5 行、只建一份
    baks = list(mini_lib.glob('invest_cards.jsonl.bak-*'))
    assert len(baks) == 1
    assert len(_read_lines(baks[0])) == 5
    assert json.loads(_read_lines(baks[0])[0])['run_id'] == _RUN_A
    # 真主档案重建:run_b 局收进开局行,chosen_env 与最早 active_env 对齐(V3)
    archive = json.loads(
        (mini_lib / 'matches' / f'match_{_GID_B}.json')
        .read_text(encoding='utf-8'))
    chosen = [r.get('name') for r in archive['slices']['invest_cards.jsonl']
              if r.get('kind') == 'env' and r.get('chosen')]
    assert chosen == ['甲'], f'修后 chosen_env 应为开局真值,实得 {chosen!r}'
    # 被抽走行的污染档案同样重建(run_a 局不再持有 run_b 的行)
    archive_a = json.loads(
        (mini_lib / 'matches' / f'match_{_GID_A}.json')
        .read_text(encoding='utf-8'))
    assert all(r.get('run_id') != _RUN_B
               for r in archive_a['slices']['invest_cards.jsonl'])
    journals = list((mini_lib / 'journals').glob('repair_journal-*.json'))
    assert len(journals) == 1
    journal = json.loads(journals[0].read_text(encoding='utf-8'))
    assert len(journal['changed_rows']) == 1
    assert journal['changed_rows'][0]['old_run_id'] == _RUN_A
    assert len(journal['manual_review']) == 2, '人工审行只点名不改,入 journal 留痕'
    assert '--apply 完成' in capsys.readouterr().out


def test_apply_idempotent_second_run_keeps_backup(
        mini_lib: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """幂等(V5):重归属后 owner==stamped 全库成立 → 二次 --apply = 0 行
    待改;备份存在即拒,不被二次覆盖。"""
    tool = _load_tool()
    monkeypatch.setattr(tool, '_JOURNAL_DIR', mini_lib / 'journals')
    assert tool.main(['--replay-dir', str(mini_lib), '--apply']) == 0
    capsys.readouterr()
    bak = next(mini_lib.glob('invest_cards.jsonl.bak-*'))
    bak_before = bak.read_text(encoding='utf-8')
    rc = tool.main(['--replay-dir', str(mini_lib), '--apply'])
    assert rc == 0
    assert '0 行待改' in capsys.readouterr().out
    assert len(list(mini_lib.glob('invest_cards.jsonl.bak-*'))) == 1
    assert bak.read_text(encoding='utf-8') == bak_before
    # apply 后档案影响面清零(全部已重建对齐)
    rows = _read_lines(mini_lib / 'invest_cards.jsonl')
    parsed = [json.loads(ln) for ln in rows]
    assert tool._affected_archives(mini_lib, parsed) == []


def test_v6_classification_and_v3_truth_from_archive_slices(tmp_path: Path) -> None:
    """落地审 F1/F2 回归锁(合成手写档案,helper 级直调):

    F1 — V6 空档案归因的 first_frame 判据:JSON 反序列化的 first_frame 是
    list,与 tuple (1,1) 直接比较恒不等(bug 曾把全部空档案误归①)。锁面:
    p1r1 局(首段 [1,1])带人工审 run 行 → 归④;p1r1 局无行 → 归②③;
    非法续段首帧([2,3])孤立局 → 归①。
    F2 — V3 真值源 = 档案内嵌 decisions 切片:根 decisions 流缺席(轮转
    形态)时对拍仍执行(checked≥1),不空转假阴。
    """
    tool = _load_tool()
    md = tmp_path / 'matches'
    md.mkdir(parents=True)

    def _write_archive(gid: str, segments: list[dict],
                       invest: list[dict], dec: list[dict]) -> None:
        with (md / f'match_{gid}.json').open('w', encoding='utf-8') as f:
            json.dump({'game_id': gid, 'segments': segments,
                       'slices': {'invest_cards.jsonl': invest,
                                  'decisions.jsonl': dec}},
                      f, ensure_ascii=False)

    crash_row = _invest_row('2026-09-07T09:10:00', 'run_crash', 'strategy',
                            'S9')
    # ④形态:p1r1 局 + 续段(崩局 run,人工审名单内)带 strategy 行
    _write_archive(
        'g_a',
        [{'run_id': 'run_m1', 'first_frame': [1, 1]},
         {'run_id': 'run_crash', 'first_frame': [2, 1]}],
        [crash_row],
        [{'ts': '2026-09-07T09:00:00', 'run_id': 'run_m1',
          'state': {'active_env': 'X'}, 'active_strategies': ['S9']}])
    # ①形态:孤立续段局(首帧 [2,3]),无 invest 行
    _write_archive('g_c', [{'run_id': 'run_iso', 'first_frame': [2, 3]}],
                   [], [])
    # ②③形态:p1r1 局,无 invest 行
    _write_archive('g_b', [{'run_id': 'run_m2', 'first_frame': [1, 1]}],
                   [], [])

    v6 = tool._v6_reconciliation(tmp_path, [crash_row], {'run_crash'})
    assert v6['  ①恢复局合法空(首段非(p1,r1))'] == ['g_c']
    assert v6['  ④前局硬崩串门嫌疑(行入人工审)'] == ['g_a'], (
        'p1r1 局首帧 [1,1](list)不得误判非 (1,1)(F1 恒真 bug 回归锁)')
    assert v6['  ②冷启动零行∨③真无选卡屏(离线不可分,人工判读)'] == ['g_b']

    lines, checked_env, checked_strat = tool._v3_cross_check(tmp_path,
                                                             [crash_row])
    assert checked_strat == 1, (
        '根 decisions 流缺席时真值仍须取自档案切片(F2 空转假阴回归锁)')
    assert checked_env == 0
    assert lines == [], '开局选择 ∈ 最早真值集时不得报 mismatch'
    # 位面过渡改选合法累积:chosen 序列 [开局, 改选] 只对拍首项 → 仍无 mismatch
    repick = _invest_row('2026-09-07T09:40:00', 'run_crash', 'strategy', 'S10')
    lines2, _, checked_strat2 = tool._v3_cross_check(tmp_path,
                                                     [crash_row, repick])
    assert checked_strat2 == 1 and lines2 == [], (
        '改选行累积不得把开局对拍打红(真值锚只取最早帧)')
