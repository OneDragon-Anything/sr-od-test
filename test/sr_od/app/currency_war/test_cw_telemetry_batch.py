"""M2 遥测增强批锁(L3 观测/遥测面硬砍批后残存锁)。

砍除面墓碑(硬砍批:默认砍,三保留条均不命中):
- serialize_action BuyCard 富化 4 测(顶层 char_id/cost 命中/未命中/费用
  失读零冒认/非 BuyCard 零外溢)→ 决策行 JSON 逐字段形状锁,纯遥测写端;
- DecisionTrace.supply_pick extra 透传 roundtrip → 同上;
- plan_gold_flow char_id 优先/旧数据回退 2 测 → spend 视图读端格式锁;
- economy 视图 luc= 列名锁 → 视图列名格式锁。

残存 1 测 = 消费权边界否定墓碑(选快照并入 extra/节点侧禁消费暂存槽),
防回退到已退役的空壳帧形态与双消费点。
"""
from __future__ import annotations


def test_run_supply_node_pick_consumption_boundary() -> None:
    """否定墓碑双条(肯定性 `'supply_pick' in src` 在场断言已删——弱接线
    存在性由行为侧 record_decision 测试覆盖):①禁回退空壳帧形态
    (`extra={'phase': 'supply_pick'}` 单键字典,选定快照丢失);②消费权
    边界 = cw_loop 合成结算行,节点侧禁 consume 暂存槽。"""
    from pathlib import Path

    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node,
    )
    src = Path(cw_screen_supply_node.__file__).read_text(encoding='utf-8')
    assert "extra={'phase': 'supply_pick'}" not in src, (
        '选定快照应并入 extra 字典(空壳帧=本批改造前形态)')
    assert 'tel_state.consume_last_supply_pick' not in src, (
        '节点侧禁消费暂存槽(消费权=cw_loop 合成结算行)')
