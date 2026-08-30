"""备战决策结果缓存锁(w891 延迟审计候选②;设计出处 = 同目录 REPORT 批
`.debug/temp/currency_war/w893_quickwin/REPORT.md` §1.2)。

锁面:
1. 开关默认关(CwStrategy 类属性,DecisionV2Strategy 继承)= 默认行为与
   无缓存完全一致(策略开关生命周期门:默认关 + 开臂判据挂账);
2. 感知指纹字段面完整性:程序化遍历 Snapshot 全部字段逐一变异断言指纹变化
   ——「缓存键漏感知字段 = 错误复用」的结构性防线,新增快照字段不入此表即红;
3. 「指纹未变 → 意向不变」语义:同指纹查缓存返回同一 (Decision, action);
4. 缓存键含 defer_count(框架侧 Defer 门计数,快照不可见的显式会话面);
5. progressed 失效接线(源码锁):任一动作落地即清空缓存。
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
    _decision_cache_clear,
    _decision_cache_lookup,
    _decision_cache_store,
    prep_decision_fingerprint,
)

_SRC = _REPO / 'src' / 'sr_od' / 'application' / 'currency_war'


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


def _decision_a() -> Decision:
    return Decision(ops=(AtomOp(op_key='run_buy_phase', domain='shop'),))


def test_same_fingerprint_reuses_decision():
    """「指纹未变 → 意向不变」:同指纹查缓存返回缓存的同一 (Decision, action)。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30, plane=1, round_num=3)
    sess = SimpleNamespace(defer_count=0)
    action = object()
    _decision_cache_store(snap, sess, _decision_a(), action)
    hit = _decision_cache_lookup(Snapshot(gold=30, plane=1, round_num=3), sess)
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
    _decision_cache_store(snap, sess, _decision_a(), 'act')
    assert _decision_cache_lookup(snap, SimpleNamespace(defer_count=1)) is None
    assert _decision_cache_lookup(snap, sess) is not None
    _decision_cache_clear('测试清理')


def test_cache_clear_invalidates():
    """progressed 失效语义:_decision_cache_clear 后同指纹必 miss。"""
    _decision_cache_clear('测试前置')
    snap = Snapshot(gold=30)
    sess = SimpleNamespace(defer_count=0)
    _decision_cache_store(snap, sess, _decision_a(), 'act')
    _decision_cache_clear('动作落地')
    assert _decision_cache_lookup(snap, sess) is None


def test_decide_port_wiring_source_lock():
    """接线源码锁:_decide_port 先查缓存后调 decide;progressed 即清缓存
    (守卫存在性;守卫移除验证 = 删 lookup 分支后 test_same_fingerprint_
    reuses_decision 的生产路径前提消失)。"""
    src = (_SRC / 'prep_director.py').read_text(encoding='utf-8')
    assert '_decision_cache_lookup(snapshot, session_)' in src
    assert '_decision_cache_store(snapshot, session_, decision,' in src
    # 失效点在 progressed 赋值之后、同函数内(动作落地即清)
    assert "if progressed and _cache_on:" in src
    assert "_decision_cache_clear('动作落地" in src
