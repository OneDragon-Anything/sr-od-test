"""行为锁:四条旁路 jsonl 流的查询视图(遥测审计 G3 读端补齐)。

实证缺口(遥测审计 G3):query CLI 此前只读 decisions/outcomes/
shop_snapshots/runs 五件,exogenous / exec_events / invest_cards /
obs_conflicts 四条流只能裸翻文件(审计统计都得现写 PowerShell)。
修法:cw_telemetry 新增四个 query 视图 + --view 挂载,约定=按 run_id
过滤(obs_conflicts 例外:跨局采集无 run_id 键)+ 最新优先 + 头部聚合计数。

纯逻辑测试(tmp_path 造样本行;不写真实 .debug 路径——测试纪律②)。
"""
from __future__ import annotations

import json
from pathlib import Path


from sr_od.application.currency_war.telemetry.query import query_exec_events, query_exogenous, query_invest_cards, query_obs_conflicts


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ===== ① exogenous:run 过滤 + 最新优先 + kind 计数 + choice 展开 =====


def test_exogenous_view_filter_and_order_and_choice(tmp_path) -> None:
    """只出目标 run 的行;时间倒序;头部 kind 计数;event_choice 行展开
    (n/pick/reason——G1「提供了什么/选了哪个/为什么」的读出端)。"""
    _write_jsonl(tmp_path / "exogenous.jsonl", [
        {"ts": "2026-08-27T22:00:01", "run_id": "run_a", "round_num": 5,
         "kind": "event_choice", "detail": "encounter pick=idx1",
         "state_snapshot": {"hp": 40, "gold": 30, "level": 4},
         "choice": {"event": "encounter", "options": [
             {"difficulty": "难度1"}, {"difficulty": "难度3"}],
             "n_options": 2, "pick_idx": 1, "reason": "formed→high-diff"}},
        {"ts": "2026-08-27T22:00:02", "run_id": "run_a", "round_num": 6,
         "kind": "node_enter", "detail": "battle_done:普通战斗",
         "state_snapshot": {"hp": 35, "gold": 25, "level": 4}},
        {"ts": "2026-08-27T21:00:00", "run_id": "run_b", "round_num": 1,
         "kind": "popup", "detail": "别的局的行"},
        {"ts": "2026-08-27T22:00:00", "run_id": "run_a", "round_num": 4,
         "kind": "briefing", "detail": "位面简报"},   # ts 更早 → 排最后
    ])
    lines = query_exogenous(tmp_path, "run_a")
    joined = "\n".join(lines)
    assert "kind 计数" in lines[0] and "event_choice×1" in lines[0] \
        and "node_enter×1" in lines[0] and "briefing×1" in lines[0]
    # 最新优先:ts 倒序(node_enter r6 首行,briefing r4 末行)
    assert "node_enter" in lines[1] and "r6" in lines[1]
    assert "briefing" in lines[-1] and "r4" in lines[-1]
    # choice 展开:候选摘要 + pick + reason 可见
    assert "pick=1" in joined and "难度3" in joined and "formed→high-diff" in joined
    # run_b 的行不出现
    assert "别的局的行" not in joined


def test_exogenous_view_empty(tmp_path) -> None:
    """无数据/文件缺失 → 明确提示不炸。"""
    lines = query_exogenous(tmp_path, "run_x")
    assert lines == ["  (无记录)"]


# ===== ② exec_events:画像头(fail 率)+ 逐事件行 =====


def test_exec_events_view_profile_and_rows(tmp_path) -> None:
    """头部 = family:event 计数 + fail 率;逐行带 screen/reason/retry。"""
    _write_jsonl(tmp_path / "exec_events.jsonl", [
        {"ts": "2026-08-27T22:00:01", "run_id": "run_a", "round_num": 3,
         "action_family": "buy", "screen": "battle_prep", "event": "fail",
         "reason": "识别MISS", "retry_count": 2},
        {"ts": "2026-08-27T22:00:02", "run_id": "run_a", "round_num": 4,
         "action_family": "buy", "screen": "battle_prep", "event": "fail",
         "reason": "识别MISS", "retry_count": 1},
        {"ts": "2026-08-27T22:00:03", "run_id": "run_a", "round_num": 5,
         "action_family": "equip", "screen": "battle_prep", "event": "bail",
         "reason": "pingpong", "retry_count": 0},
        {"ts": "2026-08-27T21:00:00", "run_id": "run_b", "round_num": 1,
         "action_family": "buy", "screen": "battle_prep", "event": "fail",
         "reason": "别的局"},
    ])
    lines = query_exec_events(tmp_path, "run_a")
    assert "共3" in lines[0] and "fail率=67%" in lines[0] \
        and "buy:fail×2" in lines[0] and "equip:bail×1" in lines[0]
    # 最新优先 + 字段摘要
    assert "bail" in lines[1] and "equip" in lines[1]
    assert "识别MISS" in "\n".join(lines) and "retry=2" in "\n".join(lines)
    assert "别的局" not in "\n".join(lines)


