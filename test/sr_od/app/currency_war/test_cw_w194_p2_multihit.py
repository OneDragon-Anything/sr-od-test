"""ADR-0378(W194)两件锁:[33] 稳态 LevelUp 多击组 + tracks 活引用深拷贝。

锁面:
- 稳态多击组(remediation.steady_state_levelup_group + arbiter
  ._steady_levelup_pass):稳态判据(cap 满 ∧ bench 方向件)发
  clicks_to_next_level 整组;boss/flag off/cap 未满/无方向件/
  已跨级/EV 拒各挡;arbiter 侧事务性重验(整组放弃计数)+ 每轮
  至多一组(轮键)+ 插入位(refresh 前);
- serialize_intention 深拷贝:dict/list 字段(tracks)快照语义
  (后续原地改写不污染已落账行);tuple 字段类型不漂移;
- sim 集成冒烟:planes=2 单局 v3_intention 全 JSON 可序列化
  (tracks 值为 dict 非 LineTrack)。

n 取断言成立最小值(README 纪律 7);不落盘。
"""
from __future__ import annotations

import dataclasses
import json
import logging

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    LineTrack,
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar, GameState
from sr_od.application.currency_war.cw_strategy import StrategySession
from sr_od.application.currency_war.telemetry.cw_telemetry import serialize_intention
from sr_od.application.currency_war.decision_v2.arbiter import (
    ArbiterResult,
    _steady_levelup_pass,
    arbitrate,
)
from sr_od.application.currency_war.kernel.cw_registry import (
    DEFAULT_REGISTRY,
)
from sr_od.application.currency_war.decision_v2.remediation import (
    steady_state_levelup_group,
)

logging.disable(logging.CRITICAL)

# 注入「press 通道关」注册表:press 通道已正式开臂(commit cb7688d4,
# press_channel_enabled 默认 True),同档/1费买改由 press_floor_exempt
# 前置臂授权。本文件锁的是 P2 核心首件门自身的辖域与轮计数,注入关臂
# 隔离该前置臂。
_REG_NO_PRESS = dataclasses.replace(DEFAULT_REGISTRY,
                                    press_channel_enabled=False)

_ENGINE = '希儿'          # engine_char_names 成员(_target_names 恒含)
_NON_TARGET = '散件'       # 注册表外名(不在目标集)


def _steady_state(level: int = 6, xp: int = 16, gold: int = 108,
                  node: str = 'battle') -> GameState:
    """[33] 稳态帧:cap=level 满员 + bench 躺方向件(run15 P2 型)。"""
    st = GameState()
    st.plane, st.level, st.gold, st.hp = 2, level, gold, 60
    st.node_type = node
    st.deployed = [BenchChar(slot=i + 1, char_id=f'c{i}', faction='仙舟')
                   for i in range(level)]
    st.bench[0] = BenchChar(slot=1, char_id=_ENGINE, faction='量子')
    st.xp_progress = (xp, {6: 40, 7: 52}.get(level, 40))
    return st


# ---------- 稳态多击组:构造判据 ----------

def test_steady_group_emits_clicks_to_next_level() -> None:
    """稳态帧:lv6 xp16/40 → 余 24 XP = 6 击,auth_basis 非空。"""
    sess = StrategySession()
    acts = steady_state_levelup_group(
        _steady_state().copy(), _steady_state(), sess, DEFAULT_REGISTRY)
    assert len(acts) == 6
    assert all(a.cost == 4 and a.auth_basis == 'pop_slot' for a in acts)


def test_steady_group_guards() -> None:
    """五路挡:flag off / P1 不辖 / cap 未满 / bench 无方向件
    / 已跨级。

    (旧「boss 轮不发」断言随 W255/ADR-0410 过期:boss 升级禁令删除,
    稳态组在 boss 轮改由 EV 总账裁决——boss 帧放行面见 test_cw_w255 锁
    与 ADR-0410 ②;其余守卫语义不变。)"""
    sess = StrategySession()
    st = _steady_state()
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  levelup_multihit_enabled=False)
    assert steady_state_levelup_group(
        st.copy(), st, sess, reg_off) == []          # flag off 回 W193 后
    p1 = _steady_state()
    p1.plane = 1
    assert steady_state_levelup_group(
        p1.copy(), p1, sess, DEFAULT_REGISTRY) == []  # P1 不辖(辙回:
    # 全位面泛化 n=300 引入 never2 9→10 回归;P1 已有补偿臂覆盖)
    not_full = _steady_state()
    not_full.deployed = not_full.deployed[:-1]
    assert steady_state_levelup_group(
        not_full.copy(), not_full, sess, DEFAULT_REGISTRY) == []  # [32](b)
    no_dir = _steady_state()
    no_dir.bench[0] = BenchChar(slot=1, char_id=_NON_TARGET, faction='?')
    assert steady_state_levelup_group(
        no_dir.copy(), no_dir, sess, DEFAULT_REGISTRY) == []
    crossed = _steady_state(xp=40)
    assert steady_state_levelup_group(
        crossed.copy(), crossed, sess, DEFAULT_REGISTRY) == []


