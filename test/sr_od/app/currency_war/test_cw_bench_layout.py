"""bench 布局单一源主题锁(布局写回/播种同构/健康门/epoch 检差/守卫有牙性)。

方案正本 = T-280-交付报告.md §③ v2 修订版(批报告易失产物,裁决持久索引 =
ADR-0646);方案对抗审凭据 = reviews/T-280-方案对抗审.md。
来源:自 test_cw_t308_bench_layout_single_source.py 整体并入(2026-09-12 归并批,
按机制主题文件命名规范)。

病灶(T-280 诊断):reconcile 写回紧凑列表制造「tracked 列表下标布局 vs
BenchChar.slot 字段」布局双源——两域在播种时刻即读出不同布局(投影 =
bench_from_compact 槽号重构、tracked = mutate 下标演化),每次落洞动作放大
一次差异 → guard 多集等价分支 WARNING。修法三件:S2 写回经 bench_from_compact
重建槽位表(kernel/cw_reconcile,deployed 侧 deployed_from_compact 同构先例
补齐)+ S1 tracked 输入域消费点下标直拷 + S3 epoch 检差三步(churn 事件
通道,当前架构恒 'clean' 纯未来防御)。

锁面(五族;证明归宿 = 结构单一源 + 变异锁有牙性,math_proofs 零增,
T-182 §⑤-3 先例):
- S2 写回形状锁:带洞 SIFT 读写回后 = 定长 9 槽位表、布局 = 画面布局、
  slot = 下标+1 逐占用成立;
- 播种同构锁(引理 2 + 定理行为面):写回 → 播种(下标直拷)→ 同一动作
  两域转移(simulate ≡ mutate_bench_deployed,引理 1 结构单一源)→ 下标
  布局逐槽相等(不变量 I)+ guard 静默(多集等价分支前提不可达);
- T-280 例 2 帧重放锁:旧世界分叉双值在 S2+S1 世界转逐槽一致(验证设计①);
- 健康门锁:脏槽号(重复/0/10)→ 拒写保旧 + 留证 + epoch 不递增
  (bench_from_compact 的静默 fallback 在写回点升级为显式拒绝);
- S3 锁:epoch 递增条件(bench 写回 ∧ drifted)三面 + 检差三态封装
  (clean/reseeded/failed);
- 有牙性锁:历史 bug 态(紧凑 tracked × slot 稀疏)喂 guard 必命中多集
  等价分支——守卫对该形态有牙,与端到端静默锁互证「生产链不再制造」。

⚠️ 断言面纪律(「期望态不变=无效验证锚」警示):布局类断言一律落到
具体下标位(哪个下标是 None、哪个下标是谁,经 :func:`_layout`),禁退化
为多集/签名相等——多集相等正是本病灶的被遮蔽面,退化的锚对布局错误
结构性失明,守卫恒过 = 无效验证。
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import exec_state_of
from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_tracking
from sr_od.application.currency_war.kernel.cw_vocab import (
    BenchChar,
    BuyCard,
    CwWorkFrame,
    ShopCard,
    bench_from_compact,
    bench_place,
    mutate_bench_deployed,
    pad_bench,
    simulate,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op import cw_shop_action_ops


def _layout(bench) -> list[tuple[int, str | None]]:
    """下标布局逐槽快照((下标, 名|None))——布局类断言唯一合法锚形态。"""
    return [(i, (b.char_id if b is not None else None))
            for i, b in enumerate(bench)]


@pytest.fixture(autouse=True)
def _no_conflict_io(monkeypatch):
    """obs_conflict 源头桩(测试零真实副作用;健康门留证断言收集用)。"""
    import sr_od.application.currency_war.kernel.cw_observe as obs_mod
    conflicts: list[tuple] = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda *a, **kw: conflicts.append((a, kw)))
    return conflicts


# ===== S2 写回形状锁 =====

def test_s2_writeback_rebuilds_slot_table_with_holes():
    """带洞 SIFT 读(槽 1/3/4 占用,洞@2)写回后布局 = 画面布局(洞在
    真实位置),非紧凑挤前(旧写回直拷紧凑列表会把乱破错放下标 1 = 槽 2)。
    slot = 下标+1 逐占用成立(S2 重建后天然一致,消费端退化为恒等)。"""
    bench = [BenchChar(slot=1, char_id='缇宝', star=1),
             BenchChar(slot=3, char_id='乱破', star=1),
             BenchChar(slot=4, char_id='翡翠', star=1)]
    sess = StrategySession()
    assert reconcile_tracking(sess, bench, [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    assert len(tracked) == 9
    assert _layout(tracked) == [
        (0, '缇宝'), (1, None), (2, '乱破'), (3, '翡翠'),
        (4, None), (5, None), (6, None), (7, None), (8, None)]
    for i, bc in enumerate(tracked):
        if bc is not None:
            assert bc.slot == i + 1, f'下标 {i}: slot 须 = 下标+1'


def test_s2_writeback_equips_carried_and_drift_honest():
    """S2 重建不破坏对账合并语义:旧账装备经 _merge_equips 续接到新读对象
    (ADR-0387),slot 布局仍按新读重建(合并与布局两语义正交)。"""
    old = [BenchChar(slot=1, char_id='缇宝', star=1, equips=[['旧装']])]
    sess = StrategySession()
    exec_state_of(sess).tracked_bench_chars = list(old)
    bench = [BenchChar(slot=2, char_id='缇宝', star=1)]
    assert reconcile_tracking(sess, bench, [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    assert tracked[1] is not None and tracked[1].equips == [['旧装']]
    assert tracked[0] is None, '新读槽位=2 → 布局按新读重建(旧@1 不残留)'


# ===== 播种同构锁(引理2+定理行为面;T-280 例2 帧重放)=====

#: T-280 例2 seed(2026-09-09 09:20:57 帧):5 张读序紧凑,画面槽号
#: [1,3,4,5,6](洞@2)。旧世界:投影槽号重构(买丹恒落洞@槽2)、tracked
#: 紧凑演化(买丹恒落尾部洞@槽6)→ 双值分叉 + guard WARNING。
_CASE2_NAMES = ['缇宝', '乱破', '乱破', '翡翠', '翡翠']
_CASE2_SLOTS = [1, 3, 4, 5, 6]
_BUY_CARD = ShopCard(x=100, name='丹恒·饮月', faction='仙舟', cost=1, star=1)


def _sift_read() -> list[BenchChar]:
    """按画面槽号构造 SIFT 读(identify_slots 同构:slot=物理槽号)。"""
    return [BenchChar(slot=s, char_id=n, star=1)
            for s, n in zip(_CASE2_SLOTS, _CASE2_NAMES, strict=True)]


def test_t280_case2_frame_replay_seed_and_buy_isomorphic():
    """T-280 例 2 帧重放(S2+S1 世界):写回 → 播种 → 同一买入两域转移
    → 下标布局逐槽一致(旧世界分叉双值 → 转一致;丹恒同落首洞下标 1)。"""
    sess = StrategySession()
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    state = CwWorkFrame(gold=30, level=3, round_num=4, hp=40)
    state.bench = pad_bench(deepcopy(tracked))   # 与 cw_op_buy_cards 播种同式
    state.deployed = []
    act = BuyCard(card=deepcopy(_BUY_CARD))
    proj = simulate(state, act)
    mutate_bench_deployed(tracked, exec_state_of(sess).tracked_deployed, act)
    assert _layout(proj.bench) == _layout(tracked), '不变量 I:两域逐槽一致'
    assert proj.bench[1] is not None and proj.bench[1].char_id == '丹恒·饮月', \
        '丹恒落画面首洞(下标1=槽2),不再落尾部洞(旧 tracked 面)'


def test_full_visit_chain_guard_silent(monkeypatch):
    """端到端:写回 → 播种 → 两动作(买+卖)投影/mutate 同步 → guard 对拍
    零告警零炸(多集等价分支前提不可达 = 定理行为面;真分歧仍 AssertionError
    由既有守卫语义承担)。"""
    warnings: list[tuple] = []
    monkeypatch.setattr(cw_shop_action_ops, 'log',
                        type('W', (), {'warning': staticmethod(
                            lambda *a, **k: warnings.append(a))})())
    sess = StrategySession()
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    state = CwWorkFrame(gold=30, level=3, round_num=4, hp=40)
    state.bench = pad_bench(deepcopy(tracked))
    state.deployed = []
    act_buy = BuyCard(card=deepcopy(_BUY_CARD))
    proj = simulate(state, act_buy)
    mutate_bench_deployed(tracked, exec_state_of(sess).tracked_deployed, act_buy)
    cw_shop_action_ops.guard_expected_vs_tracked(proj, sess)
    # 第二动作:卖掉刚买的(两域同序转移)
    from sr_od.application.currency_war.kernel.cw_vocab import SellBench
    act_sell = SellBench(bench_idx=1, expect='丹恒·饮月')
    proj2 = simulate(proj, act_sell)
    mutate_bench_deployed(tracked, exec_state_of(sess).tracked_deployed, act_sell)
    cw_shop_action_ops.guard_expected_vs_tracked(proj2, sess)
    assert warnings == [], warnings


# ===== 健康门锁(静默 fallback → 显式拒绝)=====

@pytest.mark.parametrize('bad_slots', [
    pytest.param([1, 1], id='duplicate'),
    pytest.param([0, 2], id='zero'),
    pytest.param([2, 10], id='over_capacity'),
])
def test_health_gate_rejects_unhealthy_slots(bad_slots, _no_conflict_io):
    """脏槽号(重复/0/越界)→ 拒写保旧 + 留证(verdict 含健康门标记)+
    epoch 不递增(布局未变)。旧形态静默 fallback 首空槽 = 脏读数固化为
    形状自洽槽位表(布局错守卫恒过),写回点显式拒绝封死该通道。"""
    sess = StrategySession()
    _keep = [BenchChar(slot=1, char_id='旧账角色', star=1)]
    exec_state_of(sess).tracked_bench_chars = list(_keep)
    _epoch0 = exec_state_of(sess).bench_layout_epoch
    bench = [BenchChar(slot=s, char_id=n, star=1)
             for s, n in zip(bad_slots, ['甲', '乙'], strict=True)]
    assert reconcile_tracking(sess, bench, [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    assert [(b.char_id, b.slot) for b in tracked if b is not None] == \
        [('旧账角色', 1)], '健康门拒绝 → 保旧(脏读数不写回)'
    assert exec_state_of(sess).bench_layout_epoch == _epoch0
    verdicts = [kw.get('verdict', '') for _a, kw in _no_conflict_io]
    assert any('槽号健康门' in v for v in verdicts), verdicts


def test_health_gate_deployed_side_unaffected(_no_conflict_io):
    """健康门只辖 bench 写回分支:bench 侧被拒时 deployed 侧照常写回
    (deployed 槽位语义独立,ADR-0392;两分支互不牵连)。"""
    sess = StrategySession()
    exec_state_of(sess).tracked_bench_chars = [BenchChar(slot=1, char_id='旧', star=1)]
    bench = [BenchChar(slot=0, char_id='脏', star=1)]
    deployed = [BenchChar(slot=1, char_id='场上', star=1, position_pref='front')]
    assert reconcile_tracking(sess, bench, deployed, None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    assert [(b.char_id) for b in tracked if b is not None] == ['旧']
    assert [(d.char_id) for d in exec_state_of(sess).tracked_deployed
            if d is not None] == ['场上']


# ===== S3 epoch 锁 =====

def test_epoch_increments_on_drifted_bench_writeback():
    """bench 写回 ∧ 纠漂 → 布局代次 +1(churn 事件通道唯一写点)。"""
    sess = StrategySession()
    exec_state_of(sess).tracked_bench_chars = [BenchChar(slot=1, char_id='旧', star=1)]
    _epoch0 = exec_state_of(sess).bench_layout_epoch
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    assert exec_state_of(sess).bench_layout_epoch == _epoch0 + 1


def test_epoch_stable_on_equal_writeback():
    """写回但零纠漂(同布局重读)→ epoch 不动(防抖:一致帧不制造事件)。"""
    sess = StrategySession()
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    _epoch0 = exec_state_of(sess).bench_layout_epoch
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    assert exec_state_of(sess).bench_layout_epoch == _epoch0


def test_epoch_stable_on_deployed_only_drift():
    """deployed 侧纠漂(bench 读失败侧 None)→ epoch 不动(bench 布局未变;
    保守面:宁漏 deployed 驱动的误报、不漏 bench 布局真变化)。"""
    sess = StrategySession()
    deployed0 = [BenchChar(slot=1, char_id='场上', star=1, position_pref='front')]
    assert reconcile_tracking(sess, [], deployed0, None, source='t') is True
    _epoch0 = exec_state_of(sess).bench_layout_epoch
    deployed1 = [BenchChar(slot=1, char_id='换人', star=1, position_pref='front')]
    assert reconcile_tracking(sess, None, deployed1, None, source='t') is True
    assert exec_state_of(sess).bench_layout_epoch == _epoch0


# ===== S3 检差三步封装锁 =====

def _stale_state() -> tuple[CwWorkFrame, StrategySession, list]:
    """公共夹具:写回 → 播种 → (state, sess, tracked)。"""
    sess = StrategySession()
    assert reconcile_tracking(sess, _sift_read(), [], None, source='t') is True
    tracked = exec_state_of(sess).tracked_bench_chars
    state = CwWorkFrame(gold=30, level=3, round_num=4, hp=40)
    state.bench = pad_bench(deepcopy(tracked))
    state.deployed = []
    return state, sess, tracked


def test_stale_check_clean_when_epoch_unchanged():
    """代次未变 → 'clean'(常态;S2+S1 后当前架构恒此值),投影零触碰。"""
    state, sess, _tracked = _stale_state()
    _seed = exec_state_of(sess).bench_layout_epoch
    _before = _layout(state.bench)
    assert cw_shop_action_ops.reseed_bench_if_layout_stale(
        state, sess, _seed) == 'clean'
    assert _layout(state.bench) == _before


def test_stale_check_reseeded_on_epoch_bump(_no_conflict_io):
    """代次命中(人工递增模拟 visit 内 churn)→ 'reseeded':投影 bench
    按 tracked 重建(逐槽一致),真值侧胜出。"""
    state, sess, tracked = _stale_state()
    _seed = exec_state_of(sess).bench_layout_epoch
    state.bench[1] = BenchChar(slot=2, char_id='陈旧投影', star=1)   # 投影被污染
    exec_state_of(sess).bench_layout_epoch = _seed + 1
    assert cw_shop_action_ops.reseed_bench_if_layout_stale(
        state, sess, _seed) == 'reseeded'
    assert _layout(state.bench) == _layout(pad_bench(deepcopy(tracked)))


def test_stale_check_failed_when_tracked_unhealthy():
    """重播种被槽号健康门拒绝(tracked 槽号脏)→ 'failed':投影保持旧布局,
    调用方须 fail-stop 本段收工(禁在不可信布局上继续发射 bench_idx)。"""
    state, sess, _tracked = _stale_state()
    _seed = exec_state_of(sess).bench_layout_epoch
    _before = _layout(state.bench)
    ex = exec_state_of(sess)
    ex.bench_layout_epoch = _seed + 1   # 检差命中(先命中,再走重播种健康门)
    ex.tracked_bench_chars = [BenchChar(slot=0, char_id='脏', star=1)]
    assert cw_shop_action_ops.reseed_bench_if_layout_stale(
        state, sess, _seed) == 'failed'
    assert _layout(state.bench) == _before


# ===== 有牙性锁(历史 bug 态守卫必命中;与端到端静默互证)=====

def test_guard_multiset_branch_detects_historical_bug_shape(monkeypatch):
    """历史 bug 态(紧凑 tracked × slot 稀疏,T-280 例 2 旧世界)直接喂
    guard:多集等价分支必命中(WARNING + 按 tracked 重播种)——守卫对双源
    分叉有牙;生产链(S2+S1)不再制造该形态由端到端静默锁互证。"""
    warnings: list[tuple] = []
    monkeypatch.setattr(cw_shop_action_ops, 'log',
                        type('W', (), {'warning': staticmethod(
                            lambda *a, **k: warnings.append(a))})())
    # 旧世界 tracked:紧凑读序 × slot 稀疏(洞@2),pad 后买落尾部洞
    tracked_compact = _sift_read()
    pad_bench(tracked_compact)
    bench_place(tracked_compact, BenchChar(slot=0, char_id='丹恒·饮月', star=1))
    sess = StrategySession()
    exec_state_of(sess).tracked_bench_chars = tracked_compact
    # 旧世界投影:槽号重构布局(seed 槽号放置,洞@下标1),买后丹恒@洞
    state = CwWorkFrame(gold=30, level=3, round_num=4, hp=40)
    state.bench = bench_from_compact(deepcopy(_sift_read()))
    state.deployed = []
    proj = simulate(state, BuyCard(card=deepcopy(_BUY_CARD)))
    # 多集等价(6 成员同名同星)仅槽序分歧 → WARNING 降级不炸 + 重播种
    cw_shop_action_ops.guard_expected_vs_tracked(proj, sess)
    assert len(warnings) == 1, warnings
    assert '槽位布局漂移' in str(warnings[0][0])
