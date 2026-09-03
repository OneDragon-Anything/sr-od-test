"""策略失活探针判据锁(dd-031 判据重写批)。

被测生产面:
- 运行探针:operations/cw_loop.py 备战入口失活检查(ADR-0342 接线)。
- 判据单一源:telemetry/query.py 的 _row_heartbeat / strategy_round_live /
  check_strategy_live_streak。
- 消费接线:sim/ledger_hooks.run_checks_on_replay(离线检查网)。

dd-031 定谳(g_20260904_022537 / g_20260904_010335 两局误杀):旧判据
「该轮无 strategy_id 决策行 = 策略失活」把 mandate 合法跳过开店的健康局
误杀(整轮只有载体行,sid='');新判据 = 策略心跳(sid 行或载体行,任一
即活),探针辖域收敛为「外环停转」(整轮零心跳行)。真死形态、误杀形态、
离线检查网三面同源锁定,防两处判据漂移。

⚠️ 本文件从 test_cw_intention_gate.py(legacy_baseline 桶)拆出:这些锁
钉的是**生产运行行为**(探针 + 离线检查),不随 decision_v2 旧核退役,
必须进常规快速集。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sr_od.application.currency_war.sim import ledger_hooks
from sr_od.application.currency_war.telemetry import query, recorder, state


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


@pytest.fixture(autouse=True)
def _rec(tmp_path, monkeypatch):
    rec = recorder.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    monkeypatch.setattr(state, '_RECORDER', rec)
    query._STRATEGY_LIVE_CACHE.clear()
    yield rec
    query._STRATEGY_LIVE_CACHE.clear()


# ===== 心跳判定核心(单一源 _row_heartbeat)=====

def test_heartbeat_row_criterion() -> None:
    """心跳 = sid 非空或 actions 非空,二者缺一即哑行。"""
    hb = query._row_heartbeat
    assert hb({'strategy_id': 'mandate_v1', 'actions': []}) is True
    assert hb({'strategy_id': '', 'actions': [{'__type__': 'StartBattle'}]}) is True
    assert hb({'strategy_id': '', 'actions': []}) is False
    assert hb({}) is False
    # 缺键容忍(actions None/缺键按空)
    assert hb({'strategy_id': None}) is False


# ===== 回归锁①:g_20260904_022537 r7/r8 误杀形态 =====

def test_mandate_skip_shop_round_is_live() -> None:
    """误杀形态(022537 r7/r8 / 010335 r8/r9 实录形状):整轮只有载体行
    (sid='' + StartBattle 等动作)→ 活。mandate 三开店站全关时合法跳过
    开店,sid 行唯一写点在店内决策,无 sid 行 ≠ 策略死亡。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, [
        {'run_id': 'm1', 'plane': 1, 'round_num': 7, 'strategy_id': '',
         'actions': [{'__type__': 'StartBattle'}]},
    ])
    assert query.strategy_round_live('m1', (1, 7)) is True