# ===== ③ invest_cards:按 (kind, ts) 聚组 + ★chosen =====


def test_invest_cards_view_groups_and_chosen(tmp_path) -> None:
    """同一次出卡(同 kind+ts 三行)聚一组;★标 chosen;头部出卡次数。"""
    base = {"schema_version": 1, "run_id": "run_a", "kind": "strategy"}
    _write_jsonl(tmp_path / "invest_cards.jsonl", [
        {**base, "ts": "2026-08-27T22:00:01", "idx": 0, "name": "卡A",
         "effect_text": "效果甲", "chosen": False},
        {**base, "ts": "2026-08-27T22:00:01", "idx": 1, "name": "卡B",
         "effect_text": "效果乙\n跨行", "chosen": True},
        {**base, "ts": "2026-08-27T22:00:05", "idx": 0, "name": "卡C",
         "effect_text": "效果丙", "chosen": True},
        {**base, "ts": "2026-08-27T21:00:00", "run_id": "run_b", "idx": 0,
         "name": "别局卡", "effect_text": "", "chosen": False},
    ])
    lines = query_invest_cards(tmp_path, "run_a")
    joined = "\n".join(lines)
    assert "出卡次数" in lines[0] and "strategy×2" in lines[0]
    # 两个组头;卡B 带 ★选;效果文本跨行被压平
    assert joined.count("[strategy]") == 2
    assert "★选" in joined and "卡A" in joined and "卡C" in joined
    assert "效果乙 跨行" in joined
    assert "别局卡" not in joined


# ===== ④ obs_conflicts:field 分组计数 + verdict 摘要 + 坏行容错 =====


def test_obs_conflicts_view_grouping_and_tolerant_read(tmp_path) -> None:
    """W603 起新行带 run_id:--run 给定时按键过滤(历史行无键不命中,全量
    用空参);头部按 field 计数 + verdict 首词分布;截断坏行跳过不炸
    (best-effort journal 的历史截断行)。"""
    rows = [
        {"ts": "2026-08-27T22:00:01", "field": "board", "old": 1, "new": 3,
         "verdict": "采新-badge(论据很长很长)", "run_id": "run_a"},
        {"ts": "2026-08-27T22:00:02", "field": "level", "old": 5, "new": 4,
         "verdict": "保旧-单调守卫"},
        {"ts": "2026-08-27T22:00:03", "field": "board", "old": {"ocr": 1},
         "new": "count不等", "verdict": "采新-badge", "run_id": "run_a"},
    ]
    path = tmp_path / "obs_conflicts.jsonl"
    _write_jsonl(path, rows)
    with path.open("a", encoding="utf-8") as f:
        f.write('{"ts": "截断坏行", "field": ' + "\n")   # 模拟中断截断
    # run 过滤:只命中带键且相等的行(历史行 level 无 run_id 键 → 不出现)
    lines = query_obs_conflicts(tmp_path, "run_a")
    joined = "\n".join(lines)
    assert "field 计数" in lines[0]
    assert "board×2" in lines[0] and "level" not in lines[0]
    assert "board/采新-badge: 2" in joined
    assert "level" not in joined
    assert "最近明细" in joined
    assert lines[-1].startswith("  [board]")   # 最新优先:board 22:00:03 末行
    # 空 run_id = 全量(含历史无键行)
    full = "\n".join(query_obs_conflicts(tmp_path, ""))
    assert "level/保旧-单调守卫: 1" in full
    assert "board×2" in query_obs_conflicts(tmp_path, "")[0]


def test_obs_conflicts_view_empty(tmp_path) -> None:
    assert query_obs_conflicts(tmp_path, "") == ["  (无记录)"]


# ===== ⑤ CLI 挂载(--view 新名字;源码级弱锁)=====


def test_cli_view_mounted() -> None:
    """--view choices 含四个新视图名,且分发处各挂一行(G3:读出端必须
    是「一句 CLI」,回退裸翻文件 = 回归)。"""
    import inspect

    from sr_od.application.currency_war.telemetry import cli as cw_telemetry
    src = inspect.getsource(cw_telemetry._cli_main)
    for name in ("exogenous", "execevents", "invest", "conflicts"):
        assert f"'{name}'" in src, f"--view {name} 未挂载"
