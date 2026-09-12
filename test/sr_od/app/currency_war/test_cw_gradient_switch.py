"""灰度接线+遥测 v2 字段验证(Phase A Day 11;评审修正后)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览
docs/develop/sr_od/application/currency_war/strategy-docs/README.md)(2026-08-31 测试瘦身批考证补记)。

Manager 发现/实例化/值域三测已并入主题文件 test_cw_strategy.py
(「StrategyManager 发现 / 去重 / 实例化 / 值域」节;覆盖对账:strategy 侧
为超集——闭集锁多 PluginSource.BUILTIN 断言,同文件另有第三方发现/重复
id 检测/缺省 registry 注入等 manager 独家面)。本文件主题 = config 值域门
+ 遥测 v2 字段面。"""
from pathlib import Path

import pytest

from sr_od.application.currency_war.currency_war_config import (
    CurrencyWarConfig,
)
from sr_od.application.currency_war.telemetry import recorder


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


def test_v2_extra_writer_retired(tmp_path: Path) -> None:
    """S3(删除波 1 重写):v2 披露键的 decisions 行写入端已退役
    (record_decision 删除,防半删);v2_* 键的 schema/查询面继续辖冻结
    存量档案(下方 rounds 视图测)。"""
    assert not hasattr(recorder, 'record_decision'), \
        'record_decision 应已随删除波 1 删除(防半删)'


# [退役墓碑,W3] test_query_rounds_shows_v2 随 query_rounds 旧视图退役
# (W3,删旧读面);栈显示语义的现役载体 = journal_query 视图族。
# git 历史可复活。
