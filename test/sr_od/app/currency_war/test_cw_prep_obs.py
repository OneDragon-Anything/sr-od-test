"""test_cw_prep_obs 主题锁(P26 备战帧无条件采集批)。

数学出处 = ``docs/develop/sr_od/application/currency_war/proofs/math_proofs.md`` P26 行 +
``docs/develop/sr_od/application/currency_war/proofs/p26-hardnode-prep-ev.md``(双挂账:
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

from sr_od.application.currency_war.kernel.cw_state import (
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


def test_p26_prep_obs_writer_retired() -> None:
    """锁(删除波 1 重写):p26_prep_obs 的 decisions 行落盘面(record_decision)
    已随旧流写入端退役——原②支行面锁(台账真值标签/无 match None/未命中 ''/
    零行为漂移四支)随写端消亡;采集函数读链与键面单一源(锁①a)保留辖
    读端/后续接线批。防半删 = 写端符号机器可验。"""
    assert not hasattr(cw_recorder, 'record_decision'), \
        'record_decision 应已随删除波 1 删除(防半删)'


def test_p26_prep_obs_label_from_ledger_truth(tmp_path: Path, monkeypatch) -> None:
    """采集真值面(删除波 1 重写锚):标签 = 位面节点台账真值(单一源),
    硬节点 token 原样透传不映射——锁 kernel 台账读链(ledger_node_type,
    原行内采集的读数源)对 1-based 轮次的下标换算与 boss token 透传。"""
    from sr_od.application.currency_war.kernel.cw_state import ledger_node_type
    sess = StrategySession()
    ledger_update_plane(sess, 1, ['battle', 'encounter', 'supply', 'boss'],
                        source='plane_detail')
    assert ledger_node_type(sess, 1, 1) == 'battle'
    assert ledger_node_type(sess, 1, 2) == 'encounter'
    assert ledger_node_type(sess, 1, 4) == 'boss'
    # 越界/缺表/None 位次 → None(调用方退逐帧识别链,不猜)
    assert ledger_node_type(sess, 1, 9) is None
    assert ledger_node_type(StrategySession(), 1, 1) is None
    assert ledger_node_type(None, 1, 1) is None
