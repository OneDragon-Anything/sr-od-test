"""行为锁:卖牌回金落盘(exogenous.jsonl kind='sell_income')+ economy 视图「卖回」格。

实证缺口(遥测审计卖回件):decisions 行的 actions 里有 SellBench,但卖出
**实际回金**没单独落字段——economy 视图对卖牌收入只能靠 gold 差分倒推
(混入利息/连胜金噪声),「金去向(升级/买件/刷新/卖回)」四分账缺卖回一格。
修法两段:
① 写端:shop.py SellBench 执行分支在卖出成功后读执行前后 gold 差,
   经共用辅助 cw_telemetry.record_sell_income 落 exogenous 行
   (choice={slot/char/gold_delta};OCR miss → gold_delta=None);
② 读端:query_economy 优先聚合 sell_income 实收值补「卖+NN」格;
   该轮有行但 delta=None 计 0 并标 `?`;无行(旧数据/sim 局)回退
   decisions actions 的 SellBench.income 口径,不回归。

纯逻辑/桩测试(monkeypatch 构造;TelemetryRecorder 指 tmp_path,不写真实
.debug;_CURRENT_RUN_ID 经 monkeypatch.setattr 还原,不污染 session)。
"""
from __future__ import annotations

import inspect
from contextlib import contextmanager

import pytest

from sr_od.application.currency_war import cw_telemetry
from sr_od.application.currency_war.cw_state import (
    GameState,
    SellBench,
)
from sr_od.application.currency_war.cw_telemetry import (
    TelemetryRecorder,
    query_economy,
    read_jsonl,
    record_sell_income,
)


@pytest.fixture(autouse=True)
def _reset_run_ctx(monkeypatch):
    """测试卫生:run_id 与 ctx match 引用经 monkeypatch 还原(不串后续测试)。"""
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', 'w323-run')
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [None])