def test_steady_group_ev_affordability_gate() -> None:
    """EV 总账拒:金 < n×总价(可负担性 after<0)→ 整组不发。"""
    sess = StrategySession()
    st = _steady_state(gold=20)      # 6 击 24 金 → after=-4
    assert steady_state_levelup_group(
        st.copy(), st, sess, DEFAULT_REGISTRY) == []


# ---------- 稳态多击组:arbiter 趟 ----------

def test_steady_pass_inserts_group_and_round_key() -> None:
    """arbiter 趟:组进 actions + 轮键置位(二次调用 no-op)+
    working 推进(金扣 24)。"""
    sess = StrategySession()
    st = _steady_state()
    res = ArbiterResult()
    wk = _steady_levelup_pass(st.copy(), st, sess, DEFAULT_REGISTRY, res)
    assert len(res.actions) == 6
    assert sess.v2_steady_lv_used
    assert wk.gold == st.gold - 24
    res2 = ArbiterResult()
    wk2 = _steady_levelup_pass(wk.copy(), st, sess, DEFAULT_REGISTRY, res2)
    assert res2.actions == [] and wk2.gold == wk.gold   # 轮键单组


def test_steady_pass_transactional_abandon() -> None:
    """事务性重验失败整组放弃:FORM 地板 20 下第 4 击(金 23→19
    <20)→ 放弃计数 + 无动作 + working 不动。"""
    sess = StrategySession()
    st = _steady_state(gold=35)       # 6 击 24 金:前 3 击过,第 4 击破地板
    res = ArbiterResult()
    wk = _steady_levelup_pass(st.copy(), st, sess, DEFAULT_REGISTRY, res)
    assert res.actions == []
    assert sess.v3_steady_lv_abandoned == 1
    assert wk.gold == st.gold


def test_steady_pass_inserts_before_refresh() -> None:
    """插入位:组插在已采纳 RefreshShop 之前(旧店段语义)。"""
    from sr_od.application.currency_war.kernel.cw_state import RefreshShop
    sess = StrategySession()
    st = _steady_state()
    res = ArbiterResult()
    res.actions = [RefreshShop(cost=2)]
    _steady_levelup_pass(st.copy(), st, sess, DEFAULT_REGISTRY, res)
    assert type(res.actions[0]).__name__ == 'LevelUp'
    assert type(res.actions[-1]).__name__ == 'RefreshShop'


def test_arbitrate_end_to_end_steady_group() -> None:
    """arbitrate 空候选直调:稳态组仍发(不依赖拒绝事件——Catch-22
    根治的构造性证明)。"""
    sess = StrategySession()
    st = _steady_state()
    res = arbitrate([], st, sess, DEFAULT_REGISTRY)
    lv = [a for a in res.actions if type(a).__name__ == 'LevelUp']
    assert len(lv) == 6


# ---------- tracks 活引用深拷贝 ----------

def test_serialize_intention_tracks_snapshot() -> None:
    """快照语义:serialize 后原地改 LineTrack/增删键,已落账 dict 不变。"""
    ist = IntentionState(phase='locked', locked_comp='x',
                         p1_pair=('仙舟', '列车同行'))
    ist.tracks['dot'] = LineTrack(miss_count=1, frozen_rounds=2)
    snap = serialize_intention(ist)
    # 深拷贝防线:后续原地改写不污染
    ist.tracks['dot'].miss_count = 99
    ist.tracks['dot'].frozen_rounds = 99
    ist.tracks['new'] = LineTrack()
    assert snap['tracks'] == {'dot': {'miss_count': 1, 'frozen_rounds': 2}}
    # tuple 字段不可变:类型不漂移(快照=原值)
    assert snap['p1_pair'] == ('仙舟', '列车同行')


def test_serialize_intention_json_safe() -> None:
    """tracks 值为纯 dict(JSON 可序列化——旧版 LineTrack 裸引用
    会让 json.dumps 抛 TypeError)。"""
    ist = IntentionState()
    ist.tracks['dot'] = LineTrack(miss_count=3)
    json.dumps(serialize_intention(ist))   # 不抛即过


