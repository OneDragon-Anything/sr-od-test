"""W583 阶段2批①:快照契约 + sim 合成器无损验证门。

锁的是契约,不是行为数值(零旧行为变更批:decide 无实现体、现役循环零触碰):

1. 进出无损:同一 GameState 逐字段进出,Synthesize 映射式与
   SCHEMA_DRAFT.md §四「来源」列一致;
2. None 语义保持:各「读不到」变体 → 快照对应字段为 None
   (禁 0/空/兜底——错值比 None 更毒,「读不到≠真值」纪律的回归锁);
3. 分类合成契约:sim 侧 confident 恒 True;
4. 只读保证:合成前后 GameState 深比较不变(快照纯的反向锁);
5. hp 单向蕴含不变式:hp is None ⇒ hp_readable is False;
6. Decision 契约骨架:control 与 ops 并存形状可构造(框架批消费,此处只
   锁类型可实例化与冻结性)。

出处:设计审计报告 .debug/temp/currency_war/w561_arch_review/REPORT.md
§三.1/.2/.8 + 攻击9 修法(合成器门=Schema 定稿第一个消费者测试);
Schema 审定版 = .debug/temp/currency_war/w583_stage2_contracts/SCHEMA_DRAFT.md。
"""
from __future__ import annotations

import copy
import dataclasses

import pytest

from sr_od.application.currency_war.cw_state import (
    BENCH_CAPACITY,
    DEPLOYED_FRONT_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
    deployed_place,
)
from sr_od.application.currency_war.cw_sim import synthesize_snapshot
from sr_od.application.currency_war.decision_v2.contracts import (
    SNAPSHOT_SCHEMA_VERSION,
    AtomOp,
    Bail,
    Decision,
    Defer,
    Snapshot,
    SubstateClassification,
)


def _full_state() -> GameState:
    """构造「全通道可读」的 GameState(正路径对拍底座)。"""
    st = GameState()
    st.plane, st.round_num = 2, 3
    st.node_type = 'boss'
    st.selected_difficulty = 'A8'
    st.gold, st.gold_readable = 47, True
    st.streak = -2
    st.level, st.xp_progress, st.level_up_cost = 7, (2, 6), 4
    st.bench[0] = BenchChar(slot=1, char_id='jiaoqiu', faction='xxx', star=2)
    st.bench[4] = BenchChar(slot=5, char_id='seele', faction='quantum', star=1)
    d1 = BenchChar(slot=1, char_id='acheron', faction='lightning', star=2,
                   position_pref='front')
    d2 = BenchChar(slot=1, char_id='fu_xuan', faction='quantum', star=2)
    st.deploy_cap = 5
    deployed_place(st.deployed, d1)   # front_pref → 前排区 0-3
    deployed_place(st.deployed, d2)   # back_pref  → 后排区 4-9
    st.board = {'lightning': 1, 'quantum': 1}
    st.shop = [ShopCard(x=100, faction='xxx', name='jiaoqiu', cost=3),
               ShopCard(x=200)]
    st.hp, st.hp_readable = 88, True
    return st


