"""货币战争 决策迹采集(cw_telemetry)测试 —— 纯逻辑,不依赖游戏。

验证采集管线(用户:搜集数据支持后续策略优化):
- enabled=False → no-op(不写文件)。
- 三路 JSONL(decisions/outcomes/runs)schema 稳定(schema_version + join key)。
- record_decision/outcome/run_summary 写对应流;serialize_state/action JSON-safe。
- join_decisions_outcomes 按 (run_id, round_num) join。
- 内存累积:gold_trajectory / comps_committed 进 run summary。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sr_od.application.currency_war.kernel.cw_comps import comp_score_breakdown, get_comp
from sr_od.application.currency_war.kernel.cw_state import BuyCard, GameState, ShopCard
from sr_od.application.currency_war.telemetry.cw_telemetry import (
    SCHEMA_VERSION,
    TelemetryRecorder,
    join_decisions_outcomes,
    read_jsonl,
    serialize_action,
    serialize_state,
)


def _fresh(tmp_dir: str, enabled: bool = True) -> tuple[TelemetryRecorder, Path]:
    """新建一个 recorder 指向给定 replay 目录(调用方用 TemporaryDirectory 管理清理)。"""
    return TelemetryRecorder(replay_dir=tmp_dir, enabled=enabled), Path(tmp_dir)


# —— enabled=False no-op ——


def test_disabled_writes_nothing() -> None:
    """enabled=False → record 全 no-op,不建文件。"""
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp, enabled=False)
        rec.start_run("r1", "A8")
        rec.record_decision("r1", "A8", GameState(gold=50), "c", {"c": 1.0}, {"progress": 1.0}, [])
        assert not (tmp_path / "decisions.jsonl").exists(), "disabled 不写 decisions"


# —— decisions.jsonl schema 稳定 ——


def test_record_decision_schema() -> None:
    """record_decision 写 decisions.jsonl,字段含 schema_version/run_id/round_num/state/target_comp/scores/breakdown/actions。"""
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp)
        rec.start_run("r1", "A8")
        state = GameState(gold=50, hp=80, round_num=3, plane=1, board={"巡海游侠": 2})
        actions = [BuyCard(ShopCard(x=377, faction="巡海游侠", cost=3))]
        rec.record_decision("r1", "A8", state, "列车同行",
                            {"列车同行": 0.8, "追击飞霄": 0.6},
                            {"progress": 0.8, "mechanics_fit": 0.5}, actions)
        lines = read_jsonl(tmp_path / "decisions.jsonl")
        assert len(lines) == 1
        d = lines[0]
        assert d["schema_version"] == SCHEMA_VERSION
        assert d["run_id"] == "r1"
        assert d["difficulty"] == "A8"
        assert d["round_num"] == 3
        assert d["target_comp"] == "列车同行"
        assert d["candidate_scores"]["列车同行"] == pytest.approx(0.8)
        assert "progress" in d["eval_breakdown"]
        assert d["state"]["gold"] == 50        # state 快照 JSON-safe
        assert d["state"]["hp"] == 80
        assert d["actions"][0]["__type__"] == "BuyCard"   # action 带 type 标签
        assert d["hp"] == 80
        assert d["gold"] == 50
        assert d["ts"], "ts 时间戳非空"


# —— outcomes.jsonl ——


def test_record_outcome_schema() -> None:
    """record_outcome 写 outcomes.jsonl,双侧字段完整。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp)
        rec.record_outcome("r1", RoundOutcome(round_num=2, plane=1, node_type="boss",
                                              comp_tag="c", hp_after=70, hp_confidence=0.9, killed=True))
        lines = read_jsonl(tmp_path / "outcomes.jsonl")
        assert len(lines) == 1
        o = lines[0]
        assert o["run_id"] == "r1"
        assert o["round_num"] == 2
        assert o["node_type"] == "boss"
        assert o["hp_after"] == 70
        assert o["killed"]
        assert o["schema_version"] == SCHEMA_VERSION


# —— runs.jsonl + 内存累积 ——


def test_run_summary_accumulates_gold_and_comps() -> None:
    """record_run_summary 写 runs.jsonl,gold_trajectory/comps_committed 从内存累积。"""
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp)
        rec.start_run("r1", "A8")
        for rnd, gold, comp in [(1, 50, ""), (2, 40, "列车同行"), (3, 60, "列车同行"), (4, 55, "追击飞霄")]:
            rec.record_decision("r1", "A8", GameState(gold=gold, round_num=rnd), comp, {}, {}, [])
        rec.record_run_summary("r1", "win", plane_reached=3, rounds_survived=18, final_hp=30)
        lines = read_jsonl(tmp_path / "runs.jsonl")
        assert len(lines) == 1
        s = lines[0]
        assert s["result"] == "win"
        assert s["difficulty"] == "A8"
        assert s["gold_trajectory"] == [50, 40, 60, 55]
        # comps: 空 target 不记;列车同行记一次(连续去重);追击飞霄 pivot 记一次
        assert s["comps_committed"] == ["列车同行", "追击飞霄"]
        assert s["plane_reached"] == 3


# —— join decisions ↔ outcomes ——


