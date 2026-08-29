"""观察冲突守卫/board computed 行为测试(观察冲突审计「伴随」项,2026-08-16)。

覆盖:board_from_tracked(计算为准的切换判据)、cw_reconcile.reconcile_tracking(双空读守卫/
star 回退留证)、DP 冒烟。obs_conflict 走 best-effort 不抛,monkeypatch no-op
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
    from sr_od.application.currency_war.data.cw_chars import get_char
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
    # ADR-0392:tracked_deployed 槽位表——按占用序对拍(紧缩视图)
    assert [d for d in sess.tracked_deployed if d is not None] == new_dep


def test_reconcile_star_rollback_no_crash():
    """M41 实机回归(2026-08-16):同名 star 回退(缇宝 2★→1★)走留证分支
    **不得抛异常**——旧版 _conflict 封装无 **ctx,char= 触发 TypeError → PrepDirector
    error-loop 卡死 30min(P3-4 实锤)。
    2026-08-18 防抖升级(274 存证离线复现:36/40 同图重读 2★,live 读 1★ =
    3合1 合成动画窗):首次回退 star **保旧**(动画窗读数不毒化 tracking),
    连续第二次仍回退才采新确认。"""
    sess = _Sess(bench=[BenchChar(slot=1, char_id='缇宝', star=2)])
    # 首次:防抖保旧(不写回 1★)
    assert reconcile_tracking(
        sess, [BenchChar(slot=1, char_id='缇宝', star=1)], [], None, source='t') is True
    assert sess.tracked_bench_chars[0].star == 2, '首次回退保旧(疑合成动画窗)'
    # 连续第二次(独立新读对象——防抖会原地改 star,复用同对象会假自愈):确认真回退 → 采新
    assert reconcile_tracking(
        sess, [BenchChar(slot=1, char_id='缇宝', star=1)], [], None, source='t') is True
    assert sess.tracked_bench_chars[0].star == 1, '连续 2 次回退确认采新'


def test_reconcile_star_regression_pending_self_heals():
    """防抖自愈(2026-08-18):首帧回退(动画窗)→ 下帧读回正常 → pending 清零、
    tracking star 保持旧值(2★)未被动画窗 1★ 毒化。"""
    sess = _Sess(bench=[BenchChar(slot=1, char_id='万敌', star=2)])
    # 首帧:动画窗读 1★ → 保旧
    reconcile_tracking(sess, [BenchChar(slot=1, char_id='万敌', star=1)], [], None, source='t')
    assert sess.tracked_bench_chars[0].star == 2
    # 下帧:动画结束读回 2★(=旧值,非回退)→ 自愈,防抖挂起清零
    reconcile_tracking(sess, [BenchChar(slot=1, char_id='万敌', star=2)], [], None, source='t')
    assert sess.tracked_bench_chars[0].star == 2
    assert not getattr(sess, 'star_pending_regression', {}).get('万敌'), '读回恢复清防抖'


def test_plane_table_smoke():
    """cw_plane_table 冒烟(批 3:标定表模块随 DP 退役平移;
    息闭式边界锁逐位保留)。"""
    from sr_od.application.currency_war.cw_plane_table import interest
    assert interest(49) == 4
    assert interest(50) == 5

# ===== 等级三源解析 _resolve_level(2026-08-18 治本:live 乒乓根因) =====
from sr_od.application.currency_war.cw_observation import _resolve_level  # noqa: E402


def _kinds(events) -> list[str]:
    return [e[0] for e in events]


def test_resolve_level_pingpong_root_live_regression():
    """live 乒乓场景回归(2026-08-18 10:47-10:48 实锤):OCR 失读 + 启发式兜底 6
    被写进 last_level_obs 毒化;XP 分母反推 5(真值,XP「0/20」+ 部署 5/5 双证)。
    旧链:XP 采新 5 → 单调守卫用毒化 6 打回 → 每帧 6↔5 乒乓。
    新链:XP 主权豁免单调守卫,向下校正到 5 并留证。"""
    level, events, auth = _resolve_level(None, 6, 5, 6)
    assert level == 5
    assert _kinds(events) == ['xp_down']
    assert auth is True   # XP 可读 → 真实观测,写回 last_level_obs(链路自愈)


def test_resolve_level_heuristic_not_authoritative():
    """毒化防线:OCR 与 XP 双失读 → 纯启发式值不作真实观测(authoritative=False,
    调用方不写回 last_level_obs —— 毒源堵住)。解析值本身照给(决策层用)。"""
    level, events, auth = _resolve_level(None, 6, None, 4)
    assert level == 6 and auth is False   # 6 > 4+2? 不(6=4+2)→ 不触发跳变守卫
    assert events == []


def test_resolve_level_monotonic_guard_preserved():
    """旧守卫保留:XP 未确认的下降(纯 OCR 误读)仍保旧(r1 lv4→r2 lv5→r3 lv4 倒退防)。"""
    level, events, auth = _resolve_level(4, 5, None, 6)
    assert level == 6
    assert _kinds(events) == ['mono']
    assert auth is True


def test_resolve_level_jump_guard_preserved():
    """旧守卫保留:单源 OCR 大跳(疑似 XP 数字混入,如「升到 lv10」需 360 金)拒。"""
    level, events, _ = _resolve_level(10, 5, None, 4)
    assert level == 4
    assert _kinds(events) == ['jump']


def test_resolve_level_jump_confirmed_by_xp():
    """M38 语义保留:XP 分母独立确认的真跳变(连点一波 4→8)放行 + 留证。"""
    level, events, _ = _resolve_level(8, 5, 8, 4)
    assert level == 8
    assert _kinds(events) == ['jump_ok']


def test_resolve_level_xp_override_real_disagreement_logged():
    """OCR 可读 6 与 XP 反推 5 真分歧 → 覆盖 + 留证(ADR-0129)。"""
    level, events, _ = _resolve_level(6, 6, 5, 0)
    assert level == 5
    assert _kinds(events) == ['xp_override']


def test_resolve_level_xp_over_fallback_silent():
    """OCR 失读时「兜底让位 XP」= 设计常态,不逐帧记 [cw!](live 10:47-10:48
    每帧 2 冲突的遥测噪声源);新局 last=0 无守卫交互。"""
    level, events, auth = _resolve_level(None, 6, 5, 0)
    assert level == 5 and events == [] and auth is True


def test_resolve_level_agree_no_events():
    """双源一致 → 零事件(健康帧不产遥测噪声)。"""
    level, events, auth = _resolve_level(7, 5, 7, 6)
    assert level == 7 and events == [] and auth is True