def test_sim_p1_rows_tracks_unpolluted() -> None:
    """sim 集成:planes=2 单局,P1 行 v3_intention 全 JSON 可序列化
    且 tracks 为快照(修复前=活引用,P2 段原地改写污染 P1 行)。"""
    from sr_od.application.currency_war import cw_sim
    r = cw_sim.simulate_p1(3, pool='fallback', planes=2)
    p1_rows = [row for row in r.ledger if row.get('plane', 1) == 1]
    assert p1_rows
    for row in p1_rows:
        ist = row['v3_intention']
        if ist is None:
            continue
        json.dumps(ist)
        for track in (ist.get('tracks') or {}).values():
            assert isinstance(track, dict)   # 非 LineTrack 活引用


# ---------- 件3:P2 核心件首件同息档买入门(W183 方向②)----------

def _p2_sess(core: str = '姬子·启行') -> StrategySession:
    s = StrategySession()
    s.v3_mode = 'economy'
    s.v2_round_key = (2, 3)
    s.v2_round_p2_core = 0
    s.v3_core_names = {core}
    return s


def _p2_state(gold: int = 8, level: int = 6) -> GameState:
    """P2 穷轮帧(W194 探针形态:HOARD 金<50,核心 3费在店)。"""
    st = _steady_state(level=level, gold=gold)
    st.bench[0] = None
    return st


def _core_cand(name: str = '姬子·启行', cost: int = 3) -> object:
    from sr_od.application.currency_war.kernel.cw_state import BuyCard, ShopCard
    from sr_od.application.currency_war.decision_v2.candidates import (
        Candidate,
    )
    return Candidate(
        action=BuyCard(ShopCard(name=name, faction='列车同行',
                                cost=cost, x=0, star=1), reason=''),
        tag='line_carry', source='shop')


def test_p2_core_firstpiece_exempt_passes() -> None:
    """主锁:P2 金 8 买 3费核心首件 → 同息档(8→5)放行 + auth trace。"""
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _p2_core_firstpiece_exempt as ex,
    )
    sess = _p2_sess()
    st = _p2_state(gold=8)
    auth: dict = {}
    assert ex(_core_cand(), st.copy(), st, sess, DEFAULT_REGISTRY, auth)
    assert 'p2_core' in auth


def test_p2_core_firstpiece_guards() -> None:
    """六路挡:P1 / 非核心 / 已持有(working)/ 跨息档 / flag off /
    单轮上限耗尽 / boss 轮。"""
    from sr_od.application.currency_war.decision_v2.arbiter import (
        _p2_core_firstpiece_exempt as ex,
    )
    sess = _p2_sess()
    st = _p2_state(gold=8)
    p1 = _p2_state(gold=8)
    p1.plane = 1
    assert not ex(_core_cand(), p1.copy(), p1, sess, DEFAULT_REGISTRY)
    assert not ex(_core_cand('散件'), st.copy(), st, sess,
                  DEFAULT_REGISTRY)
    owned = st.copy()
    owned.bench[0] = BenchChar(slot=1, char_id='姬子·启行',
                               faction='列车同行')
    assert not ex(_core_cand(), owned, st, sess, DEFAULT_REGISTRY)
    assert not ex(_core_cand(cost=5), _p2_state(gold=12).copy(),
                  _p2_state(gold=12), sess, DEFAULT_REGISTRY)  # 12→7 跨档
    reg_off = dataclasses.replace(DEFAULT_REGISTRY,
                                  p2_core_firstpiece_enabled=False)
    assert not ex(_core_cand(), st.copy(), st, sess, reg_off)
    capped = _p2_sess()
    capped.v2_round_p2_core = 1
    assert not ex(_core_cand(), st.copy(), st, capped, DEFAULT_REGISTRY)
    boss = _p2_state(gold=8)
    boss.node_type = 'boss'
    assert not ex(_core_cand(), boss.copy(), boss, sess, DEFAULT_REGISTRY)


def test_p2_core_firstpiece_arbitrate_counter() -> None:
    """端到端:arbitrate 采纳后 session.v2_round_p2_core 计数(单轮上限
    数据源)+ 第二笔同轮拒。"""
    sess = _p2_sess()
    st = _p2_state(gold=8)
    st.shop = []
    cand = _core_cand()
    scored = [(cand, 5.0, {})]
    res = arbitrate(scored, st, sess, _REG_NO_PRESS)
    assert len(res.actions) == 1
    assert sess.v2_round_p2_core == 1
    # 同轮第二笔(跨档外的同档帧也拒——上限耗尽)
    res2 = arbitrate([(cand, 5.0, {})], st, sess, _REG_NO_PRESS)
    assert res2.actions == []
