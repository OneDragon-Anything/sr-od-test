"""观察层对账仲裁批:星级锚定 + tracked 槽号唯一性守卫。

两锁同源两份实机证据(语义描述;深检结论见 deep_review INDEX 在册,
局档案键 = 局 id,缺陷行键 = 台账 kind):
- 实机深检(局 run_20260915_054718):bench 同名 1/2/3★ 三副本并存时
  星读在帧间翻转(不死途 3★→1★「连续 2 次,真回退」×3),旧 N=2 确认
  门恰被 2 帧抖动 episode 洗锚 → 全程抖动、3★ 合成线报废;
- 实机缺陷台账 bench_slot_unhealthy 四局(slots=[2,2,3]/[…9,9],
  reseed 健康门 L0/L1 显影)。
1. 星级锚定:旧判读按 (名,星) 对逐副本比较,真实 2★/1★ 副本被连环
   误抬。修法 = 名级锚比较 + 保旧按槽位锚定 + 降级采新确认门提到 N=3
   (推导见 cw_reconcile.STAR_DOWNGRADE_CONFIRM_FRAMES 注)。
2. 槽号守卫:tracked 摘除腿(sell/move)旧实现按信息位过滤产出紧凑
   列表,信息位/下标脱节经后续买入 bench_place 追加累积成重复槽号
   (台账 slots=[1,3,4,5,6,7,8,9,9] 等),reseed 健康门 L0 显影后
   fail-stop。修法 = 摘除按下标置 None(pad 态契约不破坏)+ 写点健康
   显影(tracked_write_guard 分键,先于 reseed 门)+ reconcile 写回门
   过共享健康谓词(bench_slots_healthy 单一源)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import sr_od.application.currency_war.kernel.cw_observe as cw_observe
from sr_od.application.currency_war import prep_actions as pa
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BENCH_CAPACITY,
    BenchChar,
    bench_from_compact,
    bench_occupied_slot_nos,
    bench_slots_healthy,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    board_state_of,
)
from sr_od.application.currency_war.kernel.cw_reconcile import (
    reconcile_tracking,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.telemetry import defects


def _spy_conflicts(monkeypatch) -> list[tuple]:
    """桩掉 obs_conflict(测试零真实副作用)+ 留行供仲裁断言。"""
    rows: list[tuple] = []

    def _rec(field, old, new, screen=None, *, verdict='', **ctx):
        rows.append((field, old, new, verdict))

    monkeypatch.setattr(cw_observe, 'obs_conflict', _rec)
    return rows


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入 + 留行供显影断言(同 seed_tracked_rebuild 模式)。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, observed, kwargs.get('reader_source')))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _mk_executor(session):
    """执行器替身构造(同 unified_action_2a harness;ctx 挂真 session)。"""
    ex = pa.PrepActionExecutor(
        SimpleNamespace(screenshot=lambda: np.zeros((4, 4), dtype='uint8')),
        SimpleNamespace(controller=SimpleNamespace(), cw_match=None,
                        run_context=None,
                        screen_loader=SimpleNamespace(
                            get_screen=lambda name: None)))
    ex._ctx = SimpleNamespace(
        controller=SimpleNamespace(),
        cw_match=SimpleNamespace(session=session),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        run_context=None)
    return ex


def _tracked_sig(session) -> list:
    return [(b.char_id, b.star) for b in
            (board_state_of(session).tracked_books.bench or [])
            if b is not None]


def _bc(slot: int, name: str, star: int) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== 锁 1:星级锚定(reconcile_tracking)=====


def test_star_flicker_hold_then_confirm_and_oscillation_never_confirms(
        monkeypatch):
    """N=3 确认门两格(并一):连续 2 帧低读保旧不洗锚,第 3 帧才采新
    (超额证据;抖动 episode 实测长度 = 2 帧,必须全程保旧);振荡断路
    ——低读间夹恢复帧清计数 → 抖动形态零采新(本局病灶形态)。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 2)])

    for _ in range(2):   # 抖动 episode 实测长度 = 2 帧:必须全程保旧
        read = [_bc(1, '不死途', 1)]
        reconcile_tracking(session, read, [], source='test')
        assert _tracked_sig(session) == [('不死途', 2)]   # 锚定星不被洗

    read = [_bc(1, '不死途', 1)]   # 第 3 帧连续低读 = 真回退 → 采新
    reconcile_tracking(session, read, [], source='test')
    assert _tracked_sig(session) == [('不死途', 1)]
    assert session.star_pending_regression == {}   # 确认后计数收口
    # 振荡断路:恢复帧夹层清计数,零采新
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 2)])
    for star in (1, 1, 2, 1, 1):   # 2 帧抖动 episode ×2,中间恢复
        read = [_bc(1, '不死途', star)]
        reconcile_tracking(session, read, [], source='test')
        assert _tracked_sig(session) == [('不死途', 2)]
    assert session.star_pending_regression.get('不死途') == 2   # 计数重起,未达 N


