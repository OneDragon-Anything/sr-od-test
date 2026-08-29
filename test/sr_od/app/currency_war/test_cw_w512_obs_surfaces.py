"""W512:观测自检框架剩余专项观测面(观测自检设计 §2.3/§2.9/§2.10/§5-B5/B6)。

测四类:①confidence 可选字段贯通(record_defect → 台账行;旁路透传数值 ctx;
非数值 → None)②策略激活态事件级对拍(record_invest_cards 暂存声明选中 →
消费即清;消费端接线用源码锁)③defect_ledger 纯净锁(台账行不再混入
spend_ledger——台账=归一索引层,spend_ledger=原始证据层,消费端按
SpendUnitRecord 字段解析,混入会被当伪单元误读)④板面动作级对拍/置信度
遥测的接线存在性(源码锁,契据=DESIGN 逐面判据,注释给锚点)。
契约锁形状不锁分布;全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。
"""
import json
from pathlib import Path

from sr_od.application.currency_war.kernel import cw_observe
from sr_od.application.currency_war.telemetry import cw_telemetry


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w512t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律:不写真实 .debug/)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        cw_telemetry.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    # 复现计数/暂存槽是进程内状态,逐测试清空防串
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')
    monkeypatch.setattr(cw_telemetry, '_PENDING_STRATEGY_PICK', None)


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
    cw_telemetry.record_defect('confidence', 'perception_conflict',
                               '商店牌1 SIFT 识别出身份', 'miss(inliers=0)',
                               confidence=0.0)
    cw_telemetry.record_defect('deployed', 'invariant_break', 'paddle=4', 'paddle=3')
    rows = _rows(tmp_path, 'defect_ledger.jsonl')
    assert rows[0]['confidence'] == 0.0   # 读空 = 内点数 0,数值面照记
    assert rows[1]['confidence'] is None


def test_obs_conflict_bypass_copies_numeric_confidence(tmp_path: Path, monkeypatch):
    """旁路:obs_conflict ctx 带数值 confidence → 台账行透传;非数值/缺省 → None。

    分包期 4:obs_conflict 的旁路出口走 kernel/cw_telemetry_exit 钩子位,
    本测注入真实现(monkeypatch 槽位,自动还原)。"""
    from sr_od.application.currency_war.kernel import cw_telemetry_exit
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry_exit, '_bypass_obs_conflict_to_defect',
                        cw_telemetry.bypass_obs_conflict_to_defect)
    monkeypatch.setattr(cw_observe, '_CONFLICT_JOURNAL', tmp_path / 'obs_conflicts.jsonl')
    cw_observe.obs_conflict('level', 4, 5, None, verdict='采新-XP确认',
                            confidence=42.0)
    cw_observe.obs_conflict('level', 5, 6, None, verdict='采新',
                            confidence='读不到')   # 非数值 → None 不炸
    defects = _rows(tmp_path, 'defect_ledger.jsonl')
    assert defects[0]['confidence'] == 42.0
    assert defects[1]['confidence'] is None


# ===== ② 策略激活态事件级对拍(§2.9)=====

def test_strategy_pick_slot_produce_consume(tmp_path: Path, monkeypatch):
    """生产:record_invest_cards('strategy') 暂存声明选中名;消费即清;
    非strategy类 / chosen='?' 不暂存。"""
    _setup_recorder(monkeypatch, tmp_path)
    cw_telemetry.record_invest_cards('strategy', [
        {'idx': 0, 'name': '策略甲', 'chosen': False},
        {'idx': 1, 'name': '策略乙', 'chosen': True},
    ])
    assert cw_telemetry.consume_pending_strategy_pick() == '策略乙'
    assert cw_telemetry.consume_pending_strategy_pick() is None   # 消费即清
    cw_telemetry.record_invest_cards('env', [{'idx': 0, 'name': '环境卡', 'chosen': True}])
    assert cw_telemetry.consume_pending_strategy_pick() is None   # env 类不进槽
    cw_telemetry.record_invest_cards('strategy', [{'idx': 0, 'name': '?', 'chosen': True}])
    assert cw_telemetry.consume_pending_strategy_pick() is None   # 识别失败不暂存


def test_strategy_pick_consumer_wiring_lock():
    """消费端接线锁(静态):cw_observation 构建 state 读 session.active_strategies
    处消费暂存并对拍,不一致落 surface='strategy' 台账行(设计 §2.9 判据:
    选了 X → active_strategies 出现 X)。锁「消费点挂在既有 session 写入点」,
    防后续重构静默断链。"""
    import sr_od.application.currency_war.obs.cw_observation as obs_mod
    src = Path(obs_mod.__file__).read_text(encoding='utf-8')
    assert 'consume_pending_strategy_pick' in src
    assert "record_defect(\n                    'strategy', 'invariant_break'" in src
    # 消费点必须在 active_strategies 同步点之后(同一 if _match 块内)
    anchor = src.index('state.active_strategies = list(_match.session.active_strategies)')
    assert src.index('consume_pending_strategy_pick', anchor) > anchor


# ===== ③ defect_ledger 纯净锁(台账不混入 spend_ledger)=====

def test_defect_row_not_appended_to_spend_ledger(tmp_path: Path, monkeypatch):
    """record_defect 只写 defect_ledger 一条流:spend_ledger 是单元框架事实的
    原始证据层,消费端 query_spend_ledger 按 SpendUnitRecord 字段解析——缺陷行
    混入会被当伪单元误读(2e7364de 引入、当批即修的接线缺陷,本锁防回归)。"""
    _setup_recorder(monkeypatch, tmp_path)
    cw_telemetry.record_defect('gold', 'perception_conflict', 'a', 'b')
    assert len(_rows(tmp_path, 'defect_ledger.jsonl')) == 1
    assert _rows(tmp_path, 'spend_ledger.jsonl') == []


# ===== ④ 板面动作级对拍 + 置信度遥测接线锁(§2.3 / §2.10)=====

def test_deploy_action_audit_wiring_lock():
    """prep_director 接线锁(静态;设计 §2.3 判据:DeployMove 执行后 paddle X
    应 +1、SellDeployed 后应 −1,不等 → 台账 surface='deployed' 留证,
    与 deployed_align 的自动纠漂分立)。"""
    import sr_od.application.currency_war.prep_director as pd
    src = Path(pd.__file__).read_text(encoding='utf-8')
    # 前读:仅部署/卖出动作,执行前读 paddle
    assert 'isinstance(action, (DeployMove, SellDeployed))' in src
    # 后读:复用 heavy 重观察帧,reader_source 独立命名(可离线聚合)
    assert 'paddle_action_audit' in src
    assert "record_defect(\n                            'deployed', 'invariant_break'" in src


def test_shop_sift_miss_confidence_wiring_lock():
    """cw_observation 接线锁(静态;设计 §2.10 判据:非空槽 SIFT miss = 读空
    事件带内点数落 confidence 面,纯留证恒 L2,不设即时告警)。"""
    import sr_od.application.currency_war.obs.cw_observation as obs_mod
    src = Path(obs_mod.__file__).read_text(encoding='utf-8')
    assert "record_defect(\n                    'confidence', 'perception_conflict'" in src
    assert "reader_source='read_shop_cards'" in src
    assert 'confidence=float(_inliers)' in src
