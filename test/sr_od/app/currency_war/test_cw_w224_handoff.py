"""ADR-0399:P2 承接快照 Phase 0(纯观测零行为)单帧锁。

锁面(设计件 08_p2_handoff §4.2 Phase 0 / §4.1 验收判据):
- 快照纯函数七维字段正确性(state 单帧;session 可缺省=离线回放形态);
- 档位边界例(hp 切点 20/50、板面维 engines/core2 切点,含 run 26/28
  两局主罚维形态——run28=hp 维归零 / run26=星级维归零而 hp 维健康);
- decide_prep 挂载(plane>=2 本位面首帧算一次写 session.v3_handoff;
  同位面不覆写;plane=1 不触发);
- sim 侧 SimResult.p2_handoff(planes=2 进场有快照/同 seed 确定性/
  planes=1 恒 None);
- 生产遥测 DecisionTrace.handoff(extra 透传;缺省 None 不破坏 schema)。
n 取断言成立最小值;sim 结构断言用 fallback 池(README 纪律)。
"""
from __future__ import annotations

import logging

import pytest

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.handoff import (
    HANDOFF_BOARD_CORE2_CUTS,
    HANDOFF_BOARD_ENGINE_CUTS,
    HANDOFF_HP_CUTS,
    HandoffSnapshot,
    handoff_hp_tier,
    handoff_snapshot,
    handoff_tier,
)
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)


@pytest.fixture(autouse=True)
def _quiet_logging():
    """本模块测试期间静音日志(测试域收口)。

    进程级 logging.disable 是全局态:pytest 在收集期 import 本模块,模块级
    调用即对整个测试会话生效,会静默饿死其他测试依赖日志落盘的断言
    (判例:test_log_utils_utf8_rollover_continuity 因此 FileNotFoundError)。
    收口为 autouse fixture:进入本模块测试时禁用,退出时还原原级别。
    """
    prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(prev)


_SNAP_KEYS = {'hp', 'engines', 'form_score', 'core2_count', 'star_sum',
              'level', 'deployed_n', 'gold', 'locked', 'locked_comp',
              'hoard_n', 'hp_tier', 'board_tier', 'tier'}


def _bench(name: str, faction: str = '仙舟', slot: int = 0,
           star: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, faction=faction, star=star)


def _state(**kw) -> GameState:
    base = {'plane': 2, 'round_num': 1, 'gold': 40, 'level': 6,
            'board': {}, 'bench': [], 'shop': [], 'hp': 55,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _sess(**kw) -> StrategySession:
    from sr_od.application.currency_war.kernel.cw_intention import IntentionState
    s = StrategySession()
    s.v2_state = ('economy', False, False, 0, 0, 0, 0, 0)
    ist = IntentionState()
    ist.phase = kw.pop('ist_phase', 'unlocked')
    ist.locked_comp = kw.pop('locked_comp', '')
    s.v3_intention = ist
    for k, v in kw.items():
        setattr(s, k, v)
    return s


# ---------- ① 快照纯函数(单帧) ----------

def test_snapshot_fields_single_frame() -> None:
    """七维向量字段正确性:仙舟三人组(一引擎)上场,其一 2★。"""
    st = _state(
        hp=55, gold=40, level=6,
        deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                  _bench('爻光', slot=2, star=2), _bench('阮·梅', slot=3)])
    sess = _sess(ist_phase='locked', locked_comp='仙舟回路',
                 v3_hoard=HoardTarget(
                     frozenset({'藿藿', '丹恒·饮月'}), frozenset(), 'locked'))
    s = handoff_snapshot(st, sess)
    assert s.hp == 55 and s.gold == 40 and s.level == 6
    assert s.deployed_n == 4
    assert s.engines >= 1            # 仙舟 3 人 → 至少一体系(_engines_count)
    assert s.core2_count == 1        # 仅爻光 2★
    assert s.star_sum == 1 + 1 + 2 + 1
    assert s.locked and s.locked_comp == '仙舟回路'
    assert s.hoard_n == 2
    assert 0.0 <= s.form_score <= 1.0
    assert set(s.as_dict()) == _SNAP_KEYS


