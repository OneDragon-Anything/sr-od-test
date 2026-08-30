"""备战决策结果缓存锁(设计出处 = 决策缓存可开臂修复批的落码报告,
语义见 prep_director 缓存段注释与 CwStrategy.prep_decision_cache_enabled)。

锁面:
1. 开关默认关(CwStrategy 类属性,DecisionV2Strategy 继承)= 默认行为与
   无缓存完全一致(策略开关生命周期门:默认关 + 开臂判据挂账);
2. 感知指纹字段面完整性:程序化遍历 Snapshot 全部字段逐一变异断言指纹变化
   ——「缓存键漏感知字段 = 错误复用」的结构性防线,新增快照字段不入此表即红;
3. P0 修复锁:实机 board(MappingProxyType 只读视图)可哈希,缓存查/存不炸;
4. 缓存键含 defer_count 与臂身份(strategy 实例 + registry 实例),跨 A/B 臂
   同指纹不互命中;
5. P1 修复锁:命中臂重放 decide 的会话簿记增量——命中帧计数器状态与未命中
   帧(真实 decide)逐位一致;decide 全量 session 写面锁死在已枚举清单内;
6. progressed 失效接线(源码锁)+ 命中统计导出口与周期日志(开臂判据①数据源)。
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.decision.cw_strategy import (  # noqa: E402
    CwStrategy,
    StrategySession,
)
from sr_od.application.currency_war.decision.decision_v2.contracts import (  # noqa: E402
    AtomOp,
    Decision,
    RewardSphere,
    Snapshot,
    SubstateClassification,
    SupplyBox,
    Tome,
)
from sr_od.application.currency_war.kernel.cw_state import (  # noqa: E402
    BenchChar,
    ShopCard,
)
from sr_od.application.currency_war.prep_director import (  # noqa: E402
    _DECISION_REPLAY_INT_FIELDS,
    _DECISION_REPLAY_LATCH_FIELDS,
    _decision_cache_clear,
    _decision_cache_lookup,
    _decision_cache_stats_snapshot,
    _decision_cache_store,
    _decision_replay_begin,
    prep_decision_fingerprint,
)

_SRC = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'


class _FakeStrategy:
    """缓存键臂身份段的替身 strategy(普通类实例可弱引用;每次实例化 = 新臂)。"""


def _strategy() -> object:
    return _FakeStrategy()


def test_switch_default_off():
    """开关默认关(开臂判据挂账见 CwStrategy.prep_decision_cache_enabled 注释)。"""
    assert CwStrategy.prep_decision_cache_enabled is False
    # 源码锁:无「默认开」翻臂痕迹(翻默认值须经开臂验证 + commit 记录)
    src = (_SRC / 'decision' / 'cw_strategy.py').read_text(encoding='utf-8')
    assert 'prep_decision_cache_enabled: bool = False' in src


# 逐字段变异对照表:(字段 → (值A, 值B))。键集必须与 Snapshot 字段集相等
# (完整性断言在测试体内)——新增快照字段未入表 = 本锁红 = 指纹漏字段。
_FIELD_PAIRS = {
    'schema_version': (1, 2),
    'classification': (SubstateClassification(name='a'),
                       SubstateClassification(name='b', confident=False)),
    'plane': (1, 2),
    'round_num': (1, 2),
    'node_type': (None, 'boss'),
    'selected_difficulty': ('', 'A8'),
    'gold': (None, 12),
    'gold_trusted': (False, True),
    'streak': (None, 3),
    'level': (None, 5),
    'xp_progress': (None, (2, 6)),
    'level_up_cost': (None, 6),
    'bench': ((None,), (BenchChar(slot=1),)),
    'deployed': ((None,), (BenchChar(slot=1, position_pref='front'),)),
    'board': (MappingProxyType({'c1': 2}), MappingProxyType({'c1': 3})),
    'deploy_cap': (None, 5),
    'deploy_vacancy': (None, 3),
    'free_bench_slots': (None, 2),
    'front_occupied': (frozenset(), frozenset({0})),
    'back_occupied': (frozenset(), frozenset({4})),
    'front_size': (4, 3),
    'back_size': (6, 5),
    'shop_open': (False, True),
    'shop_cards': (None, (ShopCard(x=1),)),
    'spheres': ((), (RewardSphere(color='g', x=1, y=2),)),
    'boxes': ((), (SupplyBox(x=1, y=2),)),
    'tomes': ((), (Tome(x=3, y=4),)),
    'box_overlay_open': (False, True),
    'event_overlay': (None, '选择伙伴'),
    'hp': (None, 88),
    'hp_readable': (False, True),
}


def test_fingerprint_covers_every_snapshot_field():
    """字段面完整性锁:任一字段变异 → 指纹必变(漏字段 = 错误复用防线)。"""
    field_names = {f.name for f in dataclasses.fields(Snapshot)}
    assert set(_FIELD_PAIRS) == field_names, (
        f'指纹变异表与 Snapshot 字段面不一致:缺 {field_names - set(_FIELD_PAIRS)}, '
        f'多 {set(_FIELD_PAIRS) - field_names}')
    base = Snapshot()
    for name, (va, vb) in _FIELD_PAIRS.items():
        sa = dataclasses.replace(base, **{name: va})
        sb = dataclasses.replace(base, **{name: vb})
        assert prep_decision_fingerprint(sa) != prep_decision_fingerprint(sb), (
            f'字段 {name} 变异未改变指纹 = 缓存键漏该字段(错误复用风险)')


def test_fingerprint_equal_for_equal_snapshots():
    """同语义快照 → 同指纹(深容器不因对象身份不同而异)。"""
    a = Snapshot(gold=30, bench=(BenchChar(slot=1, char_id='x'),),
                 board=MappingProxyType({'c1': 2}))
    b = Snapshot(gold=30, bench=(BenchChar(slot=1, char_id='x'),),
                 board=MappingProxyType({'c1': 2}))
    assert prep_decision_fingerprint(a) == prep_decision_fingerprint(b)


def test_proxy_board_fingerprint_hashable_and_cache_roundtrip():
    """P0 修复锁:实机型 board(MappingProxyType)指纹可哈希,缓存查/存全链
    不炸(修复前 proxy 原样进指纹元组,作 dict 键哈希时 TypeError)。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30, plane=1, round_num=3,
                    board=MappingProxyType({'c1': 2, 'c2': 1}))
    fp = prep_decision_fingerprint(snap)
    hash(fp)   # 修复前:TypeError: unhashable type: 'mappingproxy'
    sess = SimpleNamespace(defer_count=0)
    strat = _strategy()
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    hit = _decision_cache_lookup(
        Snapshot(gold=30, plane=1, round_num=3,
                 board=MappingProxyType({'c1': 2, 'c2': 1})),
        sess, strat)
    assert hit is not None
    _decision_cache_clear('测试清理')


