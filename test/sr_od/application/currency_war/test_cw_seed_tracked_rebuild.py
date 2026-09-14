"""T-251 种子段 tracked 空账读屏重建回归锁(2026-09-15 接管停局事故)。

事故形态:接管局/新账首分发即商店节点时,visit 入口观察
(read_game_state phase=prep_shop_open)设计上不读 bench 身份,店开 0n
分发路径(visit_open_shop→run_buy_waves)也不经过备战环 heavy 观察
(reconcile_tracking 是 tracked 主账唯一生产重建写点)→ tracked 主账
从未被建;种子守卫 guard_expected_vs_tracked(stage='seed') 真分歧即
粘性崩溃循环(实机两局停机实证)。

锁的七件事:
1. 接管形态(tracked 空 + 屏幕 9 件):重建出口两账(tracked+容器)
   同帧落地,真实守卫 stage='seed' 不炸,阀门落位;
2. 分叉形态红线(tracked 有账缺件 = 实锤组成,非接管):出口零读屏零写
   ('tracked_present'),真实种子守卫仍 AssertionError 红——有账分叉
   = 丢件/幻影,重建会掩盖真 bug,必须响亮暴露;
3. 单向阀门:同 visit 第二次调用不再读屏('valve_closed'),读函数恰
   被调一次(读链失读形态下同样关阀,两账零写);
4. 槽号不健康(重复槽号):拒绝写账,tracked 保持空账(与 reconcile
   写回健康门同式,坏槽号不进不可逆卖出链);
5. 失读/真空分型:读链 None = 失读落缺陷台账显影;[] = 屏幕席真空
   (合法态)不落台账零写;
6. 接管待办反向分叉形态(2026-09-15 04:39 实锤:接管标记在场,容器
   expected 8 件 vs tracked 9 件多镜流):有账也以屏幕真值两账再锚定,
   真实种子守卫不炸,待办消费置 False;
7. 接管待办读链失读:两账零写且待办不消费(下 visit 重试)。
"""
from __future__ import annotations

import pytest

from sr_od.application.currency_war.kernel.cw_exec_state import (
    BenchChar,
    bench_from_compact,
    exec_state_of,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    bench_slots_of,
    bench_view_of_slots,
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.operations.cw_op.cw_shop_action_ops import (
    ShopVisitLedger,
    guard_expected_vs_tracked,
)
from sr_od.application.currency_war.operations.cw_screen.cw_screen_buy_cards import (
    rebuild_tracked_at_seed_if_vacant,
)
from sr_od.application.currency_war.telemetry import defects

_SIG = ChannelSig(family='logic_action', actor='CwScreenPrep')

# 实锤组成(2026-09-15 01:41 局种子守卫 expected 侧九件)
_SCREEN_9 = [
    ('花火', 1), ('不死途', 1), ('不死途', 3), ('艾丝妲', 1), ('椒丘', 1),
    ('风堇', 1), ('藿藿', 1), ('大丽花', 1), ('丹恒·腾荒', 2),
]


def _bench_chars(names) -> list:
    """名单 → 紧缩 BenchChar 读链形态(槽号 = 读序,1 基)。"""
    return [BenchChar(slot=i + 1, char_id=n, star=s)
            for i, (n, s) in enumerate(names)]


def _fake_reader(read):
    """读链替身:返回 (read_fn, 调用帧列表),供断言读屏次数。"""
    calls: list = []

    def _read(frame):
        calls.append(frame)
        return read
    return _read, calls


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入(测试零真实副作用)+ 留调用记录供显影断言。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, expected, observed))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _tracked_sig(session) -> list:
    return [(b.char_id, b.star) for b in
            (exec_state_of(session).tracked_bench_chars or [])
            if b is not None]


