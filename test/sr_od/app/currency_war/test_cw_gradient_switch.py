"""灰度接线+遥测 v2 字段验证(Phase A Day 11;评审修正后)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览
docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。

Manager 发现/实例化/值域三测已并入主题文件 test_cw_strategy.py
(「StrategyManager 发现 / 去重 / 实例化 / 值域」节;覆盖对账:strategy 侧
为超集——闭集锁多 PluginSource.BUILTIN 断言,同文件另有第三方发现/重复
id 检测/缺省 registry 注入等 manager 独家面)。本文件主题 = config 值域门
+ 遥测 v2 字段面。"""
import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)
from sr_od.application.currency_war.telemetry import query, recorder


def test_config_domain_fields_validated_at_construction(monkeypatch) -> None:
    """config 构造期值域前置校验:strategy_id 非 mandate_v1 / ev_arm 非
    (skeleton_only|full) → ValueError(存量 yml 拼错在配置加载时暴露并给
    迁移提示,禁「运行拼错才炸」;与 cw_strategy_manager.instantiate 的
    实例化侧同名校验构成两道门)。

    get 桩隔离真实 yml 内容(构造只读、零落盘),逐字段喂非法值触发校验分支。"""
    import one_dragon.base.config.yaml_config as yaml_config_mod
    monkeypatch.setattr(
        yaml_config_mod.YamlOperator, 'get',
        lambda self, prop, value=None: 'default' if prop == 'strategy_id' else value)
    with pytest.raises(ValueError, match='strategy_id'):
        CurrencyWarConfig()
    monkeypatch.setattr(
        yaml_config_mod.YamlOperator, 'get',
        lambda self, prop, value=None: 'bogus' if prop == 'ev_arm' else value)
    with pytest.raises(ValueError, match='ev_arm'):
        CurrencyWarConfig()


def test_v2_extra_roundtrip(tmp_path: Path, monkeypatch) -> None:
    """S3:遥测链端到端——record_decision(extra v2_*) → 字段落盘。

    (2026-09-03 瘦身批:遥测全局裸赋值改 monkeypatch——原写法断言失败即
    污染后续测试文件(纪律 1 全集假红类),且 _CURRENT_DIFFICULTY 原先从不还原。)
    """
    from sr_od.application.currency_war.kernel.cw_state import GameState
    from sr_od.application.currency_war.telemetry import state as _telstate
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
