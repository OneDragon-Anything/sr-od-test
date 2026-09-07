"""对局档案 → markdown 复盘渲染器(tools/cw/replay_to_md.py)的行为锁。

被测工具 = 主仓 ``tools/cw/replay_to_md.py``(纯 stdlib,零 src 导入),
经 importlib 按路径装载(先例:test_cw_v6_cleanup.py 装载 ab_judge.py)。

锁面三件(与任务口径一致):
1. **真档 smoke**:渲染 g_20260907_075840 实机档案不断言数值,只锁
   结构(四大节 + 每轮一块判定三槽)。真档是本地易失产物(纪律 19:
   禁读 .debug 当断言锚的例外面 = 存在性门槛 + 结构断言,数据缺失即
   skip,不锁任何会随重装配漂移的数值/缺口条目)。
2. **字段缺省容忍**:最小合成档案(绝大多数键缺)渲染不炸,缺槽打
   「(无此数据)」并进缺口清单。
3. **空档汇总**:空档案的缺口汇总节存在;全字段齐备的合成档案缺口
   清单为空(反向锁:缺口追踪器零假阳性——假缺口会污染遥测缺口
   清单的判读价值,这条红 = 渲染器在冤枉数据)。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOOL_PATH = _REPO_ROOT / 'tools' / 'cw' / 'replay_to_md.py'
#: 实机档案位置(工具的缺省 replay 目录;本地易失,缺席 skip)
_REAL_REPLAY_DIR = _REPO_ROOT / '.debug' / 'temp' / 'currency_war' / 'replay'
_REAL_GAME_ID = 'g_20260907_075840'

_MODULE_NAME = 'cw_replay_to_md_tool'


def _load_tool() -> Any:
    """按路径装载被测工具(模块级缓存,跨用例只 exec 一次)。"""
    import importlib.util

    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


class TestSmokeRealArchive:
    """真档 smoke:渲染 075840,只锁结构与判定槽密度(纪律:形状锁)。"""

    def test_render_real_archive_structure(self, tmp_path: Path) -> None:
        mod = _load_tool()
        archive_path = _REAL_REPLAY_DIR / 'matches' / f'match_{_REAL_GAME_ID}.json'
        if not archive_path.exists():
            pytest.skip(f'本地易失档案不存在: {archive_path}')
        archive = json.loads(archive_path.read_text(encoding='utf-8'))
        md = mod.render_match(archive, _REAL_REPLAY_DIR)

        assert md.startswith(f'# 货币战争复盘 {_REAL_GAME_ID}')
        for section in ('## 1. 局头', '## 2. 逐轮复盘',
                        '## 3. 全局', '## 4. 本次未能渲染的字段'):
            assert section in md, section
        # 判定三槽:每轮备战帧块尾一组,槽行数与轮数相等(结构性:
        # 一轮一块三槽;槽文案由工具 JUDGMENT_SLOTS 常量承载)
        n_rounds = len(archive.get('rounds') or [])
        assert n_rounds > 0
        assert md.count(mod.JUDGMENT_SLOTS[0]) == n_rounds
        assert mod.JUDGMENT_SLOTS[1] in md and mod.JUDGMENT_SLOTS[2] in md
        # CLI 路径同源:--out 写 tmp_path(纪律 2:不落真实 .debug)
        out = tmp_path / 'review.md'
        rc = mod.main(['--match', _REAL_GAME_ID, '--out', str(out)])
        assert rc == 0
        assert out.exists() and out.read_text(encoding='utf-8').startswith('# ')

    def test_main_missing_archive_exit_code(self, tmp_path: Path) -> None:
        """CLI 对不存在的档案返回退出码 2(不抛栈,给装配指引)。"""
        mod = _load_tool()
        rc = mod.main(['--match', 'g_no_such_game', '--replay-dir',
                       str(tmp_path)])
        assert rc == 2


def _minimal_archive() -> dict[str, Any]:
    """最小合成档案:除 game_id 外全缺(字段缺省容忍的输入面)。"""
    return {'game_id': 'g_test_min', 'schema_version': 1}


class TestFieldMissingTolerance:
    """字段缺省容忍:缺槽打「(无此数据)」+ 缺口清单,渲染不炸。"""

    def test_minimal_archive_renders_without_raise(self) -> None:
        mod = _load_tool()
        md = mod.render_match(_minimal_archive(), _REPO_ROOT / 'no_such_dir')

        assert '# 货币战争复盘 g_test_min' in md
        assert mod.MISSING in md
        # 无轮数据时显式声明,不静默留白
        assert '档案无逐轮数据' in md
        # 缺口清单必须记录顶层缺列
        assert '## 4. 本次未能渲染的字段' in md
        assert '`rounds`' in md
        assert '`endgame`' in md
        # 零轮 → 零判定槽(槽只在轮块内)
        assert md.count(mod.JUDGMENT_SLOTS[0]) == 0

    def test_bare_round_renders_slots_and_gap(self) -> None:
        """只有轮键的轮行:三槽照出,该轮缺的字段进缺口清单。"""
        mod = _load_tool()
        archive = _minimal_archive() | {
            'rounds': [{'plane': 1, 'round': 1}],
            'resume_reconciliation': [],
        }
        md = mod.render_match(archive, _REPO_ROOT / 'no_such_dir')

        assert mod.JUDGMENT_SLOTS[0] in md
        assert md.count(mod.JUDGMENT_SLOTS[2]) == 1
        assert '`rounds[].gold`' in md
        assert '`rounds[].actions`' in md


class TestEmptyArchiveGapSummary:
    """空档汇总:空档案缺口节存在;全字段档案缺口为零(零假阳性锁)。"""

    def test_all_empty_archive_has_gap_section(self) -> None:
        mod = _load_tool()
        archive = _minimal_archive() | {
            'rounds': [], 'segments': [], 'resume_reconciliation': [],
            'cw4_counters': {}, 'slices': {},
        }
        md = mod.render_match(archive, _REPO_ROOT / 'no_such_dir')

        assert '## 4. 本次未能渲染的字段' in md
        assert mod.MISSING in md
        # cw4_counters 空 dict = 真实零计数,不是缺口(与 None 分型)
        assert '局内真实零计数' in md
        assert '`cw4_counters' not in md

    def test_full_archive_zero_false_gaps(self, tmp_path: Path) -> None:
        """全字段齐备的合成档案:缺口清单必须为空。

        这条锁的是缺口追踪器的准确率——任何「数据其实在、渲染器却喊缺」
        的假阳性都会污染真档判读(缺口清单唯一价值 = 差异信噪比)。
        """
        mod = _load_tool()
        # 空 obs_conflicts.jsonl 落 tmp_path(工具对「文件存在但空」不记缺口)
        (tmp_path / 'obs_conflicts.jsonl').write_text('', encoding='utf-8')
        archive = {
            'game_id': 'g_test_full', 'schema_version': 9,
            'start_ts': '2026-01-01T00:00:00',
            'end_ts': '2026-01-01T01:00:00',
            'continuity_note': '',
            'cw4_counters': {'advisor_armed': 2},
            'strategy_version': {'code_commit': 'abc1234',
                                 'registry_fingerprint': 'deadbeef'},
            'segments': [{'run_id': 'run_x', 'first_frame': [1, 1],
                          'summary': {
                              'result': 'win', 'difficulty': 'A3',
                              'rounds_survived': 1, 'final_hp': 100,
                              'gold_trajectory': [10],
                              'comps_committed': ['配方甲'], 'pivot_count': 0}}],
            'resume_reconciliation': [],
            'hp_events': [], 'hp_pay_defects': [], 'loss_nodes': [],
            'opening': {
                'difficulty': 'A3',
                'invest_cards': [{'kind': 'strategy', 'idx': 0,
                                  'name': '卡名', 'chosen': True,
                                  'effect_text': '效果'}],
                'chosen_strategies': ['卡名']},
            'endgame': {'result': 'win', 'abandoned': False,
                        'plane_reached': 1, 'rounds_survived': 1,
                        'final_hp': 100, 'difficulty': 'A3'},
            'rounds': [{
                'plane': 1, 'round': 1, 'node_type': '普通战斗',
                'node_type_source': 'settlement',
                'hp': 100, 'hp_source': 'settlement', 'hp_trusted': True,
                'hp_delta': None, 'gold': 10, 'gold_readable': True,
                'level': 3, 'xp_progress': [0, 4],
                'actions': [{'__type__': 'BuyCard', 'card': {
                    'name': '角色甲', 'star': 1, 'cost': 1}, 'cost': 1,
                    'reason': 'm2_line_member', 'char_id': '角色甲'}],
                'action_counts': {'BuyCard': 1},
                'sess_p1_pair': '', 'target_comp': '配方甲',
                'board': {'羁绊一': 1},
                'terminal': {'deployed_count': 1, 'bench_count': 0,
                             'equips_worn': 0, 'equips_owned': 0},
                'terminal_closure': 'start_battle',
                'decision_detail': {
                    'v3_intention': {'phase': 'locked',
                                     'locked_comp': '配方甲',
                                     'forced': False},
                    'candidate_scores': {}, 'eval_breakdown': {},
                    'shop_rejects': {}},
                'outcome': {'node_type': '普通战斗', 'comp_tag': '配方甲',
                            'boss_names': ['Boss甲'], 'enemy_hp_after': None,
                            'hp_after': 100, 'hp_confidence': 1.0,
                            'killed': True, 'damage_dealt': 1000,
                            'progress_delta': 1, 'streak': 1,
                            'enemy_affixes': [], 'source': ''},
                'evidence': [],
            }],
            'slices': {name: [] for name in (
                'decisions.jsonl', 'outcomes.jsonl', 'shop_snapshots.jsonl',
                'exogenous.jsonl', 'invest_cards.jsonl', 'spend_ledger.jsonl')},
        }
        md = mod.render_match(archive, tmp_path)

        assert '全部字段渲染成功,无遥测缺口。' in md
        assert mod.MISSING not in md
        # 判定三槽齐全且槽后紧跟战斗行(块序:备战帧→槽→战斗)
        assert md.count(mod.JUDGMENT_SLOTS[0]) == 1
        assert md.index(mod.JUDGMENT_SLOTS[2]) < md.index('#### 战斗行')