def _decision_a() -> Decision:
    return Decision(ops=(AtomOp(op_key='run_buy_phase', domain='shop'),))


def test_same_fingerprint_reuses_decision():
    """「指纹未变 → 意向不变」:同指纹查缓存返回缓存的同一 (Decision, action)。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30, plane=1, round_num=3)
    sess = SimpleNamespace(defer_count=0)
    strat = _strategy()
    action = object()
    _decision_cache_store(snap, sess, strat, _decision_a(), action,
                          _decision_replay_begin(sess))
    hit = _decision_cache_lookup(Snapshot(gold=30, plane=1, round_num=3),
                                 sess, strat)
    assert hit is not None
    hit_decision, hit_action = hit
    assert hit_decision == _decision_a()
    assert hit_action is action
    _decision_cache_clear('测试清理')


def test_defer_count_in_cache_key():
    """defer_count 变化 → 缓存键变化(Defer 门=2 改变策略行为的显式会话面)。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30)
    sess = SimpleNamespace(defer_count=0)
    strat = _strategy()
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    assert _decision_cache_lookup(snap, SimpleNamespace(defer_count=1),
                                  strat) is None
    assert _decision_cache_lookup(snap, sess, strat) is not None
    _decision_cache_clear('测试清理')


def test_owner_identity_in_cache_key():
    """臂身份锁:不同 strategy/registry 实例同指纹互不命中(防跨 A/B 臂污染)。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30, plane=1, round_num=3)
    sess = SimpleNamespace(defer_count=0)
    strat_a = _strategy()
    strat_b = _strategy()
    _decision_cache_store(snap, sess, strat_a, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    assert _decision_cache_lookup(snap, sess, strat_b) is None
    assert _decision_cache_lookup(snap, sess, strat_a) is not None
    _decision_cache_clear('测试清理')


def test_cache_clear_invalidates():
    """progressed 失效语义:_decision_cache_clear 后同指纹必 miss。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30)
    sess = SimpleNamespace(defer_count=0)
    strat = _strategy()
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    _decision_cache_clear('动作落地')
    assert _decision_cache_lookup(snap, sess, strat) is None