def test_star_slot_anchored_hold_spares_true_low_copy(monkeypatch):
    """同名多星三副本:保旧只抬锚槽读低副本,真实 1★/2★ 副本不被误抬。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(4, '不死途', 1), _bc(6, '不死途', 2), _bc(7, '不死途', 3)])

    # 3★@槽7 读成 1★(星读抖动),1★@槽4/2★@槽6 为真实读
    read = [_bc(4, '不死途', 1), _bc(6, '不死途', 2), _bc(7, '不死途', 1)]
    reconcile_tracking(session, read, [], source='test')

    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 3)]   # 三副本原样(锚 3★ 未洗)
    assert [(b.star, b.slot) for b in read] == [(1, 4), (2, 6), (3, 7)]
    # 读链槽7 抬回 3★,槽4 真实 1★ 不动(旧「首中低读副本」会误抬槽4)


def test_star_anchor_missing_copy_gets_reinjected(monkeypatch):
    """锚槽副本整缺(SIFT 漏检):注入锚副本防锚静默洗掉。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(7, '不死途', 3), _bc(4, '不死途', 1)])

    # 槽7 锚副本漏检,读链只剩真实 1★;名最高读星 1 < 锚 3
    read = [_bc(4, '不死途', 1)]
    reconcile_tracking(session, read, [], source='test')

    sig = sorted(_tracked_sig(session))
    assert sig == [('不死途', 1), ('不死途', 3)]   # 锚 3★ 跨帧存续
    injected = [b for b in board_state_of(session).tracked_books.bench
                if b is not None and b.slot == 7]
    assert injected and injected[0].star == 3


def test_star_upgrade_read_raises_anchor_silently(monkeypatch):
    """升星读(merge 后)高于锚 = 常态采信,不进回退路径。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 2)])

    reconcile_tracking(session, [_bc(1, '不死途', 3)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 3)]
    assert [r for r in rows if r[0] == 'star'] == []   # 零 star 冲突行


# ===== 锁 2:tracked 槽号守卫(写点置 None + 显影 + 仲裁门)=====


def test_removal_keeps_layout_sell_and_move_legs():
    """摘除腿按下标置 None 两腿(并一):sell 腿 pad 态契约不破坏,存件
    不移位、信息位不动;DeployMove 腿同治本,bench 置 None 不移位 +
    deployed 正常落槽。"""
    # sell 腿:卖槽2(下标 1)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1), _bc(3, '椒丘', 1)])
    ex = _mk_executor(session)

    ex._track_remove_bench(1)

    tracked = board_state_of(session).tracked_books.bench
    assert len(tracked) == BENCH_CAPACITY   # pad 态保持
    assert tracked[1] is None
    assert tracked[0] is not None and (tracked[0].char_id, tracked[0].slot) \
        == ('花火', 1)
    assert tracked[2] is not None and (tracked[2].char_id, tracked[2].slot) \
        == ('椒丘', 3)   # 不移位:槽3 件仍在槽3(旧紧凑重排会把它挪到槽2)
    # move 腿:花火 bench槽1 → 前排槽1
    session_m = StrategySession()
    board_state_of(session_m).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1)])
    board_state_of(session_m).tracked_books.deployed = []
    ex_m = _mk_executor(session_m)

    ex_m._track_move_deployed(0, 'front', 1)

    tracked_m = board_state_of(session_m).tracked_books.bench
    assert tracked_m[0] is None and tracked_m[1].char_id == '刃' \
        and tracked_m[1].slot == 2   # 刃 不移位
    deployed = [b for b in board_state_of(session_m).tracked_books.deployed
                if b is not None]
    assert [(b.char_id, b.position_pref) for b in deployed] == [('花火', 'front')]


def test_tracked_write_guard_defect_and_healthy_silence(monkeypatch):
    """写点健康显影两帧(并一):既有重复槽号 → bench_slot_unhealthy
    台账行(reader_source=tracked_write_guard),摘除腿照常执行(只减
    不增);健康账摘除零显影(常态无噪声)。"""
    # 反帧:既有污染形态(信息位重复;模拟旧紧凑重排+买入追加累积产物)
    rows = _spy_defects(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = [
        _bc(1, '花火', 1), _bc(2, '刃', 1), _bc(2, '椒丘', 1)]
    ex = _mk_executor(session)

    ex._track_remove_bench(0)

    assert len(rows) == 1
    surface, kind, observed, reader = rows[0]
    assert (surface, kind) == ('bench', defects.DEFECT_KIND_BENCH_SLOT_UNHEALTHY)
    assert observed == "slots=['1', '2', '2']"
    assert reader == 'tracked_write_guard'
    tracked = board_state_of(session).tracked_books.bench
    assert tracked[0] is None   # 摘除未被拒(拒绝会让已卖件滞留 tracked)
    # 正帧:健康账摘除
    rows_h = _spy_defects(monkeypatch)
    session_h = StrategySession()
    board_state_of(session_h).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1)])
    ex_h = _mk_executor(session_h)

    ex_h._track_remove_bench(1)
    assert rows_h == []


def test_reconcile_bench_gate_rejects_duplicate_slots(monkeypatch):
    """对账仲裁门(共享谓词):读链槽号重复 → bench 侧拒绝写回保旧。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    board_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1)])

    read = [_bc(2, '甲', 1), _bc(2, '乙', 1)]   # 重复槽号(无守卫读链)
    assert not bench_slots_healthy(bench_occupied_slot_nos(read))
    reconcile_tracking(session, read, [], source='test')

    assert _tracked_sig(session) == [('花火', 1)]   # 脏读数未固化
    bench_rows = [r for r in rows if r[0] == 'bench']
    assert bench_rows and 'slots=' in bench_rows[0][2]
