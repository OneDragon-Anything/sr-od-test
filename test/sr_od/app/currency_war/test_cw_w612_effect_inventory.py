"""cw_effect_inventory(W612 骨架批)测试:EffectSpec 构造锁 + inventory 登记/查表/
剩余期锁 + 四挂点证据时效锁 + 双源边界锁。

锁契约:锁结构/回显,不锁分布数值;经济数值单一源在 STRATEGY_ECONOMY(对拍锁在
test_locks_boundary)。
"""
import dataclasses
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel import cw_investments
from sr_od.application.currency_war.kernel.cw_effect_inventory import (  # noqa: E402
    ActiveEffectInventory,
    BattlefieldEffect,
    CounterKey,
    DurationKind,
    EffectKind,
    TriggerKind,
)
from sr_od.application.currency_war.data.cw_invest_data import PLAZA_AUGMENTS  # noqa: E402
from sr_od.application.currency_war.kernel.cw_investments import (  # noqa: E402
    INVESTMENT_STRATEGIES,
    STRATEGY_ECONOMY,
    STRATEGY_EFFECTS,
    EconomyEffect,
)
from sr_od.application.currency_war.decision.cw_strategy import StrategySession  # noqa: E402

# ===== T1 · EffectSpec 构造锁 =====

def test_spec_frozen() -> None:
    """frozen 不可变:任一字段赋值抛 FrozenInstanceError。"""
    spec = STRATEGY_EFFECTS['淘金客']
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.trigger = TriggerKind.INSTANT  # type: ignore[misc]


def test_overlay_no_orphans_and_id_match() -> None:
    """孤儿键 + id 双匹配:import 已过 _validate_strategy_effects(同路径再断言一次,
    防构建函数被移除后本锁静默失效)。"""
    cw_investments._validate_strategy_effects()
    for spec in STRATEGY_EFFECTS.values():
        base = INVESTMENT_STRATEGIES[spec.name]
        assert base.source == f'plaza:{spec.id}'


def test_payload_category_consistency() -> None:
    """payload 类型与 category 一致(ECONOMY/STATE→EconomyEffect、
    BATTLEFIELD→BattlefieldEffect、UNIT_BUFF→UnitBuffRef)。"""
    for spec in STRATEGY_EFFECTS.values():
        if spec.category in (EffectKind.ECONOMY, EffectKind.STATE):
            assert isinstance(spec.payload, EconomyEffect), spec.name
        elif spec.category == EffectKind.BATTLEFIELD:
            assert isinstance(spec.payload, BattlefieldEffect), spec.name
        else:
            from sr_od.application.currency_war.kernel.cw_effect_inventory import UnitBuffRef
            assert isinstance(spec.payload, UnitBuffRef), spec.name


