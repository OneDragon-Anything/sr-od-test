"""W823:GameState.hp None 化锁 + r1 档案真值反推修数锁。

None 化语义(ADR-0491 三来源;ADR-0282「开局兜底 100」正式废止):
- GameState.hp: int | None,默认 None——无真值即 None,不产「看起来像真值」的兜底;
- 对账层 reconcile_hp:读不到 → 沿用 last_hp_real;全无真值 → (None, False);
- 消费点对 None 一律保守:血线触发条件(<)不触发、授权/许可条件(>=)拒绝、
  可信位门(hp_readable or hp_trusted)fail-closed;
- 档案 r1 兜底 100 帧按局反推真值回填(规则(按局)语义,真值源=各局 r1
  结算屏,ADR-0491 结算来源可信度等同真读)。
"""
from __future__ import annotations

from pathlib import Path

# ===== 1. None 化:字段默认与对账层 =====


def test_game_state_default_hp_none() -> None:
    """默认构造 = 未观测态:hp=None(不再兜底 100)。"""
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert GameState().hp is None


def test_reconcile_no_truth_returns_none() -> None:
    """开局全无真值:reconcile_hp 返回 (None, False),不兜底 100。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = StrategySession()
    assert reconcile_hp(s, None) == (None, False)
    assert s.last_hp_real is None   # None 不写回真值锚


def test_reconcile_read_none_keeps_inherited_int() -> None:
    """读不到但有真值:沿用 last_hp_real(int)——沿用语义与 None 化并存。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.kernel.cw_reconcile import reconcile_hp
    s = StrategySession()
    s.last_hp_real = 55
    hp, readable = reconcile_hp(s, None)
    assert hp == 55 and readable is False


# ===== 2. 消费点 None 守卫(保守方向锁,抽样代表面)=====


def test_is_emergency_none_false() -> None:
    """应急触发(None=无真值)→ False(不进应急带,保守)。"""
    from sr_od.application.currency_war.kernel.cw_economy import is_emergency
    from sr_od.application.currency_war.kernel.cw_registry import DEFAULT_REGISTRY
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert is_emergency(GameState(hp=None), DEFAULT_REGISTRY) is False


def test_rounds_alive_none_zero() -> None:
    """期望存活轮(None=无真值)→ 0(fail-closed)。"""
    from sr_od.application.currency_war.kernel.cw_line_switch import rounds_alive
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert rounds_alive(GameState(hp=None), None) == 0


def test_decide_event_none_hp_no_crash() -> None:
    """局外/无真值态跑事件决策不炸(None 守卫贯穿评分面)。"""
    from sr_od.application.currency_war.kernel.cw_events import decide_event
    from sr_od.application.currency_war.kernel.cw_state import GameState
    pick = decide_event(["投资策略甲", "投资策略乙", "投资策略丙"], None,
                        GameState(hp=None))
    assert pick is not None


def test_decision_state_none_hp_stays_none() -> None:
    """快照无真值 → 策略态 hp=None(不落 100 兜底;W823 adapter 改型点)。"""
    from sr_od.application.currency_war.decision.cw_strategy import StrategySession
    from sr_od.application.currency_war.decision.decision_v2.adapter import (
        decision_state,
    )
    from sr_od.application.currency_war.decision.decision_v2.contracts import (
        Snapshot,
        SubstateClassification,
    )
    snap = Snapshot(hp=None, hp_readable=False,
                    classification=SubstateClassification(name='prep_shop'))
    st = decision_state(snap, StrategySession())
    assert st.hp is None


def test_discipline_predicates_none_false() -> None:
    """血预算谓词(None=无真值)→ False(不触发停手/降格辖域)。"""
    from sr_od.application.currency_war.decision.decision_v2.discipline import (
        p1_exit_blood_short,
    )
    from sr_od.application.currency_war.kernel.cw_registry import (
        DEFAULT_REGISTRY,
    )
    from sr_od.application.currency_war.kernel.cw_state import GameState
    assert p1_exit_blood_short(GameState(hp=None), DEFAULT_REGISTRY) is False


# ===== 3. 档案 r1 真值反推修数锁(档案缺位时 skip,不假绿)=====

_ARCHIVE_ROOT = Path(__file__).resolve().parents[4] / ".debug/temp/currency_war/replay/matches"

# 反推法:各局 rounds 表 r1 行结算屏真值(r1 节点无战斗,结算 hp=开局值)
# = 该局 2 条兜底 100 帧的回填真值。锁值出处 = w823 反推表(REPORT)。
_EXPECT_TRUTH = {
    "g_20260830_071711": 82, "g_20260830_073750": 82,
    "g_20260830_083542": 82, "g_20260830_094754": 62,
    "g_20260830_103601": 82, "g_20260830_113824": 82,
    "g_20260830_125824": 82, "g_20260830_140843": 82,
    "g_20260830_150029": 82,
}


def _load_frames(gid: str):
    import json

    import pytest
    p = _ARCHIVE_ROOT / f"match_{gid}.json"
    if not p.exists():
        pytest.skip(f"档案缺位:{p}")
    doc = json.loads(p.read_text(encoding="utf-8"))
    return [json.loads(f) if isinstance(f, str) else f
            for f in doc["slices"]["decisions.jsonl"]]


def test_archive_r1_repaired_truth_values() -> None:
    """9 局 18 帧:反推真值回填正确,source=rule_per_game,无 hp=100 残留。"""
    for gid, truth in _EXPECT_TRUTH.items():
        frames = _load_frames(gid)
        r1 = [f for f in frames if f.get("plane") == 1 and f.get("round_num") == 1]
        assert len(r1) >= 2, gid
        hits = [f for f in r1
                if f.get("hp") == truth
                and (f.get("hp_repair") or {}).get("source") == "rule_per_game"]
        assert len(hits) == 2, (gid, len(hits))
        assert not [f for f in r1 if f.get("hp") == 100], gid   # 0 兜底残留


def test_archive_index_r1_rule_value_synced() -> None:
    """index.jsonl:r1_hp_rule_value 与帧值一致(additive 键同步)。"""
    import json

    import pytest
    ip = _ARCHIVE_ROOT / "index.jsonl"
    if not ip.exists():
        pytest.skip("index.jsonl 缺位")
    rows = {json.loads(l)["game_id"]: json.loads(l)
            for l in ip.read_text(encoding="utf-8").splitlines() if l.strip()}
    for gid, truth in _EXPECT_TRUTH.items():
        row = rows.get(gid)
        assert row is not None, gid
        assert row.get("r1_hp_rule_value") == truth, gid
