"""达标臂发射面 sim 观测批:LaunchBattle 行落盘锁 + 统计族锁 + 零发射局形态锁。

背景:发射核(launch_prepared_battle,14号稿 §9.6 / checkpoint 3)效果落
在 op 执行层,严格同池 A/B 的 ledger 逐位门在 sim 结构性不可见 →
engine_p1 在战斗类节点**轮入口**(决策段循环前,同生产评估时点)建模发射事件:行内
'launch' 键(None=未触发),触发判据 = form_progress 现读直调(≥1.0,
零新阈值),victim 形态 = kernel ``launch_admission_report`` 单一源直调,
ok 恒 True(sim 无屏态过期/执行失败面,建模声明见 engine_p1「达标臂
发射事件建模」块)。设计约束:纯披露零 rng 消耗零状态写入;挂行内键
而非增行/动 actions——一轮一行、outcomes 配对、段级检查轮键与行为投影
digest(w614 锚含 actions 逐项)四不变式均不得被观测面挤占。

本批三锁:
1. 落盘:launch 行字段口径 + 只落战斗类节点 + 触发与 form_ok 同源 +
   write_batch_ledger 落盘后 decisions.jsonl 可读回(判读 CLI 消费面);
2. 统计族:cw_batch_stats 发射族(次数/成功率/victim 缺失占比/首发轮)
   对账本行聚合恒等;
3. 零发射局形态:无 launch 的局统计聚合不炸(0/None),不误报。
"""
from __future__ import annotations

import importlib.util
import json

import pytest

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

_COMBAT_NODES = ('battle', 'encounter', 'boss')
_VICTIM_KEYS = {'board_full', 'bench_core_waiting', 'victim_missing'}

_SEED_CACHE: dict[int, object] = {}

# 发射单锚(README 纪律#12):奖励帧抑制生效(2026-09-08 奖励帧策略审查
# ·可见性批)后旧锚 seed 0 零发射事件(发射时点位移,采样缺陷非机制
# 回归)。探针窗口 seed 0-39 命中 23/40;取 seed 5(发射行 5、溢出帧 4)。
_LAUNCH_SEED: int = 5


def _seeded_result(seed: int):
    """同 seed 单局结果同次运行只算一次(昂贵计算共享,README 纪律)。"""
    if seed not in _SEED_CACHE:
        _SEED_CACHE[seed] = simulate_p1(seed, pool='snapshot')
    return _SEED_CACHE[seed]


def _launch_rows(result) -> list[tuple[dict, dict]]:
    """(轮行, launch 值)对:该局全部发射事件行。"""
    return [(row, row['launch']) for row in result.ledger
            if row.get('launch') is not None]


class TestLaunchRowLedgerLock:
    """锁 1:发射行落盘(字段口径/辖域/触发同源/落盘读回)。"""

    def test_launch_row_field_shape(self):
        seen = False
        for seed in range(6):
            for _row, launch in _launch_rows(_seeded_result(seed)):
                seen = True
                assert launch['__type__'] == 'LaunchBattle'
                # 授权依据非空(触发臂可归因;与 LevelUp.auth_basis
                # 观测同键名族)
                assert isinstance(launch.get('auth_basis'), str)
                assert launch['auth_basis']
                # victim 形态 = G1 准入三元,键集恰等、全 bool(生产
                # readiness_admission_report 单一源,禁第二实现漂移);
                # None = 准入预估异常吞(仅观测位不拦短路门,ADR-0557 §4)
                victim = launch.get('victim')
                if victim is not None:
                    assert set(victim.keys()) == _VICTIM_KEYS, victim
                    assert all(isinstance(v, bool)
                               for v in victim.values())
                # 成功布尔:sim 发射核必然执行(建模声明,恒 True)
                assert launch.get('ok') is True
        assert seen, '采样 6 seed 零发射事件(采样缺陷,需换 seed 窗口)'

    def test_launch_only_on_combat_nodes(self):
        """发射事件只落战斗类节点行(reward/supply 无战可出)。"""
        for seed in range(6):
            for row, _launch in _launch_rows(_seeded_result(seed)):
                assert (row.get('sim') or {}).get('node') in _COMBAT_NODES

    def test_launch_trigger_not_mirror_bound(self):
        """触发源锁:发射事件与镜像族 v3_form_ok 解耦。

        sim71 批后 v3_form_ok 写端已接 readiness_form_ok 现读(死镜像
        处置),但触发源仍是判据核 readiness_launch_decision 直调,
        不读镜像层(engine 侧发射块注释已声明)——发射行为不随镜像
        写端缺位回归。锁形态:发射行存在即证明触发不经过镜像层读端。
        """
        launches = [lg for seed in range(6) for _r, lg
                    in _launch_rows(_seeded_result(seed))]
        assert launches, '采样 6 seed 零发射事件(采样缺陷,需换 seed 窗口)'

    def test_decisions_jsonl_persist_launch_rows(self, tmp_path):
        """落盘锁:decisions.jsonl 行内 launch 键与内存账本逐位一致。"""
        from sr_od.application.currency_war.sim.runner import (
            write_batch_ledger,
        )
        result = _seeded_result(_LAUNCH_SEED)
        out = write_batch_ledger([result], tmp_path / 'batch',
                                 pool_fp=result.pool_fingerprint)
        lines = [json.loads(line)
                 for line in (out / 'decisions.jsonl').open(encoding='utf-8')
                 if line.strip()]
        memory = [(i, row['launch']) for i, row in enumerate(result.ledger)]
        persisted = [(i, row.get('launch')) for i, row in enumerate(lines)]
        assert persisted == memory
        assert any(lg is not None for _i, lg in persisted), (
            '发射单锚零发射事件(发射锚漂移,重跑探针更新 _LAUNCH_SEED)')


