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
import shutil
import tempfile
from pathlib import Path

from sr_od.application.currency_war.cw_comps import comp_score_breakdown, get_comp
from sr_od.application.currency_war.cw_state import BuyCard, GameState, ShopCard
from sr_od.application.currency_war.cw_telemetry import (
    SCHEMA_VERSION,
    TelemetryRecorder,
    join_decisions_outcomes,
    read_jsonl,
    serialize_action,
    serialize_state,
)
from test import SrTestBase


class TestCurrencyWarTelemetry(SrTestBase):

    def __init__(self, *args, **kwargs):
        SrTestBase.__init__(self, *args, **kwargs)
        self._tmpdirs: list[str] = []

    def _fresh(self, enabled: bool = True) -> tuple[TelemetryRecorder, Path]:
        """新建一个临时 replay 目录的 recorder(测完统一清理)。"""
        tmp = tempfile.mkdtemp(prefix="cw_telemetry_")
        self._tmpdirs.append(tmp)
        return TelemetryRecorder(replay_dir=tmp, enabled=enabled), Path(tmp)

    def tearDown(self) -> None:
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)
        self._tmpdirs.clear()

    # —— enabled=False no-op ——

    def test_disabled_writes_nothing(self):
        """enabled=False → record 全 no-op,不建文件。"""
        rec, tmp = self._fresh(enabled=False)
        rec.start_run("r1", "A8")
        rec.record_decision("r1", "A8", GameState(gold=50), "c", {"c": 1.0}, {"progress": 1.0}, [])
        self.assertFalse((tmp / "decisions.jsonl").exists(), "disabled 不写 decisions")

    # —— decisions.jsonl schema 稳定 ——

    def test_record_decision_schema(self):
        """record_decision 写 decisions.jsonl,字段含 schema_version/run_id/round_num/state/target_comp/scores/breakdown/actions。"""
        rec, tmp = self._fresh()
        rec.start_run("r1", "A8")
        state = GameState(gold=50, hp=80, round_num=3, plane=1, board={"巡海游侠": 2})
        actions = [BuyCard(ShopCard(x=377, faction="巡海游侠", cost=3))]
        rec.record_decision("r1", "A8", state, "列车同行",
                            {"列车同行": 0.8, "巡击青雀": 0.6},
                            {"progress": 0.8, "mechanics_fit": 0.5}, actions)
        lines = read_jsonl(tmp / "decisions.jsonl")
        self.assertEqual(len(lines), 1)
        d = lines[0]
        self.assertEqual(d["schema_version"], SCHEMA_VERSION)
        self.assertEqual(d["run_id"], "r1")
        self.assertEqual(d["difficulty"], "A8")
        self.assertEqual(d["round_num"], 3)
        self.assertEqual(d["target_comp"], "列车同行")
        self.assertAlmostEqual(d["candidate_scores"]["列车同行"], 0.8)
        self.assertIn("progress", d["eval_breakdown"])
        self.assertEqual(d["state"]["gold"], 50)        # state 快照 JSON-safe
        self.assertEqual(d["state"]["hp"], 80)
        self.assertEqual(d["actions"][0]["__type__"], "BuyCard")   # action 带 type 标签
        self.assertEqual(d["hp"], 80)
        self.assertEqual(d["gold"], 50)
        self.assertTrue(d["ts"], "ts 时间戳非空")

    # —— outcomes.jsonl ——

    def test_record_outcome_schema(self):
        """record_outcome 写 outcomes.jsonl,双侧字段完整。"""
        from sr_od.application.currency_war.cw_performance import RoundOutcome
        rec, tmp = self._fresh()
        rec.record_outcome("r1", RoundOutcome(round_num=2, plane=1, node_type="boss",
                                              comp_tag="c", hp_after=70, hp_confidence=0.9, killed=True))
        lines = read_jsonl(tmp / "outcomes.jsonl")
        self.assertEqual(len(lines), 1)
        o = lines[0]
        self.assertEqual(o["run_id"], "r1")
        self.assertEqual(o["round_num"], 2)
        self.assertEqual(o["node_type"], "boss")
        self.assertEqual(o["hp_after"], 70)
        self.assertTrue(o["killed"])
        self.assertEqual(o["schema_version"], SCHEMA_VERSION)

    # —— runs.jsonl + 内存累积 ——

    def test_run_summary_accumulates_gold_and_comps(self):
        """record_run_summary 写 runs.jsonl,gold_trajectory/comps_committed 从内存累积。"""
        rec, tmp = self._fresh()
        rec.start_run("r1", "A8")
        for rnd, gold, comp in [(1, 50, ""), (2, 40, "列车同行"), (3, 60, "列车同行"), (4, 55, "巡击青雀")]:
            rec.record_decision("r1", "A8", GameState(gold=gold, round_num=rnd), comp, {}, {}, [])
        rec.record_run_summary("r1", "win", plane_reached=3, rounds_survived=18, final_hp=30)
        lines = read_jsonl(tmp / "runs.jsonl")
        self.assertEqual(len(lines), 1)
        s = lines[0]
        self.assertEqual(s["result"], "win")
        self.assertEqual(s["difficulty"], "A8")
        self.assertEqual(s["gold_trajectory"], [50, 40, 60, 55])
        # comps: 空 target 不记;列车同行记一次(连续去重);巡击青雀 pivot 记一次
        self.assertEqual(s["comps_committed"], ["列车同行", "巡击青雀"])
        self.assertEqual(s["plane_reached"], 3)

    # —— join decisions ↔ outcomes ——

    def test_join_decisions_outcomes(self):
        """join_decisions_outcomes 按 (run_id, round_num) 合并;无 outcome 的决策 outcome=None。"""
        from sr_od.application.currency_war.cw_performance import RoundOutcome
        rec, tmp = self._fresh()
        rec.record_decision("r1", "A8", GameState(round_num=1), "c", {}, {}, [])
        rec.record_decision("r1", "A8", GameState(round_num=2), "c", {}, {}, [])
        rec.record_outcome("r1", RoundOutcome(round_num=2, plane=1, node_type="普通战斗", comp_tag="c", hp_after=90))
        joined = join_decisions_outcomes(tmp)
        self.assertEqual(len(joined), 2)
        by_round = {j["round_num"]: j for j in joined}
        self.assertIsNone(by_round[1]["outcome"], "round 1 无 outcome → None")
        self.assertIsNotNone(by_round[2]["outcome"], "round 2 有 outcome")
        self.assertEqual(by_round[2]["outcome"]["hp_after"], 90)

    # —— 序列化 JSON-safe ——

    def test_serialize_state_jsonable(self):
        """serialize_state 产出可 json.dumps 的 dict(含嵌套 board / bench)。"""
        state = GameState(gold=10, board={"仙舟": 2}, bench=[])
        d = serialize_state(state)
        s = json.dumps(d, ensure_ascii=False)   # 不抛即 JSON-safe
        self.assertIn("gold", s)

    def test_serialize_action_has_type(self):
        """serialize_action 带 __type__ 标签 + JSON-safe。"""
        d = serialize_action(BuyCard(ShopCard(x=1, faction="仙舟", cost=2)))
        json.dumps(d)   # 不抛
        self.assertEqual(d["__type__"], "BuyCard")

    # —— read_jsonl 容错 ——

    def test_read_jsonl_missing_file(self):
        """文件不存在 → []。"""
        self.assertEqual(read_jsonl(Path("nonexistent") / "x.jsonl"), [])

    # —— 端到端:comp_score_breakdown 串 telemetry(真实复盘路径)——

    def test_breakdown_feeds_telemetry(self):
        """comp_score_breakdown 的 dict 直接进 record_decision.eval_breakdown(复盘路径通)。"""
        from sr_od.application.currency_war.cw_comps import make_score_context
        rec, tmp = self._fresh()
        rec.start_run("r1", "A8")
        阿雅 = get_comp("昼神阿雅")
        state = GameState(board={"昼之半神": 4}, round_num=8)
        ctx = make_score_context(state)
        breakdown = comp_score_breakdown(阿雅, state, ctx)
        rec.record_decision("r1", "A8", state, "昼神阿雅", {"昼神阿雅": 0.9}, breakdown, [])
        d = read_jsonl(tmp / "decisions.jsonl")[0]
        self.assertEqual(set(d["eval_breakdown"].keys()), set(breakdown.keys()),
                         "breakdown schema 透传到 telemetry")
