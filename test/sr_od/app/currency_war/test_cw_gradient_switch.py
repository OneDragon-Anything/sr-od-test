"""灰度接线+遥测 v2 字段验证(Phase A Day 11;评审修正后)。

Manager 构造需要 ctx+plugin_dirs——测试用内置目录构造
(strategies/ 包目录;PluginSource.BUILTIN)。"""
import json
from pathlib import Path

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
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
    assert ids == ['decision_v2']   # default 栈退役后唯一内置注册


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


def test_v2_extra_roundtrip(tmp_path: Path):
    """S3:遥测链端到端——record_decision(extra v2_*) → 字段落盘。"""
    from sr_od.application.currency_war.telemetry import cw_telemetry
    from sr_od.application.currency_war.kernel.cw_state import GameState
    cw_telemetry._RECORDER = cw_telemetry.TelemetryRecorder(
        enabled=True, replay_dir=tmp_path)
    cw_telemetry._CURRENT_RUN_ID = 'test_v2'
    cw_telemetry._CURRENT_DIFFICULTY = 'A8'
    st = GameState()
    st.plane, st.round_num, st.gold = 1, 1, 50
    cw_telemetry.record_decision(
        st, 'tgt', {}, {}, [],
        extra={'strategy_id': 'line_v2', 'v2_mode': 'economy',
               'v2_locked_line': 'jizi_train', 'v2_bridge': ''})
    with open(tmp_path / 'decisions.jsonl', encoding='utf-8') as fh:
        rows = [json.loads(line) for line in fh]
    assert rows[-1]['strategy_id'] == 'line_v2'
    assert rows[-1]['v2_mode'] == 'economy'
    assert rows[-1]['v2_locked_line'] == 'jizi_train'
    assert rows[-1]['v2_bridge'] == ''
    cw_telemetry._RECORDER = None
    cw_telemetry._CURRENT_RUN_ID = ''


def test_query_rounds_shows_v2(tmp_path: Path):
    """S1:rounds 视图显示 v2 字段(schema 变更查询同步)。"""
    from sr_od.application.currency_war.telemetry import cw_telemetry
    cw_telemetry._RECORDER = cw_telemetry.TelemetryRecorder(
        enabled=True, replay_dir=tmp_path)
    cw_telemetry._CURRENT_RUN_ID = 'test_v2q'
    cw_telemetry._CURRENT_DIFFICULTY = 'A8'
    from sr_od.application.currency_war.kernel.cw_state import GameState
    st = GameState()
    st.plane, st.round_num, st.gold = 1, 1, 50
    cw_telemetry.record_decision(
        st, '', {}, {}, [],
        extra={'strategy_id': 'line_v2', 'v2_mode': 'war',
               'v2_locked_line': 'jizi_train', 'v2_bridge': ''})
    lines = cw_telemetry.query_rounds(tmp_path, 'test_v2q')
    assert any('v2=[war|jizi_train|-]' in ln for ln in lines), lines
    cw_telemetry._RECORDER = None
    cw_telemetry._CURRENT_RUN_ID = ''
