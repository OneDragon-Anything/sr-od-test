"""灰度接线+遥测 v2 字段验证(Phase A Day 11;评审修正后)。

Manager 构造需要 ctx+plugin_dirs——测试用内置目录构造
(strategies/ 包目录;PluginSource.BUILTIN)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
import json
from pathlib import Path

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.telemetry import query, recorder, state
from sr_od.application.currency_war.telemetry import query as query
from sr_od.application.currency_war.decision.cw_strategy_manager import (
    PluginSource,
    StrategyManager,
)

_STRATEGIES_DIR = Path(__file__).parents[5] / 'src' / 'sr_od' \
    / 'application' / 'currency_war' / 'strategies'


def _mgr() -> StrategyManager:
    return StrategyManager(None, [(_STRATEGIES_DIR, PluginSource.BUILTIN)])


def test_strategies_discoverable():
    ids = [i.strategy_id for i in _mgr().discover()]
    assert ids == ['decision_v2', 'mandate_v1']   # §6.4-R 换核批4 扩 mandate_v1(锁语义重推:钉注册面封闭集)


def test_instantiate_line_v2():
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    mgr = _mgr()
    mgr.discover()
    assert isinstance(mgr.instantiate('decision_v2'), DecisionV2Strategy)


def test_instantiate_unknown_id_raises():
    """未知 id 显式报错(旧「回退 default」分支已随 default 本体退役删除)。"""
    mgr = _mgr()
    mgr.discover()
    import pytest
    with pytest.raises(ValueError, match='decision_v2'):
        mgr.instantiate('nonexistent')


def test_config_strategy_id_writable():
    cfg = CurrencyWarConfig()
    old = cfg.strategy_id
    try:
        cfg.strategy_id = 'decision_v2'
        assert cfg.strategy_id == 'decision_v2'
    finally:
        cfg.strategy_id = old


def test_default_session_v2_fields_none():
    """B1 回归:default 局 session 的 v2_state=None(不是假 economy)
    ——「v2_* 全空=default」判读规则的源头保证。"""
    sess = StrategySession()
    assert sess.v2_state is None
    assert sess.locked_line is None
    assert sess.bridge_id is None


def test_v2_extra_roundtrip(tmp_path: Path, monkeypatch) -> None:
    """S3:遥测链端到端——record_decision(extra v2_*) → 字段落盘。

    (2026-09-03 瘦身批:遥测全局裸赋值改 monkeypatch——原写法断言失败即
    污染后续测试文件(纪律 1 全集假红类),且 _CURRENT_DIFFICULTY 原先从不还原。)
    """
    from sr_od.application.currency_war.telemetry import state as _telstate
    from sr_od.application.currency_war.kernel.cw_state import GameState
    monkeypatch.setattr(_telstate, '_RECORDER', recorder.TelemetryRecorder(
        enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(_telstate, '_CURRENT_RUN_ID', 'test_v2')
    monkeypatch.setattr(_telstate, '_CURRENT_DIFFICULTY', 'A8')
    st = GameState()
    st.plane, st.round_num, st.gold = 1, 1, 50
    recorder.record_decision(
        st, 'tgt', {}, {}, [],
        extra={'strategy_id': 'line_v2', 'v2_mode': 'economy',
               'v2_locked_line': 'jizi_train', 'v2_bridge': ''})
    with open(tmp_path / 'decisions.jsonl', encoding='utf-8') as fh:
        rows = [json.loads(line) for line in fh]
    assert rows[-1]['strategy_id'] == 'line_v2'
    assert rows[-1]['v2_mode'] == 'economy'
    assert rows[-1]['v2_locked_line'] == 'jizi_train'
    assert rows[-1]['v2_bridge'] == ''


def test_query_rounds_shows_v2(tmp_path: Path, monkeypatch) -> None:
    """S1:rounds 视图显示 v2 字段(schema 变更查询同步;遥测全局走 monkeypatch)。"""
    from sr_od.application.currency_war.telemetry import state as _telstate
    monkeypatch.setattr(_telstate, '_RECORDER', recorder.TelemetryRecorder(
        enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(_telstate, '_CURRENT_RUN_ID', 'test_v2q')
    monkeypatch.setattr(_telstate, '_CURRENT_DIFFICULTY', 'A8')
    from sr_od.application.currency_war.kernel.cw_state import GameState
    st = GameState()
    st.plane, st.round_num, st.gold = 1, 1, 50
    recorder.record_decision(
        st, '', {}, {}, [],
        extra={'strategy_id': 'line_v2', 'v2_mode': 'war',
               'v2_locked_line': 'jizi_train', 'v2_bridge': ''})
    lines = query.query_rounds(tmp_path, 'test_v2q')
    assert any('v2=[war|jizi_train|-]' in ln for ln in lines), lines