# ===== P1 修复锁:命中臂簿记重放 =====

def test_failed_action_phase_advance_forces_real_recompute():
    """失败恢复场景锁:动作✗后相位推进 → 下一 decide 必须真实重算。

    真实 decide 的 _main_flow_step 是非幂等阶段机(相位前移借此换向动作)。
    键含 decide **前**簿记基线:命中重放使相位前进后,同条目不可再命中——
    防「同一失败动作冻结重发无限 stall / 相位重放越界出域(4,5,…)」。
    守卫移除验证 = 从 _decision_cache_key 删簿记基线段后本锁必红。"""
    _decision_cache_clear('测试前置')
    sess = SimpleNamespace(defer_count=0, prep_phase=0, prep_phase_retry=0,
                           free_bench_gold_wait=0, v2_ever_full_interest=False)
    snap = Snapshot(gold=30, plane=1, round_num=3)
    strat = _strategy()
    base = _decision_replay_begin(sess)
    sess.prep_phase += 1   # 真实 decide 的阶段机前移(0→1,出 RunBuyPhase)
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act', base)
    # 回滚到 decide 前基线(动作✗、板面指纹未变的形态)→ 命中一次:
    # 重放把相位推回 1(= 真实 decide 后状态,簿记已跑)
    sess.prep_phase = 0
    assert _decision_cache_lookup(snap, sess, strat) is not None
    assert sess.prep_phase == 1
    # 相位已前进 → 键已换 → 连续多次查询全部 miss:下一 decide 必然真实重算
    # (真实重算在相位 1 出 RunDeploy = 失败恢复机制保留;相位只经真实 decide
    # 推进,不会重放越界出域)
    for _ in range(3):
        assert _decision_cache_lookup(snap, sess, strat) is None
    _decision_cache_clear('测试清理')


def test_zero_delta_entry_repeat_hit_is_idempotent():
    """零增量条目可重复命中且零写面:纯分支 decide(箱/球/典籍/出战面等,
    decide 对 session 零写)的重复命中 ≡ 真实 decide 的重复同判(键不变 =
    会话输入不变),无害且正是缓存收益主体。"""
    _decision_cache_clear('测试前置')
    sess = SimpleNamespace(defer_count=0, prep_phase=3, prep_phase_retry=0,
                           free_bench_gold_wait=0, v2_ever_full_interest=True)
    snap = Snapshot(gold=30, plane=1, round_num=3)
    strat = _strategy()
    before = dict(vars(sess))
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    for _ in range(3):
        assert _decision_cache_lookup(snap, sess, strat) is not None
    for k, v in before.items():
        assert getattr(sess, k) == v
    _decision_cache_clear('测试清理')