def test_supply_quiet_round_isolated_no_false_stop() -> None:
    """补给轮形态(022537/010335 r5 实录:决策行存在但零动作零 sid)
    → 该轮非心跳(失活候选),但被前后健康轮隔离,连击不成立——
    两个误杀局的 r5 都形如此,探针在整局上不得判死。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    rows = []
    for rn in range(1, 9):
        if rn == 5:
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': '', 'actions': []})
        elif rn == 7:
            # 022537 r7 形态:mandate 跳过开店,仅载体行
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': '',
                         'actions': [{'__type__': 'StartBattle'}]})
        else:
            rows.append({'run_id': 'm2', 'plane': 1, 'round_num': rn,
                         'strategy_id': 'mandate_v1', 'actions': []})
    _write_rows(f, rows)
    for rn in range(1, 9):
        if rn == 5:
            assert query.strategy_round_live('m2', (1, rn)) is False
        else:
            assert query.strategy_round_live('m2', (1, rn)) is True
    # 整局连击走查(022537 逐轮 replay):连击永不达 2,不触发早停
    streak = 0
    for rn in range(1, 9):
        streak = query.dead_streak_transition(
            (1, rn), (1, rn + 1), streak,
            query.strategy_round_live('m2', (1, rn)))
    assert streak < 2


# ===== 回归锁②:真死形态(外环停转)必判死 =====

def test_outer_loop_dead_still_stops() -> None:
    """真死形态:整轮零心跳行(sid 空且动作空)连续 ≥2 → 连击成立,
    loop 侧停局线(阈值 2,同 ADR-0342 原响应性)。哑行(观测错误行)
    不算心跳——兜底/异常留证行救不活停转判定。"""
    f = Path(str(state._RECORDER.replay_dir) + '/decisions.jsonl')
    _write_rows(f, [
        {'run_id': 'dead1', 'plane': 1, 'round_num': 3,
         'strategy_id': '', 'actions': []},
        {'run_id': 'dead1', 'plane': 1, 'round_num': 4,
         'strategy_id': '', 'actions': []},
    ])
    assert query.strategy_round_live('dead1', (1, 3)) is False
    assert query.strategy_round_live('dead1', (1, 4)) is False
    # 连击状态机逐轮结算(与 cw_loop 接线同式:进入新轮结算上一轮)
    streak = 0
    for prev, cur in (((1, 2), (1, 3)), ((1, 3), (1, 4)), ((1, 4), (1, 5))):
        streak = query.dead_streak_transition(
            prev, cur, streak, query.strategy_round_live('dead1', prev))
    assert streak >= 2


def test_strategy_round_live_with_cache(tmp_path) -> None:
    """mtime 缓存:写入后重查可见;不同 run 互不串。"""
    f = tmp_path / 'decisions.jsonl'
    _write_rows(f, [
        {'run_id': 'r1', 'plane': 1, 'round_num': 1, 'strategy_id': ''},
        {'run_id': 'r1', 'plane': 1, 'round_num': 2, 'strategy_id': 'decision_v2'},
        {'run_id': 'r2', 'plane': 1, 'round_num': 1,
         'strategy_id': '', 'actions': [{'__type__': 'StartBattle'}]},
    ])
    assert query.strategy_round_live('r1', (1, 1)) is False
    assert query.strategy_round_live('r1', (1, 2)) is True
    assert query.strategy_round_live('r2', (1, 1)) is True
    # 追加(新 mtime)后缓存失效重扫:r1 r1 也变 live
    _write_rows(f, [{'run_id': 'r1', 'plane': 1, 'round_num': 1,
                     'strategy_id': 'decision_v2'}])
    assert query.strategy_round_live('r1', (1, 1)) is True


def test_dead_streak_transition_state_machine() -> None:
    """同 key 重入不计数;换 key 时 live 复位 / dead 递增。"""
    t = query.dead_streak_transition
    # 首轮(prev None):不结算
    assert t(None, (1, 1), 0, True) == 0
    assert t(None, (1, 1), 2, False) == 2
    # 同轮重入(过渡帧/重试):不结算
    assert t((1, 1), (1, 1), 1, False) == 1
    # 换轮:live 复位
    assert t((1, 1), (1, 2), 1, True) == 0
    # 换轮:dead 递增
    assert t((1, 1), (1, 2), 0, False) == 1
    assert t((1, 2), (1, 3), 1, False) == 2   # 连击到 2 = loop 侧停局线


# ===== 回归锁③:离线检查网同源同步 =====

def test_check_strategy_live_streak_same_criterion() -> None:
    """sim 检查网 check_strategy_live_streak 与运行探针同源(_row_heartbeat):
    误杀形态(载体行健康局)不报;哑行停转段必报。"""
    c = query.check_strategy_live_streak
    # 误杀形态(022537 形状:r5 补给哑行孤立,r7/r8 载体行)→ 不报
    ok_rows = []
    for rn in range(1, 9):
        if rn == 5:
            ok_rows.append({'plane': 1, 'round_num': rn,
                            'strategy_id': '', 'actions': []})
        elif rn == 7:
            ok_rows.append({'plane': 1, 'round_num': rn, 'strategy_id': '',
                            'actions': [{'__type__': 'StartBattle'}]})
        else:
            ok_rows.append({'plane': 1, 'round_num': rn,
                            'strategy_id': 'mandate_v1', 'actions': []})
    assert c(ok_rows) == []
    # 真死形态:哑行连续 ≥ 阈值 3 → 报
    dead_rows = [{'plane': 1, 'round_num': rn, 'strategy_id': '', 'actions': []}
                 for rn in range(1, 10)]
    v = c(dead_rows)
    assert v and '9 轮' in v[0] and 'dd-031' in v[0]
    # 孤立 2 轮哑行(< 阈值 3)不报
    short = [{'plane': 1, 'round_num': rn, 'strategy_id': '', 'actions': []}
             for rn in (1, 2)] + [
        {'plane': 1, 'round_num': rn, 'strategy_id': 'mandate_v1', 'actions': []}
        for rn in (3, 4)]
    assert c(short) == []
    # P2 哑行不辖(只辖 P1)
    p2 = [{'plane': 2, 'round_num': rn, 'strategy_id': '', 'actions': []}
          for rn in range(1, 5)]
    assert c(p2) == []


def test_run_checks_reports_dead_run(tmp_path) -> None:
    """run_checks_on_replay 对停转局出报警行(不被判栈跳过)。

    夹具用真死形态(哑行):旧夹具的 EnsureShopClosed 载体行在新判据下
    是心跳行(不报),语义随 dd-031 判据重写同步换形。"""
    _write_rows(tmp_path / 'decisions.jsonl', [
        {'run_id': 'dead2', 'plane': 1, 'round_num': rn,
         'strategy_id': '', 'actions': []}
        for rn in range(1, 6)
    ])
    _write_rows(tmp_path / 'outcomes.jsonl', [
        {'run_id': 'dead2', 'plane': 1, 'round_num': rn} for rn in range(1, 6)
    ])
    lines = ledger_hooks.run_checks_on_replay(tmp_path, recent=5)
    assert any('[策略失活]' in x and 'dead2' in x for x in lines), lines