@contextmanager
def _recorder_as_module(tmp_path):
    """构造 enabled recorder 并临时注入模块 get_recorder(参照 event_choice 落盘测试手法)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    origin = cw_telemetry.get_recorder
    cw_telemetry.get_recorder = lambda: rec   # noqa: ANN001  测试内注入
    try:
        yield rec
    finally:
        cw_telemetry.get_recorder = origin


# ===== ① 写端:record_sell_income =====


def test_record_sell_income_writes_row(tmp_path) -> None:
    """卖出实收回金落盘:kind/round/slot/char/gold_delta 齐,快照带 plane/gold。"""
    with _recorder_as_module(tmp_path) as rec:
        record_sell_income(GameState(gold=12, round_num=4, plane=1),
                           slot=3, char_id='桑博',
                           gold_before=10, gold_after=13)
        rows = read_jsonl(tmp_path / 'exogenous.jsonl')
    assert len(rows) == 1
    row = rows[0]
    assert row['kind'] == 'sell_income'
    assert row['round_num'] == 4
    assert row['choice'] == {'slot': 3, 'char': '桑博', 'gold_delta': 3}
    assert row['state_snapshot']['plane'] == 1
    assert row['state_snapshot']['gold'] == 12


def test_record_sell_income_none_when_gold_unreadable(tmp_path) -> None:
    """执行前后 gold 任一读不到(OCR miss)→ gold_delta=None(视图计 0 并标 ?)。"""
    with _recorder_as_module(tmp_path) as rec:
        record_sell_income(GameState(gold=10, round_num=2, plane=1),
                           slot=0, char_id='青雀', gold_before=10, gold_after=None)
        row = read_jsonl(tmp_path / 'exogenous.jsonl')[0]
    assert row['choice']['gold_delta'] is None
    assert rec.enabled   # 注入确实生效(防假绿)


def test_record_sell_income_no_run_id_noop(tmp_path) -> None:
    """run_id 空(局外)直接 no-op,不产生孤儿行(与 record_exogenous 同门控)。"""
    origin_run = cw_telemetry._CURRENT_RUN_ID
    cw_telemetry._CURRENT_RUN_ID = ''
    try:
        record_sell_income(GameState(round_num=1), slot=0, char_id='x',
                           gold_before=1, gold_after=2)
    finally:
        cw_telemetry._CURRENT_RUN_ID = origin_run
    assert not (tmp_path / 'exogenous.jsonl').exists()


def test_shop_sell_branch_wiring_in_source() -> None:
    """接线锁:shop.py SellBench 执行分支真调 record_sell_income(落盘点唯一源)。"""
    from sr_od.application.currency_war.operations.prep import shop

    src = inspect.getsource(shop.BuyShopCards.buy)
    assert 'record_sell_income(' in src, 'SellBench 执行分支未接 W323 落盘'


# ===== ② 读端:economy 视图「卖回」格 =====


def test_economy_uses_observed_sell_income(tmp_path) -> None:
    """实收 sell_income 在场:视图 卖+NN 用执行点真值,income 残差按它倒推。

    场景:r1 金 20 → r2 金 25,期间仅卖一件实收 3(无利息/连胜):
    income 残差 = 25 − 20 + 0(花)− 3(卖回)= 2。
    """
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323a', 'A8')
    rec.record_decision('w323a', 'A8',
                        GameState(gold=20, round_num=1, plane=1),
                        'c', {}, {}, [])
    rec.record_decision('w323a', 'A8',
                        GameState(gold=25, round_num=2, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0)])   # 生产行不带 income
    with _recorder_as_module(tmp_path):
        cw_telemetry._CURRENT_RUN_ID = 'w323a'
        try:
            record_sell_income(GameState(gold=25, round_num=2, plane=1),
                               slot=0, char_id='桑博', gold_before=22, gold_after=25)
        finally:
            cw_telemetry._CURRENT_RUN_ID = 'w323-run'
    eco = query_economy(tmp_path, 'w323a')
    assert any('卖+3' in ln for ln in eco), f'economy 应显示实收卖回 3,实际 {eco}'
    assert any('收=2' in ln for ln in eco), \
        f'收入残差应扣掉卖回(25-20+0-3=2,无噪声),实际 {eco}'


def test_economy_marks_unknown_when_delta_none(tmp_path) -> None:
    """该轮有 sell_income 行但 gold_delta=None → 计 0 并标 `?`(有偏可辨)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323b', 'A8')
    rec.record_decision('w323b', 'A8',
                        GameState(gold=10, round_num=2, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0)])
    with _recorder_as_module(tmp_path):
        cw_telemetry._CURRENT_RUN_ID = 'w323b'
        try:
            record_sell_income(GameState(gold=10, round_num=2, plane=1),
                               slot=0, char_id='青雀', gold_before=10, gold_after=None)
        finally:
            cw_telemetry._CURRENT_RUN_ID = 'w323-run'
    eco = query_economy(tmp_path, 'w323b')
    assert any('卖+0?' in ln for ln in eco), f'delta=None 应计 0 并标 ?,实际 {eco}'


def test_economy_falls_back_to_action_income_legacy(tmp_path) -> None:
    """旧数据/sim 局(无 exogenous 行):回退 actions 的 SellBench.income 口径
    (W69 锁 3 语义不回归,且不误标卖回 `?`)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323c', 'A8')
    rec.record_decision('w323c', 'A8',
                        GameState(gold=50, round_num=1, plane=1),
                        'c', {}, {}, [SellBench(bench_idx=0, income=6)])
    eco = query_economy(tmp_path, 'w323c')
    assert any('卖+6' in ln and '卖+6?' not in ln for ln in eco), \
        f'旧口径卖入应保留且不标 ?,实际 {eco}'


def test_economy_no_sell_round_unchanged(tmp_path) -> None:
    """无卖轮:不显示卖回格(与既有『无卖局不显示』锁一致,不回归)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('w323d', 'A8')
    rec.record_decision('w323d', 'A8',
                        GameState(gold=30, round_num=1, plane=1),
                        'c', {}, {}, [])
    eco = query_economy(tmp_path, 'w323d')
    assert len(eco) == 1 and '卖+' not in eco[0], f'无卖轮不应出现卖回格,实际 {eco}'