def test_lossless_roundtrip_full_state() -> None:
    """门①进出无损:全可读底座逐字段对拍(映射式=SCHEMA_DRAFT §四来源列)。"""
    st = _full_state()
    snap = synthesize_snapshot(st)

    assert snap.schema_version == SNAPSHOT_SCHEMA_VERSION
    # 节点域
    assert (snap.plane, snap.round_num) == (2, 3)
    assert snap.node_type == 'boss'
    assert snap.selected_difficulty == 'A8'
    # 经济域
    assert snap.gold == 47
    assert snap.gold_trusted is True            # sim 真值契约(合成器注释)
    assert snap.streak == -2
    assert snap.level == 7
    assert snap.xp_progress == (2, 6)
    assert snap.level_up_cost == 4
    # 单位域
    assert snap.bench[0] is st.bench[0] and snap.bench[4] is st.bench[4]
    assert sum(1 for b in snap.bench if b is not None) == 2
    assert snap.deploy_cap == 5
    assert snap.deploy_vacancy == 3             # 5 − 占用 2
    assert snap.free_bench_slots == BENCH_CAPACITY - 2
    assert snap.front_occupied == frozenset(range(0, 1))   # d1 落前排区首槽
    assert snap.back_occupied == frozenset(
        i for i in range(DEPLOYED_FRONT_CAPACITY, 10)
        if st.deployed[i] is not None)
    assert snap.board == {'lightning': 1, 'quantum': 1}
    assert snap.front_size == 4 and snap.back_size == 6
    # 商店域:列表拷贝(非同引用)、逐项同值
    assert snap.shop_cards == st.shop and snap.shop_cards is not st.shop
    # 交互面域:sim 无实体恒空
    assert snap.spheres == () and snap.boxes == () and snap.tomes == ()
    assert snap.box_overlay_open is False and snap.event_overlay is None
    # 生命域
    assert snap.hp == 88 and snap.hp_readable is True
    # 分类合成契约(门③)
    assert snap.classification.confident is True
    assert snap.classification.name == 'prep_shop'


def test_none_semantics_preserved() -> None:
    """门②None 语义保持:「读不到」变体 → None,禁 0/空/兜底(W558 纪律回归锁)。"""
    st = _full_state()

    st.gold_readable = False
    st.streak = None
    st.node_type = None
    st.hp_readable = False
    st.board_readable = False
    st.deploy_cap = None
    st.level_up_cost = None
    st.xp_progress = None
    snap = synthesize_snapshot(st)

    assert snap.gold is None                    # 禁 0 兜底
    assert snap.streak is None
    assert snap.node_type is None
    assert snap.hp is None                      # 禁沿用值/100 兜底(对账锚在 session)
    assert snap.board is None                   # None(不可读)≠ 空 dict(真清空)
    assert snap.deploy_cap is None
    assert snap.deploy_vacancy is None          # cap 未读 → None,禁 0 兜底
    assert snap.level_up_cost is None
    assert snap.xp_progress is None
    # free_bench_slots 与失读域解耦:sim 占用恒可读 → 恒 int(Q2 裁决)
    assert isinstance(snap.free_bench_slots, int)


def test_game_state_not_mutated() -> None:
    """门④只读保证:合成前后 GameState 深比较不变(快照纯的反向锁)。"""
    st = _full_state()
    before = copy.deepcopy(st)
    synthesize_snapshot(st)
    assert st == before


def test_hp_none_implies_not_readable() -> None:
    """hp 单向蕴含不变式:hp None ⇒ hp_readable False(反向不成立)。"""
    st = _full_state()
    snap_ok = synthesize_snapshot(st)
    assert snap_ok.hp is not None and snap_ok.hp_readable is True

    st.hp_readable = False
    snap_bad = synthesize_snapshot(st)
    assert snap_bad.hp is None and snap_bad.hp_readable is False
    assert not (snap_bad.hp is None and snap_bad.hp_readable)


def test_snapshot_frozen() -> None:
    """快照纯:实例冻结(派生/覆写必须走显式快照变换,禁内联 replace 破墙)。"""
    snap = synthesize_snapshot(_full_state())
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.gold = 50


def test_decision_contract_shapes() -> None:
    """Decision 骨架:ops+control 形状可构造;frozen;空决策=合法零进展输入。"""
    d1 = Decision()                                  # decide 返回空批 = 合法「本步不动」
    assert d1.ops == () and d1.control is None
    d2 = Decision(ops=(AtomOp(op_key='buy:0', domain='shop'),),
                  control=None)
    d3 = Decision(ops=(), control=Bail(reason='event_overlay'))
    d4 = Decision(ops=(), control=Defer())
    assert d2.ops[0].domain == 'shop'
    assert isinstance(d3.control, Bail) and isinstance(d4.control, Defer)
    for d in (d1, d2, d3, d4):
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.ops = ()
    # 分类通道默认不可信(name='unknown'):未知子态不进 decide 的缺省安全态
    assert Snapshot().classification.confident is False
    assert SubstateClassification(name='prep_shop').confident is True