def test_takeover_vacant_rebuilds_both_accounts_and_seed_guard_passes(
        monkeypatch):
    """接管形态(tracked 空+屏幕 9 件):两账同帧重建,真实种子守卫不炸。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bs = board_state_of(session)
    assert bs.bench.value is None   # 容器 bench 未观察(接管真空)
    assert _tracked_sig(session) == []
    reader, calls = _fake_reader(_bench_chars(_SCREEN_9))
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'rebuilt'
    assert len(calls) == 1   # 恰一次读屏
    assert _tracked_sig(session) == _SCREEN_9
    # 容器 bench 同帧(观察写端),两账同源
    assert ([(b.char_id, b.star) for b in bench_slots_of(bs) if b is not None]
            == _SCREEN_9)
    assert ledger.tracked_seed_rebuild_done is True   # 阀门落位
    # 回归锁本形:真实守卫 stage='seed' 通过(不抛)
    guard_expected_vs_tracked(bs, session, stage='seed')


def test_divergent_tracked_present_skips_rebuild_and_guard_still_red(
        monkeypatch):
    """分叉形态红线(tracked 有账缺件):零读屏零写,种子守卫仍红。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bs = board_state_of(session)
    bs.write_logic(bs.bench, bench_view_of_slots(_bench_chars(_SCREEN_9)),
                   produced_by='test', sig=_SIG)
    # 实锤组成:tracked 缺 ('不死途', 1)(01:41 局形态)
    exec_state_of(session).tracked_bench_chars = bench_from_compact([
        bc for bc in _bench_chars(_SCREEN_9)
        if not (bc.char_id == '不死途' and bc.star == 1)])
    reader, calls = _fake_reader(_bench_chars(_SCREEN_9))
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'tracked_present'
    assert calls == []   # 红线:有账不读屏
    assert ledger.tracked_seed_rebuild_done is False   # 阀门未动
    assert _tracked_sig(session) == [sig for sig in _SCREEN_9
                                     if sig != ('不死途', 1)]   # 零写
    with pytest.raises(AssertionError, match='expected='):
        guard_expected_vs_tracked(bs, session, stage='seed')


def test_valve_once_per_visit_and_read_failure_writes_nothing(monkeypatch):
    """单向阀门:同 visit 恰一次尝试;失读(None)两账零写。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    reader, calls = _fake_reader(None)   # 失读形态
    ledger = ShopVisitLedger()

    first = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)
    assert first == 'read_failed'
    assert _tracked_sig(session) == []   # 失读零写
    assert ledger.tracked_seed_rebuild_done is True

    second = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)
    assert second == 'valve_closed'   # 阀门已关,不重试
    assert len(calls) == 1   # 读函数本 visit 恰被调一次


def test_unhealthy_slots_refuse_write(monkeypatch):
    """槽号不健康(重复):拒绝写账,tracked 保持空账,坏槽号不进账。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bad = [BenchChar(slot=2, char_id='花火', star=1),
           BenchChar(slot=2, char_id='刃', star=1)]   # 槽号重复
    reader, _calls = _fake_reader(bad)
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'slot_unhealthy'
    assert _tracked_sig(session) == []
    assert ledger.tracked_seed_rebuild_done is True


def test_read_failure_records_defect_row(monkeypatch):
    """失读(None)落缺陷台账显影(判读「读链是否退化」可查本键)。"""
    rows = _spy_defects(monkeypatch)
    session = StrategySession()
    r1, _c1 = _fake_reader(None)

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ShopVisitLedger(), read_bench_fn=r1)

    assert outcome == 'read_failed'
    assert any(kind == defects.DEFECT_KIND_TRACKED_SEED_REBUILD
               for _s, kind, _e, _o in rows)


def test_screen_vacant_is_legal_state_silent_and_zero_write(monkeypatch):
    """屏幕席真空([])= 合法态:不落台账、零写,tracked 保持空账。"""
    rows = _spy_defects(monkeypatch)
    session = StrategySession()
    r2, _c2 = _fake_reader([])

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ShopVisitLedger(), read_bench_fn=r2)

    assert outcome == 'screen_vacant'
    assert rows == []   # 真空合法态:零台账行(未触发过分键)
    assert _tracked_sig(session) == []


