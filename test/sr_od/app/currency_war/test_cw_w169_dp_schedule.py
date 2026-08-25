# -*- coding: utf-8 -*-
"""W169/ADR-0368 DP 视界位面槽序重排单帧锁。

锁契约(每条=一个确定输入下的确定行为;不锁分布数值):
- ① 日程单一源 schedule_of:seen 序列=位面轮数真值(未揭晓位面回退 9);
  脏表封顶 [1,9](同 W154/ADR-0366 守卫语义);
- ② 默认日程 ≡ 旧常量语义逐位一致(offsets/ends/difficulty_scale/
  node_income boss 槽,全 t 域对拍旧式公式——P1 零漂移的结构面);
- ③ 修正日程 (9,7,9):boss 奖金落 P2 真实末轮 t=15(旧幻影 t=17);
  t=16 归 P3(P3 前移,总程 25 槽);
- ④ slot_of 查询映射:默认日程 ≡ 旧 ``t=(p-1)*9+r-1``;修正日程
  P2r7→15 / P3r1→16;轮/位面越界防御夹取;
- ⑤ memo 键=(指纹, 日程):P1 期(seen 至多 [9])与裸调用同键同解对象
  (P1 零漂移的结构保证);不同日程各自成解(total 27 vs 25);
- ⑥ ev.dp_posture 透传 session 且查修正日程解(P2 消费端接线);
- ⑦ prep_director.store_plane_table:每位面首帧重写(旧 write-once 守卫
  使 P1 表整局滞留的生产断链修复)+ append plane_lengths_seen。
"""
from __future__ import annotations

from sr_od.application.currency_war import cw_horizon as hz
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.ev import dp_posture


def _sess(seen: list[int] | None) -> StrategySession:
    s = StrategySession()
    if seen is not None:
        s.plane_lengths_seen = list(seen)
    return s


# ---------- ① 日程单一源 ----------

def test_schedule_of_seen_and_fallback():
    assert hz.schedule_of(None) == (9, 9, 9)
    assert hz.schedule_of(_sess(None)) == (9, 9, 9)
    # P1 期(seen 至多 [9])≡ 默认日程 → P1 零漂移的结构保证
    assert hz.schedule_of(_sess([9])) == (9, 9, 9)
    # P2 查询期:P2=7 真值,P3 未揭晓回退 9
    assert hz.schedule_of(_sess([9, 7])) == (9, 7, 9)
    # P3 进表即自适应
    assert hz.schedule_of(_sess([9, 7, 8])) == (9, 7, 8)


def test_schedule_of_dirty_table_guard():
    # 脏表封顶:每位面长度夹 [1, 9](W154 越界槽不数同款守卫)
    assert hz.schedule_of(_sess([12, 9, 7])) == (9, 9, 7)
    assert hz.schedule_of(_sess([0, 7])) == (1, 7, 9)


# ---------- ② 默认日程 ≡ 旧常量语义 ----------

def test_default_schedule_offsets_and_ends():
    assert hz.plane_offsets() == (0, 9, 18)
    assert hz.plane_end_slots() == frozenset({8, 17, 26})


def test_default_difficulty_scale_equals_legacy_divmod():
    for t in range(hz.TOTAL_NODES):
        plane, node = divmod(t, 9)   # 旧式
        if plane == 0:
            old = 0.5 if node < 4 else (0.9 if node < 8 else 1.4)
        elif plane == 1:
            old = 1.5 + 0.05 * node
        else:
            old = 1.8 + 0.05 * node
        assert hz.difficulty_scale(t) == old, t


def test_default_node_income_boss_slots_equal_legacy_mod():
    for t in range(hz.TOTAL_NODES):
        base = 9   # b=None → 5+4
        old = base + (2 if (t + 1) % 9 == 0 else 0)
        assert hz.node_income(t, None) == old, t


# ---------- ③ 修正日程 (9,7,9) ----------

def test_corrected_schedule_boss_at_real_p2_end():
    pl = (9, 7, 9)
    assert hz.plane_offsets(pl) == (0, 9, 16)
    assert hz.plane_end_slots(pl) == frozenset({8, 15, 24})
    # P2 boss 实在 t=15(r7):修正日程有奖金,旧日程无(旧落幻影 t=17)
    assert hz.node_income(15, None, pl) - hz.node_income(14, None, pl) == 2
    assert hz.node_income(15, None) == hz.node_income(14, None)  # 旧日程无差
    # t=16 归 P3 node0(修正)而非 P2 node7(旧)——P3 前移
    assert hz.difficulty_scale(16, pl) == 1.8
    assert hz.difficulty_scale(16) == 1.5 + 0.05 * 7


