"""power_model 语料抽取器测试(src 镜像:sim/power_model/corpus_extract.py)。

锁的设计约定(sim-power-model.md 正本:
sim-power-model §5.1/§8-1):
- 输入守卫 = 解析后路径精确相等断言 + sim 批根目录守卫;
- run 级隔离(fake_/sim_ 前缀 + 显式名单)= 铁律 2 的 run 粒度防线;
- canonical 口径(join 键/末帧快照/带标签优先去重与降级/战斗类判定
  以 outcomes 为准/killed 标签);
- 删失口径 = hp_after ∈ {0,1}(canonical 口径)。

fixture = 本目录 fixtures/ 自造小样本(零真实副作用;禁读本机
.debug 易失产物——sim 批根经 monkeypatch 换 tmp 桩)。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim.power_model import corpus_extract as ce
from sr_od.application.currency_war.sim.power_model.corpus_extract import (
    adjudicate_source,
    assert_input_guards,
    canonical_align,
    extract_training_corpus,
    is_censored_hp,
    load_licensed_corpus,
    run_quarantine_reason,
    source_tier,
    write_artifacts,
)

_FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture()
def fixture_corpus(tmp_path: Path,
                   monkeypatch: pytest.MonkeyPatch) -> list:
    """fixture 语料载入(守卫的 sim 批根换 tmp 桩——不触真实 .debug)。"""
    monkeypatch.setattr(ce, 'SIM_ROOT', tmp_path / 'sim')
    return load_licensed_corpus([_FIXTURES])


# ===== 输入守卫(解析后路径精确相等断言)=====

class TestInputGuards:
    """守卫三断言:解析后比较 / sim 批根拒绝 / 具名白名单。"""

    def test_returns_resolved_exact_paths(self, tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """返回值 = 两具名文件的 resolve 后路径(含相对段穿透)。"""
        monkeypatch.setattr(ce, 'SIM_ROOT', tmp_path / 'sim')
        scratch = tmp_path / 'scratch' / '..' / 'data'
        licensed = assert_input_guards([scratch], sim_root=tmp_path / 'sim')
        (paths,) = licensed.values()
        assert paths['decisions.jsonl'] == (tmp_path / 'data'
                                            / 'decisions.jsonl').resolve()
        assert paths['outcomes.jsonl'] == (tmp_path / 'data'
                                           / 'outcomes.jsonl').resolve()
        assert set(paths) == {'decisions.jsonl', 'outcomes.jsonl'}

    def test_rejects_dir_under_sim_root(self, tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
        """sim 批根下的目录拒绝(目录守卫;防 sim 批回灌 = 铁律 2)。"""
        monkeypatch.setattr(ce, 'SIM_ROOT', tmp_path / 'sim')
        (tmp_path / 'sim' / 'batch_1').mkdir(parents=True)
        with pytest.raises(RuntimeError, match='sim 批根'):
            assert_input_guards([tmp_path / 'sim' / 'batch_1'],
                                sim_root=tmp_path / 'sim')

    def test_rejects_sim_root_itself(self, tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ce, 'SIM_ROOT', tmp_path / 'sim')
        (tmp_path / 'sim').mkdir()
        with pytest.raises(RuntimeError, match='sim 批根'):
            assert_input_guards([tmp_path / 'sim'], sim_root=tmp_path / 'sim')


# ===== run 级隔离(铁律 2 的 run 粒度防线)=====

class TestRunQuarantine:
    def test_prefix_rules(self) -> None:
        assert run_quarantine_reason('fake_20260908') is not None
        assert run_quarantine_reason(
            'sim_20260920_201446_000_n60_s95100_p3_base_s95100') is not None

    def test_explicit_incident_list(self) -> None:
        """显式事故名单命中(双进程写竞争事故局)。"""
        assert run_quarantine_reason('run_20260822_185613') is not None

    def test_live_run_passes(self) -> None:
        assert run_quarantine_reason('run_20260907_214130') is None


# ===== 删失判定(canonical 口径)=====

class TestCensoring:
    @pytest.mark.parametrize('hp_after,expected', [
        (0, True), (1, True), (2, False), (23, False), (70, False),
    ])
    def test_censored_hp(self, hp_after: int, expected: bool) -> None:
        assert is_censored_hp(hp_after) is expected


# ===== canonical 口径(fixture 语料全管线)=====

class TestCanonicalPipeline:
    """fixture 语料(run_a/run_b/run_c/run_d + fake_x)逐分支锁。"""

    def test_quarantine_drops_sim_and_fake_rows(
            self, fixture_corpus: list) -> None:  # noqa: ARG002
        inp = fixture_corpus[0]
        align = canonical_align(inp.outcomes_rows, {})
        assert align.funnel['outcome_rows_quarantined'] == 1
        assert align.funnel['recovered_rows_dropped'] == 1
        assert align.funnel['outcome_keys_total'] == 8
        assert align.funnel['outcome_keys_duplicate'] == 2
        assert align.funnel['label_priority_rescues'] == 1
        assert ('fake_x', 1, 1) not in align.canonical

    def test_label_priority_picks_typed_row_over_latest(
            self, fixture_corpus: list) -> None:
        """带标签优先 > ts 最新:早行带标签/晚行 None 时选早行档;
        降级挽回(loss_page 行带标签、真值行 None)时低档标签行胜出。"""
        inp = fixture_corpus[0]
        align = canonical_align(inp.outcomes_rows, {})
        # run_a p1 r5:早行(真值档)killed=None,晚行 loss_page 带标签
        chosen = align.canonical[('run_a', 1, 5)]
        assert chosen['source'] == 'loss_page'
        assert chosen['killed'] is False
        # run_a p1 r3:两行皆真值档带标签 → ts 最新胜(killed=False)
        assert align.canonical[('run_a', 1, 3)]['killed'] is False

    def test_last_frame_snapshot_wins(self, fixture_corpus: list) -> None:
        """快照 = 键的末帧(不问帧 node_type);映射进训练行。"""
        result = extract_training_corpus(fixture_corpus)
        rows = {(r['run_id'], r['plane'], r['round_num']): r
                for r in result['training_rows']}
        # 末帧 target_comp = '绯英欢愉'(首帧为 过渡配方·仙舟)
        assert rows[('run_a', 1, 3)]['target_comp_snapshot'] == '绯英欢愉'
        # 末帧 hp = 41(首帧 40)→ 幅度行 hp_before 断言见幅度用例

    def test_battle_type_by_outcome_node(self, fixture_corpus: list) -> None:
        """战斗类判定以 outcomes 为准(中文/ASCII 双形态映射)。"""
        result = extract_training_corpus(fixture_corpus)
        meta = result['meta']['funnel']
        # 战斗类键:b/1/2、b/1/4(奖励)、d/1/1(遭遇)三键外的全部
        assert meta['battle_keys'] == 7
        assert meta['battle_rows'] == 9
        node_types = {(r['run_id'], r['plane'], r['round_num']): r['node_type']
                      for r in result['training_rows']}
        assert node_types[('run_a', 1, 5)] == 'encounter'   # 遭遇 → ASCII
        assert node_types[('run_a', 1, 7)] == 'boss'        # boss 恒 ASCII
        assert node_types[('run_c', 1, 1)] == 'battle'      # 普通战斗 → ASCII

    def test_join_and_label_rules(self, fixture_corpus: list) -> None:
        """无帧键/无标签键丢弃 + killed 标签 + 训练行零 HP 字段。"""
        result = extract_training_corpus(fixture_corpus)
        meta = result['meta']['funnel']
        assert meta['keys_no_decisions_frames'] == 1   # run_d(无帧)
        assert meta['keys_no_label'] == 1              # run_b p1 r2
        rows = {(r['run_id'], r['plane'], r['round_num']): r
                for r in result['training_rows']}
        assert set(rows) == {('run_a', 1, 3), ('run_a', 1, 5),
                             ('run_a', 1, 7), ('run_a', 2, 1),
                             ('run_c', 1, 1)}
        assert rows[('run_a', 1, 7)]['label'] is True
        assert rows[('run_c', 1, 1)]['label'] is False
        for row in rows.values():
            assert 'hp' not in json.dumps(row['features'])   # 铁律 3

    def test_three_numbers_and_budget_gate(
            self, fixture_corpus: list) -> None:
        result = extract_training_corpus(fixture_corpus)
        t = result['meta']['three_numbers_repin']
        assert t['battle_outcomes_keys'] == 7
        assert t['labeled_keys'] == 5
        assert t['win_events'] == 1
        assert t['param_budget_floor'] == 0
        assert t['budget_gate_triggered'] is True   # 1//10 = 0 < 6

    def test_amplitude_samples_and_censoring(
            self, fixture_corpus: list) -> None:
        """幅度样本表:败局 hp 结算行 + 删失标记(hp_after ∈ {0,1})。"""
        result = extract_training_corpus(fixture_corpus)
        amp = {(r['run_id'], r['plane'], r['round_num']): r
               for r in result['amplitude_samples']}
        assert result['meta']['funnel']['amplitude_rows'] == 4
        assert amp[('run_a', 2, 1)]['censored'] is True    # hp_after=0
        assert amp[('run_a', 2, 1)]['hp_before'] == 30
        assert amp[('run_a', 1, 3)]['censored'] is False   # hp_after=20
        assert amp[('run_a', 1, 3)]['hp_before'] == 41     # 末帧快照
        assert amp[('run_a', 1, 3)]['damage'] == 21
        assert amp[('run_a', 1, 5)]['source'] == 'loss_page'

    def test_drop_buckets_and_mnar(self, fixture_corpus: list) -> None:
        """丢弃按 source×位面分桶 + MNAR 缺失率按 source 分层。"""
        result = extract_training_corpus(fixture_corpus)
        buckets = result['meta']['drop_buckets_by_source_plane']
        assert buckets['non_battle_key@|plane1'] == 1
        assert buckets['no_decisions_frames@|plane1'] == 1
        assert buckets['no_label_key@|plane1'] == 1
        mnar = result['meta']['mnar_missing_by_source']
        assert mnar['']['keys'] == 6
        assert mnar['']['missing'] == 1                    # run_b p1 r2
        assert mnar['']['missing_rate'] == pytest.approx(1 / 6)
        assert mnar['loss_page']['keys'] == 1
        assert mnar['loss_page']['missing'] == 0

    def test_rung_and_context_in_training_row(
            self, fixture_corpus: list) -> None:
        """训练行特征与特征面单一源一致(仙舟三人 → rung_1 置位)。"""
        result = extract_training_corpus(fixture_corpus)
        rows = {(r['run_id'], r['plane'], r['round_num']): r
                for r in result['training_rows']}
        f = rows[('run_a', 1, 7)]['features']
        assert f['rung_1'] == 1.0
        assert f['node_boss'] == 1.0
        assert f['enemy_difficulty'] == 111.0
        assert rows[('run_a', 2, 1)]['features']['plane_not_first'] == 1.0

    def test_target_comp_stats(self, fixture_corpus: list) -> None:
        """target_comp 覆盖率与值域构成(注册套名/组合标签两族)。

        统计口径 = 纯函数按传入行算;run_extraction 传隔离后行(见
        TestRunExtraction),本用例对载入全行断言分类正确性。"""
        stats = ce.target_comp_stats(fixture_corpus[0].decisions_rows)
        assert stats['rows_total'] == 8    # 7 真实帧 + fake_x(纯函数不过滤)
        assert stats['rows_non_null'] == 3
        assert stats['registered_comp_name']['values'] == {'绯英欢愉': 1}
        assert stats['transition_recipe_label']['distinct_values'] == 2
        assert stats['other']['rows'] == 0


class TestSourceTier:
    def test_tier_order(self) -> None:
        assert source_tier('') == 0
        assert source_tier(None) == 0
        assert source_tier('loss_page') == 1
        assert source_tier('synthetic_supply') == 2
        assert source_tier('terminal_closure') == 2

    def test_post_quarantine_rows_filter(self, fixture_corpus: list) -> None:
        """统计口径入口:隔离后行过滤(fake_x 行不入 target_comp 统计)。"""
        kept = ce.post_quarantine_rows(fixture_corpus[0].decisions_rows)
        assert len(kept) == 7
        assert all(r['run_id'] != 'fake_x' for r in kept)


# ===== 普查裁定器(证据 → source;纯函数不读盘)=====

class TestSurveyAdjudication:
    def test_sim_evidence(self) -> None:
        assert adjudicate_source({'first_run_id': 'sim_20260920_201446'}) == 'sim'
        assert adjudicate_source({'first_run_id': 'run_1',
                                  'state_has_board_factions': True}) == 'sim'

    def test_live_evidence(self) -> None:
        assert adjudicate_source({'first_run_id': 'run_20260907_214130',
                                  'first_ts_is_iso': True}) == 'live'

    def test_pending_when_evidence_insufficient(self) -> None:
        assert adjudicate_source({}) == 'pending'
        assert adjudicate_source({'first_run_id': 'run_1'}) == 'pending'


# ===== 产物落盘(只写 tmp_path;零真实副作用)=====

class TestWriteArtifacts:
    def test_writes_three_files(self, tmp_path: Path,
                                fixture_corpus: list) -> None:
        result = extract_training_corpus(fixture_corpus)
        paths = write_artifacts(result, tmp_path,
                                {'source_fingerprint': {'k': 'v'}})
        names = {p.name for p in paths}
        assert names == {'meta.json', 'training_rows.jsonl',
                         'amplitude_samples.jsonl'}
        meta = json.loads((tmp_path / 'meta.json').read_text(encoding='utf-8'))
        assert meta['source_fingerprint'] == {'k': 'v'}
        assert 'three_numbers_repin' in meta
        n_rows = sum(1 for _ in (tmp_path / 'training_rows.jsonl')
                     .open(encoding='utf-8'))
        assert n_rows == len(result['training_rows'])
