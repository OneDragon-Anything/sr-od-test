"""W512:观测自检框架剩余专项观测面(观测自检设计 §2.3/§2.9/§2.10/§5-B5/B6)。

测三类行为:①confidence 可选字段贯通(record_defect → 台账行;旁路透传数值 ctx;
非数值 → None)②策略激活态事件级对拍(record_invest_cards 暂存声明选中 →
消费即清)③defect_ledger 纯净锁(台账行不再混入 spend_ledger——台账=归一索引层,
spend_ledger=原始证据层)。原 ④ 接线源码锁 3 条随瘦身批删除(见文尾注)。
契约锁形状不锁分布;全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。


出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/sr_od/application/currency_war/strategy-docs/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.telemetry import defects, recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w512t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    # 复现计数/暂存槽是进程内状态,逐测试清空防串(暂存槽自分包期 4 迁 kernel.cw_observe)
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(cw_observe, '_PENDING_STRATEGY_PICK', None)


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① confidence 字段贯通(§2.10 识别置信度遥测)=====

def test_record_defect_confidence_passthrough(tmp_path: Path, monkeypatch):
    """confidence 传入 → 台账行带数值;不传 → None(末尾可选字段,兼容)。"""
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_defect('confidence', 'perception_conflict',
                               '商店牌1 SIFT 识别出身份', 'miss(inliers=0)',
                               confidence=0.0)
    defects.record_defect('deployed', 'invariant_break', 'paddle=4', 'paddle=3')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert rows[0]['confidence'] == 0.0   # 读空 = 内点数 0,数值面照记
    assert rows[1]['confidence'] is None


def test_obs_conflict_bypass_copies_numeric_confidence(tmp_path: Path, monkeypatch):
    """旁路:obs_conflict ctx 带数值 confidence → 台账行透传;非数值/缺省 → None。

    分包期 4:obs_conflict 的旁路出口走 kernel/cw_telemetry_exit 钩子位,
    本测注入真实现(monkeypatch 槽位,自动还原)。删除波 1:证据行归宿 =
    journal obs_event,旁路面不受账本武装影响。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry_exit, '_bypass_obs_conflict_to_defect',
                        defects.bypass_obs_conflict_to_defect)
    cw_observe.obs_conflict('level', 4, 5, None, verdict='采新-XP确认',
                            confidence=42.0)
    cw_observe.obs_conflict('level', 5, 6, None, verdict='采新',
                            confidence='读不到')   # 非数值 → None 不炸
    # 局部名改 ledger_rows:不得遮蔽模块级 defects(同函数上方
    # monkeypatch.setattr(..., defects.bypass_obs_conflict_to_defect)
    # 经同一名字解析,遮蔽=UnboundLocalError——纯测试侧缺陷,语义不变)
    ledger_rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert ledger_rows[0]['confidence'] == 42.0
    assert ledger_rows[1]['confidence'] is None


# ===== ② 策略激活态事件级对拍(§2.9;删除波 1 退役重写)=====

def test_strategy_pick_slot_producer_retired(tmp_path: Path, monkeypatch):
    """删除波 1:槽生产端(record_invest_cards)已随 invest_cards 流写入端
    退役——槽(kernel stage/consume)与消费面(obs 对拍)保留,候
    strategy_offer 收编批重接生产端。本锁钉:槽符号在、写端符号不在
    (防半删);消费面无暂存时零开销通路(恒 None)。"""
    _setup_recorder(monkeypatch, tmp_path)
    from sr_od.application.currency_war.kernel.cw_observe import (
        consume_pending_strategy_pick,
        stage_pending_strategy_pick,
    )
    assert callable(stage_pending_strategy_pick)
    assert callable(consume_pending_strategy_pick)
    assert not hasattr(recorder, 'record_invest_cards'), \
        'record_invest_cards 应已随删除波 1 删除(防半删)'
    assert consume_pending_strategy_pick() is None, \
        '无生产端时消费面恒 None(零开销通路,不炸)'


# ===== ③ defect_ledger 纯净锁(台账不混入 spend_ledger)=====

def test_defect_row_not_appended_to_spend_ledger(tmp_path: Path, monkeypatch):
    """record_defect 只写 defect_ledger 一条流:spend_ledger 是单元框架事实的
    原始证据层,消费端 query_spend_ledger 按 SpendUnitRecord 字段解析——缺陷行
    混入会被当伪单元误读(2e7364de 引入、当批即修的接线缺陷,本锁防回归)。"""
    _setup_recorder(monkeypatch, tmp_path)
    defects.record_defect('gold', 'perception_conflict', 'a', 'b')
    assert len(_rows(tmp_path, 'defect_ledger.jsonl')) == 1
    assert _rows(tmp_path, 'spend_ledger.jsonl') == []


# (2026-09-03 瘦身批:原 ④ 的 3 条接线源码锁删除——
#  test_strategy_pick_consumer_wiring_lock / test_deploy_action_audit_wiring_lock /
#  test_shop_sift_miss_confidence_wiring_lock 断言缩进字面/index 顺序/标识符在场,
#  均为实现形状锁(纪律 8),同文件远超「接线烟雾至多 1 条」容差;
#  行为面由 ①②③ 行为测辖定。文尾游离 `from ... import state` 一并清理。)
