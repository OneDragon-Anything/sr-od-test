"""观察冲突守卫/board computed 行为测试(观察冲突审计「伴随」项,2026-08-16)。

覆盖:board_from_tracked(计算为准的切换判据)、cw_reconcile.reconcile_tracking(双空读守卫/
star 回退留证)、cw_horizon(DP 冒烟)。obs_conflict 走 best-effort 不抛,monkeypatch no-op
防测试落盘(AGENTS.local 钩子约定)。
"""
import pytest

from sr_od.application.currency_war.cw_observation import board_from_tracked
from sr_od.application.currency_war.cw_reconcile import reconcile_tracking
from sr_od.application.currency_war.cw_state import BenchChar


@pytest.fixture(autouse=True)
def _no_conflict_io(monkeypatch):
    """obs_conflict 落盘 no-op(测试不写 .debug)。

    ⚠️ 打桩打在 cw_observe.obs_conflict **源头**(非 cw_reconcile._conflict 封装)——
    M41 实机教训(2026-08-16):mock 掉封装则封装签名不被执行,#13 star 回退传 char=
    的 TypeError 测试全绿照样漏网,实机 error-loop 卡死 30min。封装必须真实跑。
    (封装函数内延迟 import obs_conflict → 源头 patch 对其生效。)
    """
    import sr_od.application.currency_war.cw_observe as obs_mod
    monkeypatch.setattr(obs_mod, 'obs_conflict', lambda *a, **kw: None)


class _Sess:
    def __init__(self, bench=None, deployed=None):
        self.tracked_bench_chars = bench or []
        self.tracked_deployed = deployed or []


def test_board_from_tracked_full_known():
    """全已知身份 → 全集计数(每人贡献全部阵营)。"""
    # 瓦尔特: 列车同行+星间旅人;姬子·启行: 列车同行(以注册表为准,断言用注册表值动态算)
    from sr_od.application.currency_war.cw_chars import get_char
    chars = [BenchChar(slot=1, char_id='瓦尔特'), BenchChar(slot=2, char_id='姬子·启行')]
    board = board_from_tracked(chars)
    assert board is not None
    for cid in ('瓦尔特', '姬子·启行'):
        for f in get_char(cid).factions:
            assert board.get(f, 0) >= 1


def test_board_from_tracked_unknown_rejects():
    """含未知身份('?' / 空 / 注册表无) → None(混合态不切,OCR 兜底)。"""
    assert board_from_tracked([]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='?')]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='')]) is None
    assert board_from_tracked([BenchChar(slot=1, char_id='不存在角色')]) is None


def test_board_from_tracked_factionless_known_skips():
    """无阵营已知角色(白厄「救世主」)不 bail:复制效果不计人数(官方 trait 3005)
    → 跳过零贡献即精确;独立羁绊行计入(与左面板显示同口径,防对拍留证噪声)。
    2026-08-17 修:旧版 not ch.factions 即 None,白厄上场整链误退 OCR。
    """
    chars = [BenchChar(slot=1, char_id='白厄'), BenchChar(slot=2, char_id='姬子·启行')]
    board = board_from_tracked(chars)
    assert board is not None, '白厄上场不应退 OCR(身份已知,贡献可精确计算)'
    assert board.get('救世主') == 1, '独立羁绊「救世主」应计入(面板同口径)'
    assert board.get('列车同行') == 1, '姬子·启行的阵营正常计数'


def test_board_from_tracked_flows_only_char_counts():
    """factions 空但 flows 非空(布洛妮娅 燃血)→ 正常贡献 flows 计数,不 bail。
    旧版只查 ch.factions → 布洛妮娅上场误退 OCR(同白厄 bug 的第二受害者)。"""
    board = board_from_tracked([BenchChar(slot=1, char_id='布洛妮娅')])
    assert board is not None
    assert board.get('燃血') == 1
    assert board.get('大守护者') == 1


def test_streak_dual_source_conflict_guard(test_context, monkeypatch):
    """streak 双源留证(审计 #8 P2,2026-08-17):read_game_state 内联判定 —— 结算带符号
    与备战 magnitude 不等(且结算≠0)→ obs_conflict 留证;一致 → 无噪声。
    直接跑 read_game_state 不可行(需 OCR 全屏栈),此处验判定的两端行为:
    复制内联条件(streak 逻辑为纯比较,无隐藏状态)。"""
    import sr_od.application.currency_war.cw_observe as obs_mod
    calls: list[tuple] = []
    monkeypatch.setattr(obs_mod, 'obs_conflict',
                        lambda field, old, new, *a, **kw: calls.append((field, old, new)))

    def _check(last_streak: int, prep: int | None) -> None:
        # = read_game_state 内联判定(cw_observation streak 段,保持同条件复制)
        if prep is not None and last_streak != 0 and abs(last_streak) != prep:
            obs_mod.obs_conflict('streak', last_streak, prep, None,
                                 verdict='留证-双源不等(结算带符号 vs 备战magnitude,一方误读)',
                                 source='settlement_vs_prep')

    _check(3, 3)          # 一致 → 不报
    _check(0, 5)          # 结算 0(重置边缘)→ 不报
    _check(3, None)       # 备战读不到 → 不报(单源)
    assert calls == []
    _check(3, 2)          # 不等 → 报
    assert calls == [('streak', 3, 2)]


def test_reconcile_double_empty_guard_keeps_old():
    """双空读 + 前值非空 → 保旧(M14 过渡帧守卫),不写回。"""
    old = [BenchChar(slot=1, char_id='瓦尔特')]
    sess = _Sess(bench=old, deployed=[])
    assert reconcile_tracking(sess, [], [], None, source='t') is False
    assert sess.tracked_bench_chars == old


def test_reconcile_double_empty_with_empty_prev_ok():
    """双空读但前值也空 → 正常写回(空板开局,非读失败)。"""
    sess = _Sess()
    assert reconcile_tracking(sess, [], [], None, source='t') is True
    assert sess.tracked_bench_chars == []


def test_reconcile_none_side_kept():
    """bench=None(读失败侧)不写,deployed 侧正常写。"""
    sess = _Sess(deployed=[BenchChar(slot=1, char_id='瓦尔特')])
    new_dep = [BenchChar(slot=1, char_id='姬子·启行')]
    assert reconcile_tracking(sess, None, new_dep, None, source='t') is True
    assert sess.tracked_bench_chars == []
    assert sess.tracked_deployed == new_dep


def test_reconcile_star_rollback_no_crash():
    """M41 实机回归(2026-08-16):同名 star 回退(缇宝 2★→1★)走留证分支
    **不得抛异常**——旧版 _conflict 封装无 **ctx,char= 触发 TypeError → PrepDirector
    error-loop 卡死 30min(P3-4 实锤)。留证后采新写回(tracking 更新)。"""
    sess = _Sess(bench=[BenchChar(slot=1, char_id='缇宝', star=2)])
    new = [BenchChar(slot=1, char_id='缇宝', star=1)]
    assert reconcile_tracking(sess, new, [], None, source='t') is True
    assert sess.tracked_bench_chars[0].star == 1


def test_horizon_dp_smoke():
    """cw_horizon DP 冒烟:解不为空、终局边界有值、posture 查询可回退。"""
    from sr_od.application.currency_war import cw_horizon as hz
    sol = hz.HorizonSolution()
    # 不全量 solve(秒级但测试要快):只验 posture 回退 + interest 规则
    p = sol.posture(0, 33, 5, 88, 1)
    assert p.save is True and p.tag == 'fallback'
    assert hz.interest(49) == 4
    assert hz.interest(50) == 5
    assert hz.interest(110) == 5   # 封顶