def test_hit_replays_decide_bookkeeping_bitwise():
    """单帧锁:命中帧计数器状态与未命中帧(真实跑了 decide)逐位一致。

    存储时捕获的簿记增量(prep_phase 阶段机 / free_bench_gold_wait 等待计数 /
    满息 latch)在命中臂逐一重放;重放后各重放字段值 == 真实 decide 后值。"""
    _decision_cache_clear('测试前置')
    sess = SimpleNamespace(defer_count=0, prep_phase=0, prep_phase_retry=1,
                           free_bench_gold_wait=0, v2_ever_full_interest=False)
    snap = Snapshot(gold=30, plane=1, round_num=3)
    strat = _strategy()
    base = _decision_replay_begin(sess)
    # 模拟一次真实 decide 的簿记面(与 decide 副作用变更集清单同形):
    sess.prep_phase += 1          # 阶段机出动作时前移
    sess.prep_phase_retry += 1    # 空板出战守卫回部署段计数
    sess.free_bench_gold_wait += 1   # 腾席链 b 金真值等待
    sess.v2_ever_full_interest = True   # r412 满息 latch
    post_decide = {k: getattr(sess, k)
                   for k in (*_DECISION_REPLAY_INT_FIELDS,
                             *_DECISION_REPLAY_LATCH_FIELDS)}
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act', base)
    # 回滚到 decide 前基线,再走命中臂:重放必须把字段推回 post_decide 逐位值
    sess.prep_phase = 0
    sess.prep_phase_retry = 1
    sess.free_bench_gold_wait = 0
    sess.v2_ever_full_interest = False
    assert _decision_cache_lookup(snap, sess, strat) is not None
    for k in (*_DECISION_REPLAY_INT_FIELDS, *_DECISION_REPLAY_LATCH_FIELDS):
        assert getattr(sess, k) == post_decide[k], (
            f'命中臂簿记重放不一致:{k} 命中帧={getattr(sess, k)} '
            f'未命中帧={post_decide[k]}')
    _decision_cache_clear('测试清理')


def test_hit_replay_zero_delta_is_noop():
    """簿记无增量(latch 已真/int 无变化)→ 命中臂零写面(幂等)。"""
    _decision_cache_clear('测试前置')
    sess = SimpleNamespace(defer_count=0, prep_phase=2, prep_phase_retry=0,
                           free_bench_gold_wait=3, v2_ever_full_interest=True)
    snap = Snapshot(gold=30)
    strat = _strategy()
    before = dict(vars(sess))
    _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                          _decision_replay_begin(sess))
    # 命中后字段值不得漂移(无增量 → 不写)
    assert _decision_cache_lookup(snap, sess, strat) is not None
    for k, v in before.items():
        assert getattr(sess, k) == v
    _decision_cache_clear('测试清理')


# ===== decide 全量副作用面锁(P1-2 变更集清单的可执行形态)=====

#: decide 调用树(DecideAdapter.decide → prep_brain → decide_prep_action)允许
#: 写的全部 session 键。决策加新写面 = 本锁红 → 必须先入 prep_director 的
#: 重放清单(_DECISION_REPLAY_*)再合入,否则缓存命中帧静默漏簿记。
_ALLOWED_DECIDE_SESSION_WRITES = {
    'v2_ever_full_interest',    # r412 满息 latch(decide_prep_action 后置采样)
    'prep_phase',               # 主流程阶段机(_main_flow_step 出动作时前移)
    'prep_phase_retry',         # 空板出战守卫回部署段计数
    'free_bench_gold_wait',     # 腾席链 b 金真值等待计数
}


def _run_decide_and_diff_session(snapshot: Snapshot,
                                 sess: StrategySession) -> set[str]:
    from sr_od.application.currency_war.decision.decision_v2.strategy import (
        DecisionV2Strategy,
    )
    from sr_od.application.currency_war.decision_assembly import DecideAdapter
    adapter = DecideAdapter(DecisionV2Strategy(),
                            SimpleNamespace(character_priority=[]), None)
    before = dict(vars(sess))
    adapter.decide(snapshot, sess)
    return {k for k, v in vars(sess).items()
            if k not in before or before[k] != v}


def _decide_snapshot(**kw) -> Snapshot:
    kw.setdefault('classification',
                  SubstateClassification(name='prep_shop', confident=True))
    return Snapshot(**kw)


