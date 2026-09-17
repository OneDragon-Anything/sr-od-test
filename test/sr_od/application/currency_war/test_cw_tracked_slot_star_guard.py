"""观察层对账仲裁批:star 回退采新(终态契约 §A)+ tracked 槽号守卫。

锁 1 语义变更(用户裁定 2026-09-17 + 2026-09-16):star 回退防抖/帧态门
(ADR-0420)/银狼升费豁免退役——回退即采新,失败可见;留证停机钩子与
star_regression 采样登记已随「星回退处置归观察对账」裁定整删(2026-09-16),
本文件只锁采新行为本身;实机失准走识别优化批。

锁 2(tracked 槽号守卫)不受本契约影响,原样保留:
- 实机缺陷台账 bench_slot_unhealthy 四局(slots=[2,2,3]/[…9,9],
  reseed 健康门 L0/L1 显影);摘除腿按下标置 None(pad 态契约不破坏)+
  写点健康显影 + reconcile 写回门过共享健康谓词(bench_slots_healthy
  单一源)。
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
    game_state_of,
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
            (game_state_of(session).tracked_books.bench or [])
            if b is not None]


def _bc(slot: int, name: str, star: int) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== 锁 1:star 回退采新(终态契约 §A:防抖/帧态门/银狼豁免/停机钩子均退役)=====


def test_star_downgrade_adopts_new_immediately(monkeypatch):
    """回退即采新(防抖退役):2★ 读成 1★ → tracked 直采 1★(失败可见,
    合成动画窗误读直进板面账)。"""
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 2)])
    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1)]


def test_star_downgrade_silver_wolf_no_longer_exempt(monkeypatch):
    """银狼升费豁免退役:银狼 2★→1★ 同样采新。"""
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '银狼', 2)])
    reconcile_tracking(session, [_bc(1, '银狼', 1)], [], source='test')
    assert _tracked_sig(session) == [('银狼', 1)]


def test_star_upgrade_still_silent_and_multi_copy_adopted(monkeypatch):
    """升星/新角色正常采新;同名多副本各按现读采新(旧锚定抬回退役)。"""
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(4, '不死途', 1), _bc(6, '不死途', 2), _bc(7, '不死途', 3)])
    # 3★@槽7 读成 1★(读抖):直采,无锚定抬回
    reconcile_tracking(session, [_bc(4, '不死途', 1), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 1)]
    # 升星对照:1★→2★ 正常写回
    reconcile_tracking(session, [_bc(4, '不死途', 2), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 2), ('不死途', 2),
                                     ('不死途', 1)]


# ===== 锁 2:tracked 槽号守卫(写点置 None + 显影 + 仲裁门)=====


def test_removal_keeps_layout_sell_and_move_legs():
    """摘除腿按下标置 None 两腿(并一):sell 腿 pad 态契约不破坏,存件
    不移位、信息位不动;DeployMove 腿同治本,bench 置 None 不移位 +
    deployed 正常落槽。"""
    # sell 腿:卖槽2(下标 1)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1), _bc(3, '椒丘', 1)])
    ex = _mk_executor(session)

    ex._track_remove_bench(1)

    tracked = game_state_of(session).tracked_books.bench
    assert len(tracked) == BENCH_CAPACITY   # pad 态保持
    assert tracked[1] is None
    assert tracked[0] is not None and (tracked[0].char_id, tracked[0].slot) \
        == ('花火', 1)
    assert tracked[2] is not None and (tracked[2].char_id, tracked[2].slot) \
        == ('椒丘', 3)   # 不移位:槽3 件仍在槽3(旧紧凑重排会把它挪到槽2)
    # move 腿:花火 bench槽1 → 前排槽1
    session_m = StrategySession()
    game_state_of(session_m).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1)])
    game_state_of(session_m).tracked_books.deployed = []
    ex_m = _mk_executor(session_m)

    ex_m._track_move_deployed(0, 'front', 1)

    tracked_m = game_state_of(session_m).tracked_books.bench
    assert tracked_m[0] is None and tracked_m[1].char_id == '刃' \
        and tracked_m[1].slot == 2   # 刃 不移位
    deployed = [b for b in game_state_of(session_m).tracked_books.deployed
                if b is not None]
    assert [(b.char_id, b.position_pref) for b in deployed] == [('花火', 'front')]


def test_tracked_write_guard_defect_and_healthy_silence(monkeypatch):
    """写点健康显影两帧(并一):既有重复槽号 → bench_slot_unhealthy
    台账行(reader_source=tracked_write_guard),摘除腿照常执行(只减
    不增);健康账摘除零显影(常态无噪声)。"""
    # 反帧:既有污染形态(信息位重复;模拟旧紧凑重排+买入追加累积产物)
    rows = _spy_defects(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = [
        _bc(1, '花火', 1), _bc(2, '刃', 1), _bc(2, '椒丘', 1)]
    ex = _mk_executor(session)

    ex._track_remove_bench(0)

    assert len(rows) == 1
    surface, kind, observed, reader = rows[0]
    assert (surface, kind) == ('bench', defects.DEFECT_KIND_BENCH_SLOT_UNHEALTHY)
    assert observed == "slots=['1', '2', '2']"
    assert reader == 'tracked_write_guard'
    tracked = game_state_of(session).tracked_books.bench
    assert tracked[0] is None   # 摘除未被拒(拒绝会让已卖件滞留 tracked)
    # 正帧:健康账摘除
    rows_h = _spy_defects(monkeypatch)
    session_h = StrategySession()
    game_state_of(session_h).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1), _bc(2, '刃', 1)])
    ex_h = _mk_executor(session_h)

    ex_h._track_remove_bench(1)
    assert rows_h == []


def test_reconcile_bench_gate_rejects_duplicate_slots(monkeypatch):
    """对账仲裁门(共享谓词):读链槽号重复 → bench 侧拒绝写回保旧。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '花火', 1)])

    read = [_bc(2, '甲', 1), _bc(2, '乙', 1)]   # 重复槽号(无守卫读链)
    assert not bench_slots_healthy(bench_occupied_slot_nos(read))
    reconcile_tracking(session, read, [], source='test')

    assert _tracked_sig(session) == [('花火', 1)]   # 脏读数未固化
    bench_rows = [r for r in rows if r[0] == 'bench']
    assert bench_rows and 'slots=' in bench_rows[0][2]
