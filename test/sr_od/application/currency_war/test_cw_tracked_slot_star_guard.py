"""观察层对账仲裁批:星级抖动门(槽位锚定+两帧一致)+ tracked 槽号守卫。

锁 1 语义变更(T-35 识别优化批,取代终态契约 §A「回退即采新」临时语义):
run_20260915_054718 §5/§8 候选2 实锤「回退即采新」让同名多星单元的单帧
星读抖动直进 tracked 主账(3★ 合成线整局被污染,episode ×3 全部「连续
2 帧」形态恰好吃掉旧 N=2 确认门)。现行口径 = 槽位锚定 + 两帧一致才采新:
单帧差保旧写账 + 抖动台账行(surface='star');升/降同门、银狼升费形态无
豁免(门按锚判定与名无关);合成特效窗内星读不可信(冻结,不计两帧);
锚上身份变换(换人/落新单元)星级随身份直采。

锁 2(tracked 槽号守卫)不受本批影响,原样保留:
- 实机缺陷台账 bench_slot_unhealthy 四局(slots=[2,2,3]/[…9,9],
  reseed 健康门 L0/L1 显影);摘除腿按下标置 None(pad 态契约不破坏)+
  写点健康显影 + reconcile 写回门过共享健康谓词(bench_slots_healthy
  单一源)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import sr_od.application.currency_war.kernel.cw_observe as cw_observe
import sr_od.application.currency_war.kernel.cw_reconcile as cw_reconcile
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


def _deployed_sig(session) -> list:
    return [(b.char_id, b.position_pref, b.star) for b in
            (game_state_of(session).tracked_books.deployed or [])
            if b is not None]


def _bc(slot: int, name: str, star: int) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


# ===== 锁 1:星级抖动门(槽位锚定 + 两帧一致才采新)=====


def test_star_single_frame_jitter_held(monkeypatch):
    """单帧抖动不写账:3★@槽1 单帧读 1★ → tracked 保 3★ + surface='star'
    抖动台账行;下帧读回与账一致 → 候选作废,无新增台账行(常态无噪声)。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 3)])

    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], source='test')

    assert _tracked_sig(session) == [('不死途', 3)]   # 单帧抖动保旧
    star_rows = [r for r in rows if r[0] == 'star']
    assert len(star_rows) == 1 and '保旧' in star_rows[0][3]

    reconcile_tracking(session, [_bc(1, '不死途', 3)], [], source='test')

    assert _tracked_sig(session) == [('不死途', 3)]
    assert len([r for r in rows if r[0] == 'star']) == 1   # 读账一致零噪声


def test_star_change_needs_two_frame_consistency(monkeypatch):
    """两帧一致才采新(升/降同门):3★→1★ 连续两帧才落账;1★→2★ 升星
    读数同样须两帧(合成后实读延迟一帧,防单帧抖动毒化 3★ 合成判断)。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 3)])

    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 首帧差:保旧
    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 次帧同值:采新

    reconcile_tracking(session, [_bc(1, '不死途', 2)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 升星首帧:保旧
    reconcile_tracking(session, [_bc(1, '不死途', 2)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 2)]   # 升星次帧:采新


def test_same_name_multi_star_slot_anchored_no_cross_star(monkeypatch):
    """同名多星并存槽位锚定:单槽抖动不串邻槽;真换位(整表重排)两帧
    按新槽位落账且全程不串星;换人(锚上身份变)星级随身份直采不辖门。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(4, '不死途', 1), _bc(6, '不死途', 2), _bc(7, '不死途', 3)])
    # 帧1:槽7 单帧读 1★(抖动),槽4/6 照读 → 逐槽保旧,邻槽不串
    reconcile_tracking(session, [_bc(4, '不死途', 1), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 3)]
    # 帧2:槽7 同抖动复现(两帧一致采新 1★);槽4 升 2★ 单帧读保旧
    reconcile_tracking(session, [_bc(4, '不死途', 2), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 1)]
    # 换位:槽4↔槽7 星级互换(1★/3★ 两帧一致后落新槽位,槽6 不串)
    reconcile_tracking(session, [_bc(4, '不死途', 3), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 1)]   # 换位首帧:保旧
    reconcile_tracking(session, [_bc(4, '不死途', 3), _bc(6, '不死途', 2),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 3), ('不死途', 2),
                                     ('不死途', 1)]   # 次帧:新槽位落账
    # 换人:槽6 落新单元(异名)→ 直采,不受门前槽6 候选态影响
    reconcile_tracking(session, [_bc(4, '不死途', 3), _bc(6, '花火', 1),
                                 _bc(7, '不死途', 1)], [], source='test')
    assert _tracked_sig(session) == [('不死途', 3), ('花火', 1),
                                     ('不死途', 1)]


def test_star_gate_name_agnostic_silver_wolf(monkeypatch):
    """门按锚判定与名无关(银狼升费形态无豁免):单帧保旧,两帧采新。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '银狼', 2)])

    reconcile_tracking(session, [_bc(1, '银狼', 1)], [], source='test')
    assert _tracked_sig(session) == [('银狼', 2)]
    reconcile_tracking(session, [_bc(1, '银狼', 1)], [], source='test')
    assert _tracked_sig(session) == [('银狼', 1)]


def test_deployed_slot_anchor_two_frame(monkeypatch):
    """deployed 侧锚 = 槽位表下标→(排, 排内槽号)(ADR-0392):后排槽3
    单帧 3★→1★ 保旧,两帧一致采新。(种子直构 pad 态槽位表——
    deployed_from_compact 按首空槽落位,不保 slot 信息位。)"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _dep: list = [None] * 10
    _dep[6] = BenchChar(slot=3, char_id='不死途', star=3,
                        position_pref='back')   # 下标 6 = 后排槽 3
    game_state_of(session).tracked_books.deployed = _dep

    def _read_back3(star: int) -> list[BenchChar]:
        return [BenchChar(slot=3, char_id='不死途', star=star,
                          position_pref='back')]

    reconcile_tracking(session, [], _read_back3(1), source='test')
    assert _deployed_sig(session) == [('不死途', 'back', 3)]   # 首帧:保旧
    reconcile_tracking(session, [], _read_back3(1), source='test')
    assert _deployed_sig(session) == [('不死途', 'back', 1)]   # 次帧:采新


def test_merge_effect_window_freezes_confirmation(monkeypatch):
    """合成特效窗冻结(帧态维,与两帧时间维正交):窗内星差保旧且不登记
    候选(动画帧不计两帧)——窗后干净帧须再连续两帧才采新。"""
    _spy_conflicts(monkeypatch)
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: True)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = bench_from_compact(
        [_bc(1, '不死途', 3)])
    _scr = np.zeros((4, 4), dtype='uint8')   # 非 None 帧才进特效窗判别

    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], screen=_scr,
                       source='test')
    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], screen=_scr,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 窗内两帧不确认

    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: False)
    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], screen=_scr,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 干净帧1:候选登记
    reconcile_tracking(session, [_bc(1, '不死途', 1)], [], screen=_scr,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 干净帧2:采新


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
