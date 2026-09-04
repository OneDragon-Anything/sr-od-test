"""M2 遥测增强批锁(观察层数据移交 + 补给轮决策行采集)。

锁面:
- BuyCard 决策帧富化(serialize_action 顶层 char_id/cost;命中/未命中/
  非 BuyCard 三分型);
- DecisionTrace.supply_pick 末尾追加字段(recorder extra 透传,缺省 None);
- CwScreenSupplyNode 选定快照接线(弱锁:选定分支本地拷贝 + 合成决策帧
  extra.supply_pick,不动暂存槽消费权);
- economy 视图升级花费列名 luc=(防与 rounds 视图 lv=等级 同名误读)。

对局档案战后终态列不在此锁:该列已在 match_archive v3 装配端落地
(terminal/terminal_closure/terminal_source/terminal_ts;锁在
test_cw_telemetry_archive.py 的档案装配锁族),本批仅核验不重复锁。
"""
from __future__ import annotations

from pathlib import Path

from sr_od.application.currency_war.kernel.cw_state import (
    BuyCard,
    GameState,
    LevelUp,
    ShopCard,
)
from sr_od.application.currency_war.telemetry.query import query_economy
from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder
from sr_od.application.currency_war.telemetry.schema import (
    serialize_action,
)

# ===== BuyCard 决策帧富化(顶层 char_id/cost) =====


def test_serialize_buycard_char_id_cost_hit() -> None:
    """注册表命中:顶层 char_id=规范名、cost=OCR 费用平铺;card 嵌套原样保留。"""
    d = serialize_action(BuyCard(ShopCard(x=1, name='卡芙卡', faction='公司',
                                          cost=4)))
    assert d['__type__'] == 'BuyCard'
    assert d['char_id'] == '卡芙卡'          # 注册表规范名命中
    assert d['cost'] == 4                    # OCR 费用平铺
    assert d['card']['cost'] == 4            # 旧嵌套读端零波及
    assert d['card']['name'] == '卡芙卡'


def test_serialize_buycard_unknown_name_char_id_empty() -> None:
    """OCR 名未命中注册表:char_id=''(诚实缺省,不猜);cost 仍平铺。"""
    d = serialize_action(BuyCard(ShopCard(x=0, name='不存在的角色', cost=2)))
    assert d['char_id'] == ''
    assert d['cost'] == 2


def test_serialize_buycard_cost_miss_is_zero_not_registry() -> None:
    """OCR 费用失读(cost=0):cost 平铺 0,**不用注册表费用冒认真值**
    (多源混写=board_before 人次口径已付过的学费;消费方按缺口对待)。"""
    d = serialize_action(BuyCard(ShopCard(x=0, name='卡芙卡', cost=0)))
    assert d['cost'] == 0
    assert d['char_id'] == '卡芙卡'          # 名字命中照常解析(与费用独立)


def test_serialize_non_buycard_untouched() -> None:
    """非 BuyCard 动作不加 char_id 键(富化只辖 BuyCard,零外溢;
    LevelUp.cost 是其自身字段天然存在,不在此锁面)。"""
    d = serialize_action(LevelUp(cost=4))
    assert d['__type__'] == 'LevelUp'
    assert 'char_id' not in d


# ===== DecisionTrace.supply_pick(补给轮决策行采集) =====


def test_decision_trace_supply_pick_passthrough(tmp_path: Path) -> None:
    """extra.supply_pick → 决策行 supply_pick 字段(透传);不传 → None。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    pick = {'char': '姬子', 'equip': '火焰', 'has_diamond': False,
            'refreshed': False,
            'options': [{'char': '姬子', 'equip': '火焰', 'has_diamond': False}],
            'n_options': 1}
    rec.record_decision('m2sp', 'A8', GameState(plane=1, round_num=5),
                        '', {}, {}, [],
                        extra={'phase': 'supply_pick', 'supply_pick': pick})
    rec.record_decision('m2sp', 'A8', GameState(plane=1, round_num=6),
                        '', {}, {}, [])
    from sr_od.application.currency_war.telemetry.query import read_jsonl
    lines = read_jsonl(tmp_path / 'decisions.jsonl')
    assert lines[0]['phase'] == 'supply_pick'
    assert lines[0]['supply_pick'] == pick
    assert lines[1]['supply_pick'] is None   # 旧 schema 兼容(缺省 None)


def test_run_supply_node_pick_consumption_boundary() -> None:
    """否定墓碑双条(肯定性 `'supply_pick' in src` 在场断言已删——弱接线
    存在性由行为侧 record_decision 测试覆盖):①禁回退空壳帧形态
    (`extra={'phase': 'supply_pick'}` 单键字典,选定快照丢失);②消费权
    边界 = cw_loop 合成结算行,节点侧禁 consume 暂存槽。"""
    from sr_od.application.currency_war.operations.cw_screen import (
        cw_screen_supply_node,
    )
    src = Path(cw_screen_supply_node.__file__).read_text(encoding='utf-8')
    assert "extra={'phase': 'supply_pick'}" not in src, (
        '选定快照应并入 extra 字典(空壳帧=本批改造前形态)')
    assert 'tel_state.consume_last_supply_pick' not in src, (
        '节点侧禁消费暂存槽(消费权=cw_loop 合成结算行)')


# ===== spend 账逐项归因读端(plan_gold_flow 优先平铺 char_id) =====


def test_plan_gold_flow_prefers_char_id_over_ocr_name() -> None:
    """BuyCard 逐项归因:顶层 char_id(注册表规范名)优先于 card.name
    (OCR 原名)——spend_ledger 侧跨流对账吃规范名,M2 富化的读端消费。"""
    from sr_od.application.currency_war.telemetry.query import plan_gold_flow
    flow = plan_gold_flow([{'__type__': 'BuyCard',
                            'char_id': '卡芙卡',
                            'card': {'name': '卡芙卡LV.2', 'cost': 4}}])
    assert flow['items'][0]['target'] == '卡芙卡'
    assert flow['planned_spend'] == 4


def test_plan_gold_flow_falls_back_to_card_name_legacy() -> None:
    """旧记录兼容:无 char_id 键(富化前数据)回退 card.name;再退 x 序号。"""
    from sr_od.application.currency_war.telemetry.query import plan_gold_flow
    flow = plan_gold_flow([{'__type__': 'BuyCard',
                            'card': {'name': '椒丘', 'cost': 2}}])
    assert flow['items'][0]['target'] == '椒丘'
    flow2 = plan_gold_flow([{'__type__': 'BuyCard',
                             'card': {'x': 3, 'cost': 1}}])
    assert flow2['items'][0]['target'] == 'x3'


# ===== economy 视图列名 luc=(防 lv 同名误读) =====


def test_query_economy_level_up_cost_column_renamed(tmp_path: Path) -> None:
    """economy 视图升级花费列名 = luc=(曾 lv= 与 rounds 视图等级列同名——
    「升级花费兜底显示 4 被误读成等级恒 4」的视图侧歧义根治)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    st = GameState(gold=30, plane=1, round_num=3, level=5)
    st.level_up_cost = 4
    rec.record_decision('m2luc', 'A8', st, '', {}, {}, [])
    lines = query_economy(tmp_path, 'm2luc')
    assert any('luc=' in ln for ln in lines), lines
    assert not any('lv=' in ln for ln in lines), (
        f'economy 视图不得再用 lv= 列名(与等级列歧义): {lines}')