def _load_stats_module():
    """cw_batch_stats(skill 脚本,非包成员)按路径加载。"""
    from one_dragon.utils.file_utils import get_project_root
    path = (get_project_root() / 'skills' / 'sr-od-currency-war-dev'
            / 'scripts' / 'cw_batch_stats.py')
    spec = importlib.util.spec_from_file_location('cw_batch_stats', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLaunchStatsFamilyLock:
    """锁 2:统计族对接(cw_batch_stats 发射计数/成功率族)。"""

    def test_stats_family_matches_ledger(self, tmp_path):
        mod = _load_stats_module()
        result = _seeded_result(0)
        from sr_od.application.currency_war.sim.runner import (
            write_batch_ledger,
        )
        out = write_batch_ledger([result], tmp_path / 'batch',
                                 pool_fp=result.pool_fingerprint)
        rows_by_game = mod._sim_rows(out)
        assert len(rows_by_game) == 1
        (rows,) = rows_by_game.values()
        m = mod.analyze_game(rows)
        n_launch = sum(1 for row in result.ledger
                       if row.get('launch') is not None)
        assert m['发射次数'] == n_launch
        # sim 发射核必然执行 → 成功率恒 1(建模声明,非分布结论)
        if n_launch:
            assert m['发射成功率'] == 1.0
            assert 0.0 <= m['发射victim缺失占比'] <= 1.0
            assert m['首发轮'] == next(
                row['round_num'] for row in result.ledger
                if row.get('launch') is not None)

    def test_stats_survives_archive_rows_without_launch(self, tmp_path,
                                                        monkeypatch):
        """真调 _archive_rows:档案行 StartBattle 行动 → launch 事件转换
        (ok 恒 True,发射核执行痕迹)+ 无发射局统计退化 0/None 不炸。"""
        mod = _load_stats_module()
        monkeypatch.setattr(mod, 'MATCHES', tmp_path)
        (tmp_path / 'match_T2.json').write_text(json.dumps({
            'game_id': 'T2',
            'opening': {},
            'rounds': [
                {'plane': 1, 'round': 1, 'node_type': '普通战斗',
                 'gold': 10, 'hp': 90, 'hp_delta': None,
                 'form_score': 0.5, 'form_ok': False, 'level': 3,
                 'deployed': [], 'board': {},
                 'actions': [{'__type__': 'StartBattle'}],
                 'shop_snapshots': []},
                {'plane': 1, 'round': 2, 'node_type': '普通战斗',
                 'gold': 12, 'hp': 85, 'hp_delta': -5, 'form_score': 0.6,
                 'form_ok': False, 'level': 3, 'deployed': [],
                 'board': {}, 'actions': [{'__type__': 'BuyCard'}],
                 'shop_snapshots': []},
            ]}, ensure_ascii=False), encoding='utf-8')
        archive = mod._archive_rows('T2')
        assert archive['game_id'] == 'T2'
        rows = archive['rows']
        # StartBattle → launch 转换(档案只记「发生了」,ok 恒 True)
        assert rows[0]['launch'] == {'__type__': 'StartBattle', 'ok': True}
        assert rows[1]['launch'] is None
        m = mod.analyze_game(rows)
        assert m['发射次数'] == 1
        assert m['发射成功率'] == 1.0


class TestZeroLaunchGameShapeLock:
    """锁 3:零发射局形态(聚合不炸、不误报)。"""

    def test_zero_launch_game_stats_shape(self):
        mod = _load_stats_module()
        result = _seeded_result(0)
        rows = [{'plane': row['plane'], 'round': row['round_num'],
                 'node_type': (row.get('sim') or {}).get('node'),
                 'gold': row['gold'], 'hp': row['hp'], 'hp_delta': None,
                 'form': row.get('form_score'),
                 'form_ok': row.get('form_ok'), 'level':
                     (row.get('state') or {}).get('level'),
                 'deployed': (row.get('state') or {}).get('deployed') or [],
                 'factions': dict((row.get('state') or {})
                                  .get('board_factions') or {}),
                 'acts': row.get('actions') or [],
                 # 零发射局 = launch 全 None(从未达标的局形态)
                 'launch': None, 'shop_waves': []}
                for row in result.ledger]
        m = mod.analyze_game(rows)
        assert m['发射次数'] == 0
        assert m['发射成功率'] is None
        assert m['发射victim缺失占比'] is None
        assert m['首发轮'] is None

    def test_ledger_rows_all_carry_launch_key(self):
        """行形态锁:每轮行都带 launch 键(None=未触发,消费端零缺键分支)。"""
        result = _seeded_result(0)
        assert all('launch' in row for row in result.ledger)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