def test_join_decisions_outcomes() -> None:
    """join_decisions_outcomes 按 (run_id, round_num) 合并;无 outcome 的决策 outcome=None。"""
    from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp)
        rec.record_decision("r1", "A8", GameState(round_num=1), "c", {}, {}, [])
        rec.record_decision("r1", "A8", GameState(round_num=2), "c", {}, {}, [])
        rec.record_outcome("r1", RoundOutcome(round_num=2, plane=1, node_type="普通战斗", comp_tag="c", hp_after=90))
        joined = join_decisions_outcomes(tmp_path)
        assert len(joined) == 2
        by_round = {j["round_num"]: j for j in joined}
        assert by_round[1]["outcome"] is None, "round 1 无 outcome → None"
        assert by_round[2]["outcome"] is not None, "round 2 有 outcome"
        assert by_round[2]["outcome"]["hp_after"] == 90


# —— 序列化 JSON-safe ——


def test_serialize_state_jsonable() -> None:
    """serialize_state 产出可 json.dumps 的 dict(含嵌套 board / bench)。"""
    state = GameState(gold=10, board={"仙舟": 2}, bench=[])
    d = serialize_state(state)
    s = json.dumps(d, ensure_ascii=False)   # 不抛即 JSON-safe
    assert "gold" in s


def test_serialize_action_has_type() -> None:
    """serialize_action 带 __type__ 标签 + JSON-safe。"""
    d = serialize_action(BuyCard(ShopCard(x=1, faction="仙舟", cost=2)))
    json.dumps(d)   # 不抛
    assert d["__type__"] == "BuyCard"


# —— read_jsonl 容错 ——


def test_read_jsonl_missing_file() -> None:
    """文件不存在 → []。"""
    assert read_jsonl(Path("nonexistent") / "x.jsonl") == []


# —— 端到端:comp_score_breakdown 串 telemetry(真实复盘路径)——


def test_breakdown_feeds_telemetry() -> None:
    """comp_score_breakdown 的 dict 直接进 record_decision.eval_breakdown(复盘路径通)。"""
    from sr_od.application.currency_war.kernel.cw_comps import make_score_context
    with tempfile.TemporaryDirectory(prefix="cw_telemetry_") as tmp:
        rec, tmp_path = _fresh(tmp)
        rec.start_run("r1", "A8")
        阿雅 = get_comp("昼神阿雅")
        state = GameState(board={"昼之半神": 4}, round_num=8)
        ctx = make_score_context(state)
        breakdown = comp_score_breakdown(阿雅, state, ctx)
        rec.record_decision("r1", "A8", state, "昼神阿雅", {"昼神阿雅": 0.9}, breakdown, [])
        d = read_jsonl(tmp_path / "decisions.jsonl")[0]
        assert set(d["eval_breakdown"].keys()) == set(breakdown.keys()), (
            "breakdown schema 透传到 telemetry"
        )


# ===== ADR-0132 投资卡效果原文采集(bucket_card_texts + invest_cards.jsonl) =====
def test_bucket_card_texts_nearest_anchor() -> None:
    """分桶:文本归 x 最近锚点卡;y 带外(标题/卡名行/底部 UI)不归;桶内 y 升序。"""
    from sr_od.application.currency_war.telemetry.cw_telemetry import bucket_card_texts
    anchors = [(0, 300), (1, 920), (2, 1540)]
    items = [
        ("请选择投资策略", 960, 98),    # 标题:带外
        ("中产阶级", 300, 490),        # 卡名行:带外(y<505)
        ("每次进入新节点获得2金币", 290, 560),
        ("立刻获得4金币", 930, 545),
        ("商店刷新费用降低", 1550, 610),
        ("确认", 978, 983),            # 底部 UI:带外
    ]
    out = bucket_card_texts(anchors, items, 505, 835)
    assert out[0] == ["每次进入新节点获得2金币"]
    assert out[1] == ["立刻获得4金币"]
    assert out[2] == ["商店刷新费用降低"]


def test_bucket_card_texts_empty_anchors() -> None:
    from sr_od.application.currency_war.telemetry.cw_telemetry import bucket_card_texts
    assert bucket_card_texts([], [("x", 1, 2)], 0, 100) == {}


def test_record_invest_cards_writes_jsonl(tmp_path, monkeypatch) -> None:
    """record_invest_cards:逐卡一行写 invest_cards.jsonl(带 run_id/kind/chosen);无 run 时不写。"""
    from sr_od.application.currency_war.telemetry import cw_telemetry
    rec = cw_telemetry.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(cw_telemetry, '_RECORDER', rec)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'run_test_1')
    cw_telemetry.record_invest_cards('strategy', [
        {"idx": 0, "name": "定期福利", "x": 300, "effect_text": "立刻获得4金币 | 每次进入新节点获2金币", "chosen": True},
        {"idx": 1, "name": "数值碾压", "x": 920, "effect_text": "", "chosen": False},
    ])
    rows = cw_telemetry.read_jsonl(tmp_path / 'invest_cards.jsonl')
    assert len(rows) == 2
    assert rows[0]['kind'] == 'strategy' and rows[0]['run_id'] == 'run_test_1'
    assert rows[0]['chosen'] is True and '金币' in rows[0]['effect_text']