def test_snapshot_offline_without_session() -> None:
    """session 缺省 = 离线回放形态(锁线/囤货维不可算 → 缺省值不炸)。"""
    st = _state(deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                          _bench('爻光', slot=2)])
    s = handoff_snapshot(st)
    assert s.locked is False and s.locked_comp == '' and s.hoard_n == 0
    assert s.engines == 1 and s.deployed_n == 3
    # 纯函数契约:不写 state
    assert st.gold == 40 and st.hp == 55


# ---------- ② 档位边界例 ----------

def test_hp_tier_boundaries() -> None:
    """hp 维切点 (20,50) 边界:切点值落低档(超切点数口径)。"""
    assert HANDOFF_HP_CUTS == (20, 50)
    assert handoff_hp_tier(1) == 0    # run 28 型(hp=1 归零维)
    assert handoff_hp_tier(20) == 0
    assert handoff_hp_tier(21) == 1
    assert handoff_hp_tier(50) == 1
    assert handoff_hp_tier(51) == 2   # run 26 型(hp=64 健康)


def test_board_tier_and_overall() -> None:
    """板面维 = min(engines 档, core2 档);总档位 = min(hp, 板面)。

    run 26 型回验形态:hp 维健康(64→tier2)但星级维归零(core2=0)
    → 板面档 0、总档 0(主罚维=板面/星级);run 28 型:hp 维归零
    (hp=1→tier0)为主罚维。两局都被判「承接不足」且可指认主罚维。
    """
    assert HANDOFF_BOARD_ENGINE_CUTS == (1,)
    assert HANDOFF_BOARD_CORE2_CUTS == (1,)
    run26 = HandoffSnapshot(hp=64, engines=2, core2_count=0, star_sum=6,
                            level=6, deployed_n=6, gold=75, locked=True)
    assert handoff_hp_tier(run26.hp) == 2
    assert run26.as_dict()['board_tier'] == 0
    assert handoff_tier(run26) == 0     # 承接不足,罚在板面(星级)维
    run28 = HandoffSnapshot(hp=1, engines=1, core2_count=0, star_sum=6,
                            level=6, deployed_n=6, gold=86, locked=True)
    assert handoff_hp_tier(run28.hp) == 0
    assert handoff_tier(run28) == 0     # 罚在 hp 维
    # 健康高端:hp>50 且板面 ≥1 → 总档位仍 1(板面维单切点封顶 1,
    # 总档位实际两档——ADR-0399 标定结论;hp 高端区分度归 hp_tier)
    hi = HandoffSnapshot(hp=69, engines=1, core2_count=1, star_sum=7,
                         level=6, deployed_n=6, gold=78, locked=True)
    assert handoff_tier(hi) == 1 and handoff_hp_tier(hi.hp) == 2


# ---------- ③ decide_prep 挂载 ----------

