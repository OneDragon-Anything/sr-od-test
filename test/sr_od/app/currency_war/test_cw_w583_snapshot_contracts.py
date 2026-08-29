"""快照契约 + sim 合成器无损验证门(契约加固批后的现行版本)。

锁的是契约,不是行为数值(零旧行为变更:decide 无实现体、现役循环零触碰):

1. 进出无损:同一 GameState 逐字段进出,Synthesize 映射式与
   SCHEMA_DRAFT.md §四「来源」列一致;
2. None 语义保持:各「读不到」变体 → 快照对应字段为 None
   (禁 0/空/兜底——错值比 None 更毒,「读不到≠真值」纪律的回归锁);
3. 分类合成契约:sim 侧 confident 恒 True;
4. 只读保证:合成前后 GameState 深比较不变(快照纯的反向锁);
5. hp 单向蕴含不变式:hp is None ⇒ hp_readable is False;
6. Decision 契约骨架:control 与 ops 并存形状可构造;
7. 容器隔离防线:快照容器只读 + 元素深拷贝(污染快照不回写上游
   GameState)——原锁曾以「snap.bench[0] is st.bench[0]」把共享可变元素
   钉死为合法,与 frozen 不变式相悖,已按锁纪律改写为「深拷贝后 ==
   等价 + 非同引用」(改锁依据 = 对抗审计攻击2:frozen 挡不住容器就地
   变异,共享引用使策略侧一行赋值即可污染上游 GameState);
8. 显式变换通道:derive_snapshot 派生新实例、原帧不受扰、冻结性不丢;
9. schema_version 执行者:DirectorV2 环顶对版本不匹配显式抛错;
10. 逆真值注入表达性:合成器 9 个恒真位逐一可构造反事实快照(防批③
    适配器把恒真面原样过河后策略端 None/False 改判式无载体)。

出处:设计审计报告 .debug/temp/currency_war/w561_arch_review/REPORT.md
§三.1/.2/.8 + 攻击9 修法(合成器门=Schema 定稿第一个消费者测试);
Schema 审定版 = .debug/temp/currency_war/w583_stage2_contracts/SCHEMA_DRAFT.md;
加固依据 = .debug/temp/currency_war/w598_contracts_adversarial/REPORT.md。
"""
from __future__ import annotations

import copy
import dataclasses
from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    DEPLOYED_FRONT_CAPACITY,
    BenchChar,
    GameState,
    ShopCard,
    deployed_place,
)

