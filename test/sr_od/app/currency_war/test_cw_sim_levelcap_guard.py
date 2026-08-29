"""sim 执行层 LevelUp 满级 cap 守卫锁。

实机满级时「购买经验」按钮禁用(点击无效不扣金);sim 执行层旧无守卫,
满级后 LevelUp 照扣 4 金/击(富金批实测 ≥5040 金/360 局白烧,见
w507_richsim_hunt 报告 N1)。守卫语义:level ≥ LEVEL_CAP 时 LevelUp
拒付——不扣金/不进 XP,账本记 LevelUpRejected 行(不占 LevelUp 类型,
flat4 台账锁判据 spend.levelup == 4×LevelUp 行数才不被拒付行破坏),
计数进 sim.level_cap_rejects。
"""
from __future__ import annotations


class _LevelUpSpamStub:
    """升级桩:每段恒发 3 个 LevelUp——未满级时合法执行,满级后逼出守卫。"""

    def update_target(self, st, sess, cfg) -> None:  # noqa: ANN001
        pass

    def decide_prep(self, st, sess, cfg):  # noqa: ANN001
        from sr_od.application.currency_war.kernel.cw_state import LevelUp
        return [LevelUp(cost=4) for _ in range(3)]


def test_sim_levelup_cap_guard_rejects_and_discloses() -> None:
    """满级后 LevelUp 拒付:金不扣、无 LevelUp 执行行、计数披露。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    rows = res.ledger
    assert rows, '账本为空:运行异常'

    # 守卫确实介入:有轮记录了拒付计数
    rejected_total = sum((r.get('sim') or {}).get('level_cap_rejects', 0)
                         for r in rows)
    assert rejected_total > 0, '满级桩未逼出守卫:level_cap_rejects 全 0'

    # 满级判定:某轮末 state.level 已达上限 → 该轮**之后**的轮不再有
    # LevelUp 执行行(拒付行 LevelUpRejected 不算执行)。
    cap_seen = False
    for r in rows:
        if cap_seen:
            st = r.get('state') or {}
            assert st.get('level', 0) >= 9, '满级后等级回退:状态链坏'
            lv_rows = [a for a in (r.get('actions') or [])
                       if a.get('__type__') == 'LevelUp']
            assert not lv_rows, (
                f"r{r.get('round_num')} 满级后仍有 LevelUp 执行行:"
                f'{len(lv_rows)}(cap 守卫回归)')
            assert (r.get('sim') or {}).get('spend', {}).get('levelup', 0) == 0, \
                f"r{r.get('round_num')} 满级后仍扣升级金(白烧回归)"
            rej_rows = [a for a in (r.get('actions') or [])
                        if a.get('__type__') == 'LevelUpRejected']
            assert rej_rows, (
                f"r{r.get('round_num')} 满级拒付未记 LevelUpRejected 账本行"
                '(台账断链)')
        cap_seen = cap_seen or (r.get('state') or {}).get('level', 0) >= 9


def test_sim_levelup_pre_cap_regression() -> None:
    """回归:未满级时 LevelUp 行为不变——照常执行、照常扣 4 金/击。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    pre_cap = [r for r in res.ledger
               if (r.get('state') or {}).get('level', 0) < 9
               and (r.get('sim') or {}).get('spend', {}).get('levelup', 0) > 0]
    assert pre_cap, '未满级轮无升级执行:回归(合法升级被误拦)'
    for r in pre_cap:
        acts = r.get('actions') or []
        n_lv = sum(1 for a in acts if a.get('__type__') == 'LevelUp')
        spent = (r.get('sim') or {}).get('spend', {}).get('levelup', 0)
        assert spent == 4 * n_lv, (
            f"r{r.get('round_num')} 未满级支出 {spent} ≠ 4×{n_lv}(flat4 回归)")


def test_sim_levelup_rejected_rows_keep_flat4_ledger_lock() -> None:
    """拒付行不破坏 flat4 台账锁(spend.levelup == 4×LevelUp 行数)。"""

    from sr_od.application.currency_war.sim.engine_p1 import simulate_p1

    from sr_od.application.currency_war.sim.checks.ledger import check_levelup_flat4_ledger_lock

    res = simulate_p1(1, pool='fallback', strategy=_LevelUpSpamStub())
    violations = check_levelup_flat4_ledger_lock(res.ledger)
    assert not violations, f'flat4 台账锁被拒付行破坏:{violations[:3]}'


def test_sim_batch_aggregate_discloses_level_cap_rejects() -> None:
    """批量报告聚合披露 level_cap_rejects(键存在且 ≥0)。"""

    from sr_od.application.currency_war.sim.runner import simulate_p1_batch

    rep = simulate_p1_batch(6, pool='fallback', seed_base=600,
                            ledger=False, checks=False)
    assert rep['level_cap_rejects'] >= 0


def test_sim_batch_cap_rejects_by_plane_consistent_with_total() -> None:
    """按 plane 分解披露:键值合法、与总量键和恒等、plane 单调可读。

    为什么按 plane:lv≥9 态在实机只见 P2/P3(实机 P1 等级上限 7),
    总量把 P1 等级虚高噪声与 P2/P3 语义分歧混桶,分解后才能为
    LEVEL_CAP 放开批提供干净读数。兼容判据:总量键保留不删,分解值
    求和必须等于总量——不等即聚合端分组与总量口径漂移。
    """

    from sr_od.application.currency_war.sim.runner import simulate_p1_batch

    rep = simulate_p1_batch(6, pool='fallback', seed_base=600,
                            ledger=False, checks=False)
    by_plane = rep['level_cap_rejects_by_plane']
    assert isinstance(by_plane, dict)
    for plane, cnt in by_plane.items():
        assert plane in (1, 2, 3), f'非法 plane 键:{plane}'
        assert isinstance(cnt, int) and cnt > 0
    assert sum(by_plane.values()) == rep['level_cap_rejects'], (
        f"分解和 {sum(by_plane.values())} ≠ 总量 "
        f"{rep['level_cap_rejects']}(聚合口径漂移)")