def test_decide_session_write_surface_lock():
    """decide 全量 session 写面锁:真实 decide 的变更集 ⊆ 已枚举清单。

    缓存命中臂只重放清单内增量;decide 若新增任何 session 写面而未入清单,
    命中帧即静默漏簿记——本锁以「全量 dict diff ⊆ 白名单」把清单钉死。"""
    _decision_cache_clear('测试前置')
    scenarios = [
        # 主流程:空球空箱 → 阶段机前移出 RunBuyPhase
        _decide_snapshot(gold=30, gold_trusted=True, plane=1, round_num=3,
                         free_bench_slots=2, board=MappingProxyType({})),
        # 满息 latch 采样:金可信 ≥50 → v2_ever_full_interest 置真
        _decide_snapshot(gold=55, gold_trusted=True, plane=1, round_num=3,
                         free_bench_slots=2, board=MappingProxyType({})),
        # 腾席链入口:有球满席(defer 门内)→ free_bench_step 面
        _decide_snapshot(gold=30, gold_trusted=True, plane=1, round_num=3,
                         free_bench_slots=0, deploy_vacancy=0,
                         spheres=(RewardSphere(color='g', x=1, y=2),),
                         board=MappingProxyType({})),
    ]
    for snap in scenarios:
        changed = _run_decide_and_diff_session(snap, StrategySession())
        unexpected = changed - _ALLOWED_DECIDE_SESSION_WRITES
        assert not unexpected, (
            f'decide 出现未枚举的 session 写面 {unexpected}——缓存命中臂不会'
            f'重放它们,必须先入 prep_director._DECISION_REPLAY_* 清单')
    _decision_cache_clear('测试清理')


def test_decide_bookkeeping_matches_replay_whitelist():
    """重放清单与真实 decide 写面的交集锁:真实 decide 实际写过的簿记键
    必须都在重放清单内(防「白名单漏收真实写面」方向的缺口)。"""
    assert set(_ALLOWED_DECIDE_SESSION_WRITES) == (
        set(_DECISION_REPLAY_INT_FIELDS) | set(_DECISION_REPLAY_LATCH_FIELDS))


# ===== P2 修复锁:命中统计导出口与周期日志(开臂判据①数据源)=====

def test_cache_stats_export_and_periodic_log(monkeypatch, caplog):
    """命中/未命中计数可导出、且每 N 次 decide 落一行统计日志。"""
    import logging
    import sys as _sys
    _decision_cache_clear('测试前置')
    module = _sys.modules['sr_od.application.currency_war.prep_director']
    monkeypatch.setattr(module, '_DECISION_STATS_LOG_EVERY', 2)
    module._decision_cache_stats.update(hit=0, miss=0)
    snap = Snapshot(gold=30, plane=1, round_num=3)
    sess = SimpleNamespace(defer_count=0)
    strat = _strategy()
    with caplog.at_level(logging.INFO, logger='one_dragon'):
        _decision_cache_lookup(snap, sess, strat)      # miss 1(触发 n=1 不落)
        _decision_cache_store(snap, sess, strat, _decision_a(), 'act',
                              _decision_replay_begin(sess))
        _decision_cache_lookup(snap, sess, strat)      # hit 1 → n=2 落行
    stats = _decision_cache_stats_snapshot()
    assert stats == {'hit': 1, 'miss': 1}
    assert any('决策缓存统计' in r.message for r in caplog.records)
    _decision_cache_clear('测试清理')


def test_decide_port_wiring_source_lock():
    """接线源码锁:_decide_port 先查缓存后调 decide;progressed 即清缓存
    (守卫存在性;守卫移除验证 = 删 lookup 分支后 test_same_fingerprint_
    reuses_decision 的生产路径前提消失)。"""
    src = (_SRC / 'prep_director.py').read_text(encoding='utf-8')
    assert '_decision_cache_lookup(snapshot, session_,\n                                                match.strategy)' in src
    assert '_decision_cache_store(snapshot, session_, match.strategy,' in src
    assert '_decision_replay_begin(session_)' in src
    # 键含 decide 前簿记基线(相位推进即换键,失败恢复保留)——
    # 守卫移除验证:删该段后 test_failed_action_phase_advance_forces_real_recompute 红
    assert 'bookkeeping_base=replay_base' in src
    # 失效点在 progressed 赋值之后、同函数内(动作落地即清)
    assert "if progressed and _cache_on:" in src
    assert "_decision_cache_clear('动作落地" in src