# 04:39 实锤反向形态:容器(守卫 expected 侧)8 件缺镜流,tracked 9 件
# 多镜流1(账屏结构性不同源,接管场景)
_SCREEN_8_EXPECTED = [
    ('花火', 1), ('丹恒·腾荒', 1), ('丹恒·腾荒', 1), ('艾丝妲', 1),
    ('椒丘', 1), ('黄泉', 1), ('大丽花', 1), ('丹恒·腾荒', 2),
]
_TRACKED_9_STALE = [
    ('花火', 1), ('丹恒·腾荒', 1), ('丹恒·腾荒', 1), ('艾丝妲', 1),
    ('椒丘', 1), ('镜流', 1), ('大丽花', 1), ('丹恒·腾荒', 2), ('黄泉', 1),
]


def test_resume_anchor_rebuilds_reversed_divergence_and_guard_passes(
        monkeypatch):
    """接管待办反向分叉形态(04:39 实锤):有账也两账再锚定,守卫不炸。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bs = board_state_of(session)
    bs.write_logic(bs.bench,
                   bench_view_of_slots(_bench_chars(_SCREEN_8_EXPECTED)),
                   produced_by='test', sig=_SIG)
    exec_state_of(session).tracked_bench_chars = bench_from_compact(
        _bench_chars(_TRACKED_9_STALE))
    exec_state_of(session).cw_resume_seed_anchor = True   # 接管标记在场
    # 屏幕真值 = 8 件(镜流已不在场;读取面含试用卡疑识别的账面陈旧件)
    reader, calls = _fake_reader(_bench_chars(_SCREEN_8_EXPECTED))
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'rebuilt'
    assert len(calls) == 1
    assert _tracked_sig(session) == _SCREEN_8_EXPECTED
    assert ([(b.char_id, b.star) for b in bench_slots_of(bs) if b is not None]
            == _SCREEN_8_EXPECTED)
    assert exec_state_of(session).cw_resume_seed_anchor is False   # 成功消费
    # 回归锁本形:真实种子守卫通过(双账同源后不抛)
    guard_expected_vs_tracked(bs, session, stage='seed')


def test_resume_anchor_read_failure_keeps_pending_for_retry(monkeypatch):
    """接管待办 + 读链失读:两账零写,待办不消费(下 visit 重试)。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bs = board_state_of(session)
    bs.write_logic(bs.bench,
                   bench_view_of_slots(_bench_chars(_SCREEN_8_EXPECTED)),
                   produced_by='test', sig=_SIG)
    exec_state_of(session).tracked_bench_chars = bench_from_compact(
        _bench_chars(_TRACKED_9_STALE))
    exec_state_of(session).cw_resume_seed_anchor = True
    reader, calls = _fake_reader(None)   # 失读
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'read_failed'
    assert exec_state_of(session).cw_resume_seed_anchor is True   # 不消费
    assert _tracked_sig(session) == _TRACKED_9_STALE   # 零写
    assert ledger.tracked_seed_rebuild_done is True   # 同 visit 阀门照关


def test_non_resume_divergent_still_asserts_is_unaffected(monkeypatch):
    """红线回归:同款反向分歧但无接管标记 → 照旧 tracked_present+守卫红。"""
    _spy_defects(monkeypatch)
    session = StrategySession()
    bs = board_state_of(session)
    bs.write_logic(bs.bench,
                   bench_view_of_slots(_bench_chars(_SCREEN_8_EXPECTED)),
                   produced_by='test', sig=_SIG)
    exec_state_of(session).tracked_bench_chars = bench_from_compact(
        _bench_chars(_TRACKED_9_STALE))
    reader, calls = _fake_reader(_bench_chars(_SCREEN_8_EXPECTED))
    ledger = ShopVisitLedger()

    outcome = rebuild_tracked_at_seed_if_vacant(
        session, object(), ledger, read_bench_fn=reader)

    assert outcome == 'tracked_present'   # 红线:非接管有账不重建
    assert calls == []
    assert exec_state_of(session).cw_resume_seed_anchor is False
    with pytest.raises(AssertionError, match='expected='):
        guard_expected_vs_tracked(bs, session, stage='seed')
