"""economy 视图费用真值锁:升级花费逐轮读 state.level_up_cost(OCR 真值),
读不到时按 XP_CLICK_COST_FALLBACK 兜底并在视图标 `?`;升级成本与 gold
并列显示。

背景:视图曾把升级花费硬编码 4 金/次,与每轮已落盘的 level_up_cost
真值脱节——费用随等级/词缀变动时收入支出对账系统性失真。
"""
from __future__ import annotations

from pathlib import Path

from sr_od.application.currency_war.kernel.cw_state import (
    XP_CLICK_COST_FALLBACK,
    GameState,
    LevelUp,
)
from sr_od.application.currency_war.cw_telemetry import (
    TelemetryRecorder,
    query_economy,
)


def _record_one_round(tmp: str, run_id: str, level_up_cost: int | None) -> list[str]:
    """写一轮带 LevelUp 动作的 decisions 样本到 tmp_path,返回 economy 视图行。"""
    rec = TelemetryRecorder(replay_dir=tmp, enabled=True)
    rec.start_run(run_id, 'A8')
    rec.record_decision(
        run_id, 'A8',
        GameState(gold=30, round_num=1, plane=1, level_up_cost=level_up_cost),
        'c', {}, {}, [LevelUp(cost=level_up_cost or XP_CLICK_COST_FALLBACK)])
    return query_economy(Path(tmp), run_id)


def test_economy_uses_state_level_up_cost(tmp_path: Path):
    """level_up_cost 真值在场:视图 lv= 显示真值,升级花费按真值计(非 4)。"""
    eco = _record_one_round(str(tmp_path), 'w318a', 5)
    assert len(eco) == 1, f'应恰好一行,实际 {eco}'
    # lv=5 与 gold 并列可见;花=5(1 次 LevelUp × 真值 5;若仍按 4 硬编码会得 4)
    assert 'lv=5' in eco[0], f'升级成本应与 gold 并列显示,实际 {eco}'
    assert '花=5' in eco[0], f'升级花费应按 level_up_cost=5 计,实际 {eco}'


def test_economy_falls_back_and_marks_when_cost_missing(tmp_path: Path):
    """level_up_cost 缺(None,OCR 未读/旧数据):按 XP_CLICK_COST_FALLBACK
    兜底计入,且 lv= 后标 `?` 提示成本项可能有偏。"""
    eco = _record_one_round(str(tmp_path), 'w318b', None)
    assert len(eco) == 1, f'应恰好一行,实际 {eco}'
    assert f'lv={XP_CLICK_COST_FALLBACK}?' in eco[0], f'兜底须带 ? 标记,实际 {eco}'
    assert f'花={XP_CLICK_COST_FALLBACK}' in eco[0], f'花费按兜底常量计入,实际 {eco}'
