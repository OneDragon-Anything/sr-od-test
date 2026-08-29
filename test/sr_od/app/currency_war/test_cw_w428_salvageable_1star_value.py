"""P10④ 出口财富口径:遥测「可回收 1★ 值」字段锁(读端零行为)。

锁面(docs/game/currency_war/research/proofs/p10-exit-gold-floor.md
§④ 与「对实现的检验点」3;防「袋穷板富」误读的判读数据面):
- 计算式:``salvageable_1star_value`` = 手上(deployed+bench)全部 1★ 件
  Σ cost——单价表单一源 ``cw_state.sell_refund``(1★ 全额退、无手续费),
  费用单一源 ``cw_state._bench_char_cost``(未知身份 → 3 保守估);
  2★+ 不算(沉没通道),空槽跳过;
- 遥测挂载:``DecisionTrace.handoff`` 落账行富化该字段(仅 production
  decisions 行;handoff 缺省 None 时无键,sim p2_handoff 键集不变);
- 零行为锚:纯函数只读 state(state 调用前后逐字段不变)。
注册表费用锚:cw_chars——藿藿=1 / 爻光=1 / 阮·梅=2 / 丹恒·饮月=2。
"""
from __future__ import annotations

import json
import logging

from sr_od.application.currency_war import cw_telemetry
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.decision_v2.handoff import (
    handoff_snapshot,
)

logging.disable(logging.CRITICAL)


def _bench(name: str, faction: str = '仙舟', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 1, 'gold': 3, 'level': 6,
            'board': {}, 'bench': [], 'shop': [], 'hp': 55,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def test_formula_1star_sum_of_costs() -> None:
    """1★ 件值 = Σ 注册表费用:1+1+2+2=6(藿藿/爻光=1,阮·梅/丹恒·饮月=2)。"""
    st = _state(
        deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                  _bench('阮·梅', slot=2)],
        bench=[_bench('爻光', slot=1)])
    assert cw_telemetry.salvageable_1star_value(st) == 1 + 2 + 2 + 1


def test_formula_excludes_2star_and_none_slots() -> None:
    """2★+ 不算(沉没通道);None 空槽跳过;纯 1★ bench 也计入。"""
    st = _state(
        deployed=[None, _bench('爻光', slot=1), _bench('藿藿', slot=2, star=2),
                  _bench('丹恒·饮月', slot=3, star=3)],
        bench=[None, None, _bench('阮·梅', slot=4)])
    assert cw_telemetry.salvageable_1star_value(st) == 1 + 2   # 爻光 + 阮·梅


def test_formula_unknown_char_falls_back_to_3() -> None:
    """char_id 未识别 → _bench_char_cost 兜 3(中费保守估)。"""
    st = _state(bench=[_bench('不存在角色', slot=0)])
    assert cw_telemetry.salvageable_1star_value(st) == 3


def test_formula_empty_hand() -> None:
    """空手(全 None)→ 0。"""
    st = _state(deployed=[None], bench=[None])
    assert cw_telemetry.salvageable_1star_value(st) == 0


def test_pure_function_does_not_mutate_state() -> None:
    """零行为锚:只读 state——deployed/bench/gold/board 调用前后不变。"""
    dep = [_bench('藿藿', slot=0), None, _bench('阮·梅', slot=2, star=2)]
    bench = [_bench('爻光', slot=1)]
    st = _state(deployed=dep, bench=bench)
    before = ([list(d.__dict__.items()) if d else None for d in dep],
              [list(b.__dict__.items()) if b else None for b in bench],
              st.gold, dict(st.board))
    cw_telemetry.salvageable_1star_value(st)
    after = ([list(d.__dict__.items()) if d else None for d in dep],
             [list(b.__dict__.items()) if b else None for b in bench],
             st.gold, dict(st.board))
    assert before == after


def test_handoff_row_carries_salvageable_value(tmp_path) -> None:
    """遥测挂载:P2 首轮 handoff 行富化字段且与纯函数同值;
    无 handoff 行(None)不冒键;快照本体键集不变。"""
    rec = cw_telemetry.TelemetryRecorder(tmp_path, enabled=True)
    st = _state(deployed=[_bench('藿藿', slot=0), _bench('阮·梅', slot=1)],
                bench=[_bench('爻光', slot=1)],
                shop=[ShopCard(x=0, name='藿藿', faction='仙舟', cost=1)])
    sess = StrategySession()
    snap = handoff_snapshot(st, sess)
    rec.record_decision('run_w428', 'A4', st, '', {}, {}, [],
                        extra={'handoff': snap.as_dict()})
    row = json.loads(
        (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
        .strip().splitlines()[-1])
    assert row['handoff']['salvageable_1star_value'] \
        == cw_telemetry.salvageable_1star_value(st) == 1 + 2 + 1
    # 快照本体键集不变(sim p2_handoff 同构不受富化影响)
    assert 'salvageable_1star_value' not in snap.as_dict()
    # 无 handoff 行:字段无处挂,不冒键
    rec.record_decision('run_w428', 'A4', st, '', {}, {}, [])
    row2 = json.loads(
        (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
        .strip().splitlines()[-1])
    assert row2['handoff'] is None