def test_first_batch_structures() -> None:
    """首批条目四元组结构回显锁(锁结构不锁数值;数值在 payload/注册表)。"""
    expect = {
        # (id, trigger, duration, category, duties.predict, pending)
        '301601': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.STATE, False, False),
        '201801': (TriggerKind.PLANE_START, DurationKind.PERMANENT, EffectKind.STATE, False, True),
        '103601': (TriggerKind.CONDITIONAL, DurationKind.WHILE_HELD, EffectKind.ECONOMY, False, True),
        '300201': (TriggerKind.LEVEL_UP, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '204101': (TriggerKind.NODE_ENTER, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '201201': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '303101': (TriggerKind.ON_REFRESH, DurationKind.WHILE_HELD, EffectKind.BATTLEFIELD, True, False),
        '102701': (TriggerKind.INSTANT, DurationKind.ONCE, EffectKind.BATTLEFIELD, True, False),
        '102801': (TriggerKind.INSTANT, DurationKind.ONCE, EffectKind.BATTLEFIELD, True, False),
        '102001': (TriggerKind.CONDITIONAL, DurationKind.N_NODES, EffectKind.ECONOMY, False, False),
    }
    assert {s.id for s in STRATEGY_EFFECTS.values()} == set(expect)
    by_id = {s.id: s for s in STRATEGY_EFFECTS.values()}
    for spec_id, (trig, dur, cat, predict, pending) in expect.items():
        spec = by_id[spec_id]
        assert (spec.trigger, spec.duration, spec.category) == (trig, dur, cat), spec_id
        assert spec.duties.predict is predict, spec_id
        assert spec.pending is pending, spec_id


def test_pending_entries_have_conservative_notes_and_verdict_unset() -> None:
    """二义条目:pending=True 必须 notes 写保守支、verdict 保持 None(不猜,等实采)。"""
    for spec in STRATEGY_EFFECTS.values():
        if spec.pending:
            assert spec.verdict is None, spec.name
            assert spec.notes, spec.name
    assert STRATEGY_EFFECTS['固定理财'].pending
    assert STRATEGY_EFFECTS['经验就是财富'].pending


# ===== T2 · inventory 登记/查表/剩余期锁 =====

def _inv_with_all_specs() -> ActiveEffectInventory:
    inv = ActiveEffectInventory()
    for spec in STRATEGY_EFFECTS.values():
        inv.register_strategy(spec, acquired_t=10)
    return inv


def test_register_query_roundtrip() -> None:
    inv = _inv_with_all_specs()
    assert len(inv.entries) == len(STRATEGY_EFFECTS)
    assert len(inv.by_category(EffectKind.BATTLEFIELD)) == 6
    assert len(inv.by_trigger(TriggerKind.ON_REFRESH)) == 3
    assert inv.first('301601') is not None
    assert inv.first('999999') is None


def test_predict_for_level_up_returns_spy_only() -> None:
    """predict_for('level_up') 恰返回商业间谍一条(升级触发族唯一 predict 条目)。"""
    inv = _inv_with_all_specs()
    hits = inv.predict_for('level_up')
    assert [e.spec.id for e in hits] == ['300201']
    # 未知 action 保守返回全部 predict 条目(漏预知=读牌误判,多给不错给)
    assert len(inv.predict_for('unknown_action')) == len(
        [e for e in inv.entries if e.spec.duties.predict])


def test_tangping_remaining_nodes_decrement_and_expiry() -> None:
    """躺平余期:自然数计数 3→递减,第 3 次 tick 移除;第 2 次后 remaining==1 回显。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['躺平'], acquired_t=5)
    inv.tick_node()
    inv.tick_node()
    entry = inv.first('102001')
    assert entry is not None and entry.remaining_nodes == 1   # 未过期回显
    inv.tick_node()
    assert inv.first('102001') is None                        # 第 3 次移除


def test_permanent_entries_survive_tick() -> None:
    """WHILE_HELD/PERMANENT 条目 tick 不递减不移除。"""
    inv = _inv_with_all_specs()
    inv.tick_node()
    assert inv.first('301601') is not None    # 淘金客 while_held
    assert inv.first('201801') is not None    # 固定理财 permanent
    assert inv.entries[0].remaining_nodes is None


def test_counters_isolated_per_spec() -> None:
    """计数器按 (spec_id, key) 隔离:两条 ON_REFRESH 策略同 key 不串账。"""
    inv = ActiveEffectInventory()
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·金'], acquired_t=1)
    inv.register_strategy(STRATEGY_EFFECTS['采购专员·彩'], acquired_t=1)
    inv.bump('201201', CounterKey.REFRESH)
    inv.bump('201201', CounterKey.REFRESH)
    inv.bump('303101', CounterKey.REFRESH)
    assert inv.counter('201201', CounterKey.REFRESH) == 2
    assert inv.counter('303101', CounterKey.REFRESH) == 1
    assert inv.counter('201201', CounterKey.BUY) == 0


def test_event_markers_count_only() -> None:
    """on_level_up/on_battle_end 只标记不产效果(P0 语义:效果结算归后续批)。"""
    inv = ActiveEffectInventory()
    inv.on_level_up()
    inv.on_level_up()
    inv.on_battle_end()
    assert inv.event_count('_event_level_up') == 2
    assert inv.event_count('_event_battle_end') == 1
    assert len(inv.entries) == 0   # 不产生/移除任何条目


def test_session_host_field_default() -> None:
    """session 宿主字段:默认工厂给独立实例,两局不共享(局级隔离)。"""
    s1, s2 = StrategySession(), StrategySession()
    assert isinstance(s1.effect_inventory, ActiveEffectInventory)
    assert s1.effect_inventory is not s2.effect_inventory


# ===== T3 · 双源边界锁 =====

def test_strategy_economy_untouched() -> None:
    """STRATEGY_ECONOMY 全量与键集对拍(防实现批顺手改经济值/丢条目)。
    若红:先判锁再判改——可能有合法经济建模修正,禁机械跟绿。"""
    expected_keys = {
        '高效决策', '采购专员·彩', '本金充裕', '开源节流', '利息上调', '买断制',
        '淘金客', '伟大征服', '商业间谍', '返利+', '采购专员·金', '定期福利',
        '加油站', '乱成一锅粥+', '乱成一锅粥', '着眼当下', '搜打撤', '远见',
        '贸易专家:停云', '佩佩驾到', '控制规模', '藏一手', '及时雨', '决议:娱乐星球',
        '公司严选', '节节高升', '本金充裕+', '黄金垃圾', '退化', '停云顾问',
        '加拉赫顾问', '摸个鱼吧II', '摸个鱼吧I', '按劳分配', '专家招募+',
        '专家招募', '大扩招', '五百强', '成本控制', '剩余价值', '四费晋升',
        '小复制+', '小复制', '长期主义+', '长期主义', '大裁员', '嘴硬',
        '秘密典籍+', '秘密典籍', '经验就是财富', '二极管', '免费升舱', '无害垃圾',
        '胜利,还是胜利', '打捞人才库+', '尾款交付', '免费午餐', '特战资金+',
        '特战资金', '返利', '军火贸易', '军火贸易+', '以战养战', '躺平',
        '公司人才流动', '武装支援+', '合并同类项', '无伤通关', '招聘资金',
        '招聘资金+', '溜佩佩', '溜佩佩+', '保险', '成长基金', '成长的快乐',
        '超发货币', '固定理财', '固定理财+', '经验到账', '孪生素数', '狸财经狸',
        '不等价交换', '星际和平保险', '简单模式', '难度修改器', '砂里淘金',
        '星星相印', '武力刷新', '降本增效',
    }
    assert set(STRATEGY_ECONOMY) == expected_keys
    # 本批高频件数值不变(指针引用同一实例的防线:payload 与 overlay 同源)
    assert STRATEGY_EFFECTS['淘金客'].payload is STRATEGY_ECONOMY['淘金客']


def test_only_strategy_source_in_batch() -> None:
    """双源边界:本批数据条目 100% 策略源;环境/词缀源是 W607 辖域不在此建模。
    (source 值在 register 时写死 'strategy';schema 预留值由 ActiveEffect.source
    注释承载,此处锁注册行为。)"""
    inv = _inv_with_all_specs()
    assert {e.source for e in inv.entries} == {'strategy'}


def test_overlay_id_set_matches_registry_ids() -> None:
    """overlay id 全部能在 plaza base 中按 (id, name) 双命中(昵称漂移防线:
    如 Gemi狸 的官方卡名是「双手狸开键盘!」,禁昵称入注册表)。"""
    by_id = {a.id: a.name for a in PLAZA_AUGMENTS}
    for spec in STRATEGY_EFFECTS.values():
        assert by_id.get(spec.id) == spec.name


# ===== T4 · 挂点证据时效锁 =====

def test_hook_points_exist() -> None:
    """四挂点证据时效(HOOKS.md 证据过期即红):
    ①选卡 handler append active_strategies;②battle_loop node_enter 事件;
    ③record_outcome;④升级挂点(prep_actions._level_up 内 inventory 标记 + 'level_up' 事件行)。"""
    import inspect

    import sr_od.application.currency_war.operations.battle_loop as battle_loop
    import sr_od.application.currency_war.operations.handlers.handle_invest_strategy as his
    import sr_od.application.currency_war.prep_actions as prep_actions

    his_src = inspect.getsource(his)
    assert 'active_strategies.append' in his_src
    loop_src = inspect.getsource(battle_loop)
    assert "'node_enter'" in loop_src
    assert 'record_outcome' in loop_src
    prep_src = inspect.getsource(prep_actions)
    assert 'on_level_up' in prep_src
    assert "'level_up'" in prep_src
    # ④ 记录端 kind 枚举补齐(编排者裁决:record_exogenous 支持 level_up)

    from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
    assert 'level_up' in inspect.getsource(TelemetryRecorder.record_exogenous)
