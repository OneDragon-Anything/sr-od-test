"""test_cw_p26_prep_obs 主题锁(P26 备战帧无条件采集批)。

数学出处 = ``docs/develop/currency_war/proofs/math_proofs.md`` P26 行 +
``docs/develop/currency_war/proofs/p26-hardnode-prep-ev.md``(双挂账:
Δp_prep 条件表 + L_node 分位口径);采集点裁定 = 19 号稿 §2.3-4
(「实采须另立采集点,非 D-D 计数位」)。

锁面三件:
- 锁① 采集分键锁:``p26_prep_obs`` 键面单一源(schema.P26_PREP_OBS_FIELDS)
  + 标签来自位面节点台账真值(单一源 = ``cw_state.ledger_node_type``)。
- 锁② 缺省零漂移锁:无 match 注册 → None;session 在场台账未命中 →
  ''(不猜);两种缺省都不产生猜测值。
- hp 硬闸门(00_framework §3)的执行面 = 锁①a 键面精确等值:键集
  扩条即红,新键禁携 hp/战力量(采 hp = 越闸;分位口径走既有结算
  三项遥测授权面离线 join,不加新读链)。不另立负向扫描锁——
  「键面无 hp」是精确等值的真子集,重复断言构成删并理由(README 纪律 7)。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_state import (
    GameState,
    ledger_update_plane,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    StrategySession,
)
from sr_od.application.currency_war.telemetry import (
    recorder as cw_recorder,
)
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.telemetry.schema import (
    P26_PREP_OBS_FIELDS,
)


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'p26t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/;w603 同款)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(cw_telemetry, '_RUN_CLOSED', False)
    monkeypatch.setattr(cw_telemetry, '_PENDING_BRIEFING_ROWS', [])
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_HANDLER', lambda payload: True)
    monkeypatch.setattr(cw_telemetry, '_L0_ANDON_FIRED_RUNS', set())
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    monkeypatch.setattr(cw_telemetry_exit, '_run_id_provider',
                        cw_telemetry.current_run_id)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


def _match_with_session(sess: StrategySession):
    return SimpleNamespace(session=sess)


# ===== 锁① 采集分键锁 =====

def test_p26_prep_obs_key_surface_single_source() -> None:
    """锁①a:键面单一源 = P26_PREP_OBS_FIELDS,当前恰一键。"""
    assert P26_PREP_OBS_FIELDS == ('node_type_next',)


def test_p26_prep_obs_label_from_ledger_truth(tmp_path: Path, monkeypatch) -> None:
    """锁①b:标签 = 位面节点台账真值(单一源);硬节点 token 原样透传不映射。"""
    _setup_recorder(monkeypatch, tmp_path)
    sess = StrategySession()
    ledger_update_plane(sess, 1, ['battle', 'encounter', 'supply', 'boss'],
                        source='plane_detail')
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF',
                        [_match_with_session(sess)])
    rec = cw_telemetry.get_recorder()
    for rn in (1, 2, 4):
        rec.record_decision('p26a', 'A8',
                            GameState(gold=10, hp=50, round_num=rn, plane=1),
                            '', {}, {}, [])
    rows = _rows(tmp_path, 'decisions.jsonl')
    assert [r['p26_prep_obs']['node_type_next'] for r in rows] == \
        ['battle', 'encounter', 'boss']


def test_p26_prep_obs_no_match_default_none(tmp_path: Path, monkeypatch) -> None:
    """锁②a:无 match 注册(离线/测试)→ 字段恒 None,不猜。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [None])
    cw_telemetry.get_recorder().record_decision(
        'p26b', 'A8', GameState(gold=10, hp=50, round_num=2, plane=1),
        '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['p26_prep_obs'] is None


def test_p26_prep_obs_ledger_miss_empty_not_guess(tmp_path: Path, monkeypatch) -> None:
    """锁②b:session 在场但台账未命中(表缺/越界/该位次 None)→ '' 诚实缺省。"""
    _setup_recorder(monkeypatch, tmp_path)
    sess = StrategySession()   # 无台账写入 → ledger_node_type 读不到表
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF',
                        [_match_with_session(sess)])
    rec = cw_telemetry.get_recorder()
    rec.record_decision('p26c', 'A8',
                        GameState(gold=10, hp=50, round_num=9, plane=1),
                        '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['p26_prep_obs'] == {'node_type_next': ''}
    # None 位次(未识别占位)同样 '' 不猜
    ledger_update_plane(sess, 1, [None], source='prep_row')
    rec.record_decision('p26c', 'A8',
                        GameState(gold=10, hp=50, round_num=1, plane=1),
                        '', {}, {}, [])
    r2 = _rows(tmp_path, 'decisions.jsonl')[1]
    assert r2['p26_prep_obs'] == {'node_type_next': ''}


def test_p26_prep_obs_zero_behavior_drift(tmp_path: Path, monkeypatch) -> None:
    """锁②c:零行为漂移——采集失败路径(异常 session)不炸、决策行照写,
    其余字段面不受钩子影响(纯观测零行为)。"""
    _setup_recorder(monkeypatch, tmp_path)
    # 采集故障注入:台账容器形态坏(seq_by_plane 非 dict → .get 抛)——
    # 钩子在 best-effort suppress 内,只影响本钩子及其后字段,不炸主链
    broken = SimpleNamespace(seq_by_plane=object())
    sess = SimpleNamespace()
    # 台账宿主迁 ExecState(经 exec_state_of 附着;session 职责分离批同款)
    exec_state_of(sess).plane_node_ledger = broken
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF',
                        [SimpleNamespace(session=sess)])
    cw_telemetry.get_recorder().record_decision(
        'p26d', 'A8', GameState(gold=10, hp=50, round_num=2, plane=1),
        '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['p26_prep_obs'] is None          # 异常 → 缺省,不炸不猜
    assert r['gold'] == 10 and r['plane'] == 1   # 决策行本体零漂移