def test_decide_prep_mounts_snapshot_once_per_plane() -> None:
    """plane>=2 本位面首帧算一次写 session.v3_handoff;同位面不覆写。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(deployed=[_bench('藿藿', slot=0), _bench('丹恒·饮月', slot=1),
                          _bench('爻光', slot=2, star=2)])
    strat.decide_prep(st, sess, None)
    assert sess.v3_handoff is not None
    first = sess.v3_handoff
    assert first.hp == 55 and first.deployed_n == 3 and first.core2_count == 1
    assert sess.v3_handoff_plane == 2
    # 同位面第二轮:不覆写(同一对象——位面首帧一次性采样)
    st2 = _state(round_num=2, hp=40, gold=30,
                 deployed=[_bench('藿藿', slot=0)])
    strat.decide_prep(st2, sess, None)
    assert sess.v3_handoff is first


def test_decide_prep_no_snapshot_on_plane1() -> None:
    """plane=1 不触发(Phase 0 观测只辖 P2 承接;P1 零漂移的结构面)。"""
    strat = DecisionV2Strategy()
    sess = _sess()
    st = _state(plane=1, round_num=5)
    strat.decide_prep(st, sess, None)
    assert sess.v3_handoff is None


# ---------- ④ sim 侧观测 ----------

def test_sim_p2_handoff_field() -> None:
    """SimResult.p2_handoff:planes=2 进场有快照/同 seed 确定/
    planes=1 恒 None。"""
    r = engine_p1.simulate_p1(0, pool='fallback', planes=2)
    if r.p2_entered:
        assert isinstance(r.p2_handoff, dict)
        assert set(r.p2_handoff) == _SNAP_KEYS
        r2 = engine_p1.simulate_p1(0, pool='fallback', planes=2)
        assert r2.p2_handoff == r.p2_handoff   # 同 seed 确定性
    else:
        assert r.p2_handoff is None
    r1 = engine_p1.simulate_p1(0, pool='fallback', planes=1)
    assert r1.p2_handoff is None and r1.p2_entered is False


def test_sim_replay_entry_snapshot() -> None:
    """案 b 臂(真值进场态)同样经首轮 decide_prep 采样快照。"""
    entry = engine_p2.P2ReplayEntry(
        hp=64, gold=75, level=6, board={'仙舟': 3},
        deployed=[{'char_id': '藿藿', 'faction': '仙舟', 'star': 1},
                  {'char_id': '丹恒·饮月', 'faction': '仙舟', 'star': 1},
                  {'char_id': '爻光', 'faction': '仙舟', 'star': 2}])
    r = engine_p2.simulate_p2_replay_entry(entry, 0, pool='fallback')
    assert r.p2_entered
    h = r.p2_handoff
    assert h['hp'] == 64 and h['deployed_n'] == 3
    # gold 含 P2 r1 轮收入(75 + 11;快照时点=首轮 decide_prep 入口,
    # 与生产/标定语料同口径——见 handoff_snapshot 时点语义注)
    assert h['gold'] == 86
    assert h['core2_count'] == 1 and h['hp_tier'] == 2


# ---------- ⑤ 生产遥测 ----------

def test_decision_trace_handoff_field(tmp_path) -> None:
    """DecisionTrace.handoff:extra 透传 dict;缺省 None(schema 兼容)。

    P10④ 挂账落码后读端富化:落账行在快照 dict 副本上补
    ``salvageable_1star_value``(计算式锁在 test_cw_w428_salvageable_
    1star_value.py);快照本体 as_dict() 键集不变(sim 同构不受影响)。
    """
    rec = recorder.TelemetryRecorder(tmp_path, enabled=True)
    st = _state(shop=[ShopCard(x=0, name='藿藿', faction='仙舟', cost=1)])
    sess = _sess()
    snap = handoff_snapshot(st, sess)
    rec.record_decision('run_t', 'A4', st, '', {}, {}, [],
                        extra={'handoff': snap.as_dict()})
    line = (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
    import json
    row = json.loads(line.strip().splitlines()[-1])
    expect = dict(snap.as_dict())
    expect['salvageable_1star_value'] = row['handoff']['salvageable_1star_value']
    assert row['handoff'] == expect
    assert set(snap.as_dict()) == _SNAP_KEYS   # 快照本体键集不变
    # 缺省(旧调用形态):None 不破坏 schema
    rec.record_decision('run_t', 'A4', st, '', {}, {}, [])
    line = (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8')
    row2 = json.loads(line.strip().splitlines()[-1])
    assert row2['handoff'] is None


from sr_od.application.currency_war.sim import engine_p1, engine_p2
from sr_od.application.currency_war.telemetry import recorder
