# -*- coding: utf-8 -*-
"""经济冻结型败局三病灶修复锁(经济冻结批)。

设计出处:实机局复盘 g_20260904_031925 / g_20260904_042657 定谳的三病灶
(目标空窗 → 决策引擎全停;posture 接而不用;P2 选线绕过 weak_planes),
修法与证据链见 `.debug/temp/currency_war/economic_freeze_fix/REPORT.md`
与各被测函数 docstring 引注。锁的是策略意图(目标不空窗/守卫字段必须
置位/弱面线不进候选),不锁具体发牌。

四个回归锁:
① r7-r9 形态(P1 配方对退场 + P2 开局)目标不空窗;
② posture='level' 未兑现 → posture_unfulfilled 置位(带帧级复位);
③ weak_planes 含当前位面的线不进锁线候选(信号面与强制 assignment 面);
④ 断供驱逐可逆(供给再现撤销驱逐,单向驱逐=空窗根)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sr_od.application.currency_war.data.cw_chars import CHARACTERS
from sr_od.application.currency_war.decision.cw4 import entry
from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)
from sr_od.application.currency_war.kernel import cw_intention
from sr_od.application.currency_war.kernel.cw_comps import get_comp
from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    update_intention,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    LevelUp,
    OpenShop,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)


def _bc(name: str, slot: int = 0) -> BenchChar:
    ch = CHARACTERS[name]
    return BenchChar(slot=slot, char_id=name,
                     faction=(ch.factions or ['?'])[0])


def _state(**kw) -> GameState:
    base = {'plane': 1, 'round_num': 7, 'gold': 53, 'level': 5,
            'board': {}, 'bench': [], 'shop': [], 'hp': 76,
            'deployed': []}
    base.update(kw)
    return GameState(**base)


def _obs(state: GameState) -> SimpleNamespace:
    # bench_chars/deployed_chars 口径=占用件(生产 obs 契约;GameState
    # 槽表含 None 占位,观察面滤空)。
    return SimpleNamespace(boxes=(), tomes=(), spheres=(),
                           event_overlay='',
                           bench_chars=tuple(
                               b for b in state.bench if b is not None),
                           deployed_chars=tuple(
                               d for d in state.deployed if d is not None),
                           deploy_vacancy=0, state=state)


def _sess() -> StrategySession:
    s = StrategySession()
    s.v3_intention = IntentionState()
    return s


# ===== ① r7-r9 形态:目标不空窗(P1 配方对退场 + P2 开局移交) =====

def test_p1_evicted_pair_still_materializes_target() -> None:
    """P1 配方对退场帧(断供驱逐后重派生为空,r7 形态):update_target
    必须按 p1_early_pair 无门槛方向物化伪 comp,目标不得为 None——
    旧形态 None → 部署/评分/准备域引擎全盲,0 买 0 刷经济冻结
    (g_20260904_042657 p1r7-r9)。"""
    strat = DecisionV2Strategy()
    sess = StrategySession()
    ist = IntentionState()
    ist.p1_pair = ()
    ist.pair_evicted = {'列车同行', '持续伤害'}
    sess.v3_intention = ist
    sess.v3_intention_key = (1, 7)          # = state 轮键 → 跳过状态机驱动
    st = _state(round_num=7)
    strat.update_target(st, sess, None)
    assert sess.target_comp is not None, \
        'P1 配方对退场帧目标不得为 None(目标空窗=经济冻结根)'
    assert sess.target_comp.name.startswith('过渡配方·')


def test_prep_fallback_keeps_engine_alive_without_target() -> None:
    """target_comp=None 帧,准备域 K 空窗回退(与商店域同源)给出方向
    成员 ⇒ M2 有缺口可买,发射 OpenShop 意图——引擎不得只剩 M7 空转。"""
    st = _state(bench=[_bc('卡芙卡', slot=1)])
    sess = _sess()
    out = entry.emit(_obs(st), SimpleNamespace(), sess, None)
    assert any(isinstance(e.action, OpenShop) for e in out), \
        '目标空窗帧必须有方向驱动的开店意图(引擎非空转)'
    assert sess.cw4_counters.get('prep_k_fallback_p1_lock_band', 0) >= 1


def test_p2_handoff_locks_non_weak_plane_target() -> None:
    """P2 开局 unlocked 帧(配方锁已退场)必须强制 assignment 出目标:
    phase=locked 且锁中线不是本位面弱面线——目标移交不空窗
    (g_20260904_042657 P2r1 旧形态锁 DOT队=P2 弱面死路)。"""
    st = _state(plane=2, round_num=1, bench=[_bc('卡芙卡', slot=1)],
                level=6)
    ist = update_intention(st, IntentionState())
    assert ist.phase == 'locked', 'P2 开局 unlocked 必须强制 assignment 目标'
    comp = get_comp(ist.locked_comp)
    assert comp is not None
    assert 2 not in (comp.weak_planes or ()), \
        f'P2 移交不得选本位面弱面线:{ist.locked_comp}'
    assert ist.locked_comp != 'DOT队', \
        'DOT队(注册表自注 weak_planes=(2,))不得在 P2 被锁'


# ===== ② posture 接而不用:授权未兑现必须显式置位 =====

def _emit_with_posture(monkeypatch, spend_mode: str,
                       state: GameState) -> tuple[list, StrategySession]:
    from sr_od.application.currency_war.kernel import cw_economy
    monkeypatch.setattr(
        cw_economy, 'get_node_goal',
        lambda *a, **k: SimpleNamespace(spend_mode=spend_mode,
                                        target_level=6))
    sess = _sess()
    out = entry.emit(_obs(state), SimpleNamespace(), sess, None)
    return out, sess


def test_level_posture_unfulfilled_declared(monkeypatch) -> None:
    """posture='level'(授权升级)而发射序列无 LevelUp ⇒
    v3_posture_unfulfilled 显式置位(带原因分键+计数)——守卫字段
    接而不用=病灶②,g_20260904_042657 p1r7-r9 posture='level' 全程
    零 LevelUp 而 posture_unfulfilled 恒 None。"""
    st = _state(bench=[_bc('卡芙卡', slot=1)])
    out, sess = _emit_with_posture(monkeypatch, 'level', st)
    assert not any(isinstance(e.action, LevelUp) for e in out)
    un = sess.v3_posture_unfulfilled
    assert un is not None, 'level 授权未兑现必须置位 posture_unfulfilled'
    assert un['channel'] == 'levelup'
    assert un['reason'], '置位必须带未兑现原因(显式降级可归因)'
    assert un['action'] == 'downgrade'
    assert sess.cw4_counters.get('posture_unfulfilled_level', 0) >= 1


def test_posture_unfulfilled_frame_reset_and_negative(monkeypatch) -> None:
    """帧级复位+负例:interest 姿态(无升级授权)不置位,且上一帧残留
    声明必须在入口复位(禁跨帧滞留成假信号)。"""
    st = _state(bench=[_bc('卡芙卡', slot=1)])
    sess = _sess()
    sess.v3_posture_unfulfilled = {'stale': True}   # 上一帧残留
    _out, sess = _emit_with_posture(monkeypatch, 'interest', st)
    assert sess.v3_posture_unfulfilled is None, \
        '无授权帧不得留未兑现声明(帧级复位)'


# ===== ③ weak_planes 过滤:弱面线不进锁线候选 =====

def test_weak_plane_line_excluded_from_signal_lock() -> None:
    """回归锁(任务书口径):weak_planes 含当前位面的线不进锁线候选
    ——P2r1 卡芙卡(DOT队核心)可见,旧形态③信号绕过过滤锁出 DOT队;
    修后信号面被注册表自注过滤(单一源=Comp.weak_planes)。"""
    st = _state(plane=2, round_num=1, bench=[_bc('卡芙卡', slot=1)],
                level=6)
    assert 2 in (get_comp('DOT队').weak_planes or ()), '夹具前提'
    ist = update_intention(st, IntentionState())
    if ist.phase == 'locked':
        assert ist.locked_comp != 'DOT队'


# ===== ④ 断供驱逐可逆:供给再现撤销驱逐 =====

def test_pair_drought_eviction_reversible_on_supply() -> None:
    """驱逐的唯一证据=连续 N 轮不在在店供给面;成员重新在店 ⇒ 驱逐
    撤销(证据被驳)。单向驱逐=空窗根:g_20260904_042657 p1r7 起两
    体系永久出局、p1_pair 重派生为空。"""
    # 断供计数的供给面=在店(蓝图 §4.3-R3:到手资产不救供给)
    st = _state(round_num=8)
    st.shop = [SimpleNamespace(name='桑博')]
    ist = IntentionState()
    ist.p1_pair = ('列车同行', '持续伤害')
    ist.pair_evicted = {'列车同行', '持续伤害'}
    ist = update_intention(st, ist)
    assert '持续伤害' not in ist.pair_evicted, \
        '体系成员(桑博=持续伤害)重新在店必须撤销驱逐(驱逐可逆)'
    assert '列车同行' in ist.pair_evicted, '对照:未供体系维持驱逐'


def test_k_empty_window_fallback_bands() -> None:
    """回退单一源分带:p1 空窗带=四体系全集;p2plus=兜底档;两域
    (shop/entry)共用本函数,禁第二源。"""
    ist = IntentionState()
    st_gap = _state(bench=[])                     # 空板:支持度 0 < 门槛
    members, band = cw_intention.k_empty_window_fallback(st_gap, ist)
    assert band == 'p1_gap' and members, '空窗带必须给四体系引擎件全集'
    st_p2 = _state(plane=2, round_num=1)
    members2, band2 = cw_intention.k_empty_window_fallback(st_p2, ist)
    assert band2 == 'p2plus' and members2, 'P2+ 带必须给兜底方向'


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__]))