# ---------- ④ slot_of 查询映射 ----------

def test_slot_of_default_equals_legacy_formula():
    sol = hz.HorizonSolution(pl=hz.DEFAULT_PLANE_LENGTHS)
    for p in (1, 2, 3, 4):
        for r in (1, 5, 9, 12):
            assert sol.slot_of(p, r) == (min(p, 3) - 1) * 9 + min(r, 9) - 1
    # 越界防御:plane 下夹 1(旧式对 plane<1 产出负 t 后被 None 分支拦,
    # GameState 域内 plane 恒 ≥1,此处只锁防御不越日程)
    assert sol.slot_of(0, 1) == 0


def test_slot_of_corrected_schedule():
    sol = hz.HorizonSolution(pl=(9, 7, 9))
    assert sol._total == 25
    assert sol.slot_of(1, 1) == 0
    assert sol.slot_of(2, 1) == 9        # P2 偏移不变(两种日程同 9)
    assert sol.slot_of(2, 7) == 15       # P2 真实末轮
    assert sol.slot_of(2, 9) == 15       # 轮越界夹本位面轮数(7)
    assert sol.slot_of(3, 1) == 16       # P3 前移(旧 18)
    assert sol.slot_of(3, 20) == 24      # 槽越界夹 total-1


# ---------- ⑤ memo 键=(指纹, 日程) ----------

def test_solved_memo_p1_same_object_and_schedule_split():
    # P1 期与裸调用同键 → 同一解对象(P1 零漂移的结构保证)
    assert (hz._solved(None, _sess([9])) is hz._solved(None)
            is hz._solved(None, _sess(None)))
    # P2 真值日程各自成解,且与默认日程不同对象
    fix = hz._solved(None, _sess([9, 7]))
    assert fix is not hz._solved(None)
    assert fix._total == 25 and hz._solved(None)._total == 27


# ---------- ⑥ dp_posture 消费端 ----------

def test_dp_posture_p2_uses_session_schedule(monkeypatch):
    st_dp = None
    real_solved = hz._solved
    captured: dict = {}

    def spy(strategies, session=None):
        captured['session'] = session
        return real_solved(strategies, session)

    monkeypatch.setattr(hz, '_solved', spy)

    class _St:   # 最小 state 桩(dp_posture 只读五字段)
        plane, round_num = 2, 7
        gold, level, hp = 40, 8, 60
        active_strategies = []

    sess = _sess([9, 7])
    p = dp_posture(_St(), sess)   # type: ignore[arg-type]
    assert captured['session'] is sess
    expected = hz.solve_cached(None, (9, 7, 9)).posture(15, 40, 8, 60, 0.0)
    assert p.tag == expected.tag and p.refresh_budget == expected.refresh_budget
    # 旧日程(先验)同槽动作不同(伤害实证:该帧翻转——锁翻转存在性,
    # 具体分布数值不锁)
    legacy = hz.solve_cached(None).posture(15, 40, 8, 60, 0.0)
    assert legacy.tag != expected.tag or legacy.refresh_budget != expected.refresh_budget


# ---------- ⑦ 写入端断链修复 ----------

def test_store_plane_table_rewrites_per_plane():
    from sr_od.application.currency_war.prep_director import store_plane_table
    s = StrategySession()
    p1 = ['battle'] * 9
    assert store_plane_table(s, p1, 1) is True
    assert s.plane_node_table == p1 and s.plane_node_table_plane == 1
    assert s.plane_lengths_seen == [9]
    # 同位面多次 probe 不覆写(位面内恒定)
    assert store_plane_table(s, ['battle'] * 8, 1) is False
    assert s.plane_node_table == p1
    # 进 P2 首帧重写:7 槽真值落盘(旧 write-once 守卫此处恒 False=断链)
    p2 = ['battle'] * 7
    assert store_plane_table(s, p2, 2) is True
    assert s.plane_node_table == p2
    assert s.plane_lengths_seen == [9, 7]
    # 空序/位面未知不写
    assert store_plane_table(s, [], 2) is False
    assert store_plane_table(s, p2, None) is False


def test_store_plane_table_schedule_feeds_horizon():
    from sr_od.application.currency_war.prep_director import store_plane_table
    s = StrategySession()
    store_plane_table(s, ['battle'] * 9, 1)
    store_plane_table(s, ['battle'] * 7, 2)
    assert hz.schedule_of(s) == (9, 7, 9)