from sr_od.application.currency_war.sim.runner import synthesize_snapshot
from sr_od.application.currency_war.decision.decision_v2.contracts import (
    SNAPSHOT_SCHEMA_VERSION,
    AtomOp,
    Bail,
    Decision,
    Defer,
    RewardSphere,
    Snapshot,
    SnapshotSchemaVersionError,
    SubstateClassification,
    derive_snapshot,
)
from sr_od.application.currency_war.decision.decision_v2.director_v2 import (
    DirectorV2,
    _DirectorPorts,
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
    # 单位域:元素深拷贝(值等价、非同引用——原 is 共享断言已废,改锁依据见模块 docstring)
    assert snap.bench[0] == st.bench[0] and snap.bench[0] is not st.bench[0]
    assert snap.bench[4] == st.bench[4] and snap.bench[4] is not st.bench[4]
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
    # 商店域:列表拷贝(容器与元素均非同引用)、逐项同值
    assert snap.shop_cards == tuple(st.shop)
    assert snap.shop_cards is not st.shop
    assert all(sc is not orig
               for sc, orig in zip(snap.shop_cards, st.shop))
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
    assert snap.board is None                   # None(不可读)≠ 空 mapping(真清空)
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
    """快照纯:实例冻结(派生/覆写必须走 derive_snapshot,禁内联 replace 破墙)。"""
    snap = synthesize_snapshot(_full_state())
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.gold = 50


def test_snapshot_container_isolation() -> None:
    """容器隔离防线:容器只读 + 元素深拷贝——污染快照不回写上游 GameState。"""
    st = _full_state()
    snap = synthesize_snapshot(st)
    assert isinstance(snap.bench, tuple)
    assert isinstance(snap.deployed, tuple)
    assert isinstance(snap.shop_cards, tuple)
    # board 只读映射:就地写显式炸(TypeError),不是静默生效
    with pytest.raises(TypeError):
        snap.board['lightning'] = 5  # type: ignore[index]
    # 元素变异只落在快照私有拷贝上,上游零污染(原 is 共享断言合法化的实洞已焊)
    snap.bench[0].star = 9
    snap.deployed[0].char_id = 'polluted'
    snap.shop_cards[0].name = 'polluted'
    assert st.bench[0].star == 2
    assert st.deployed[0].char_id == 'acheron'
    assert st.shop[0].name == 'jiaoqiu'


def test_derive_snapshot_transform_channel() -> None:
    """显式变换通道:派生新实例、原帧不受扰、派生帧容器互不共享、冻结性不丢。"""
    snap = synthesize_snapshot(_full_state())
    derived = derive_snapshot(snap, gold=50)
    assert derived.gold == 50 and snap.gold == 47
    derived.bench[0].star = 9
    assert snap.bench[0].star == 2              # 派生帧元素深拷贝,不串原帧
    with pytest.raises(dataclasses.FrozenInstanceError):
        derived.gold = 1


def test_director_rejects_version_mismatch() -> None:
    """schema_version 执行者:DirectorV2 环顶对不匹配版本显式抛错(非注释纪律)。"""
    snap = synthesize_snapshot(_full_state())
    bad = derive_snapshot(snap, schema_version=SNAPSHOT_SCHEMA_VERSION + 1)
    ports = _DirectorPorts(
        decide=lambda s, sess: Decision(),
        observe=lambda heavy: bad,
        execute=lambda op: (True, ''),
        recover=lambda: False,
        force_battle=lambda: True,
        is_stopped=lambda: False,
        stop_with_evidence=lambda msg: None,
        record_defect=lambda kind, detail: None,
    )
    session = SimpleNamespace(defer_count=0, prep_phase=0, bail_reason_counts={})
    with pytest.raises(SnapshotSchemaVersionError):
        DirectorV2(ports).run(session)


def test_sim_constant_truth_positions_counterfactual_expressible() -> None:
    """逆真值注入表达性:合成器 9 个恒真位逐一可构造反事实快照。

    sim 合成器恒真值(与实机识别侧的边界态断层),本锁钉住契约面可表达
    非恒真位——批③逆真值 fixture/策略端 None/False 改判式有载体,不会
    被「合成器永远恒真」锁死。
    """
    cases: list[tuple[str, Snapshot, object]] = [
        ('classification.confident', Snapshot(
            classification=SubstateClassification(name='prep_shop',
                                                  confident=False)),
            lambda s: s.classification.confident is False),
        ('gold_trusted', Snapshot(gold_trusted=False),
         lambda s: s.gold_trusted is False),
        ('shop_open', Snapshot(shop_open=False),
         lambda s: s.shop_open is False),
        ('board 不可读', Snapshot(board=None), lambda s: s.board is None),
        ('free_bench_slots 失读', Snapshot(free_bench_slots=None),
         lambda s: s.free_bench_slots is None),
        ('spheres 非空', Snapshot(spheres=(RewardSphere(color='blue', x=1, y=2),)),
         lambda s: len(s.spheres) == 1),
        ('event_overlay 挡操作', Snapshot(event_overlay='modal_event'),
         lambda s: s.event_overlay == 'modal_event'),
        ('box_overlay_open', Snapshot(box_overlay_open=True),
         lambda s: s.box_overlay_open is True),
        ('shop_cards 未读', Snapshot(shop_cards=None),
         lambda s: s.shop_cards is None),
    ]
    assert len(cases) == 9
    for name, snap_cf, check in cases:
        assert check(snap_cf), name


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
